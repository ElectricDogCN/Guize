"""Typed record materialization components; no execution or approval issuance.

The complete caller must authenticate the exact run, source, epoch, approvals and
raw selection. These functions preserve actual facts and their derivations; they
do not produce a formal PASS/profile locator or invent missing cache evidence.
"""
from collections import Counter
from datetime import datetime
import json
import math
from pathlib import Path

from poc003_canonical_derivation_v3 import (
    Unproven, require, file_digest, response_headers, protected_transfer,
    first_response_byte, native_logical_object,
)
from poc003_request_cache_provenance_v2 import utc


STAGES = ('before','filled','interrupted','recovered','updated','cleanup')


def record(common, kind, **fields):
    expected = {'configurationRef','inputSamples','inputSampleId','subjectVersion',
                'acceptanceProfile','assetId','aclVersion'}
    require(set(common) == expected, 'exact governed common bindings required')
    return dict(schemaVersion=1, kind=kind, **common, **fields)


def stable_cache_context_key(common, row, context_path):
    """A stable logical identity; each native Slice lookup URL stays separate."""
    require(row['aclVersion'] == common['aclVersion'] and context_path.startswith('/ctx/'),
            'actual governed cache context required')
    return json.dumps([common['assetId'],row['sourceVersion'],row['sourceSha256'],
        row['aclVersion'],row['userId'],context_path], separators=(',',':'))


def concurrency_for(row, rows):
    start, end = utc(row['startedAt']), utc(row['finishedAt'])
    require(start < end, 'nonempty measured HTTP interval required')
    intervals = [(r['userId'],utc(r['startedAt']),utc(r['finishedAt'])) for r in rows]
    instants = {start} | {a for _,a,b in intervals if start <= a < end}
    return max(len({user for user,a,b in intervals if a <= t < b}) for t in instants)


def purge_for(row, rows, controls):
    start = utc(row['startedAt'])
    clears = [c for c in controls if c.get('action') == 'cache-cleared-by-owned-ATS-command'
              and utc(c['at']) <= start]
    if not clears:
        return None
    last = max(clears, key=lambda c: utc(c['at']))
    # True means this is the first media request after that real completed clear.
    if any(r['requestId'] != row['requestId'] and utc(last['at']) <= utc(r['startedAt']) < start for r in rows):
        return None
    return last['at']


def origin_observation(common, row, purged_at=None):
    raw = row['originObservation']
    require(raw['requestId'] == row['requestId'] and row['originPollingSettled'] is True,
            'actual settled per-request origin witness required')
    binding = {k: row[k] for k in ('requestId','userId','requestRange','ifRange','sourceVersion','aclVersion')}
    observation = dict(schemaVersion=1,kind='range_origin_access_observation',
        configurationRef=common['configurationRef'],case=row['case'],assetId=common['assetId'],
        **binding, requestURL=row['url'],sourceSha256='sha256:'+row['sourceSha256'],
        startedAt=row['startedAt'],finishedAt=row['finishedAt'],
        originRequestCount=raw['originRequestCount'],objectReadCount=raw['objectReadCount'])
    if purged_at is not None:
        observation['cachePurgedAt'] = purged_at
    provenance = dict(actualWitnessObservedAt=raw['observedAt'],
        actualTransactions=raw['originTransactions'],actualGatewayTransactions=raw['gatewayTransactions'],
        intervalMeaning='Typed start/end identify the HTTP request; counts are its RID-bound settled observations, not a claim that no I/O occurred after HTTP finish.')
    return observation, provenance


def request_record(common, row, response_file, source_file, etag, body_ref, origin_ref,
                   cache_proof, cache_status, context_path, maximum_buffered_bytes,
                   rows, controls, policy):
    """Require pre-derived cache evidence, never a case-driven true default."""
    require(cache_status in {'MISS','FILL','HIT','INVALIDATED','PARTIAL','BYPASS'}, 'cache classification missing')
    require(type(maximum_buffered_bytes) is int and maximum_buffered_bytes >= 0,
            'complete closed-window capacity derivation required')
    require(all(type(cache_proof.get(k)) is bool for k in ('cacheComplete','cacheVisible')),
            'cache completion/visibility unproven')
    transfer = protected_transfer(row,response_file,source_file,etag)
    headers = response_headers(row)
    purged_at = purge_for(row,rows,controls)
    witness, origin_provenance = origin_observation(common,row,purged_at)
    origins = row['originObservation']['originTransactions']
    duplicates = Counter((r['path'],r['range'],r['ifRange']) for r in origins)
    retry = max([row['collectorRetryCount']]+[n-1 for n in duplicates.values()])
    typed = dict(requestId=row['requestId'],originAccessRef=origin_ref,
        startedAt=row['startedAt'],firstByteAt=first_response_byte(row),finishedAt=row['finishedAt'],
        sourceVersion=row['sourceVersion'],sourceSha256='sha256:'+row['sourceSha256'],
        requestURL=row['url'],aclVersion=row['aclVersion'],userId=row['userId'],
        cacheKey=stable_cache_context_key(common,row,context_path),requestRange=row['requestRange'],ifRange=row['ifRange'],
        statusCode=row['statusCode'],etag=headers.get('etag',''),contentRange=headers.get('content-range',''),
        responseBodyRef=body_ref,responseSha256='sha256:'+transfer['actualBodySha256'],
        responseByteCount=transfer['actualBodyBytes'],cacheComplete=cache_proof['cacheComplete'],
        cacheVisible=cache_proof['cacheVisible'],transferCompleted=transfer['transferCompleted'],
        maximumBufferedBytes=maximum_buffered_bytes,retryCount=retry,cacheStatus=cache_status,
        cachePurged=purged_at is not None,originDelayMs=policy['slowOriginDelayMs'],
        originBandwidthBytesPerSecond=policy['slowOriginBandwidthBytesPerSecond'],
        concurrentUsers=concurrency_for(row,rows))
    if purged_at is not None:
        typed['cachePurgedAt'] = purged_at
    provenance = dict(requestId=row['requestId'],transfer=transfer,cache=cache_proof,origin=origin_provenance,
        canonicalCacheStatus=cache_status,rawResponseHeaders=row['responseHeaders'],
        rawTransportCompleted=row['transportCompleted'],
        configuredOriginProfile=dict(delayMs=policy['slowOriginDelayMs'],
            bandwidthBytesPerSecond=policy['slowOriginBandwidthBytesPerSecond'],
            observedFaultModes=[r['fault'] for r in origins],
            meaning='Configured controlled profile parameters; throttling is applied only in actual slow-mode transactions, not measured normal-case throughput.'),
        maximumBufferMeaning='Complete closed-run conservative source-payload bound, not sampled RSS or an exact per-request live peak',
        cacheStatusMeaning='Evidence-constrained registered action category; original native status/header retained separately',
        retryMeaning='Actual collector retries plus repeated same-path/Range origin transactions; pinned ATS configuration must also have both connection-retry settings0')
    return typed,witness,provenance


