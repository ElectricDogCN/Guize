"""Actual final-image Windows reservation and approval-gated initial-thread resume."""
from __future__ import annotations

import os
import queue
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from metadata_scan import ScanError
from native_scan_control import NativeRun, manifest_for
from native_scan_protocol import (Clock, check_sources, read_json, scoped, utc, write_json)
from windows_native import SuspendedProcess, clock_sample, identity


def windows_manifest_for(config_ref, cfg, reservation_deadline, *, identity_ref):
    runtime = Path(__file__).with_name('windows_scan_runtime.py').resolve()
    result = manifest_for(config_ref, cfg, reservation_deadline, runtime_script=runtime)
    result['processIdentityRef'] = identity_ref
    result['platform'] = 'windows_suspended_final_image_v1'
    return result


class WindowsNativeRun(NativeRun):
    def __init__(self, manifest_ref, manifest_sha, *, trace_ref, stderr_ref):
        if os.name != 'nt':
            raise ScanError('WINDOWS_NATIVE_RUNTIME_REQUIRED')
        self.manifest_ref, self.manifest_sha = str(manifest_ref), manifest_sha
        self.manifest, _ = read_json(manifest_ref, manifest_sha)
        check_sources(self.manifest)
        if self.manifest.get('platform') != 'windows_suspended_final_image_v1':
            raise ScanError('EXPLICIT_WINDOWS_SUSPENDED_MANIFEST_REQUIRED')
        remaining = (utc(self.manifest['reservationDeadline'])-datetime.now(timezone.utc)).total_seconds()
        if not 0 < remaining <= 86400:
            raise ScanError('FINITE_FUTURE_RESERVATION_REQUIRED')
        self.runtime_script = Path(__file__).with_name('windows_scan_runtime.py').resolve()
        self.child_environment = {**os.environ, 'PYTHONIOENCODING': 'utf-8', 'PYTHONUTF8': '1',
            'PYTHONDONTWRITEBYTECODE': '1', 'GUIZE_POC_MANIFEST_REF': self.manifest_ref,
            'GUIZE_POC_MANIFEST_SHA': self.manifest_sha}
        self.trace = Path(trace_ref).open('xb')
        self.stderr = None
        self.process = self.reader = None
        self._closed = False
        self.messages, self.phases = queue.Queue(), {}
        self.clock = self.ready = self.approval = self.cfg = None
        self.memory_samples, self.post_receipt = [], None
        self._reservation_done, self._state_lock = threading.Event(), threading.Lock()
        try:
            self.stderr = Path(stderr_ref).open('xb')
            self.process = SuspendedProcess(self.manifest['argv'], cwd=Path.cwd(), stderr=self.stderr, env=self.child_environment)
            sample = clock_sample()
            seconds, nanos = divmod(sample['wallNs'], 1000000000)
            at = (datetime.fromtimestamp(seconds, timezone.utc)+timedelta(microseconds=nanos//1000)).isoformat().replace('+00:00', 'Z')
            self.reservation = dict(kind='reservation_ready', identity=self.process.reservation_identity,
                reservedAt=at, nativeClockSample=sample, manifestSha256=self.manifest_sha,
                finalArgv=self.manifest['argv'], initialThreadId=self.process.thread_id,
                semantics='final OS image with initial thread suspended; no worker Python code has executed')
            self.identity_sha = write_json(self.manifest['processIdentityRef'], self.reservation['identity'])
            self.reader = threading.Thread(target=self._read, daemon=True)
            self.reader.start()
            self.expiry = threading.Thread(target=self._expire, args=(remaining,), daemon=True)
            self.expiry.start()
        except BaseException:
            self.close()
            raise

    def _expire(self, remaining):
        if self._reservation_done.wait(remaining):
            return
        with self._state_lock:
            if not self._reservation_done.is_set():
                self.process.terminate()
                code = self.process.wait(timeout=5)
                write_json(self.manifest_ref+'.reservation-expired.json', dict(kind='expired_suspended_reservation',
                    reservation=self.reservation, actualWaitReturnCode=code, observedAt=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                    resumed=False, qualificationAccepted=False))
                self._reservation_done.set()

    def release(self, approval_ref, approval_sha):
        try:
            with self._state_lock:
                if self._reservation_done.is_set() or datetime.now(timezone.utc) >= utc(self.manifest['reservationDeadline']):
                    raise ScanError('WINDOWS_RESERVATION_EXPIRED_OR_ALREADY_RELEASED')
                from native_scan_runtime import release_data
                _, approval, cfg, actual = release_data(self.manifest_ref, self.manifest_sha,
                    str(approval_ref), approval_sha, after_exec=None)
                if (actual != self.reservation['identity'] or approval['reservationAt'] != self.reservation['reservedAt']
                        or identity(self.process.pid) != self.reservation['identity']):
                    raise ScanError('EXACT_SUSPENDED_RESERVATION_REQUIRED')
                self.approval_ref, self.approval_sha = str(approval_ref), approval_sha
                self.approval, self.cfg = approval, cfg
                # The private inherited pipe carries the approved hash. No writable
                # environment or guessed future approval hash is substituted.
                self.send(dict(command='release', approvalRef=str(approval_ref), approvalSha256=approval_sha))
                resume = self.process.resume()
                self.handoff = dict(kind='suspended_image_resumed', **resume, manifestSha256=self.manifest_sha,
                    approvalSha256=approval_sha, finalArgv=self.manifest['argv'],
                    semantics='actual ResumeThread result, not the worker entry marker')
                self._reservation_done.set()
            self.ready = self.expect('scanner_ready')
            if (self.ready['identity'] != self.reservation['identity'] or self.ready['argv'] != self.manifest['argv']
                    or self.ready['processStart']['processId'] != self.process.pid):
                raise ScanError('ACTUAL_WINDOWS_IMAGE_ENTRY_MISMATCH')
            self.clock = Clock(self.ready['calibration'])
            write_json(scoped(self.cfg['artifactRoot'], self.cfg['readyReceipt']), self.ready)
        except BaseException:
            self.close()
            raise

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._reservation_done.set()
        if self.process is not None:
            try:
                if self.reader is not None:
                    super().close()
                else:
                    if self.process.poll() is None:
                        self.process.terminate()
                    self.process.wait(timeout=5)
            finally:
                self.process.close_handles()
        for stream in (self.trace, self.stderr):
            if stream is not None and not stream.closed:
                stream.close()
