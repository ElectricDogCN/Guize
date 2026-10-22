"""Reject unhealthy, mixed-process and reset live-counter evidence."""
import copy,json
import pytest
from live_buffer_probe import parse_snapshots

IDENTITY=dict(pid=1234,startTicks=5678)
EXPECTED=dict(ledgerHeaderSha256='a'*64,observerSourceSha256='b'*64)

def row(sequence=0):
    return dict(kind='INSTRUMENTED_ATS_LIVE_MEDIA_CAPACITY',atsPid=1234,startTicks=5678,sequence=sequence,
                abiVersion=1,generation=1,snapshotBeforeMonotonicNs=100+sequence*100,
                snapshotAfterMonotonicNs=110+sequence*100,reset=sequence==0,cacheReady=True,httpCacheReady=True,
                currentBytes=4096,peakBytes=4096 if sequence==0 else 12288,violations=0,uncoveredExternalEvents=0,
                currentByKind=[0,4096,0,0],liveByKind=[0,1,0,0],acquisitions=[sequence,1,0,0],releases=[sequence,0,0,0],
                baselineSubtracted=False,experimentApprovedByObserver=False,**EXPECTED)

def encoded(*rows):return b''.join((json.dumps(value)+'\n').encode() for value in rows)

def test_exact_window_retains_baseline_and_peak():
    result=parse_snapshots(encoded(row(),row(1)),IDENTITY,EXPECTED,150)
    assert result['recordCount']==2 and result['maximumObservedLiveCapacityBytes']==12288
    assert result['first']['currentBytes']==4096 and not result['baselineSubtracted']
    assert not result['fullMediaBufferBoundProven']

def test_waits_for_post_request_snapshot():
    assert parse_snapshots(encoded(row()),IDENTITY,EXPECTED,150) is None

def test_complete_prefix_excludes_inflight_write():
    raw=encoded(row(),row(1))
    result=parse_snapshots(raw+b'{"incomplete":',IDENTITY,EXPECTED,150)
    assert result['rawEnd']==len(raw)

@pytest.mark.parametrize('key,value',[
    ('atsPid',1235),('startTicks',5679),('ledgerHeaderSha256','c'*64),('observerSourceSha256','d'*64),
    ('generation',2),('reset',True),('sequence',3),('abiVersion',2),('cacheReady',False),
    ('httpCacheReady',False),('baselineSubtracted',True),('violations',1),('uncoveredExternalEvents',1),
    ('peakBytes',4095),('currentBytes',True),('currentByKind',[0,4095,0,0]),('releases',[0,0,0,0]),
    ('snapshotBeforeMonotonicNs',109),('snapshotAfterMonotonicNs',199),
])
def test_rejects_corrupt_or_unhealthy_records(key,value):
    last=row(1);last[key]=value
    with pytest.raises(ValueError):parse_snapshots(encoded(row(),last),IDENTITY,EXPECTED,150)

def test_rejects_error_record():
    with pytest.raises(ValueError):parse_snapshots(encoded(row(),dict(error='instrumented_core_api_missing')),IDENTITY,EXPECTED)

def test_rejects_duplicate_json_field():
    raw=encoded(row()).replace(b'"sequence": 0',b'"sequence": 0, "sequence": 0')
    with pytest.raises(ValueError):parse_snapshots(raw,IDENTITY,EXPECTED)

def test_rejects_boundary_before_window_and_malformed_identity():
    with pytest.raises(ValueError):parse_snapshots(encoded(row()),IDENTITY,EXPECTED,99)
    with pytest.raises(ValueError):parse_snapshots(encoded(row()),IDENTITY,dict(EXPECTED,observerSourceSha256=''),0)

def test_rejects_peak_decrease():
    last=row(2);last['peakBytes']=8192
    with pytest.raises(ValueError):parse_snapshots(encoded(row(),row(1),last),IDENTITY,EXPECTED,150)

def test_external_owner_cannot_hide_with_zero_unknown_counter():
    last=row(1);last['acquisitions'][2]=1;last['releases'][2]=1
    with pytest.raises(ValueError):parse_snapshots(encoded(row(),last),IDENTITY,EXPECTED,150)
