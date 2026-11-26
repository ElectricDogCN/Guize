"""Summarize successful origin reads without retaining payload bytes."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256

READ_SPAN_BYTES = 1024 * 1024


@dataclass(frozen=True)
class ObservedRead:
    offset: int
    byte_count: int
    sha256: str
    observed_at: datetime


class ObserveFixtureWrites:
    """Wrap the sink of a single origin response and record contiguous observed bytes."""

    def __init__(self, write: Callable[[memoryview], int], offset: int) -> None:
        self._write = write
        self._offset = offset
        self._count = 0
        self._digest = sha256()
        self._reads: list[ObservedRead] = []

    def __call__(self, block: memoryview) -> int:
        count = self._write(block)
        if count != len(block):
            return count
        remaining = block
        while remaining:
            part_size = min(len(remaining), READ_SPAN_BYTES - self._count)
            self._digest.update(remaining[:part_size])
            self._count += part_size
            remaining = remaining[part_size:]
            if self._count == READ_SPAN_BYTES:
                self._record_span()
        return count

    def finish(self) -> tuple[ObservedRead, ...]:
        """Call after the stream completes successfully to record the final partial span."""
        if self._count:
            self._record_span()
        return tuple(self._reads)

    def _record_span(self) -> None:
        self._reads.append(ObservedRead(
            self._offset, self._count, "sha256:" + self._digest.hexdigest(), datetime.now(timezone.utc)
        ))
        self._offset += self._count
        self._count = 0
        self._digest = sha256()
