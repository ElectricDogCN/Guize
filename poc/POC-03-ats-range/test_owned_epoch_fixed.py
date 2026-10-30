"""Caller metadata and real pipe ownership only; never launch/install a policy."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import owned_epoch as owned

pytestmark=pytest.mark.skipif(not sys.platform.startswith('linux'),reason='Linux descriptor-only tests')


def epoch(tmp_path, **options):
    journal=tmp_path/'journal'
    return owned.OwnedEpoch(['/not/launched'],'0'*64,journal,tmp_path/'launch',
        env={'GUIZE_POC003_PEAK_JOURNAL_DIR':str(journal),'LC_ALL':'C.UTF-8','PYTHONCOERCECLOCALE':'0'},
        cwd=str(tmp_path),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,components={},
        fixed_single_exec=True,**options)


def pinned(epoch):
    gate=Path(owned.__file__).resolve().parent/'instrumentation/single_exec_gate.py'
    for path in (Path(sys.executable).resolve(),gate,gate.with_name('single_exec_filter.py')):
        epoch.components[str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()
    return gate


def test_fixed_parent_requires_pinned_interpreter_gate_and_policy_before_loading(tmp_path):
    item=epoch(tmp_path)
    with pytest.raises(owned.EpochLaunchError,match='must be pinned'):
        item._load_fixed_policy()
    gate=pinned(item)
    assert item._load_fixed_policy()==gate
    assert item.process is None and not item.output.exists()
    item.components[str(gate.with_name('single_exec_filter.py'))]='0'*64
    with pytest.raises(owned.EpochLaunchError,match='fixed policy changed'):
        item._load_fixed_policy()


@pytest.mark.parametrize('change',[{'LC_ALL':'C'}, {'PYTHONCOERCECLOCALE':'1'}])
def test_locale_rejection_precedes_any_launch(tmp_path,change):
    item=epoch(tmp_path);pinned(item);item.env.update(change)
    with patch.object(owned.subprocess,'Popen',side_effect=AssertionError('no child allowed')):
        with pytest.raises(owned.EpochLaunchError,match='fixed locale'):
            item._load_fixed_policy()
    assert item.process is None and not item.output.exists()


def test_pending_listener_blocks_other_launches_before_output_or_popen(tmp_path):
    prior=owned.OwnedEpoch._single_exec_pending
    try:
        owned.OwnedEpoch._single_exec_pending=object()
        item=epoch(tmp_path)
        with patch.object(owned.subprocess,'Popen',side_effect=AssertionError('no child allowed')):
            with pytest.raises(owned.EpochLaunchError,match='owns the launch slot'):
                item.prepare()
        assert not item.output.exists()
    finally:
        owned.OwnedEpoch._single_exec_pending=prior


@pytest.mark.parametrize('handoff_error',[True,False,None])
def test_consumed_listener_is_not_closed_twice_and_send_alone_never_accepts_exec(tmp_path,handoff_error):
    item=epoch(tmp_path);item.output.mkdir();item.process=SimpleNamespace(stdin=None)
    item.launch_identity={'pid':123,'startTicks':456};item.record['componentsBeforeExec']={}
    if handoff_error is not None:item.record['targetExecutable']={}
    control_read,item.control=os.pipe2(os.O_CLOEXEC)
    item.error_fd,error_writer=os.pipe2(os.O_CLOEXEC)
    item.listener,other_end=os.pipe2(os.O_CLOEXEC)
    listener=item.listener
    item._fds.update((item.control,item.error_fd,listener))
    owned.OwnedEpoch._single_exec_pending=item
    calls=[]
    def consume(descriptor,*args,**kwargs):
        assert handoff_error is not None,'invalid caller metadata must precede ownership transfer'
        assert descriptor not in item._fds
        calls.append(descriptor);os.close(descriptor)
        audit=args[-1];audit.update(listenerClosed=True,continueSent=not handoff_error)
        if handoff_error:raise TimeoutError('injected handoff failure')
    item._fixed_policy=SimpleNamespace(_deadline_owner=lambda:None,continue_initial=consume)
    try:
        # Real pipes exercise consumption and EOF timeout; identity/native grant are mocked.
        with patch.object(owned,'process_identity',return_value=item.launch_identity), \
             patch.object(item,'_verify_components',return_value={}), \
             patch.object(item,'abort',side_effect=item.close_channels) as abort:
            with pytest.raises(KeyError if handoff_error is None else TimeoutError):item.activate(timeout=.03)
        assert calls==([] if handoff_error is None else [listener]) and abort.call_count==1
        assert owned.OwnedEpoch._single_exec_pending is None and not item._fds
        if handoff_error is not None:assert item.record['singleExecHandoff']['listenerClosed']
        assert not item.record['targetExecAttestedByNativeJournal']
        assert not item.record['completeTrackedProcessEpoch']
        assert not item.record.get('execErrorPipeClosedWithoutMessage')
        with pytest.raises(OSError):os.fstat(listener)
    finally:
        item.close_channels()
        for descriptor in (control_read,error_writer,other_end):os.close(descriptor)
