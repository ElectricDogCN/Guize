"""Retain rejected native clock evidence and the actual child failure cause."""
import copy
import queue
import unittest
from unittest.mock import patch

from metadata_scan import ScanError
from native_scan_control import NativeRun
from native_scan_protocol import Clock
from native_scan_runtime import _entry_marker


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

    def test_entry_keeps_cold_wide_read_and_chooses_only_by_bracket_width(self):
        clock = self.clock()
        samples = []
        for index in range(32):
            before = clock.mono + 10000000 + index * 10000
            width = 4000 if index == 0 else 100 if index == 1 else 200
            samples.append(dict(beforeNs=before, afterNs=before + width,
                                wallNs=clock.wall + before - clock.mono + width // 2))
        original = copy.deepcopy(samples)
        event = _entry_marker(clock, samples)
        self.assertEqual(event['chosenClockSample'], 1)
        self.assertEqual(event['clockSamples'], original)
        self.assertEqual(samples, original)
        self.assertEqual(event['monotonicNs'], samples[1]['beforeNs'] + 50)
        self.assertEqual(event['directWallNs'], samples[1]['wallNs'])
        self.assertEqual(event['observedAt'], clock.mapped_utc(event['monotonicNs']))

    def test_entry_failures_retain_all_reads_without_finding_a_passing_sample(self):
        for drifting in (False, True):
            with self.subTest(drifting=drifting):
                clock = self.clock()
                samples = []
                for index in range(32):
                    before = clock.mono + 10000000 + index * 10000
                    width = (100 if index == 0 else 200) if drifting else 3000
                    wall = clock.wall + before - clock.mono + width // 2
                    if drifting and index == 0:
                        wall += 2000001
                    samples.append(dict(beforeNs=before, afterNs=before + width, wallNs=wall))
                original = copy.deepcopy(samples)
                expected = 'WALL_CLOCK_CHANGED' if drifting else 'CLOCK_SAMPLE_UNCERTAINTY'
                with self.assertRaisesRegex(ScanError, expected) as failure:
                    _entry_marker(clock, samples)
                self.assertEqual(failure.exception.observation['samples'], original)
                self.assertEqual(failure.exception.observation['chosen'], 0)
                self.assertEqual(failure.exception.observation['directWallNs'], samples[0]['wallNs'])
                self.assertFalse(failure.exception.observation['accepted'])
                self.assertEqual(samples, original)

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
