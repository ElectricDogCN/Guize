"""Retain native read-only ATS cache exports. No HTTP fetch or PASS synthesis."""
from __future__ import annotations

import hashlib
import ctypes
import os
from pathlib import Path
import re
import stat
import time
import uuid

from lab import context, unique_json, utc, write_json


def private_directory(path):
    path = Path(path)
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o700 or path.resolve() != path):
        raise ValueError('owned private nonsymlink observer directory required')
    return path


def journal(path):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1
            or info.st_size > 8 << 20):
        raise ValueError('owned regular native journal required')
    raw = path.read_bytes()
    if len(raw) > 8 << 20:
        raise ValueError('native journal byte bound')
    # A concurrently appended final line may not be complete yet.
    rows = [unique_json(line.decode()) for line in raw.splitlines(keepends=True)
            if line.endswith(b'\n')]
    return raw, rows


def rename_noreplace(source, destination):
    """Publish one single-link file atomically; never replace a pending request."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1) != 0:
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(destination))


def slice_catalogue(rows, cfg, version, user):
    """Select real Slice keys; never construct unobserved cache keys."""
    prefix = (r'^http://(?:127\.0\.0\.1:18231|ats\.local(?::80)?)/ctx/'
              + re.escape(context(cfg['aclVersion'], user)) + '/'
              + re.escape(version) + r'/object\.bin-bytes=(\d+)-(\d+)$')
    pattern = re.compile(prefix)
    found = []
    seen = set()
    size = cfg['inputs'][version]['sizeBytes']
    for row in rows:
        match = pattern.fullmatch(row['lookupUrl'])
        if not match:
            continue
        start, end = map(int, match.groups())
        key = row['keyId']
        if (type(key) is not int or not 1 <= key <= 512 or key in seen
                or start % cfg['sliceBytes'] or not 0 <= start <= end < size
                or end != min(start + cfg['sliceBytes'], size) - 1):
            raise ValueError('duplicate or invalid actual Slice catalogue entry')
        seen.add(key)
        found.append(dict(row, start=start, end=end))
    if len(found) > 128 or len({(r['start'], r['end']) for r in found}) != len(found):
        raise ValueError('duplicate Slice interval or export key bound')
    return sorted(found, key=lambda row: row['start'])


def read_export_body(body, maximum_bytes):
    """Read one selected native export body for byte-exact comparison."""
    return body.read_bytes()


def export_stage(run, out, cfg, snapshot, version, user='lab-user-a'):
    output = Path(out)
    existed = output.exists() or output.is_symlink()
    try:
        return _export_stage(run, out, cfg, snapshot, version, user)
    except Exception as error:
        # Keep the immutable start/raw records and a distinct failure receipt.
        if not existed and output.is_dir() and not output.is_symlink() and not (output / 'stage.failed.json').exists():
            write_json(output / 'stage.failed.json', dict(status='FAILED_RAW_RETAINED',
                       observedAt=utc(), errorType=type(error).__name__, error=str(error),
                       formalPocAccepted=False))
        raise


def _export_stage(run, out, cfg, snapshot, version, user):
    """Snapshot only actual key exports; read failures remain unclassified failures."""
    run, out = Path(run), Path(out)
    pid = snapshot['atsPid']
    if type(pid) is not int or pid <= 0:
        raise ValueError('actual live ATS pid required')
    native = private_directory(run / 'cache-observer' / ('cache-export-' + str(pid)))
    if out.exists() or out.is_symlink():
        raise ValueError('new stage output required')
    out.mkdir(mode=0o700)
    deadline = time.monotonic() + 5
    previous = None
    stable = 0
    while time.monotonic() < deadline:
        catalogue_raw, catalogue = journal(native / 'lookups.jsonl')
        stable = stable + 1 if catalogue_raw == previous else 0
        previous = catalogue_raw
        if stable >= 3:
            break
        time.sleep(.3)
    else:
        raise TimeoutError('actual observer catalogue did not settle')
    selected = slice_catalogue(catalogue, cfg, version, user)
    (out / 'catalogue.before.jsonl').write_bytes(catalogue_raw)
    before, events = journal(native / 'events.jsonl')
    (out / 'events.before.jsonl').write_bytes(before)
    if any((native / name).exists() for name in ('request.ready', 'request.active')):
        raise ValueError('another observer request is active')
    if sum(row['event'] == 'request_accepted' for row in events) != sum(
            row['event'] == 'request_finished' for row in events):
        raise ValueError('observer must be idle before stage export')
    if snapshot.get('activeOriginRequests') != 0 or snapshot.get('activeGatewayRequests') != 0:
        raise ValueError('stage export requires observed idle gateway and origin')
    origin_before = {name: (run / name).read_bytes() if (run / name).exists() else b''
                     for name in ('origin-start.jsonl', 'origin-access.jsonl')}
    report = dict(kind='ACTUAL_NATIVE_CACHE_STAGE_EXPORT_UNASSESSED', stage=snapshot['stage'],
                  startedAt=utc(), atsPid=pid, sourceVersion=version, userId=user,
                  selectedKeys=selected, exports=[], nativeExportFinished=False,
                  noKeysObserved=not selected, completeLogicalObjectVerified=False,
                  partialDiscardProven=False, formalPocAccepted=False)
    write_json(out / 'stage.started.json', report)
    if selected:
        request_id = 'stage-' + uuid.uuid4().hex[:24]
        preparing = native / ('preparing-' + request_id)
        fd = os.open(preparing, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as stream:
            stream.write(request_id + '\n' + ''.join(str(row['keyId']) + '\n' for row in selected))
            stream.flush()
            os.fsync(stream.fileno())
        # One atomic rename keeps st_nlink==1 even if ATS immediately consumes it.
        rename_noreplace(preparing, native / 'request.ready')
        job = native / ('request-' + request_id)
        deadline = time.monotonic() + 160
        while time.monotonic() < deadline:
            after, current_events = journal(native / 'events.jsonl')
            new_events = current_events[len(events):]
            accepted = any(row['event'] == 'request_accepted'
                           and row.get('requestId') == request_id for row in new_events)
            if accepted and any(row['event'] == 'request_finished' for row in new_events):
                report['nativeExportFinished'] = True
                break
            time.sleep(.1)
        else:
            raise TimeoutError('native read-only cache export deadline')
        private_directory(job)
        results_raw, results = journal(job / 'results.jsonl')
        (out / 'results.jsonl').write_bytes(results_raw)
        (out / 'request.txt').write_bytes((job / 'request.txt').read_bytes())
        (out / 'events.after.jsonl').write_bytes(after)
        if len(results) != len(selected) or {r['keyId'] for r in results} != {r['keyId'] for r in selected}:
            raise ValueError('native terminal results must cover each selected key exactly once')
        exported_total = 0
        for result in results:
            key = next(row for row in selected if row['keyId'] == result['keyId'])
            if result['lookupUrl'] != key['lookupUrl']:
                raise ValueError('native result key mismatch')
            observed = dict(result, start=key['start'], end=key['end'])
            if result['file']:
                if result['file'] not in ('key-' + str(key['keyId']) + '.body',
                                          'key-' + str(key['keyId']) + '.body.part'):
                    raise ValueError('unexpected native export filename')
                body = job / result['file']
                info = body.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
                    raise ValueError('owned regular export body required')
                exported_total += info.st_size
                if info.st_size > 64 << 20 or exported_total > 128 << 20:
                    raise ValueError('stage exported-byte bound')
                count = key['end'] - key['start'] + 1
                actual = read_export_body(body, count)
                (out / result['file']).write_bytes(actual)
                with Path(cfg['inputs'][version]['path']).open('rb') as source:
                    source.seek(key['start'])
                    expected = source.read(count)
                observed.update(actualBytes=len(actual), actualSha256=hashlib.sha256(actual).hexdigest(),
                                exactInputSliceEqual=len(actual) == count and actual == expected)
            report['exports'].append(observed)
    origin_after = {name: (run / name).read_bytes() if (run / name).exists() else b''
                    for name in origin_before}
    for name in origin_before:
        (out / (name + '.before')).write_bytes(origin_before[name])
        (out / (name + '.after')).write_bytes(origin_after[name])
    unchanged = origin_after == origin_before
    report.update(finishedAt=utc(), originJournalUnchangedDuringExport=unchanged)
    size = cfg['inputs'][version]['sizeBytes']
    cursor = 0
    complete = bool(selected) and unchanged and report['nativeExportFinished']
    parts = []
    for key in selected:
        result = next(row for row in report['exports'] if row['keyId'] == key['keyId'])
        count = key['end'] - key['start'] + 1
        complete = complete and key['start'] == cursor and result['status'] == 'exported'
        complete = complete and result.get('exactInputSliceEqual', False)
        complete = complete and result['reportedObjectBytes'] == count and result['exportedBytes'] == count
        cursor = key['end'] + 1
        parts.append(result)
    complete = complete and cursor == size
    if complete:
        derived = out / 'assembled-from-native-cache.bin'
        hasher = hashlib.sha256()
        count = 0
        with derived.open('xb') as stream:
            for result in parts:
                with (out / result['file']).open('rb') as body:
                    while block := body.read(65536):
                        stream.write(block)
                        hasher.update(block)
                        count += len(block)
        complete = count == size and hasher.hexdigest() == cfg['inputs'][version]['sha256']
        report['derivedLogicalObject'] = dict(file=derived.name, byteCount=count,
            sha256=hasher.hexdigest(), derivation='Ordered concatenation of actual native TSCacheRead bodies',
            derivedFrom=[dict(keyId=row['keyId'], file=row['file'], sha256=row['actualSha256'],
                              start=row['start'], end=row['end']) for row in parts],
            nativeSingleEntryClaimed=False)
    report['completeLogicalObjectVerified'] = complete
    # An open-read failure alone does not prove disposal or absence of a busy cache entry.
    write_json(out / 'native-stage.json', report)
    return report
