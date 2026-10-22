"""Retain rejected native clock evidence and the actual child failure cause."""
import copy
import queue
import unittest
from unittest.mock import patch

from metadata_scan import ScanError
from native_scan_control import NativeRun
from native_scan_protocol import Clock


class ClockEvidenceTests(unittest.TestCase):
    def clock(self):
        return Clock(dict(samples=[dict(beforeNs=1000000000,afterNs=1000000100,wallNs=2000000000000000000)],chosen=0))

    def test_rejected_clock_change_keeps_original_pair_calibration_and_deviation(self):
        clock=self.clock()
        with self.assertRaisesRegex(ScanError,'WALL_CLOCK_CHANGED') as failure:
            clock.marker('phase_start',tick=clock.mono+10000000,wall=clock.wall+12000001)
        raw=failure.exception.observation
        self.assertEqual(raw['monotonicNs'],clock.mono+10000000)
        self.assertEqual(raw['directWallNs'],clock.wall+12000001)
        self.assertEqual(raw['expectedWallNs'],clock.wall+10000000)
        self.assertEqual(raw['residualNs'],2000001)
        self.assertEqual(raw['calibration'],clock.calibration)
        self.assertFalse(raw['accepted'])

    def test_marker_selects_bounded_bracket_and_keeps_every_actual_read(self):
        clock=self.clock()
        before=clock.mono+10000000
        ticks=[value for _ in range(32) for value in (before,before+100)]
        with patch('native_scan_protocol.time.monotonic_ns',side_effect=ticks), patch('native_scan_protocol.time.time_ns',return_value=clock.wall+10000050):
            event=clock.marker('phase_start')
        self.assertEqual(event['monotonicNs'],before+50)
        self.assertEqual(event['directWallNs'],clock.wall+10000050)
        self.assertEqual(event['observedAt'],clock.mapped_utc(before+50))
        self.assertEqual(len(event['clockSamples']),32)
        self.assertEqual(event['clockSamples'][event['chosenClockSample']],dict(beforeNs=before,afterNs=before+100,wallNs=clock.wall+10000050))

    def test_uncertain_reads_are_preserved_and_rejected_without_relaxing_drift(self):
        clock=self.clock()
        before=clock.mono+10000000
        ticks=[value for _ in range(32) for value in (before,before+3000)]
        with patch('native_scan_protocol.time.monotonic_ns',side_effect=ticks), patch('native_scan_protocol.time.time_ns',return_value=clock.wall+10001500):
            with self.assertRaisesRegex(ScanError,'CLOCK_SAMPLE_UNCERTAINTY') as failure:
                clock.marker('phase_exit')
        raw=failure.exception.observation
        self.assertEqual(len(raw['samples']),32)
        self.assertEqual(raw['samples'][raw['chosen']]['afterNs']-raw['samples'][raw['chosen']]['beforeNs'],3000)
        self.assertEqual(raw['residualNs'],0)
        self.assertFalse(raw['accepted'])

    def test_child_failure_reaches_controller_without_becoming_state_mismatch(self):
        run=object.__new__(NativeRun)
        run.messages=queue.Queue()
        child=dict(kind='runtime_failure',error='WALL_CLOCK_CHANGED',clockObservation=dict(accepted=False,residualNs=2000001))
        run.messages.put(copy.deepcopy(child))
        with self.assertRaisesRegex(ScanError,'SCANNER_RUNTIME_FAILURE:WALL_CLOCK_CHANGED') as failure:
            run.expect('phase_start',timeout=0)
        self.assertEqual(failure.exception.runtime_failure,child)


if __name__=='__main__':
    unittest.main()
