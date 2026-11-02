"""Owned Windows processes, suspended images, QPC/UTC and native working-set counters."""
from __future__ import annotations

import base64
import ctypes as c
import hashlib
import json
import math
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from metadata_scan import file_sha256


class WindowsNativeError(ValueError):
    pass


U32, I32, U64, I64, PTR = c.c_uint32, c.c_int32, c.c_uint64, c.c_int64, c.c_void_p


class FileTime(c.Structure):
    _fields_ = [('low', U32), ('high', U32)]
    def integer(self):
        return self.low | self.high << 32


class UnicodeString(c.Structure):
    _fields_ = [('length', c.c_uint16), ('maximumLength', c.c_uint16), ('buffer', PTR)]


class MemoryCounters(c.Structure):
    _fields_ = [('cb', U32), ('PageFaultCount', U32)] + [(key, c.c_size_t) for key in
        ('PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage',
         'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage')]


class BasicJobLimits(c.Structure):
    _fields_ = [('PerProcessUserTimeLimit', I64), ('PerJobUserTimeLimit', I64), ('LimitFlags', U32),
               ('MinimumWorkingSetSize', c.c_size_t), ('MaximumWorkingSetSize', c.c_size_t),
               ('ActiveProcessLimit', U32), ('Affinity', c.c_size_t), ('PriorityClass', U32), ('SchedulingClass', U32)]


class JobLimits(c.Structure):
    _fields_ = [('BasicLimitInformation', BasicJobLimits), ('IoInfo', U64 * 6),
               ('ProcessMemoryLimit', c.c_size_t), ('JobMemoryLimit', c.c_size_t),
               ('PeakProcessMemoryUsed', c.c_size_t), ('PeakJobMemoryUsed', c.c_size_t)]


class StartupInfo(c.Structure):
    _fields_ = [('cb', U32), ('lpReserved', c.c_wchar_p), ('lpDesktop', c.c_wchar_p),
        ('lpTitle', c.c_wchar_p)] + [(name, U32) for name in
        ('dwX', 'dwY', 'dwXSize', 'dwYSize', 'dwXCountChars', 'dwYCountChars', 'dwFillAttribute', 'dwFlags')] + [
        ('wShowWindow', c.c_uint16), ('cbReserved2', c.c_uint16), ('lpReserved2', PTR),
        ('hStdInput', PTR), ('hStdOutput', PTR), ('hStdError', PTR)]


class StartupInfoEx(c.Structure):
    _fields_ = [('StartupInfo', StartupInfo), ('lpAttributeList', PTR)]


class ProcessInformation(c.Structure):
    _fields_ = [('hProcess', PTR), ('hThread', PTR), ('dwProcessId', U32), ('dwThreadId', U32)]


