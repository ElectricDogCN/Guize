"""Serve the local POC's two protected fixture resources on loopback."""

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread


@dataclass(frozen=True)
class ProtectedResource:
    authorize: Callable[[str, datetime], bool]
    read: Callable[[], bytes]
    content_type: str


@dataclass(frozen=True)
class ResourceDecision:
    route: str
    request_id: str
    trace_id: str
    observed_at: datetime
    allowed: bool
    range_header: str | None


@contextmanager
def resource_gateway(
    management: ProtectedResource,
    worker_output: ProtectedResource,
    *,
    port: int = 0,
    observe: Callable[[ResourceDecision], None] | None = None,
) -> Iterator[int]:
    """Validate platform authority before reading either configured OpenList resource."""
    routes = {"/management/storage": management, "/worker/output.bin": worker_output}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def send_resource(self, status: int, body: bytes = b"", content_type: str | None = None) -> None:
            self.send_response(status)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            if content_type:
                self.send_header("Content-Type", content_type)
            self.end_headers()
            if body:
                self.wfile.write(body)

        def do_GET(self) -> None:
            resource = routes.get(self.path)
            if resource is None:
                self.send_resource(404)
                return
            observed_at = datetime.now(timezone.utc)
            allowed = resource.authorize(self.headers.get("Authorization", ""), observed_at) is True
            if observe is not None:
                observe(ResourceDecision(
                    self.path, self.headers.get("X-Guize-Request-Id", ""),
                    self.headers.get("X-Guize-Trace-Id", ""), observed_at, allowed, self.headers.get("Range"),
                ))
            if not allowed:
                self.send_resource(403)
                return
            try:
                body = resource.read()
            except (OSError, ValueError):
                self.send_resource(502)
                return
            self.send_resource(200, body, resource.content_type)

    with HTTPServer(("127.0.0.1", port), Handler) as server:
        thread = Thread(target=server.serve_forever, name="poc007-resource-gateway")
        thread.start()
        try:
            yield server.server_port
        finally:
            server.shutdown()
            thread.join()
