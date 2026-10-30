"""Mandatory REAL sandbox test. Missing sandbox/observer/input is a hard failure."""
from __future__ import annotations
import argparse,hashlib,http.client,json,os,uuid
from pathlib import Path
from collect import Collector
from grants import utc_instant
from lab import context,digest,unique_json,utc,write_json


def require(condition, message):
    if not condition:raise AssertionError(message)


def retained_bytes(path, maximum=4<<20):
    with path.open('rb') as stream:data=stream.read(maximum+1)
    require(len(data)<=maximum,'observation byte budget exceeded')
    require(not data or data.endswith(b'\n'),'unfinished native journal record')
    return data


def records(data):
    return [unique_json(line) for line in data.decode('utf8').splitlines()]


def process_identity(pid):
    raw=Path('/proc',str(pid),'stat').read_text()
    return dict(pid=pid,startTicks=raw.split(') ',1)[1].split()[19],
                executable=str(Path('/proc',str(pid),'exe').resolve()))


def warm_binding(warm,cfg,user):
    # Equal short prefixes do not establish source-version or cache identity.
    transactions=warm['originObservation']['gatewayTransactions']
    require(len(transactions)==1,'warm gateway context witness missing')
    gateway=transactions[0];version=warm['sourceVersion'];ctx=context(cfg['aclVersion'],user)
    require(version=='base' and warm['sourceSha256']==cfg['inputs']['base']['sha256'],
            'fresh base source identity required')
    require(gateway['sourceVersion']==version and gateway['userId']==user and
            gateway['cacheContextPath']==f'/ctx/{ctx}/{version}/object.bin' and
            warm['authorizationContext']==ctx,'actual warm gateway/source/context identity mismatch')
    return gateway


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir',default=os.environ.get('GUIZE_POC003_RUN_DIR'))
    p.add_argument('--output-dir',default=os.environ.get('GUIZE_POC003_REVOCATION_OUT'))
    a=p.parse_args()
    if not a.run_dir or not a.output_dir:
        raise ValueError('actual GUIZE_POC003_RUN_DIR and new GUIZE_POC003_REVOCATION_OUT required')
    require(os.name=='posix' and os.geteuid()!=0,'ordinary native Linux sandbox required')
    run=Path(a.run_dir).resolve();owner=unique_json((run/'owner.json').read_text())
    require(owner['uid']==os.getuid() and owner['runDir']==str(run),'actual sandbox ownership mismatch')
    collector=Collector(run,a.output_dir);collector.save();out=collector.out
    report=dict(kind='REAL_WARM_CACHE_REVOCATION_TEST',startedAt=utc(),
                scriptSha256=digest(Path(__file__)),executedScenarios=0,
                skippedAssertions=0,status='RUNNING',pocAccepted=False)
    try:
        cfg=collector.cfg
        require(all(digest(Path(__file__).parent/name)==sha for name,sha in cfg['implementationSources'].items()),
                'prepared implementation source changed')
        listening=unique_json((run/'listeners-started.json').read_text());pid=listening['atsPid']
        preflight=collector.control('snapshot',stage='revocation-preflight')
        require(preflight['atsPid']==pid and preflight['sourceVersion']=='base',
                'fresh current ATS identity and base source required; do not reuse a restarted/changed matrix sandbox')
        identity=process_identity(pid)
        require(identity['executable']==str((Path(cfg['pkgroot'])/'usr/bin/traffic_server').resolve()),
                'owned ATS executable mismatch')
        observer=run/'cache-observer'/('cache-export-'+str(pid))
        lookup=observer/'lookup-events.jsonl';exports=observer/'events.jsonl'
        require(lookup.is_file() and exports.is_file(),'actual per-request cache observer required')
        user='lab-user-a';grant_id=cfg['grants'][user]['grantId']
        state=collector.control('grant-state',grantId=grant_id)['grant']
        require(state['reason']=='allowed' and state['revokedAt'] is None,'fresh unrevoked live grant required')
        # No clear/purge/restart occurs anywhere in this test.
        collector.request('revocation',user=user)
        warm=collector.request('revocation',user=user)
        require(warm['statusCode']==206 and warm['bodyBytes']==8 and warm['transportCompleted'],
                'real successful warm-up read required')
        require(warm.get('sourceIntervalComparison',{}).get('actualBytesEqual'),
                'warm response does not match actual protected source bytes')
        origin=warm['originObservation']
        warm_gateway=warm_binding(warm,cfg,user)
        require(warm['originPollingSettled'] and origin['originRequestCount']==origin['objectReadCount']==0,
                'warm hit must use zero origin requests/reads')
        events=records(retained_bytes(lookup))
        require(any(row['requestId']==warm['requestId'] and row['statusAvailable'] and
                    row['nativeLookupStatus']==2 for row in events),
                'actual ATS9.2.3 HIT_FRESH lookup witness required')
        before_lookup=retained_bytes(lookup);before_exports=retained_bytes(exports)
        export_rows=records(before_exports)
        if export_rows:
            require(export_rows[-1]['event'] in ('request_finished','request_rejected'),
                    'cache exporter must be idle before denial interval')
        before_controller=retained_bytes(run/'controller.jsonl')
        revoked=collector.control('revoke-grant',grantId=grant_id)['grant']
        require(revoked['grantId']==state['grantId'] and revoked['validFrom']==state['validFrom'] and
                revoked['validUntil']==state['validUntil'] and revoked['reason']=='revoked',
                'real revocation must preserve the same original grant interval')
        denied=collector.request('revocation',user=user)
        witness=collector.control('witness',requestId=denied['requestId'])
        require(denied['statusCode']==403 and denied['bodyBytes']==0,'revoked request disclosed media or was not403')
        require(witness['originRequestCount']==witness['objectReadCount']==witness['objectReadBytes']==0,
                'denied request contacted origin/read protected source')
        transactions=witness['gatewayTransactions']
        require(len(transactions)==1 and transactions[0].get('finishedAt'),'actual completed denial transaction required')
        transaction=transactions[0];auth=transaction['grantObservation']
        require(transaction['sourceVersion']==warm_gateway['sourceVersion'],
                'actual denial source version differs from the warmed protected object')
        require(not transaction['atsRequestSent'] and transaction['responseByteCount']==0 and
                transaction.get('denialReason')=='revoked' and auth['reason']=='revoked',
                'denied request reached ATS or lacks actual revoked reason')
        require(auth['grantId']==state['grantId'] and auth['validFrom']==state['validFrom'] and
                auth['validUntil']==state['validUntil'],'denial used a different grant')
        valid_from,valid_until=map(utc_instant,[state['validFrom'],state['validUntil']])
        auth_at=utc_instant(auth['authorizedAt']);effective=utc_instant(revoked['revokedAt'])
        require(valid_from<=effective<=utc_instant(denied['startedAt'])<=auth_at<valid_until,
                'replay must occur after actual revocation and before original natural expiry')
        require(denied['url']==warm['url'] and denied['requestRange']==warm['requestRange'] and
                denied['sourceVersion']==warm['sourceVersion'] and
                denied['authorizationContext']==warm['authorizationContext'],
                'replay changed protected object/version/path/range/context')
        after_lookup=retained_bytes(lookup);after_exports=retained_bytes(exports)
        require(before_lookup==after_lookup,'protected ATS cache lookup occurred during denial window')
        require(before_exports==after_exports,'cache export activity interfered with denial window')
        require(process_identity(pid)==identity,'owned ATS restarted during denial')
        after_controller=retained_bytes(run/'controller.jsonl')
        require(after_controller.startswith(before_controller),'controller journal changed history')
        changes=records(after_controller[len(before_controller):])
        require(not any(row.get('action') in ('ats-start','ats-stop-owned-child',
                    'cache-cleared-by-owned-ATS-command') or str(row.get('action','')).startswith('clear-cache')
                    for row in changes),'cache cleared or ATS restarted during denial window')
        # Preserve exact native denial-window snapshots before a separate privileged
        # control read proves the OLD cache context still contains the warm bytes.
        for name,data in [('lookup-before',before_lookup),('lookup-after',after_lookup),
                          ('export-before',before_exports),('export-after',after_exports),
                          ('controller-before',before_controller),('controller-after',after_controller)]:
            (out/(name+'.native.jsonl')).write_bytes(data)
        probe_id=uuid.uuid4().hex
        old_path=warm_gateway['cacheContextPath'];connection=http.client.HTTPConnection('127.0.0.1',cfg['atsPort'],timeout=10)
        try:
            connection.request('GET',old_path,headers={'Host':'ats.local','Range':warm['requestRange'],
                'X-Lab-ATS-Key':cfg['secret'],'X-Lab-Request-ID':probe_id,'Accept-Encoding':'identity','Connection':'close'})
            response=connection.getresponse();probe_body=response.read(9)
            probe=dict(requestId=probe_id,path=old_path,statusCode=response.status,
                       observedAt=utc(),responseHeaders=list(response.getheaders()),
                       byteCount=len(probe_body),sha256=hashlib.sha256(probe_body).hexdigest(),
                       scope='SEPARATE_PRIVILEGED_CACHE_CONTROL_AFTER_DENIAL_WINDOW')
            response.close()
        finally:connection.close()
        (out/'post-denial-control.body.bin').write_bytes(probe_body)
        probe_origin=collector.control('witness',requestId=probe_id)
        require(probe['statusCode']==206 and probe['byteCount']==8 and probe['sha256']==warm['bodySha256'],
                'original warm cache bytes are no longer available to independent control')
        require(probe_origin['originRequestCount']==probe_origin['objectReadCount']==0,
                'post-denial control was refilled from origin')
        probe_events=records(retained_bytes(lookup))
        require(any(row['requestId']==probe_id and row['statusAvailable'] and row['nativeLookupStatus']==2
                    for row in probe_events),'post-denial native warm-cache HIT witness missing')
        probe_body=None
        collector.close_request_window()
        report.update(status='PASS',executedScenarios=1,finishedAt=utc(),
                      grantBefore=state,grantRevoked=revoked,warm=warm,denied=denied,
                      denialWitness=witness,atsIdentity=identity,postDenialControl=probe,
                      postDenialOriginWitness=probe_origin,
                      scope='One actual same-unexpired-grant warm-cache revocation scenario; original15 and independent result review still required')
    except BaseException as error:
        probe_body=None
        report.update(status='FAIL',finishedAt=utc(),errorType=type(error).__name__,error=str(error))
        try:collector.close_request_window()
        except Exception as closure_error:report['requestWindowClosureError']=str(closure_error)
        write_json(out/'revocation-result.json',report);collector.save();raise
    write_json(out/'revocation-result.json',report);collector.save()
    require(report['executedScenarios']==1 and report['skippedAssertions']==0,'nonempty real scenario required')
    print(json.dumps(dict(status=report['status'],executedScenarios=1,skippedAssertions=0,pocAccepted=False)))


if __name__=='__main__':main()
