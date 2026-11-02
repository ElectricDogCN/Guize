"""Offline protection against equal-prefix/different-version revocation false positives."""
import copy
import unittest

from lab import context
from test_warm_cache_revocation import warm_binding


class RevocationBindingTests(unittest.TestCase):
    def setUp(self):
        self.cfg = dict(aclVersion='acl', inputs={'base': dict(sha256='a' * 64)})
        self.ctx = context('acl', 'lab-user-a')
        self.warm = dict(sourceVersion='base', sourceSha256='a' * 64,
            authorizationContext=self.ctx, bodySha256='c' * 64,
            originObservation=dict(gatewayTransactions=[dict(sourceVersion='base', userId='lab-user-a',
                cacheContextPath='/ctx/' + self.ctx + '/base/object.bin')]))

    def test_exact_actual_gateway_version_and_context_are_bound(self):
        self.assertEqual(warm_binding(self.warm, self.cfg, 'lab-user-a')['sourceVersion'], 'base')

    def test_equal_body_hash_cannot_hide_changed_version_or_other_context(self):
        changed = copy.deepcopy(self.warm)
        changed['originObservation']['gatewayTransactions'][0].update(sourceVersion='changed',
            cacheContextPath='/ctx/' + self.ctx + '/changed/object.bin')
        other = copy.deepcopy(self.warm)
        other['originObservation']['gatewayTransactions'][0]['userId'] = 'lab-user-b'
        for record in [changed, other]:
            self.assertEqual(record['bodySha256'], self.warm['bodySha256'])
            with self.assertRaises(AssertionError):
                warm_binding(record, self.cfg, 'lab-user-a')


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RevocationBindingTests))
    if result.testsRun != 2 or result.skipped:
        raise SystemExit('Expected two actual binding tests and no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)
