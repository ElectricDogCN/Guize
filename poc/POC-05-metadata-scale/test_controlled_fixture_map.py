import hashlib
import http.server
import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path

import jsonschema
import yaml

from canonical_metadata import CanonicalPair
from controlled_fixture_map import ControlledFixtureMap
from metadata_scan import ScanError, canonical
from openlist_listing import OpenListListing
from test_openlist_listing import Handler, item


def profile(ident, path, kind="file", size=16):
    return dict(objectId=ident, kind=kind, versionId="fixture-v1", depth=len(path.split("/")),
                fileSizeBytes=0 if kind == "directory" else size, name=path.rsplit("/", 1)[-1],
                path=path, modifiedAt="2026-01-01T00:00:00Z")


class FixtureMapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.origin = "http://127.0.0.1:" + str(cls.server.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.rows = [profile("z-parent", "dir", "directory"), profile("a-child", "dir/f.mp4"),
                     profile("root-file", "root.txt", size=3)]
        basic = [{k: row[k] for k in ("objectId", "kind", "versionId", "depth", "fileSizeBytes")} for row in self.rows]
        for name, rows in (("basic", basic), ("profiled", self.rows)):
            (self.root / name).write_bytes(b"".join((canonical(row) + "\n").encode() for row in rows))
        self.pair = CanonicalPair(self.root / "basic", self.root / "profiled",
                                  baseline_sha256=hashlib.sha256((self.root / "basic").read_bytes()).hexdigest(),
                                  profiled_sha256=hashlib.sha256((self.root / "profiled").read_bytes()).hexdigest(),
                                  source_id="controlled-unit-source", snapshot_version="fixture-v1", page_size=1)
        self.source = OpenListListing(self.origin, "fixtures")
        self.identity = dict(adapterId="controlled-listing-unit", adapterBuild="unit-code", sourceId="controlled-unit-source",
                             sourceVersion="unit-http-not-real-openlist")
        self.mapping = ControlledFixtureMap(self.root / "map.sqlite", self.pair, self.source, source_identity=self.identity)
        self.addCleanup(self.mapping.close)
        self.tree = {"/fixtures": [item("dir", True, 4096), item("root.txt", size=3)],
                     "/fixtures/dir": [item("f.mp4")]}
        self.server.requests = []
        self.server.respond = self.respond

    def respond(self, request):
        rows = self.tree[request["path"]]
        offset = (request["page"] - 1) * request["per_page"]
        raw = json.dumps(dict(code=200, data=dict(total=len(rows), content=rows[offset:offset+request["per_page"]]))).encode()
        return 200, raw, {"Content-Type": "application/json", "Content-Length": str(len(raw))}, 0

    def run_listing(self, run_id, *, per_page=1):
        self.mapping.begin_run(run_id)
        self.bound = []
        def bind(page):
            self.bound.append(self.mapping.bind_page(run_id, page))
        return self.source.walk(self.root / (run_id + ".sqlite"), on_observation=lambda _: None,
                                on_page=bind, per_page=per_page)

    def one_page(self):
        observation = self.source.observe(per_page=200)
        total, entries = self.source.parse_page(observation)
        return dict(observation=observation, entries=entries, directoryTotal=total,
                    requestCursor=None, nextCursor='{"directory":"dir","page":1}')

    def test_extra_empty_password_field_is_rejected_even_with_matching_raw_hash(self):
        self.mapping.begin_run("extra-field")
        page = self.one_page()
        request = json.loads(page["observation"]["requestBody"])
        request["password"] = ""
        raw = canonical(request).encode()
        page["observation"]["requestBody"] = raw
        page["observation"]["requestBodySha256"] = hashlib.sha256(raw).hexdigest()
        with self.assertRaisesRegex(ScanError, "CONTROLLED_REQUEST_MISMATCH"):
            self.mapping.bind_page("extra-field", page)

    def test_actual_repeated_listings_export_full_observed_population_with_explicit_ids(self):
        schema = yaml.safe_load((Path(__file__).resolve().parents[2] / "specs/poc/program.schema.yaml").read_text(encoding="utf8"))["$defs"]["metadataProfiledObjectRecord"]
        for run_id in ("run-one", "run-two"):
            self.assertTrue(self.run_listing(run_id)["completed"])
            self.assertEqual(self.mapping.state(run_id)["objects"], 3)
            output = self.root / (run_id + ".jsonl")
            result = self.mapping.export_observed(run_id, output)
            self.assertEqual(result["count"], 3)
            self.assertFalse(result["stableProviderIdentityVerified"])
            observed = [json.loads(raw) for raw in output.read_bytes().splitlines()]
            self.assertEqual(sorted(map(canonical, observed)), sorted(map(canonical, self.rows)))
            for row in observed:
                jsonschema.validate(row, schema)
            self.assertIsNone(self.bound[0]["header"]["requestCursor"])
            self.assertIsNone(self.bound[-1]["header"]["nextCursor"])
            self.assertTrue(self.bound[-1]["completePopulationMapped"])
            self.assertTrue(all(row["header"]["statusCode"] == 200 for row in self.bound))
            for row in self.bound:
                self.assertEqual(row["header"]["sourceIdentity"], self.identity)
                self.assertTrue(row["header"]["providerTimestamp"].endswith("Z"))
        with closing(sqlite3.connect(self.root / "map.sqlite")) as db:
            self.assertEqual(db.execute("SELECT fileSizeBytes,sourceSizeBytes FROM observed WHERE runId='run-one' AND objectId='z-parent'").fetchone(), (0, 4096))

    def test_observed_metadata_mismatch_is_rejected_rather_than_filled_from_approved(self):
        for number, changed in enumerate((dict(size=15), dict(is_dir=True), dict(modified="2026-01-01T00:00:00.000000001Z"))):
            self.tree["/fixtures/dir"] = [{**item("f.mp4"), **changed}]
            run_id = "mismatch-" + str(number)
            with self.assertRaisesRegex(ScanError, "CONTROLLED_OBSERVED_METADATA_MISMATCH"):
                self.run_listing(run_id)
            self.assertEqual(self.mapping.state(run_id)["completed"], 0)
            with self.assertRaisesRegex(ScanError, "INCOMPLETE_CONTROLLED_RUN"):
                self.mapping.export_observed(run_id, self.root / (run_id + ".jsonl"))

    def test_equivalent_offset_complete_population_keeps_raw_and_exports_canonical_time(self):
        original = "2026-01-01T08:00:00+08:00"
        for entries in self.tree.values():
            for entry in entries:
                entry["modified"] = original
        run_id, observations = "equivalent-offset", []
        self.mapping.begin_run(run_id)
        result = self.source.walk(self.root / "equivalent-listing.sqlite", on_observation=observations.append,
                                  on_page=lambda page: self.mapping.bind_page(run_id, page), per_page=1)
        self.assertEqual(result["objectCount"], 3)
        self.assertTrue(self.mapping.state(run_id)["completed"])
        output = self.root / "equivalent-profiled.jsonl"
        self.assertEqual(self.mapping.export_observed(run_id, output)["count"], 3)
        observed = [json.loads(raw) for raw in output.read_bytes().splitlines()]
        self.assertEqual(sorted(map(canonical, observed)), sorted(map(canonical, self.rows)))
        self.assertEqual(len(observations), 3)
        for observation in observations:
            raw = observation["body"]
            self.assertEqual(observation["status"], 200)
            self.assertEqual(observation["bodySha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(observation["bodyBytes"], len(raw))
            for entry in json.loads(raw)["data"]["content"]:
                self.assertEqual(entry["modified"], original)

    def test_terminal_listing_must_cover_every_approved_object(self):
        self.tree["/fixtures"] = [item("dir", True, 4096)]
        with self.assertRaisesRegex(ScanError, "INCOMPLETE_CONTROLLED_POPULATION"):
            self.run_listing("missing")
        self.assertEqual(self.mapping.state("missing")["completed"], 0)

    def test_unknown_later_record_rolls_back_whole_bound_page_and_cursor(self):
        self.tree["/fixtures"] = [item("dir", True), item("unknown.txt")]
        self.mapping.begin_run("atomic")
        page = self.one_page()
        with self.assertRaisesRegex(ScanError, "UNKNOWN_CONTROLLED_FIXTURE_LOCATOR"):
            self.mapping.bind_page("atomic", page)
        self.assertEqual(self.mapping.state("atomic")["objects"], 0)
        self.assertIsNone(self.mapping.state("atomic")["nextCursor"])
        self.assertEqual(self.mapping.db.execute("SELECT count(*) FROM observed").fetchone()[0], 0)

    def test_raw_or_parsed_page_mutation_cannot_replace_actual_observation(self):
        for number, mode in enumerate(("raw", "request", "parsed", "date")):
            page = self.one_page()
            self.mapping.begin_run("mutated-" + str(number))
            if mode == "raw":
                page["observation"]["body"] += b" "
            elif mode == "request":
                page["observation"]["requestBody"] += b" "
            elif mode == "parsed":
                page["entries"][0]["modifiedAt"] = "2025-01-01T00:00:00Z"
            else:
                del page["observation"]["headers"]["date"]
            with self.subTest(mode=mode), self.assertRaises(ScanError):
                self.mapping.bind_page("mutated-" + str(number), page)

    def test_cursor_replay_reused_run_and_export_before_completion_fail(self):
        self.mapping.begin_run("cursor")
        page = self.one_page()
        self.mapping.bind_page("cursor", page)
        with self.assertRaisesRegex(ScanError, "CONTROLLED_CURSOR_OR_TERMINAL_MISMATCH"):
            self.mapping.bind_page("cursor", page)
        with self.assertRaisesRegex(ScanError, "CONTROLLED_RUN_ALREADY_EXISTS"):
            self.mapping.begin_run("cursor")
        with self.assertRaisesRegex(ScanError, "INCOMPLETE_CONTROLLED_RUN"):
            self.mapping.export_observed("cursor", self.root / "incomplete.jsonl")
        with self.assertRaisesRegex(ScanError, "UNKNOWN_CONTROLLED_RUN"):
            self.mapping.state("unknown")

    def test_wrong_identity_or_existing_map_never_overwrites_owner_bytes(self):
        with self.assertRaisesRegex(ScanError, "INVALID_CONTROLLED_SOURCE_BINDING"):
            ControlledFixtureMap(self.root / "bad.sqlite", self.pair, self.source,
                                 source_identity={**self.identity, "sourceId": "foreign"})
        existing = self.root / "existing.sqlite"
        existing.write_bytes(b"owned-existing")
        with self.assertRaises(FileExistsError):
            ControlledFixtureMap(existing, self.pair, self.source, source_identity=self.identity)
        self.assertEqual(existing.read_bytes(), b"owned-existing")


if __name__ == "__main__":
    unittest.main()
