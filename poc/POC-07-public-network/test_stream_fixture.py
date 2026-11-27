import hashlib
from argparse import Namespace
from datetime import timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
import json
from pathlib import PureWindowsPath
import subprocess
import threading
import unittest
from unittest.mock import patch

from native_access_capture import CaptureError, capture_tls_request, observe_access_request
from observe_fixture import ObserveFixtureWrites, READ_SPAN_BYTES
from stream_fixture import CHUNK_BYTES, FixtureSource, RangeNotSatisfiable, UnexpectedOriginResponse


class NativeEvidencePathTests(unittest.TestCase):
    def test_windows_request_uses_portable_evidence_paths(self):
        response = PureWindowsPath("evidence/POC-007/capture/playback/response.http")
        trust_store = PureWindowsPath("evidence/POC-007/capture/localhost-trust.pem")

        with patch(
            "native_access_capture.subprocess.run",
            side_effect=subprocess.TimeoutExpired("local request", 25),
        ) as run:
            with self.assertRaises(CaptureError):
                observe_access_request(
                    "https://localhost:48743/synthetic.bin",
                    response,
                    trust_store=trust_store,
                    request_id="fixture-request",
                    trace_id="fixture-trace",
                )

        self.assertEqual(run.call_args.args[0][-1], response.as_posix())
        settings = json.loads(run.call_args.kwargs["input"])
        self.assertEqual(settings["trust_store"], trust_store.as_posix())

    def test_windows_tls_command_records_portable_output(self):
        response = PureWindowsPath("evidence/POC-007/capture/playback/response.http")
        trust_store = "evidence/POC-007/capture/localhost-trust.pem"
        args = Namespace(target="https://localhost:48743/synthetic.bin", response=response,
                         trace_id="fixture-trace", request_id="fixture-request")

        with patch("native_access_capture.subprocess.Popen", side_effect=OSError("local process stub")) as launch:
            with self.assertRaises(OSError):
                capture_tls_request(args, {"trust_store": trust_store, "maximum_body_bytes": 64, "request": {}})

        command = launch.call_args.args[0]
        self.assertEqual(command[command.index("--tls-ca-file") + 1], trust_store)
        self.assertEqual(command[-1], response.with_suffix(".tls.json").as_posix())


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


class FixtureReadObservationTests(unittest.TestCase):
    def test_64_mib_has_64_ordered_spans_with_exact_digests(self):
        offset = 1025
        observer = ObserveFixtureWrites(len, offset)
        expected = []
        for index in range(64):
            chunk = bytes([index]) * CHUNK_BYTES
            for _ in range(READ_SPAN_BYTES // CHUNK_BYTES):
                self.assertEqual(observer(memoryview(chunk)), CHUNK_BYTES)
            digest = hashlib.sha256(chunk * (READ_SPAN_BYTES // CHUNK_BYTES)).hexdigest()
            expected.append((offset + index * READ_SPAN_BYTES, READ_SPAN_BYTES, "sha256:" + digest))
        observed = observer.finish()
        self.assertEqual([(row.offset, row.byte_count, row.sha256) for row in observed], expected)
        self.assertTrue(all(row.observed_at.tzinfo == timezone.utc for row in observed))

    def test_boundary_split_and_final_partial_span_bind_sink_bytes(self):
        sink = BytesIO()
        observer = ObserveFixtureWrites(sink.write, 17)
        chunk = memoryview(bytes(range(256)) * 211)
        for _ in range(20):
            observer(chunk)
        raw = sink.getvalue()
        observed = observer.finish()
        self.assertEqual(len(observed), 2)
        for index, expected_bytes in enumerate((raw[:READ_SPAN_BYTES], raw[READ_SPAN_BYTES:])):
            row = observed[index]
            self.assertEqual(row.offset, 17 + index * READ_SPAN_BYTES)
            self.assertEqual(row.byte_count, len(expected_bytes))
            self.assertEqual(row.sha256, "sha256:" + hashlib.sha256(expected_bytes).hexdigest())


if __name__ == "__main__":
    unittest.main()
