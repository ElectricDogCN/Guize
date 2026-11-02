"""UTC serialization must be consumable by the frozen evidence acceptor."""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from native_scan_protocol import Clock
import test_controlled_source_run as source_fixtures


spec = importlib.util.spec_from_file_location(
    'frozen_utc_evidence_acceptor', Path(__file__).resolve().parents[2]/'specs/poc/check_program.py')
acceptor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptor)


class UTCEvidenceTests(unittest.TestCase):
    def assert_accepted_utc(self, value):
        self.assertTrue(acceptor.valid_utc_timestamp(value), repr(value))
        self.assertIsNotNone(acceptor.utc(value))

    def test_native_clock_marker_is_accepted_without_changing_its_mapping(self):
        clock = Clock()
        event = clock.marker('utc_serialization_regression')
        self.assert_accepted_utc(event['observedAt'])
        self.assertEqual(event['observedAt'], clock.mapped_utc(event['monotonicNs']))

    def test_actual_listing_dav_and_gateway_observations_use_accepted_utc(self):
        fixture = source_fixtures.SourceTests('test_actual_forwarded_range_and_negative_bytes_and_missing_validator_are_unchanged')
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        gateway, listing, dav, _ = fixture.gateway()
        observed = listing.observe(per_page=2)
        for key in ('startedAt', 'endedAt'):
            self.assert_accepted_utc(observed[key])
        row = next(row for row in fixture.rows if row['kind'] == 'file' and row['fileSizeBytes'] == 4096)
        observed = dav.observe('GET', row['path'], maximum_bytes=65536)
        for key in ('startedAt', 'endedAt'):
            self.assert_accepted_utc(observed[key])
        gateway.close()
        for event in gateway.events:
            self.assert_accepted_utc(event['startedAt'])
            self.assert_accepted_utc(event['finishedAt'])

    def test_independent_native_memory_receipt_uses_accepted_utc(self):
        if os.name == 'nt':
            from windows_native import collect, identity
        else:
            from native_memory import collect, native_identity as identity
        with tempfile.TemporaryDirectory() as temp:
            child = subprocess.Popen([sys.executable, '-B', '-c', 'import time;time.sleep(10)'],
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                receipt = collect(child.pid, Path(temp)/'actual-counter', expected=identity(child.pid))
                self.assertEqual(receipt['counters']['nativeProcessId'], child.pid)
                self.assert_accepted_utc(receipt['observedAt'])
            finally:
                if child.poll() is None:
                    child.terminate()
                child.wait(timeout=5)


if __name__ == '__main__':
    unittest.main()
