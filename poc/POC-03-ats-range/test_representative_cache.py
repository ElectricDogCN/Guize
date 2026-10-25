"""Larger-input cache provenance regressions; no ATS or media experiment."""
import unittest
from cache_probe import slice_catalogue
from lab import context

SLICE=1048576

def configuration(size):
    return dict(fixtureProfile='representative-v1',aclVersion='acl-representative',sliceBytes=SLICE,
                inputs={'base':{'sizeBytes':size},'changed':{'sizeBytes':size}})

def catalogue(size,user='alice',version='base'):
    return [dict(keyId=index+1,lookupUrl='http://127.0.0.1:18231/ctx/'+context('acl-representative',user)+'/'+version+
                 '/object.bin-bytes='+str(start)+'-'+str(min(start+SLICE,size)-1))
            for index,start in enumerate(range(0,size,SLICE))]

class RepresentativeCacheTests(unittest.TestCase):
    def test_complete_larger_object_with_short_final_slice_retains_all_129_keys(self):
        size=129*SLICE-17
        selected=slice_catalogue(catalogue(size),configuration(size),'base','alice')
        self.assertEqual(len(selected),129)
        self.assertEqual(sum(row['end']-row['start']+1 for row in selected),size)
        self.assertEqual(selected[-1]['end'],size-1)

    def test_foreign_user_and_version_cannot_complete_a_large_input(self):
        size=129*SLICE
        own=catalogue(size)[:128]
        foreign=[catalogue(size,user='bob')[-1],catalogue(size,version='changed')[-1]]
        selected=slice_catalogue(own+foreign,configuration(size),'base','alice')
        self.assertEqual(len(selected),128)
        self.assertEqual(selected[-1]['end']+1,128*SLICE)

    def test_native_key_capacity_is_still_enforced(self):
        size=513*SLICE
        with self.assertRaises(ValueError):
            slice_catalogue(catalogue(size),configuration(size),'base','alice')

if __name__=='__main__':unittest.main(verbosity=2)
