"""Separate Linux collector of unmodified, identity-bound process OS counters."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


class CounterError(ValueError):
    pass


def _read(path, limit=65536):
    with Path(path).open("rb") as stream:
        raw = stream.read(limit + 1)
    if not raw or len(raw) > limit:
        raise CounterError("INVALID_NATIVE_COUNTER_SIZE")
    return raw


def _digest(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def start_ticks(raw, pid):
    try:
        prefix, tail = raw.rsplit(b") ", 1)
        if int(prefix.split(b" ", 1)[0]) != pid:
            raise ValueError()
        value = tail.split()[19]
        if re.fullmatch(rb"[0-9]{1,20}", value) is None or int(value) < 1:
            raise ValueError()
        return int(value)
    except (ValueError, IndexError):
        raise CounterError("INVALID_NATIVE_PROCESS_START") from None


def parse_status(raw, pid):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 65536:
        raise CounterError("INVALID_NATIVE_COUNTER_SIZE")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeError:
        raise CounterError("INVALID_NATIVE_COUNTER_ENCODING") from None
    values = {}
    for key in ("Pid", "VmHWM", "VmRSS"):
        lines = re.findall(r"^" + key + r":[^\r\n]*$", decoded, re.MULTILINE)
        pattern = key + r":[ \t]*([0-9]{1,16})" + (r"[ \t]+kB" if key != "Pid" else "") + r"[ \t]*"
        match = re.fullmatch(pattern, lines[0]) if len(lines) == 1 else None
        if match is None:
            raise CounterError("MISSING_DUPLICATE_OR_INVALID_NATIVE_COUNTER")
        values[key] = int(match.group(1))
    if values["Pid"] != pid or not 0 <= values["VmRSS"] <= values["VmHWM"] <= 2**50:
        raise CounterError("NATIVE_COUNTER_IDENTITY_OR_RANGE_MISMATCH")
    return dict(nativeProcessId=pid, peakResidentBytes=values["VmHWM"] * 1024,
                residentBytes=values["VmRSS"] * 1024)


def native_identity(pid):
    if not sys.platform.startswith("linux"):
        raise CounterError("LINUX_PROC_REQUIRED")
    if type(pid) is not int or not 1 <= pid <= 2**32-1:
        raise CounterError("INVALID_NATIVE_PROCESS_ID")
    proc = Path("/proc") / str(pid)
    if proc.stat().st_uid != os.getuid():
        raise CounterError("OWNED_NATIVE_PROCESS_REQUIRED")
    executable = (proc / "exe").resolve(strict=True)
    boot = _read("/proc/sys/kernel/random/boot_id", 128).decode("ascii").strip()
    if re.fullmatch(r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", boot) is None:
        raise CounterError("INVALID_NATIVE_BOOT_ID")
    return dict(nativeProcessId=pid, bootId=boot, startTicks=start_ticks(_read(proc / "stat"), pid),
                executable=str(executable), executableSha256=_digest(proc / "exe"),
                cmdlineSha256=hashlib.sha256(_read(proc / "cmdline")).hexdigest(), uid=os.getuid())


def collect(pid, output, *, expected):
    if pid == os.getpid():
        raise CounterError("INDEPENDENT_COLLECTOR_REQUIRED")
    before = native_identity(pid)
    if before != expected:
        raise CounterError("NATIVE_PROCESS_BINDING_MISMATCH")
    raw = _read(Path("/proc") / str(pid) / "status")
    observed_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    counters = parse_status(raw, pid)
    if native_identity(pid) != before:
        raise CounterError("NATIVE_PROCESS_CHANGED_DURING_CAPTURE")
    with Path(output).open("xb") as stream:
        stream.write(raw)
    actual_argv = _read("/proc/self/cmdline").rstrip(b"\0").split(b"\0")
    return dict(observedAt=observed_at, collectorProcessId=os.getpid(), identity=before,
                counterFormat="linux_proc_status", counters=counters, counterRef=str(output),
                byteCount=len(raw), sha256="sha256:" + hashlib.sha256(raw).hexdigest(),
                toolBuild="sha256:" + _digest(__file__),
                commandArgs=[arg.decode("utf-8") for arg in actual_argv], exitCode=0)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-ticks", required=True, type=int)
    parser.add_argument("--boot-id", required=True)
    parser.add_argument("--exe", required=True)
    parser.add_argument("--exe-sha256", required=True)
    parser.add_argument("--cmdline-sha256", required=True)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not sys.platform.startswith("linux"):
        raise CounterError("LINUX_PROC_REQUIRED")
    expected = dict(nativeProcessId=args.pid, bootId=args.boot_id, startTicks=args.start_ticks,
                    executable=str(Path(args.exe).resolve(strict=True)), executableSha256=args.exe_sha256,
                    cmdlineSha256=args.cmdline_sha256, uid=os.getuid())
    print(json.dumps(collect(args.pid, args.output, expected=expected), sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except CounterError as failure:
        print(str(failure), file=sys.stderr)
        raise SystemExit(1)
    except (OSError, UnicodeError, ValueError):
        print("NATIVE_COUNTER_IO_FAILURE", file=sys.stderr)
        raise SystemExit(1)
