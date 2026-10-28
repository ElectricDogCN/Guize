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


def export_bounds(cfg, version):
    """Keep prototype limits; bound explicit representative exports by the input."""
    if cfg.get('fixtureProfile', 'prototype-64m-v1') != 'representative-v1':
        return 128, 128 << 20
    size = cfg['inputs'][version]['sizeBytes']
    slices = (size + cfg['sliceBytes'] - 1) // cfg['sliceBytes']
    if not 1 <= slices <= 512:
        raise ValueError('representative input exceeds native export key capacity')
    return slices, size


def slice_catalogue(rows, cfg, version, user):
    """Select real Slice keys; never construct unobserved cache keys."""
    prefix = (r'^http://(?:127\.0\.0\.1:18231|ats\.local(?::80)?)/ctx/'
              + re.escape(context(cfg['aclVersion'], user)) + '/'
              + re.escape(version) + r'/object\.bin-bytes=(\d+)-(\d+)$')
    pattern = re.compile(prefix)
    found = []
    seen = set()
    size = cfg['inputs'][version]['sizeBytes']
    maximum_keys, _ = export_bounds(cfg, version)
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
    if len(found) > maximum_keys or len({(r['start'], r['end']) for r in found}) != len(found):
        raise ValueError('duplicate Slice interval or export key bound')
    return sorted(found, key=lambda row: row['start'])


def raw_write_all(stream, block):
    """Consume an existing media view without allocating a returned bytes body."""
    offset = 0
    while offset < len(block):
        with block[offset:] as remaining:
            written = stream.write(remaining)
        if type(written) is not int or not 0 < written <= len(block) - offset:
            raise OSError('raw media write made no valid progress')
        offset += written


def export_body_observation(body, destination, input_path, start, count):
    """Copy and compare with two fixed raw-I/O slots; return metadata only."""
    if type(count) is not int or count <= 0:
        raise ValueError('positive selected Slice length required')
    size = body.stat().st_size
    if size > count:
        raise ValueError('native export body exceeds selected Slice')
    hasher = hashlib.sha256()
    actual_count = 0
    equal = True
    with body.open('rb', buffering=0) as stream, Path(destination).open('wb', buffering=0) as output:
        with memoryview(bytearray(65536)) as actual, memoryview(bytearray(65536)) as expected:
            if any(slot.obj.__alloc__() != len(slot) + 1 for slot in (actual, expected)):
                raise OSError('unqualified fixed export backing capacity')
            source = None
            try:
                while True:
                    with actual[:min(len(actual), count - actual_count + 1)] as target:
                        received = stream.readinto(target)
                        if type(received) is not int or not 0 <= received <= len(target):
                            raise OSError('invalid raw export read count')
                    if not received:
                        break
                    actual_count += received
                    if actual_count > count or actual_count > size:
                        raise ValueError('native export body changed or exceeds selected Slice')
                    with actual[:received] as block:
                        raw_write_all(output, block)
                        hasher.update(block)
                        if source is None:
                            source = Path(input_path).open('rb', buffering=0)
                            source.seek(start)
                        filled = 0
                        while filled < received:
                            with expected[filled:received] as target:
                                read = source.readinto(target)
                                if type(read) is not int or not 0 <= read <= len(target):
                                    raise OSError('invalid raw comparison read count')
                            if not read:
                                break
                            filled += read
                        with expected[:filled] as reference:
                            equal = equal and filled == received and block == reference
                if actual_count != size:
                    raise ValueError('native export body changed or exceeds selected Slice')
                return dict(actualBytes=actual_count, actualSha256=hasher.hexdigest(),
                            exactInputSliceEqual=actual_count == count and equal)
            finally:
                if source is not None:
                    source.close()
                source = None


