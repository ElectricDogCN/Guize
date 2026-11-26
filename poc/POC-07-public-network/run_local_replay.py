"""Run the local fixture replay against an already prepared loopback OpenList."""

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import file_digest
from hmac import compare_digest
import json
from pathlib import Path
import re
import secrets
import ssl
import sys

from capture_playback import utc_stamp
from playback_gateway import PlaybackAuthorization, PlaybackPolicy, playback_gateway
from replay_fixture import replay_fixture
from stream_fixture import FixtureSource
from verify_fixture import verify_fixture

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "POC-03-ats-range"))
from grants import Grant, utc_instant

PREFLIGHT_BYTES = 2_097_189
PREFLIGHT_SHA256 = "dd6a5c8b02ef6c8c3bbe7c1132948d3fb949bb6dbd234e9f7d23c7a1b42a6cad"
CONTEXT_FIELDS = {"configurationRef", "pathConfigurationRef", "resourceId", "acceptanceProfile", "subjectVersion",
                  "inputSamples", "assetId", "sourceVersion", "aclVersion", "inputSampleId"}


def playback_grants(schedule: dict[str, str] | None, now: datetime) -> tuple[Grant, Grant]:
    if schedule is None:
        schedule = {
            "grantValidFrom": now.isoformat(),
            "grantValidUntil": (now + timedelta(minutes=5)).isoformat(),
            "expiredAt": (now - timedelta(minutes=1)).isoformat(),
        }
    if not isinstance(schedule, dict) or schedule.keys() != {"grantValidFrom", "grantValidUntil", "expiredAt"}:
        raise ValueError("Expected the fixed playback grant schedule")
    start, end, expired_at = (utc_instant(schedule[key]) for key in ("grantValidFrom", "grantValidUntil", "expiredAt"))
    if not start <= now < end or expired_at > now:
        raise ValueError("Playback must start with a live grant and an already expired grant")
    return (
        Grant("current", "sample-owner", start.isoformat(), end.isoformat()),
        Grant("expired", "sample-owner", (expired_at - timedelta(minutes=1)).isoformat(), expired_at.isoformat()),
    )


def verify_preflight_sample(path: Path) -> dict[str, str | int]:
    if path.stat().st_size != PREFLIGHT_BYTES:
        raise ValueError("The preflight fixture has an unexpected size")
    with path.open("rb") as sample:
        digest = file_digest(sample, "sha256").hexdigest()
    if digest != PREFLIGHT_SHA256:
        raise ValueError("The preflight fixture does not match the recorded synthetic bytes")
    return {"sampleId": "local-playback-preflight", "byteCount": PREFLIGHT_BYTES, "checksum": "sha256:" + digest}


def run(args: argparse.Namespace, *, origin_authorization: str | None = None) -> dict:
    sample = verify_preflight_sample(args.fixture) if args.preflight else verify_fixture(args.fixture)
    context = None
    if args.transport_context is not None:
        if not args.native_transport:
            raise ValueError("Transport context requires native request capture")
        context = json.loads(args.transport_context.read_bytes())
        if (not isinstance(context, dict) or context.keys() != CONTEXT_FIELDS
                or context["inputSampleId"] != sample["sampleId"] or not isinstance(context["inputSamples"], list)
                or sum(isinstance(row, dict) and row.get("id") == sample["sampleId"]
                       and row.get("checksum") == sample["checksum"] for row in context["inputSamples"]) != 1):
            raise ValueError("Transport context must bind the selected synthetic sample")
    source = FixtureSource(
        args.origin_port, "synthetic.bin", int(sample["byteCount"]), str(sample["checksum"]).removeprefix("sha256:")
    )
    policy = PlaybackPolicy((args.cache_first, args.cache_last + 1), args.request_limit, args.window_seconds)
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.minimum_version = ssl.TLSVersion.TLSv1_3
    tls.load_cert_chain(args.certificate, args.certificate_key)

    if args.output.exists():
        raise ValueError("The capture destination already exists")
    if origin_authorization is None:
        origin_authorization = sys.stdin.readline(1025).rstrip("\r\n")
    if not re.fullmatch(r"Basic [A-Za-z0-9+/]{1,1008}={0,2}", origin_authorization):
        raise ValueError("Expected one temporary OpenList reader credential on standard input")

    schedule = None if args.grant_schedule is None else json.loads(args.grant_schedule.read_bytes())
    if args.grant_schedule is not None and schedule is None:
        raise ValueError("Expected the fixed playback grant schedule")
    active, expired = playback_grants(schedule, datetime.now(timezone.utc))
    owner, stale, other = ("Bearer " + secrets.token_urlsafe(24) for _ in range(3))
    subjects = ((owner, "sample-owner", active), (stale, "sample-owner", expired), (other, "other-sample-user", active))

    def authorize(presented: str, observed_at: datetime) -> PlaybackAuthorization:
        if presented.isascii():
            for credential, principal, grant in subjects:
                if compare_digest(presented, credential):
                    return PlaybackAuthorization(grant.decision(principal, observed_at.isoformat()),
                                                 principal, grant.grant_id)
        return PlaybackAuthorization("missing_identity")

    observations = []
    with playback_gateway(source, origin_authorization, authorize, tls, policy, observations.append,
                          port=args.playback_port) as port:
        result = replay_fixture(source, args.fixture, port, args.certificate, policy, args.output, observations,
                                owner=owner, expired=stale, other_identity=other, native_transport=args.native_transport,
                                transport_context=context)
    result.update(operation="local_fixture_replay", sample=sample, preflight=args.preflight, gatewayStopped=True)
    result["playbackGrantPolicy"] = {
        "authorizedUserId": active.principal, "deniedUserId": subjects[2][1],
        "authorizedGrantId": active.grant_id, "deniedGrantId": active.grant_id, "expiredGrantId": expired.grant_id,
        "grantValidFrom": utc_stamp(utc_instant(active.valid_from)),
        "grantValidUntil": utc_stamp(utc_instant(active.valid_until)),
        "expiredAt": utc_stamp(utc_instant(expired.valid_until)),
    }
    with (args.output / "replay-result.json").open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
        output.write("\n")
    return result


def argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--origin-port", type=int, required=True)
    parser.add_argument("--playback-port", type=int, required=True)
    parser.add_argument("--certificate", type=Path, required=True)
    parser.add_argument("--certificate-key", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache-first", type=int, required=True)
    parser.add_argument("--cache-last", type=int, required=True)
    parser.add_argument("--request-limit", type=int, required=True)
    parser.add_argument("--window-seconds", type=float, required=True)
    parser.add_argument("--grant-schedule", type=Path, help="Fixed UTC playback grant times for local evidence")
    parser.add_argument("--native-transport", action="store_true", help="Record actual per-request and TLS subprocesses")
    parser.add_argument("--transport-context", type=Path, help="Bind native access evidence to a fixed context")
    parser.add_argument("--preflight", action="store_true", help="Select the fixed small synthetic fixture")
    return parser


def main() -> None:
    parser = argument_parser()
    args = parser.parse_args()
    if not 0 <= args.playback_port <= 65535 or (args.playback_port == 0 and not args.preflight):
        parser.error("Supply a fixed loopback playback port, or use port 0 for preflight")
    try:
        result = run(args)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps({"playbackCasesVerified": len(result["caseResults"]), "originDenialStatus": result["originDenial"]["status"]}))


if __name__ == "__main__":
    main()
