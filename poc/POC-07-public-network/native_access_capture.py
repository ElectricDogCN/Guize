"""Run observed requests against the disposable loopback access fixture."""

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from os import getpid
from pathlib import Path
import ssl
import subprocess
import sys
from urllib.parse import urlsplit

from capture_playback import (
    Capture, CaptureLimitExceeded, capture_anonymous_origin_response, capture_resource_denial, capture_response, utc_stamp,
)

SCRIPT = Path(__file__).resolve()
CLOCKS = ("started_at", "connected_at", "request_started_at", "first_response_at", "finished_at")


class CaptureError(ValueError):
    """A capture failure whose message is safe to pass between processes."""


def playback_port(target: str, path: str) -> int:
    parts = urlsplit(target)
    if (
        parts.scheme != "https" or parts.hostname != "localhost" or parts.path != path
        or parts.username is not None or parts.password is not None or parts.query or parts.fragment
        or not parts.port or parts.netloc != f"localhost:{parts.port}"
    ):
        raise CaptureError("Expected the fixed loopback playback endpoint")
    return parts.port


def write_bytes(path: Path, content: bytes) -> None:
    with path.open("xb") as output:
        output.write(content)


def json_bytes(data: dict) -> bytes:
    return (json.dumps(data, default=utc_stamp) + "\n").encode("utf-8")


def capture_tls(args: argparse.Namespace, settings: dict) -> None:
    port = playback_port(args.target_origin, "")
    ca_file = args.tls_ca_file
    trust = ca_file.read_bytes()
    if trust.count(b"-----BEGIN CERTIFICATE-----") != 1:
        raise CaptureError("This loopback collector requires one pinned fixture certificate")
    anchor = "sha256:" + sha256(ssl.PEM_cert_to_DER_cert(trust.decode("ascii"))).hexdigest()
    request = settings["request"]
    capture = capture_response(port, ca_file, Path(settings["response"]), settings["maximum_body_bytes"], **request)
    if capture.certificate_sha256 != anchor or capture.verified_server_name != args.tls_verify_peer:
        raise CaptureError("The verified playback leaf differs from the pinned fixture")
    result = {
        "schemaVersion": 1, "kind": "local_access_tls_result", "connectionId": args.connection_id,
        "processId": capture.process_id, "entryOrigin": args.target_origin,
        "peerAddress": capture.peer_address, "peerPort": capture.peer_port,
        "serverName": capture.verified_server_name, "sni": capture.verified_server_name,
        "verifiedPeerName": capture.verified_server_name, "protocol": capture.protocol, "cipher": capture.cipher,
        "trustStoreBuild": ssl.OPENSSL_VERSION, "trustStoreSha256": "sha256:" + sha256(trust).hexdigest(),
        "certificateSha256": capture.certificate_sha256, "trustAnchorSha256": anchor,
        "chainFingerprints": [anchor], "verificationCode": 0, "hostnameVerificationCode": 0,
        "handshakeStartedAt": capture.started_at, "handshakeFinishedAt": capture.connected_at,
    }
    content = json_bytes(result)
    write_bytes(args.tls_output, content)
    write_bytes(Path(settings["receipt"]), json_bytes(asdict(capture)))
    sys.stdout.buffer.write(content)


def capture_http_request(args: argparse.Namespace, settings: dict) -> dict:
    target = urlsplit(args.target)
    port = target.port
    if not port or target.netloc != f"127.0.0.1:{port}" or target.query or target.fragment:
        raise CaptureError("Expected a direct loopback fixture endpoint")
    identifiers = {"request_id": args.request_id, "trace_id": args.trace_id}
    request = settings["request"]
    if target.path == "/dav/synthetic.bin":
        capture = capture_anonymous_origin_response(port, args.response, request["range_header"], **identifiers)
    else:
        capture = capture_resource_denial(port, target.path, args.response,
                                          authorization=request["authorization"], range_header=request.get("range_header"),
                                          **identifiers)
    return {"requestProcessId": getpid(), "requestCommand": sys.orig_argv, "capture": asdict(capture)}


