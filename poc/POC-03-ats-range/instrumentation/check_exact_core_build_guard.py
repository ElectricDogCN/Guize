"""Offline lab-entry rejection check with actual core/observer receipts.

Input preparation and an unloaded exporter are synthetic setup only. Stop at
the run-directory boundary: no input media, sandbox, service or POC is created.
"""
from pathlib import Path
import argparse,hashlib,json,os,sys
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import lab

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('old-runtime','new-runtime','live-receipt','live-plugin','out'):
        parser.add_argument('--'+name,required=True)
    args=parser.parse_args();assert os.name=='posix' and os.geteuid()!=0
    out=Path(args.out).absolute();out.mkdir(mode=0o700)
    (out/'fixture.json').write_text('{}')
    exporter=out/'unloaded-exporter.so';exporter.write_bytes(b'offline-unloaded-exporter-fixture')
    export_receipt=out/'exporter.json'
    export_receipt.write_text(json.dumps(dict(exitCode=0,sourceSha256=lab.digest(lab.HERE/'cache_export.cc'),
                                             pluginSha256=lab.digest(exporter))))
    config=dict(fixtureManifest='fixture.json',runtimeReceipt=args.old_runtime,
        originPort=18231,atsPort=18232,entryPort=18233,chunkBytes=65536,cacheMiB=256,
        maximumRetries=0,maximumRunSeconds=120,latencySampleCount=2,concurrentUsers=2,
        slowOriginDelayMs=250,slowOriginBandwidthBytesPerSecond=1048576,faultAfterBytes=4,
        exportPluginPath=str(exporter),exportPluginSha256=lab.digest(exporter),exportBuildReceipt=str(export_receipt),
        liveBufferObserver=dict(path=args.live_plugin,sha256=lab.digest(Path(args.live_plugin)),buildReceipt=args.live_receipt))
    config_path=out/'config.json';run=out/'must-not-create'
    class ReachedRunCreation(Exception):pass
    original_mkdir=Path.mkdir
    def stop_before_creation(path,*args,**kwargs):
        if path==run:raise ReachedRunCreation('current build passed admission before any run creation')
        return original_mkdir(path,*args,**kwargs)
    checks=[]
    for label,runtime in [('old-five-file',args.old_runtime),('current-six-file',args.new_runtime)]:
        config['runtimeReceipt']=runtime;config_path.write_text(json.dumps(config))
        with mock.patch.object(lab,'prepare_input_pair',return_value={}),mock.patch.object(Path,'mkdir',stop_before_creation):
            try:lab.prepare(config_path,run)
            except ValueError as error:
                assert label=='old-five-file'
                assert str(error)=='exact current core patch and all installed accounting headers required'
                checks.append(dict(label=label,rejectedBeforeRunCreation=True,error=str(error)))
            except ReachedRunCreation:
                assert label=='current-six-file'
                checks.append(dict(label=label,passedAdmissionBeforeRunCreation=True))
            else:raise AssertionError('test unexpectedly created a sandbox')
        assert not run.exists()
    record=dict(checks=checks,labSha256=lab.digest(lab.HERE/'lab.py'),
        currentManifestSha256=lab.digest(lab.HERE/'instrumentation/patch-manifest.json'),
        runtimeReceiptHashes={label:lab.digest(Path(path)) for label,path in
             [('old',args.old_runtime),('current',args.new_runtime),('observer',args.live_receipt)]},
        inputsSynthetic=True,exporterSyntheticNeverLoaded=True,runDirectoryCreated=False,
        atsStarted=False,experimentExecuted=False,fullMediaBufferBoundProven=False)
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(record),flush=True)

if __name__=='__main__':main()
