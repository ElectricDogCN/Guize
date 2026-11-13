"""Evidence-constrained request cache decisions; not execution authentication or PASS."""
from poc003_canonical_derivation_v3 import require, Unproven, requested_interval
from poc003_request_cache_provenance_v2 import utc, needed_urls, native_hit_proof, sidecar_read_proof


def gateway_witness(row):
    observation=row['originObservation']
    require(observation['requestId']==row['requestId'] and row['originPollingSettled'] is True,
            'settled actual request witness required')
    gateways=observation['gatewayTransactions']
    require(len(gateways)==1,'one actual gateway transaction required')
    g=gateways[0]
    for k in ('requestId','case','userId','sourceVersion','aclVersion','requestRange','ifRange'):
        require(g[k]==row[k],'gateway request identity differs: '+k)
    require(g['statusCode']==row['statusCode'] and g['responseByteCount']==row['bodyBytes'],
            'gateway/collector response differs')
    require(utc(row['startedAt'])<=utc(g['startedAt'])<=utc(g['finishedAt'])<=utc(observation['observedAt']),
            'gateway outside actual settled request interval')
    return g


def reject_destructive_boundary(row, observed_until, controls, observed_from=None):
    start,end=utc(observed_from or row['startedAt']),utc(observed_until)
    require(start<=end,'cache witness predates request')
    for c in controls:
        if c.get('action')=='cache-cleared-by-owned-ATS-command':
            at=c['at']
        elif c.get('action')=='version' and c['before']!=c['after']:
            at=c['observedAt']
        else:
            continue
        require(not start<utc(at)<=end,'cache witness crosses an actual clear/version boundary')


def negative_partial_proof(row, events, urls, stage):
    require(row['case'] in ('interrupted','partial_read'),'not a partial request')
    require(stage['stage']=='interrupted' and stage['atsPid']==events[0]['atsPid']
            and stage['sourceVersion']==row['sourceVersion'] and stage['userId']==row['userId'],
            'negative native read has another process/context')
    require(stage['nativeExportFinished'] is True and stage['completeLogicalObjectVerified'] is False
            and stage['originJournalUnchangedDuringExport'] is True and stage['originCountersUnchanged'] is True,
            'negative native read lacks closure/origin stability')
    require(len(urls)==len(stage['selectedKeys'])==len(stage['exports'])==1,
            'one exact negative native key required')
    key,result=stage['selectedKeys'][0],stage['exports'][0]
    require(key['lookupUrl']==result['lookupUrl']==urls[0] and key['keyId']==result['keyId']
            and result['status']=='open_read_failed' and result['reason']=='ATS_event_error_-20400'
            and not result['file'] and result['exportedBytes']==0,
            'actual same-key native NO_DOC required')
    needed=[e for e in events if e['lookupUrl'] in urls]
    require(needed and all(e.get('statusAvailable') is True and e['nativeLookupStatus']==0 for e in needed),
            'partial request does not have actual native MISS')
    if row['case']=='interrupted':
        require(row['statusCode']==206 and row['bodyBytes']>0 and row['transportCompleted'] is False
                and utc(row['finishedAt'])<=utc(stage['startedAt']),
                'interruption/negative-read order differs')
    else:
        require(row['statusCode']==503 and row['bodyBytes']==0
                and utc(stage['finishedAt'])<=utc(row['startedAt']),
                'unpublished retry/negative-read order differs')
    witness_end=max((row['finishedAt'],stage['finishedAt']),key=utc)
    return dict(cacheComplete=False,cacheVisible=False,atsPid=stage['atsPid'],
        observedFrom=min((row['startedAt'],stage['startedAt']),key=utc),
        observedUntil=witness_end,negativeNativeReadFrom=stage['startedAt'],negativeNativeReadUntil=stage['finishedAt'],
        nativeNoDoc=result,lookupEvidence=needed,
        evidenceScope='Actual NO_DOC plus corresponding MISS/interrupted or unavailable response; no physical-erasure claim',
        actualExecutionAuthenticationStillRequired=True)


