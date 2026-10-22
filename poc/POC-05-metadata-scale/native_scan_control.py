"""External native controller: actual process wait, independent counters and typed captures."""
from __future__ import annotations

import argparse
import json
import os
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from metadata_scan import MAX_LINE_BYTES, ScanError, canonical, file_sha256
from native_memory import native_identity
from native_scan_protocol import (Clock, SOURCES, actual_argv, argv_sha, decode, descriptor, emit,
                                  read_json, scoped, typed_event, utc, write_json)


def manifest_for(config_ref, cfg, reservation_deadline):
    runtime = str(Path(__file__).with_name("native_scan_runtime.py").resolve())
    argv = [sys.executable, "-B", runtime, "worker", "--config", str(config_ref),
            "--scan-id", cfg["scanId"], "--change-set-id", cfg["changeSetId"], "--input", cfg["baseline"]["ref"]]
    for key in ("objects", "events", "appliedEvents", "traversedObjects"):
        argv += ["--" + key, cfg["outputs"][key]]
    return dict(schemaVersion=1, configRef=str(config_ref), scannerBuild=cfg["context"]["scannerBuild"],
                argv=argv, reservationDeadline=reservation_deadline,
                sourceFiles={str(Path(__file__).with_name(name).resolve()): "sha256:" + file_sha256(Path(__file__).with_name(name))
                             for name in SOURCES})


