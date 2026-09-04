#!/usr/bin/env python3
"""Load the reviewed pre-Registration lifecycle core fail-closed.

The immutable blob is retained in repository history.  This loader exists only
for the OPS-008 self-hosting change so the canonical entry point can dispatch
Registration while all non-Registration behavior remains byte-identical.
"""

from __future__ import annotations

import os
import subprocess

CORE_BLOB = "cd1242fbdd8959376635d25e4f4cb4aefa0fa11a"
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_result = subprocess.run(
    ["git", "cat-file", "blob", CORE_BLOB],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=False,
)
if _result.returncode != 0:
    raise RuntimeError(
        f"Immutable Program lifecycle core blob {CORE_BLOB} is unavailable: "
        + _result.stderr.strip()
    )
exec(compile(_result.stdout, __file__ + ":" + CORE_BLOB, "exec"), globals())
