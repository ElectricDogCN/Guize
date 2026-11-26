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


@contextmanager
def resource_gateway(
    management: ProtectedResource,
    worker_output: ProtectedResource,
    *,
    port: int = 0,
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
            presented = self.headers.get("Authorization", "")
            if resource.authorize(presented, datetime.now(timezone.utc)) is not True:
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
