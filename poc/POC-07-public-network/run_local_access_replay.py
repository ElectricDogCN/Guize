"""Collect playback and resource access observations in one local execution window."""

from datetime import datetime, timezone
from hashlib import file_digest
import json
from pathlib import Path

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
        replay(args.origin_port, identities, fixture, resources, entry_port=args.resource_port)
        finish = datetime.now(timezone.utc)
        result = {
            "startedAt": start.isoformat(), "finishedAt": finish.isoformat(), "sample": playback["sample"],
            "originPort": args.origin_port, "playbackPort": args.playback_port, "resourcePort": args.resource_port,
            "playback": receipt(args.output / "replay-result.json", root),
            "resources": receipt(resources / "resource-replay.json", root),
        }
        with (root / "access-replay.json").open("x", encoding="utf-8") as output:
            json.dump(result, output, indent=2)
            output.write("\n")
        print(json.dumps(result, separators=(",", ":")))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
