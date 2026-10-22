"""Read exact owned instrumented snapshots; never infer a bound from sampling."""
from __future__ import annotations
import hashlib,os,re,stat,time
from pathlib import Path
from buffer_probe import process_identity
from lab import unique_json

LIMIT=8*1048576
KINDS=4

def parse_snapshots(raw,identity,expected,after_ns=0):
    if type(after_ns)!=int or after_ns<0:raise ValueError('explicit monotonic request boundary required')
    if set(expected)!={'ledgerHeaderSha256','observerSourceSha256'} or any(not re.fullmatch('[a-f0-9]{64}',v) for v in expected.values()):
        raise ValueError('exact header and observer identities required')
    end=raw.rfind(b'\n')+1
    if not end:return None
    rows=[unique_json(line) for line in raw[:end].splitlines()]
    previous=None
    for sequence,row in enumerate(rows):
        if not isinstance(row,dict) or 'error' in row:raise ValueError('observer error record')
        if (row.get('kind')!='INSTRUMENTED_ATS_LIVE_MEDIA_CAPACITY' or row.get('atsPid')!=identity['pid']
                or row.get('startTicks')!=identity['startTicks'] or any(row.get(k)!=v for k,v in expected.items())):
            raise ValueError('mixed observer/process/header identity')
        scalar=('sequence','abiVersion','generation','snapshotBeforeMonotonicNs','snapshotAfterMonotonicNs',
                'currentBytes','peakBytes','violations','uncoveredExternalEvents')
        if any(type(row.get(k))!=int or not 0<=row[k]<=2**64-1 for k in scalar):raise ValueError('invalid integer snapshot')
        if (row['sequence']!=sequence or row['abiVersion']!=1 or row['generation']!=1 or row.get('reset') is not (sequence==0)
                or row.get('cacheReady') is not True or row.get('httpCacheReady') is not True
                or row.get('baselineSubtracted') is not False or row.get('experimentApprovedByObserver') is not False):
            raise ValueError('invalid readiness/reset/generation')
        if (not row['snapshotBeforeMonotonicNs'] or row['snapshotAfterMonotonicNs']<row['snapshotBeforeMonotonicNs']
                or row['peakBytes']<row['currentBytes'] or row['violations'] or row['uncoveredExternalEvents']):
            raise ValueError('unhealthy or uncovered observation')
        for key in ('currentByKind','liveByKind','acquisitions','releases'):
            values=row.get(key)
            if (not isinstance(values,list) or len(values)!=KINDS
                    or any(type(v)!=int or not 0<=v<=2**64-1 for v in values)):
                raise ValueError('invalid category counters')
        if sum(row['currentByKind'])!=row['currentBytes']:raise ValueError('live byte total mismatch')
        for kind in range(KINDS):
            if row['acquisitions'][kind]-row['releases'][kind]!=row['liveByKind'][kind]:raise ValueError('lifecycle counter mismatch')
            if bool(row['liveByKind'][kind])!=bool(row['currentByKind'][kind]):raise ValueError('payload/count mismatch')
        if row['acquisitions'][2] or row['currentByKind'][2]:raise ValueError('unknown external owner')
        if previous:
            if row['snapshotBeforeMonotonicNs']<previous['snapshotAfterMonotonicNs'] or row['peakBytes']<previous['peakBytes']:
                raise ValueError('nonmonotonic window or peak')
            if any(row[key][k]<previous[key][k] for key in ('acquisitions','releases') for k in range(KINDS)):
                raise ValueError('counter reset within window')
        elif row['peakBytes']!=row['currentBytes']:raise ValueError('reset must retain current baseline')
        previous=row
    if after_ns and after_ns<rows[0]['snapshotAfterMonotonicNs']:raise ValueError('request boundary predates window readiness')
    if rows[-1]['snapshotBeforeMonotonicNs']<after_ns:return None
    return dict(first=rows[0],last=rows[-1],recordCount=len(rows),rawEnd=end,
                rawSha256=hashlib.sha256(raw[:end]).hexdigest(),maximumObservedLiveCapacityBytes=rows[-1]['peakBytes'],
                requestCompletedMonotonicNs=after_ns,fullMediaBufferBoundProven=False,baselineSubtracted=False)

def capture_live(child,directory,output,expected,after_ns=0):
    """Keep the exact complete file prefix even when validation fails."""
    output=Path(output);output.mkdir(mode=0o700)
    before=process_identity(child);path=Path(directory)/('live-buffer-'+str(child.pid)+'.jsonl')
    deadline=time.monotonic()+5;raw=b'';fd=None
    try:
        while time.monotonic()<deadline:
            if process_identity(child)!=before:raise ValueError('owned child identity changed')
            if fd is None:
                try:fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
                except FileNotFoundError:time.sleep(.05);continue
                info=os.fstat(fd)
                if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)!=0o600 or info.st_nlink!=1:
                    raise ValueError('private owned observer file required')
            raw=os.pread(fd,LIMIT+1,0)
            if len(raw)>LIMIT:raise ValueError('observer byte quota')
            result=parse_snapshots(raw,before,expected,after_ns)
            if result:
                if process_identity(child)!=before:raise ValueError('child changed after snapshot')
                raw=raw[:result['rawEnd']]
                result.update(kind='INSTRUMENTED_LIVE_MEDIA_OBSERVATION_NOT_QUALIFIED',process=before,
                              observerFileDevice=info.st_dev,observerFileInode=info.st_ino,rawBytes=len(raw),
                              rawFile='live-snapshots.raw',experimentApprovedByObserver=False)
                return result
            time.sleep(.05)
        raise TimeoutError('post-boundary healthy live snapshot not observed')
    finally:
        (output/'live-snapshots.raw').write_bytes(raw)
        if fd is not None:os.close(fd)