def capture_tls_request(args: argparse.Namespace, settings: dict) -> dict:
    port = playback_port(args.target, "/synthetic.bin")
    tls_result = args.response.with_suffix(".tls.json")
    capture_receipt = args.response.with_suffix(".capture.json")
    stderr = args.response.with_suffix(".tls.stderr")
    tls_command = [
        sys.executable, "-B", str(SCRIPT), "--target-origin", f"https://localhost:{port}",
        "--connection-id", args.trace_id, "--tls-ca-file", settings["trust_store"],
        "--tls-verify-peer", "localhost", "--tls-verify-mode", "strict", "--tls-output", tls_result.as_posix(),
    ]
    child_input = {
        "response": str(args.response), "maximum_body_bytes": settings["maximum_body_bytes"],
        "receipt": str(capture_receipt),
        "request": settings["request"] | {"request_id": args.request_id, "trace_id": args.trace_id},
    }
    started = datetime.now(timezone.utc)
    process = subprocess.Popen(tls_command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout_bytes, stderr_bytes = process.communicate(json_bytes(child_input), timeout=20)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise CaptureError("The native loopback TLS collector timed out") from None
    if process.returncode != 0:
        detail = stderr_bytes.decode(errors="replace").strip()
        raise CaptureError(f"The native loopback TLS collector failed: {detail}")
    finished = datetime.now(timezone.utc)
    if tls_result.read_bytes() != stdout_bytes:
        raise CaptureError("Retained TLS stdout differs from the executed client")
    capture = json.loads(capture_receipt.read_bytes())
    if capture["process_id"] != process.pid:
        raise CaptureError("The response was not collected by the recorded TLS process")
    write_bytes(stderr, stderr_bytes)
    return {
        "requestProcessId": getpid(), "requestCommand": sys.orig_argv, "tlsCommand": tls_command,
        "tlsProcessId": process.pid, "tlsStartedAt": utc_stamp(started), "tlsFinishedAt": utc_stamp(finished),
        "tlsExitCode": process.returncode,
        "tlsResult": tls_result.name, "tlsResultSha256": "sha256:" + sha256(stdout_bytes).hexdigest(),
        "tlsStderr": stderr.name, "tlsStderrSha256": "sha256:" + sha256(stderr_bytes).hexdigest(),
        "capture": capture,
    }


def observe_access_request(
    target: str, response: Path, *, trust_store: Path | None = None, maximum_body_bytes: int = 0, **request,
) -> tuple[Capture, dict]:
    command = [
        sys.executable, "-B", str(SCRIPT), "--request-id", request.pop("request_id"),
        "--trace-id", request.pop("trace_id"), "--target", target,
        "--response", response.as_posix(),
    ]
    try:
        completed = subprocess.run(
            command, input=json_bytes({"trust_store": trust_store.as_posix() if trust_store is not None else None,
                                       "maximum_body_bytes": maximum_body_bytes,
                                       "request": request}), capture_output=True, timeout=25,
        )
    except subprocess.TimeoutExpired:
        raise CaptureError("The native access request collector timed out") from None
    if completed.returncode != 0 or completed.stderr:
        detail = completed.stderr.decode(errors="replace").strip()
        raise CaptureError(f"The native access request collector failed: {detail}")
    evidence = json.loads(completed.stdout)
    if evidence["requestCommand"] != command:
        raise CaptureError("The observed request command differs from the invoked command")
    evidence["requestExitCode"] = completed.returncode
    raw = evidence.pop("capture")
    capture = Capture(**(raw | {field: datetime.fromisoformat(raw[field]) for field in CLOCKS}))
    return capture, evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--request-id")
    mode.add_argument("--target-origin")
    parser.add_argument("--trace-id")
    parser.add_argument("--target")
    parser.add_argument("--response", type=Path)
    parser.add_argument("--connection-id")
    parser.add_argument("--tls-ca-file", type=Path)
    parser.add_argument("--tls-verify-peer", choices=["localhost"])
    parser.add_argument("--tls-verify-mode", choices=["strict"])
    parser.add_argument("--tls-output", type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(sys.stdin.buffer.readline(8193))
        if args.request_id and args.trace_id and args.target and args.response:
            evidence = (capture_http_request(args, data) if urlsplit(args.target).scheme == "http"
                        else capture_tls_request(args, data))
            sys.stdout.buffer.write(json_bytes(evidence))
        elif all((args.target_origin, args.connection_id, args.tls_ca_file, args.tls_verify_peer,
                  args.tls_verify_mode, args.tls_output)):
            capture_tls(args, data)
        else:
            raise CaptureError("Incomplete native fixture command")
    except (CaptureError, CaptureLimitExceeded) as error:
        parser.exit(1, f"{error}\n")
    except (OSError, ValueError, TypeError, KeyError) as error:
        parser.exit(1, f"Native loopback capture failed: {type(error).__name__}\n")


if __name__ == "__main__":
    main()
