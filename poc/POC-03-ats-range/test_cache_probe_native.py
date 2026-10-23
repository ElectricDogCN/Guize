"""Linux filesystem regressions only, using an empty observer-directory double.

No ATS listener or protected HTTP request is started by these tests.
"""
import os
from pathlib import Path
import tempfile
import unittest

from cache_probe import export_stage, rename_noreplace
from lab import unique_json


class NativePublicationTests(unittest.TestCase):
    def test_empty_stage_returns_with_distinct_immutable_start_and_final_records(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory).resolve()
            native = run / 'cache-observer' / ('cache-export-' + str(os.getpid()))
            native.mkdir(parents=True, mode=0o700)
            for name in ('lookups.jsonl', 'events.jsonl'):
                (native / name).write_bytes(b'')
            cfg = dict(aclVersion='acl', sliceBytes=1048576,
                       inputs={'base': {'sizeBytes': 67108864}})
            snapshot = dict(atsPid=os.getpid(), stage='before', activeOriginRequests=0,
                            activeGatewayRequests=0)
            result = export_stage(run, run / 'output', cfg, snapshot, 'base')
            self.assertTrue(result['noKeysObserved'])
            self.assertFalse(result['completeLogicalObjectVerified'])
            self.assertFalse(result['partialDiscardProven'])
            self.assertFalse(result['formalPocAccepted'])
            start = unique_json((run / 'output/stage.started.json').read_text())
            final = unique_json((run / 'output/native-stage.json').read_text())
            self.assertNotIn('finishedAt', start)
            self.assertIn('finishedAt', final)
            self.assertFalse((run / 'output/stage.json').exists())
            before = {p.name: p.read_bytes() for p in (run / 'output').iterdir()}
            with self.assertRaises(ValueError):
                export_stage(run, run / 'output', cfg, snapshot, 'base')
            self.assertEqual(before, {p.name: p.read_bytes() for p in (run / 'output').iterdir()})

    def test_atomic_publication_stays_single_link_and_refuses_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, ready = root / 'preparing', root / 'ready'
            source.write_bytes(b'original')
            source.chmod(0o600)
            rename_noreplace(source, ready)
            self.assertFalse(source.exists())
            self.assertEqual(ready.stat().st_nlink, 1)
            self.assertEqual(ready.stat().st_mode & 0o777, 0o600)
            source.write_bytes(b'new')
            with self.assertRaises(FileExistsError):
                rename_noreplace(source, ready)
            self.assertEqual(ready.read_bytes(), b'original')
            self.assertEqual(source.read_bytes(), b'new')
            self.assertEqual(ready.stat().st_nlink, 1)


if __name__ == '__main__':
    if os.name != 'posix' or not hasattr(os, 'getuid'):
        raise SystemExit('Actual ordinary-user Linux filesystem required; no skipped substitute')
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(NativePublicationTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != 2 or result.skipped:
        raise SystemExit('Expected two actual native filesystem tests and no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)
