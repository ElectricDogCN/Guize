"""Deterministic derivation components; no execution, approvals or PASS emission.

Raw HTTP completion and delivery of the requested protected representation are
different facts. Native cache files are distinct again. Callers retain this
provenance beside the unchanged frozen typed records, never inside their schema.
"""
from pathlib import Path
import hashlib


class Unproven(ValueError):
    """The selected raw material cannot support the requested derivation."""


def require(condition, reason):
    if not condition:
        raise Unproven(reason)


def file_digest(file, start=0, count=None):
    """Hash retained bytes with a fixed 64KiB reader, including empty files."""
    file = Path(file)
    require(file.is_file() and not file.is_symlink(), 'regular retained file required')
    require(start >= 0 and (count is None or count >= 0), 'nonnegative interval')
    total = 0
    digest = hashlib.sha256()
    with file.open('rb', buffering=0) as stream:
        stream.seek(start)
        while count is None or total < count:
            chunk = stream.read(65536 if count is None else min(65536, count-total))
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
    require(count is None or total == count, 'retained source interval shortened')
    return total, digest.hexdigest()


def response_headers(row):
    """Keep protocol identity unambiguous instead of choosing one duplicate."""
    result = {}
    for key, value in row['responseHeaders']:
        key = key.lower()
        if key in ('etag', 'content-range', 'content-length'):
            require(key not in result, 'duplicate response identity header')
        result[key] = value
    return result


def requested_interval(range_header, if_range, etag, size):
    if not range_header or if_range and if_range != etag:
        return 200, 0, size-1
    require(range_header.startswith('bytes=') and ',' not in range_header, 'single byte range required')
    first, last = range_header[6:].split('-', 1)
    if not first:
        require(last.isdigit() and int(last) > 0, 'positive suffix required')
        return 206, max(0, size-int(last)), size-1
    require(first.isdigit() and (not last or last.isdigit()), 'numeric byte interval required')
    first = int(first)
    end = min(size-1, int(last)) if last else size-1
    if first >= size or end < first:
        return 416, 0, -1
    return 206, first, end


def protected_transfer(row, response_file, source_file, etag):
    """Derive transferCompleted without consulting the case's desired outcome."""
    source_size, source_sha = file_digest(source_file)
    body_size, body_sha = file_digest(response_file)
    require(source_sha == row['sourceSha256'], 'source hash differs from raw binding')
    require((body_size, body_sha) == (row['bodyBytes'], row['bodySha256']), 'raw response bytes changed')
    code, start, end = requested_interval(row['requestRange'], row['ifRange'], etag, source_size)
    headers = response_headers(row)
    length = headers.get('content-length')
    if length is not None:
        require(length.isascii() and length.isdigit(), 'invalid Content-Length syntax')
        if row['transportCompleted'] is True:
            require(int(length) == body_size, 'Content-Length contradicts complete HTTP response bytes')
    expected_range = f'bytes {start}-{end}/{source_size}' if code == 206 else ''
    delivered = bool(code in (200, 206) and row['statusCode'] == code
        and row['transportCompleted'] is True
        and not row.get('transportError') and not row.get('bodyPersistenceError')
        and headers.get('etag') == etag and headers.get('content-range', '') == expected_range
        and body_size == end-start+1)
    expected_sha = None
    if code in (200, 206):
        _, expected_sha = file_digest(source_file, start, end-start+1)
        delivered = delivered and body_sha == expected_sha
    return dict(transferCompleted=delivered, rawTransportCompleted=row['transportCompleted'],
        actualStatus=row['statusCode'], expectedStatus=code, expectedStart=start, expectedEnd=end,
        actualBodyBytes=body_size, actualBodySha256=body_sha, expectedBodySha256=expected_sha,
        derivation='Complete byte-correct requested protected representation; not HTTP message completion')


def first_response_byte(row):
    """Use the same observed response-first-byte clock for success and errors."""
    require(isinstance(row.get('firstResponseByteAt'), str) and row['firstResponseByteAt'],
            'actual response-first-byte observation missing')
    return row['firstResponseByteAt']


def native_logical_object(stage, directory, source_file):
    """Validate actual Slice bodies and their separately retained concatenation.

    This derives a logical whole object, never one physical ATS entry or memory
    capacity. Empty/NO_DOC stages need their own observed-isolation derivation.
    """
    directory = Path(directory).resolve()
    require(stage['completeLogicalObjectVerified'] is True, 'native logical object unproven')
    require(stage['nativeExportFinished'] is True and stage['originJournalUnchangedDuringExport'] is True
            and stage['originCountersUnchanged'] is True, 'native export/origin stability missing')
    before, after = stage['controllerSnapshotBefore'], stage['controllerSnapshotAfter']
    require(before['atsPid'] == after['atsPid'] == stage['atsPid'], 'native process changed')
    require(before['sourceVersion'] == after['sourceVersion'] == stage['sourceVersion'], 'version changed')
    for key in ('originRequestCount', 'originObjectReadBytes'):
        require(before[key] == after[key], 'origin access changed')
    for key in ('activeOriginRequests', 'activeGatewayRequests'):
        require(before[key] == after[key] == 0, 'request still active')
    size, source_sha = file_digest(source_file)
    keys, exports = stage['selectedKeys'], stage['exports']
    require(len(keys) == len(exports) and bool(keys), 'native key/result coverage missing')
    require(len({r['keyId'] for r in keys}) == len(keys), 'duplicate native key')
    cursor = 0
    parts = []
    combined = hashlib.sha256()
    for key, result in zip(keys, exports):
        require(key['start'] == cursor and key['end'] >= cursor, 'noncontiguous native coverage')
        count = key['end']-cursor+1
        require(result['keyId'] == key['keyId'] and result['lookupUrl'] == key['lookupUrl']
            and result['status'] == 'exported' and result.get('exactInputSliceEqual') is True,
            'native result identity or complete read missing')
        require(result['reportedObjectBytes'] == result['exportedBytes'] == result['actualBytes'] == count,
                'native byte counts differ')
        file = directory/result['file']
        require(not file.is_symlink() and file.resolve().is_relative_to(directory), 'native export escaped output directory')
        require(not file.samefile(source_file), 'native artifact aliases immutable source')
        actual = file_digest(file)
        require(actual == (count, result['actualSha256']) and actual == file_digest(source_file, cursor, count),
                'native retained Slice bytes differ')
        with file.open('rb', buffering=0) as stream:
            for chunk in iter(lambda: stream.read(65536), b''):
                combined.update(chunk)
        parts.append(dict(keyId=key['keyId'], file=result['file'], sha256=actual[1], start=cursor, end=key['end']))
        cursor += count
    require(cursor == size and combined.hexdigest() == source_sha, 'whole source coverage differs')
    derived = stage['derivedLogicalObject']
    require(derived['nativeSingleEntryClaimed'] is False and derived['derivedFrom'] == parts,
            'logical object provenance differs')
    file = directory/derived['file']
    require(not file.is_symlink() and file.resolve().is_relative_to(directory), 'logical artifact escaped output directory')
    require(not file.samefile(source_file), 'logical artifact aliases immutable source')
    require(file_digest(file) == (size, source_sha) == (derived['byteCount'], derived['sha256']),
            'actual retained logical object differs')
    return dict(file=derived['file'], byteCount=size, sha256=source_sha, derivedFrom=parts,
                nativeSingleEntryClaimed=False, scope='Actual native Slice concatenation; no physical-disk or memory claim')
