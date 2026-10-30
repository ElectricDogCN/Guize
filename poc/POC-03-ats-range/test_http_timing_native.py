"""Actual loopback timing regressions; no ATS or POC performance acceptance."""
import os
import socket
import threading
import time
import unittest
import urllib.error
import urllib.request

from http_timing import timing_handler


class HttpTimingTests(unittest.TestCase):
    def response(self, payload, delay_after_first=0):
        listener = socket.socket()
        listener.bind(('127.0.0.1', 0))
        listener.listen(1)
        listener.settimeout(3)
        address = listener.getsockname()
        errors = []
        def serve():
            try:
                with listener, listener.accept()[0] as connection:
                    connection.settimeout(3)
                    request = b''
                    while b'\r\n\r\n' not in request:
                        block = connection.recv(4096)
                        if not block:
                            raise RuntimeError('client closed before request')
                        request += block
                    connection.sendall(payload[:1])
                    time.sleep(delay_after_first)
                    connection.sendall(payload[1:])
            except Exception as error:
                errors.append(error)
        worker = threading.Thread(target=serve)
        worker.start()
        marks = {}
        started = time.monotonic()
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), timing_handler(marks, started))
        try:
            try:
                response = opener.open('http://127.0.0.1:' + str(address[1]) + '/', timeout=3)
            except urllib.error.HTTPError as error:
                response = error
            headers_finished = time.monotonic()
            with response:
                body = response.read()
        finally:
            worker.join(timeout=3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        return marks, (headers_finished - started) * 1000, body

    def test_first_response_byte_precedes_delayed_header_completion(self):
        marks, headers_ms, body = self.response(
            b'HTTP/1.1 200 OK\r\nContent-Length: 3\r\nConnection: close\r\n\r\nabc', .15)
        self.assertEqual(body, b'abc')
        self.assertGreaterEqual(headers_ms - marks['firstResponseByteLatencyMs'], 100)
        self.assertIn('firstResponseByteAt', marks)

    def test_zero_body_denial_still_observes_real_http_response_byte(self):
        marks, headers_ms, body = self.response(
            b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n')
        self.assertEqual(body, b'')
        self.assertIn('firstResponseByteAt', marks)
        self.assertGreaterEqual(headers_ms, marks['firstResponseByteLatencyMs'])


if __name__ == '__main__':
    if os.name != 'posix':
        raise SystemExit('Actual Linux loopback sockets required; no skipped substitute')
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(HttpTimingTests))
    if result.testsRun != 2 or result.skipped:
        raise SystemExit('Expected two actual timing tests and no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)
