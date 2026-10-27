"""Fixed x86_64 trusted-bootstrap helper; not a sandbox or an active lab path.

No filter is installed at import. Native execution needs a separately reviewed
finite profile. CONTINUE is valid here only for the pinned, blocked singleton
bootstrap with default signals and no mutating peer; ID_VALID is not a lock.
See docs.kernel.org/userspace-api/seccomp_filter.html and seccomp_unotify(2).
"""
import array
import contextlib
import ctypes
import hashlib
import os
from pathlib import Path
import signal
import socket
import stat
import struct
import sys
import threading
import time

ARCH = 0xc000003e
KILL, ALLOW, NOTIFY = 0x80000000, 0x7fff0000, 0x7fc00000
DENY, UNAVAILABLE = 0x00050001, 0x00050026  # Linux EPERM=1, ENOSYS=38 on the fixed ABI.
AT_EMPTY_PATH = 0x1000
MAX_ELF_BYTES = 256 * 1024 * 1024


def fixed_filter():
    """One immutable BPF profile, not caller-supplied policy or syscall lists."""
    return (
        (0x20, 0, 0, 4), (0x15, 1, 0, ARCH), (0x06, 0, 0, KILL),
        (0x20, 0, 0, 0), (0x35, 0, 1, 0x40000000), (0x06, 0, 0, KILL),
        (0x15, 0, 1, 57), (0x06, 0, 0, DENY),       # fork
        (0x15, 0, 1, 58), (0x06, 0, 0, DENY),       # vfork
        (0x15, 0, 1, 435), (0x06, 0, 0, UNAVAILABLE),# clone3: prove libc fallback
        (0x15, 0, 1, 317), (0x06, 0, 0, DENY),      # later seccomp installation
        (0x15, 0, 1, 59), (0x06, 0, 0, NOTIFY),     # execve: parent rejects
        (0x15, 0, 1, 322), (0x06, 0, 0, NOTIFY),    # exact initial execveat only
        (0x15, 0, 4, 56), (0x20, 0, 0, 16),       # legacy clone flags
        (0x45, 1, 0, 0x10000), (0x06, 0, 0, DENY), (0x06, 0, 0, ALLOW),
        (0x15, 0, 4, 157), (0x20, 0, 0, 16),      # prctl option, kernel int ABI
        (0x15, 0, 1, 22), (0x06, 0, 0, DENY), (0x06, 0, 0, ALLOW),
        (0x06, 0, 0, ALLOW),
    )


class Filter(ctypes.Structure):
    _fields_ = [('code', ctypes.c_uint16), ('jt', ctypes.c_uint8),
                ('jf', ctypes.c_uint8), ('k', ctypes.c_uint32)]


class Program(ctypes.Structure):
    _fields_ = [('length', ctypes.c_uint16), ('instructions', ctypes.POINTER(Filter))]


class Sizes(ctypes.Structure):
    _fields_ = [('notification', ctypes.c_uint16), ('response', ctypes.c_uint16), ('data', ctypes.c_uint16)]


class Data(ctypes.Structure):
    _fields_ = [('number', ctypes.c_int32), ('arch', ctypes.c_uint32),
                ('ip', ctypes.c_uint64), ('args', ctypes.c_uint64 * 6)]


class Notification(ctypes.Structure):
    _fields_ = [('id', ctypes.c_uint64), ('pid', ctypes.c_uint32),
                ('flags', ctypes.c_uint32), ('data', Data)]


class Response(ctypes.Structure):
    _fields_ = [('id', ctypes.c_uint64), ('value', ctypes.c_int64),
                ('error', ctypes.c_int32), ('flags', ctypes.c_uint32)]


