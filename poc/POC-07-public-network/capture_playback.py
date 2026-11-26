"""Retain a native response from the disposable loopback TLS playback entry."""

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from http.client import HTTPSConnection
from pathlib import Path
import ssl

CHUNK_BYTES = 64 * 1024


@dataclass(frozen=True)
class Capture:
    peer_address: str
    peer_port: int
    protocol: str
    cipher: str
    started_at: datetime
    connected_at: datetime
    finished_at: datetime
    raw_byte_count: int
    raw_sha256: str


def capture_response(
    port: int,
    trust_store: Path,
    response_file: Path,
    maximum_body_bytes: int,
    *,
    authorization: str | None = None,
    range_header: str | None = None,
    if_range: str | None = None,
) -> Capture:
    """Write the actual decoded TLS stream before application HTTP parsing."""
    if not 1 <= port <= 65535 or maximum_body_bytes < 0:
        raise ValueError("Expected a loopback port and a nonnegative body limit")
    context = ssl.create_default_context(cafile=str(trust_store))
    context.minimum_version = ssl.TLSVersion.TLSv1_3
    connection = HTTPSConnection("localhost", port, timeout=10, context=context)
    headers = {"Connection": "close", "Accept-Encoding": "identity"}
    for name, value in (("Authorization", authorization), ("Range", range_header), ("If-Range", if_range)):
        if value is not None:
            headers[name] = value
    started = datetime.now(timezone.utc)
    try:
        connection.connect()
        connected = datetime.now(timezone.utc)
        tls_socket = connection.sock
        if tls_socket is None:
            raise OSError("The playback connection did not open")
        address, observed_port = tls_socket.getpeername()[:2]
        if address != "127.0.0.1" or observed_port != port:
            raise ValueError("The TLS peer did not match the disposable listener")
        protocol = tls_socket.version()
        cipher = tls_socket.cipher()
        if not protocol or cipher is None:
            raise OSError("The playback connection has no negotiated TLS session")
        connection.request("GET", "/synthetic.bin", headers=headers)
        buffer = memoryview(bytearray(CHUNK_BYTES))
        digest = sha256()
        received = 0
        with response_file.open("xb") as stream:
            while count := tls_socket.recv_into(buffer):
                received += count
                if received > maximum_body_bytes + CHUNK_BYTES:
                    raise ValueError("Native response exceeded its capture limit")
                block = buffer[:count]
                stream.write(block)
                digest.update(block)
        if not received:
            raise OSError("The playback listener returned no HTTP response")
        finished = datetime.now(timezone.utc)
        return Capture(address, observed_port, protocol, cipher[0], started, connected, finished,
                       received, "sha256:" + digest.hexdigest())
    finally:
        connection.close()
