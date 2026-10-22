from contextlib import closing
import hashlib
import http.server
import json
import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from openlist_listing import OpenListListing, SourceError

TOKEN = "unit-reader-token-not-for-real-use"


def item(name, directory=False, size=16):
    return dict(name=name, is_dir=directory, size=size, modified="2026-01-01T00:00:00Z",
                sign="", thumb="", type=0, created="2026-01-01T00:00:00Z", hash_info={})


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_POST(self):
        raw = self.rfile.read(int(self.headers["Content-Length"]))
        request = json.loads(raw)
        self.server.requests.append((self.path, request, self.headers.get("Authorization"), raw))
        status, body, headers, delay = self.server.respond(request)
        self.send_response(status)
        for key, value in headers.items():
            self.send_header(key, value)
        self.end_headers()
        if delay:
            time.sleep(delay)
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass


class ListingTests(unittest.TestCase):
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
        self.index = Path(self.tmp.name) / "listing.sqlite"
        self.server.requests = []
        self.tree = {"/fixtures": [item("z-dir", True, 4096), item("with space 视频.mp4"), item("a.txt", size=3)],
                     "/fixtures/z-dir": [item("inner.bin"), item("more.bin")]}
        self.server.respond = self.normal
        self.source = OpenListListing(self.origin, "fixtures", token=TOKEN)
        self.observations, self.pages = [], []

    def normal(self, request):
        rows = self.tree[request["path"]]
        offset = (request["page"] - 1) * request["per_page"]
        return self.reply(dict(code=200, message="success", data=dict(
            content=rows[offset:offset + request["per_page"]], total=len(rows), provider="unknown")))

    @staticmethod
    def reply(body, status=200, **headers):
        raw = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=True).encode()
        return status, raw, {"Content-Type": "application/json", "Content-Length": str(len(raw)), **headers}, 0

    def walk(self, **options):
        return self.source.walk(self.index, on_observation=self.observations.append,
                                on_page=self.pages.append, per_page=2, **options)

    def state(self):
        with closing(sqlite3.connect(self.index)) as db:
            return db.execute("SELECT completed,objects,pages FROM state").fetchone()

    def test_actual_paginated_tree_retains_real_requests_and_disk_frontier(self):
        result = self.walk()
        self.assertEqual((result["objectCount"], result["pageCount"]), (5, 3))
        self.assertFalse(result["stableProviderIdentityVerified"])
        self.assertFalse(result["snapshotVerified"])
        self.assertEqual(self.state(), (1, 5, 3))
        self.assertIsNone(self.pages[0]["requestCursor"])
        self.assertIsNone(self.pages[-1]["nextCursor"])
        for earlier, later in zip(self.pages, self.pages[1:]):
            self.assertEqual(earlier["nextCursor"], later["requestCursor"])
        self.assertEqual(json.loads(self.pages[0]["nextCursor"]), dict(directory="", page=2))
        self.assertEqual(json.loads(self.pages[1]["nextCursor"]), dict(directory="z-dir", page=1))
        with closing(sqlite3.connect(self.index)) as db:
            actual = db.execute("SELECT locator,fileSizeBytes,sourceSizeBytes FROM objects ORDER BY locator").fetchall()
        self.assertEqual(actual, [("a.txt", 3, 3), ("with space 视频.mp4", 16, 16),
                                  ("z-dir", 0, 4096), ("z-dir/inner.bin", 16, 16), ("z-dir/more.bin", 16, 16)])
        for path, request, authorization, raw in self.server.requests:
            self.assertEqual(path, "/api/fs/list")
            self.assertEqual(authorization, TOKEN)
            self.assertIs(request["refresh"], False)
            self.assertEqual(request["password"], "")
            self.assertTrue(request["path"].startswith("/fixtures"))
            self.assertNotIn(TOKEN.encode(), raw)
        for page in self.pages:
            for entry in page["entries"]:
                self.assertIsNone(entry["stableObjectId"])
                self.assertIsNone(entry["versionId"])
        for row in self.observations:
            self.assertEqual(row["status"], 200)
            self.assertEqual(row["bodyBytes"], len(row["body"]))
            self.assertEqual(row["bodySha256"], hashlib.sha256(row["body"]).hexdigest())
            self.assertEqual(row["requestBodySha256"], hashlib.sha256(row["requestBody"]).hexdigest())
            self.assertGreater(row["elapsedNs"], 0)
            self.assertLess(row["startedAt"], row["endedAt"])
        self.assertNotIn(TOKEN, repr(self.observations))

    def test_http200_application_auth_failure_is_retained_and_not_a_listing(self):
        self.server.respond = lambda _: self.reply(dict(code=401, message="expired", data=None))
        with self.assertRaisesRegex(SourceError, "LISTING_APPLICATION_FAILURE") as failure:
            self.walk()
        self.assertEqual(failure.exception.observation["status"], 200)
        self.assertEqual(failure.exception.observation["applicationCode"], 401)
        self.assertEqual(len(self.observations), 1)
        self.assertEqual(self.state(), (0, 0, 0))

    def test_actual_offset_timestamps_normalize_without_losing_raw_bytes_or_nanoseconds(self):
        cases = [
            ("2026-01-01T08:00:00+08:00", "2026-01-01T00:00:00Z"),
            ("2026-01-01T00:00:00.000000000+00:00", "2026-01-01T00:00:00Z"),
            ("2026-01-01T00:00:00-00:00", "2026-01-01T00:00:00Z"),
            ("2026-01-01T01:02:03.123456789+08:00", "2025-12-31T17:02:03.123456789Z"),
            ("2026-01-01T01:02:03.123456788+08:00", "2025-12-31T17:02:03.123456788Z"),
            ("2026-01-01T01:02:03.123400000-08:00", "2026-01-01T09:02:03.1234Z"),
            ("2026-01-01T08:00:01+08:00", "2026-01-01T00:00:01Z"),
        ]
        values = []
        for original, expected in cases:
            with self.subTest(original=original):
                obj = {**item("observed.bin"), "modified": original}
                self.tree["/fixtures"] = [obj]
                observation = self.source.observe(per_page=2)
                raw = observation["body"]
                total, entries = self.source.parse_page(observation)
                values.append(entries[0]["modifiedAt"])
                self.assertEqual(total, 1)
                self.assertEqual(entries[0]["modifiedAt"], expected)
                self.assertEqual(json.loads(raw)["data"]["content"][0]["modified"], original)
                self.assertEqual(observation["body"], raw)
                self.assertEqual(observation["bodySha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(observation["status"], 200)
        self.assertNotEqual(values[3], values[4])
        self.assertNotEqual(values[0], values[-1])
        for invalid in ("0001-01-01T00:00:00+08:00", "2026-01-01T00:00:00+24:00", "2026-02-30T00:00:00Z",
                        "2026-01-01T00:00:00+00:60", "2026-01-01T00:00:00-00:60", "2026-01-01T00:00:00+01:99"):
            with self.subTest(invalid=invalid):
                self.tree["/fixtures"] = [{**item("invalid.bin"), "modified": invalid}]
                observation = self.source.observe(per_page=2)
                with self.assertRaisesRegex(SourceError, "INVALID_LISTING_TIMESTAMP"):
                    self.source.parse_page(observation)

    def test_actual_http_quota_server_and_auth_failures_remain_actual_status(self):
        for status in (401, 429, 503):
            with self.subTest(status=status):
                self.server.respond = lambda _, status=status: self.reply(dict(code=status, data=None), status,
                                                                         **{"Retry-After": "2"})
                row = self.source.observe(per_page=2)
                self.assertEqual(row["status"], status)
                self.assertEqual(row["headers"]["retry-after"], "2")
                with self.assertRaises(SourceError):
                    self.source.parse_page(row)

    def test_scope_method_endpoint_and_limits_rejected_before_any_request(self):
        for origin in ("https://127.0.0.1:9", "http://localhost:9", "http://127.0.0.1:9/api/",
                       "http://user:pass@127.0.0.1:9", "http://127.0.0.1:9?x=1", "http://127.0.0.1:\t9"):
            with self.subTest(origin=origin), self.assertRaises(SourceError):
                OpenListListing(origin, "fixtures")
        for scope in ("", "/", "../x", "x//y", "x\\y", "x/./y", "@s", "@share/path"):
            with self.subTest(scope=scope), self.assertRaises(SourceError):
                OpenListListing(self.origin, scope)
        for kwargs in (dict(directory="../escape"), dict(page=0), dict(page=True), dict(per_page=0),
                       dict(per_page=1001), dict(maximum_bytes=0)):
            with self.subTest(kwargs=kwargs), self.assertRaises(SourceError):
                self.source.observe(**kwargs)
        self.assertEqual(self.server.requests, [])

    def test_same_origin_redirect_is_never_followed(self):
        self.server.respond = lambda _: self.reply(b"", 302, Location="/outside")
        with self.assertRaisesRegex(SourceError, "REDIRECT_REJECTED") as failure:
            self.walk()
        self.assertEqual(len(self.server.requests), 1)
        self.assertEqual(failure.exception.observation["status"], 302)
        self.assertEqual(self.state(), (0, 0, 0))

    def test_sensitive_signed_or_escaped_token_bodies_never_enter_observations(self):
        variants = [dict(code=200, data=dict(total=1, content=[{**item("f"), "sign": "capability"}])),
                    dict(code=200, data=dict(total=1, content=[{**item("f"), "thumb": "https://private/"}])),
                    dict(code=401, message=TOKEN, data=None),
                    (b'{"code":401,"message":"' + b"".join(("\\u%04x" % ord(c)).encode() for c in TOKEN) + b'"}'),
                    (b'{"code":401,"' + b"".join(("\\u%04x" % ord(c)).encode() for c in TOKEN) + b'":null}')]
        for body in variants:
            self.server.respond = lambda _, body=body: self.reply(body)
            with self.subTest(body_type=type(body).__name__), self.assertRaisesRegex(SourceError, "SENSITIVE_LISTING_CAPABILITY") as failure:
                self.source.observe(per_page=2)
            row = failure.exception.observation
            self.assertFalse(row["bodyRetained"])
            self.assertEqual(row["body"], b"")
            self.assertNotIn(TOKEN, repr(row))
            self.assertEqual(row["bodyOmittedReason"], "SENSITIVE_LISTING_CAPABILITY")
            self.assertGreater(row["bodyBytes"], 0)

    def test_wrong_cardinality_duplicate_names_and_total_drift_fail_partial(self):
        for mode in ("short", "duplicate", "drift"):
            with self.subTest(mode=mode):
                index = Path(self.tmp.name) / (mode + ".sqlite")
                def respond(request):
                    status, raw, headers, delay = self.normal(request)
                    body = json.loads(raw)
                    if request["page"] == 1 and mode == "short":
                        body["data"]["content"] = body["data"]["content"][:1]
                    if request["page"] == 2 and mode == "duplicate":
                        body["data"]["content"] = [item("z-dir", True)]
                    if request["page"] == 2 and mode == "drift":
                        body["data"]["total"] = 4
                        body["data"]["content"] = [item("a"), item("b")]
                    return self.reply(body)
                self.server.respond = respond
                with self.assertRaises(SourceError):
                    self.source.walk(index, on_observation=lambda _: None, on_page=lambda _: None, per_page=2)
                with closing(sqlite3.connect(index)) as db:
                    self.assertEqual(db.execute("SELECT completed FROM state").fetchone()[0], 0)

    def test_uninspectable_json_never_bypasses_secret_check_before_retention_callback(self):
        escaped = b"".join(("\\u%04x" % ord(c)).encode() for c in TOKEN)
        variants = [b'{"code":200,"data":{"sign":"unit-capability",',
                    b'{"code":200,"code":401,"message":"' + escaped + b'","data":null}']
        for number, raw in enumerate(variants):
            self.server.respond = lambda _, raw=raw: self.reply(raw)
            observed = []
            index = Path(self.tmp.name) / ("uninspectable-" + str(number) + ".sqlite")
            with self.subTest(number=number), self.assertRaisesRegex(SourceError, "UNINSPECTABLE_LISTING_BODY"):
                self.source.walk(index, on_observation=observed.append, on_page=lambda _: self.fail("accepted unsafe page"))
            self.assertEqual(len(observed), 1)
            row = observed[0]
            self.assertEqual(row["status"], 200)
            self.assertTrue(row["bodyComplete"])
            self.assertFalse(row["bodyRetained"])
            self.assertEqual(row["body"], b"")
            self.assertEqual(row["bodyOmittedReason"], "UNINSPECTABLE_LISTING_BODY")
            self.assertEqual(row["bodyBytes"], len(raw))
            self.assertEqual(row["bodySha256"], hashlib.sha256(raw).hexdigest())
            self.assertNotIn(TOKEN, repr(row))
            self.assertNotIn("unit-capability", repr(row))
            with closing(sqlite3.connect(index)) as db:
                self.assertEqual(db.execute("SELECT completed,objects,pages FROM state").fetchone(), (0, 0, 0))

    def test_invalid_names_types_dates_depth_and_duplicate_json_rejected(self):
        invalid = [{**item("f"), **override} for override in
                   (dict(name=".."), dict(name="a/b"), dict(name="a\\b"), dict(name="a\nb"),
                    dict(size=True), dict(size=-1), dict(is_dir=1), dict(modified="2026-02-30T00:00:00Z"),
                    dict(modified="2026-01-01T00:00:00"), dict(name="x" * 1025))]
        for record in invalid:
            self.server.respond = lambda _, record=record: self.reply(dict(code=200, data=dict(total=1, content=[record])))
            with self.subTest(record=record), self.assertRaises(SourceError):
                self.source.parse_page(self.source.observe(per_page=2))
        self.server.respond = lambda _: self.reply(b'{"code":200,"code":401,"data":null}')
        with self.assertRaises(SourceError):
            self.source.parse_page(self.source.observe())
        self.server.respond = lambda _: self.reply(dict(code=200, data=dict(total=1, content=[item("f")])))
        row = self.source.observe("/".join(["d"] * 64))
        with self.assertRaisesRegex(SourceError, "LISTING_PATH_OR_DEPTH_LIMIT"):
            self.source.parse_page(row)

    def test_empty_directory_is_actual_terminal_listing_without_anchor_object(self):
        self.server.respond = lambda _: self.reply(dict(code=200, data=dict(total=0, content=None)))
        self.assertEqual(self.walk()["objectCount"], 0)
        self.assertEqual(self.state(), (1, 0, 1))
        self.assertEqual(self.pages[0]["entries"], [])

    def test_existing_index_callback_failure_and_population_limit_never_complete(self):
        self.index.write_bytes(b"existing-owner-bytes")
        with self.assertRaises(FileExistsError):
            self.walk()
        self.assertEqual(self.index.read_bytes(), b"existing-owner-bytes")
        self.assertEqual(self.server.requests, [])
        other = Path(self.tmp.name) / "callback.sqlite"
        def failed(_):
            raise RuntimeError("retention-failed")
        with self.assertRaisesRegex(RuntimeError, "retention-failed"):
            self.source.walk(other, on_observation=self.observations.append, on_page=failed, per_page=2)
        with closing(sqlite3.connect(other)) as db:
            self.assertEqual(db.execute("SELECT completed FROM state").fetchone()[0], 0)
        limited = Path(self.tmp.name) / "limited.sqlite"
        with self.assertRaisesRegex(SourceError, "LISTING_POPULATION_LIMIT"):
            self.source.walk(limited, on_observation=self.observations.append, on_page=self.pages.append,
                             per_page=2, maximum_objects=1)
        with closing(sqlite3.connect(limited)) as db:
            self.assertEqual(db.execute("SELECT completed,objects FROM state").fetchone(), (0, 0))

    def test_oversized_truncated_socket_timeout_and_invalid_mime_keep_failure_facts(self):
        self.server.respond = lambda _: (200, b"x" * 33, {"Content-Type": "application/json"}, 0)
        with self.assertRaisesRegex(SourceError, "RESPONSE_BODY_LIMIT") as failure:
            self.source.observe(maximum_bytes=32)
        self.assertEqual(failure.exception.observation["bodyBytes"], 33)
        self.server.respond = lambda _: (200, b"short", {"Content-Type": "application/json", "Content-Length": "10"}, 0)
        with self.assertRaisesRegex(SourceError, "TRUNCATED_RESPONSE") as failure:
            self.source.observe()
        self.assertEqual(failure.exception.observation["body"], b"")
        self.assertEqual(failure.exception.observation["bodyOmittedReason"], "UNINSPECTABLE_LISTING_BODY")
        self.assertEqual(failure.exception.observation["bodyBytes"], 5)
        self.assertEqual(failure.exception.observation["bodySha256"], hashlib.sha256(b"short").hexdigest())
        self.server.respond = lambda _: (200, b"late", {"Content-Type": "application/json", "Content-Length": "4"}, .15)
        fast = OpenListListing(self.origin, "fixtures", timeout=.03)
        with self.assertRaises(SourceError) as failure:
            fast.observe()
        self.assertEqual(failure.exception.observation["error"], "SOURCE_TRANSPORT_FAILURE")
        self.assertFalse(failure.exception.observation["bodyComplete"])
        self.server.respond = lambda _: self.reply(dict(code=200, data=dict(total=0, content=None)),
                                                  **{"Content-Type": "text/html"})
        with self.assertRaisesRegex(SourceError, "LISTING_JSON_CONTENT_TYPE_REQUIRED"):
            self.source.parse_page(self.source.observe())


if __name__ == "__main__":
    unittest.main()