class Native:
    def __init__(self):
        if (not sys.platform.startswith('linux') or os.uname().machine != 'x86_64'
                or sys.byteorder != 'little' or ctypes.sizeof(ctypes.c_void_p) != 8
                or ctypes.sizeof(ctypes.c_long) != 8
                or (ctypes.sizeof(Notification), ctypes.sizeof(Response), ctypes.sizeof(Data)) != (80, 24, 64)):
            raise ValueError('fixed native x86_64 ABI required')
        self.libc = ctypes.CDLL(None, use_errno=True)
        self.libc.syscall.restype = ctypes.c_long
        self.libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
        self.libc.prctl.restype = ctypes.c_int
        self.libc.ioctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_void_p]
        self.libc.ioctl.restype = ctypes.c_int

    def sizes(self):
        sizes = Sizes()
        result = self.libc.syscall(ctypes.c_long(317), ctypes.c_uint(3), ctypes.c_uint(0), ctypes.byref(sizes))
        if result != 0:
            raise OSError(ctypes.get_errno(), 'seccomp notification sizes unavailable')
        if (sizes.notification, sizes.response, sizes.data) != (80, 24, 64):
            raise ValueError('unsupported kernel notification ABI')
        return sizes

    def ioctl(self, descriptor, operation, value):
        if self.libc.ioctl(descriptor, operation, ctypes.byref(value)) != 0:
            raise OSError(ctypes.get_errno(), 'single-exec notification ioctl rejected')

    def valid(self, descriptor, notification_id):
        value = ctypes.c_uint64(notification_id)
        self.ioctl(descriptor, 0x40082102, value)


def _status(pid):
    rows = {}
    for line in (Path('/proc')/str(pid)/'status').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in rows:
            raise ValueError('duplicate process status')
        rows[key] = value.strip()
    return rows