def derive_request_cache(row, all_rows, controls, stages, sidecars, collection_root,
                         source_file, source_size, etag, slice_bytes, origin_url, index,
                         base_version, updated_version):
    """Return typed category/context and explicit proof; caller authenticates the run.

    This function never creates a profile or asserts whole-run qualification.
    Current raw source, epoch births and component/approval pins remain mandatory
    caller checks even when a returned body or native status can be verified here.
    """
    g=gateway_witness(row);origin=row['originObservation'];case=row['case']
    common=dict(actualExecutionAuthenticationStillRequired=True)
    if case in ('denied_user','unsatisfiable'):
        require(g['atsRequestSent'] is False and not index.by_request.get(row['requestId'])
                and origin['originRequestCount']==origin['objectReadCount']==origin['objectReadBytes']==0
                and not origin['originTransactions'] and row['bodyBytes']==0,
                'early rejected request touched ATS/origin/protected bytes')
        if case=='denied_user':
            require(row['statusCode']==403 and g.get('denialReason')=='acl_denied'
                    and 'cacheContextPath' not in g,'actual pre-ATS ACL rejection required')
            # This is only a declared logical policy identity, never a native lookup.
            context='/ctx/'+row['authorizationContext']+'/'+row['sourceVersion']+'/object.bin'
            scope='Declared logical denied-user context; no native key was looked up'
        else:
            require(row['statusCode']==416 and g.get('rangeResolution')=='unsatisfiable_against_governed_immutable_version',
                    'actual pre-ATS unsatisfiable Range required')
            context=g['cacheContextPath'];scope='Actual gateway context; Range rejected before ATS'
        return dict(cacheStatus='BYPASS',contextPath=context,
                    proof=dict(common,cacheComplete=False,cacheVisible=False,evidenceScope=scope))
    require(g['atsRequestSent'] is True,'actual ATS request required')
    context=g['cacheContextPath']
    require(context=='/ctx/'+row['authorizationContext']+'/'+row['sourceVersion']+'/object.bin',
            'actual gateway and collector cache contexts differ')
    status,start,end=requested_interval(row['requestRange'],row['ifRange'],etag,source_size)
    require(status in (200,206),'actual protected interval required')
    urls=needed_urls(context,start,end,source_size,slice_bytes,origin_url)
    events=index.request(row['requestId'])
    if case in ('interrupted','partial_read'):
        matches=[s for s in stages if s['stage']=='interrupted']
        require(len(matches)==1,'one interrupted native stage required')
        proof=negative_partial_proof(row,events,urls,matches[0])
        reject_destructive_boundary(row,proof['observedUntil'],controls,proof['observedFrom'])
        return dict(cacheStatus='PARTIAL',contextPath=context,proof=proof)
    if row['requestId'] in sidecars:
        proof=sidecar_read_proof(row,sidecars[row['requestId']],collection_root,source_file,start,end,index,urls)
        observed=proof['observedUntil']
    else:
        proof=native_hit_proof(row,all_rows,index,urls)
        observed=max([row['finishedAt']]+[w['finishedAt'] for w in proof.get('laterWitnessRequests',[])],key=utc)
    reject_destructive_boundary(row,observed,controls)
    needed=[e for e in events if e['lookupUrl'] in urls]
    require(needed and all(e.get('statusAvailable') is True and e['nativeLookupStatus'] in (0,2) for e in needed),
            'unclassified native lookup outcome')
    missed=any(e['nativeLookupStatus']==0 for e in needed)
    if missed:
        require(origin['originRequestCount']>0 and origin['objectReadCount']>0,
                'native MISS lacks actual origin/object access')
        category='MISS'
    else:
        require(origin['originRequestCount']==origin['objectReadCount']==origin['objectReadBytes']==0,
                'native HIT was not origin-silent')
        category='HIT'
    if case in ('fill','recovered'):
        require(category=='MISS','fill action must have actual miss/origin plus readable cache witness')
        category='FILL'
    elif case=='updated':
        changes=[c for c in controls if c.get('action')=='version' and c['before']!=c['after']]
        require(category=='MISS' and row['sourceVersion']==updated_version and len(changes)==1
                and changes[0]['before']==base_version and changes[0]['after']==updated_version
                and utc(changes[0]['observedAt'])<=utc(row['startedAt']),
                'invalidation category lacks actual preceding governed version transition and miss')
        category='INVALIDATED'
    expected={'miss':'MISS','hit':'HIT','latency_hot':'HIT','latency_cold':'MISS',
              'latency_slow':'MISS','latency_multi':'HIT'}.get(case)
    require(expected is None or category==expected,'observed native/origin category differs from registered scenario')
    proof.update(observedUntil=observed,canonicalActionCategory=category,
        rawNativeStatuses=[e['nativeLookupStatus'] for e in needed],
        evidenceScope=proof['evidenceScope']+'; typed action category is constrained by actual lookups/origin and version control')
    return dict(cacheStatus=category,contextPath=context,proof=proof)