class NativeRun:
    """No approval is generated here. Release requires an independently supplied record."""
    def __init__(self, manifest_ref, manifest_sha, *, trace_ref, stderr_ref):
        if not sys.platform.startswith("linux"):
            raise ScanError("LINUX_NATIVE_RUNTIME_REQUIRED")
        self.manifest_ref, self.manifest_sha = str(manifest_ref), manifest_sha
        self.manifest, _ = read_json(manifest_ref, manifest_sha)
        self.trace = Path(trace_ref).open("xb")
        self.stderr = Path(stderr_ref).open("xb")
        self.process = subprocess.Popen([sys.executable, "-B", str(Path(__file__).with_name("native_scan_runtime.py")),
                                         "reserve", "--manifest", str(manifest_ref), "--sha256", manifest_sha],
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self.stderr)
        self.messages, self.phases = queue.Queue(), {}
        self.clock = self.ready = self.approval = self.cfg = None
        self.memory_samples = []
        self.post_receipt = None
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.reader.start()
        try:
            self.reservation = self.expect("reservation_ready", timeout=20)
        except BaseException:
            self.close()
            raise

    def _read(self):
        try:
            while True:
                raw = self.process.stdout.readline(MAX_LINE_BYTES + 1)
                if not raw:
                    self.messages.put(ScanError("SCANNER_STREAM_EOF"))
                    break
                self.trace.write(raw)
                self.trace.flush()
                if len(raw) > MAX_LINE_BYTES or not raw.endswith(b"\n"):
                    raise ScanError("SCANNER_STREAM_LIMIT")
                record = decode(raw)
                self.messages.put(record)
        except BaseException as failure:
            self.messages.put(failure)

    def expect(self, kind, *, timeout=None):
        if timeout is None:
            timeout = max(0, (utc(self.approval["windowEnd"]) - datetime.now(timezone.utc)).total_seconds())
        try:
            record = self.messages.get(timeout=timeout)
        except queue.Empty:
            raise ScanError("SCANNER_RESPONSE_DEADLINE") from None
        if isinstance(record, BaseException):
            raise record
        if record.get("kind") == "runtime_failure":
            code = record.get("error")
            if not isinstance(code, str) or not code.isascii() or not code.isidentifier() or len(code) > 128:
                raise ScanError("INVALID_SCANNER_RUNTIME_FAILURE")
            failure = ScanError("SCANNER_RUNTIME_FAILURE:" + code)
            failure.runtime_failure = record
            raise failure
        if record.get("kind") != kind:
            raise ScanError("SCANNER_PROTOCOL_STATE_MISMATCH")
        return record

    def send(self, value):
        raw = (canonical(value) + "\n").encode()
        if len(raw) > MAX_LINE_BYTES:
            raise ScanError("CONTROLLER_COMMAND_LIMIT")
        self.process.stdin.write(raw)
        self.process.stdin.flush()

    def release(self, approval_ref, approval_sha):
        self.approval_ref, self.approval_sha = str(approval_ref), approval_sha
        self.approval, _ = read_json(approval_ref, approval_sha)
        self.cfg, _ = read_json(self.manifest["configRef"], self.approval["runtimeConfigSha256"])
        self.send(dict(command="release", approvalRef=str(approval_ref), approvalSha256=approval_sha))
        self.handoff = self.expect("exec_handoff")
        self.ready = self.expect("scanner_ready")
        expected = {**self.reservation["identity"], "cmdlineSha256": argv_sha(self.manifest["argv"])}
        if (self.ready["identity"] != expected or self.ready["argv"] != self.manifest["argv"]
                or self.handoff["processId"] != self.process.pid or self.ready["processStart"]["processId"] != self.process.pid):
            raise ScanError("ACTUAL_EXEC_HANDOFF_MISMATCH")
        self.clock = Clock(self.ready["calibration"])
        write_json(scoped(self.cfg["artifactRoot"], self.cfg["readyReceipt"]), self.ready)

    def memory(self, *, final=False):
        tag = "after" if final else "before"
        root, refs = self.cfg["artifactRoot"], self.cfg["memory"][tag]
        argv = self.cfg["memoryCollectorCommandArgs"] + ["--pid", str(self.process.pid), "--output", refs["counter"]]
        result = subprocess.run(argv, capture_output=True, timeout=30)
        with scoped(root, refs["stdout"]).open("xb") as output:
            output.write(result.stdout)
        with scoped(root, refs["stderr"]).open("xb") as output:
            output.write(result.stderr)
        if result.returncode:
            raise ScanError("INDEPENDENT_COUNTER_PROCESS_FAILED")
        receipt = decode(result.stdout)
        if (receipt["identity"] != self.ready["identity"] or receipt["collectorProcessId"] == self.process.pid
                or receipt["commandArgs"] != argv or receipt["toolBuild"] != self.cfg["counterCollectorBuild"]):
            raise ScanError("COUNTER_PROCESS_RECEIPT_MISMATCH")
        receipt_sha = "sha256:" + file_sha256(scoped(root, refs["stdout"]))
        self.send(dict(command="memory_after" if final else "memory_before", receiptRef=refs["stdout"],
                       receiptSha256=receipt_sha, **(dict(postReceiptRef=self.cfg["postReceipt"],
                                                        postReceiptSha256=self.post_receipt_sha) if final else {})))
        ack = self.expect("memory_after_accepted" if final else "memory_before_accepted")
        capture = dict(schemaVersion=1, **self.cfg["context"], scanId=self.cfg["scanId"],
                       processId=self.cfg["processId"], collectorBuild=self.cfg["counterCollectorBuild"],
                       nativeProcessId=self.process.pid, counterFormat="linux_proc_status", kind="metadata_memory_counter_capture",
                       observedAt=receipt["observedAt"], toolBuild=receipt["toolBuild"],
                       collectorProcessId=receipt["collectorProcessId"], commandArgs=receipt["commandArgs"],
                       counterRef=refs["counter"], exitCode=result.returncode)
        write_json(scoped(root, refs["capture"]), capture)
        sample = dict(processId=self.cfg["processId"], scanId=self.cfg["scanId"], scannerBuild=self.cfg["context"]["scannerBuild"],
                      observedAt=receipt["observedAt"], peakResidentBytes=ack["peakResidentBytes"], counterCaptureRef=refs["capture"])
        self.memory_samples.append(sample)
        return sample

    def start_phase(self, name, command):
        self.send(dict(command=command))
        record = self.expect("phase_start")
        if record["phase"] != name:
            raise ScanError("PHASE_ORDER_MISMATCH")
        self.phases[name] = dict(start=record["event"])
        return record["event"]

    def end_phase(self, name):
        record = self.expect("phase_exit")
        if record["phase"] != name or record["event"]["exitCode"] != 0:
            raise ScanError("NATIVE_PHASE_FAILED")
        self.phases[name].update(end=record["event"], outputs=record["outputs"])
        return record

    def enumerate(self):
        self.start_phase("enumeration", "enumerate")
        return self.end_phase("enumeration")

    def begin_changes(self):
        return self.start_phase("changeStream", "begin_changes")

    def observe_change(self, observation_ref, observation_sha):
        self.send(dict(command="observed_change", observationRef=str(observation_ref), observationSha256=observation_sha))
        return self.expect("change_observed")

    def end_changes(self):
        self.send(dict(command="end_changes"))
        return self.end_phase("changeStream")

    def incremental(self):
        self.start_phase("incremental", "incremental")
        result = self.end_phase("incremental")
        self.expect("work_complete")
        return result

    def post_catalogue(self):
        root = self.cfg["artifactRoot"]
        argv = [sys.executable, "-B", str(Path(__file__).with_name("native_scan_runtime.py")), "catalogue",
                "--approval", self.approval_ref, "--approval-sha", self.approval_sha,
                "--clock", self.cfg["readyReceipt"], "--output", self.cfg["outputs"]["postScanObjects"]]
        env = {**os.environ, "GUIZE_POC_MANIFEST_REF": self.manifest_ref, "GUIZE_POC_MANIFEST_SHA": self.manifest_sha}
        result = subprocess.run(argv, capture_output=True, timeout=180, env=env)
        with scoped(root, self.cfg["postStderr"]).open("xb") as output:
            output.write(result.stderr)
        if result.returncode:
            raise ScanError("INDEPENDENT_POST_CATALOGUE_FAILED")
        self.post_receipt = decode(result.stdout)
        if (self.post_receipt["collectorProcessId"] == self.process.pid or self.post_receipt["scannerProcessId"] != self.process.pid
                or self.post_receipt["context"] != self.cfg["context"] or self.post_receipt["commandArgs"] != argv):
            raise ScanError("INDEPENDENT_POST_CATALOGUE_RECEIPT_MISMATCH")
        self.post_receipt_sha = write_json(scoped(root, self.cfg["postReceipt"]), self.post_receipt)
        return self.post_receipt

    def finish(self):
        self.send(dict(command="exit"))
        self.expect("exit_requested")
        returncode = self.process.wait(timeout=20)
        exit_event = self.clock.marker("process_exit", process_id=self.process.pid, exit_code=returncode)
        failure = None
        if returncode != 0 or set(self.phases) != {"enumeration", "changeStream", "incremental"} or len(self.memory_samples) != 2:
            failure = "SUCCESSFUL_COMPLETE_REAL_PROCESS_EXIT_REQUIRED"
        elif not (utc(self.approval["windowStart"]) <= utc(self.ready["processStart"]["observedAt"])
                  <= utc(exit_event["observedAt"]) <= utc(self.approval["windowEnd"])):
            failure = "ACTUAL_LIFETIME_OUTSIDE_APPROVED_WINDOW"
        facts = dict(context=self.cfg["context"], scanId=self.cfg["scanId"], changeSetId=self.cfg["changeSetId"],
                     processId=self.process.pid, argv=self.ready["argv"], calibration=self.ready["calibration"],
                     processStart=self.ready["processStart"], processExit=exit_event, phases=self.phases,
                     realWaitReturnCode=returncode, exitObservedAfterWait=True, observerProcessId=os.getpid(),
                     timingCollectorBuild=self.cfg["timingCollectorBuild"],
                     timingCollectorCommandArgs=self.cfg["timingCollectorCommandArgs"], memorySamples=self.memory_samples,
                     reservation=self.reservation, execHandoff=self.handoff, postCatalogue=self.post_receipt,
                     executionWindow={key: self.approval[key] for key in ("windowStart", "windowEnd")},
                     outcome="rejected" if failure else "accepted", failureReason=failure)
        root = self.cfg["artifactRoot"]
        write_json(scoped(root, self.cfg["phaseFacts"]), facts)
        if failure:
            raise ScanError(failure)
        for name in ("enumeration", "changeStream", "incremental"):
            argv = self.cfg["timingCollectorCommandArgs"] + ["--phase", name]
            completed = subprocess.run(argv, capture_output=True, timeout=20)
            with scoped(root, self.cfg["phaseCaptures"][name]).open("xb") as output:
                output.write(completed.stdout)
            with scoped(root, self.cfg["phaseStderr"][name]).open("xb") as output:
                output.write(completed.stderr)
            if completed.returncode:
                raise ScanError("NATIVE_TIMING_CAPTURE_PROCESS_FAILED")
        return facts

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        self.reader.join(timeout=5)
        for pipe in (self.process.stdin, self.process.stdout, self.trace, self.stderr):
            pipe.close()