_apis = None
def api():
    global _apis
    if os.name != 'nt':
        raise WindowsNativeError('WINDOWS_NATIVE_REQUIRED')
    if _apis is None:
        libraries = {key: c.WinDLL(key, use_last_error=True) for key in ('kernel32', 'advapi32', 'ntdll', 'shell32', 'psapi')}
        signatures = {
            'OpenProcess': ('kernel32', PTR, [U32, I32, U32]),
            'CloseHandle': ('kernel32', I32, [PTR]),
            'GetProcessTimes': ('kernel32', I32, [PTR] + [c.POINTER(FileTime)] * 4),
            'QueryFullProcessImageNameW': ('kernel32', I32, [PTR, U32, c.c_wchar_p, c.POINTER(U32)]),
            'GetCommandLineW': ('kernel32', c.c_wchar_p, []),
            'QueryPerformanceCounter': ('kernel32', I32, [c.POINTER(I64)]),
            'QueryPerformanceFrequency': ('kernel32', I32, [c.POINTER(I64)]),
            'GetSystemTimePreciseAsFileTime': ('kernel32', None, [c.POINTER(FileTime)]),
            'WaitForSingleObject': ('kernel32', U32, [PTR, U32]),
            'GetExitCodeProcess': ('kernel32', I32, [PTR, c.POINTER(U32)]),
            'TerminateProcess': ('kernel32', I32, [PTR, U32]),
            'ResumeThread': ('kernel32', U32, [PTR]),
            'CreateJobObjectW': ('kernel32', PTR, [PTR, c.c_wchar_p]),
            'SetInformationJobObject': ('kernel32', I32, [PTR, I32, PTR, U32]),
            'InitializeProcThreadAttributeList': ('kernel32', I32, [PTR, U32, U32, c.POINTER(c.c_size_t)]),
            'UpdateProcThreadAttribute': ('kernel32', I32, [PTR, U32, c.c_size_t, PTR, c.c_size_t, PTR, PTR]),
            'DeleteProcThreadAttributeList': ('kernel32', None, [PTR]),
            'CreateProcessW': ('kernel32', I32, [c.c_wchar_p, c.c_wchar_p, PTR, PTR, I32, U32,
                PTR, c.c_wchar_p, c.POINTER(StartupInfoEx), c.POINTER(ProcessInformation)]),
            'SetHandleInformation': ('kernel32', I32, [PTR, U32, U32]),
            'LocalFree': ('kernel32', PTR, [PTR]),
            'OpenProcessToken': ('advapi32', I32, [PTR, U32, c.POINTER(PTR)]),
            'GetTokenInformation': ('advapi32', I32, [PTR, I32, PTR, U32, c.POINTER(U32)]),
            'ConvertSidToStringSidW': ('advapi32', I32, [PTR, c.POINTER(c.c_wchar_p)]),
            'NtQueryInformationProcess': ('ntdll', I32, [PTR, I32, PTR, U32, c.POINTER(U32)]),
            'CommandLineToArgvW': ('shell32', c.POINTER(c.c_wchar_p), [c.c_wchar_p, c.POINTER(I32)]),
            'GetProcessMemoryInfo': ('psapi', I32, [PTR, c.POINTER(MemoryCounters), U32]),
        }
        bound = {}
        for name, (library, result, arguments) in signatures.items():
            function = getattr(libraries[library], name)
            function.restype, function.argtypes = result, arguments
            bound[name] = function
        frequency = I64()
        if not bound['QueryPerformanceFrequency'](c.byref(frequency)) or frequency.value <= 0:
            raise WindowsNativeError('NATIVE_QPC_FREQUENCY_REQUIRED')
        bound['frequency'] = frequency.value
        _apis = bound
    return _apis


def require(ok, code):
    if not ok:
        raise WindowsNativeError(code)


def close_handle(handle):
    if handle:
        require(api()['CloseHandle'](handle), 'NATIVE_HANDLE_CLOSE_FAILED')


def argv_for(command_line):
    require(isinstance(command_line, str) and 0 < len(command_line) <= 32767, 'BOUNDED_NATIVE_COMMAND_LINE_REQUIRED')
    count = I32()
    parts = api()['CommandLineToArgvW'](command_line, c.byref(count))
    require(bool(parts) and 1 <= count.value <= 512, 'NATIVE_COMMAND_LINE_PARSE_FAILED')
    try:
        return [parts[index] for index in range(count.value)]
    finally:
        api()['LocalFree'](c.cast(parts, PTR))


def actual_argv():
    return argv_for(api()['GetCommandLineW']())


