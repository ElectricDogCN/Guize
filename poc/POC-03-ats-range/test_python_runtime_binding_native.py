"""Actual fixed-image runtime/mapping and pre-media refusal tests; no ATS or input."""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from collect import Collector
from lab import State,prepare
import python_runtime as runtime

HERE=Path(__file__).resolve().parent
PROFILE=json.loads((HERE/'python-runtime-profile.json').read_bytes())


class RuntimeBindingTests(unittest.TestCase):
    def test_actual_runtime_files_match_profile_and_actual_native_maps(self):
        row=runtime.verify_runtime_file(HERE/'python-runtime-profile.json')
        self.assertTrue(row['componentBytesBound']);self.assertEqual(row['pid'],os.getpid())
        self.assertGreater(row['processStartTicks'],0);self.assertNotEqual(row['uid'],0)
        self.assertEqual(len(row['actualMappedNativeComponents']),9)
        self.assertEqual(set(row['files']),set(PROFILE['files']))
        self.assertEqual(row['profileSha256'],hashlib.sha256((HERE/'python-runtime-profile.json').read_bytes()).hexdigest())
        self.assertFalse(row['aggregateCapacityProofComplete'])

    def test_wrong_native_component_hash_is_rejected(self):
        changed=copy.deepcopy(PROFILE);changed['files']['_socket']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'runtime bytes differ'):runtime.verify_runtime(changed)

    def test_actual_crypto_configuration_provider_engine_and_memcpy_match_fixed_route(self):
        row=runtime.verify_runtime(PROFILE);crypto=row['crypto']
        self.assertEqual(crypto['configuration']['activeIncludeCount'],0)
        self.assertEqual(crypto['configuration']['sha256'],'a65a2cb9f4ee8ffdc7ef4f0ac600c0bdafb95b7b1ab457188ac610a62f5ad6b3')
        self.assertEqual(crypto['algorithm']['provider'],'default')
        self.assertFalse(crypto['algorithm']['defaultDigestEnginePresent'])
        self.assertEqual(crypto['algorithm']['fipsDefaultEnabled'],0)
        self.assertEqual(crypto['algorithm']['functions']['3']['offsetHex'],'0x3a48c0')
        self.assertEqual(crypto['resolvedMemcpy']['offsetHex'],'0x17b800')
        self.assertIn('_ctypes',row['actualMappedNativeComponents'])
        self.assertIn('libffi.so.8',row['actualMappedNativeComponents'])

    def test_wrong_crypto_configuration_binding_is_rejected(self):
        changed=copy.deepcopy(PROFILE);changed['crypto']['configuration']['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'runtime bytes differ'):runtime.verify_runtime(changed)

    def test_another_resolved_memcpy_binding_is_rejected(self):
        changed=copy.deepcopy(PROFILE);changed['crypto']['resolvedMemcpy']['offsetHex']='0x0'
        with self.assertRaisesRegex(ValueError,'runtime bytes differ'):runtime.verify_runtime(changed)

    def test_wrong_profile_abi_identity_is_rejected(self):
        changed=copy.deepcopy(PROFILE);changed['identity']['pointerBytes']=4
        with self.assertRaisesRegex(ValueError,'runtime bytes differ'):runtime.verify_runtime(changed)

    def test_equal_native_file_copy_cannot_impersonate_loaded_mapping(self):
        with tempfile.TemporaryDirectory() as directory:
            native=Path(runtime._socket.__file__)
            copied=Path(directory)/native.name;copied.write_bytes(native.read_bytes())
            self.assertEqual(hashlib.sha256(copied.read_bytes()).hexdigest(),PROFILE['files']['_socket']['sha256'])
            with patch.object(runtime._socket,'__file__',str(copied)):
                with self.assertRaisesRegex(ValueError,'actual mapped executable inode'):runtime.verify_runtime(PROFILE)

    def test_runtime_override_is_rejected_without_media(self):
        with patch.dict(os.environ,{'OPENSSL_CONF':'/tmp/unapproved-config-reference'}):
            with self.assertRaisesRegex(ValueError,'unsupported runtime override'):runtime.verify_runtime(PROFILE)

    def test_collector_refuses_changed_profile_before_creating_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);run=root/'run';run.mkdir();out=root/'collection'
            (run/'settings.private.json').write_text(json.dumps({'liveBufferObserver':{},'pythonRuntimeProfileSha256':'wrong'}))
            with self.assertRaisesRegex(ValueError,'runtime profile changed or missing'):Collector(run,out)
            self.assertFalse(out.exists())

    def test_controller_refuses_changed_profile_before_inputs_or_runtime_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            run=Path(directory)
            (run/'settings.private.json').write_text(json.dumps({'liveBufferObserver':{},'pythonRuntimeProfileSha256':'wrong'}))
            (run/'owner.json').write_text(json.dumps({'uid':os.getuid(),'runDir':str(run.resolve())}))
            with self.assertRaisesRegex(ValueError,'runtime profile changed or missing'):State(run)
            self.assertFalse((run/'python-runtime-binding.controller.json').exists())

    def test_prepare_refuses_override_before_input_preparation_or_run_creation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);run=root/'new-run'
            (root/'manifest.json').write_text('{}')
            (root/'receipt.json').write_text(json.dumps({'status':'ready_for_future_poc_environment','prefix':str(root/'not-a-runtime'),
                'versions':{'traffic_server':{'returncode':0,'stdout':'9.2.3'}}}))
            cfg={'fixtureManifest':'manifest.json','runtimeReceipt':'receipt.json','originPort':18231,'atsPort':18232,'entryPort':18233,
                 'chunkBytes':65536,'cacheMiB':256,'maximumRetries':0,'maximumRunSeconds':1800,'latencySampleCount':4,'concurrentUsers':2,
                 'slowOriginDelayMs':250,'slowOriginBandwidthBytesPerSecond':1048576,'faultAfterBytes':4,'liveBufferObserver':{}}
            config=root/'config.json';config.write_text(json.dumps(cfg))
            with patch.dict(os.environ,{'OPENSSL_CONF':'/tmp/unapproved-config-reference'}):
                with self.assertRaisesRegex(ValueError,'unsupported runtime override'):prepare(config,run)
            self.assertFalse(run.exists())


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RuntimeBindingTests))
    if result.testsRun!=11 or result.skipped:raise SystemExit('Expected eleven fixed-image tests with no skips')
    raise SystemExit(0 if result.wasSuccessful() else 1)
