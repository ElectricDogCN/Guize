"""Request-key provenance components; no ATS execution or formal acceptance.

Native HIT_FRESH is enum2 from the pinned ATS ABI. Cache visibility is asserted
at the observed native lookup/read, never backdated to HTTP response completion.
Actual approved execution/source/epoch authentication remains the caller's job.
"""
from datetime import datetime
from pathlib import Path
import json

from poc003_canonical_derivation_v3 import require, file_digest, Unproven


def utc(value):
    require(isinstance(value, str) and value.endswith('Z'), 'actual UTC observation required')
    return datetime.fromisoformat(value[:-1]+'+00:00')


def journal(file):
    raw = Path(file).read_bytes()
    require(len(raw) <= 16*1024*1024, 'native metadata journal quota')
    return [json.loads(line) for line in raw.splitlines()]


class NativeRequestIndex:
    def __init__(self, native_root):
        self.by_request = {}
        self.events = {}
        for folder in sorted(Path(native_root).glob('cache-export-*')):
            pid = int(folder.name.removeprefix('cache-export-'))
            require(pid not in self.events, 'ambiguous native process folder')
            events = journal(folder/'lookup-events.jsonl')
            self.events[pid] = events
            for ordinal, event in enumerate(events):
                row = dict(event, ordinal=ordinal, atsPid=pid,
                           journalRef=str(folder/'lookup-events.jsonl'))
                self.by_request.setdefault(event['requestId'], []).append(row)

    def request(self, request_id):
        rows = self.by_request.get(request_id, [])
        require(rows and len({r['atsPid'] for r in rows}) == 1,
                'one actual native process required for this request')
        return rows


