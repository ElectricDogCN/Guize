"""Collect playback and resource access observations in one local execution window."""

from datetime import datetime, timezone
from hashlib import file_digest
import json
from pathlib import Path

from access_evidence import retain, retain_access_artifacts, retain_access_report
from capture_playback import utc_stamp
from run_local_replay import argument_parser, run
from run_local_resource_replay import read_origin_identities, read_output_fixture, replay


def receipt(path: Path, root: Path) -> dict:
    with path.open("rb") as stream:
        digest = file_digest(stream, "sha256").hexdigest()
    return {"ref": path.relative_to(root).as_posix(), "sha256": "sha256:" + digest}


def main() -> None:
    parser = argument_parser()
    parser.description = __doc__
    parser.add_argument("--resource-port", type=int, required=True)
    parser.add_argument("--output-fixture", type=Path, required=True)
    args = parser.parse_args()
    ports = {args.origin_port, args.playback_port, args.resource_port}
    if len(ports) != 3 or any(not 1 <= port <= 65535 for port in ports):
        parser.error("Expected three distinct, fixed loopback ports")
    try:
        fixture = read_output_fixture(args.output_fixture)
        identities = read_origin_identities({"playback", "management", "worker"})
        origin_authorization = identities.pop("playback")
        root = args.output
        root.mkdir()
        args.output = root / "playback"
        start = datetime.now(timezone.utc)
        playback = run(args, origin_authorization=origin_authorization)
        resources = root / "resources"
        resource_results = replay(
            args.origin_port, identities, fixture, resources, entry_port=args.resource_port,
            native_transport=args.native_transport,
            protected_range=playback["cacheRange"] if args.transport_context else None,
        )
        finish = datetime.now(timezone.utc)
        result = {
            "startedAt": utc_stamp(start), "finishedAt": utc_stamp(finish), "sample": playback["sample"],
            "originPort": args.origin_port, "playbackPort": args.playback_port, "resourcePort": args.resource_port,
            "playback": receipt(args.output / "replay-result.json", root),
            "resources": receipt(resources / "resource-replay.json", root),
        }
        command_output = root / "access-replay.json"
        if args.transport_context is not None:
            report = retain_access_report(root, playback, resource_results)
            result["accessOutcome"] = receipt(Path(report), root)
        retain(command_output, result)
        if args.transport_context is not None:
            retain_access_artifacts(root / "raw-artifacts.json", report, command_output, args.certificate)
        print(json.dumps(result, separators=(",", ":")))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
