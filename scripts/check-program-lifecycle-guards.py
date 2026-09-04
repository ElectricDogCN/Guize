#!/usr/bin/env python3
"""Dispatch Program lifecycle validation to Registration or preserved core."""

from __future__ import annotations

import importlib.util
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CORE_PATH = os.path.join(SCRIPT_DIR, "check-program-lifecycle-guards-core.py")
REGISTRATION_PATH = os.path.join(SCRIPT_DIR, "check-program-task-registration.py")


def _load(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


CORE = _load(CORE_PATH, "guize_program_lifecycle_guards_core")
REGISTRATION = _load(
    REGISTRATION_PATH, "guize_program_task_registration_for_lifecycle"
)
for _name, _value in vars(CORE).items():
    if not _name.startswith("__"):
        globals().setdefault(_name, _value)


def main() -> int:
    args = CORE.parse_args()
    root = os.path.abspath(args.repo_root)
    if REGISTRATION.is_registration_candidate(
        root, args.base_ref, args.head_ref
    ):
        code, details = REGISTRATION.validate_registration(
            root,
            args.base_ref,
            args.head_ref,
            task_hint=args.task,
            branch_name=args.branch_name,
        )
        if code:
            for error in details.get("errors") or []:
                REGISTRATION.emit("FAIL", error)
            return code
        REGISTRATION.emit(
            "PASS", "Program Task Registration lifecycle scope passed", details
        )
        return 0

    # run-program-lifecycle-gate.py monkey-patches these exported hooks.  Copy
    # the current wrapper values into the preserved core before delegation.
    CORE.changed_paths = globals().get("changed_paths", CORE.changed_paths)
    CORE.task_ids_from_diff = globals().get(
        "task_ids_from_diff", CORE.task_ids_from_diff
    )
    return CORE.main()


if __name__ == "__main__":
    sys.exit(main())
