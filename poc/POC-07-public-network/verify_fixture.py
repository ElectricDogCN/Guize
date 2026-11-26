"""Verify the reusable synthetic sample before seeking POC-007 approval."""

import argparse
import hashlib
import json
from pathlib import Path

SAMPLE_BYTES = 67_108_864
SAMPLE_SHA256 = "9a30d2bb1a4f1eabcb41baa5b6518628411ba8ac668fc1e7085983261aa5f419"


def verify_fixture(path: Path) -> dict[str, str | int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            size += len(chunk)
            if size > SAMPLE_BYTES:
                raise ValueError("Candidate fixture exceeds the recorded size")
            digest.update(chunk)
    if size != SAMPLE_BYTES or digest.hexdigest() != SAMPLE_SHA256:
        raise ValueError("Candidate fixture differs from the recorded synthetic sample")
    return {
        "sampleId": "SAMPLE-RANGE-LARGEFILE",
        "immutableId": "guize-fresh-de8ad3f-v1-base-64m",
        "byteCount": size,
        "checksum": "sha256:" + digest.hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path, help="Local materialized synthetic input file")
    args = parser.parse_args()
    try:
        inventory = verify_fixture(args.fixture)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(inventory, indent=2))


if __name__ == "__main__":
    main()
