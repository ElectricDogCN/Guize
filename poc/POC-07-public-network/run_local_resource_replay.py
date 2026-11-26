"""Validate management and Worker output separately from the playback fixture."""

import argparse
from contextlib import nullcontext
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest
from http.client import HTTPConnection
import json
from pathlib import Path
import secrets
import sys
from tempfile import TemporaryDirectory
from uuid import uuid4

from capture_playback import capture_resource_denial, utc_stamp
from native_access_capture import observe_access_request
from replay_fixture import retain_response_body, retained_access_http_response
from resource_gateway import ProtectedResource, ResourceDecision, resource_gateway

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "POC-03-ats-range"))
from grants import Grant

MAXIMUM_BODY_BYTES = 64 * 1024


def get(port: int, path: str, authorization: str) -> tuple[int, bytes]:
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", path, headers={"Authorization": authorization})
        response = connection.getresponse()
        body = response.read(MAXIMUM_BODY_BYTES + 1)
        if len(body) > MAXIMUM_BODY_BYTES:
            raise ValueError("Fixture response exceeded its approved capture size")
        return response.status, body
    finally:
        connection.close()


def retain_denial(
    port: int, path: str, output: Path, identity: str, decisions: list[ResourceDecision],
    *, native_transport: bool = False, protected_range: str | None = None,
) -> tuple[int, bytes, dict]:
    request_id, trace_id = uuid4().hex, uuid4().hex
    previous = len(decisions)
    native = {}
    request = {"request_id": request_id, "trace_id": trace_id, "range_header": protected_range}
    capture_directory = nullcontext(output.parent) if native_transport else TemporaryDirectory(dir=output.parent)
    with capture_directory as directory:
        candidate = Path(directory) / output.name
        if native_transport:
            capture, receipt = observe_access_request(
                f"http://127.0.0.1:{port}{path}", candidate, authorization=identity, **request,
            )
            native["nativeTransport"] = receipt
        else:
            capture = capture_resource_denial(port, path, candidate, authorization=identity, **request)
        status, headers, count, digest = retained_access_http_response(candidate)
        if status != 403 or count != 0:
            raise ValueError("A resource denial did not return the expected empty HTTP 403 response")
        observed = decisions[previous:]
        if len(observed) != 1:
            raise ValueError("Expected exactly one gateway decision for the resource request")
        decision = observed[0]
        if (
            (decision.route, decision.request_id, decision.trace_id, decision.allowed)
            != (path, request_id, trace_id, False)
            or decision.range_header != protected_range
            or not capture.connected_at <= capture.request_started_at <= decision.observed_at <= capture.first_response_at
        ):
            raise ValueError("The captured denial and actual gateway decision do not match")
        body = retain_response_body(candidate, headers, count, digest)
        if not native_transport:
            candidate.rename(output)
            candidate.with_name(body).rename(output.with_name(body))
    observation = asdict(capture)
    for key in ("started_at", "connected_at", "finished_at", "request_started_at", "first_response_at"):
        observation[key] = utc_stamp(observation[key])
    return status, b"", {
        **observation, **native, "requestId": request_id, "traceId": trace_id, "route": path,
        "authorizationObservedAt": utc_stamp(decision.observed_at), "requestRange": decision.range_header,
        "statusCode": status, "rawResponse": output.name, "responseBody": body,
        "responseByteCount": count, "responseSha256": digest,
    }