def phase_capture(args):
    facts, _ = read_json(args.facts)
    own_build = "sha256:" + file_sha256(__file__)
    if (facts["exitObservedAfterWait"] is not True or facts["realWaitReturnCode"] != 0
            or facts["outcome"] != "accepted" or facts["failureReason"] is not None
            or facts["observerProcessId"] == facts["processId"]
            or own_build != facts["timingCollectorBuild"]
            or actual_argv() != facts["timingCollectorCommandArgs"] + ["--phase", args.phase]):
        raise ScanError("REAL_EXIT_AND_APPROVED_TIMING_COLLECTOR_REQUIRED")
    phase = facts["phases"][args.phase]
    events = [facts["processStart"], phase["start"], phase["end"], facts["processExit"]]
    if any(event["processId"] != facts["processId"] for event in events) or any(event["exitCode"] for event in events):
        raise ScanError("SAME_SUCCESSFUL_SCANNER_LIFETIME_REQUIRED")
    clock = Clock(facts["calibration"])
    window = facts["executionWindow"]
    if not utc(window["windowStart"]) <= utc(events[0]["observedAt"]) <= utc(events[-1]["observedAt"]) <= utc(window["windowEnd"]):
        raise ScanError("ACTUAL_LIFETIME_OUTSIDE_APPROVED_WINDOW")
    if ([event["type"] for event in events] != ["process_start", "phase_start", "phase_exit", "process_exit"]
            or any(type(event["monotonicNs"]) is not int for event in events)
            or any(event["observedAt"] != clock.mapped_utc(event["monotonicNs"]) for event in events)
            or any(abs(event["directWallNs"] - clock.wall - event["monotonicNs"] + clock.mono) > 1000000 for event in events)
            or any(left["monotonicNs"] > right["monotonicNs"] for left, right in zip(events, events[1:]))):
        raise ScanError("ACTUAL_ORDERED_CALIBRATED_LIFETIME_REQUIRED")
    emit(dict(schemaVersion=1, kind="native_metadata_phase_execution", context=facts["context"], phase=args.phase,
              scanId=facts["scanId"], changeSetId=facts["changeSetId"], collectorBuild=own_build,
              collectorCommandArgs=actual_argv(), argv=facts["argv"], processId=facts["processId"],
              events=[typed_event(event) for event in events]))


if __name__ == "__main__":
    try:
        if not sys.platform.startswith("linux"):
            raise ScanError("LINUX_NATIVE_RUNTIME_REQUIRED")
        parser = argparse.ArgumentParser()
        parser.add_argument("mode", choices=["phase"])
        parser.add_argument("--facts", required=True)
        parser.add_argument("--phase", required=True, choices=["enumeration", "changeStream", "incremental"])
        phase_capture(parser.parse_args())
    except (ScanError, OSError, ValueError, KeyError, TypeError) as failure:
        print(str(failure) if isinstance(failure, ScanError) else type(failure).__name__, file=sys.stderr)
        raise SystemExit(1)
