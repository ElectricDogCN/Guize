"""Protocol/failure and regular-file integration tests; never start an owner.

No target, filter, signal, container or media workload is executed. Mock process
results check control flow only and are never native execution evidence.
"""
import array
import json
import os
from pathlib import Path
import socket
import sys
import threading
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

import buffer_probe
import epoch_owner as owner
import lab

pytestmark = pytest.mark.skipif(not sys.platform.startswith('linux'), reason='Linux descriptor/control-only tests')


class FatalExit(BaseException):
    pass


def client():
    result = owner.EpochOwner.__new__(owner.EpochOwner)
    result.sequence = 0
    result.closing = False
    result.expected_shutdown_until = None
    result.lock = threading.Lock()
    result.channel = Mock()
    result.process = SimpleNamespace(pid=123)
    result.check_alive = Mock()
    result._fatal = Mock(side_effect=FatalExit)
    return result


def test_duplicate_and_nonfinite_metadata_are_rejected():
    for raw in ('{"id":1,"id":2}', '{"timeout":NaN}', '{"timeout":Infinity}'):
        with pytest.raises(owner.OwnerError):
            owner._json(raw)


def test_all_received_rights_close_even_after_unexpected_ancillary():
    channel = Mock()
    channel.recvmsg.return_value = (
        b'{}', [(123, 456, b''), (socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [81, 82]).tobytes())], 0, None)
    with patch.object(owner.os, 'close') as close:
        with pytest.raises(owner.OwnerError, match='ancillary'):
            owner._receive(channel)
        assert [call.args[0] for call in close.call_args_list] == [81, 82]