def replay(
    origin_port: int, origin_auth: dict[str, str], fixture: bytes, evidence_dir: Path | None = None,
    *, entry_port: int = 0, native_transport: bool = False, protected_range: str | None = None,
) -> dict:
    credentials = {role: "Bearer " + secrets.token_urlsafe(24) for role in ("admin", "worker", "reader")}
    now = datetime.now(timezone.utc)
    grant = Grant("local-output-fixture", "worker-fixture", now.isoformat(),
                  (now + timedelta(minutes=2)).isoformat())
    origin_reads = {"management": 0, "worker": 0}

    def read_management() -> bytes:
        origin_reads["management"] += 1
        status, result = get(origin_port, "/api/admin/storage/list", origin_auth["management"])
        document = json.loads(result)
        if status != 200 or not isinstance(document, dict) or document.get("code") != 200:
            raise ValueError("OpenList did not return the authorized management data")
        return result

    def read_output() -> bytes:
        origin_reads["worker"] += 1
        status, result = get(origin_port, "/dav/output.bin", origin_auth["worker"])
        if status != 200 or result != fixture:
            raise ValueError("OpenList did not return the expected Worker fixture")
        return result

    def management_allowed(presented: str, _: datetime) -> bool:
        return presented.isascii() and compare_digest(presented, credentials["admin"])

    def output_allowed(presented: str, observed: datetime) -> bool:
        return (presented.isascii() and compare_digest(presented, credentials["worker"])
                and grant.decision("worker-fixture", observed.isoformat()) == "allowed")

    management = ProtectedResource(management_allowed, read_management, "application/json")
    output = ProtectedResource(output_allowed, read_output, "application/octet-stream")
    captures = {}
    decisions: list[ResourceDecision] = []
    if evidence_dir is not None:
        evidence_dir.mkdir()

    def observe_reader(port: int, path: str, name: str) -> tuple[int, bytes]:
        if evidence_dir is None:
            return get(port, path, credentials["reader"])
        status, body, capture = retain_denial(
            port, path, evidence_dir / f"{name}.http", credentials["reader"], decisions,
            native_transport=native_transport, protected_range=protected_range,
        )
        captures[name] = capture
        return status, body

    with resource_gateway(management, output, port=entry_port, observe=decisions.append) as port:
        management_status, _ = get(port, "/management/storage", credentials["admin"])
        output_status, output_body = get(port, "/worker/output.bin", credentials["worker"])
        reader_management = observe_reader(port, "/management/storage", "direct_admin")
        reader_output = observe_reader(port, "/worker/output.bin", "direct_worker")

    if management_status != 200 or output_status != 200 or output_body != fixture:
        raise ValueError("Authorized resource requests did not reach the expected fixtures")
    if reader_management != (403, b"") or reader_output != (403, b"") or any(v != 1 for v in origin_reads.values()):
        raise ValueError("A reader outside the management and Worker scopes reached a protected origin")
    result = {
        "managementOwnerStatus": management_status, "outputGrantStatus": output_status,
        "outputGrantBytes": len(output_body), "outputGrantSha256": sha256(output_body).hexdigest(),
        "readerManagementStatus": reader_management[0], "readerManagementBytes": len(reader_management[1]),
        "readerOutputStatus": reader_output[0], "readerOutputBytes": len(reader_output[1]),
        "upstreamReads": origin_reads,
    }
    if evidence_dir is not None:
        result["retainedDenials"] = captures
        (evidence_dir / "resource-replay.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def read_output_fixture(path: Path) -> bytes:
    with path.open("rb") as sample:
        fixture = sample.read(MAXIMUM_BODY_BYTES + 1)
    if not 0 < len(fixture) <= MAXIMUM_BODY_BYTES:
        raise ValueError("Expected a bounded Worker output fixture")
    return fixture


def read_origin_identities(roles: set[str]) -> dict[str, str]:
    identities = json.loads(sys.stdin.readline(8192))
    if not isinstance(identities, dict) or identities.keys() != roles or any(
        not isinstance(value, str) or not value or not value.isascii() or "\r" in value or "\n" in value
        for value in identities.values()
    ):
        raise ValueError("Expected the configured temporary OpenList identities on standard input")
    return identities


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin-port", type=int, required=True)
    parser.add_argument("--output-fixture", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, help="New directory for the two denial responses and their receipt")
    parser.add_argument("--native-transport", action="store_true", help="Record actual per-request subprocesses")
    args = parser.parse_args()
    if not 1 <= args.origin_port <= 65535:
        parser.error("Expected the private OpenList loopback port")
    if args.native_transport and args.evidence_dir is None:
        parser.error("Native request capture requires an evidence directory")
    try:
        fixture = read_output_fixture(args.output_fixture)
        origin_auth = read_origin_identities({"management", "worker"})
        result = replay(args.origin_port, origin_auth, fixture, args.evidence_dir, native_transport=args.native_transport)
        print(json.dumps(result, separators=(",", ":")))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
