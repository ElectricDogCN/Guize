import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import jsonschema
import yaml

from canonical_metadata import (
    ANCHOR, BASIC, PROFILE, CanonicalPair, CanonicalScanner,
    basic_record, generate_canonical, validate_profile,
)
from metadata_scan import ScanError, canonical, file_sha256


class CanonicalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.baseline, self.profiled = self.root/"basic.jsonl", self.root/"profiled.jsonl"
        self.recipe = generate_canonical(
            self.baseline, self.profiled, file_count=17, directory_count=5, maximum_depth=3, seed=7)
        self.scanner = CanonicalScanner(self.root/"index.sqlite", self.pair())
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(lambda: self.scanner.close() if self.scanner else None)

    def pair(self, baseline=None, profiled=None):
        baseline, profiled = baseline or self.baseline, profiled or self.profiled
        return CanonicalPair(baseline, profiled, baseline_sha256=file_sha256(baseline),
                             profiled_sha256=file_sha256(profiled), source_id="unit-canonical",
                             snapshot_version="baseline-v1", page_size=3)

    def complete(self):
        while not self.scanner.core.state()["complete"]:
            self.scanner.apply_next()

    def profiles(self):
        return [json.loads(line) for line in self.profiled.read_bytes().splitlines()]

    def write_pair(self, rows, prefix="changed", basic=None):
        a, b = self.root/(prefix+"-basic.jsonl"), self.root/(prefix+"-profiled.jsonl")
        a.write_bytes("".join(canonical(row)+"\n" for row in (basic if basic is not None else map(basic_record, rows))).encode("utf-8"))
        b.write_bytes("".join(canonical(row)+"\n" for row in rows).encode("utf-8"))
        return a, b

    def batch(self, events, profiles=()):
        return {"sourceId":"unit-canonical", "baselineSha256":self.recipe["baselineSha256"],
                "events":events, "profiles":list(profiles)}

    def event(self, sequence, operation, object_id, before, after):
        return {"eventId":f"event-{sequence}", "sequence":sequence, "objectId":object_id,
                "operation":operation, "beforeVersion":before, "afterVersion":after}

    def new_file(self, version="v1", path="new.txt"):
        return {"objectId":"new-object", "kind":"file", "versionId":version, "depth":1,
                "fileSizeBytes":19, "name":path, "path":path, "modifiedAt":"2026-01-01T00:00:00Z"}

    def test_generated_and_observed_streams_match_actual_frozen_schemas(self):
        schema = yaml.safe_load((Path(__file__).resolve().parents[2]/
                                "specs/poc/program.schema.yaml").read_text(encoding="utf-8"))
        validators = [jsonschema.Draft202012Validator(schema["$defs"][name],
                      format_checker=jsonschema.FormatChecker())
                      for name in ("metadataObjectRecord", "metadataProfiledObjectRecord")]
        self.complete()
        outputs = [self.root/"out-basic.jsonl", self.root/"out-profiled.jsonl", self.root/"versions.jsonl"]
        self.assertEqual(self.scanner.export(*outputs), 22)
        for paths, validator in zip(((self.baseline,outputs[0]),(self.profiled,outputs[1])), validators):
            for path in paths:
                for raw in path.read_bytes().splitlines():
                    validator.validate(json.loads(raw))
        self.assertCountEqual([json.loads(x) for x in self.baseline.read_bytes().splitlines()],
                              [json.loads(x) for x in outputs[0].read_bytes().splitlines()])
        self.assertCountEqual(self.profiles(), [json.loads(x) for x in outputs[1].read_bytes().splitlines()])
        records = self.profiles()
        self.assertEqual(sum(r["kind"]=="file" for r in records), 17)
        self.assertEqual(sum(r["kind"]=="directory" for r in records), 5)
        self.assertEqual(max(r["depth"] for r in records), 3)
        self.assertNotIn(ANCHOR, {r["objectId"] for r in records})
        actual = self.scanner.profile()
        self.assertEqual((actual["file_count"],actual["directory_count"],
                          actual["directory_depth_max"],actual["object_depth_max"]), (17,5,3,3))
        self.assertTrue(actual["complete"])
        self.assertEqual(len(outputs[2].read_bytes().splitlines()),22)

    def test_export_roundtrip_does_not_assume_opaque_id_order_is_topological(self):
        parent = {"objectId":"z-parent", "kind":"directory", "versionId":"v1", "depth":1,
                  "fileSizeBytes":0, "name":"dir", "path":"dir", "modifiedAt":"2026-01-01T00:00:00Z"}
        child = {**self.new_file(), "objectId":"a-child", "path":"dir/new.txt", "depth":2}
        a,b = self.write_pair([parent,child],prefix="opaque")
        first = CanonicalScanner(self.root/"opaque.sqlite",self.pair(a,b))
        self.addCleanup(first.close)
        while not first.core.state()["complete"]:
            first.apply_next()
        outputs = [self.root/"opaque-basic",self.root/"opaque-profiled",self.root/"opaque-versions"]
        self.assertEqual(first.export(*outputs),2)
        self.assertEqual([json.loads(x)["objectId"] for x in outputs[0].read_bytes().splitlines()],
                         ["z-parent","a-child"])
        second = CanonicalScanner(self.root/"reingested.sqlite",self.pair(outputs[0],outputs[1]))
        self.addCleanup(second.close)
        while not second.core.state()["complete"]:
            second.apply_next()
        self.assertEqual(second.profile()["object_count"],2)
        actual = second.db.execute("SELECT parent_id,path FROM objects WHERE object_id=\"a-child\"").fetchone()
        self.assertEqual(tuple(actual),("z-parent","/dir/new.txt"))

    def test_reopen_resumes_both_stream_offsets_and_binds_companion_digest(self):
        self.scanner.apply_next()
        cursor = self.scanner.core.state()["cursor"]
        self.assertIn(":",cursor)
        self.scanner.close()
        self.scanner = CanonicalScanner(self.root/"index.sqlite",self.pair())
        self.assertEqual(self.scanner.core.state()["cursor"],cursor)
        self.complete()
        rows = self.profiles()
        rows[0]["modifiedAt"]="2026-01-02T00:00:00Z"
        new_basic,new_profile=self.write_pair(rows)
        self.assertEqual(file_sha256(new_basic),file_sha256(self.baseline))
        with self.assertRaisesRegex(ScanError,"CHECKPOINT_BINDING_MISMATCH"):
            CanonicalScanner(self.root/"index.sqlite",self.pair(new_basic,new_profile))

    def test_profile_insertion_failure_rolls_back_core_page_cursor_and_metadata(self):
        self.scanner.db.execute(
            "CREATE TRIGGER reject_profile BEFORE INSERT ON canonical_profiles "
            "WHEN NEW.object_id='d-000000002' BEGIN SELECT RAISE(ABORT,'unit profile failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.scanner.apply_next()
        self.assertEqual(self.scanner.core.state()["cursor"],"0")
        self.assertEqual(self.scanner.db.execute("SELECT count(*) FROM objects").fetchone()[0],0)
        self.assertEqual(self.scanner.db.execute("SELECT count(*) FROM canonical_profiles").fetchone()[0],0)
        self.assertFalse(self.scanner.db.in_transaction)
        self.scanner.db.execute("DROP TRIGGER reject_profile")
        self.complete()

    def test_sqlite_implicit_rollback_preserves_failure_and_can_restart(self):
        self.scanner.db.execute(
            "CREATE TRIGGER reject_object BEFORE INSERT ON objects "
            "WHEN NEW.object_id='d-000000002' BEGIN SELECT RAISE(ROLLBACK,'implicit rollback'); END")
        with self.assertRaisesRegex(sqlite3.IntegrityError,"implicit rollback"):
            self.scanner.apply_next()
        self.assertEqual(self.scanner.core.state()["cursor"],"0")
        self.assertFalse(self.scanner.db.in_transaction)
        self.scanner.db.execute("DROP TRIGGER reject_object")
        self.complete()

    def test_canonical_create_rename_delete_replay_and_complete_post_catalogue(self):
        self.complete()
        created,updated=self.new_file(),self.new_file("v2","renamed.txt")
        events=[self.event(1,"create","new-object","absent","v1"),
                self.event(2,"update","new-object","v1","v2"),
                self.event(3,"delete","new-object","v2","absent")]
        self.scanner.apply_events(self.batch(events[:2],[created,updated]))
        row=self.scanner.db.execute("SELECT object_id,path FROM objects WHERE object_id='new-object'").fetchone()
        self.assertEqual(tuple(row),("new-object","/renamed.txt"))
        self.scanner.apply_events(self.batch(events,[created,updated]))
        self.scanner.apply_events(self.batch(events,[created,updated]))
        self.assertEqual(self.scanner.core.state()["sequence"],3)
        self.assertEqual(self.scanner.db.execute("SELECT deleted FROM objects WHERE object_id='new-object'").fetchone()[0],1)
        outputs=[self.root/"post-basic",self.root/"post-profile",self.root/"post-versions"]
        self.assertEqual(self.scanner.export(*outputs),22)
        self.assertCountEqual([json.loads(x) for x in outputs[0].read_bytes().splitlines()],
                              [json.loads(x) for x in self.baseline.read_bytes().splitlines()])
        self.assertNotIn(b"new-object",outputs[2].read_bytes())

    def test_wrong_before_version_late_in_batch_rolls_back_every_record_and_ledger(self):
        self.complete()
        events=[self.event(1,"create","new-object","absent","v1"),
                self.event(2,"update","new-object","wrong-before","v2")]
        with self.assertRaisesRegex(ScanError,"CANONICAL_BEFORE_VERSION_MISMATCH"):
            self.scanner.apply_events(self.batch(events,[self.new_file(),self.new_file("v2")]))
        self.assertEqual(self.scanner.core.state()["sequence"],0)
        for table in ("events","canonical_events"):
            self.assertEqual(self.scanner.db.execute("SELECT count(*) FROM "+table).fetchone()[0],0)
        self.assertIsNone(self.scanner.db.execute("SELECT 1 FROM objects WHERE object_id='new-object'").fetchone())

    def test_conflicting_event_id_and_metadata_replay_cannot_alias_accepted_event(self):
        self.complete()
        event=self.event(1,"create","new-object","absent","v1")
        self.scanner.apply_events(self.batch([event],[self.new_file()]))
        alias={**event,"eventId":"different-event"}
        with self.assertRaisesRegex(ScanError,"CONFLICTING_CANONICAL_REPLAY"):
            self.scanner.apply_events(self.batch([alias],[self.new_file()]))
        changed={**self.new_file(),"modifiedAt":"2026-01-02T00:00:00Z"}
        with self.assertRaisesRegex(ScanError,"CONFLICTING_CANONICAL_REPLAY"):
            self.scanner.apply_events(self.batch([event],[changed]))

    def test_pair_content_types_lengths_and_duplicate_json_fields_fail_closed(self):
        rows=self.profiles()
        basic=[basic_record(row) for row in rows]
        basic[0]["fileSizeBytes"]=False
        a,b=self.write_pair(rows,basic=basic)
        with self.assertRaisesRegex(ScanError,"CANONICAL_STREAM_CONTENT_MISMATCH"):
            self.pair(a,b).read("0")
        a,b=self.write_pair(rows,prefix="short")
        with a.open("ab") as handle:
            handle.write((canonical(basic_record(rows[-1]))+"\n").encode())
        pair=self.pair(a,b)
        cursor="0"
        with self.assertRaisesRegex(ScanError,"CANONICAL_STREAM_LENGTH_MISMATCH"):
            while True:
                _,cursor=pair.read(cursor)
                if cursor is None:
                    break
        a,b=self.write_pair(rows,prefix="duplicate")
        raw=a.read_text(encoding="utf8")
        a.write_text(raw.replace('{"depth":','{"depth":1,"depth":',1),encoding="utf8")
        with self.assertRaisesRegex(ScanError,"DUPLICATE_JSON_FIELD"):
            self.pair(a,b).read("0")

    def test_actual_missing_index_metadata_cannot_silently_disappear_from_export(self):
        self.complete()
        self.scanner.db.execute("DELETE FROM canonical_profiles WHERE object_id='f-000000001'")
        with self.assertRaisesRegex(ScanError,"MISSING_CANONICAL_PROFILE"):
            self.scanner.export(self.root/"a",self.root/"b",self.root/"c")

    def test_relative_path_depth_timestamps_reserved_anchor_and_cursor_constraints(self):
        for patch in ({"path":"/file"},{"path":"a/../file","depth":3},{"depth":0},
                      {"modifiedAt":"2026-01-01 00:00:00+00:00"},{"objectId":ANCHOR},
                      {"versionId":"absent"},{"fileSizeBytes":True}):
            row={**self.new_file(),**patch}
            with self.assertRaises(ScanError):
                validate_profile(row)
        pair=self.pair()
        with self.assertRaisesRegex(ScanError,"CURSOR_NOT_LINE_BOUNDARY"):
            pair.read("1:1")
        with self.profiled.open("ab") as handle:
            handle.write(b"{}\n")
        with self.assertRaisesRegex(ScanError,"FIXTURE_CHANGED"):
            pair.read("0")


if __name__=="__main__":
    unittest.main()
