import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
import threading
import unittest

from stream_fixture import CHUNK_BYTES, FixtureSource, RangeNotSatisfiable, UnexpectedOriginResponse


class FixtureStreamTests(unittest.TestCase):
    def setUp(self):
        self.content = bytes(range(256)) * 700
        self.invalid_interval = False
        self.truncate = False
        case = self

        class Origin(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/dav/synthetic.bin":
                    self.send_error(404)
                    return
                selected = self.headers.get("Range")
                payload = case.content
                if selected:
                    first, last = map(int, selected.removeprefix("bytes=").split("-"))
                    payload = payload[first : last + 1]
                self.send_response(206 if selected else 200)
                self.send_header("Content-Length", str(len(payload)))
                if selected:
                    interval = f"bytes {first}-{last}/{len(case.content)}"
                    self.send_header("Content-Range", "bytes 0-1/2" if case.invalid_interval else interval)
                self.end_headers()
                self.wfile.write(payload[:-1] if case.truncate else payload)

            def log_message(self, *_):
                pass

        server = HTTPServer(("127.0.0.1", 0), Origin)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(server.server_close)
        self.addCleanup(worker.join, 5)
        self.addCleanup(server.shutdown)
        self.fixture = FixtureSource(
            server.server_port, "synthetic.bin", len(self.content), hashlib.sha256(self.content).hexdigest()
        )
        self.output = BytesIO()
        self.headers = []

    def stream(self, **headers):
        def receive_headers(status, values):
            self.headers.append((status, values))

        return self.fixture.stream("Basic fixture-only", receive_headers, self.output.write, **headers)

    def test_full_representation_streams_with_matching_digest(self):
        result = self.stream(range_header="bytes=64-95", if_range='"stale"')
        self.assertEqual(self.headers[0][0], 200)
        self.assertEqual(self.headers[0][1]["ETag"], self.fixture.etag)
        self.assertNotIn("Content-Range", self.headers[0][1])
        self.assertEqual(self.output.getvalue(), self.content)
        self.assertEqual(result.byte_count, len(self.content))
        self.assertEqual(result.sha256, "sha256:" + self.fixture.sha256_hex)
        self.assertEqual(result.peak_read_bytes, CHUNK_BYTES)

    def test_matching_if_range_streams_requested_slice(self):
        result = self.stream(range_header="bytes=64-95", if_range=self.fixture.etag)
        self.assertEqual(self.headers[0][0], 206)
        self.assertEqual(self.headers[0][1]["Content-Range"], f"bytes 64-95/{len(self.content)}")
        self.assertEqual(self.output.getvalue(), self.content[64:96])
        self.assertEqual(result.byte_count, 32)
        self.assertEqual(result.peak_read_bytes, 32)

    def test_open_and_suffix_ranges_and_unsatisfiable_range(self):
        self.assertEqual(self.fixture.interval("bytes=64-", None), (64, len(self.content)))
        self.assertEqual(self.fixture.interval("bytes=-8", None), (len(self.content) - 8, len(self.content)))
        with self.assertRaises(RangeNotSatisfiable):
            self.fixture.interval(f"bytes={len(self.content)}-", None)

    def test_origin_interval_must_match_before_any_headers_or_payload(self):
        self.invalid_interval = True
        with self.assertRaises(UnexpectedOriginResponse):
            self.stream(range_header="bytes=64-95")
        self.assertEqual(self.headers, [])
        self.assertEqual(self.output.getvalue(), b"")

    def test_truncation_cannot_return_a_successful_transfer(self):
        self.truncate = True
        with self.assertRaises(UnexpectedOriginResponse):
            self.stream()


if __name__ == "__main__":
    unittest.main()
