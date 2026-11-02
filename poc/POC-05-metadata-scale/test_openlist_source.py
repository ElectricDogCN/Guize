import base64
import copy
import hashlib
import http.server
import json
import threading
import time
import unittest
from xml.sax.saxutils import escape

from openlist_source import OpenListSource, PROPFIND_BODY, SourceError

PAYLOAD = b"0123456789abcdef"
AUTH = "Basic " + base64.b64encode(b"unit-reader:unit-pass").decode()


def dav_response(href, collection=False, properties=None, unavailable=()):
    values = {"resourcetype": "<d:collection/>" if collection else "",
              "getcontentlength": "0" if collection else "16", "getetag": "&quot;unit-v1&quot;",
              "getlastmodified": "Mon, 01 Jan 2024 00:00:00 GMT"}
    if properties is not None:
        values = properties
    success = "".join("<d:"+key+">"+value+"</d:"+key+">" for key, value in values.items())
    absent = "".join("<d:"+key+"/>" for key in unavailable)
    return ("<d:response><d:href>"+escape(href)+"</d:href><d:propstat><d:prop>"+success+
            "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat>"+
            ("<d:propstat><d:prop>"+absent+"</d:prop><d:status>HTTP/1.1 404 Not Found"
             "</d:status></d:propstat>" if absent else "")+"</d:response>")


def multistatus(*entries):
    return ('<?xml version="1.0" encoding="utf-8"?><d:multistatus xmlns:d="DAV:">'+
            "".join(entries)+"</d:multistatus>").encode()


class DavHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, body=b"", **headers):
        self.send_response(status)
        for name, value in headers.items():
            self.send_header(name.replace("_", "-"), value)
        self.end_headers()
        if self.command != "HEAD":
            try:
                self.wfile.write(body)
            except ConnectionError:
                pass

    def authorized(self):
        self.server.requests.append({"method": self.command, "path": self.path,
                                     "depth": self.headers.get("Depth"),
                                     "authorized": self.headers.get("Authorization") == AUTH})
        if self.headers.get("Authorization") != AUTH:
            self.reply(401, b"denied", Content_Length="6")
            return False
        return True

    def do_PROPFIND(self):
        if not self.authorized():
            return
        body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
        self.server.request_bodies.append(body)
        raw = multistatus(dav_response("/dav/lab/", True),
                          dav_response("/dav/lab/with%20space%20%E8%A7%86%E9%A2%91.mp4"))
        self.reply(207, raw, Content_Length=str(len(raw)), Content_Type="application/xml")

    def do_HEAD(self):
        if self.authorized():
            self.reply(200, Content_Length="16", ETag='"unit-v1"', Accept_Ranges="bytes")

    def do_GET(self):
        if not self.authorized():
            return
        if self.path == "/dav/lab/redirect":
            self.reply(302, Location="/outside")
        elif self.path == "/outside":
            self.reply(200, b"outside")
        elif self.path.endswith("/large"):
            self.reply(200, b"x" * 1024, Content_Length="1024")
        elif self.path.endswith("/unknown-length"):
            self.reply(200, b"x" * 17)
        elif self.path.endswith("/short"):
            self.reply(200, b"short", Content_Length="10")
        elif self.path.endswith("/slow"):
            time.sleep(0.15)
            self.reply(200, b"slow", Content_Length="4")
        elif self.path.endswith("/limited"):
            self.reply(429, b"limited", Content_Length="7", Retry_After="2")
        elif self.headers.get("Range") == "bytes=2-5" and self.headers.get("If-Range") != '"old"':
            self.reply(206, PAYLOAD[2:6], Content_Length="4", Content_Range="bytes 2-5/16",
                       ETag='"unit-v1"')
        elif self.headers.get("Range") == "bytes=100-":
            self.reply(416, b"", Content_Length="0", Content_Range="bytes */16")
        elif self.headers.get("If-None-Match") == '"unit-v1"':
            self.reply(304, ETag='"unit-v1"')
        else:
            self.reply(200, PAYLOAD, Content_Length="16", ETag='"unit-v1"')


class DavTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), DavHandler)
        cls.server.daemon_threads = True
        cls.server.requests, cls.server.request_bodies = [], []
        cls.thread = threading.Thread(target=lambda: cls.server.serve_forever(poll_interval=0.01))
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_port}/dav/lab/"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        if cls.thread.is_alive():
            raise AssertionError("Owned HTTP test listener did not stop")

    def setUp(self):
        self.client = OpenListSource(self.base, username="unit-reader", password="unit-pass")

    def listing(self, raw):
        return {"method": "PROPFIND", "status": 207, "bodyComplete": True, "body": raw, "locator": ""}

    def test_real_http_propfind_preserves_metadata_without_inventing_identity(self):
        observation = self.client.observe("PROPFIND", maximum_bytes=65536)
        parsed = self.client.directory_entries(observation)
        self.assertEqual([e["locator"] for e in parsed["entries"]], ["", "with space 视频.mp4"])
        self.assertEqual(parsed["entries"][1]["sizeBytes"], 16)
        self.assertEqual(parsed["entries"][1]["etag"], '"unit-v1"')
        self.assertTrue(all(e["stableObjectId"] is None for e in parsed["entries"]))
        self.assertFalse(parsed["paginationImplemented"])
        self.assertFalse(parsed["sourcePaginationProbed"])
        self.assertFalse(parsed["snapshotConsistencyValidated"])
        self.assertEqual(self.server.request_bodies[-1], PROPFIND_BODY)
        self.assertEqual(self.server.requests[-1]["depth"], "1")
        self.assertEqual(observation["bodySha256"], hashlib.sha256(observation["body"]).hexdigest())
        self.assertGreater(observation["monotonicEndNs"], observation["monotonicStartNs"])

    def test_range_fallback_invalid_range_and_conditional_response_are_raw_observations(self):
        ordinary = self.client.observe("GET", "with space 视频.mp4", maximum_bytes=32)
        self.assertEqual(ordinary["body"], PAYLOAD)
        self.assertIn("with%20space%20%E8%A7%86%E9%A2%91.mp4", self.server.requests[-1]["path"])
        ranged = self.client.observe("GET", "file", maximum_bytes=32, headers={"Range": "bytes=2-5"})
        self.assertEqual((ranged["status"], ranged["body"], ranged["headers"]["content-range"]),
                         (206, b"2345", "bytes 2-5/16"))
        fallback = self.client.observe("GET", "file", maximum_bytes=32,
                                       headers={"Range": "bytes=2-5", "If-Range": '"old"'})
        self.assertEqual((fallback["status"], fallback["body"]), (200, PAYLOAD))
        invalid = self.client.observe("GET", "file", maximum_bytes=32, headers={"Range": "bytes=100-"})
        self.assertEqual((invalid["status"], invalid["headers"]["content-range"]), (416, "bytes */16"))
        conditional = self.client.observe("GET", "file", maximum_bytes=1,
                                          headers={"If-None-Match": '"unit-v1"'})
        self.assertEqual((conditional["status"], conditional["body"]), (304, b""))

    def test_anonymous_denial_and_rate_limit_are_retained_not_treated_as_success(self):
        anonymous = OpenListSource(self.base).observe("GET", "file", maximum_bytes=32)
        self.assertEqual((anonymous["status"], anonymous["body"]), (401, b"denied"))
        limited = self.client.observe("GET", "limited", maximum_bytes=32)
        self.assertEqual((limited["status"], limited["headers"]["retry-after"]), (429, "2"))

    def test_credentials_never_appear_in_observations(self):
        observation = self.client.observe("GET", "file", maximum_bytes=32)
        raw = repr(observation)
        self.assertNotIn("unit-pass", raw)
        self.assertNotIn(AUTH, raw)
        self.assertNotIn("Authorization", raw)
        self.assertTrue(self.server.requests[-1]["authorized"])

    def test_redirect_is_not_followed_even_to_same_origin(self):
        previous = len(self.server.requests)
        with self.assertRaisesRegex(SourceError, "REDIRECT_REJECTED") as error:
            self.client.observe("GET", "redirect", maximum_bytes=32)
        self.assertEqual(error.exception.observation["status"], 302)
        self.assertEqual(len(self.server.requests), previous + 1)
        self.assertFalse(error.exception.observation["bodyComplete"])

    def test_limits_truncation_and_transport_failure_keep_partial_facts(self):
        for locator in ("large", "unknown-length"):
            with self.assertRaisesRegex(SourceError, "RESPONSE_BODY_LIMIT") as error:
                self.client.observe("GET", locator, maximum_bytes=8)
            self.assertLessEqual(error.exception.observation["bodyBytes"], 9)
            self.assertFalse(error.exception.observation["bodyComplete"])
            self.assertEqual(error.exception.observation["status"], 200)
        with self.assertRaises(SourceError) as error:
            self.client.observe("GET", "short", maximum_bytes=32)
        self.assertEqual(error.exception.code, "TRUNCATED_RESPONSE")
        self.assertEqual(error.exception.observation["body"], b"short")
        impatient = OpenListSource(self.base, username="unit-reader", password="unit-pass", timeout=0.03)
        with self.assertRaisesRegex(SourceError, "SOURCE_TRANSPORT_FAILURE") as error:
            impatient.observe("GET", "slow", maximum_bytes=32)
        self.assertIn("endedAt", error.exception.observation)

    def test_head_can_observe_large_source_without_reading_payload(self):
        observation = self.client.observe("HEAD", "file", maximum_bytes=1)
        self.assertEqual((observation["status"], observation["body"]), (200, b""))
        self.assertEqual(observation["headers"]["content-length"], "16")

    def test_read_only_scope_validation_happens_before_network(self):
        previous = len(self.server.requests)
        for method, locator, headers in (("PUT", "file", None), ("GET", "../escape", None),
                                          ("GET", "/outside", None), ("GET", "a\\b", None),
                                          ("GET", "file", {"Authorization": "forbidden"}),
                                          ("GET", "file", {"Range": "bytes=1-2\r\nX: injected"})):
            with self.assertRaises(SourceError):
                self.client.observe(method, locator, maximum_bytes=32, headers=headers)
        self.assertEqual(len(self.server.requests), previous)
        for base in ("http://example.com/dav/", self.base+"?token=x",
                     self.base.replace("127.0.0.1", "localhost"), self.base.replace("/dav/", "/other/"),
                     self.base.replace("http://", "http://user:pass@")):
            with self.assertRaises(SourceError):
                OpenListSource(base)

    def test_optional_404_properties_are_explicit_and_required_type_is_enforced(self):
        raw = multistatus(dav_response("/dav/lab/", True),
                          dav_response("/dav/lab/file", properties={"resourcetype": "", "getcontentlength": "16"},
                                       unavailable=("getetag", "getlastmodified")))
        result = self.client.directory_entries(self.listing(raw))
        self.assertIsNone(result["entries"][1]["etag"])
        self.assertEqual(result["entries"][1]["unavailableProperties"], ["getetag", "getlastmodified"])
        bad = multistatus(dav_response("/dav/lab/", properties={"getetag": "x"}))
        with self.assertRaisesRegex(SourceError, "DAV_RESOURCE_TYPE_REQUIRED"):
            self.client.directory_entries(self.listing(bad))

    def test_optional_identity_and_sync_properties_are_observed_without_accepting_semantics(self):
        props = {"resourcetype": "<d:collection/>",
                 "resource-id": "<d:href>urn:uuid:unit-resource</d:href>",
                 "sync-token": "urn:unit:sync-1"}
        parsed = self.client.directory_entries(self.listing(multistatus(
            dav_response("/dav/lab/", properties=props))))
        self.assertTrue(parsed["resourceIdPropertyExposed"])
        self.assertTrue(parsed["syncTokenPropertyExposed"])
        self.assertEqual(parsed["entries"][0]["providerResourceId"], "urn:uuid:unit-resource")
        self.assertIsNone(parsed["entries"][0]["stableObjectId"])
        self.assertFalse(parsed["stableObjectIdentityValidated"])
        self.assertFalse(parsed["changeJournalProbed"])

    def test_malformed_xml_entities_and_wrong_top_level_are_rejected(self):
        for raw in (b"<bad", b"<notdav/>",
                    b'<!DOCTYPE d [<!ENTITY e "entity">]><d:multistatus xmlns:d="DAV:"/>',
                    '<?xml version="1.0"?><d:multistatus xmlns:d="DAV:"/>'.encode("utf-16")):
            with self.assertRaises(SourceError):
                self.client.directory_entries(self.listing(raw))

    def test_raw_href_controls_are_rejected_before_urlsplit_can_rewrite_identity(self):
        for control in ("\t", "\n", "\r", "\x7f"):
            href = "/dav/lab/a" + control + "b"
            with self.assertRaises(SourceError):
                self.client._href(href)
            body = multistatus(dav_response("/dav/lab/", True), dav_response(href))
            with self.assertRaises(SourceError):
                self.client.directory_entries(self.listing(body))
        with self.assertRaises(SourceError):
            self.client._href(" /dav/lab/file")

    def test_duplicate_outside_nested_and_encoded_traversal_entries_are_rejected(self):
        self_entry = dav_response("/dav/lab/", True)
        for href in ("/dav/elsewhere/file", "/dav/lab/a/b", "/dav/lab/%2e%2e/escape",
                     "/dav/lab/a%2fb", "//example.com/dav/lab/file", "/dav/lab/file?token=x",
                     "/dav/lab/bad%zz", "/dav/lab/"):
            with self.assertRaises(SourceError):
                self.client.directory_entries(self.listing(multistatus(self_entry, dav_response(href))))
        with self.assertRaisesRegex(SourceError, "DAV_SELF_COLLECTION_MISSING"):
            self.client.directory_entries(self.listing(multistatus(dav_response("/dav/lab/file"))))


if __name__ == "__main__":
    unittest.main()