def command_line_for(handle):
    size = U32()
    api()['NtQueryInformationProcess'](handle, 60, None, 0, c.byref(size))
    require(c.sizeof(UnicodeString) <= size.value <= 131072, 'BOUNDED_OS_COMMAND_LINE_REQUIRED')
    buffer = c.create_string_buffer(size.value)
    status = api()['NtQueryInformationProcess'](handle, 60, buffer, size, c.byref(size))
    require(status >= 0, 'OS_COMMAND_LINE_QUERY_FAILED')
    value = UnicodeString.from_buffer(buffer)
    address = c.addressof(buffer)
    require(value.length % 2 == 0 and value.buffer is not None and
            address <= value.buffer <= address + len(buffer) - value.length, 'OS_COMMAND_LINE_BUFFER_INVALID')
    return c.wstring_at(value.buffer, value.length // 2)


def owner_sid(handle):
    token = PTR()
    require(api()['OpenProcessToken'](handle, 8, c.byref(token)), 'NATIVE_OWNER_TOKEN_REQUIRED')
    try:
        size = U32()
        api()['GetTokenInformation'](token, 1, None, 0, c.byref(size))
        require(c.sizeof(PTR) <= size.value <= 4096, 'BOUNDED_OWNER_TOKEN_REQUIRED')
        buffer = c.create_string_buffer(size.value)
        require(api()['GetTokenInformation'](token, 1, buffer, size, c.byref(size)), 'NATIVE_OWNER_QUERY_FAILED')
        sid = PTR.from_buffer(buffer)
        text = c.c_wchar_p()
        require(api()['ConvertSidToStringSidW'](sid, c.byref(text)), 'NATIVE_OWNER_SID_REQUIRED')
        try:
            return text.value
        finally:
            api()['LocalFree'](c.cast(text, PTR))
    finally:
        close_handle(token)


def process_creation(handle):
    values = [FileTime() for _ in range(4)]
    require(api()['GetProcessTimes'](handle, *(c.byref(value) for value in values)), 'NATIVE_PROCESS_TIMES_REQUIRED')
    return values[0].integer()


def identity(pid):
    require(type(pid) is int and 1 <= pid <= 2**32-1, 'INVALID_NATIVE_PROCESS_ID')
    handle = api()['OpenProcess'](0x1000 | 0x100000, False, pid)
    require(handle, 'OWNED_LIVE_NATIVE_PROCESS_REQUIRED')
    try:
        require(api()['WaitForSingleObject'](handle, 0) == 258, 'OWNED_LIVE_NATIVE_PROCESS_REQUIRED')
        created = process_creation(handle)
        owner = owner_sid(handle)
        require(owner == owner_sid(PTR(-1)), 'OWNED_NATIVE_PROCESS_REQUIRED')
        buffer, length = c.create_unicode_buffer(32768), U32(32768)
        require(api()['QueryFullProcessImageNameW'](handle, 0, buffer, c.byref(length)), 'NATIVE_EXECUTABLE_REQUIRED')
        executable = Path(buffer.value).resolve(strict=True)
        command = command_line_for(handle)
        argv = argv_for(command)
        require(process_creation(handle) == created and api()['WaitForSingleObject'](handle, 0) == 258,
                'NATIVE_PROCESS_CHANGED_DURING_IDENTITY')
        digest = file_sha256(executable)
        return dict(nativeProcessId=pid, creationTime100ns=created, ownerSid=owner, executable=str(executable),
                    executableSha256=digest, cmdlineSha256=hashlib.sha256(b'\0'.join(os.fsencode(part) for part in argv)+b'\0').hexdigest(),
                    nativeCommandLine=command, nativeCommandLineSha256=hashlib.sha256(command.encode('utf-16le')).hexdigest())
    finally:
        close_handle(handle)


def qpc_ns():
    value = I64()
    require(api()['QueryPerformanceCounter'](c.byref(value)), 'NATIVE_QPC_READ_FAILED')
    return value.value * 1000000000 // api()['frequency']


def clock_sample():
    functions = api()
    before, after, wall = I64(), I64(), FileTime()
    require(functions['QueryPerformanceCounter'](c.byref(before)), 'NATIVE_QPC_READ_FAILED')
    functions['GetSystemTimePreciseAsFileTime'](c.byref(wall))
    require(functions['QueryPerformanceCounter'](c.byref(after)), 'NATIVE_QPC_READ_FAILED')
    frequency = functions['frequency']
    return dict(beforeNs=before.value*1000000000//frequency, afterNs=after.value*1000000000//frequency,
                wallNs=(wall.integer()-116444736000000000)*100, beforeQpc=before.value, afterQpc=after.value,
                qpcFrequency=frequency, utcFileTime100ns=wall.integer())


def read_counter(pid):
    handle = api()['OpenProcess'](0x410, False, pid)
    require(handle, 'NATIVE_COUNTER_PROCESS_REQUIRED')
    try:
        values = MemoryCounters()
        values.cb = c.sizeof(values)
        require(api()['GetProcessMemoryInfo'](handle, c.byref(values), c.sizeof(values)), 'NATIVE_WORKING_SET_COUNTER_REQUIRED')
        require(0 <= values.WorkingSetSize <= values.PeakWorkingSetSize <= 2**60, 'NATIVE_COUNTER_RANGE_MISMATCH')
        return dict(ProcessId=pid, PeakWorkingSetSize=values.PeakWorkingSetSize, WorkingSetSize=values.WorkingSetSize), bytes(values)
    finally:
        close_handle(handle)


def collect(pid, output, *, expected):
    require(pid != os.getpid(), 'INDEPENDENT_COLLECTOR_REQUIRED')
    before = identity(pid)
    require(before == expected, 'NATIVE_PROCESS_BINDING_MISMATCH')
    values, raw_struct = read_counter(pid)
    sample = clock_sample()
    require(identity(pid) == before, 'NATIVE_PROCESS_CHANGED_DURING_CAPTURE')
    raw = (json.dumps(values, sort_keys=True, separators=(',', ':'))+'\n').encode()
    with Path(output).open('xb') as destination:
        destination.write(raw)
    seconds, nanos = divmod(sample['wallNs'], 1000000000)
    observed = (datetime.fromtimestamp(seconds, timezone.utc)+timedelta(microseconds=nanos//1000)).isoformat().replace('+00:00', 'Z')
    return dict(identity=before, observedAt=observed, collectorProcessId=os.getpid(),
                counterFormat='windows_process_memory_counters',
                counters=dict(nativeProcessId=pid, peakResidentBytes=values['PeakWorkingSetSize'], residentBytes=values['WorkingSetSize']),
                counterRef=str(output), byteCount=len(raw), sha256='sha256:'+hashlib.sha256(raw).hexdigest(),
                nativeCounterStructBase64=base64.b64encode(raw_struct).decode(),
                nativeCounterStructSha256=hashlib.sha256(raw_struct).hexdigest(), nativeClockSample=sample,
                toolBuild='sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), commandArgs=actual_argv(), exitCode=0)


def create_suspended_image(argv, *, cwd, standard_handles, job_handle, env):
    """Assign the Job as part of native creation, before any parent return gap."""
    functions = api()
    size = c.c_size_t()
    functions['InitializeProcThreadAttributeList'](None, 2, 0, c.byref(size))
    require(0 < size.value <= 65536, 'BOUNDED_NATIVE_CREATION_ATTRIBUTES_REQUIRED')
    attributes = c.create_string_buffer(size.value)
    require(functions['InitializeProcThreadAttributeList'](attributes, 2, 0, c.byref(size)),
            'NATIVE_CREATION_ATTRIBUTES_REQUIRED')
    try:
        inherited = (PTR * 3)(*standard_handles)
        jobs = (PTR * 1)(job_handle)
        # ProcThreadAttributeValue(number, FALSE, TRUE, FALSE): HANDLE_LIST=2,
        # JOB_LIST=13. Both arrays stay alive until the attribute list is deleted.
        for attribute, values in ((0x00020002, inherited), (0x0002000D, jobs)):
            require(functions['UpdateProcThreadAttribute'](attributes, 0, attribute, values,
                    c.sizeof(values), None, None), 'ATOMIC_JOB_AND_HANDLE_ATTRIBUTES_REQUIRED')
        startup = StartupInfoEx()
        startup.StartupInfo.cb = c.sizeof(startup)
        startup.StartupInfo.dwFlags = 0x100  # STARTF_USESTDHANDLES
        startup.StartupInfo.hStdInput, startup.StartupInfo.hStdOutput, startup.StartupInfo.hStdError = standard_handles
        startup.lpAttributeList = c.cast(attributes, PTR)
        environment = None
        if env is not None:
            require(all(isinstance(key, str) and key and '\0' not in key and '=' not in key[1:]
                    and isinstance(value, str) and '\0' not in value for key, value in env.items()),
                    'VALID_UNICODE_ENVIRONMENT_REQUIRED')
            block = '\0'.join(key+'='+value for key, value in sorted(env.items(), key=lambda item: item[0].upper()))+'\0\0'
            environment = c.create_unicode_buffer(block)
        command = c.create_unicode_buffer(subprocess.list2cmdline(argv))
        information = ProcessInformation()
        flags = 0x00000004 | 0x08000000 | 0x00080000 | 0x00000400
        require(functions['CreateProcessW'](argv[0], command, None, None, True, flags,
                environment, str(cwd), c.byref(startup), c.byref(information)), 'ATOMIC_OWNED_SUSPENDED_IMAGE_REQUIRED')
        return information.hProcess, information.hThread, information.dwProcessId, information.dwThreadId
    finally:
        functions['DeleteProcThreadAttributeList'](attributes)


class SuspendedProcess:
    """The final image, owned by a kill-on-close job before any thread is resumed."""
    def __init__(self, argv, *, cwd, stderr, env=None):
        api()
        import _winapi
        import msvcrt
        self.pid = self.thread_id = None
        self.process_handle = self.thread_handle = self.job_handle = None
        self.stdin = self.stdout = None
        self.returncode = None
        self.resumed = False
        temporary = []
        try:
            self.job_handle = api()['CreateJobObjectW'](None, None)
            require(self.job_handle, 'NATIVE_JOB_REQUIRED')
            limits = JobLimits()
            limits.BasicLimitInformation.LimitFlags = 0x2000
            require(api()['SetInformationJobObject'](self.job_handle, 9, c.byref(limits), c.sizeof(limits)), 'KILL_ON_PARENT_EXIT_REQUIRED')
            input_read, input_write = _winapi.CreatePipe(None, 0)
            temporary += [input_read, input_write]
            output_read, output_write = _winapi.CreatePipe(None, 0)
            temporary += [output_read, output_write]
            current = _winapi.GetCurrentProcess()
            error_write = _winapi.DuplicateHandle(current, msvcrt.get_osfhandle(stderr.fileno()), current, 0, True, 2)
            temporary.append(error_write)
            for handle in (input_read, output_write):
                require(api()['SetHandleInformation'](handle, 1, 1), 'NATIVE_PIPE_INHERITANCE_REQUIRED')
            command = subprocess.list2cmdline(argv)
            self.process_handle, self.thread_handle, self.pid, self.thread_id = create_suspended_image(
                argv, cwd=cwd, standard_handles=(input_read, output_write, error_write), job_handle=self.job_handle, env=env)
            self.reservation_identity = identity(self.pid)
            require(self.reservation_identity['nativeCommandLine'] == command and argv_for(command) == argv,
                    'EXACT_SUSPENDED_IMAGE_COMMAND_REQUIRED')
            self.stdin = os.fdopen(msvcrt.open_osfhandle(input_write, os.O_WRONLY | os.O_BINARY), 'wb', buffering=0)
            temporary.remove(input_write)
            self.stdout = os.fdopen(msvcrt.open_osfhandle(output_read, os.O_RDONLY | os.O_BINARY), 'rb', buffering=0)
            temporary.remove(output_read)
        except BaseException:
            if self.process_handle:
                self.terminate()
                self.wait(timeout=5)
            self.close_handles()
            raise
        finally:
            for handle in temporary:
                close_handle(handle)

    def resume(self):
        require(not self.resumed and identity(self.pid) == self.reservation_identity, 'EXACT_UNRESUMED_PROCESS_REQUIRED')
        before = clock_sample()
        result = api()['ResumeThread'](self.thread_handle)
        after = clock_sample()
        require(result == 1, 'EXACT_INITIAL_THREAD_RESUME_REQUIRED')
        self.resumed = True
        close_handle(self.thread_handle)
        self.thread_handle = None
        return dict(previousSuspendCount=result, threadId=self.thread_id, processId=self.pid,
                    resumeCallBefore=before, resumeCallAfter=after)

    def poll(self):
        if self.returncode is None and api()['WaitForSingleObject'](self.process_handle, 0) == 0:
            value = U32()
            require(api()['GetExitCodeProcess'](self.process_handle, c.byref(value)), 'ACTUAL_NATIVE_EXIT_CODE_REQUIRED')
            self.returncode = value.value
        return self.returncode

    def wait(self, timeout=None):
        if self.returncode is not None:
            return self.returncode
        milliseconds = 0xffffffff if timeout is None else max(0, min(0xfffffffe, math.ceil(timeout*1000)))
        result = api()['WaitForSingleObject'](self.process_handle, milliseconds)
        if result == 258:
            raise subprocess.TimeoutExpired('owned suspended image', timeout)
        require(result == 0, 'NATIVE_PROCESS_WAIT_FAILED')
        return self.poll()

    def terminate(self):
        if self.poll() is None:
            require(api()['TerminateProcess'](self.process_handle, 1), 'OWNED_PROCESS_TERMINATION_FAILED')

    kill = terminate

    def close_handles(self):
        for key in ('thread_handle', 'process_handle', 'job_handle'):
            value = getattr(self, key, None)
            if value:
                close_handle(value)
                setattr(self, key, None)


def main():
    import argparse
    from native_scan_protocol import read_json
    parser = argparse.ArgumentParser()
    parser.add_argument('--expected', required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--pid', type=int, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    expected, _ = read_json(args.expected, args.expected_sha256)
    print(json.dumps(collect(args.pid, args.output, expected=expected), sort_keys=True))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, AttributeError) as failure:
        import sys
        print(str(failure) if isinstance(failure, WindowsNativeError) else type(failure).__name__, file=sys.stderr)
        raise SystemExit(1)
