"""Real bounded configuration inputs and override refusal; no native target."""
import hashlib
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from crypto_runtime import configuration,validate_environment,OVERRIDE_ENV


class CryptoConfigurationTests(unittest.TestCase):
    def test_real_config_hash_and_commented_include(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'openssl.cnf';raw=b'# .include not-loaded.cnf\n[openssl_init]\n'
            path.write_bytes(raw);row=configuration(path)
            self.assertEqual(row,dict(path=str(path.resolve()),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),activeIncludeCount=0))

    def test_active_includes_are_refused(self):
        for raw in [b'.include other.cnf\n',b'  .include=other.cnf\n']:
            with self.subTest(raw=raw),tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'openssl.cnf';path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError,'configuration include'):configuration(path)

    def test_real_oversized_configuration_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'openssl.cnf';path.write_bytes(b'#'*65537)
            with self.assertRaisesRegex(ValueError,'configuration byte quota'):configuration(path)

    def test_each_native_override_is_refused_without_loading_an_engine(self):
        for name in OVERRIDE_ENV:
            with self.subTest(name=name),patch.dict(os.environ,{name:'unapproved-selector'}):
                with self.assertRaisesRegex(ValueError,'unsupported runtime override'):validate_environment()


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CryptoConfigurationTests))
    if result.testsRun!=4 or result.skipped:raise SystemExit('Expected four actual configuration tests with no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)
