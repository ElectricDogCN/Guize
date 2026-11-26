"""Run the bounded playback gateway for one disposable loopback fixture."""

from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
import ssl
from threading import Thread
import time

from observe_fixture import ObservedRead, ObserveFixtureWrites
from stream_fixture import FixtureSource, RangeNotSatisfiable, Transfer


@dataclass(frozen=True)
class PlaybackPolicy:
    cache_interval: tuple[int, int]
    request_limit: int
    window_seconds: float

    def __post_init__(self) -> None:
        first, stop = self.cache_interval
        if first < 0 or not 0 < stop - first <= 256 * 1024:
            raise ValueError("Expected one bounded cache interval")
        if not 1 <= self.request_limit <= 32 or not 0 < self.window_seconds <= 30:
            raise ValueError("Expected a bounded local replay window")


@dataclass(frozen=True)
class PlaybackObservation:
    observed_at: datetime
    status: int
    decision: str
    range_header: str | None
    if_range: str | None
    request_id: str | None
    trace_id: str | None
    cache_hit: bool = False
    source_requested_at: datetime | None = None
    transfer: Transfer | None = None
    reads: tuple[ObservedRead, ...] = ()


@contextmanager
def playback_gateway(
    source: FixtureSource,
    origin_authorization: str,
    authorize: Callable[[str, datetime], str],
    tls_context: ssl.SSLContext,
    policy: PlaybackPolicy,
    observe: Callable[[PlaybackObservation], None],
    *,
    port: int = 0,
) -> Iterator[int]:
    """Serve only the fixture once the playback grant decision returns allowed."""
    if policy.cache_interval[1] > source.byte_count:
        raise ValueError("The cache interval must lie inside the bound fixture")
    if tls_context.minimum_version != ssl.TLSVersion.TLSv1_3:
        raise ValueError("The disposable playback listener requires TLS 1.3")
    recent: deque[float] = deque()
    cached: tuple[dict[str, str], bytes] | None = None

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send_fixture_headers(self, status: int, headers: dict[str, str]) -> None:
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Connection", "close")
            self.end_headers()

        def do_GET(self) -> None:
            nonlocal cached
            observed_at = datetime.now(timezone.utc)
            requested = self.headers.get("Range")
            if_range = self.headers.get("If-Range")
            request_id = self.headers.get("X-Guize-Request-Id")
            trace_id = self.headers.get("X-Guize-Trace-Id")

            def record(status: int, decision: str, **outcome) -> None:
                observe(PlaybackObservation(observed_at, status, decision, requested, if_range,
                                            request_id, trace_id, **outcome))

            def reject(status: int, reason: str, **headers: str) -> None:
                record(status, reason)
                self.send_fixture_headers(status, {"Content-Length": "0", **headers})

            if self.path != "/synthetic.bin":
                reject(404, "unknown_route")
                return
            decision = authorize(self.headers.get("Authorization", ""), observed_at)
            if decision != "allowed":
                reject(403, decision)
                return
            now = time.monotonic()
            while recent and now - recent[0] >= policy.window_seconds:
                recent.popleft()
            if len(recent) >= policy.request_limit:
                reject(429, "rate_limited")
                return
            recent.append(now)

            try:
                interval = source.interval(requested, if_range)
            except RangeNotSatisfiable:
                reject(416, "unsatisfiable_range", **{"Content-Range": f"bytes */{source.byte_count}"})
                return
            except ValueError:
                reject(400, "invalid_range")
                return
            use_cache = interval == policy.cache_interval
            if use_cache and cached is not None:
                headers, body = cached
                self.send_fixture_headers(206, headers)
                if self.wfile.write(body) != len(body):
                    raise OSError("Playback client did not consume the cached response")
                record(206, "allowed", cache_hit=True)
                return

            capture = BytesIO() if use_cache else None
            cache_headers: dict[str, str] = {}
            source_requested_at = None

            def request_sent(sent_at: datetime) -> None:
                nonlocal source_requested_at
                source_requested_at = sent_at

            def send_headers(status: int, headers: dict[str, str]) -> None:
                if capture is not None:
                    cache_headers.update(headers)
                self.send_fixture_headers(status, headers)

            def write(block: memoryview) -> int:
                count = self.wfile.write(block)
                if capture is not None and count == len(block):
                    capture.write(block)
                return count

            observer = ObserveFixtureWrites(write, interval[0] if interval else 0)
            transfer = source.stream(
                origin_authorization, send_headers, observer, range_header=requested, if_range=if_range,
                request_sent=request_sent,
            )
            if capture is not None:
                cached = cache_headers, capture.getvalue()
            record(206 if interval else 200, "allowed", source_requested_at=source_requested_at,
                   transfer=transfer, reads=observer.finish())

    class FixtureServer(HTTPServer):
        def get_request(self):
            client, address = super().get_request()
            client.settimeout(5)
            try:
                return tls_context.wrap_socket(client, server_side=True), address
            except OSError:
                client.close()
                raise

    with FixtureServer(("127.0.0.1", port), Handler) as server:
        worker = Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            yield server.server_port
        finally:
            server.shutdown()
            worker.join()
