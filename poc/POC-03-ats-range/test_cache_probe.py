"""Offline cache catalogue isolation tests; never real ATS experiment evidence."""
import unittest

from cache_probe import slice_catalogue
from lab import context


class CacheCatalogueIsolationTests(unittest.TestCase):
    def setUp(self):
        self.cfg = dict(aclVersion='acl-1', sliceBytes=1048576,
                        inputs={'base': {'sizeBytes': 67108864}, 'changed': {'sizeBytes': 67108864}})

    def key(self, key_id=1, user='alice', version='base', start=0, end=1048575):
        return dict(keyId=key_id, lookupUrl='http://127.0.0.1:18231/ctx/'
                    + context('acl-1', user) + '/' + version + '/object.bin-bytes='
                    + str(start) + '-' + str(end))

    def test_other_user_and_old_version_cannot_supply_missing_cache_bytes(self):
        rows = [self.key(), self.key(2, user='bob'), self.key(3, version='changed')]
        selected = slice_catalogue(rows, self.cfg, 'base', 'alice')
        self.assertEqual([row['keyId'] for row in selected], [1])
        self.assertEqual(sum(row['end'] - row['start'] + 1 for row in selected), 1048576)

    def test_same_interval_under_two_native_keys_is_rejected(self):
        duplicate = self.key(2)
        duplicate['lookupUrl'] = duplicate['lookupUrl'].replace('127.0.0.1:18231', 'ats.local')
        with self.assertRaises(ValueError):
            slice_catalogue([self.key(), duplicate], self.cfg, 'base', 'alice')

    def test_misaligned_shortened_or_out_of_input_slice_is_rejected(self):
        for start, end in [(1, 1048576), (0, 7), (67108864, 68157439)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                slice_catalogue([self.key(start=start, end=end)], self.cfg, 'base', 'alice')

    def test_unknown_origin_cannot_become_cache_provenance(self):
        row = self.key()
        row['lookupUrl'] = row['lookupUrl'].replace('127.0.0.1:18231', 'example.invalid')
        self.assertEqual(slice_catalogue([row], self.cfg, 'base', 'alice'), [])


if __name__ == '__main__':
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CacheCatalogueIsolationTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != 4 or result.skipped:
        raise SystemExit('Expected four actual offline tests and no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)
