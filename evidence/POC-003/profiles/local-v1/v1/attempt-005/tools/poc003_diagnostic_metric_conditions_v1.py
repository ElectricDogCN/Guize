"""Explicit diagnostic conditions for all15 observations; never execution/profile acceptance."""
from collections import defaultdict
from poc003_canonical_derivation_v3 import require,file_digest,requested_interval
from poc003_request_cache_provenance_v2 import utc


def derive_diagnostic_conditions(assembled,collection,policy,sources,input_identities,resolve_artifact,complete_capacity):
    """Inputs must come from the authenticated caller, which is still outstanding.

    The booleans below describe rechecked record conditions only. Formal values
    remain unset until exact approval/source/epoch/runtime/raw authenticity and
    original execution qualification are separately established.
    """
    by=assembled['requestsByCase'];details={p['requestId']:p for p in assembled['requestProvenance']}
    rows=[r for requests in by.values() for r in requests]
    require(len(rows)==len(details)==33 and len(by)==21,'exact assembled primary request matrix required')
    base,changed=policy['baseVersion'],policy['updatedVersion'];limit=policy['maximumBufferedBytes']
    require(limit==8388608 and policy['maximumRetries']==0,'unchanged original8MiB/retry0 policy required')
    require(type(complete_capacity) is int and complete_capacity>0
            and all(r['maximumBufferedBytes']==complete_capacity for r in rows),'one actual complete-run bound required')
    objects=list(assembled['records'].values())
    update=next(x for x in objects if x['kind']=='range_source_update')
    lifecycle=next(x for x in objects if x['kind']=='range_cache_lifecycle')
    matrix=next(x for x in objects if x['kind']=='range_matrix_report')
    etags={base:policy['baseETag'],changed:policy['updatedETag']}
    expected_sha={v:'sha256:'+identity['sha256'] for v,identity in input_identities.items()}
    single=lambda case:by[case][0]
    successful=lambda r:r['statusCode'] in (200,206) and r['transferCompleted'] is True
    fullcache=lambda r:r['cacheComplete'] is True and r['cacheVisible'] is True
    count=lambda r:details[r['requestId']]['origin']['actualTransactions']
    proof=lambda r:details[r['requestId']]['cache']
    cap_ok=complete_capacity<=limit
    retries_ok=all(r['retryCount']<=policy['maximumRetries'] for r in rows)
    byte_results=[];qualified_range=[]
    for case in ('range_start','range_middle','range_end','suffix','unsatisfiable','if_match','if_stale'):
        r=single(case);size=input_identities[r['sourceVersion']]['sizeBytes']
        code,start,end=requested_interval(r['requestRange'],r['ifRange'],etags[r['sourceVersion']],size)
        expected_range=('bytes */'+str(size)) if code==416 else '' if code==200 else 'bytes '+str(start)+'-'+str(end)+'/'+str(size)
        valid=r['statusCode']==code and r['etag']==etags[r['sourceVersion']] and r['contentRange']==expected_range
        if code==416:valid=valid and r['responseByteCount']==0
        else:valid=valid and successful(r) and fullcache(r) and r['responseByteCount']==end-start+1
        byte_results.append(bool(valid));qualified_range.append(bool(valid and cap_ok and r['retryCount']<=policy['maximumRetries']))
    matched,stale=single('if_match'),single('if_stale')
    etag_ok=etags[base]!=etags[changed] and all(r['etag']==etags[r['sourceVersion']] for r in rows if r['statusCode'] in (200,206,416))
    if_range_ok=successful(matched) and matched['statusCode']==206 and matched['responseByteCount']==8 and matched['ifRange']==etags[base]
    if_range_ok=if_range_ok and successful(stale) and stale['statusCode']==200 and stale['responseByteCount']==input_identities[base]['sizeBytes']
    if_range_ok=if_range_ok and stale['ifRange']!=etags[base] and stale['responseSha256']==expected_sha[base]
    slices=matrix['slices'];cursor=0;slice_ok=bool(slices)
    for part in slices:
        n=part['end']-part['start']+1
        slice_ok=slice_ok and part['start']==cursor and n==min(policy['sliceBytes'],input_identities[base]['sizeBytes']-cursor) and n>0
        cursor=part['end']+1
    filled=next(s for s in lifecycle['stages'] if s['stage']=='filled')
    slice_ok=slice_ok and cursor==input_identities[base]['sizeBytes'] and len(filled['objects'])==1 and filled['objects'][0]['sha256']==expected_sha[base]
    updated=single('updated');changed_at=utc(update['observedAt'])
    base_contexts={r['cacheKey'] for r in rows if r['sourceVersion']==base and r['userId']==updated['userId']}
    update_ok=update['baseSha256']==expected_sha[base] and update['updatedSha256']==expected_sha[changed] and expected_sha[base]!=expected_sha[changed]
    update_ok=update_ok and etag_ok and updated['sourceVersion']==changed and utc(updated['startedAt'])>=changed_at
    update_ok=update_ok and all(utc(r['finishedAt'])<=changed_at for r in rows if r['sourceVersion']==base)
    update_ok=update_ok and successful(updated) and fullcache(updated) and updated['cacheStatus']=='INVALIDATED' and updated['cacheKey'] not in base_contexts
    interrupted,partial,recovered=single('interrupted'),single('partial_read'),single('recovered')
    _,prefix_start,_=requested_interval(interrupted['requestRange'],interrupted['ifRange'],etags[base],input_identities[base]['sizeBytes'])
    prefix=file_digest(resolve_artifact(interrupted['responseBodyRef']))
    correct_prefix=prefix==(interrupted['responseByteCount'],interrupted['responseSha256'].removeprefix('sha256:')) and prefix==file_digest(sources[base],prefix_start,interrupted['responseByteCount'])
    interruption_ok=utc(interrupted['startedAt'])<utc(partial['startedAt'])<utc(recovered['startedAt'])
    interruption_ok=interruption_ok and interrupted['statusCode']==206 and 0<interrupted['responseByteCount']<8 and correct_prefix and interrupted['transferCompleted'] is False
    interruption_ok=interruption_ok and partial['statusCode']==503 and partial['responseByteCount']==0 and partial['transferCompleted'] is False
    interruption_ok=interruption_ok and any(t['fault']=='truncate' and t['objectReadBytes']==interrupted['responseByteCount'] for t in count(interrupted))
    interruption_ok=interruption_ok and count(partial) and all(t['fault']=='unavailable' and t['objectReadCount']==t['objectReadBytes']==0 for t in count(partial))
    interruption_ok=interruption_ok and successful(recovered) and fullcache(recovered) and recovered['cacheStatus']=='FILL' and count(recovered) and all(t['fault']=='none' for t in count(recovered)) and retries_ok
    partial_ok=bool(interruption_ok) and all(not r['cacheComplete'] and not r['cacheVisible'] and r['cacheStatus']=='PARTIAL' for r in (interrupted,partial))
    partial_ok=partial_ok and all(proof(r).get('nativeNoDoc',{}).get('reason')=='ATS_event_error_-20400' for r in (interrupted,partial))
    partial_ok=partial_ok and not next(s for s in lifecycle['stages'] if s['stage']=='interrupted')['objects']
    hot=[single('hit')]+by['latency_hot']+by['latency_multi']
    hit_ok=all(successful(r) and fullcache(r) and r['cacheStatus']=='HIT' and not count(r)
               and proof(r)['rawNativeStatuses'] and set(proof(r)['rawNativeStatuses'])=={2} for r in hot)
    hit_ok=hit_ok and all(single(c)['cacheStatus']==status and count(single(c)) for c,status in [('miss','MISS'),('fill','FILL')])
    disk_checks=[]
    for stage in collection['cacheStages']:
        for k in ('controllerSnapshotBefore','controllerSnapshotAfter'):
            s=stage[k];entries=s['cacheFiles']
            disk_checks.append(s['atsPid']==stage['atsPid'] and s['sourceVersion']==stage['sourceVersion']
                and type(s['allocatedDiskBytes']) is int and s['allocatedDiskBytes']>=0
                and sum(f['allocatedBytes'] for f in entries)==s['allocatedDiskBytes']
                and all(type(f['logicalBytes']) is int and f['logicalBytes']>=f['allocatedBytes']>=0 for f in entries))
    stage_names=[s['stage'] for s in lifecycle['stages']]
    clears=[c for c in collection['controls'] if c.get('action')=='cache-cleared-by-owned-ATS-command']
    disk_ok=stage_names==['before','filled','interrupted','recovered','updated','cleanup'] and len(disk_checks)==12 and all(disk_checks) and len(clears)==12
    disk_ok=disk_ok and all(not s['objects'] for s in lifecycle['stages'] if s['stage'] in ('before','cleanup'))
    contexts=defaultdict(lambda:defaultdict(set))
    for r in rows:contexts[r['sourceVersion']][r['userId']].add(r['cacheKey'])
    isolation_ok=set(contexts[base])==set(policy['authorizedUsers']+[policy['deniedUser']])
    for users in contexts.values():
        isolation_ok=isolation_ok and all(len(keys)==1 for keys in users.values()) and len({next(iter(keys)) for keys in users.values()})==len(users)
    denied,other=single('denied_user'),single('other_user')
    isolation_ok=isolation_ok and denied['statusCode']==403 and denied['responseByteCount']==0 and not denied['cacheVisible'] and not count(denied)
    isolation_ok=isolation_ok and other['userId']!=policy['authorizedUsers'][0] and fullcache(other) and successful(other)
    streaming_ok=cap_ok and all(successful(single(c)) and single(c)['statusCode']==200
        and single(c)['responseByteCount']==input_identities[base]['sizeBytes'] and single(c)['responseSha256']==expected_sha[base]
        and 0<complete_capacity<input_identities[base]['sizeBytes'] for c in ('stream','if_stale'))
    gates=dict(etag_semantics=etag_ok,if_range_semantics=if_range_ok,ats_slice_behavior=slice_ok,
        source_update_invalidation=update_ok,origin_interruption_recovery=bool(interruption_ok),
        partial_cache_integrity=bool(partial_ok),cache_hit_observation=bool(hit_ok),cache_disk_observation=bool(disk_ok),
        cache_key_isolation=bool(isolation_ok),large_file_streaming=bool(streaming_ok))
    return dict(gateDiagnostics=gates,rangeByteCorrectnessPercent=100*sum(byte_results)/len(byte_results),
        rangeCaseValidationPercent=100*sum(qualified_range)/len(qualified_range),latencyDiagnostics=assembled['latencyDerivations'],
        completeCapacityWithinOriginalBound=cap_ok,completeCapacityBytes=complete_capacity,originalCapacityLimitBytes=limit,
        physicalCacheErasureClaimed=False,diskMeaning='Actual disk allocation observations and separately typed selected logical-object lifecycle; cleanup is not physical-zero allocation.',
        formalMeasurements=None,actualExecutionAuthenticationStillRequired=True,formalPocAccepted=False)