def assemble_export_bodies(paths, destination):
    """Assemble actual native exports with one fixed raw read/write slot."""
    hasher = hashlib.sha256()
    count = 0
    with Path(destination).open('xb', buffering=0) as output, memoryview(bytearray(65536)) as backing:
        if backing.obj.__alloc__() != len(backing) + 1:
            raise OSError('unqualified fixed assembly backing capacity')
        for path in paths:
            with Path(path).open('rb', buffering=0) as body:
                while True:
                    received = body.readinto(backing)
                    if type(received) is not int or not 0 <= received <= len(backing):
                        raise OSError('invalid raw assembly read count')
                    if not received:
                        break
                    with backing[:received] as block:
                        raw_write_all(output, block)
                        hasher.update(block)
                        count += received
    return count, hasher.hexdigest()


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
    _, maximum_exported_bytes = export_bounds(cfg, version)
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
        batches = [selected[i:i+128] for i in range(0,len(selected),128)]
        accepted_ids = [row['requestId'] for row in events if row['event']=='request_accepted']
        controls = sum(row['event'] in {'request_accepted','request_rejected'} for row in events)
        if len(accepted_ids)!=len(set(accepted_ids)) or len(accepted_ids)+len(batches)>8 or controls+len(batches)>16:
            raise ValueError('native process request/control budget insufficient')
        prior_bytes = 0
        prior_results = []
        for prior_id in accepted_ids:
            if not isinstance(prior_id,str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,32}',prior_id):
                raise ValueError('invalid native prior request identity')
            prior_job = private_directory(native/('request-'+prior_id))
            prior_raw, prior_rows = journal(prior_job/'results.jsonl')
            for row in prior_rows:
                value=row.get('exportedBytes')
                if type(value) is not int or not 0<=value<=64<<20:
                    raise ValueError('invalid native prior byte observation')
                prior_bytes+=value
            prior_results.append(dict(requestId=prior_id,bytes=len(prior_raw),sha256=hashlib.sha256(prior_raw).hexdigest()))
        planned_bytes=sum(row['end']-row['start']+1 for row in selected)
        if prior_bytes+planned_bytes>512<<20:
            raise ValueError('native process export byte budget insufficient')
        report['nativeBudget']=dict(priorAcceptedJobs=len(accepted_ids),priorControls=controls,
            priorExportedBytes=prior_bytes,plannedJobs=len(batches),plannedExportBytes=planned_bytes,priorResults=prior_results)
        write_json(out/'native-budget.json',report['nativeBudget'])
        report['nativeRequests']=[]
        exported_total=0
        for batch_index,batch in enumerate(batches):
            artifact=out if len(batches)==1 else out/('batch-'+str(batch_index+1).zfill(4))
            if artifact!=out:artifact.mkdir(mode=0o700)
            request_id = 'stage-' + uuid.uuid4().hex[:24]
            preparing = native / ('preparing-' + request_id)
            fd = os.open(preparing, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'w') as stream:
                stream.write(request_id + '\n' + ''.join(str(row['keyId']) + '\n' for row in batch))
                stream.flush()
                os.fsync(stream.fileno())
            # One atomic rename keeps st_nlink==1 even if ATS immediately consumes it.
            rename_noreplace(preparing, native / 'request.ready')
            job = native / ('request-' + request_id)
            deadline = time.monotonic() + 160
            batch_finished = False
            while time.monotonic() < deadline:
                after, current_events = journal(native / 'events.jsonl')
                new_events = current_events[len(events):]
                accepted = any(row['event'] == 'request_accepted'
                               and row.get('requestId') == request_id for row in new_events)
                if any(row['event'] == 'request_rejected' for row in new_events):
                    raise ValueError('native batch request rejected; raw native evidence retained')
                accepted_rows = [row for row in new_events if row['event'] == 'request_accepted']
                finished_rows = [row for row in new_events if row['event'] == 'request_finished']
                if len(accepted_rows)>1 or len(finished_rows)>1:
                    raise ValueError('interleaved native batch events')
                if accepted and finished_rows:
                    if len(accepted_rows)!=1 or accepted_rows[0].get('keys')!=len(batch):
                        raise ValueError('native accepted batch key count differs')
                    if new_events.index(finished_rows[0])<new_events.index(accepted_rows[0]):
                        raise ValueError('native batch finish precedes acceptance')
                    batch_finished = True
                    break
                time.sleep(.1)
            else:
                raise TimeoutError('native read-only cache export deadline')
            if not batch_finished:raise ValueError('native batch did not finish')
            private_directory(job)
            expected_request=(request_id+'\n'+''.join(str(row['keyId'])+'\n' for row in batch)).encode()
            if (job/'request.txt').read_bytes()!=expected_request:
                raise ValueError('native batch request identity changed')
            results_raw, results = journal(job / 'results.jsonl')
            (artifact / 'results.jsonl').write_bytes(results_raw)
            (artifact / 'request.txt').write_bytes((job / 'request.txt').read_bytes())
            (artifact / 'events.after.jsonl').write_bytes(after)
            if len(results) != len(batch) or {r['keyId'] for r in results} != {r['keyId'] for r in batch}:
                raise ValueError('native terminal results must cover each selected key exactly once')
            for result in results:
                key = next(row for row in batch if row['keyId'] == result['keyId'])
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
                    if info.st_size > 64 << 20 or exported_total > maximum_exported_bytes:
                        raise ValueError('stage exported-byte bound')
                    count = key['end'] - key['start'] + 1
                    observed.update(export_body_observation(body, out / result['file'],
                        cfg['inputs'][version]['path'], key['start'], count))
                report['exports'].append(observed)
            report['nativeRequests'].append(dict(requestId=request_id,keyIds=[row['keyId'] for row in batch],rawDirectory=artifact.relative_to(out).as_posix()))
            events=current_events
        report['nativeExportFinished']=True
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
        count, assembled_sha256 = assemble_export_bodies((out / result['file'] for result in parts), derived)
        complete = count == size and assembled_sha256 == cfg['inputs'][version]['sha256']
        report['derivedLogicalObject'] = dict(file=derived.name, byteCount=count,
            sha256=assembled_sha256, derivation='Ordered concatenation of actual native TSCacheRead bodies',
            derivedFrom=[dict(keyId=row['keyId'], file=row['file'], sha256=row['actualSha256'],
                              start=row['start'], end=row['end']) for row in parts],
            nativeSingleEntryClaimed=False)
    report['completeLogicalObjectVerified'] = complete
    # An open-read failure alone does not prove disposal or absence of a busy cache entry.
    write_json(out / 'native-stage.json', report)
    return report
