"""Final Windows image: actual native entry, private release hash, unchanged scan phases."""
from __future__ import annotations

from windows_native import clock_sample

ENTRY_SAMPLES = [clock_sample() for _ in range(32)]
ENTRY_SAMPLE = min(ENTRY_SAMPLES, key=lambda value: value['afterNs']-value['beforeNs'])

import argparse
import os
import sqlite3

from metadata_scan import ScanError
from native_scan_protocol import ClockFailure, ControlReader, emit, read_json
from native_scan_runtime import Worker, catalogue


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='mode', required=True)
    worker = sub.add_parser('worker')
    worker.add_argument('--config', required=True)
    for flag in ('scan-id', 'change-set-id', 'input', 'objects', 'events', 'appliedEvents', 'traversedObjects'):
        worker.add_argument('--'+flag, required=True)
    reader_parser = sub.add_parser('catalogue')
    for flag in ('approval', 'approval-sha', 'clock', 'output'):
        reader_parser.add_argument('--'+flag, required=True)
    args = parser.parse_args()
    if args.mode == 'catalogue':
        catalogue(args)
        return
    manifest, _ = read_json(os.environ['GUIZE_POC_MANIFEST_REF'], os.environ['GUIZE_POC_MANIFEST_SHA'])
    reader = ControlReader()
    release = reader.receive(manifest['reservationDeadline'])
    if set(release) != {'command', 'approvalRef', 'approvalSha256'} or release['command'] != 'release':
        raise ScanError('APPROVED_PRIVATE_PIPE_RELEASE_REQUIRED')
    os.environ.update(GUIZE_POC_APPROVAL_REF=release['approvalRef'], GUIZE_POC_APPROVAL_SHA=release['approvalSha256'])
    Worker(args, entry_sample=ENTRY_SAMPLE, entry_samples=ENTRY_SAMPLES, control_reader=reader).run()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as failure:
        value = dict(kind='runtime_failure', error=str(failure) if isinstance(failure, ScanError) else type(failure).__name__)
        if isinstance(failure, ClockFailure):
            value['clockObservation'] = failure.observation
        emit(value)
        raise SystemExit(1)
