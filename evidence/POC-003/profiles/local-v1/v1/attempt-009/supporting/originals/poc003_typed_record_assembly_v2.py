"""Assemble typed evidence records only; no execution authentication, metrics PASS or profile."""
from pathlib import Path
from poc003_canonical_derivation_v3 import require
from poc003_canonical_record_materializer_v1 import (
    request_record,source_update,cache_lifecycle,matrix_report,latency_measurements,record,
)
from poc003_request_cache_decisions_v2 import derive_request_cache

EXPECTED_CASES=frozenset(('miss','fill','hit','range_start','range_middle','range_end','suffix','unsatisfiable',
    'if_match','if_stale','other_user','denied_user','stream','interrupted','partial_read','recovered',
    'latency_hot','latency_cold','latency_slow','latency_multi','updated'))


def assemble_typed_records(common,policy,collection,collection_root,sources,input_identities,
                           sidecars,index,maximum_buffered_bytes,artifact_ref,record_ref):
    """All refs/bindings must be supplied by the future authenticated full caller.

    Retained response/native bodies are rechecked by the existing materializers.
    Schema-compatible records alone do not establish a permitted run, original
    execution qualification, buffering acceptance or any one of the ten gates.
    """
    require(set(collection['collectedCases'])==EXPECTED_CASES and not collection['missingCases'],
            'exact original21 case collection required')
    require(type(maximum_buffered_bytes) is int and maximum_buffered_bytes>0,
            'actual positive complete closed-run capacity required')
    rows=collection['rows'];primary=[r for r in rows if r['case'] in EXPECTED_CASES]
    require(len({r['requestId'] for r in rows})==len(rows),'duplicate actual HTTP identity')
    require(len(primary)==33 and len(rows)==101,'original33 primary plus68 supplemental requests required')
    require(set(sources)==set(input_identities)=={policy['baseVersion'],policy['updatedVersion']},
            'exact two governed source versions required')
    root=Path(collection_root);records={};provenance=[];by_case={k:[] for k in EXPECTED_CASES}
    for row in primary:
        version=row['sourceVersion'];identity=input_identities[version]
        decision=derive_request_cache(row,rows,collection['controls'],collection['cacheStages'],sidecars,root,
            sources[version],identity['sizeBytes'],identity['etag'],policy['sliceBytes'],policy['originURL'],index,
            policy['baseVersion'],policy['updatedVersion'])
        origin_ref=record_ref('origin-'+row['requestId'])
        typed,origin,detail=request_record(common,row,root/row['bodyRef'],sources[version],identity['etag'],
            artifact_ref(root/row['bodyRef']),origin_ref,decision['proof'],decision['cacheStatus'],
            decision['contextPath'],maximum_buffered_bytes,rows,collection['controls'],policy)
        # Correct the earlier component's explanatory text without changing its bytes.
        detail['retryMeaning']='Maximum of actual collectorRetryCount and repeated same-path/Range/If-Range origin transaction count minus one; both ATS connection retry settings remain0.'
        require(origin_ref not in records,'duplicate typed origin reference')
        records[origin_ref]=origin;by_case[row['case']].append(typed);provenance.append(detail)
    case_refs={}
    for case,requests in sorted(by_case.items()):
        expected=policy['latencySampleCount'] if case.startswith('latency_') else 1
        require(len(requests)==expected,'actual governed case sample count differs')
        ref=record_ref('case-'+case);case_refs[case]=ref
        records[ref]=record(common,'range_request_observation',case=case,requests=requests)
    update_ref=record_ref('source-update');lifecycle_ref=record_ref('cache-lifecycle');report_ref=record_ref('range-matrix')
    records[update_ref]=source_update(common,collection['controls'],policy,sources)
    lifecycle,lifecycle_provenance=cache_lifecycle(common,collection['cacheStages'],root,sources,artifact_ref)
    records[lifecycle_ref]=lifecycle
    filled=[s for s in collection['cacheStages'] if s['stage']=='filled'];require(len(filled)==1,'one actual filled native stage required')
    parts=filled[0]['derivedLogicalObject']['derivedFrom']
    slices=[dict(start=p['start'],end=p['end'],sha256='sha256:'+p['sha256'],
                 artifactRef=artifact_ref(root/'cache-stage-filled'/p['file'])) for p in parts]
    records[report_ref]=matrix_report(common,case_refs,slices,update_ref,lifecycle_ref)
    require(len(records)==57,'exact33 origins/21 case records/update/lifecycle/report required')
    return dict(records=records,reportRef=report_ref,requestProvenance=provenance,
        lifecycleProvenance=lifecycle_provenance,requestsByCase=by_case,
        latencyDerivations=latency_measurements(by_case,policy['percentileMethod']),
        actualExecutionAuthenticationStillRequired=True,tenBooleanMetricsDerived=False,
        completeExecutionQualification=False,formalPocAccepted=False)
