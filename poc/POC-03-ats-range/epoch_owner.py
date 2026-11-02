"""POC-specific, single-thread owner of instrumented ATS executions.

The lab must be the ordinary-user PID1 of an independently approved private
namespace. The local PID1 guard is necessary, not external isolation proof.
Only this process has target Popen/wait/signalling authority. The client view
reports owner facts and deliberately has no target wait or signal methods.
"""
from __future__ import annotations

import array
import hashlib
import json
import os
from pathlib import Path
import re
import select
import signal
import socket
import stat
import subprocess
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
MAX_PACKET = 65536
FD_BYTES = array.array('i').itemsize
RPC_TIMEOUTS = {'launch': 60, 'status': 3, 'identity': 10, 'finish': 30,
                'live_snapshot': 15, 'allocator_dump': 10, 'shutdown': 30}


class OwnerError(RuntimeError):
    pass


def _json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise OwnerError('duplicate protocol field')
            result[key] = value
        return result
    def constant(_):
        raise OwnerError('nonfinite protocol number')
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def _send(channel, value, fds=()):
    raw = json.dumps(value, separators=(',', ':'), allow_nan=False).encode('utf-8')
    if not 0 < len(raw) <= MAX_PACKET:
        raise OwnerError('protocol packet limit')
    ancillary = [(socket.SOL_SOCKET, socket.SCM_RIGHTS, array.array('i', fds))] if fds else []
    if channel.sendmsg([raw], ancillary) != len(raw):
        raise OwnerError('short protocol packet')


