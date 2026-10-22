import copy
import hashlib
import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from metadata_scan import (
    JsonlSource, MAX_LINE_BYTES, ScanError, Scanner, TransientFailure,
    fetch_with_retry, file_sha256, generate_fixture,
)


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.fixture = self.root / "objects.jsonl"
        self.recipe = generate_fixture(
            self.fixture, file_count=17, directory_count=5, maximum_depth=3, seed=7)
        self.binding = dict(source_id="unit-fixture", fixture_sha256=self.recipe["fixtureSha256"],
                            snapshot_version="snapshot-1")
        self.database = self.root / "index.sqlite"
        self.scanner = Scanner(self.database, **self.binding)
        self.source = JsonlSource(self.fixture, page_size=4, **self.binding)
        self.addCleanup(self.temporary.cleanup)
        self.addCleanup(lambda: self.scanner.close() if self.scanner else None)

    def changes(self, events):
        return self.scanner.apply_changes({"sourceId": self.binding["source_id"],
                                           "fixtureSha256": self.binding["fixture_sha256"],
                                           "events": events})

    def complete(self):
        while not self.scanner.state()["complete"]:
            self.scanner.apply_page(self.source.page(self.scanner.state()["cursor"]))

    def record(self, object_id):
        return dict(self.scanner.db.execute(
            "SELECT * FROM objects WHERE object_id=?", (object_id,)).fetchone())

    def file(self, object_id="new-file", name="new file.mp4"):
        return {"objectId": object_id, "parentId": "d-000000000", "name": name,
                "path": "/" + name, "isDirectory": False, "sizeBytes": 19, "versionId": "v1"}

    def event(self, number, operation, *, record=None, object_id=None):
        result = {"sequence": number, "operation": operation,
                  "fromVersion": "snapshot-1" if number == 1 else f"change-{number-1}",
                  "toVersion": f"change-{number}"}
        result.update({"objectId": object_id} if operation == "delete" else {"record": record})
        return result

    def test_exact_population_depth_names_and_reproducible_bytes(self):
        self.complete()
        measured = self.scanner.profile()
        self.assertEqual((measured["file_count"], measured["directory_count"],
                          measured["directory_depth_max"], measured["object_count"]), (17, 5, 3, 22))
        self.assertGreater(measured["average_file_size"], 0)
        self.assertGreater(measured["names"]["nonAscii"], 0)
        self.assertEqual(measured["names"]["spaces"], 2)
        self.assertGreater(measured["names"]["maximumNameUtf8Bytes"], 180)
        other = self.root / "again.jsonl"
        generate_fixture(other, file_count=17, directory_count=5, maximum_depth=3, seed=7)
        self.assertEqual(self.fixture.read_bytes(), other.read_bytes())

    def test_actual_other_process_resumes_persisted_checkpoint(self):
        self.scanner.apply_page(self.source.page("0"))
        self.scanner.close()
        self.scanner = None
        code = (
            "import json,sys; from metadata_scan import Scanner,JsonlSource; "
            "b=json.loads(sys.argv[3]); s=Scanner(sys.argv[1],**b); "
            "p=JsonlSource(sys.argv[2],page_size=3,**b); "
            "\nwhile not s.state()['complete']: s.apply_page(p.page(s.state()['cursor']))"
            "\nprint(json.dumps(s.profile())); s.close()"
        )
        result = subprocess.run([sys.executable, "-B", "-c", code, str(self.database),
                                 str(self.fixture), json.dumps(self.binding)],
                                cwd=Path(__file__).parent, capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["object_count"], 22)
        self.scanner = Scanner(self.database, **self.binding)
        self.assertTrue(self.scanner.state()["complete"])

    def test_duplicate_in_page_rolls_back_entire_page_and_cursor(self):
        page = self.source.page("0")
        page["records"].append(copy.deepcopy(page["records"][1]))
        with self.assertRaises(sqlite3.IntegrityError):
            self.scanner.apply_page(page)
        self.assertEqual(self.scanner.state()["cursor"], "0")
        self.assertEqual(self.scanner.profile()["object_count"], 0)
        self.scanner.apply_page(self.source.page("0"))
        with self.assertRaises(ScanError):
            self.scanner.apply_page(self.source.page("0"))

    def test_injected_database_failure_preserves_resume_point(self):
        self.scanner.db.execute(
            "CREATE TRIGGER fail_second BEFORE INSERT ON objects "
            "WHEN NEW.object_id='d-000000001' BEGIN SELECT RAISE(ABORT,'injected'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.scanner.apply_page(self.source.page("0"))
        self.scanner.close()
        self.scanner = Scanner(self.database, **self.binding)
        self.assertEqual(self.scanner.state()["cursor"], "0")
        self.assertEqual(self.scanner.profile()["object_count"], 0)
        self.scanner.db.execute("DROP TRIGGER fail_second")
        self.complete()

    def test_cursor_loop_is_rejected_atomically(self):
        first = self.source.page("0")
        self.scanner.apply_page(first)
        second = self.source.page(first["nextCursor"])
        second["nextCursor"] = "0"
        with self.assertRaisesRegex(ScanError, "CURSOR_LOOP"):
            self.scanner.apply_page(second)
        self.assertEqual(self.scanner.profile()["object_count"], 4)
        self.assertEqual(self.scanner.state()["cursor"], first["nextCursor"])

    def test_source_page_binding_and_checkpoint_binding(self):
        for key, value in (("sourceId", "other"), ("snapshotVersion", "other"),
                           ("fixtureSha256", "0" * 64)):
            page = self.source.page("0")
            page[key] = value
            with self.assertRaisesRegex(ScanError, "PAGE_BINDING_MISMATCH"):
                self.scanner.apply_page(page)
        for key in self.binding:
            other = {**self.binding, key: "0" * 64 if key == "fixture_sha256" else "other"}
            with self.assertRaisesRegex(ScanError, "CHECKPOINT_BINDING_MISMATCH"):
                Scanner(self.database, **other)

    def test_fixture_replacement_wrong_digest_and_nonboundary_cursor(self):
        with self.assertRaisesRegex(ScanError, "CURSOR_NOT_LINE_BOUNDARY"):
            self.source.page("1")
        with self.assertRaises(ScanError):
            JsonlSource(self.fixture, **{**self.binding, "fixture_sha256": "0" * 64})
        with self.fixture.open("ab") as handle:
            handle.write(b"{}\n")
        with self.assertRaisesRegex(ScanError, "FIXTURE_CHANGED"):
            self.source.page("0")

    def test_malformed_oversized_and_unterminated_input_rejected(self):
        for number, raw in enumerate((b"{broken}\n", b"x" * (MAX_LINE_BYTES + 1) + b"\n", b"{}")):
            path = self.root / f"invalid-{number}.jsonl"
            path.write_bytes(raw)
            source = JsonlSource(path, **{**self.binding, "fixture_sha256": file_sha256(path)})
            with self.assertRaises(ScanError):
                source.page("0")

    def test_bad_hierarchy_multiple_roots_and_empty_scan_cannot_complete(self):
        for mode in ("parent", "path", "secondRoot", "empty"):
            page = self.source.page("0")
            if mode == "parent":
                page["records"][1]["parentId"] = "not-present"
            elif mode == "path":
                page["records"][1]["path"] = "/wrong"
            elif mode == "secondRoot":
                root = copy.deepcopy(page["records"][0])
                root["objectId"] = "other-root"
                page["records"].append(root)
            else:
                page["records"], page["nextCursor"] = [], None
            with self.assertRaises(ScanError):
                self.scanner.apply_page(page)
            self.assertEqual(self.scanner.profile()["object_count"], 0)

    def test_incremental_create_rename_delete_replay_and_path_reuse(self):
        self.complete()
        initial = self.file()
        renamed = {**initial, "name": "重命名.mp4", "path": "/重命名.mp4", "versionId": "v2"}
        events = [self.event(1, "create", record=initial),
                  self.event(2, "update", record=renamed),
                  self.event(3, "delete", object_id="new-file")]
        self.changes(events[:2])
        self.assertEqual(self.record("new-file")["path"], "/重命名.mp4")
        self.assertEqual(self.record("new-file")["object_id"], "new-file")
        self.changes(events)
        self.assertEqual(self.record("new-file")["deleted"], 1)
        self.assertEqual(self.scanner.profile()["file_count"], 17)
        self.assertEqual(self.scanner.state()["sequence"], 3)
        self.changes(events)
        self.assertEqual(self.scanner.state()["sequence"], 3)
        self.changes([self.event(4, "create", record=self.file("other", "重命名.mp4"))])
        self.assertEqual(self.record("other")["deleted"], 0)
        self.assertEqual(self.record("new-file")["deleted"], 1)

    def test_conflicting_replay_gap_and_version_drift_rejected(self):
        self.complete()
        first = self.event(1, "create", record=self.file())
        self.changes([first])
        conflict = copy.deepcopy(first)
        conflict["record"]["sizeBytes"] += 1
        invalid = [conflict, self.event(3, "delete", object_id="new-file"),
                   {**self.event(2, "delete", object_id="new-file"), "fromVersion": "drift"}]
        for event in invalid:
            with self.assertRaises(ScanError):
                self.changes([event])
        self.assertEqual(self.scanner.state()["sequence"], 1)
        self.assertEqual(self.record("new-file")["size_bytes"], 19)

    def test_change_batch_from_other_source_is_rejected(self):
        self.complete()
        for key in ("sourceId", "fixtureSha256"):
            batch = {"sourceId": self.binding["source_id"],
                     "fixtureSha256": self.binding["fixture_sha256"],
                     "events": [self.event(1, "create", record=self.file())]}
            batch[key] = "other"
            with self.assertRaisesRegex(ScanError, "CHANGE_BINDING_MISMATCH"):
                self.scanner.apply_changes(batch)
        self.assertEqual(self.scanner.state()["sequence"], 0)

    def test_bad_change_batch_rolls_back_earlier_valid_event(self):
        self.complete()
        events = [self.event(1, "create", record=self.file()),
                  self.event(2, "delete", object_id="absent")]
        with self.assertRaisesRegex(ScanError, "CHANGE_MISSING_OBJECT"):
            self.changes(events)
        self.assertEqual(self.scanner.state()["sequence"], 0)
        self.assertIsNone(self.scanner.db.execute(
            "SELECT 1 FROM objects WHERE object_id='new-file'").fetchone())
        self.assertEqual(self.scanner.db.execute("SELECT count(*) FROM events").fetchone()[0], 0)

    def test_changes_before_scan_and_nonempty_directory_mutation_rejected(self):
        with self.assertRaisesRegex(ScanError, "INCOMPLETE_INITIAL_SCAN"):
            self.changes([self.event(1, "create", record=self.file())])
        self.complete()
        with self.assertRaisesRegex(ScanError, "DELETE_NONEMPTY_OR_ROOT"):
            self.changes([self.event(1, "delete", object_id="d-000000000")])
        record = {"objectId": "d-000000001", "parentId": "d-000000000", "name": "moved",
                  "path": "/moved", "isDirectory": True, "sizeBytes": 0, "versionId": "v2"}
        with self.assertRaisesRegex(ScanError, "NONEMPTY_DIRECTORY_MOVE"):
            self.changes([self.event(1, "update", record=record)])

    def test_unrecognized_database_is_never_migrated(self):
        path = self.root / "unknown.sqlite"
        db = sqlite3.connect(path)
        db.execute("CREATE TABLE unrelated(secret TEXT)")
        db.close()
        before = path.read_bytes()
        with self.assertRaisesRegex(ScanError, "UNSUPPORTED_INDEX_VERSION"):
            Scanner(path, **self.binding)
        self.assertEqual(path.read_bytes(), before)

    def test_generator_rejects_false_depth_and_refuses_overwrite(self):
        for directory_count, depth in ((2, 3), (2, 0), (0, 0)):
            with self.assertRaisesRegex(ScanError, "UNACHIEVABLE_DIRECTORY_DEPTH"):
                generate_fixture(self.root / "bad", file_count=1, directory_count=directory_count,
                                 maximum_depth=depth)
        with self.assertRaises(FileExistsError):
            generate_fixture(self.fixture, file_count=1, directory_count=1, maximum_depth=0)


class RetryTests(unittest.TestCase):
    def test_transient_retry_delays_are_bounded_and_observed(self):
        now, observations, calls = [0.0], [], []
        def fetch(cursor):
            calls.append(cursor)
            if len(calls) < 3:
                raise TransientFailure(429 if len(calls) == 1 else 503, 0.2)
            return {"received": True}
        def sleep(delay):
            now[0] += delay
        result = fetch_with_retry(fetch, "bound-cursor", observations=observations,
                                  clock=lambda: now[0], sleep=sleep)
        self.assertTrue(result["received"])
        self.assertEqual(calls, ["bound-cursor"] * 3)
        self.assertEqual(now[0], 0.4)
        self.assertEqual([row["status"] for row in observations], [429, 503, "received"])

    def test_permanent_failure_is_not_retried(self):
        calls = []
        def fetch(cursor):
            calls.append(cursor)
            raise PermissionError("denied")
        with self.assertRaises(PermissionError):
            fetch_with_retry(fetch, "0", observations=[])
        self.assertEqual(len(calls), 1)

    def test_excessive_delay_attempt_limit_and_late_response_fail(self):
        def fail(cursor):
            raise TransientFailure(429, 100)
        with self.assertRaisesRegex(ScanError, "RETRY_BUDGET_EXCEEDED"):
            fetch_with_retry(fail, "0", observations=[], maximum_delay=1)
        with self.assertRaises(TransientFailure):
            fetch_with_retry(fail, "0", observations=[], attempts=1)
        now = [0.0]
        def late(cursor):
            now[0] += 2
            return {}
        with self.assertRaisesRegex(ScanError, "FETCH_EXCEEDED_DEADLINE"):
            fetch_with_retry(late, "0", observations=[], timeout=1, clock=lambda: now[0])


if __name__ == "__main__":
    unittest.main()
