"""Evaluate emitted BPF/ABI only. No prctl, seccomp, child, listener or media."""
import ctypes
import os
import struct
import unittest
from unittest.mock import patch
from instrumentation import single_exec_filter as policy


def evaluate(number, *, arch=policy.ARCH, args=()):
    data = bytearray(64)
    struct.pack_into('<II', data, 0, number & 0xffffffff, arch)
    for index, value in enumerate(args):
        struct.pack_into('<Q', data, 16+8*index, value)
    instructions = policy.fixed_filter()
    pc, accumulator = 0, 0
    for _ in range(100):
        code, yes, no, value = instructions[pc]
        pc += 1
        if code == 0x20:
            if yes or no or value % 4 or not 0 <= value <= len(data)-4:
                raise AssertionError('invalid absolute word load')
            accumulator = struct.unpack_from('<I', data, value)[0]
        elif code == 0x15:
            pc += yes if accumulator == value else no
        elif code == 0x35:
            pc += yes if accumulator >= value else no
        elif code == 0x45:
            pc += yes if accumulator & value else no
        elif code == 0x06:
            if yes or no:
                raise AssertionError('invalid return encoding')
            return value
        else:
            raise AssertionError('unexpected BPF instruction')
        if not 0 <= pc < len(instructions):
            raise AssertionError('BPF branch escaped fixed program')
    raise AssertionError('BPF evaluation did not terminate')


class FixedSingleExecTests(unittest.TestCase):
    def test_deadline_rejects_masked_alarm_extra_native_thread_and_false_main_label(self):
        owner = object()
        for tasks, blocked, native_id, accepted in [(['700'], 0, 700, True),
                (['700', '701'], 0, 700, False), (['700'], 1 << 13, 700, False),
                (['700'], 0, 701, False), ([], 0, 700, False)]:
            with self.subTest(tasks=tasks, blocked=blocked, native_id=native_id):
                with patch.object(policy.sys, 'platform', 'linux'), patch.object(policy.os, 'getpid', return_value=700), \
                     patch.object(policy.threading, 'current_thread', return_value=owner), \
                     patch.object(policy.threading, 'main_thread', return_value=owner), \
                     patch.object(policy.threading, 'get_native_id', return_value=native_id), \
                     patch.object(policy.Path, 'iterdir', return_value=iter(policy.Path(n) for n in tasks)), \
                     patch.object(policy, '_status', return_value={'SigBlk': format(blocked, 'x')}):
                    if accepted:
                        policy._deadline_owner()
                    else:
                        with self.assertRaisesRegex(ValueError, 'single native main thread'):
                            policy._deadline_owner()

    def test_invalid_birth_still_consumes_descriptor_before_any_native_call(self):
        reader, writer = os.pipe()
        audit = {}
        try:
            with patch.object(policy, 'Native', side_effect=AssertionError('native call not allowed')):
                with self.assertRaises(KeyError):
                    policy.continue_initial(reader, {}, {}, [], {}, audit)
            self.assertTrue(audit['listenerClosed'])
            with self.assertRaises(OSError):
                os.fstat(reader)
        finally:
            for descriptor in (reader, writer):
                try:
                    os.close(descriptor)
                except OSError:
                    pass

    def test_compat_x32_and_invalid_syscall_routes_cannot_bypass_profile(self):
        for arch in (0, 0x40000003, 0x40000028, 0xc00000b7):
            for call in (0, 56, 59, 157, 317, 322):
                self.assertEqual(evaluate(call, arch=arch), policy.KILL)
        for call in (0, 56, 59, 157, 317, 322):
            self.assertEqual(evaluate(call | 0x40000000), policy.KILL)
        self.assertEqual(evaluate(-1), policy.KILL)

    def test_process_creation_and_filter_replacement_are_rejected(self):
        for flags in (0, 17, 0x100, 0x800, 0x900, 1 << 40):
            self.assertEqual(evaluate(56, args=(flags,)), policy.DENY)
        for call in (57, 58, 317):
            for argument in (0, 1, 2, 3, 8, 0xffffffff):
                self.assertEqual(evaluate(call, args=(argument,)), policy.DENY)
        for option in (22, (1 << 32) | 22):
            self.assertEqual(evaluate(157, args=(option,)), policy.DENY)

    def test_thread_flag_and_explicit_clone3_unavailability(self):
        for flags in (0x10000, 0x10900, 0x3d0f00, (1 << 40) | 0x10000):
            self.assertEqual(evaluate(56, args=(flags,)), policy.ALLOW)
        self.assertEqual(evaluate(435, args=(0xffffffffffffffff,)), policy.UNAVAILABLE)
        # This is BPF semantics only, not a claim that libc pthread actually works.

    def test_only_exec_calls_notify_and_unrelated_syscalls_keep_their_semantics(self):
        for call in range(1024):
            if call in (59, 322):
                expected = policy.NOTIFY
            elif call in (56, 57, 58, 317):
                expected = policy.DENY
            elif call == 435:
                expected = policy.UNAVAILABLE
            else:
                expected = policy.ALLOW
            self.assertEqual(evaluate(call), expected, call)
        for option in (0, 1, 15, 38, 39):
            self.assertEqual(evaluate(157, args=(option,)), policy.ALLOW)

    def test_native_uapi_structure_sizes_offsets_and_filter_bytes(self):
        self.assertEqual((policy.DENY, policy.UNAVAILABLE), (0x00050001, 0x00050026))
        self.assertEqual((ctypes.sizeof(policy.Filter), ctypes.sizeof(policy.Data),
                          ctypes.sizeof(policy.Notification), ctypes.sizeof(policy.Response)), (8, 64, 80, 24))
        self.assertEqual((policy.Data.arch.offset, policy.Data.args.offset, policy.Notification.data.offset), (4, 16, 16))
        native = b''.join(bytes(policy.Filter(*row)) for row in policy.fixed_filter())
        packed = b''.join(struct.pack('<HBBI', *row) for row in policy.fixed_filter())
        self.assertEqual(native, packed)
        self.assertEqual(len(native), 29*8)


if __name__ == '__main__':
    unittest.main()
