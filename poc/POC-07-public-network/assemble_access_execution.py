"""Assemble a POC-007 execution record from retained access observations."""

import argparse
import json
from pathlib import Path
import sys


REPOSITORY = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPOSITORY))
from specs.poc.check_program import (
    load,
    qualified_window,
    validate_qualified_access_outcomes,
    validate_qualified_raw,
)


def assemble(evidence_root: Path, capture_dir: Path, execution: dict) -> dict:
    """Bind the recorded runtime facts to execution metadata supplied by the caller."""
    root = evidence_root.resolve()
    capture = (root / capture_dir).resolve()
    relative = capture.relative_to(root)
    combined = load(capture / "access-replay.json")
    manifest = load(capture / "raw-artifacts.json")
    prefix = relative.parent.as_posix()
    capture_ref = relative / combined["accessOutcome"]["ref"]
    command_ref = (relative / "access-replay.json").as_posix()
    record_hashes = [artifact["sha256"] for artifact in manifest["rawExecutionArtifacts"]
                     if artifact["ref"] == capture_ref.as_posix() and artifact["artifactType"] == "measurement_output"]
    if record_hashes != [combined["accessOutcome"]["sha256"]]:
        raise ValueError("The access report must match its command receipt and artifact inventory")
    if not any(command.get("outputRef") == command_ref for command in execution["commands"]):
        raise ValueError("Execution metadata must identify the actual combination command output")

    plan = load(REPOSITORY / "specs/poc/plans/POC-007.yaml")
    definitions = load(REPOSITORY / "specs/poc/program.schema.yaml")["$defs"]
    identity = {key: plan[key] for key in ("taskId", "pocId", "evidencePath")}
    if any(execution.get(key) != value for key, value in identity.items()):
        raise ValueError("Execution metadata must identify POC-007 and its evidence directory")
    environment = {
        **execution["environmentCaptured"],
        "executionWindow": {key: combined[key] for key in ("startedAt", "finishedAt")},
        "rawExecutionArtifacts": manifest["rawExecutionArtifacts"],
        "accessOutcomeRef": capture_ref.as_posix(),
    }
    assembled = {
        **execution, "environmentCaptured": environment, "rawOutputRefs": manifest["rawOutputRefs"],
        "measurements": [
            {"id": measurement["id"], "actual": True}
            for measurement in plan["localValidation"]["protocol"]["measurements"]
        ],
    }

    errors: list[str] = []
    cache = {}
    window = qualified_window(assembled, definitions["executionWindow"], "POC-007 capture", errors)
    validate_qualified_raw(root, plan, assembled, {}, definitions, prefix, "pass", set(), errors, cache)
    validate_qualified_access_outcomes(root, plan, assembled, prefix, "pass", window, definitions, errors, cache)
    if errors:
        raise ValueError("\n".join(errors))
    return assembled


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path, help="Capture directory relative to the evidence root")
    parser.add_argument("metadata", type=Path, help="Execution metadata and references prepared for this run")
    parser.add_argument("output", type=Path, help="Destination for the assembled execution record")
    parser.add_argument("--evidence-root", type=Path, default=REPOSITORY)
    args = parser.parse_args()
    try:
        record = assemble(args.evidence_root, args.capture, load(args.metadata))
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, indent=2)
            stream.write("\n")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
