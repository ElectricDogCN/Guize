"""Owned ATS allocator diagnostics, not a complete media-buffer bound.

The absolute default-freelist allocated capacity includes retained baseline pools.
It excludes direct allocations, including each cache Vol's aggregation buffer.
Never use a baseline difference or RSS sample as maximumBufferedBytes.
"""
from __future__ import annotations
import hashlib, os, re, signal, stat, time
from pathlib import Path

HEADER = b'     Allocated      |        In-Use      | Type Size  |   Free List Name\n'
SEPARATOR = b'--------------------|--------------------|------------|----------------------------------\n'
FOOTER = b'-----------------------------------------------------------------------------------------\n'
ROW = re.compile(rb' +([0-9]+) \| +([0-9]+) \| +([0-9]+) \| memory/([^\r\n|]+)\n')
TOTAL = re.compile(rb' +([0-9]+) \| +([0-9]+) \| +\| TOTAL\n')
LIMIT = 1 << 20


def parse_dump(raw):
    """Require one complete absolute dump and consistent native byte totals."""
    start = raw.find(HEADER)
    if start < 0 or raw.find(HEADER, start + len(HEADER)) >= 0:
        raise ValueError('one absolute allocator header required')
    lines = raw[start:].splitlines(keepends=True)
    if len(lines) < 5 or lines[1] != SEPARATOR:
        raise ValueError('allocator table separator missing')
    rows = []
    for index, line in enumerate(lines[2:], 2):
        total = TOTAL.fullmatch(line)
        if total:
            if index + 1 >= len(lines) or lines[index + 1] != FOOTER or not rows:
                raise ValueError('allocator footer/rows missing')
            if any(HEADER.rstrip() in part or b'| TOTAL' in part for part in lines[index + 2:]):
                raise ValueError('multiple allocator tables')
            allocated, used = map(int, total.groups())
            if (allocated != sum(row['allocatedBytes'] for row in rows)
                    or used != sum(row['inUseBytes'] for row in rows)):
                raise ValueError('allocator totals mismatch')
            return dict(rows=rows, allocatedPoolBytes=allocated, inUsePoolBytes=used,
                        tableStart=start, tableEnd=start + sum(map(len, lines[:index + 2])),
                        fullMediaBufferBoundProven=False, baselineSubtracted=False)
        match = ROW.fullmatch(line)
        if not match:
            raise ValueError('incomplete or interleaved allocator row')
        allocated, used, size = map(int, match.groups()[:3])
        if not size or used > allocated or allocated % size or used % size or allocated // size > 0xffffffff:
            raise ValueError('invalid allocator counters')
        rows.append(dict(name=match[4].decode('utf8'), typeBytes=size,
                         allocatedBytes=allocated, inUseBytes=used))
    raise ValueError('allocator TOTAL/footer missing')


def process_identity(child):
    if child.poll() is not None:
        raise ValueError('owned child has exited')
    proc = Path('/proc') / str(child.pid)
    # A process comm may contain spaces or parentheses. Field22 follows its last ')'.
    fields = (proc / 'stat').read_text().rsplit(')', 1)[1].split()
    argv = (proc / 'cmdline').read_bytes().split(b'\0')[:-1]
    environment = dict(part.split(b'=', 1) for part in (proc / 'environ').read_bytes().split(b'\0')
                       if b'=' in part)
    expected = [os.fsencode(arg) for arg in child.args]
    if argv != expected or any(arg in (b'-f', b'-F', b'--disable_freelist', b'--disable_pfreelist') for arg in argv):
        raise ValueError('owned ATS argv/default allocator mismatch')
    if environment.get(b'PROXY_DPRINTF_LEVEL', b'0') != b'0' or environment.get(b'LD_PRELOAD') or environment.get(b'LD_AUDIT'):
        raise ValueError('allocator override environment')
    executable = proc / 'exe'
    info = executable.stat()
    return dict(pid=child.pid, startTicks=int(fields[19]), executable=os.readlink(executable),
                executableDevice=info.st_dev, executableInode=info.st_ino,
                argv=[os.fsdecode(arg) for arg in argv], allocatorOverridesAbsent=True)


def capture_dump(child, stderr, output):
    """Signal only the owned live pidfd, then wait for an actual complete dump.

    The new private output holds raw bytes even on timeout/parser failure. Sending
    a signal is never itself considered an observation or an approval.
    """
    if os.name != 'posix' or not hasattr(os, 'pidfd_open') or not hasattr(signal, 'pidfd_send_signal'):
        raise ValueError('Linux pidfd signalling required')
    output = Path(output)
    output.mkdir(mode=0o700)
    before = process_identity(child)
    fd = os.open(stderr.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    pidfd = None
    raw = b''
    try:
        metadata = os.fstat(fd)
        writer = os.fstat(stderr.fileno())
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_uid != os.getuid()
                or (metadata.st_dev,metadata.st_ino)!=(writer.st_dev,writer.st_ino)):
            raise ValueError('owned regular stderr required')
        offset = metadata.st_size
        pidfd = os.pidfd_open(child.pid)
        if process_identity(child) != before:
            raise ValueError('child identity changed before signal')
        sent = time.time_ns()
        signal.pidfd_send_signal(pidfd, signal.SIGUSR1)
        deadline = time.monotonic() + 5
        result = None
        while time.monotonic() < deadline:
            if process_identity(child) != before or os.fstat(fd).st_size < offset:
                raise ValueError('child/log identity changed')
            raw = os.pread(fd, LIMIT + 1, offset)
            if len(raw) > LIMIT:
                raise ValueError('allocator diagnostic byte limit')
            try:
                result = parse_dump(raw)
                break
            except ValueError:
                time.sleep(.05)
        if result is None:
            raise TimeoutError('complete native allocator dump not observed')
        # Bound this exact file interval; later unrelated stderr is outside it.
        raw = raw[:result['tableEnd']]
        result.update(kind='ABSOLUTE_NATIVE_POOL_DIAGNOSTIC_NOT_MEDIA_BOUND', process=before,
                      signalSentUnixNs=sent, observedUnixNs=time.time_ns(),
                      stderrOffset=offset, stderrEnd=offset + len(raw),
                      stderrDevice=metadata.st_dev, stderrInode=metadata.st_ino,
                      rawBytes=len(raw), rawSha256=hashlib.sha256(raw).hexdigest(),
                      rawFile='stderr-interval.raw', experimentApprovedByObserver=False)
        return result
    finally:
        (output / 'stderr-interval.raw').write_bytes(raw)
        os.close(fd)
        if pidfd is not None:
            os.close(pidfd)
