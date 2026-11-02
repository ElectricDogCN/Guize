"""Actual Linux process/ELF mapping checks; simulated child, no ATS service."""
import hashlib,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from live_buffer_probe import capture_components

class ActualMappingTests(unittest.TestCase):
    def run_case(self,wrong_hash):
        env=dict(os.environ,PROXY_DPRINTF_LEVEL='0');env.pop('LD_PRELOAD',None);env.pop('LD_AUDIT',None)
        child=subprocess.Popen([sys.executable,'-B','-c','import time;time.sleep(10)'],env=env)
        try:
            executable=Path('/proc',str(child.pid),'exe').resolve()
            expected=hashlib.sha256(executable.read_bytes()).hexdigest()
            with tempfile.TemporaryDirectory() as directory:
                out=Path(directory)/'mapping'
                if wrong_hash:
                    with self.assertRaisesRegex(ValueError,'raw maps and rejection reasons retained'):
                        capture_components(child,{str(executable):'0'*64},out)
                    record=json.loads((out/'component-mapping.json').read_bytes())
                    self.assertEqual(record['components'][0]['rejectionReason'],'component_hash_mismatch')
                    self.assertFalse(record['allVerified'])
                else:
                    record=capture_components(child,{str(executable):expected},out)
                    self.assertTrue(record['allVerified'])
                    component=record['components'][0]
                    self.assertEqual(component['actualFileSha256'],expected)
                    self.assertTrue(any(row['inode']==component['actualInode'] and 'x' in row['permissions'] for row in component['candidateMappings']))
                raw=(out/'maps.raw').read_bytes()
                self.assertEqual(hashlib.sha256(raw).hexdigest(),record['mapsSha256'])
                self.assertEqual((out/'maps.raw').stat().st_mode&0o777,0o600)
        finally:
            if child.poll() is None:child.terminate()
            child.wait(timeout=3)
    def test_actual_executable_mapping_binds_inode_and_hash(self):self.run_case(False)
    def test_hash_mismatch_retains_actual_maps_and_reason(self):self.run_case(True)

if __name__=='__main__':unittest.main()
