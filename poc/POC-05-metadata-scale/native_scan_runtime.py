"""Approved same-PID scanner image, bounded phase IPC and independent catalogue reader."""
from __future__ import annotations

import time
ENTRY_MONO_NS, ENTRY_WALL_NS, ENTRY_AFTER_NS = time.monotonic_ns(), time.time_ns(), time.monotonic_ns()

import argparse
import base64
import hashlib
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from canonical_metadata import ANCHOR, EVENT, CanonicalPair, CanonicalScanner, validate_profile
from metadata_scan import MAX_PAGE_BYTES, MAX_PAGE_RECORDS, ScanError, canonical, file_sha256
from native_memory import parse_status
from native_scan_protocol import (Clock, ClockFailure, ControlReader, actual_argv, argv_sha, check_sources,
                                  decode, descriptor, emit, process_identity as native_identity, read_json, scoped, utc)


def require_linux():
    if not sys.platform.startswith("linux"):
        raise ScanError("LINUX_NATIVE_RUNTIME_REQUIRED")


def release_data(manifest_ref, manifest_sha, approval_ref, approval_sha, *, after_exec):
    manifest, _ = read_json(manifest_ref, manifest_sha)
    approval, _ = read_json(approval_ref, approval_sha)
    if approval.get("decision") != "approved" or approval.get("manifestSha256") != manifest_sha:
        raise ScanError("EXPLICIT_BOUND_APPROVAL_REQUIRED")
    cfg, _ = read_json(manifest["configRef"], approval["runtimeConfigSha256"])
    if (approval["runtimeConfigRef"] != manifest["configRef"]
            or not approval.get("reviewer") or approval["reviewer"] == cfg["executor"]
            or cfg["context"]["configurationRef"] != approval["configurationRef"]
            or "sha256:" + file_sha256(approval["configurationRef"]) != approval["configurationSha256"]):
        raise ScanError("INDEPENDENT_CONFIGURATION_APPROVAL_REQUIRED")
    begin, end, approved = (utc(approval[key]) for key in ("windowStart", "windowEnd", "approvedAt"))
    now = datetime.now(timezone.utc)
    if not utc(approval["reservationAt"]) <= approved <= begin <= now <= end or not 0 < (end-begin).total_seconds() <= 86400:
        raise ScanError("APPROVAL_OR_EXECUTION_WINDOW_MISMATCH")
    identity = native_identity(os.getpid() if after_exec is not None else approval["reservation"]["nativeProcessId"])
    expected = dict(approval["reservation"])
    if after_exec is not False:
        expected["cmdlineSha256"] = argv_sha(manifest["argv"])
    if identity != expected:
        raise ScanError("RESERVED_PROCESS_IDENTITY_MISMATCH")
    if cfg["context"]["scannerBuild"] != manifest["scannerBuild"] or cfg["context"]["subjectVersion"] != manifest["scannerBuild"]:
        raise ScanError("SCANNER_BUILD_BINDING_MISMATCH")
    check_sources(manifest)
    return manifest, approval, cfg, identity


def reserve(args):
    manifest, _ = read_json(args.manifest, args.sha256)
    check_sources(manifest)
    argv = manifest["argv"]
    prefix = [sys.executable, "-B", str(Path(__file__).resolve()), "worker", "--config", manifest["configRef"]]
    if argv[:len(prefix)] != prefix or not all(isinstance(part, str) and part for part in argv):
        raise ScanError("FIXED_SCANNER_EXEC_REQUIRED")
    identity = native_identity(os.getpid())
    stat = Path("/proc/self/stat").read_bytes()
    reserved_at = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    emit(dict(kind="reservation_ready", identity=identity, reservedAt=reserved_at,
              osStatBase64=base64.b64encode(stat).decode(), osStatSha256=hashlib.sha256(stat).hexdigest(),
              manifestSha256=args.sha256, finalArgv=argv,
              semantics="waiting OS process, no scanner workload has started"))
    # Reservation expiry bounds a disconnected controller; it is not an experiment window.
    reader = ControlReader()
    message = reader.receive(manifest["reservationDeadline"])
    if set(message) != {"command", "approvalRef", "approvalSha256"} or message["command"] != "release":
        raise ScanError("APPROVED_RELEASE_REQUIRED")
    _, approval, _, checked = release_data(args.manifest, args.sha256, message["approvalRef"],
                                          message["approvalSha256"], after_exec=False)
    if checked != identity or approval["reservationAt"] != reserved_at or reader.buffer:
        raise ScanError("EXACT_RESERVATION_HANDOFF_REQUIRED")
    emit(dict(kind="exec_handoff", processId=os.getpid(), monotonicNs=time.monotonic_ns(),
              observedAt=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), approvalSha256=message["approvalSha256"],
              manifestSha256=args.sha256, finalArgv=argv))
    os.environ.update(GUIZE_POC_MANIFEST_REF=str(args.manifest), GUIZE_POC_MANIFEST_SHA=args.sha256,
                      GUIZE_POC_APPROVAL_REF=message["approvalRef"], GUIZE_POC_APPROVAL_SHA=message["approvalSha256"])
    os.execv(argv[0], argv)


