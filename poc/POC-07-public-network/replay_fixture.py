"""Collect the ordinary local playback cases and verify their retained HTTP responses."""

from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
from shutil import copyfileobj
import sys
import time

from capture_playback import capture_anonymous_origin_response, capture_response
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
) -> dict:
    """Capture a fixed set of cases against a running disposable gateway and OpenList."""
    if source.filename != "synthetic.bin":
        raise ValueError("This replay requires the fixed OpenList fixture route")
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
        capture = capture_response(playback_port, trust_store, path, count, **request_options)
        actual_status, headers, bytes_received, observed_digest = retained_access_http_response(path)
        if (actual_status, bytes_received, observed_digest) != (status, count, expected_digest):
            raise ValueError(f"{label} returned unexpected status or fixture bytes")
        if capture.protocol != "TLSv1.3" or headers.get("content-range") != (content_range if status == 206 else None):
            raise ValueError(f"{label} returned unexpected TLS or Content-Range")
        if status in (200, 206) and headers.get("etag") != source.etag:
            raise ValueError(f"{label} returned an unexpected fixture validator")
        if len(observations) != previous + 1 or observations[-1].status != actual_status:
            raise ValueError(f"{label} has no matching gateway observation")
        outcome = observations[-1]
        if outcome.transfer is not None and (
            outcome.transfer.byte_count != count or outcome.transfer.sha256 != observed_digest
            or outcome.transfer.peak_read_bytes > CHUNK_BYTES
        ):
            raise ValueError(f"{label} returned an inconsistent source observation")
        if outcome.transfer is not None:
            cursor = 0 if full else first
            for read in outcome.reads:
                if read.offset != cursor or read.byte_count <= 0:
                    raise ValueError(f"{label} has a discontinuous source read")
                cursor += read.byte_count
            if cursor != (source.byte_count if full else stop):
                raise ValueError(f"{label} source reads do not cover the exact response interval")
        return {
            "case": label,
            "status": actual_status,
            "bodyByteCount": bytes_received,
            "bodySha256": observed_digest,
            "responseBody": retain_response_body(path, headers, bytes_received, observed_digest),
            "rawResponse": path.name,
            "rawResponseSha256": capture.raw_sha256,
            "rawResponseByteCount": capture.raw_byte_count,
            "clientStartedAt": capture.started_at.isoformat(),
            "clientConnectedAt": capture.connected_at.isoformat(),
            "clientFinishedAt": capture.finished_at.isoformat(),
            "tls": capture.protocol,
            "cipher": capture.cipher,
            "gatewayObservedAt": outcome.observed_at.isoformat(),
            "gatewayDecision": outcome.decision,
            "requestRange": outcome.range_header,
            "ifRange": outcome.if_range,
            "cacheHit": outcome.cache_hit,
            "completedSourceTransfers": int(outcome.transfer is not None),
            "sourceReadPeakBytes": outcome.transfer.peak_read_bytes if outcome.transfer else 0,
            "sourceReads": [asdict(read) | {"observed_at": read.observed_at.isoformat()} for read in outcome.reads],
        }

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

    origin_file = directory / "origin-anonymous.http"
    origin = capture_anonymous_origin_response(source.port, origin_file, byte_range)
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
        "originDenial": {
            "status": status,
            "bodyByteCount": count,
            "bodySha256": digest,
            "responseBody": retain_response_body(origin_file, headers, count, digest),
            "rawResponse": origin_file.name,
            "rawResponseSha256": origin.raw_sha256,
            "rawResponseByteCount": origin.raw_byte_count,
        },
    }