def source_update(common, controls, policy, sources):
    changes = [c for c in controls if c.get('action') == 'version' and c['before'] != c['after']]
    require(len(changes) == 1, 'one actual governed source transition required')
    change = changes[0]
    base, updated = policy['baseVersion'], policy['updatedVersion']
    require(change['before'] == base and change['after'] == updated, 'source transition differs')
    hashes = {version:file_digest(file)[1] for version,file in sources.items()}
    require(change['beforeSha256'] == hashes[base] and change['afterSha256'] == hashes[updated]
            and hashes[base] != hashes[updated], 'actual changed source bytes required')
    return record(common,'range_source_update',observedAt=change['observedAt'],
        baseVersion=base,updatedVersion=updated,baseSha256='sha256:'+hashes[base],updatedSha256='sha256:'+hashes[updated])


def cache_lifecycle(common, stages, collection_root, sources, artifact_ref):
    require(tuple(s['stage'] for s in stages) == STAGES, 'exact six actual lifecycle stages required')
    typed, provenance = [], []
    for stage in stages:
        name = stage['stage']
        directory = Path(collection_root)/('cache-stage-'+name)
        objects = []
        if name in ('filled','recovered','updated'):
            derived = native_logical_object(stage,directory,sources[stage['sourceVersion']])
            objects.append(dict(sourceVersion=stage['sourceVersion'],artifactRef=artifact_ref(directory/derived['file']),
                sha256='sha256:'+derived['sha256'],byteCount=derived['byteCount'],complete=True,visible=True))
            detail = derived
        elif name in ('before','cleanup'):
            require(stage['noKeysObserved'] is True and not stage['selectedKeys'] and not stage['exports']
                    and stage['originCountersUnchanged'] is True, 'actual empty selected-cache observation required')
            detail = dict(noKeysObserved=True,scope='Selected test keys only; not disk occupancy')
        else:
            require(stage['completeLogicalObjectVerified'] is False and stage['nativeExportFinished'] is True
                    and stage['originCountersUnchanged'] is True and stage['exports'],
                    'actual interrupted native read required')
            require(all(r['status'] == 'open_read_failed' and not r['file'] and r['exportedBytes'] == 0
                        for r in stage['exports']), 'actual retained partial bytes need a separate proven derivation')
            detail = dict(nativeResults=stage['exports'],partialDiscardProven=stage['partialDiscardProven'],
                          scope='No readable selected complete object observed; no physical-erasure claim')
        typed.append(dict(stage=name,observedAt=stage['finishedAt'],
            allocatedBytes=sum(o['byteCount'] for o in objects),objects=objects))
        provenance.append(dict(stage=name,rawDirectory=str(directory),derivation=detail))
    return record(common,'range_cache_lifecycle',stages=typed),provenance


def matrix_report(common, case_refs, slices, source_update_ref, lifecycle_ref):
    return record(common,'range_matrix_report',sourceUpdateRef=source_update_ref,
        cacheLifecycleRef=lifecycle_ref,cases=[dict(case=k,witnessRef=v) for k,v in sorted(case_refs.items())],slices=slices)


def latency_measurements(requests_by_case, method):
    require(method in ('mean','nearest-rank-p95'), 'approved latency method required')
    result = {}
    for metric, case in [('range_hot_cache_latency','latency_hot'),('range_cold_cache_latency','latency_cold'),
                         ('range_slow_origin_latency','latency_slow'),('range_multi_user_latency','latency_multi')]:
        rows = requests_by_case[case]
        require(len(rows) == 4, 'original four actual latency samples required')
        values = [(utc(r['firstByteAt'])-utc(r['startedAt'])).total_seconds()*1000 for r in rows]
        require(all(math.isfinite(v) and v >= 0 for v in values), 'actual finite response-first-byte latency required')
        result[metric] = sum(values)/len(values) if method == 'mean' else sorted(values)[math.ceil(.95*len(values))-1]
    return result