class Worker:
    def __init__(self, args, *, entry_sample=None, control_reader=None, entry_samples=None):
        self.manifest, self.approval, self.cfg, self.identity = release_data(
            os.environ["GUIZE_POC_MANIFEST_REF"], os.environ["GUIZE_POC_MANIFEST_SHA"],
            os.environ["GUIZE_POC_APPROVAL_REF"], os.environ["GUIZE_POC_APPROVAL_SHA"], after_exec=True)
        if actual_argv() != self.manifest["argv"] or args.config != self.manifest["configRef"]:
            raise ScanError("ACTUAL_SCANNER_ARGV_MISMATCH")
        self.args, self.reader, self.clock = args, control_reader or ControlReader(), Clock()
        self.root = self.cfg["artifactRoot"]
        if entry_sample is None:
            self.start = self.clock.marker("process_start", tick=ENTRY_MONO_NS, wall=ENTRY_WALL_NS, after_tick=ENTRY_AFTER_NS)
        else:
            self.start = self.clock.marker('process_start', tick=entry_sample['beforeNs'], wall=entry_sample['wallNs'], after_tick=entry_sample['afterNs'])
            self.start['nativeClockSample'] = entry_sample
            self.start['entryClockSamples'] = entry_samples
        if utc(self.start["observedAt"]) < utc(self.approval["windowStart"]):
            raise ScanError("SCANNER_ENTRY_OUTSIDE_WINDOW")
        expected = ["--scan-id", self.cfg["scanId"], "--change-set-id", self.cfg["changeSetId"],
                    "--input", self.cfg["baseline"]["ref"], "--objects", self.cfg["outputs"]["objects"],
                    "--events", self.cfg["outputs"]["events"], "--appliedEvents", self.cfg["outputs"]["appliedEvents"],
                    "--traversedObjects", self.cfg["outputs"]["traversedObjects"]]
        if self.manifest["argv"][-len(expected):] != expected:
            raise ScanError("EXACT_FROZEN_SCANNER_ARGUMENTS_REQUIRED")
        outputs = [self.cfg["database"], *self.cfg["outputs"].values()]
        paths = [scoped(self.root, ref) for ref in outputs]
        if len(paths) != len(set(paths)) or any(path.exists() for path in paths):
            raise ScanError("NEW_INDEPENDENT_RUNTIME_OUTPUTS_REQUIRED")
        self.scan, self.first_peak, self.incremental_end = None, None, None
        emit(dict(kind="scanner_ready", identity=self.identity, argv=actual_argv(), context=self.cfg["context"],
                  processStart=self.start, calibration=self.clock.calibration,
                  lifetimeSemantics=("native worker entry after approved initial-thread resume and platform-clock binding; OS creation is separate"
                                     if entry_sample is not None else "scanner image entry after approved exec; OS birth is separate")))

    def check(self):
        if datetime.now(timezone.utc) > utc(self.approval["windowEnd"]):
            raise ScanError("WORKLOAD_WINDOW_EXPIRED")
        if "sha256:" + file_sha256(self.args.config) != self.approval["runtimeConfigSha256"]:
            raise ScanError("RUNTIME_CONFIGURATION_CHANGED")

    def receive(self, command):
        self.check()
        message = self.reader.receive(self.approval["windowEnd"])
        if message.get("command") != command:
            raise ScanError("CONTROL_COMMAND_ORDER_MISMATCH")
        return message

    def phase(self, name, action):
        self.check()
        self.phase_start = self.clock.marker("phase_start")
        emit(dict(kind="phase_start", phase=name, event=self.phase_start))
        try:
            result = action()
            self.check()
        except BaseException:
            emit(dict(kind="phase_exit", phase=name, event=self.clock.marker("phase_exit", exit_code=1)))
            raise
        event = self.clock.marker("phase_exit")
        emit(dict(kind="phase_exit", phase=name, event=event, outputs=result))
        return event

    def memory(self, command):
        message = self.receive(command)
        refs = self.cfg["memory"]["before" if command == "memory_before" else "after"]
        if message["receiptRef"] != refs["stdout"]:
            raise ScanError("APPROVED_COUNTER_RECEIPT_REQUIRED")
        receipt, _ = read_json(scoped(self.root, message["receiptRef"]), message["receiptSha256"])
        raw_ref = scoped(self.root, receipt["counterRef"])
        with raw_ref.open("rb") as stream:
            raw = stream.read(65537)
        current = native_identity(os.getpid())
        if self.cfg.get('counterFormat', 'linux_proc_status') == 'windows_process_memory_counters':
            value = decode(raw)
            if (not isinstance(value, dict) or set(value) != {'ProcessId', 'PeakWorkingSetSize', 'WorkingSetSize'}
                    or any(type(number) is not int for number in value.values()) or value['ProcessId'] != os.getpid()
                    or not 0 <= value['WorkingSetSize'] <= value['PeakWorkingSetSize'] <= 2**60):
                raise ScanError('ACTUAL_WINDOWS_MEMORY_COUNTER_REQUIRED')
            counters = dict(nativeProcessId=value['ProcessId'], peakResidentBytes=value['PeakWorkingSetSize'], residentBytes=value['WorkingSetSize'])
        else:
            counters = parse_status(raw, os.getpid())
        if (len(raw) > 65536 or receipt["identity"] != current or receipt["collectorProcessId"] == os.getpid()
                or receipt['counterFormat'] != self.cfg.get('counterFormat', 'linux_proc_status')
                or receipt["counterRef"] != refs["counter"]
                or receipt["exitCode"] != 0 or receipt["toolBuild"] != self.cfg["counterCollectorBuild"]
                or receipt["commandArgs"] != self.cfg["memoryCollectorCommandArgs"] + ["--pid", str(os.getpid()), "--output", receipt["counterRef"]]
                or receipt["sha256"] != "sha256:" + hashlib.sha256(raw).hexdigest()
                or receipt["byteCount"] != len(raw) or receipt["counters"] != counters
                or not utc(self.start["observedAt"]) <= utc(receipt["observedAt"]) <= datetime.now(timezone.utc)):
            raise ScanError("ACTUAL_INDEPENDENT_MEMORY_RECEIPT_REQUIRED")
        if command == "memory_before":
            self.first_peak = counters["peakResidentBytes"]
        else:
            if message["postReceiptRef"] != self.cfg["postReceipt"]:
                raise ScanError("APPROVED_POST_CATALOGUE_RECEIPT_REQUIRED")
            post, _ = read_json(scoped(self.root, message["postReceiptRef"]), message["postReceiptSha256"])
            if (self.first_peak is None or counters["peakResidentBytes"] < self.first_peak
                    or post["collectorProcessId"] == os.getpid() or post["scannerProcessId"] != os.getpid()
                    or post.get("kind") != "independent_post_scan_catalogue" or post.get("exitCode") != 0
                    or post.get("context") != self.cfg["context"]
                    or not utc(self.incremental_end["observedAt"]) <= utc(post["observedAt"]) <= utc(receipt["observedAt"])):
                raise ScanError("FINAL_MEMORY_AND_POST_CATALOGUE_ORDER_REQUIRED")
            output = post["objects"]
            if (output["ref"] != self.cfg["outputs"]["postScanObjects"] or type(output["count"]) is not int
                    or not 0 <= output["count"] <= 2000000
                    or output["sha256"] != "sha256:" + file_sha256(scoped(self.root, output["ref"]))):
                raise ScanError("ACTUAL_POST_CATALOGUE_BYTES_REQUIRED")
        emit(dict(kind=command + "_accepted", observedAt=receipt["observedAt"], peakResidentBytes=counters["peakResidentBytes"]))

    def describe(self, name, count):
        ref = self.cfg["outputs"][name]
        result = descriptor(scoped(self.root, ref), count)
        result["ref"] = ref
        return result

    def enumeration(self):
        baseline, profiled = self.cfg["baseline"], self.cfg["profiled"]
        pair = CanonicalPair(scoped(self.root, baseline["ref"]), scoped(self.root, profiled["ref"]),
                             baseline_sha256=baseline["sha256"].removeprefix("sha256:"),
                             profiled_sha256=profiled["sha256"].removeprefix("sha256:"), source_id=self.cfg["sourceId"],
                             snapshot_version=self.cfg["snapshotVersion"], page_size=self.cfg["pageSize"])
        self.scan = CanonicalScanner(scoped(self.root, self.cfg["database"]), pair)
        while not self.scan.core.state()["complete"]:
            self.check()
            self.scan.apply_next()
        count = self.scan.export(*(scoped(self.root, self.cfg["outputs"][key]) for key in
                                   ("objects", "filenameObjects", "enumeratedVersions")))
        self.scan.db.executescript("CREATE TABLE driver_pending(sequence INTEGER PRIMARY KEY,event_id TEXT UNIQUE,event TEXT,profile TEXT);"
                                  "CREATE TABLE driver_visits(object_id TEXT PRIMARY KEY);")
        return {key: self.describe(key, count) for key in ("objects", "filenameObjects", "enumeratedVersions")}

    def changes(self):
        self.change_start = self.phase_start["observedAt"]
        count = 0
        with scoped(self.root, self.cfg["outputs"]["events"]).open("xb") as output:
            while True:
                self.check()
                message = self.reader.receive(self.approval["windowEnd"])
                if message == {"command": "end_changes"}:
                    break
                if set(message) != {"command", "observationRef", "observationSha256"} or message["command"] != "observed_change":
                    raise ScanError("ACTUAL_SOURCE_OBSERVATION_REFERENCE_REQUIRED")
                observation, _ = read_json(scoped(self.root, message["observationRef"]), message["observationSha256"], 65536)
                event, profile = observation["event"], observation["profile"]
                if (observation["kind"] != "controlled_source_change_observation" or observation["sourceId"] != self.cfg["sourceId"]
                        or set(event) != EVENT or event["sequence"] != count + 1 or count >= 1000000
                        or not utc(self.change_start) <= utc(observation["observedAt"]) <= utc(self.clock.mapped_utc(self.clock.now_ns()))
                        or not isinstance(observation["evidenceRefs"], list) or not 1 <= len(observation["evidenceRefs"]) <= 16):
                    raise ScanError("CONTROLLED_CHANGE_SOURCE_TIME_OR_SEQUENCE_MISMATCH")
                for evidence in observation["evidenceRefs"]:
                    path = scoped(self.root, evidence["ref"])
                    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_PAGE_BYTES or "sha256:" + file_sha256(path) != evidence["sha256"]:
                        raise ScanError("ACTUAL_CHANGE_EVIDENCE_MISMATCH")
                if profile is not None:
                    validate_profile(profile)
                if (event["operation"] == "delete") != (profile is None):
                    raise ScanError("CHANGE_PROFILE_DISPOSITION_MISMATCH")
                self.scan.db.execute("INSERT INTO driver_pending VALUES(?,?,?,?)", (
                    event["sequence"], event["eventId"], canonical(event), canonical(profile)))
                output.write((canonical({**event, "observedAt": observation["observedAt"]}) + "\n").encode())
                output.flush()
                count += 1
                emit(dict(kind="change_observed", sequence=count, observationSha256=message["observationSha256"]))
        if not count:
            raise ScanError("EMPTY_OBSERVED_CHANGE_STREAM")
        return dict(events=self.describe("events", count))

    def apply_batch(self, events, profiles):
        self.scan.apply_events(dict(sourceId=self.cfg["sourceId"], baselineSha256=self.scan.pair.shas[0],
                                    events=events, profiles=profiles))
        # The traversal output means distinct logical targets actually reread after replay,
        # not a claim that every internal SQLite/B-tree lookup is an enumerated object visit.
        for object_id in {event["objectId"] for event in events}:
            row = self.scan.db.execute("SELECT object_id FROM objects WHERE object_id=?", (object_id,)).fetchone()
            if row is None or row[0] == ANCHOR:
                raise ScanError("REPLAY_TARGET_WAS_NOT_TRAVERSED")
            self.scan.db.execute("INSERT OR IGNORE INTO driver_visits VALUES(?)", (row[0],))

    def incremental(self):
        events, profiles, size = [], [], 0
        for row in self.scan.db.execute("SELECT event,profile FROM driver_pending ORDER BY sequence"):
            self.check()
            if events and (len(events) >= MAX_PAGE_RECORDS or size + len(row[0]) + len(row[1]) > MAX_PAGE_BYTES // 2):
                self.apply_batch(events, profiles)
                events, profiles, size = [], [], 0
            event, profile = decode(row[0]), decode(row[1])
            events.append(event)
            if profile is not None:
                profiles.append(profile)
            size += len(row[0]) + len(row[1])
        if events:
            self.apply_batch(events, profiles)
        result = {}
        for name, query, field in (("appliedEvents", "SELECT event_id FROM canonical_events ORDER BY sequence", "eventId"),
                                   ("traversedObjects", "SELECT object_id FROM driver_visits ORDER BY object_id", "objectId")):
            count = 0
            with scoped(self.root, self.cfg["outputs"][name]).open("xb") as output:
                for row in self.scan.db.execute(query):
                    output.write((canonical({field: row[0]}) + "\n").encode())
                    count += 1
            result[name] = self.describe(name, count)
        return result

    def run(self):
        try:
            self.memory("memory_before")
            self.receive("enumerate")
            self.phase("enumeration", self.enumeration)
            self.receive("begin_changes")
            self.phase("changeStream", self.changes)
            self.receive("incremental")
            self.incremental_end = self.phase("incremental", self.incremental)
            emit(dict(kind="work_complete", scannerProcessId=os.getpid()))
            self.memory("memory_after")
            self.receive("exit")
            self.check()
            emit(dict(kind="exit_requested", scannerProcessId=os.getpid(), semantics="actual exit is observed externally"))
        finally:
            if self.scan is not None:
                self.scan.close()


def catalogue(args):
    _, approval, cfg, identity = release_data(os.environ["GUIZE_POC_MANIFEST_REF"], os.environ["GUIZE_POC_MANIFEST_SHA"],
                                             args.approval, args.approval_sha, after_exec=None)
    ready, _ = read_json(scoped(cfg["artifactRoot"], args.clock))
    if ready["identity"] != identity or identity["nativeProcessId"] == os.getpid():
        raise ScanError("INDEPENDENT_LIVE_CATALOGUE_READER_REQUIRED")
    clock = Clock(ready["calibration"])
    output = scoped(cfg["artifactRoot"], args.output)
    database = scoped(cfg["artifactRoot"], cfg["database"])
    db = sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)
    count = 0
    try:
        db.execute("BEGIN")
        state = db.execute("SELECT source_id,fixture_sha,complete FROM state WHERE id=1").fetchone()
        if state != (cfg["sourceId"], cfg["baseline"]["sha256"].removeprefix("sha256:"), 1):
            raise ScanError("POST_INDEX_SOURCE_BINDING_MISMATCH")
        with output.open("xb") as stream:
            for object_id, version in db.execute("SELECT object_id,version_id FROM objects WHERE deleted=0 AND object_id<>? ORDER BY object_id", (ANCHOR,)):
                stream.write((canonical(dict(objectId=object_id, versionId=version)) + "\n").encode())
                count += 1
    finally:
        db.close()
    if native_identity(identity["nativeProcessId"]) != identity:
        raise ScanError("SCANNER_CHANGED_DURING_POST_CATALOGUE")
    emit(dict(kind="independent_post_scan_catalogue", context=cfg["context"], scannerProcessId=identity["nativeProcessId"],
              collectorProcessId=os.getpid(), observedAt=clock.mapped_utc(clock.now_ns()),
              objects={**descriptor(output, count), "ref": args.output}, commandArgs=actual_argv(), exitCode=0))


def main():
    require_linux()
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)
    reserve_parser = sub.add_parser("reserve")
    reserve_parser.add_argument("--manifest", required=True)
    reserve_parser.add_argument("--sha256", required=True)
    worker_parser = sub.add_parser("worker")
    worker_parser.add_argument("--config", required=True)
    for flag in ("scan-id", "change-set-id", "input", "objects", "events", "appliedEvents", "traversedObjects"):
        worker_parser.add_argument("--" + flag, required=True)
    reader_parser = sub.add_parser("catalogue")
    for flag in ("approval", "approval-sha", "clock", "output"):
        reader_parser.add_argument("--" + flag, required=True)
    args = parser.parse_args()
    if args.mode == "reserve":
        reserve(args)
    elif args.mode == "worker":
        Worker(args).run()
    else:
        catalogue(args)


if __name__ == "__main__":
    try:
        main()
    except (ScanError, OSError, ValueError, KeyError, TypeError, sqlite3.Error) as failure:
        record = dict(kind="runtime_failure", error=str(failure) if isinstance(failure, ScanError) else type(failure).__name__)
        if isinstance(failure, ClockFailure):
            record["clockObservation"] = failure.observation
        emit(record)
        raise SystemExit(1)
