"""Bounded control records and one explicit native UTC/monotonic mapping."""
from __future__ import annotations

import hashlib
import json
import os
import select
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from metadata_scan import MAX_LINE_BYTES, ScanError, canonical, file_sha256

SOURCES = ("native_scan_protocol.py", "native_scan_runtime.py", "native_scan_control.py",
           "native_memory.py", "canonical_metadata.py", "metadata_scan.py")


def unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ScanError("DUPLICATE_CONTROL_FIELD")
        result[key] = value
    return result


def decode(raw):
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (ValueError, UnicodeError, RecursionError):
        raise ScanError("INVALID_CONTROL_JSON") from None


def read_json(path, expected=None, limit=262144):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ScanError("REGULAR_CONTROL_FILE_REQUIRED")
    with path.open("rb") as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    if (not raw or len(raw) > limit or (before.st_ino, before.st_dev, before.st_size, before.st_mtime_ns)
            != (after.st_ino, after.st_dev, after.st_size, after.st_mtime_ns)):
        raise ScanError("CONTROL_FILE_LIMIT_OR_CHANGE")
    digest = "sha256:" + hashlib.sha256(raw).hexdigest()
    if expected is not None and digest != expected:
        raise ScanError("CONTROL_FILE_HASH_MISMATCH")
    return decode(raw), digest


def write_json(path, value):
    raw = (canonical(value) + "\n").encode()
    with Path(path).open("xb") as stream:
        stream.write(raw)
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def utc(value):
    if not isinstance(value, str):
        raise ScanError("UTC_REQUIRED")
    try:
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if instant.tzinfo is None:
            raise ValueError()
        return instant.astimezone(timezone.utc)
    except ValueError:
        raise ScanError("UTC_REQUIRED") from None


def scoped(root, ref):
    path = Path(ref).resolve()
    if not path.is_relative_to(Path(root).resolve()) or path == Path(root).resolve():
        raise ScanError("ARTIFACT_OUTSIDE_RUN_ROOT")
    return path


def descriptor(path, count):
    return dict(ref=str(path), sha256="sha256:" + file_sha256(path), count=count)


def actual_argv():
    with Path("/proc/self/cmdline").open("rb") as stream:
        raw = stream.read(65537)
    if not raw or len(raw) > 65536:
        raise ScanError("ACTUAL_ARGV_LIMIT")
    return [part.decode("utf-8") for part in raw.rstrip(b"\0").split(b"\0")]


def argv_sha(argv):
    return hashlib.sha256(b"\0".join(os.fsencode(part) for part in argv) + b"\0").hexdigest()


def check_sources(manifest):
    expected = {str(Path(__file__).with_name(name).resolve()) for name in SOURCES}
    sources = manifest.get("sourceFiles")
    if not isinstance(sources, dict) or set(sources) != expected:
        raise ScanError("EXACT_RUNTIME_SOURCE_SET_REQUIRED")
    for path, digest in sources.items():
        if "sha256:" + file_sha256(path) != digest:
            raise ScanError("RUNTIME_SOURCE_CHANGED")


class Clock:
    def __init__(self, calibration=None):
        if calibration is None:
            samples = []
            for _ in range(32):
                before = time.monotonic_ns()
                wall = time.time_ns()
                after = time.monotonic_ns()
                samples.append(dict(beforeNs=before, wallNs=wall, afterNs=after))
            chosen = min(range(len(samples)), key=lambda n: samples[n]["afterNs"] - samples[n]["beforeNs"])
            calibration = dict(samples=samples, chosen=chosen, clock="time.monotonic_ns",
                               implementation=time.get_clock_info("monotonic").implementation,
                               utcSemantics="wall calibration mapped from retained native monotonic ticks")
        self.calibration = calibration
        sample = calibration["samples"][calibration["chosen"]]
        self.mono = (sample["beforeNs"] + sample["afterNs"]) // 2
        self.wall = sample["wallNs"]
        if not 0 <= sample["afterNs"] - sample["beforeNs"] <= 2000:
            raise ScanError("CLOCK_CALIBRATION_UNCERTAINTY")

    def mapped_utc(self, tick):
        nanos = self.wall + tick - self.mono
        seconds, remainder = divmod(nanos, 1_000_000_000)
        return (datetime.fromtimestamp(seconds, timezone.utc) + timedelta(microseconds=remainder // 1000)).isoformat()

    def marker(self, kind, *, tick=None, wall=None, exit_code=0, process_id=None):
        tick = time.monotonic_ns() if tick is None else tick
        wall = time.time_ns() if wall is None else wall
        if abs(wall - (self.wall + tick - self.mono)) > 1_000_000:
            raise ScanError("WALL_CLOCK_CHANGED")
        return dict(type=kind, processId=os.getpid() if process_id is None else process_id, observedAt=self.mapped_utc(tick),
                    monotonicNs=tick, exitCode=exit_code, directWallNs=wall)


def typed_event(event):
    return {key: event[key] for key in ("type", "processId", "observedAt", "monotonicNs", "exitCode")}


class ControlReader:
    def __init__(self, fd=0):
        self.fd, self.buffer = fd, bytearray()

    def receive(self, deadline):
        while b"\n" not in self.buffer:
            remaining = (utc(deadline) - datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0 or not select.select([self.fd], [], [], remaining)[0]:
                raise ScanError("CONTROL_DEADLINE")
            chunk = os.read(self.fd, 4096)
            if not chunk:
                raise ScanError("CONTROL_EOF")
            self.buffer.extend(chunk)
            if len(self.buffer) > MAX_LINE_BYTES and b"\n" not in self.buffer[:MAX_LINE_BYTES]:
                raise ScanError("CONTROL_LINE_LIMIT")
        raw, _, remaining = self.buffer.partition(b"\n")
        self.buffer = bytearray(remaining)
        if len(raw) > MAX_LINE_BYTES:
            raise ScanError("CONTROL_LINE_LIMIT")
        return decode(raw)


def emit(value):
    print(canonical(value), flush=True)
