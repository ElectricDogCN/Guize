"""Retain a native response from the disposable loopback TLS playback entry."""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from http.client import HTTPConnection, HTTPSConnection
from pathlib import Path
import ssl

CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class Capture:
    peer_address: str
    peer_port: int
    protocol: str | None
    cipher: str | None
    started_at: datetime
    connected_at: datetime
    finished_at: datetime
    raw_byte_count: int
    raw_sha256: str
    certificate_sha256: str | None = None


def capture_response(
    port: int,
    trust_store: Path,
    response_file: Path,
    maximum_body_bytes: int,
    *,
    authorization: str | None = None,
    range_header: str | None = None,
    if_range: str | None = None,
    request_id: str | None = None,
    trace_id: str | None = None,
) -> Capture:
    """Write the actual decoded TLS stream before application HTTP parsing."""
    context = ssl.create_default_context(cafile=str(trust_store))
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    connection = HTTPSConnection("localhost", port, timeout=10, context=context)
    headers = {}
    for name, value in (
        ("Authorization", authorization), ("Range", range_header), ("If-Range", if_range),
        ("X-Guize-Request-Id", request_id), ("X-Guize-Trace-Id", trace_id),
    ):
        if value is not None:
            headers[name] = value
    return _capture(connection, "/synthetic.bin", response_file, maximum_body_bytes, headers)


def capture_anonymous_origin_response(
    port: int, response_file: Path, range_header: str, *, request_id: str | None = None, trace_id: str | None = None
) -> Capture:
    """Record the ordinary anonymous response from the disposable WebDAV fixture."""
    connection = HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Range": range_header}
    if request_id is not None:
        headers["X-Guize-Request-Id"] = request_id
    if trace_id is not None:
        headers["X-Guize-Trace-Id"] = trace_id
    return _capture(connection, "/dav/synthetic.bin", response_file, 1024, headers)


def _capture(
    connection: HTTPConnection,
    path: str,
    response_file: Path,
    maximum_body_bytes: int,
    headers: dict[str, str],
) -> Capture:
    if not 1 <= connection.port <= 65535 or maximum_body_bytes < 0:
        raise ValueError("Expected a loopback port and a nonnegative body limit")
    started = datetime.now(timezone.utc)
    try:
        connection.connect()
        connected = datetime.now(timezone.utc)
        peer_socket = connection.sock
        if peer_socket is None:
            raise OSError("The playback connection did not open")
        address, observed_port = peer_socket.getpeername()[:2]
        if address != "127.0.0.1" or observed_port != connection.port:
            raise ValueError("The peer did not match the disposable listener")
        protocol = cipher_name = certificate_sha256 = None
        if isinstance(connection, HTTPSConnection):
            if not isinstance(peer_socket, ssl.SSLSocket):
                raise OSError("The playback connection did not establish TLS")
            protocol = peer_socket.version()
            cipher = peer_socket.cipher()
            if not protocol or cipher is None:
                raise OSError("The playback connection has no negotiated TLS session")
            cipher_name = cipher[0]
            certificate = peer_socket.getpeercert(binary_form=True)
            if certificate is None:
                raise OSError("The verified playback connection did not return a certificate")
            certificate_sha256 = "sha256:" + sha256(certificate).hexdigest()
        connection.request("GET", path, headers={"Connection": "close", "Accept-Encoding": "identity", **headers})
        buffer = memoryview(bytearray(CHUNK_BYTES))
        digest = sha256()
        received = 0
        with response_file.open("xb") as stream:
            while count := peer_socket.recv_into(buffer):
                received += count
                if received > maximum_body_bytes + CHUNK_BYTES:
                    raise ValueError("Native response exceeded its capture limit")
                block = buffer[:count]
                stream.write(block)
                digest.update(block)
        if not received:
            raise OSError("The playback listener returned no HTTP response")
        finished = datetime.now(timezone.utc)
        return Capture(address, observed_port, protocol, cipher_name, started, connected, finished,
                       received, "sha256:" + digest.hexdigest(), certificate_sha256)
    finally:
        connection.close()
