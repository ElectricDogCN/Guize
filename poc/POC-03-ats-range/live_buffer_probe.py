"""Read exact owned instrumented snapshots; never infer a bound from sampling."""
from __future__ import annotations
import hashlib,os,re,stat,time
from pathlib import Path
from buffer_probe import process_identity
from lab import unique_json

LIMIT=8*1048576
KINDS=4

def capture_components(child,required,output):
    """Retain actual maps before rejecting any component identity mismatch."""
    output=Path(output);output.mkdir(mode=0o700)
    identity=process_identity(child);raw=(Path('/proc')/str(child.pid)/'maps').read_bytes()
    if len(raw)>1048576:raise ValueError('component mapping byte quota')
    with os.fdopen(os.open(output/'maps.raw',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream:stream.write(raw)
    mappings=[]
    for line in raw.decode().splitlines():
        parts=line.split(maxsplit=5)
        if len(parts)!=6 or not parts[5].startswith('/'):continue
        major,minor=parts[3].split(':')
        mappings.append(dict(path=parts[5],permissions=parts[1],device=os.makedev(int(major,16),int(minor,16)),inode=int(parts[4])))
    rows=[]
    for path,expected in required.items():
        row=dict(expectedPath=path,expectedSha256=expected,candidateMappings=[m for m in mappings if m['path'].removesuffix(' (deleted)')==path or Path(m['path'].removesuffix(' (deleted)')).name==Path(path).name])
        try:
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
            with os.fdopen(fd,'rb') as stream:
                before=os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):raise ValueError('component must be regular file')
                actual=hashlib.file_digest(stream,'sha256').hexdigest();after=os.fstat(stream.fileno())
            row.update(actualFileSha256=actual,actualDevice=before.st_dev,actualInode=before.st_ino)
            exact=[m for m in row['candidateMappings'] if m['path']==path and 'x' in m['permissions'] and (m['device'],m['inode'])==(before.st_dev,before.st_ino)]
            changed=any(getattr(before,key)!=getattr(after,key) for key in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))
            for candidate in row['candidateMappings']:
                if candidate['path'].endswith(' (deleted)'):candidate['hashUnavailableReason']='mapped_file_deleted'
                elif candidate['path']==path and (candidate['device'],candidate['inode'])==(before.st_dev,before.st_ino) and not changed:
                    candidate['actualMappedFileSha256']=actual
                else:candidate['hashUnavailableReason']='candidate_not_exact_verified_installed_inode'
            if changed:row['rejectionReason']='component_changed_during_hash'
            elif actual!=expected:row['rejectionReason']='component_hash_mismatch'
            elif not exact:row['rejectionReason']='exact_live_executable_mapping_missing_or_deleted'
            else:row['verified']=True
        except (OSError,ValueError) as error:row.update(rejectionReason='component_file_unverifiable',errorType=type(error).__name__)
        rows.append(row)
    try:stable=process_identity(child)==identity
    except (OSError,ValueError):stable=False
    record=dict(kind='ACTUAL_OWNED_PROCESS_COMPONENT_MAPPING',process=identity,components=rows,
                processIdentityStable=stable,mapsBytes=len(raw),mapsSha256=hashlib.sha256(raw).hexdigest(),
                allVerified=stable and bool(rows) and all(row.get('verified') is True for row in rows))
    with os.fdopen(os.open(output/'component-mapping.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as stream:
        import json
        stream.write(json.dumps(record,indent=2)+'\n')
    if not record['allVerified']:raise ValueError('actual process component mapping mismatch; exact raw maps and rejection reasons retained')
    return record

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
        if (row['sequence']!=sequence or row['abiVersion']!=1 or row['generation']!=0 or row.get('reset') is not False
                or row.get('accountingWindow')!='process-lifetime'
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
        previous=row
    if after_ns and after_ns<rows[0]['snapshotAfterMonotonicNs']:raise ValueError('request boundary predates window readiness')
    if rows[-1]['snapshotBeforeMonotonicNs']<after_ns:return None
    return dict(first=rows[0],last=rows[-1],recordCount=len(rows),rawEnd=end,
                rawSha256=hashlib.sha256(raw[:end]).hexdigest(),maximumObservedLiveCapacityBytes=rows[-1]['peakBytes'],
                requestCompletedMonotonicNs=after_ns,fullMediaBufferBoundProven=False,baselineSubtracted=False)

def capture_live(child,directory,output,expected,after_ns=0,*,journal_directory=None):
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
                from durable_peak_probe import capture_peak_journal
                durable=capture_peak_journal(child,directory if journal_directory is None else journal_directory,
                                             output/'durable-peak',before)
                if durable['maximumObservedTrackedCapacityBytes']<result['maximumObservedLiveCapacityBytes']:
                    raise ValueError('durable publication does not cover the observed ledger peak')
                result['durablePeakSnapshot']=durable
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
