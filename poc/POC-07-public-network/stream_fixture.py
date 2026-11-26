"""Stream one bound OpenList fixture after the local playback entry grants access."""

from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from http.client import HTTPConnection, HTTPResponse
import re

CHUNK_BYTES = 64 * 1024


class RangeNotSatisfiable(ValueError):
    """The requested interval lies outside the selected fixture."""


class UnexpectedOriginResponse(OSError):
    """The source did not return the selected version's expected representation."""


@dataclass(frozen=True)
class Transfer:
    byte_count: int
    sha256: str
    peak_read_bytes: int


@dataclass(frozen=True)
class FixtureSource:
    port: int
    filename: str
    byte_count: int
    sha256_hex: str

    def __post_init__(self) -> None:
        if not 1 <= self.port <= 65535 or self.byte_count < 1:
            raise ValueError("Expected a loopback port and a nonempty fixture")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", self.filename):
            raise ValueError("Expected one fixture filename")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256_hex):
            raise ValueError("Expected the fixture SHA-256")

    @property
    def etag(self) -> str:
        return '"' + self.sha256_hex + '"'

    def interval(self, range_header: str | None, if_range: str | None) -> tuple[int, int] | None:
        """Return the [start, end) interval, or None for a full response."""
        if range_header is None or (if_range is not None and if_range != self.etag):
            return None
        match = re.fullmatch(r"bytes=([0-9]{0,18})-([0-9]{0,18})", range_header)
        if match is None:
            raise ValueError("Expected one byte range")
        first, last = match.groups()
        if not first:
            if not last or int(last) == 0:
                raise RangeNotSatisfiable("Expected a nonempty suffix")
            return max(0, self.byte_count - int(last)), self.byte_count
        start = int(first)
        end = min(self.byte_count, int(last) + 1) if last else self.byte_count
        if start >= end:
            raise RangeNotSatisfiable("The fixture does not contain this interval")
        return start, end

    def stream(
        self,
        authorization: str,
        send_headers: Callable[[int, dict[str, str]], None],
        write: Callable[[memoryview], int],
        *,
        range_header: str | None = None,
        if_range: str | None = None,
    ) -> Transfer:
        """Call the response callbacks synchronously; do not retain the temporary write buffer."""
        interval = self.interval(range_header, if_range)
        start, end = interval or (0, self.byte_count)
        expected_count = end - start
        status = 206 if interval else 200
        request_headers = {"Authorization": authorization, "Accept-Encoding": "identity"}
        response_headers = {"Content-Length": str(expected_count), "ETag": self.etag, "Accept-Ranges": "bytes"}
        if interval:
            request_headers["Range"] = f"bytes={start}-{end - 1}"
            response_headers["Content-Range"] = f"bytes {start}-{end - 1}/{self.byte_count}"

        connection = HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request("GET", "/dav/" + self.filename, headers=request_headers)
            with connection.getresponse() as response:
                if (
                    response.status != status
                    or response.headers.get_all("Content-Length") != [str(expected_count)]
                    or response.headers.get_all("Content-Range") != (
                        [response_headers["Content-Range"]] if interval else None
                    )
                    or response.getheader("Content-Encoding", "identity").lower() != "identity"
                    or response.getheader("Transfer-Encoding") is not None
                ):
                    raise UnexpectedOriginResponse("OpenList status or representation headers did not match")
                send_headers(status, response_headers)
                return _copy_body(response, write, expected_count)
        finally:
            connection.close()


def _copy_body(
    response: HTTPResponse, write: Callable[[memoryview], int], expected_count: int
) -> Transfer:
    buffer = memoryview(bytearray(min(CHUNK_BYTES, expected_count)))
    received = peak_read = 0
    digest = sha256()
    while received < expected_count:
        count = response.readinto(buffer[: expected_count - received])
        if not count:
            raise UnexpectedOriginResponse("OpenList closed before the complete fixture interval")
        block = buffer[:count]
        if write(block) != count:
            raise OSError("The playback sink did not consume the full buffer")
        digest.update(block)
        received += count
        peak_read = max(peak_read, count)
    return Transfer(received, "sha256:" + digest.hexdigest(), peak_read)
