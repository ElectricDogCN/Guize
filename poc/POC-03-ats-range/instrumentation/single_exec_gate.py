"""Dormant fixed-profile bootstrap; only a future reviewed caller may launch it.

Before installation this exact prefix reads code and control metadata only.
The caller must already exclude preload/audit and mutable image/code actors.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import select
import socket
import stat
import struct
import sys
import time
import types


def main():
    error_fd = None
    listener = None
    channel = None
    try:
        if len(sys.argv) != 9:
            raise ValueError('fixed gate argument count')
        executable, control, ready, error_fd, parent, transfer = map(int, sys.argv[1:7])
        command, policy_sha = json.loads(sys.argv[7]), sys.argv[8]
        descriptors = (executable, control, ready, error_fd, transfer)
        if (os.getuid() == 0 or os.getuid() != os.geteuid() or os.getppid() != parent
                or len(set(descriptors)) != 5 or min(descriptors) < 3
                or not re.fullmatch('[0-9a-f]{64}', policy_sha)
                or not isinstance(command, list) or not command
                or any(not isinstance(arg, str) or '\0' in arg for arg in command)
                or not os.path.isabs(command[0]) or os.environ.get('LD_PRELOAD') or os.environ.get('LD_AUDIT')
                or os.environ.get('LC_ALL') != 'C.UTF-8' or os.environ.get('PYTHONCOERCECLOCALE') != '0'):
            raise ValueError('fixed trusted gate inputs required')
        target = os.fstat(executable)
        if not stat.S_ISREG(target.st_mode) or target.st_mode & (stat.S_ISUID | stat.S_ISGID):
            raise ValueError('ordinary native ELF descriptor required')
        header = os.pread(executable, 20, 0)
        if (len(header) != 20 or header[:6] != b'\x7fELF\x02\x01'
                or struct.unpack_from('<H', header, 18)[0] != 62):
            raise ValueError('native x86_64 ELF required')
        for descriptor in (control, ready, error_fd):
            if not stat.S_ISFIFO(os.fstat(descriptor).st_mode):
                raise ValueError('private control pipe required')
        if not stat.S_ISSOCK(os.fstat(transfer).st_mode):
            raise ValueError('private listener socket required')
        for descriptor in descriptors:
            os.set_inheritable(descriptor, False)
        # Execute precisely the hashed source bytes, avoiding a second loader read.
        policy_path = Path(__file__).absolute().with_name('single_exec_filter.py')
        fd = os.open(policy_path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW | os.O_CLOEXEC)
        with os.fdopen(fd, 'rb') as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_size > 65536:
                raise ValueError('bounded fixed policy source required')
            source = stream.read(65537)
            after = os.fstat(stream.fileno())
        if (hashlib.sha256(source).hexdigest() != policy_sha or len(source) != before.st_size
                or any(getattr(before, key) != getattr(after, key)
                       for key in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))):
            raise ValueError('fixed policy source changed')
        policy = types.ModuleType('guize_poc003_fixed_single_exec')
        exec(compile(source, str(policy_path), 'exec'), policy.__dict__)
        channel = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET, fileno=transfer)
        policy.gate_signal_defaults()
        listener = policy.install_listener(parent)
        consumed, listener = listener, None
        policy.transfer_listener(channel, consumed)
        channel = None
        if os.write(ready, b'READY\n') != 6:
            raise ValueError('short fixed gate readiness')
        os.close(ready)
        deadline = time.monotonic()+5
        message = bytearray()
        while True:
            remaining = deadline-time.monotonic()
            if remaining <= 0 or not select.select([control], [], [], remaining)[0]:
                raise ValueError('missing bounded GO EOF')
            block = os.read(control, 2-len(message))
            if not block:
                if message != b'G':
                    raise ValueError('exact complete GO required')
                break
            message.extend(block)
            if len(message) > 1:
                raise ValueError('extra GO bytes')
        os.close(control)
        # The notification must be approved by the real parent before this can proceed.
        os.execve(executable, command, os.environ)
    except BaseException as error:
        if listener is not None:
            os.close(listener)
        if channel is not None:
            channel.close()
        if error_fd is not None:
            try:
                os.write(error_fd, ('ERROR errno='+str(getattr(error, 'errno', 0) or 0)+'\n').encode())
            except OSError:
                pass
    os._exit(71)


if __name__ == '__main__':
    main()
