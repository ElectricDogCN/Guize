"""Collect the ordinary local playback cases and verify their retained HTTP responses."""

from dataclasses import asdict
from hashlib import file_digest, sha256
import json
from pathlib import Path
from shutil import copyfileobj
import ssl
import sys
import time
from uuid import uuid4

from capture_playback import capture_anonymous_origin_response, capture_response, utc_stamp
from native_access_capture import observe_access_request
from playback_gateway import PlaybackObservation, PlaybackPolicy
from stream_fixture import CHUNK_BYTES, FixtureSource

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from specs.poc.check_program import retained_access_http_response


def retain_response_body(path: Path, headers: dict[str, str], byte_count: int, digest: str) -> str:
    """Retain the verifier's fixed-length body as a separate, verbatim artifact."""
    if "transfer-encoding" in headers or headers.get("content-length", "0") != str(byte_count):
        raise ValueError("This fixture replay requires a fixed-length response")
    body = path.with_suffix(".body")
    with path.open("rb") as response, body.open("xb") as destination:
        response.seek(-byte_count, 2)
        copyfileobj(response, destination, length=CHUNK_BYTES)
    with body.open("rb") as verified:
        observed = sha256()
        size = 0
        while block := verified.read(CHUNK_BYTES):
            size += len(block)
            observed.update(block)
    if (size, "sha256:" + observed.hexdigest()) != (byte_count, digest):
        raise ValueError("The retained body differs from the native response")
    return body.name


def retain_rate_attempts(directory: Path, context: dict, attempts: list[dict]) -> list[str]:
    """Translate actual consecutive warm-cache requests into the local rate verifier format."""
    script = Path(attempts[0]["nativeTransport"]["requestCommand"][2])
    with script.open("rb") as observer:
        observer_build = "sha256:" + file_digest(observer, "sha256").hexdigest()
    retained = []
    for sequence, attempt in enumerate(attempts, start=1):
        if attempt["completedSourceTransfers"] or not all((attempt["userId"], attempt["grantId"], attempt["cacheKey"])):
            raise ValueError("Rate observation requires the authenticated warm cache scope and no source read")
        native = attempt["nativeTransport"]
        command = native["requestCommand"]
        if Path(command[-1]) != directory / attempt["rawResponse"]:
            raise ValueError("Rate observation command does not bind the retained HTTP response")
        identifiers = {key: attempt[key] for key in ("requestId", "traceId")}
        start, finish = attempt["clientRequestStartedAt"], attempt["clientFinishedAt"]
        request = {key: attempt[key] for key in ("userId", "grantId", "requestRange", "ifRange", "cacheKey")}
        request["ifRange"] = request["ifRange"] or ""
        trace = {
            "schemaVersion": 1, "kind": "local_access_rate_transport_trace", "context": context,
            "sequence": sequence, **identifiers, "observerBuild": observer_build, "commandArgs": command,
            "pid": native["requestProcessId"], "startedAt": start, "finishedAt": finish,
            "exitCode": native["requestExitCode"],
            "responseRef": command[-1], "responseSha256": attempt["rawResponseSha256"],
            "responseBodyRef": (directory / attempt["responseBody"]).as_posix(),
            "events": [
                {"type": "request", "observedAt": start, **identifiers, **request, "requestURL": command[-3],
                 "httpMethod": "GET"},
                {"type": "exit", "observedAt": finish, **identifiers, "exitCode": native["requestExitCode"]},
            ],
        }
        path = directory / f"{attempt['case']}.rate.json"
        with path.open("x", encoding="utf-8") as output:
            json.dump(trace, output, indent=2)
            output.write("\n")
        retained.append(path.name)
    return retained


