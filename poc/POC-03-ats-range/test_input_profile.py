"""Offline real-file/stream regressions; no ATS, network or POC acceptance."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock

from collect import Collector
from input_profile import prepare_input_pair, _actual_digest
from lab import PINNED
import lab


class ManifestIngressTests(unittest.TestCase):
    def test_prepare_caps_real_manifest_read_before_runtime_or_run_creation(self):
        with tempfile.TemporaryDirectory(prefix='poc003-manifest-unit-') as directory:
            root = Path(directory)
            manifest = root/'oversized.json'
            manifest.write_bytes(b' '*131073)
            config = root/'config.json'
            config.write_text(json.dumps(dict(fixtureManifest=manifest.name,
                                             runtimeReceipt='must-not-read.json')))
            run = root/'must-not-create'
            actual_open = Path.open
            reads = []

            class BoundedRead:
                def __init__(self, stream):
                    self.stream = stream

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    self.stream.close()

                def read(self, count=-1):
                    if count != 65537:
                        raise AssertionError('manifest ingress requested unbounded or wrong-size read')
                    raw = self.stream.read(count)
                    reads.append((count, len(raw)))
                    return raw

            def open_path(path, *args, **kwargs):
                stream = actual_open(path, *args, **kwargs)
                return BoundedRead(stream) if path == manifest else stream

            with mock.patch.object(lab, 'os', SimpleNamespace(name='posix', geteuid=lambda: 1000)), \
                    mock.patch.object(Path, 'open', open_path):
                with self.assertRaisesRegex(ValueError, 'manifest exceeds 64KiB'):
                    lab.prepare(config, run)
            self.assertEqual(reads, [(65537, 65537)])
            self.assertFalse(run.exists())


class InputProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='poc003-input-unit-')
        cls.directory = Path(cls.temporary.name)
        cls.size = 67108864+131072
        cls.rows = {}
        for label, byte in [('base', b'a'), ('changed', b'b')]:
            path = cls.directory/(label+'.bin')
            value = hashlib.sha256()
            remaining = cls.size
            with path.open('wb') as stream:
                while remaining:
                    block = byte*min(1048576, remaining)
                    stream.write(block)
                    value.update(block)
                    remaining -= len(block)
            cls.rows[label] = dict(file=path.name, sizeBytes=cls.size, sha256=value.hexdigest())

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def fixture(self):
        manifest = dict(schemaVersion=1, kind='poc003-representative-pair-v1',
                        base=copy.deepcopy(self.rows['base']), changedVersion=copy.deepcopy(self.rows['changed']))
        cfg = dict(fixtureProfile='representative-v1', minimumInputBytes=67108864,
                   maximumInputBytes=self.size, sliceBytes=1048576, maximumBufferedBytes=8388608,
                   maximumOriginRequests=2048, maximumCollectionBytes=5*self.size+2097152)
        return cfg, manifest

    def call(self, cfg, manifest, *, raw=None, bind_hash=True):
        raw = raw if raw is not None else json.dumps(manifest).encode()
        if bind_hash:
            cfg['fixtureManifestSha256'] = hashlib.sha256(raw).hexdigest()
        return prepare_input_pair(cfg, self.directory/'manifest.json', raw, PINNED)

    def test_real_pair_above_legacy_size_is_verified_without_issuing_approval(self):
        cfg, manifest = self.fixture()
        actual = self.call(cfg, manifest)
        self.assertEqual(set(actual), {'base', 'changed'})
        for label, row in actual.items():
            self.assertEqual(row['sizeBytes'], self.size)
            self.assertEqual(row['sha256'], self.rows[label]['sha256'])
            self.assertEqual(Path(row['path']).stat().st_size, self.size)
            self.assertEqual(set(row), {'path', 'sizeBytes', 'sha256', 'etag'})

    def test_prototype_default_pins_and_limits_are_preserved(self):
        cfg, manifest = self.fixture()
        cfg.pop('fixtureProfile')
        cfg.pop('maximumCollectionBytes')
        with mock.patch('input_profile._actual_digest', side_effect=AssertionError('invalid prototype opened inputs')):
            with self.assertRaisesRegex(ValueError, 'prototype input pair'):
                self.call(cfg, manifest)
            for change in [dict(minimumInputBytes=134217728), dict(maximumOriginRequests=4096),
                           dict(maximumCollectionBytes=1073741825)]:
                with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'prototype limits'):
                    self.call(dict(cfg, **change), manifest)

    def test_manifest_hash_duplicate_shape_and_unknown_profile_fail(self):
        cfg, manifest = self.fixture()
        cfg['fixtureManifestSha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'manifest hash'):
            self.call(cfg, manifest, bind_hash=False)
        for altered in [dict(manifest, schemaVersion=True), dict(manifest, unexpected=1)]:
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                self.call(dict(cfg), altered)
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.call(dict(cfg), manifest, raw=b'{"schemaVersion":1,"schemaVersion":1}')
        with self.assertRaisesRegex(ValueError, 'unknown fixture'):
            self.call(dict(cfg, fixtureProfile='unknown'), manifest)

    def test_names_declared_size_content_hash_and_version_collision_fail(self):
        cfg, manifest = self.fixture()
        changes = [dict(file='../outside.bin'), dict(file='/outside.bin'), dict(file='C:\\outside.bin'),
                   dict(sizeBytes=self.size-1), dict(sizeBytes=self.size+1), dict(sizeBytes=True),
                   dict(sha256='0'*64), dict(sha256='X'*64), dict(file='changed.bin'),
                   dict(sha256=self.rows['changed']['sha256'])]
        for change in changes:
            altered = copy.deepcopy(manifest)
            altered['base'].update(change)
            with self.subTest(change=change), self.assertRaises((ValueError, OSError)):
                self.call(dict(cfg), altered)
        # A declared two-GiB value without those bytes never becomes an input.
        altered = copy.deepcopy(manifest)
        altered['base']['sizeBytes'] = 2147483648
        broad = dict(cfg, maximumInputBytes=2147483648, maximumCollectionBytes=16*2147483648,
                     maximumOriginRequests=20000)
        with self.assertRaisesRegex(ValueError, 'actual input size'):
            self.call(broad, altered)

    def test_representative_resource_bounds_are_explicit(self):
        cfg, manifest = self.fixture()
        for change in [dict(maximumInputBytes=self.size-1), dict(maximumOriginRequests=2047),
                       dict(maximumCollectionBytes=5*self.size+2097151),
                       dict(maximumBufferedBytes=67108864), dict(minimumInputBytes=True)]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.call(dict(cfg, **change), manifest)

    def test_shortening_growth_symlink_and_replacement_identity_fail(self):
        with tempfile.TemporaryDirectory(prefix='poc003-input-race-') as directory:
            path = Path(directory)/'sample.bin'
            original_read = __import__('os').read
            for kind in ['shorten', 'grow']:
                path.write_bytes(b'abcdefgh')
                changed = False

                def read(fd, count):
                    nonlocal changed
                    if not changed:
                        changed = True
                        path.write_bytes(b'abc' if kind == 'shorten' else b'abcdefghi')
                    return original_read(fd, count)

                with self.subTest(kind=kind), mock.patch('input_profile.os.read', side_effect=read):
                    with self.assertRaises((ValueError, OSError)):
                        _actual_digest(path, 8)
            path.write_bytes(b'abcdefgh')
            with mock.patch.object(Path, 'is_symlink', return_value=True):
                with self.assertRaisesRegex(ValueError, 'symlink'):
                    _actual_digest(path, 8)
            original_stat = path.lstat()
            replacement = mock.Mock(st_dev=original_stat.st_dev, st_ino=original_stat.st_ino+1,
                st_mode=original_stat.st_mode, st_size=8, st_mtime_ns=original_stat.st_mtime_ns,
                st_ctime_ns=original_stat.st_ctime_ns)
            with mock.patch.object(Path, 'lstat', return_value=replacement):
                with self.assertRaisesRegex(ValueError, 'identity'):
                    _actual_digest(path, 8)

    def collector(self, out, source, *, total=0, budget=1073741824):
        value = Collector.__new__(Collector)
        value.out = out
        (out/'bodies').mkdir()
        (out/'observations').mkdir()
        value.cfg = dict(aclVersion='unit-acl', users={'lab-user-a': 'unit-only'},
            maximumCollectionBytes=budget, inputs={'base': source})
        value.entry = 'http://127.0.0.1:1'
        value.rows = []
        value.lock = threading.Lock()
        value.total_bytes = total
        value.request_active = value.request_peak = 0
        value.monotonic = time.monotonic()
        value.control = mock.Mock(return_value=dict(originRequestCount=0, objectReadCount=0,
                                                    objectReadBytes=0, activeOriginRequests=0))
        return value

    def request(self, collector, path, size):
        class Response:
            code = 200
            headers = {'Content-Length': str(size)}

            def __init__(self):
                self.stream = path.open('rb')

            def read(self, count):
                return self.stream.read(count)

            def readinto(self, target):
                return self.stream.readinto(target)

            def close(self):
                self.stream.close()

        opener = mock.Mock()
        opener.open.side_effect = lambda *a, **k: Response()
        with mock.patch('collect.urllib.request.build_opener', return_value=opener), mock.patch('collect.time.sleep'):
            return collector.request('stream', range_header='')

    def test_collector_streams_real_file_above_original_response_ceiling(self):
        with tempfile.TemporaryDirectory(prefix='poc003-body-unit-') as directory:
            path = self.directory/'base.bin'
            source = dict(path=str(path), sizeBytes=self.size, sha256=self.rows['base']['sha256'], etag='"unit-base"')
            collector = self.collector(Path(directory), source)
            row = self.request(collector, path, self.size)
            self.assertTrue(row['transportCompleted'])
            self.assertTrue(row['sourceIntervalComparison']['actualBytesEqual'])
            self.assertEqual(row['bodyBytes'], self.size)
            self.assertLessEqual(row['clientChunkPeak'], 65536)

    def test_collector_uses_declared_aggregate_limit_and_retains_failure_body(self):
        # Seeded logical prior totals exercise accounting, not a GiB transfer.
        for budget, accepted in [(2147483648, True), (1073741824, False)]:
            with self.subTest(budget=budget), tempfile.TemporaryDirectory(prefix='poc003-budget-unit-') as directory:
                root = Path(directory)
                path = root/'source.bin'
                path.write_bytes(b'abcdefgh')
                source = dict(path=str(path), sizeBytes=8, sha256=hashlib.sha256(b'abcdefgh').hexdigest(), etag='"unit-small"')
                collector = self.collector(root, source, total=1073741824, budget=budget)
                if accepted:
                    row = self.request(collector, path, 8)
                    self.assertTrue(row['sourceIntervalComparison']['actualBytesEqual'])
                else:
                    with self.assertRaisesRegex(ValueError, 'collection byte budget'):
                        self.request(collector, path, 8)
                    self.assertEqual(next((root/'bodies').iterdir()).read_bytes(), b'abcdefgh')


if __name__ == '__main__':
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(case)
                               for case in (InputProfileTests, ManifestIngressTests))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if result.testsRun != 9 or result.skipped:
        raise SystemExit('Expected nine actual offline tests and no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)
