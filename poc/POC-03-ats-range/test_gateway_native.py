"""Real loopback HTTP regressions with in-memory subjects; no ATS or source media."""
import http.server
import os
import socket
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from grants import Grant
from lab import Gateway, Server


class GatewayNativeTests(unittest.TestCase):
    def state(self):
        cfg = dict(users={'lab-user-a': 'offline-test-credential'}, aclVersion='offline-acl',
                   inputs={'base': dict(sizeBytes=67108864, etag='"offline-etag"')})
        return SimpleNamespace(cfg=cfg, version='base', lock=threading.RLock(), gateway_active=0, gateway_active_peak=0,
            gateway_rows={}, grants={'lab-user-a': Grant('offline-grant', 'lab-user-a',
                '2000-01-01T00:00:00Z', '2100-01-01T00:00:00Z')}, log=lambda *args: None)

    def request(self, state, credential):
        with Server(('127.0.0.1', 0), Gateway, state) as server:
            worker = threading.Thread(target=server.handle_request)
            worker.start()
            try:
                with socket.create_connection(server.server_address, timeout=3) as client:
                    client.sendall(('GET /media/object.bin HTTP/1.1\r\nHost: local\r\n'
                        'Connection: close\r\nAuthorization: Bearer ' + credential
                        + '\r\nX-Lab-Request-ID: ' + 'a' * 32
                        + '\r\nX-Lab-Case: unsatisfiable\r\nRange: bytes=67108864-67108871\r\n\r\n').encode())
                    response = bytearray()
                    while block := client.recv(4096):
                        response.extend(block)
            finally:
                worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
        header, body = bytes(response).split(b'\r\n\r\n', 1)
        return header, body

    def test_unsatisfiable_interval_has_empty_correct_response_without_contacting_ats(self):
        state = self.state()
        with patch('lab.http.client.HTTPConnection', side_effect=AssertionError('ATS must not be contacted')):
            header, body = self.request(state, 'offline-test-credential')
        self.assertIn(b' 416 ', header.split(b'\r\n', 1)[0])
        self.assertIn(b'Content-Range: bytes */67108864', header)
        self.assertIn(b'ETag: "offline-etag"', header)
        self.assertIn(b'Content-Length: 0', header)
        self.assertEqual(body, b'')
        self.assertFalse(state.gateway_rows['a' * 32][0]['atsRequestSent'])

    def test_denied_user_cannot_obtain_unsatisfiable_representation_metadata(self):
        state = self.state()
        with patch('lab.http.client.HTTPConnection', side_effect=AssertionError('ATS must not be contacted')):
            header, body = self.request(state, 'invalid-test-credential')
        self.assertIn(b' 403 ', header.split(b'\r\n', 1)[0])
        self.assertNotIn(b'Content-Range:', header)
        self.assertNotIn(b'ETag:', header)
        self.assertEqual(body, b'')
        self.assertFalse(state.gateway_rows['a' * 32][0]['atsRequestSent'])

    def test_owned_port_can_rebind_after_close_but_refuses_live_listener(self):
        class Empty(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(204)
                self.send_header('Content-Length', '0')
                self.send_header('Connection', 'close')
                self.end_headers()
            def log_message(self, *args):
                pass
        with Server(('127.0.0.1', 0), Empty, None) as first:
            address = first.server_address
            with self.assertRaises(OSError):
                Server(address, Empty, None)
            worker = threading.Thread(target=first.handle_request)
            worker.start()
            with socket.create_connection(address, timeout=3) as client:
                client.sendall(b'GET / HTTP/1.0\r\n\r\n')
                while client.recv(4096):
                    pass
            worker.join(timeout=3)
            self.assertFalse(worker.is_alive())
        with Server(address, Empty, None) as second:
            self.assertEqual(second.server_address, address)


if __name__ == '__main__':
    if os.name != 'posix':
        raise SystemExit('Actual Linux loopback sockets required; no skipped substitute')
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(GatewayNativeTests))
    if result.testsRun != 3 or result.skipped:
        raise SystemExit('Expected three actual native tests and no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)
