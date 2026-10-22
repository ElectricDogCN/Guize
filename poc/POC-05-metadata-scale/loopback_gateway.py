"""Owned, read-only controlled adapter; injected faults never claim upstream origin."""
from __future__ import annotations

import base64
import hashlib
import hmac
import http.client
import math
import secrets
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import deque
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from metadata_scan import ScanError, canonical
from native_scan_protocol import utc
from openlist_source import MAX_BODY_BYTES, RESPONSE_HEADERS, _NoRedirect, _segments


class ControlledGateway:
    def __init__(self, origin, scope, *, upstream_token, upstream_basic, window, request_limit, period_seconds,
                 port=0, timeout=5, event_limit=20000):
        parsed = urllib.parse.urlsplit(origin)
        if (parsed.scheme != 'http' or parsed.hostname != '127.0.0.1' or not parsed.port
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment or parsed.username or parsed.password):
            raise ScanError('FIXED_LOOPBACK_UPSTREAM_REQUIRED')
        self.scope = '/'.join(_segments(scope))
        if not self.scope or self.scope.startswith('@s'):
            raise ScanError('EXPLICIT_GATEWAY_SCOPE_REQUIRED')
        if (type(request_limit) is not int or not 1 <= request_limit <= 100000
                or type(period_seconds) not in (int, float) or not math.isfinite(period_seconds) or not 0 < period_seconds <= 3600
                or type(timeout) not in (int, float) or not 0 < timeout <= 10
                or type(event_limit) is not int or not 1 <= event_limit <= 20000):
            raise ScanError('FINITE_GATEWAY_LIMITS_REQUIRED')
        self.start, self.end = map(utc, window)
        if not 0 < (self.end-self.start).total_seconds() <= 86400:
            raise ScanError('FINITE_GATEWAY_WINDOW_REQUIRED')
        self.expired_at = self.start-timedelta(seconds=1)
        if (not isinstance(upstream_token, str) or not upstream_token or len(upstream_token) > 8192
                or any(ord(c) < 33 or ord(c) > 126 for c in upstream_token)
                or not isinstance(upstream_basic, str) or not upstream_basic.startswith('Basic ')
                or not upstream_basic[6:] or len(upstream_basic) > 8192
                or any(ord(c) < 33 or ord(c) > 126 for c in upstream_basic[6:])):
            raise ScanError('PRIVATE_UPSTREAM_AUTH_REQUIRED')
        self.origin, self.timeout = origin.rstrip('/'), timeout
        self.upstream_token, self.upstream_basic = upstream_token, upstream_basic
        self.token, self.expired_token, self.password = (secrets.token_urlsafe(32) for _ in range(3))
        self.username = 'controlled-gateway-reader'
        self.basic = 'Basic '+base64.b64encode((self.username+':'+self.password).encode()).decode()
        self.request_limit, self.period_seconds = request_limit, period_seconds
        self.events, self.event_limit, self.faults = [], event_limit, deque()
        self.lock = threading.Lock()
        self.opened_tick, self.bucket, self.used = time.monotonic(), 0, 0
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        gateway = self
        class Handler(BaseHTTPRequestHandler):
            protocol_version = 'HTTP/1.1'
            def log_message(self, *_):
                pass
            def do_GET(self): gateway.handle(self)
            def do_HEAD(self): gateway.handle(self)
            def do_POST(self): gateway.handle(self)
            def do_PROPFIND(self): gateway.handle(self)
            def do_PUT(self): gateway.handle(self)
            def do_DELETE(self): gateway.handle(self)
        self.server = HTTPServer(('127.0.0.1', port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.endpoint = 'http://127.0.0.1:'+str(self.server.server_port)

    def start_server(self):
        self.thread.start()
        return self

    def close(self):
        if self.thread.is_alive():
            self.server.shutdown()
            self.thread.join(timeout=10)
        self.server.server_close()

    def inject(self, fault):
        if fault not in ('http_429', 'http_5xx', 'network_disconnect'):
            raise ScanError('EXPLICIT_CONTROLLED_FAULT_REQUIRED')
        with self.lock:
            if self.faults:
                raise ScanError('PENDING_CONTROLLED_FAULT_EXISTS')
            self.faults.append(fault)

    def handle(self, request):
        request.connection.settimeout(self.timeout)
        event = dict(startedAt=datetime.now(timezone.utc).isoformat(), monotonicStartNs=time.monotonic_ns(),
                     method=request.command, status=None, upstreamContacted=False, injectedFault=None,
                     authorization='denied', responseBytes=0, responseSha256=None)
        def respond(status, body, headers=()):
            event.update(status=status, responseBytes=len(body), responseSha256=hashlib.sha256(body).hexdigest())
            request.send_response_only(status)
            for name, value in headers:
                if name.lower() != 'connection':
                    request.send_header(name, value)
            if not any(name.lower() == 'content-length' for name, _ in headers):
                request.send_header('Content-Length', str(len(body)))
            request.send_header('Connection', 'close')
            request.end_headers()
            if request.command != 'HEAD':
                request.wfile.write(body)
            request.close_connection = True
        try:
            now = datetime.now(timezone.utc)
            if not self.start <= now <= self.end:
                respond(403, b'{"error":"outside_approved_window"}')
                return
            parsed = urllib.parse.urlsplit(request.path)
            if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
                respond(403, b'{"error":"route_denied"}')
                return
            listing = request.command == 'POST' and parsed.path == '/api/fs/list'
            try:
                decoded = urllib.parse.unquote(parsed.path, encoding='utf8', errors='strict')
                pieces = _segments(decoded.lstrip('/'))
                dav = (request.command in ('GET', 'HEAD', 'PROPFIND') and pieces[:1] == ['dav']
                       and not decoded.startswith('//')
                       and pieces[1:1+len(self.scope.split('/'))] == self.scope.split('/'))
                # Encoded slashes/backslashes or noncanonical quoting never change routing.
                if '%2f' in parsed.path.lower() or '%5c' in parsed.path.lower():
                    dav = False
            except (ValueError, UnicodeError):
                dav = False
            if not listing and not dav:
                respond(403, b'{"error":"route_denied"}')
                return
            auths = request.headers.get_all('Authorization', [])
            expected = self.token if listing else self.basic
            if len(auths) != 1 or not hmac.compare_digest(auths[0], expected):
                if len(auths) == 1 and listing and hmac.compare_digest(auths[0], self.expired_token):
                    event.update(authorization='expired', injectedFault='auth_expired', authorizationExpiredAt=self.expired_at.isoformat())
                respond(401, b'{"code":401,"message":"adapter authorization expired or invalid"}')
                return
            event['authorization'] = 'valid'
            if request.headers.get('Transfer-Encoding') is not None:
                respond(400, b'{"error":"bounded_content_length_required"}')
                return
            lengths = request.headers.get_all('Content-Length', [])
            if len(lengths) > 1 or lengths and (not lengths[0].isdigit() or int(lengths[0]) > 4096):
                respond(400, b'{"error":"request_limit"}')
                return
            body = request.rfile.read(int(lengths[0])) if lengths else b''
            if listing:
                from openlist_listing import _decode
                document = _decode(body)
                prefix = '/'+self.scope
                locator = document.get('path') if isinstance(document, dict) else None
                if (not isinstance(locator, str) or not (locator == prefix or locator.startswith(prefix+'/'))
                        or '/'.join(_segments(locator.lstrip('/'))) != locator.lstrip('/')
                        or document.get('refresh') is not False or document.get('password') != ''):
                    respond(403, b'{"error":"listing_scope_denied"}')
                    return
            with self.lock:
                if len(self.events) >= self.event_limit:
                    respond(429, b'{"code":429,"message":"adapter event budget"}')
                    return
                elapsed = time.monotonic()-self.opened_tick
                bucket = int(elapsed//self.period_seconds)
                if bucket != self.bucket:
                    self.bucket, self.used = bucket, 0
                if self.used >= self.request_limit:
                    respond(429, b'{"code":429,"message":"adapter quota"}', [('Retry-After', str(math.ceil(self.period_seconds-elapsed%self.period_seconds)))])
                    return
                self.used += 1
                fault = self.faults.popleft() if self.faults else None
            if fault:
                event['injectedFault'] = fault
                if fault == 'network_disconnect':
                    request.close_connection = True
                    request.connection.shutdown(socket.SHUT_RDWR)
                    request.connection.close()
                    return
                status = 429 if fault == 'http_429' else 503
                respond(status, canonical(dict(code=status, message='controlled adapter fault')).encode(),
                        [('Content-Type', 'application/json'), ('Retry-After', '0')])
                return
            headers = {name: value for name, value in request.headers.items() if name.lower() in
                       {'content-type', 'accept', 'accept-encoding', 'user-agent', 'range', 'if-range', 'if-match', 'if-none-match', 'depth'}}
            headers['Authorization'] = self.upstream_token if listing else self.upstream_basic
            headers['Accept-Encoding'] = 'identity'
            event['upstreamContacted'] = True
            event['upstreamPath'] = parsed.path  # Approved routes contain no query or credentials.
            remaining = (self.end-datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0:
                event['upstreamContacted'] = False
                respond(403, b'{"error":"outside_approved_window"}')
                return
            try:
                upstream = self.opener.open(urllib.request.Request(self.origin+parsed.path,
                    data=body if listing or request.command == 'PROPFIND' else None,
                    method=request.command, headers=headers), timeout=min(self.timeout, remaining))
            except urllib.error.HTTPError as error:
                upstream = error
            with upstream:
                raw = upstream.read(MAX_BODY_BYTES+1)
                if len(raw) > MAX_BODY_BYTES:
                    raise ScanError('UPSTREAM_RESPONSE_LIMIT')
                retained_headers = [(name, value) for name in (*RESPONSE_HEADERS, 'Date')
                                    for value in upstream.headers.get_all(name, [])]
                # Forward duplicate headers unchanged; the observing client must reject ambiguity.
                respond(upstream.status, raw, retained_headers)
        except (OSError, ValueError, TypeError, urllib.error.URLError, http.client.HTTPException) as failure:
            event['error'] = str(failure) if isinstance(failure, ScanError) else type(failure).__name__
            request.close_connection = True
        finally:
            event.update(finishedAt=datetime.now(timezone.utc).isoformat(), monotonicEndNs=time.monotonic_ns())
            with self.lock:
                if len(self.events) < self.event_limit:
                    self.events.append(event)