def replay_fixture(
    source: FixtureSource,
    fixture: Path,
    playback_port: int,
    trust_store: Path,
    policy: PlaybackPolicy,
    directory: Path,
    observations: list[PlaybackObservation],
    *,
    owner: str,
    expired: str,
    other_identity: str,
    native_transport: bool = False,
    transport_context: dict | None = None,
) -> dict:
    """Capture a fixed set of cases against a running disposable gateway and OpenList."""
    if source.filename != "synthetic.bin":
        raise ValueError("This replay requires the fixed OpenList fixture route")
    trust_bytes = trust_store.read_bytes()
    certificate = ssl.PEM_cert_to_DER_cert(trust_bytes.decode("ascii"))
    certificate_identity = "sha256:" + sha256(certificate).hexdigest()
    directory.mkdir(exist_ok=False)
    first, stop = policy.cache_interval
    byte_range = f"bytes={first}-{stop - 1}"
    content_range = f"bytes {first}-{stop - 1}/{source.byte_count}"
    with fixture.open("rb") as contents:
        contents.seek(first)
        selected = contents.read(stop - first)
    if len(selected) != stop - first:
        raise ValueError("The selected fixture interval is incomplete")
    range_digest = "sha256:" + sha256(selected).hexdigest()
    fixture_digest = "sha256:" + source.sha256_hex
    empty_digest = "sha256:" + sha256(b"").hexdigest()

    def request(
        label: str,
        status: int,
        **request_options,
    ) -> dict:
        full = status == 200
        count = source.byte_count if full else len(selected) if status == 206 else 0
        expected_digest = fixture_digest if full else range_digest if status == 206 else empty_digest
        path = directory / f"{label}.http"
        previous = len(observations)
        request_id, trace_id = uuid4().hex, uuid4().hex
        options = {"request_id": request_id, "trace_id": trace_id, **request_options}
        if native_transport:
            capture, native = observe_access_request(
                f"https://localhost:{playback_port}/synthetic.bin", path,
                trust_store=trust_store, maximum_body_bytes=count, **options,
            )
        else:
            capture = capture_response(playback_port, trust_store, path, count, **options)
            native = None
        actual_status, headers, bytes_received, observed_digest = retained_access_http_response(path)
        if (actual_status, bytes_received, observed_digest) != (status, count, expected_digest):
            raise ValueError(f"{label} returned unexpected status or fixture bytes")
        if (
            capture.protocol != "TLSv1.3"
            or capture.verified_server_name != "localhost"
            or capture.certificate_sha256 != certificate_identity
            or headers.get("content-range") != (content_range if status == 206 else None)
        ):
            raise ValueError(f"{label} returned unexpected TLS or Content-Range")
        if status in (200, 206) and headers.get("etag") != source.etag:
            raise ValueError(f"{label} returned an unexpected fixture validator")
        if len(observations) != previous + 1 or observations[-1].status != actual_status:
            raise ValueError(f"{label} has no matching gateway observation")
        outcome = observations[-1]
        if (
            (outcome.request_id, outcome.trace_id) != (request_id, trace_id)
            or not capture.connected_at <= capture.request_started_at <= outcome.observed_at <= capture.finished_at
        ):
            raise ValueError(f"{label} does not bind the captured request to its gateway observation")
        if outcome.transfer is not None and (
            outcome.transfer.byte_count != count or outcome.transfer.sha256 != observed_digest
            or outcome.transfer.peak_read_bytes > CHUNK_BYTES
        ):
            raise ValueError(f"{label} returned an inconsistent source observation")
        if outcome.transfer is not None:
            cursor = 0 if full else first
            last_seen = outcome.source_requested_at
            if last_seen is None or last_seen < outcome.observed_at:
                raise ValueError(f"{label} has no observed source request")
            for read in outcome.reads:
                if read.offset != cursor or read.byte_count <= 0 or not last_seen <= read.observed_at <= capture.finished_at:
                    raise ValueError(f"{label} has a discontinuous source read")
                cursor += read.byte_count
                last_seen = read.observed_at
            if cursor != (source.byte_count if full else stop):
                raise ValueError(f"{label} source reads do not cover the exact response interval")
        result = {
            **capture.transport_observation(),
            "case": label,
            "requestId": request_id,
            "traceId": trace_id,
            "status": actual_status,
            "bodyByteCount": bytes_received,
            "bodySha256": observed_digest,
            "responseBody": retain_response_body(path, headers, bytes_received, observed_digest),
            "rawResponse": path.name,
            "rawResponseSha256": capture.raw_sha256,
            "rawResponseByteCount": capture.raw_byte_count,
            "clientStartedAt": utc_stamp(capture.started_at),
            "clientConnectedAt": utc_stamp(capture.connected_at),
            "clientFinishedAt": utc_stamp(capture.finished_at),
            "peerAddress": capture.peer_address,
            "peerPort": capture.peer_port,
            "tls": capture.protocol,
            "cipher": capture.cipher,
            "certificateSha256": capture.certificate_sha256,
            "gatewayObservedAt": utc_stamp(outcome.observed_at),
            "sourceRequestedAt": utc_stamp(outcome.source_requested_at) if outcome.source_requested_at else None,
            "gatewayDecision": outcome.decision,
            "userId": outcome.user_id,
            "grantId": outcome.grant_id,
            "cacheKey": outcome.cache_key,
            "requestRange": outcome.range_header,
            "ifRange": outcome.if_range,
            "cacheHit": outcome.cache_hit,
            "completedSourceTransfers": int(outcome.transfer is not None),
            "sourceReadPeakBytes": outcome.transfer.peak_read_bytes if outcome.transfer else 0,
            "sourceReads": [asdict(read) | {"observed_at": utc_stamp(read.observed_at)} for read in outcome.reads],
        }
        if native is not None:
            result["nativeTransport"] = native
        return result

    allowed = {"authorization": owner}
    protected_range = {"range_header": byte_range}
    prime = request("range", 206, **allowed, **protected_range)
    if policy.request_limit == 1:
        time.sleep(policy.window_seconds)
    matching = request("if-range", 206, **allowed, **protected_range, if_range=source.etag)
    denied = [
        request(label, 403, **protected_range, authorization=authorization)
        for label, authorization in (("anonymous", None), ("expired", expired), ("other-identity", other_identity))
    ]
    if prime["cacheHit"] or prime["completedSourceTransfers"] != 1 or not matching["cacheHit"]:
        raise ValueError("The initial range must reach OpenList and the matching request must use the warm cache")
    if [row["gatewayDecision"] for row in denied] != ["missing_identity", "expired", "principal_mismatch"]:
        raise ValueError("The denial cases did not exercise the expected grant states")
    if any(row["cacheHit"] or row["completedSourceTransfers"] for row in denied):
        raise ValueError("A denied playback request used the cache or the source")

    time.sleep(policy.window_seconds)
    full = request("full", 200, **allowed)
    if full["cacheHit"] or full["completedSourceTransfers"] != 1 or not full["sourceReads"]:
        raise ValueError("Full playback did not stream from the source")

    time.sleep(policy.window_seconds)
    start = time.monotonic()
    burst = [request(f"burst-{step}", 206, **allowed, **protected_range) for step in range(1, policy.request_limit + 1)]
    throttled = request("burst-limited", 429, **allowed, **protected_range)
    elapsed = time.monotonic() - start
    if elapsed > policy.window_seconds or any(not row["cacheHit"] or row["completedSourceTransfers"] for row in burst):
        raise ValueError("The bounded replay did not stay within one warm cache rate window")
    if throttled["gatewayDecision"] != "rate_limited" or throttled["cacheHit"] or throttled["completedSourceTransfers"]:
        raise ValueError("The throttled request accessed the cache or the source")
    rate_receipts = {}
    if transport_context is not None:
        rate_receipts["rateTransport"] = retain_rate_attempts(directory, transport_context, [*burst, throttled])

    origin_file = directory / "origin-anonymous.http"
    origin_request_id, origin_trace_id = uuid4().hex, uuid4().hex
    origin_ids = {"request_id": origin_request_id, "trace_id": origin_trace_id}
    origin_native = {}
    if native_transport:
        origin, receipt = observe_access_request(
            f"http://127.0.0.1:{source.port}/dav/synthetic.bin", origin_file, range_header=byte_range, **origin_ids,
        )
        origin_native["nativeTransport"] = receipt
    else:
        origin = capture_anonymous_origin_response(source.port, origin_file, byte_range, **origin_ids)
    status, headers, count, digest = retained_access_http_response(origin_file)
    if status not in (401, 403) or count or digest != empty_digest:
        raise ValueError("The anonymous OpenList source returned an unexpected response")
    return {
        "caseResults": [prime, matching, *denied, full, *burst, throttled],
        "fixtureByteCount": source.byte_count,
        "fixtureSha256": fixture_digest,
        "cacheRange": byte_range,
        "requestLimit": policy.request_limit,
        "windowSeconds": policy.window_seconds,
        "burstElapsedSeconds": elapsed,
        "trustStoreSha256": "sha256:" + sha256(trust_bytes).hexdigest(),
        "tlsLeafSha256": certificate_identity,
        **rate_receipts,
        "originDenial": {
            **origin.transport_observation(),
            **origin_native,
            "requestId": origin_request_id,
            "traceId": origin_trace_id,
            "status": status,
            "bodyByteCount": count,
            "bodySha256": digest,
            "responseBody": retain_response_body(origin_file, headers, count, digest),
            "rawResponse": origin_file.name,
            "rawResponseSha256": origin.raw_sha256,
            "rawResponseByteCount": origin.raw_byte_count,
            "clientStartedAt": utc_stamp(origin.started_at),
            "clientConnectedAt": utc_stamp(origin.connected_at),
            "clientFinishedAt": utc_stamp(origin.finished_at),
            "peerAddress": origin.peer_address,
            "peerPort": origin.peer_port,
        },
    }