def _receive(channel, expected_fds=None):
    fds = []
    try:
        raw, ancillary, flags, _ = channel.recvmsg(
            MAX_PACKET + 1, socket.CMSG_SPACE(2 * FD_BYTES), socket.MSG_CMSG_CLOEXEC)
        invalid = False
        for level, kind, data in ancillary:
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                values = array.array('i'); values.frombytes(data[:len(data) // FD_BYTES * FD_BYTES]); fds.extend(values)
                invalid |= bool(len(data) % FD_BYTES)
            else:
                invalid = True
        if invalid:
            raise OwnerError('unexpected ancillary data')
        if not raw or len(raw) > MAX_PACKET or flags & (socket.MSG_TRUNC | socket.MSG_CTRUNC):
            raise OwnerError('closed or truncated protocol packet')
        if len(fds) > 2 or expected_fds is not None and len(fds) != expected_fds:
            raise OwnerError('unexpected protocol descriptors')
        value = _json(raw)
        if type(value) is not dict:
            raise OwnerError('protocol object required')
        return value, fds
    except BaseException:
        for fd in fds:
            os.close(fd)
        raise


def _digest(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(65536), b''):
            digest.update(block)
    return digest.hexdigest()


def _birth(pid):
    fields = (Path('/proc') / str(pid) / 'stat').read_text().rsplit(')', 1)[1].split()
    return {'pid': pid, 'startTicks': int(fields[19])}


def _ordinary_scope(*, init):
    if os.name != 'posix' or os.getuid() == 0 or os.getuid() != os.geteuid():
        raise OwnerError('ordinary Linux UID required')
    if init and os.getpid() != 1 or not init and os.getppid() != 1:
        raise OwnerError('lab PID1 and direct owner child required')
    status = dict(line.split(':', 1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    if (status['NoNewPrivs'].strip() != '1'
            or any(int(status[key].strip(), 16) for key in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb'))
            or len(list(Path('/proc/self/task').iterdir())) != 1
            or threading.get_native_id() != os.getpid()):
        raise OwnerError('singleton native main thread, no capabilities and no-new-privileges required')


def _write_new(path, value):
    raw = (json.dumps(value, indent=2, allow_nan=False) + '\n').encode('utf-8')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)


class OwnerTarget:
    """Bound target metadata and owner's liveness; not a subprocess.Popen."""
    def __init__(self, owner, description):
        self._owner = owner
        self.description = dict(description)
        self.pid = description['birth']['pid']
        self.args = tuple(description['command'])

    def poll(self):
        result = self._owner.call('status', token=self.description['token'])
        if (type(result) is not dict or set(result) != {'birth', 'exitCode', 'ownerPid'}
                or result['birth'] != self.description['birth'] or result['ownerPid'] != self._owner.process.pid
                or result['exitCode'] is not None and type(result['exitCode']) is not int):
            self._owner._fatal('target status identity mismatch')
        return result['exitCode']


class EpochOwner:
    """Private client. Protocol failure exits PID1 without taking State.lock."""
    def __init__(self, run, cfg):
        _ordinary_scope(init=True)
        self.run = Path(run)
        self.cfg = cfg
        self.channel = None
        self.process = None
        self.pidfd = None
        self.sequence = 0
        self.lock = threading.Lock()
        self.closing = False
        self.expected_shutdown_until = None
        interpreter = cfg['executionInterpreter']
        source = HERE / 'epoch_owner.py'
        if (str(Path(sys.executable).resolve()) != interpreter['path']
                or _digest(interpreter['path']) != interpreter['sha256']
                or _digest(source) != cfg['implementationSources']['epoch_owner.py']):
            raise OwnerError('prepared owner/interpreter pins required')
        parent, child = socket.socketpair(socket.AF_UNIX, socket.SOCK_SEQPACKET | socket.SOCK_CLOEXEC)
        streams = []
        try:
            for name in ('stdout', 'stderr'):
                fd = os.open(self.run / ('execution-owner.' + name + '.raw'),
                             os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, 0o600)
                streams.append(os.fdopen(fd, 'wb'))
            env = dict(os.environ, LC_ALL='C.UTF-8', PYTHONCOERCECLOCALE='0')
            env.pop('LD_PRELOAD', None); env.pop('LD_AUDIT', None)
            self.process = subprocess.Popen(
                [interpreter['path'], '-I', '-S', '-B', str(source), str(child.fileno()), str(self.run)],
                stdin=subprocess.DEVNULL, stdout=streams[0], stderr=streams[1], env=env,
                close_fds=True, pass_fds=(child.fileno(),), cwd=self.run)
            child.close(); self.channel = parent; parent.settimeout(15)
            self.pidfd = os.pidfd_open(self.process.pid)
            self.owner_birth = _birth(self.process.pid)
            response, _ = _receive(parent, 0)
            if response != {'ready': True, 'birth': self.owner_birth, 'parentPid': 1}:
                raise OwnerError('owner birth handshake mismatch')
            self.check_alive()
        except BaseException:
            child.close(); parent.close()
            if self.process is not None:
                self._fatal('owner startup failed')
            raise
        finally:
            for stream in streams:
                stream.close()

    def _fatal(self, reason):
        # Never enter State.lock, HTTP error handling, server.shutdown or an RPC.
        # Actual external init exit/engine wait must attest namespace termination;
        # no target wait or return code is invented here when owner is lost.
        # Do not delay namespace termination on a filesystem write or pipe drain.
        # The outer controller must retain actual init exit70 and engine state.
        os._exit(70)

    def check_alive(self):
        # Independent of the RPC mutex and State.lock; called by namespace PID1.
        if self.expected_shutdown_until is not None:
            if time.monotonic() > self.expected_shutdown_until:
                self._fatal('authorized owner shutdown exceeded deadline')
            return
        if self.process.poll() is not None or select.select([self.pidfd], [], [], 0)[0]:
            self._fatal('unexpected owner exit')

    def call(self, verb, *, descriptors=(), **arguments):
        with self.lock:
            if self.closing:
                raise OwnerError('owner already closing')
            if self.expected_shutdown_until is not None:
                raise OwnerError('owner shutdown already requested')
            self.check_alive(); self.sequence += 1
            try:
                self.channel.settimeout(RPC_TIMEOUTS[verb])
                if verb == 'shutdown':
                    self.expected_shutdown_until = time.monotonic() + RPC_TIMEOUTS[verb] + 5
                _send(self.channel, {'id': self.sequence, 'operation': verb, 'arguments': arguments}, descriptors)
                response, _ = _receive(self.channel, 0)
                if (type(response.get('id')) is not int or response['id'] != self.sequence
                        or type(response.get('ok')) is not bool):
                    raise OwnerError('mismatched owner response')
                if set(response) != ({'id', 'ok', 'result'} if response['ok'] else {'id', 'ok', 'error'}):
                    raise OwnerError('mismatched owner outcome fields')
            except BaseException:
                self._fatal('owner channel failed; no request replay')
            if not response['ok']:
                raise OwnerError('owner operation rejected: ' + str(response['error']))
            return response['result']

    def shutdown(self):
        try:
            result = self.call('shutdown')
        except BaseException:
            self._fatal('owner shutdown protocol rejected')
        self.closing = True; self.channel.close()
        try:
            code = self.process.wait(timeout=5)
        except BaseException:
            self._fatal('owner shutdown wait failed')
        if code != 0:
            self._fatal('owner shutdown exit rejected')
        os.close(self.pidfd); self.pidfd = None
        _write_new(self.run / 'execution-owner-wait.json', {
            'ownerBirth': self.owner_birth, 'ownerExitCode': code,
            'actualOwnerWaitCompleted': True, 'targetClosureSummary': result})
        if (type(result) is not dict
                or set(result) != {'epochCount','closedEpochCount','acceptedCount','allAccepted','closureRoot'}
                or any(type(result[key]) is not int for key in ('epochCount','closedEpochCount','acceptedCount'))
                or not 0 <= result['acceptedCount'] <= result['closedEpochCount'] == result['epochCount']
                or type(result['allAccepted']) is not bool
                or result['allAccepted'] != (result['acceptedCount'] == result['epochCount'])
                or result['closureRoot'] != 'process-epochs' or not result['allAccepted']):
            raise OwnerError('target closure summary rejected')


class _NamedWriter:
    """Own a received regular-file FD and retain its verified path for probes."""
    def __init__(self, fd, path):
        self._stream = os.fdopen(os.dup(fd), 'wb', buffering=0)
        self.name = str(path)

    def fileno(self):
        return self._stream.fileno()

    def close(self):
        self._stream.close()


class _Controller:
    """No State constructor, HTTP state, input reads or background threads."""
    def __init__(self, run):
        from lab import EPOCH_CONFIGURATION_FILES
        self.run = Path(run).resolve()
        self.cfg = _json((self.run / 'settings.private.json').read_text())
        self.epochs = {}; self.streams = {}; self.closures = {}
        if self.cfg.get('liveBufferObserver') is None:
            raise OwnerError('instrumented profile required')
        if set(self.cfg['epochConfiguration']) != set(EPOCH_CONFIGURATION_FILES):
            raise OwnerError('exact seven effective configuration pins required')
        for name, expected in self.cfg['implementationSources'].items():
            if _digest(HERE / name) != expected:
                raise OwnerError('prepared implementation changed')
        interpreter = self.cfg['executionInterpreter']
        if str(Path(sys.executable).resolve()) != interpreter['path'] or _digest(interpreter['path']) != interpreter['sha256']:
            raise OwnerError('owner interpreter changed')

    def components(self):
        required = {str(Path(self.cfg['pkgroot']) / name): sha
                    for name, sha in self.cfg['instrumentedRuntime']['components'].items()}
        required.update({row['path']: row['sha256'] for row in self.cfg['plugins'].values()})
        required.update({str(self.run / name): sha for name, sha in self.cfg['epochConfiguration'].items()})
        for name in ('epoch_owner.py', 'instrumentation/single_exec_gate.py', 'instrumentation/single_exec_filter.py'):
            required[str(HERE / name)] = self.cfg['implementationSources'][name]
        required[self.cfg['executionInterpreter']['path']] = self.cfg['executionInterpreter']['sha256']
        return required

    def _environment(self, directory):
        env = dict(os.environ, LD_LIBRARY_PATH=self.cfg['ldLibraryPath'],
                   TS_RUNROOT=str(self.run / 'runroot.yaml'), PROXY_DPRINTF_LEVEL='0',
                   GUIZE_POC003_PEAK_JOURNAL_DIR=str(directory), LC_ALL='C.UTF-8', PYTHONCOERCECLOCALE='0')
        env.pop('LD_PRELOAD', None); env.pop('LD_AUDIT', None)
        return env

    def _stdio(self, fds, label, helper):
        import fcntl
        if len(fds) != 2:
            raise OwnerError('exact stdout/stderr descriptors required')
        if helper:
            stem = self.run / 'commands' / label
        else:
            match = re.fullmatch(r'ats-start-([0-9]+)', label)
            if not match:
                raise OwnerError('bounded ATS start label required')
            stem = self.run / 'log' / ('ats-' + match[1])
        streams = []
        try:
            for fd, suffix in zip(fds, ('stdout', 'stderr')):
                path = Path(str(stem) + '.' + suffix + '.raw')
                actual = os.fstat(fd); named = path.lstat()
                if (not stat.S_ISREG(actual.st_mode) or actual.st_uid != os.getuid()
                        or not stat.S_ISREG(named.st_mode) or actual.st_size != 0
                        or fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_WRONLY
                        or stat.S_IMODE(actual.st_mode) != 0o600 or actual.st_nlink != 1
                        or (actual.st_dev, actual.st_ino) != (named.st_dev, named.st_ino)):
                    raise OwnerError('private configured stdout/stderr identity required')
                streams.append(_NamedWriter(fd, path))
            return streams
        except BaseException:
            for stream in streams:
                stream.close()
            raise

    def launch(self, operation, label, fds):
        from owned_epoch import OwnedEpoch
        helper = operation != 'start'
        if operation not in ('start', 'verify_config', 'clear_cache') or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', label):
            raise OwnerError('fixed ATS operation and bounded label required')
        if any(token not in self.closures for token in self.epochs):
            raise OwnerError('finish the current service/helper before another launch')
        command = [str(Path(self.cfg['pkgroot']) / 'usr/bin/traffic_server'), '--run-root=' + str(self.run)]
        command += ['-n', '2'] if not helper else ['-C', operation]
        streams = self._stdio(fds, label, helper)
        token = str(len(self.epochs)); root = self.run / 'process-epochs' / ('epoch-' + token)
        epoch = None
        try:
            root.mkdir(mode=0o700)
            required = self.components()
            epoch = OwnedEpoch(command, required[command[0]], root / 'journal', root / 'launch',
                               env=self._environment(root / 'journal'), cwd=self.run,
                               stdout=streams[0], stderr=streams[1], components=required, fixed_single_exec=True)
            self.epochs[token] = epoch; self.streams[token] = streams
            epoch.prepare(); epoch.activate()
            description = {'token': token, 'birth': epoch.birth_identity, 'command': command,
                           'directory': str(epoch.directory), 'output': str(epoch.output)}
            if helper:
                code = None
                try:
                    code = epoch.process.wait(timeout=30)
                finally:
                    closure = self.finish(token, label, stop=False)
                return {'description': description, 'exitCode': code, 'closure': closure}
            return description
        except BaseException:
            if epoch is not None and token not in self.closures:
                self.finish(token, label + '-launch-failed', stop=False)
            elif epoch is None:
                for stream in streams:
                    stream.close()
            raise

    def epoch(self, token):
        if type(token) is not str or token not in self.epochs:
            raise OwnerError('unknown epoch token')
        return self.epochs[token]

    def finish(self, token, label, *, stop):
        if token in self.closures:
            return self.closures[token]
        epoch = self.epoch(token); result = None; failure = None
        try:
            if epoch.process is not None and epoch.process.poll() is None:
                if stop:
                    try:
                        signal.pidfd_send_signal(epoch.pidfd, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        epoch.process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        epoch.abort()
                else:
                    epoch.abort()
            result = epoch.finish_journal(epoch.output.parent / 'finished')
        except Exception as error:
            failure = type(error).__name__ + ': ' + str(error)
        finally:
            if epoch.process is not None and epoch.process.poll() is None:
                epoch.abort()
            else:
                epoch.close_channels()
            for stream in self.streams[token]:
                stream.close()
        row = {'action': 'owned-epoch-closed', 'label': label, 'pid': epoch.process.pid if epoch.process else None,
               'epochRef': str(epoch.output.parent.relative_to(self.run)), 'accepted': result is not None,
               'trackedEpoch': result, 'error': failure,
               'exitCode': epoch.process.returncode if epoch.process else None,
               'actualWaitCompleted': bool(epoch.record.get('waitCompleted')),
               'allDescendantsCovered': False, 'noSubsequentExecProven': False, 'fullMediaBufferBoundProven': False}
        _write_new(epoch.output.parent / 'closure.json', row); self.closures[token] = row
        return row

    def _ready(self, token):
        epoch = self.epoch(token); epoch.target_identity()
        ready = self.run / 'cache-observer' / ('cache-export-' + str(epoch.process.pid)) / 'cache-ready.json'
        observation = _json(ready.read_text())
        if (observation.get('atsPid') != epoch.process.pid or observation.get('cacheReady') is not True
                or observation.get('httpCacheReady') is not True or ready.is_symlink()):
            raise OwnerError('actual native HTTP cache readiness required')
        return epoch, observation

    def diagnostic(self, operation, token, label=None, after_ns=0):
        from buffer_probe import capture_dump, process_identity
        epoch, ready = self._ready(token)
        if operation == 'allocator_dump':
            label = 'allocator-dump-' + str(self.dump_count); self.dump_count += 1
            if self.dump_count > 16:
                raise OwnerError('diagnostic quota')
            result = capture_dump(epoch.view, self.streams[token][1], self.run / label)
        else:
            from live_buffer_probe import capture_components, capture_live
            if (not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', label or '') or self.live_count >= 16
                    or type(after_ns) is not int or not 0 <= after_ns <= time.monotonic_ns()):
                raise OwnerError('bounded live snapshot required')
            self.live_count += 1; identity = process_identity(epoch.view)
            required = {str(Path(self.cfg['pkgroot']) / name): sha
                        for name, sha in self.cfg['instrumentedRuntime']['components'].items()}
            required.update({row['path']: row['sha256'] for row in self.cfg['plugins'].values()})
            mappings = capture_components(epoch.view, required, self.run / (label + '-components'))
            expected = {key: self.cfg['liveBufferObserver'][key] for key in ('ledgerHeaderSha256', 'observerSourceSha256')}
            result = capture_live(epoch.view, self.run / 'cache-observer', self.run / label,
                                  expected, after_ns, journal_directory=epoch.directory)
            if process_identity(epoch.view) != identity:
                raise OwnerError('target changed during live snapshot')
            result.update(actualMappedComponents=required, componentMapping=mappings)
        result['nativeCacheReady'] = ready
        return result

    def check_idle_targets(self):
        for token, epoch in self.epochs.items():
            if token not in self.closures and epoch.process.poll() is not None:
                self.finish(token, 'unexpected-target-exit', stop=False)
                raise OwnerError('active ATS target exited unexpectedly')

    def close(self):
        for token in self.epochs:
            if token not in self.closures:
                self.finish(token, 'owner-shutdown', stop=True)
        accepted = sum(row.get('accepted') is True for row in self.closures.values())
        return {'epochCount': len(self.epochs), 'closedEpochCount': len(self.closures),
                'acceptedCount': accepted, 'allAccepted': accepted == len(self.epochs),
                'closureRoot': 'process-epochs'}


def _serve(fd, run):
    _ordinary_scope(init=False)
    controller = _Controller(run); controller.dump_count = 0; controller.live_count = 0
    channel = socket.socket(fileno=fd); channel.set_inheritable(False); channel.settimeout(.2)
    sequence = 0
    try:
        _send(channel, {'ready': True, 'birth': _birth(os.getpid()), 'parentPid': os.getppid()})
        while True:
            controller.check_idle_targets()
            try:
                message, fds = _receive(channel)
            except socket.timeout:
                continue
            shutdown = False
            try:
                if (set(message) != {'id', 'operation', 'arguments'} or type(message['id']) is not int
                        or message['id'] != sequence + 1 or type(message['arguments']) is not dict):
                    raise OwnerError('closed sequenced request required')
                sequence = message['id']; operation = message['operation']; args = message['arguments']
                shapes = {'launch': {'operation', 'label'}, 'status': {'token'}, 'identity': {'token'},
                          'finish': {'token', 'label', 'stop'}, 'live_snapshot': {'token', 'label', 'after_ns'},
                          'allocator_dump': {'token'}, 'shutdown': set()}
                if operation not in shapes or set(args) != shapes[operation] or len(fds) != (2 if operation == 'launch' else 0):
                    raise OwnerError('unknown operation, fields or descriptors')
                try:
                    if operation == 'launch':
                        result = controller.launch(args['operation'], args['label'], fds)
                    elif operation == 'status':
                        epoch = controller.epoch(args['token'])
                        result = {'birth': epoch.birth_identity, 'exitCode': epoch.process.poll(), 'ownerPid': os.getpid()}
                    elif operation == 'identity':
                        result = controller.epoch(args['token']).target_identity()
                    elif operation == 'finish':
                        if type(args['stop']) is not bool or not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', args['label']):
                            raise OwnerError('closed finish policy required')
                        result = controller.finish(args['token'], args['label'], stop=args['stop'])
                    elif operation in ('live_snapshot', 'allocator_dump'):
                        result = controller.diagnostic(operation, **args)
                    else:
                        result = controller.close(); shutdown = True
                    response = {'id': sequence, 'ok': True, 'result': result}
                except Exception as error:
                    # Do not serialize private environment/credentials or a traceback.
                    response = {'id': sequence, 'ok': False, 'error': type(error).__name__}
                _send(channel, response)
            finally:
                for received in fds:
                    os.close(received)
            if shutdown:
                return
    finally:
        try:
            controller.close()
        finally:
            channel.close()


if __name__ == '__main__':
    # -I/-S intentionally omit the script directory; only the pinned directory
    # is added, without site packages, startup hooks or a user search path.
    sys.path.insert(0, str(HERE))
    if len(sys.argv) != 3 or not sys.argv[1].isascii() or not sys.argv[1].isdigit():
        raise SystemExit('fixed owner descriptor and prepared run required')
    _serve(int(sys.argv[1]), sys.argv[2])
