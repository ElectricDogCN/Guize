"""Corrupt/reset/failed durable streams cannot become complete epoch evidence."""
import copy,json,pytest
from durable_peak_probe import parse_durable_peaks
IDENTITY=dict(pid=1234,startTicks=5678)
def row(sequence=0):
    peak=4096 if sequence else 0
    return dict(kind='INSTRUMENTED_ATS_DURABLE_PEAK',schemaVersion=1,pid=1234,startTicks=5678,
                sequence=sequence,abiVersion=1,generation=0,accountingWindow='process-lifetime',
                beforeMonotonicNs=100+sequence*100,peakBytes=peak,currentBytes=peak,
                currentByKind=[peak,0,0,0],acquisitions=[sequence,0,0,0],releases=[0,0,0,0],
                violations=0,uncoveredExternalEvents=0)
def encoded(*rows):return b''.join((json.dumps(r)+'\n').encode() for r in rows)
def test_completed_healthy_tracked_epoch_is_explicitly_not_media_qualification():
    result=parse_durable_peaks(encoded(row(),row(1)),IDENTITY,finished=True,exit_code=0)
    assert result['maximumObservedTrackedCapacityBytes']==4096 and result['completeTrackedProcessEpoch']
    assert not result['fullMediaBufferBoundProven']
def test_live_inflight_prefix_does_not_claim_exit_coverage():
    result=parse_durable_peaks(encoded(row(),row(1))+b'{"partial":',IDENTITY)
    assert result['trailingBytes'] and not result['completeTrackedProcessEpoch']
@pytest.mark.parametrize('exit_code',[70,-6,-15,None,True])
def test_failed_or_unconfirmed_exit_rejects_even_a_complete_prefix(exit_code):
    with pytest.raises(ValueError):parse_durable_peaks(encoded(row(),row(1)),IDENTITY,finished=True,exit_code=exit_code)
def test_finished_partial_write_is_not_trimmed_into_success():
    with pytest.raises(ValueError):parse_durable_peaks(encoded(row())+b'{"partial":',IDENTITY,finished=True,exit_code=0)
@pytest.mark.parametrize('key,value',[
    ('pid',1235),('startTicks',5679),('generation',1),('sequence',4),('schemaVersion',2),('abiVersion',2),
    ('accountingWindow','cache-ready'),('peakBytes',4095),('currentBytes',True),('violations',1),
    ('uncoveredExternalEvents',1),('beforeMonotonicNs',99),('acquisitions',[0,0,0,0]),
    ('releases',[2,0,0,0]),('currentByKind',[1,0,0,0]),('extra',0)])
def test_rejects_changed_context_or_unhealthy_record(key,value):
    last=row(1);last[key]=value
    with pytest.raises(ValueError):parse_durable_peaks(encoded(row(),last),IDENTITY)
def test_late_initialization_cannot_hide_an_earlier_allocation():
    first=row(1);first['sequence']=0
    with pytest.raises(ValueError):parse_durable_peaks(encoded(first),IDENTITY)
def test_unknown_external_owner_and_repeated_peak_are_rejected():
    last=row(1);last.update(currentByKind=[0,0,4096,0],acquisitions=[0,0,1,0])
    with pytest.raises(ValueError):parse_durable_peaks(encoded(row(),last),IDENTITY)
    repeated=row(2);repeated['peakBytes']=repeated['currentBytes']=4096
    with pytest.raises(ValueError):parse_durable_peaks(encoded(row(),row(1),repeated),IDENTITY)
