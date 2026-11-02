"""Allocator text parser adversarial tests; no real ATS or buffer qualification."""
import unittest
from buffer_probe import HEADER, SEPARATOR, FOOTER, parse_dump


def fixture():
    return (HEADER + SEPARATOR
            + b'               8192 |               4096 |       4096 | memory/ioBufAllocator[3]\n'
            + b'                128 |                 64 |         64 | memory/MIOBuffer\n'
            + b'               8320 |               4160 |            | TOTAL\n' + FOOTER)


class AllocatorParserTests(unittest.TestCase):
    def test_absolute_capacity_includes_unused_retained_pool(self):
        result = parse_dump(fixture())
        self.assertEqual(result['allocatedPoolBytes'], 8320)
        self.assertEqual(result['inUsePoolBytes'], 4160)
        self.assertFalse(result['baselineSubtracted'])
        self.assertFalse(result['fullMediaBufferBoundProven'])

    def test_interval_can_contain_diagnostics_around_complete_table(self):
        result = parse_dump(b'ordinary diagnostic\n' + fixture() + b'next diagnostic\n')
        self.assertEqual(result['tableStart'], len(b'ordinary diagnostic\n'))
        self.assertEqual(result['tableEnd'], len(b'ordinary diagnostic\n' + fixture()))

    def test_partial_header_or_missing_footer_does_not_count(self):
        for raw in (fixture()[:20], fixture()[:-len(FOOTER)], fixture()[:-1]):
            with self.subTest(rawBytes=len(raw)), self.assertRaises(ValueError):
                parse_dump(raw)

    def test_wrong_native_total_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_dump(fixture().replace(b'8320', b'8319'))

    def test_interleaved_log_or_baseline_relative_row_is_rejected(self):
        for raw in (fixture().replace(SEPARATOR, SEPARATOR + b'background log\n'),
                    fixture().replace(b'       4096 | memory/', b' 1 | 4096 | memory/')):
            with self.assertRaises(ValueError):
                parse_dump(raw)

    def test_counter_units_and_used_beyond_capacity_are_rejected(self):
        for before, after in ((b'8192', b'8193'), (b'8192', b'0'),
                              (b'       4096 | memory/', b'          0 | memory/')):
            with self.assertRaises(ValueError):
                parse_dump(fixture().replace(before, after, 1))

    def test_duplicate_dump_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_dump(fixture() + fixture())


if __name__ == '__main__':
    unittest.main()