def needed_urls(context_path, start, end, source_size, slice_bytes, origin_url):
    require(context_path.startswith('/ctx/') and 0 <= start <= end < source_size
            and type(slice_bytes) is int and slice_bytes > 0, 'actual protected context/interval required')
    return [origin_url+context_path+'-bytes='+str(first)+'-'+str(min(source_size-1, first+slice_bytes-1))
            for first in range(start//slice_bytes*slice_bytes, end+1, slice_bytes)]


def same_context(left, right):
    return all(left[key] == right[key] for key in ('userId', 'sourceVersion', 'sourceSha256', 'aclVersion'))


def native_hit_proof(row, later_rows, index, urls):
    """Use exact needed Slice keys; a first-Slice HIT cannot attest a tail MISS.

    A later witness stays in the same process/context and must not cross another
    non-HIT lookup for the needed key. The caller also authenticates the process
    epoch/clear/version history. Native second-resolution timestamps stay raw.
    """
    require(isinstance(urls, (list, tuple)) and bool(urls)
            and all(isinstance(url, str) and bool(url) for url in urls)
            and len(set(urls)) == len(urls), 'nonempty unique needed Slice URLs required')
    events = index.request(row['requestId'])
    pid = events[0]['atsPid']
    original_last = max(e['ordinal'] for e in events)
    first = min(e['ordinal'] for e in events)
    own = {e['ordinal']: e for e in events}
    hits = {}
    for ordinal in range(first, original_last+1):
        event = index.events[pid][ordinal]
        url = event['lookupUrl']
        if url not in urls:
            continue
        if event.get('statusAvailable') is not True or event['nativeLookupStatus'] != 2:
            hits.pop(url, None)
        elif ordinal in own:
            hits[url] = own[ordinal]
    if all(url in hits for url in urls):
        return dict(cacheComplete=True, cacheVisible=True, atsPid=pid,
            evidenceScope='At actual native HIT_FRESH lookups during this request',
            postResponseWitness=False, nativeWitnessCutoffOrdinal=original_last,
            lookupEvidence=[hits[url] for url in urls], actualExecutionAuthenticationStillRequired=True)
    original_finish = utc(row['finishedAt'])
    candidates = []
    rows_by_id = {}
    for following in later_rows:
        if not same_context(row, following) or utc(following['startedAt']) < original_finish:
            continue
        rows_by_id[following['requestId']] = following
        candidates.extend(e for e in index.by_request.get(following['requestId'], [])
            if e['atsPid'] == pid and e['ordinal'] > original_last)
    cursor = original_last+1
    invalidated = set()
    for event in sorted(candidates, key=lambda e: e['ordinal']):
        # Inspect all needed keys to the same cutoff, including other requests.
        for pending in index.events[pid][cursor:event['ordinal']+1]:
            url = pending['lookupUrl']
            if url in urls and (pending.get('statusAvailable') is not True or pending['nativeLookupStatus'] != 2):
                hits.pop(url, None)
                invalidated.add(url)
        cursor = event['ordinal']+1
        url = event['lookupUrl']
        if url not in urls or url in invalidated:
            continue
        if event.get('statusAvailable') is True and event['nativeLookupStatus'] == 2:
            hits[url] = event
        if all(url in hits for url in urls):
            ids = {e['requestId'] for e in hits.values() if e['requestId'] != row['requestId']}
            witnesses = [{k: rows_by_id[rid][k] for k in ('requestId', 'startedAt', 'finishedAt')}
                         for rid in sorted(ids)]
            return dict(cacheComplete=True, cacheVisible=True, atsPid=pid,
                evidenceScope='Observed after original response, before a destructive boundary; not response-finish commit time',
                postResponseWitness=True, originalFinishedAt=row['finishedAt'],
                nativeWitnessCutoffOrdinal=event['ordinal'], laterWitnessRequests=witnesses,
                lookupEvidence=[hits[url] for url in urls], actualExecutionAuthenticationStillRequired=True)
    raise Unproven('needed Slice keys lack current/same-epoch subsequent native HIT_FRESH proof')


def sidecar_read_proof(row, sidecar, collection_root, source_file, start, end, index, urls):
    """Recheck one actual targeted native exported Slice, preserving read-time scope."""
    require(sidecar['requestId'] == row['requestId'] and same_context(sidecar, row),
            'sidecar request/source/user/ACL differs')
    require(sidecar['originalRequestStartedAt'] == row['startedAt']
            and sidecar['originalRequestFinishedAt'] == row['finishedAt']
            and utc(row['finishedAt']) <= utc(sidecar['startedAt']) <= utc(sidecar['finishedAt']),
            'sidecar does not follow actual HTTP response')
    require(sidecar['nativeExportInvoked'] is True and sidecar['nativeReadAttempted'] is True
            and sidecar['readableSliceVerified'] is True and sidecar['sameContextAndOriginUnchanged'] is True,
            'targeted read missing, incomplete or unknown')
    report = sidecar['nativeExport']
    require(report['nativeExportFinished'] is True and report['originJournalUnchangedDuringExport'] is True,
            'native read/origin closure missing')
    require(report['sourceVersion'] == sidecar['controllerSnapshotBefore']['sourceVersion']
            == sidecar['controllerSnapshotAfter']['sourceVersion'] == row['sourceVersion']
            and report['userId'] == row['userId'],
            'native read source/user differs')
    pid = index.request(row['requestId'])[0]['atsPid']
    require(pid == report['atsPid'] == sidecar['controllerSnapshotBefore']['atsPid']
            == sidecar['controllerSnapshotAfter']['atsPid'], 'targeted read changed process')
    require(len(urls) == len(report['selectedKeys']) == len(report['exports']) == 1,
            'one exact native Slice required')
    key, result = report['selectedKeys'][0], report['exports'][0]
    require(key['lookupUrl'] == result['lookupUrl'] == urls[0] and key['keyId'] == result['keyId']
            and key['start'] <= start <= end <= key['end']
            and urls[0].endswith('-bytes='+str(key['start'])+'-'+str(key['end'])),
            'targeted read key/interval differs')
    require(len(report['nativeRequests']) == 1 and report['nativeRequests'][0]['keyIds'] == [key['keyId']],
            'one actual targeted native job required')
    count = key['end']-key['start']+1
    require(result['status'] == 'exported' and result.get('exactInputSliceEqual') is True
            and result['reportedObjectBytes'] == result['exportedBytes'] == result['actualBytes'] == count,
            'targeted read did not finish the complete Slice')
    root = Path(collection_root).resolve()
    output = root/sidecar['exportOutputDirectory']
    file = output/result['file']
    require(not file.is_symlink() and file.resolve().is_relative_to(root), 'targeted body escaped collection')
    require(not file.samefile(source_file), 'native body aliases immutable source')
    body = file_digest(file)
    require(body == (count, result['actualSha256']) == file_digest(source_file, key['start'], count),
            'actual targeted body does not equal source Slice')
    for counter in ('originRequestCount', 'originObjectReadBytes'):
        require(sidecar['controllerSnapshotBefore'][counter] == sidecar['controllerSnapshotAfter'][counter],
                'origin changed during targeted read')
    for counter in ('activeOriginRequests', 'activeGatewayRequests'):
        require(sidecar['controllerSnapshotBefore'][counter] == sidecar['controllerSnapshotAfter'][counter] == 0,
                'targeted read did not occur in an idle context')
    return dict(cacheComplete=True, cacheVisible=True, atsPid=pid,
        postResponseWitness=True, observedFrom=sidecar['startedAt'], observedUntil=sidecar['finishedAt'],
        originalFinishedAt=row['finishedAt'], nativeKey=key, exportedFile=str(file),
        exportedBytes=body[0], exportedSha256=body[1],
        evidenceScope='Actual complete targeted Slice read after response; not whole-source or response-finish commit proof',
        actualExecutionAuthenticationStillRequired=True)