def test_truncated_metadata_does_not_leak_received_rights():
    channel = Mock()
    channel.recvmsg.return_value = (
        b'{', [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', [83]).tobytes())], socket.MSG_TRUNC, None)
    with patch.object(owner.os, 'close') as close:
        with pytest.raises(owner.OwnerError, match='truncated'):
            owner._receive(channel)
        close.assert_called_once_with(83)


def test_ambiguous_reply_timeout_never_replays_a_launch():
    item = client()
    with patch.object(owner, '_send') as send, patch.object(owner, '_receive', side_effect=TimeoutError):
        with pytest.raises(FatalExit):
            item.call('launch', operation='start', label='ats-start-0', descriptors=(81, 82))
    send.assert_called_once()
    assert send.call_args.args[1]['operation'] == 'launch'
    assert send.call_args.args[1]['arguments'] == {'operation': 'start', 'label': 'ats-start-0'}
    item._fatal.assert_called_once()
    assert item.sequence == 1


@pytest.mark.parametrize('reply', [
    {'id': 2, 'ok': True, 'result': {}},
    {'id': True, 'ok': True, 'result': {}},
    {'id': 1, 'ok': True, 'error': 'wrong outcome'},
    {'id': 1, 'ok': False, 'result': {}},
])
def test_mismatched_response_is_fatal_before_http_can_recover(reply):
    item = client()
    with patch.object(owner, '_send'), patch.object(owner, '_receive', return_value=(reply, [])):
        with pytest.raises(FatalExit):
            item.call('status', token='0')
    item._fatal.assert_called_once()


def test_authorized_shutdown_is_visible_to_monitor_before_send():
    item = client()
    # Restore the real independent monitor; no real process or pidfd is used.
    item.check_alive = lambda: owner.EpochOwner.check_alive(item)
    item.process = Mock(pid=123)
    item.process.poll.return_value = None
    item.pidfd = 99
    def send(channel, message, fds):
        assert item.expected_shutdown_until is not None
        item.process.poll.return_value = 0
        item.check_alive()  # Authorized exit while the shutdown reply is pending.
    summary = {'epochCount': 0, 'closedEpochCount': 0, 'acceptedCount': 0,
               'allAccepted': True, 'closureRoot': 'process-epochs'}
    with patch.object(owner.select, 'select', return_value=([], [], [])), \
            patch.object(owner, '_send', side_effect=send), \
            patch.object(owner, '_receive', return_value=({'id': 1, 'ok': True, 'result': summary}, [])):
        assert item.call('shutdown') == summary
    item._fatal.assert_not_called()


def test_expected_shutdown_does_not_disable_its_deadline():
    item = client(); item.expected_shutdown_until = 10
    with patch.object(owner.time, 'monotonic', return_value=11):
        with pytest.raises(FatalExit):
            owner.EpochOwner.check_alive(item)


def test_emergency_exit_does_not_wait_for_filesystem_or_rpc():
    item = client()
    with patch.object(owner, '_write_new') as write, patch.object(owner.os, '_exit', side_effect=FatalExit) as leave:
        with pytest.raises(FatalExit):
            owner.EpochOwner._fatal(item, 'lost owner')
    leave.assert_called_once_with(70)
    write.assert_not_called()
    item.channel.sendmsg.assert_not_called()


def test_target_view_rejects_wrong_birth_and_has_no_wait_or_signal_api():
    item = client(); item.process = SimpleNamespace(pid=123)
    description = {'token': '0', 'birth': {'pid': 124, 'startTicks': 7}, 'command': ['/fixed/ats']}
    target = owner.OwnerTarget(item, description)
    item.call = Mock(return_value={'birth': {'pid': 124, 'startTicks': 8}, 'exitCode': None, 'ownerPid': 123})
    with pytest.raises(FatalExit):
        target.poll()
    for name in ('wait', 'kill', 'terminate', 'send_signal', 'returncode'):
        assert not hasattr(target, name)


def test_regular_stderr_paths_reach_existing_probe_identity_boundary(tmp_path):
    (tmp_path / 'commands').mkdir()
    controller = owner._Controller.__new__(owner._Controller); controller.run = tmp_path
    class ProbeReached(RuntimeError):
        pass
    with lab.raw_writer(tmp_path / 'commands/verify-config.stdout.raw') as out, \
            lab.raw_writer(tmp_path / 'commands/verify-config.stderr.raw') as err:
        assert Path(err.name) == tmp_path / 'commands/verify-config.stderr.raw'
        assert os.fstat(err.fileno()).st_mode & 0o777 == 0o600
        streams = controller._stdio([out.fileno(), err.fileno()], 'verify-config', True)
        try:
            for name, writer in [('legacy', err), ('owner', streams[1])]:
                assert Path(writer.name) == tmp_path / 'commands/verify-config.stderr.raw'
                # The actual os.open/fstat/name-vs-FD checks run. Stop before any
                # real pidfd or signal, so this cannot become a diagnostic run.
                with patch.object(buffer_probe, 'process_identity', return_value={'pid': 124}), \
                        patch.object(buffer_probe.os, 'pidfd_open', side_effect=ProbeReached) as pidfd:
                    with pytest.raises(ProbeReached):
                        buffer_probe.capture_dump(SimpleNamespace(pid=124), writer, tmp_path / name)
                    pidfd.assert_called_once_with(124)
        finally:
            for writer in streams:
                writer.close()


def test_second_launch_is_rejected_before_descriptors_or_target_creation():
    controller = owner._Controller.__new__(owner._Controller)
    controller.epochs = {'0': object()}; controller.closures = {}
    with patch.object(controller, '_stdio') as stdio:
        with pytest.raises(owner.OwnerError, match='current service/helper'):
            controller.launch('start', 'ats-start-1', [])
    stdio.assert_not_called()


def test_shutdown_summary_stays_bounded_with_many_full_historical_closures():
    controller = owner._Controller.__new__(owner._Controller)
    controller.epochs = {str(i): object() for i in range(2000)}
    row = {'accepted': True, 'trackedEpoch': {'preservedMetadata': 'x' * 10000}}
    controller.closures = dict.fromkeys(controller.epochs, row)
    summary = controller.close()
    assert summary == {'epochCount': 2000, 'closedEpochCount': 2000, 'acceptedCount': 2000,
                       'allAccepted': True, 'closureRoot': 'process-epochs'}
    assert len(json.dumps(summary).encode()) < 256
    assert len(controller.closures) == 2000


def test_helper_rejected_closure_is_not_success_in_http_controller(tmp_path):
    state = lab.State.__new__(lab.State)
    state.cfg = {'pkgroot': '/fixed', 'liveBufferObserver': {}}
    state.run = tmp_path; (tmp_path / 'commands').mkdir()
    state.lock = threading.RLock(); state.owned_epochs = []; state.epoch_closures = []
    state.log = Mock()
    closure = {'accepted': False, 'actualWaitCompleted': True, 'exitCode': 0}
    state.epoch_owner = SimpleNamespace(call=Mock(return_value={
        'description': {'token': '0'}, 'exitCode': 0, 'closure': closure}))
    with pytest.raises(RuntimeError, match='epoch failed'):
        state.ats_command(['-C', 'verify_config'], 'verify-config')
    assert state.epoch_closures == [closure]
    assert state.epoch_owner.call.call_count == 1
