"""Disposable unit fixtures, never an approved OpenList/scale measurement."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jsonschema
import yaml

from canonical_metadata import generate_canonical
from metadata_scan import ScanError, file_sha256
from native_memory import native_identity, parse_status, start_ticks
from native_scan_control import NativeRun, manifest_for
from native_scan_protocol import Clock, argv_sha, decode, read_json, utc, write_json
from native_scan_runtime import require_linux


class ProtocolTests(unittest.TestCase):
    def test_control_json_and_digest_reject_ambiguous_or_changed_bytes(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'\xff', b'{'):
            with self.assertRaises(ScanError):
                decode(raw)
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"record"
            digest = write_json(path, {"a": 1})
            self.assertEqual(read_json(path, digest)[0], {"a": 1})
            with self.assertRaises(FileExistsError):
                write_json(path, {"a": 2})
            path.write_bytes(b'{"a":2}')
            with self.assertRaisesRegex(ScanError, "HASH_MISMATCH"):
                read_json(path, digest)
            with self.assertRaisesRegex(ScanError, "LIMIT_OR_CHANGE"):
                read_json(path, limit=2)

    def test_one_clock_mapping_preserves_measured_ticks_and_raw_wall(self):
        clock = Clock()
        events = [clock.marker("unit") for _ in range(3)]
        twin = Clock(copy.deepcopy(clock.calibration))
        for event in events:
            self.assertEqual(event["observedAt"], twin.mapped_utc(event["monotonicNs"]))
            self.assertLessEqual(abs(event["directWallNs"] - clock.wall - event["monotonicNs"] + clock.mono), 1000000)
        with self.assertRaisesRegex(ScanError, "WALL_CLOCK_CHANGED"):
            clock.marker("unit", tick=clock.mono, wall=clock.wall+2000000)
        bad = copy.deepcopy(clock.calibration)
        bad["samples"][bad["chosen"]]["afterNs"] += 3000
        with self.assertRaisesRegex(ScanError, "UNCERTAINTY"):
            Clock(bad)


class NativeLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)
        self.here = Path(__file__).resolve().parent

    def supported(self):
        if sys.platform.startswith("linux"):
            return True
        with self.assertRaisesRegex(ScanError, "LINUX_NATIVE_RUNTIME_REQUIRED"):
            require_linux()
        with self.assertRaisesRegex(ScanError, "LINUX_NATIVE_RUNTIME_REQUIRED"):
            NativeRun("not-read", "not-read", trace_ref="not-created", stderr_ref="not-created")
        return False

    def prepare(self, alter_config=None, alter_manifest=None):
        def ref(name):
            return str(self.root/name)
        baseline, profiled = self.root/"baseline.jsonl", self.root/"profiled.jsonl"
        generate_canonical(baseline, profiled, file_count=5, directory_count=2, maximum_depth=2, seed=4)
        self.rows = [json.loads(row) for row in profiled.read_bytes().splitlines()]
        self.source = self.root/"unit-source"
        self.source.mkdir()
        for row in self.rows:
            path = self.source/row["path"]
            if row["kind"] == "directory":
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"x"*row["fileSizeBytes"])
        resource = ref("unit-resource.json")
        resource_sha = write_json(resource, {"unitFixtureOnly": True, "productionClaim": False})
        build = "unit-synthetic-scanner-v1"
        cfg = dict(executor="unit-executor", artifactRoot=str(self.root),
                   context=dict(configurationRef=resource, acceptanceProfile={"unitFixtureOnly": True},
                                subjectVersion=build, scannerBuild=build, manifestId="unit-inputs",
                                inputSamples=[dict(id="unit", immutableId="unit-v1", checksum="sha256:"+file_sha256(baseline))]),
                   scanId="unit-scan", changeSetId="unit-changes", sourceId="unit-controlled-source",
                   snapshotVersion="unit-v1", pageSize=2,
                   baseline=dict(ref=str(baseline), sha256="sha256:"+file_sha256(baseline)),
                   profiled=dict(ref=str(profiled), sha256="sha256:"+file_sha256(profiled)), database=ref("index.sqlite"),
                   outputs={key: ref(key+".jsonl") for key in ("objects", "filenameObjects", "enumeratedVersions", "events",
                                                             "appliedEvents", "traversedObjects", "postScanObjects")},
                   readyReceipt=ref("ready.json"), postReceipt=ref("post.json"), postStderr=ref("post.stderr"),
                   phaseFacts=ref("phase-facts.json"), phaseCaptures={key: ref(key+".json") for key in ("enumeration", "changeStream", "incremental")},
                   phaseStderr={key: ref(key+".stderr") for key in ("enumeration", "changeStream", "incremental")},
                   counterCollectorBuild="sha256:"+file_sha256(self.here/"native_memory.py"),
                   memory={tag: {key: ref(tag+"-"+key) for key in ("counter", "stdout", "stderr", "capture")}
                           for tag in ("before", "after")}, processId="unit-logical-scanner",
                   timingCollectorBuild="sha256:"+file_sha256(self.here/"native_scan_control.py"))
        cfg["timingCollectorCommandArgs"] = [sys.executable, "-B", str(self.here/"native_scan_control.py"),
                                              "phase", "--facts", cfg["phaseFacts"]]
        if alter_config:
            alter_config(cfg)
        config_ref, manifest_ref = ref("config.json"), ref("manifest.json")
        manifest = manifest_for(config_ref, cfg, (datetime.now(timezone.utc)+timedelta(seconds=90)).isoformat())
        if alter_manifest:
            alter_manifest(manifest)
        manifest_sha = write_json(manifest_ref, manifest)
        run = NativeRun(manifest_ref, manifest_sha, trace_ref=ref("scanner.stdout"), stderr_ref=ref("scanner.stderr"))
        self.addCleanup(run.close)
        identity = run.reservation["identity"]
        cfg["memoryCollectorCommandArgs"] = [sys.executable, "-B", str(self.here/"native_memory.py"),
            "--start-ticks", str(identity["startTicks"]), "--boot-id", identity["bootId"], "--exe", identity["executable"],
            "--exe-sha256", identity["executableSha256"], "--cmdline-sha256", argv_sha(manifest["argv"])]
        config_sha = write_json(config_ref, cfg)
        approved_at = datetime.now(timezone.utc)
        begin = approved_at+timedelta(milliseconds=50)
        approval = dict(decision="approved", reviewer="unit-independent-reviewer", manifestSha256=manifest_sha,
                        runtimeConfigRef=config_ref, runtimeConfigSha256=config_sha,
                        configurationRef=resource, configurationSha256=resource_sha, reservation=identity,
                        reservationAt=run.reservation["reservedAt"], approvedAt=approved_at.isoformat(),
                        windowStart=begin.isoformat(), windowEnd=(begin+timedelta(seconds=60)).isoformat())
        self.cfg, self.run, self.approval = cfg, run, approval
        return run

    def release(self, alter=None):
        approval = copy.deepcopy(self.approval)
        if alter:
            alter(approval)
        ref = self.root/"approval.json"
        digest = write_json(ref, approval)
        delay = (utc(approval["windowStart"])-datetime.now(timezone.utc)).total_seconds()
        if delay > 0:
            time.sleep(delay+0.001)
        self.run.release(ref, digest)

    def observation(self, sequence, operation, original=None, *, missing_evidence=False):
        # Controlled fixture versions are explicit unit labels. Attributes come from
        # actual local mutations/stat/read, and observedAt is taken after that observation.
        row = copy.deepcopy(original) if original else dict(objectId="unit-created", kind="file", versionId="v1",
                                                          depth=1, fileSizeBytes=0, name="new.bin", path="new.bin", modifiedAt="")
        path = self.source/row["path"]
        before = "absent" if operation == "create" else row["versionId"]
        after = "absent" if operation == "delete" else "v1" if operation == "create" else "v2"
        if operation == "delete":
            path.unlink()
            evidence = dict(unitSourcePath=str(path), exists=path.exists(), parentNames=sorted(p.name for p in path.parent.iterdir()))
            profile = None
        else:
            path.write_bytes(b"actual-unit-create" if operation == "create" else b"actual-unit-update")
            state = path.stat()
            profile = {**row, "versionId": after, "fileSizeBytes": state.st_size,
                       "modifiedAt": datetime.fromtimestamp(state.st_mtime, timezone.utc).isoformat()}
            evidence = dict(unitSourcePath=str(path), statSize=state.st_size, mtimeNs=state.st_mtime_ns,
                            contentSha256="sha256:"+file_sha256(path))
        evidence_ref = self.root/("evidence-"+str(sequence)+".json")
        evidence_sha = write_json(evidence_ref, evidence)
        event = dict(eventId="unit-event-"+str(sequence), sequence=sequence, objectId=row["objectId"],
                     operation=operation, beforeVersion=before, afterVersion=after)
        observation = dict(kind="controlled_source_change_observation", sourceId=self.cfg["sourceId"], event=event,
                           profile=profile, observedAt=self.run.clock.mapped_utc(time.monotonic_ns()),
                           evidenceRefs=[] if missing_evidence else [dict(ref=str(evidence_ref), sha256=evidence_sha)])
        ref = self.root/("observation-"+str(sequence)+".json")
        digest = write_json(ref, observation)
        return ref, digest, event, profile

    def until_incremental(self):
        self.run.memory()
        self.run.enumerate()
        self.run.begin_changes()
        files = [row for row in self.rows if row["kind"] == "file"]
        changes = [self.observation(1, "create"), self.observation(2, "update", files[0]),
                   self.observation(3, "delete", files[1])]
        for ref, digest, _, _ in changes:
            self.run.observe_change(ref, digest)
        self.run.end_changes()
        self.run.incremental()
        return changes

    def test_actual_linux_lifetime_counters_replay_post_catalogue_and_frozen_captures(self):
        if not self.supported():
            return
        run = self.prepare()
        pid = run.process.pid
        self.assertEqual(native_identity(pid), run.reservation["identity"])
        self.assertFalse(Path(self.cfg["database"]).exists())
        self.assertTrue(all(not Path(ref).exists() for ref in self.cfg["outputs"].values()))
        self.release()
        self.assertEqual(pid, run.ready["processStart"]["processId"])
        self.assertEqual(native_identity(pid)["startTicks"], run.reservation["identity"]["startTicks"])
        self.assertNotEqual(native_identity(pid)["cmdlineSha256"], run.reservation["identity"]["cmdlineSha256"])
        self.assertGreater(run.ready["processStart"]["monotonicNs"], run.handoff["monotonicNs"])
        changes = self.until_incremental()
        post = run.post_catalogue()
        run.memory(final=True)
        facts = run.finish()
        self.assertEqual(run.process.returncode, 0)
        self.assertFalse((Path("/proc")/str(pid)).exists())
        self.assertTrue(facts["exitObservedAfterWait"])
        self.assertNotEqual(facts["observerProcessId"], pid)
        self.assertNotEqual(post["collectorProcessId"], pid)
        schema = yaml.safe_load((self.here.parents[1]/"specs/poc/program.schema.yaml").read_text(encoding="utf-8"))
        for name in ("enumeration", "changeStream", "incremental"):
            capture, _ = read_json(self.cfg["phaseCaptures"][name])
            jsonschema.Draft202012Validator(schema["$defs"]["metadataPhaseExecution"], format_checker=jsonschema.FormatChecker()).validate(capture)
            self.assertEqual(capture["argv"], run.manifest["argv"])
            self.assertEqual(capture["collectorCommandArgs"], self.cfg["timingCollectorCommandArgs"]+["--phase", name])
            self.assertEqual([e["type"] for e in capture["events"]], ["process_start", "phase_start", "phase_exit", "process_exit"])
            for event in capture["events"]:
                self.assertEqual(event["processId"], pid)
                self.assertEqual(event["observedAt"], run.clock.mapped_utc(event["monotonicNs"]))
            self.assertEqual(capture["events"][0]["monotonicNs"], facts["processStart"]["monotonicNs"])
            self.assertEqual(capture["events"][-1]["monotonicNs"], facts["processExit"]["monotonicNs"])
            elapsed_utc = (utc(capture["events"][2]["observedAt"])-utc(capture["events"][1]["observedAt"])).total_seconds()
            elapsed_ticks = (capture["events"][2]["monotonicNs"]-capture["events"][1]["monotonicNs"])/1e9
            self.assertLessEqual(abs(elapsed_utc-elapsed_ticks), 1e-6)
        for tag in ("before", "after"):
            capture, _ = read_json(self.cfg["memory"][tag]["capture"])
            jsonschema.Draft202012Validator(schema["$defs"]["metadataMemoryCounterCapture"], format_checker=jsonschema.FormatChecker()).validate(capture)
            raw = Path(capture["counterRef"]).read_bytes()
            actual = parse_status(raw, pid)
            sample = facts["memorySamples"][0 if tag == "before" else 1]
            self.assertEqual(sample["peakResidentBytes"], actual["peakResidentBytes"])
            self.assertNotEqual(capture["collectorProcessId"], pid)
        self.assertLessEqual(utc(facts["memorySamples"][0]["observedAt"]), utc(facts["phases"]["enumeration"]["start"]["observedAt"]))
        self.assertLessEqual(utc(post["observedAt"]), utc(facts["memorySamples"][1]["observedAt"]))
        self.assertGreaterEqual(facts["memorySamples"][1]["peakResidentBytes"], facts["memorySamples"][0]["peakResidentBytes"])
        expected = {row["objectId"]: row["versionId"] for row in self.rows}
        for _, _, event, profile in changes:
            if profile:
                expected[event["objectId"]] = event["afterVersion"]
            else:
                expected.pop(event["objectId"])
        def rows(key):
            return [json.loads(line) for line in Path(self.cfg["outputs"][key]).read_bytes().splitlines()]
        self.assertEqual({row["objectId"]: row["versionId"] for row in rows("postScanObjects")}, expected)
        self.assertEqual([row["eventId"] for row in rows("appliedEvents")], [entry[2]["eventId"] for entry in changes])
        self.assertEqual({row["objectId"] for row in rows("traversedObjects")}, {entry[2]["objectId"] for entry in changes})
        self.assertEqual([row["observedAt"] for row in rows("events")], [read_json(entry[0])[0]["observedAt"] for entry in changes])
        identities = [(Path(ref).stat().st_dev, Path(ref).stat().st_ino) for ref in self.cfg["outputs"].values()]
        self.assertEqual(len(identities), len(set(identities)))

    def test_reservation_rejects_self_approval_wrong_pid_and_past_window(self):
        if not self.supported():
            return
        # A separate owned process/fixture for each rejection keeps each real exit observable.
        for mutation in (lambda a: a.update(reviewer="unit-executor"),
                         lambda a: a["reservation"].update(nativeProcessId=os.getpid()),
                         lambda a: a.update(approvedAt=(utc(a["windowStart"])+timedelta(seconds=1)).isoformat())):
            with tempfile.TemporaryDirectory() as temp:
                old_root = self.root
                self.root = Path(temp)
                run = self.prepare()
                with self.assertRaises(ScanError):
                    self.release(mutation)
                self.assertNotEqual(run.process.wait(timeout=10), 0)
                self.assertFalse(Path(self.cfg["database"]).exists())
                run.close()
                self.root = old_root

    def test_tampered_approved_config_prevents_exec_workload(self):
        if not self.supported():
            return
        run = self.prepare()
        with Path(run.manifest["configRef"]).open("ab") as output:
            output.write(b" ")
        with self.assertRaises(ScanError):
            self.release()
        # Controller rejects before sending. Deliver the already fixed release explicitly
        # to verify the launcher independently refuses those tampered bytes as well.
        self.assertIsNone(run.process.poll())
        approval_ref = self.root/"approval.json"
        run.send(dict(command="release", approvalRef=str(approval_ref), approvalSha256="sha256:"+file_sha256(approval_ref)))
        with self.assertRaises(ScanError):
            run.expect("exec_handoff")
        self.assertNotEqual(run.process.wait(timeout=10), 0)
        self.assertFalse(Path(self.cfg["database"]).exists())

    def test_scanner_requires_first_independent_counter_and_new_outputs(self):
        if not self.supported():
            return
        run = self.prepare()
        self.release()
        run.send(dict(command="enumerate"))
        with self.assertRaises(ScanError):
            run.expect("phase_start")
        self.assertNotEqual(run.process.wait(timeout=10), 0)
        self.assertFalse(Path(self.cfg["database"]).exists())
        self.assertTrue(all(not Path(ref).exists() for ref in self.cfg["phaseCaptures"].values()))

    def test_expected_change_row_without_source_evidence_is_rejected(self):
        if not self.supported():
            return
        run = self.prepare()
        self.release()
        run.memory()
        run.enumerate()
        run.begin_changes()
        event = dict(eventId="expected-only", sequence=1, objectId="new", operation="create", beforeVersion="absent", afterVersion="v1")
        ref = self.root/"expected-only.json"
        digest = write_json(ref, event)
        with self.assertRaises(ScanError):
            run.observe_change(ref, digest)
        self.assertNotEqual(run.process.wait(timeout=10), 0)
        self.assertFalse(Path(self.cfg["outputs"]["appliedEvents"]).exists())

    def test_actual_change_with_missing_evidence_is_rejected(self):
        if not self.supported():
            return
        run = self.prepare()
        self.release()
        run.memory()
        run.enumerate()
        run.begin_changes()
        ref, digest, _, _ = self.observation(1, "create", missing_evidence=True)
        with self.assertRaises(ScanError):
            run.observe_change(ref, digest)
        self.assertNotEqual(run.process.wait(timeout=10), 0)

    def test_final_counter_requires_post_catalogue_after_incremental(self):
        if not self.supported():
            return
        run = self.prepare()
        self.release()
        self.until_incremental()
        # Real counter receipt exists, but a substituted post receipt cannot release it.
        fake = dict(scannerProcessId=run.process.pid, collectorProcessId=os.getpid(), observedAt=run.ready["processStart"]["observedAt"])
        run.post_receipt_sha = write_json(self.cfg["postReceipt"], fake)
        with self.assertRaises(ScanError):
            run.memory(final=True)
        self.assertNotEqual(run.process.wait(timeout=10), 0)
        self.assertTrue(all(not Path(ref).exists() for ref in self.cfg["phaseCaptures"].values()))

    def test_existing_output_fails_before_scanner_ready(self):
        if not self.supported():
            return
        run = self.prepare()
        Path(self.cfg["outputs"]["objects"]).write_bytes(b"existing")
        with self.assertRaises(ScanError):
            self.release()
        self.assertNotEqual(run.process.wait(timeout=10), 0)
        self.assertEqual(Path(self.cfg["outputs"]["objects"]).read_bytes(), b"existing")

    def test_changed_runtime_source_closure_rejects_reservation(self):
        if not self.supported():
            return
        def changed(manifest):
            manifest["sourceFiles"][str(self.here/"native_scan_runtime.py")] = "sha256:"+"0"*64
        with self.assertRaises(ScanError):
            self.prepare(alter_manifest=changed)
        self.assertEqual(list(self.root.glob("index.sqlite*")), [])

    def test_changed_input_after_release_fails_actual_enumeration(self):
        if not self.supported():
            return
        run = self.prepare()
        self.release()
        run.memory()
        with Path(self.cfg["baseline"]["ref"]).open("ab") as output:
            output.write(b" ")
        with self.assertRaises(ScanError):
            run.enumerate()
        self.assertNotEqual(run.process.wait(timeout=10), 0)
        self.assertTrue(all(not Path(ref).exists() for ref in self.cfg["phaseCaptures"].values()))

    def test_timing_capture_refuses_nonzero_exit_or_rewritten_native_tick(self):
        if not self.supported():
            return
        run = self.prepare()
        self.release()
        self.until_incremental()
        run.post_catalogue()
        run.memory(final=True)
        facts = run.finish()
        for mutation in (lambda f: f.update(realWaitReturnCode=1),
                         lambda f: f["phases"]["enumeration"]["end"].update(monotonicNs=f["processStart"]["monotonicNs"]-1)):
            changed = copy.deepcopy(facts)
            mutation(changed)
            Path(self.cfg["phaseFacts"]).write_text(json.dumps(changed), encoding="utf-8")
            completed = subprocess.run(self.cfg["timingCollectorCommandArgs"]+["--phase", "enumeration"], capture_output=True, timeout=20)
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(completed.stdout, b"")
            self.assertTrue(completed.stderr)

    def test_real_exit_observation_after_window_preserves_failure_without_success_captures(self):
        if not self.supported():
            return
        run = self.prepare()
        # This disposable fixture approves a real finite future window. The harness
        # delays only the external observer after actual OS wait, never the raw clock.
        self.approval["windowEnd"] = (utc(self.approval["windowStart"])+timedelta(seconds=8)).isoformat()
        self.release()
        self.until_incremental()
        run.post_catalogue()
        run.memory(final=True)
        original_wait = run.process.wait
        def delayed_observer(*args, **kwargs):
            code = original_wait(*args, **kwargs)
            delay = (utc(self.approval["windowEnd"])-datetime.now(timezone.utc)).total_seconds()
            if delay > 0:
                time.sleep(delay+0.01)
            return code
        with patch.object(run.process, "wait", side_effect=delayed_observer):
            with self.assertRaisesRegex(ScanError, "ACTUAL_LIFETIME_OUTSIDE_APPROVED_WINDOW"):
                run.finish()
        facts, _ = read_json(self.cfg["phaseFacts"])
        self.assertEqual(run.process.returncode, 0)
        self.assertEqual(facts["realWaitReturnCode"], 0)
        self.assertTrue(facts["exitObservedAfterWait"])
        self.assertEqual(facts["outcome"], "rejected")
        self.assertEqual(facts["failureReason"], "ACTUAL_LIFETIME_OUTSIDE_APPROVED_WINDOW")
        self.assertGreater(utc(facts["processExit"]["observedAt"]), utc(self.approval["windowEnd"]))
        self.assertTrue(all(not Path(ref).exists() for ref in self.cfg["phaseCaptures"].values()))
        completed = subprocess.run(self.cfg["timingCollectorCommandArgs"]+["--phase", "enumeration"], capture_output=True, timeout=20)
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(completed.stdout, b"")


if __name__ == "__main__":
    unittest.main()