def _singleton(pid, birth, parent, *, installed):
    status = _status(pid)
    if (os.getuid() == 0 or os.getuid() != os.geteuid()
            or [int(x) for x in status['Uid'].split()] != [os.geteuid()]*4
            or int(status['Tgid']) != pid or int(status['PPid']) != parent
            or sorted(p.name for p in (Path('/proc')/str(pid)/'task').iterdir()) != [str(pid)]
            or int(status['SigCgt'], 16) or int(status['SigBlk'], 16) or int(status['SigIgn'], 16)
            or any(int(status[k], 16) for k in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb'))):
        raise ValueError('ordinary trusted singleton/default-signal/capability profile required')
    tail = (Path('/proc')/str(pid)/'stat').read_text().rpartition(')')[2].split()
    if birth is not None and int(tail[19]) != int(birth['startTicks']):
        raise ValueError('owned gate birth changed')
    if installed and (status['NoNewPrivs'] != '1' or status['Seccomp'] != '2'):
        raise ValueError('installed unprivileged filter observation required')
    return dict(pid=pid, startTicks=int(tail[19]), parent=parent,
                taskCount=1, signalsDefault=True, capabilitiesZero=True,
                noNewPrivs=status['NoNewPrivs'], seccomp=status['Seccomp'])


def gate_signal_defaults():
    """Trusted gate only: no user handler may mutate a blocked initial exec."""
    signal.pthread_sigmask(signal.SIG_SETMASK, [])
    for number in signal.valid_signals() - {signal.SIGKILL, signal.SIGSTOP}:
        signal.signal(number, signal.SIG_DFL)


def install_listener(expected_parent):
    native = Native()
    native.sizes()  # No further seccomp syscall is permitted after installation.
    _singleton(os.getpid(), None, expected_parent, installed=False)
    instructions = (Filter * len(fixed_filter()))(*(Filter(*row) for row in fixed_filter()))
    program = Program(len(instructions), instructions)
    if native.libc.prctl(38, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'NoNewPrivs rejected')
    result = native.libc.syscall(ctypes.c_long(317), ctypes.c_uint(1), ctypes.c_uint(8), ctypes.byref(program))
    if result < 0:
        raise OSError(ctypes.get_errno(), 'fixed listener creation rejected')
    descriptor = int(result)
    try:
        if descriptor < 3:
            raise ValueError('separate listener descriptor required')
        os.set_inheritable(descriptor, False)
        _singleton(os.getpid(), None, expected_parent, installed=True)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def transfer_listener(channel, descriptor):
    """Consume the gate's only listener ref before close-ack and channel EOF."""
    try:
        try:
            rights = array.array('i', [descriptor])
            if channel.sendmsg([b'L'], [(socket.SOL_SOCKET, socket.SCM_RIGHTS, rights)], socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL) != 1:
                raise ValueError('short listener transfer')
        finally:
            os.close(descriptor)
        if channel.send(b'C', socket.MSG_DONTWAIT | socket.MSG_NOSIGNAL) != 1:
            raise ValueError('short listener close acknowledgement')
    finally:
        channel.close()


def receive_listener(channel, timeout):
    """One private SOCK_SEQPACKET message/ref, close-ack and empty EOF only."""
    descriptors = []
    try:
        if not 0 < timeout <= 5 or channel.family != socket.AF_UNIX or channel.type & 0xf != socket.SOCK_SEQPACKET:
            raise ValueError('private sequenced local channel required')
        deadline = time.monotonic()+timeout
        def receive():
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise TimeoutError('listener transfer deadline')
            channel.settimeout(remaining)
            return channel.recvmsg(1, socket.CMSG_SPACE(16), socket.MSG_CMSG_CLOEXEC)
        message, ancillary, flags, _ = receive()
        invalid = False
        for level, kind, data in ancillary:
            invalid |= level != socket.SOL_SOCKET or kind != socket.SCM_RIGHTS or len(data) % 4 != 0
            if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                values = array.array('i');values.frombytes(data[:len(data)//4*4]);descriptors.extend(values)
        if invalid or message != b'L' or flags & (socket.MSG_CTRUNC | socket.MSG_TRUNC) or len(descriptors) != 1:
            raise ValueError('exactly one complete listener transfer required')
        for expected in (b'C', b''):
            message, ancillary, flags, _ = receive()
            # Collect delivered descriptors even in a rejected later message.
            for level, kind, data in ancillary:
                if level == socket.SOL_SOCKET and kind == socket.SCM_RIGHTS:
                    values = array.array('i');values.frombytes(data[:len(data)//4*4]);descriptors.extend(values)
            if message != expected or ancillary or flags & (socket.MSG_CTRUNC | socket.MSG_TRUNC):
                raise ValueError('listener sender closure not established')
        descriptor = descriptors[0]
        os.set_inheritable(descriptor, False)
        channel.close()
        descriptors.clear()
        return descriptor
    finally:
        for descriptor in descriptors:
            os.close(descriptor)
        channel.close()


def _deadline_owner():
    # ITIMER_REAL is process-directed: a Python MainThread label alone is insufficient.
    pid = os.getpid()
    if (not sys.platform.startswith('linux') or threading.current_thread() is not threading.main_thread()
            or threading.get_native_id() != pid
            or sorted(p.name for p in Path('/proc/self/task').iterdir()) != [str(pid)]
            or int(_status(pid)['SigBlk'], 16) & (1 << (14-1))):
        raise ValueError('single native main thread with unblocked SIGALRM required')


@contextlib.contextmanager
def _deadline(seconds):
    _deadline_owner()
    if (not 0 < seconds <= 5 or signal.getitimer(signal.ITIMER_REAL) != (0.0, 0.0)
            or signal.getsignal(signal.SIGALRM) != signal.SIG_DFL):
        raise ValueError('exclusive finite main-thread handoff deadline required')
    prior = signal.getsignal(signal.SIGALRM)
    def expired(*_):
        raise TimeoutError('single initial-exec deadline')
    signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, seconds)
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, prior)


def _strings(memory, vector, expected):
    if not 0 < vector < 2**63 or len(expected) > 128:
        raise ValueError('finite pointer vector required')
    pointers = os.pread(memory, (len(expected)+1)*8, vector)
    if len(pointers) != (len(expected)+1)*8:
        raise ValueError('short argument vector')
    pointers = struct.unpack('<'+'Q'*(len(expected)+1), pointers)
    if pointers[-1] != 0:
        raise ValueError('unexpected argument vector suffix')
    for pointer, value in zip(pointers, expected):
        if not 0 < pointer < 2**63 or b'\0' in value or len(value) > 4096:
            raise ValueError('bounded immutable argument string required')
        if os.pread(memory, len(value)+1, pointer) != value+b'\0':
            raise ValueError('initial argument or environment changed')


def _verify_elf(pid, descriptor, expected):
    fd = os.open('/proc/'+str(pid)+'/fd/'+str(descriptor), os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    with os.fdopen(fd, 'rb') as source:
        before = os.fstat(source.fileno())
        if (not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= MAX_ELF_BYTES
                or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) !=
                   tuple(expected[k] for k in ('device', 'inode', 'bytes', 'mtimeNs', 'ctimeNs'))):
            raise ValueError('pinned initial ELF descriptor changed')
        digest = hashlib.sha256();count = 0
        for block in iter(lambda: source.read(65536), b''):
            count += len(block)
            if count > MAX_ELF_BYTES or count > before.st_size:
                raise ValueError('initial ELF exceeds fixed byte bound')
            digest.update(block)
        after = os.fstat(source.fileno())
    if (count != before.st_size or digest.hexdigest() != expected['sha256'] or any(getattr(before, k) != getattr(after, k)
            for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))):
        raise ValueError('initial ELF bytes changed')


def continue_initial(listener, birth, target, command, environment, audit, *, timeout=5):
    """Consume sole listener; at most one SEND, never service a second request.

    Caller must detach this FD from its cleanup set before calling, hold its
    real child/pidfd, forbid concurrent spawn/FD sharing during this handoff,
    and actually abort/wait its owned scope on every exception. A successful
    response is not proof of exec, target identity, journal or completion.
    """
    try:
        pid = birth['pid']
        audit.update(grantAttempted=False, continueSent=False, listenerClosed=False)
        native = Native();native.sizes()
        argv = [os.fsencode(value) for value in command]
        env = [os.fsencode(key)+b'='+os.fsencode(value) for key, value in environment.items()]
        if not argv or sum(map(len, argv)) > 32768 or sum(map(len, env)) > 65536:
            raise ValueError('finite prepared argv and environment required')
        if os.get_inheritable(listener):
            raise ValueError('listener must be CLOEXEC')
        with _deadline(timeout):
            message = Notification()
            native.ioctl(listener, 0xc0502100, message)
            audit['notification'] = dict(id=message.id, pid=message.pid, number=message.data.number,
                                         arch=message.data.arch, args=list(message.data.args))
            if (message.pid != pid or message.flags or message.data.arch != ARCH or message.data.number != 322
                    or message.data.args[0] != target['openedDescriptor'] or message.data.args[4] != AT_EMPTY_PATH):
                raise ValueError('only the owned initial native FDexec may be continued')
            _singleton(pid, birth, os.getpid(), installed=True)
            if os.stat('/proc/self/ns/pid').st_ino != os.stat('/proc/'+str(pid)+'/ns/pid').st_ino:
                raise ValueError('same private PID namespace required')
            memory = os.open('/proc/'+str(pid)+'/mem', os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            try:
                native.valid(listener, message.id)
                if not 0 < message.data.args[1] < 2**63 or os.pread(memory, 1, message.data.args[1]) != b'\0':
                    raise ValueError('empty initial FDexec pathname required')
                _strings(memory, message.data.args[2], argv)
                _strings(memory, message.data.args[3], env)
                _verify_elf(pid, target['openedDescriptor'], target)
                native.valid(listener, message.id)
                _singleton(pid, birth, os.getpid(), installed=True)
                response = Response(message.id, 0, 0, 1)
                native.valid(listener, message.id)
                audit['grantAttempted'] = True  # Irreversible even if SEND fails/interrupted.
                native.ioctl(listener, 0xc0182101, response)
                audit['continueSent'] = True
            finally:
                os.close(memory)
    finally:
        os.close(listener)
        audit['listenerClosed'] = True
