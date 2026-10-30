"""Read the private tracked-allocation journal; never qualify the media domain."""
import hashlib,os,stat
from pathlib import Path
from lab import unique_json

LIMIT=8*1048576
FIELDS={'kind','schemaVersion','pid','startTicks','sequence','abiVersion','generation','accountingWindow',
        'beforeMonotonicNs','peakBytes','currentBytes','currentByKind','acquisitions','releases','violations','uncoveredExternalEvents'}

def parse_durable_peaks(raw,identity,*,finished=False,exit_code=None):
    if not isinstance(raw,bytes) or len(raw)>LIMIT:raise ValueError('durable journal byte bound')
    if finished and (type(exit_code) is not int or exit_code!=0):
        raise ValueError('successful actual process exit required for a complete epoch')
    end=raw.rfind(b'\n')+1
    if not end or finished and end!=len(raw):raise ValueError('missing or incomplete durable journal')
    lines=raw[:end].splitlines();rows=[];previous=None
    if len(lines)>4096 or any(len(line)+1>2048 for line in lines):raise ValueError('durable record quota')
    for sequence,line in enumerate(lines):
        row=unique_json(line)
        if not isinstance(row,dict) or set(row)!=FIELDS:raise ValueError('closed durable record shape required')
        scalars=('schemaVersion','pid','startTicks','sequence','abiVersion','generation','beforeMonotonicNs',
                 'peakBytes','currentBytes','violations','uncoveredExternalEvents')
        if any(type(row[k]) is not int or not 0<=row[k]<=2**64-1 for k in scalars):raise ValueError('invalid durable integer')
        if (row['kind']!='INSTRUMENTED_ATS_DURABLE_PEAK' or row['schemaVersion']!=1 or row['abiVersion']!=1
                or row['generation']!=0 or row['accountingWindow']!='process-lifetime'
                or row['pid']!=identity['pid'] or row['startTicks']!=identity['startTicks']
                or not row['pid'] or not row['startTicks'] or not row['beforeMonotonicNs']
                or row['sequence']!=sequence or row['violations'] or row['uncoveredExternalEvents']):
            raise ValueError('durable identity, reset or health mismatch')
        for key in ('currentByKind','acquisitions','releases'):
            if not isinstance(row[key],list) or len(row[key])!=4 or any(type(v) is not int or not 0<=v<=2**64-1 for v in row[key]):
                raise ValueError('invalid durable category counters')
        if row['currentBytes']!=row['peakBytes'] or sum(row['currentByKind'])!=row['currentBytes']:
            raise ValueError('durable peak publication totals mismatch')
        for kind in range(4):
            live=row['acquisitions'][kind]-row['releases'][kind]
            if live<0 or bool(live)!=bool(row['currentByKind'][kind]):raise ValueError('durable ownership counter mismatch')
        if any(row[key][2] for key in ('currentByKind','acquisitions','releases')):
            raise ValueError('uncovered external ownership invalidates epoch')
        if previous:
            if row['peakBytes']<=previous['peakBytes'] or row['beforeMonotonicNs']<previous['beforeMonotonicNs']:
                raise ValueError('durable peak or clock reset')
            if any(row[key][k]<previous[key][k] for key in ('acquisitions','releases') for k in range(4)):
                raise ValueError('durable counter reset')
        elif row['peakBytes'] or any(any(row[key]) for key in ('currentByKind','acquisitions','releases')):
            raise ValueError('initial durable record must precede target allocations')
        previous=row;rows.append(row)
    return dict(kind='TRACKED_ALLOCATION_PEAK_PREFIX_NOT_MEDIA_QUALIFICATION',recordCount=len(rows),
                rawEnd=end,trailingBytes=len(raw)-end,rawSha256=hashlib.sha256(raw[:end]).hexdigest(),
                first=rows[0],last=rows[-1],maximumObservedTrackedCapacityBytes=rows[-1]['peakBytes'],
                completeTrackedProcessEpoch=finished,fullMediaBufferBoundProven=False)

def capture_peak_journal(child,directory,output,identity,*,finished=False):
    """Bind actual Popen state and an earlier owned PID/start identity to raw bytes."""
    from buffer_probe import process_identity
    if child.pid!=identity['pid']:raise ValueError('child identity mismatch')
    if finished:
        if child.poll() is None:raise ValueError('child still running')
        code=child.wait(timeout=0)
    else:
        if process_identity(child)!=identity:raise ValueError('live child identity changed')
        code=None
    output=Path(output);output.mkdir(mode=0o700)
    path=Path(directory)/('peak-'+str(child.pid)+'-'+str(identity['startTicks'])+'.jsonl')
    raw=b''
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
        with os.fdopen(fd,'rb') as stream:
            before=os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_uid!=os.getuid() or stat.S_IMODE(before.st_mode)!=0o600 or before.st_nlink!=1:
                raise ValueError('private single-link durable journal required')
            named_before=path.lstat()
            if (named_before.st_dev,named_before.st_ino)!=(before.st_dev,before.st_ino):
                raise ValueError('durable journal path replaced before capture')
            raw=stream.read(LIMIT+1);after=os.fstat(stream.fileno())
            named_after=path.lstat()
        if (before.st_dev,before.st_ino)!=(after.st_dev,after.st_ino):raise ValueError('durable journal identity changed')
        if (named_after.st_dev,named_after.st_ino)!=(after.st_dev,after.st_ino):
            raise ValueError('durable journal path replaced during capture')
        if finished and any(getattr(before,k)!=getattr(after,k) for k in ('st_size','st_mtime_ns','st_ctime_ns')):
            raise ValueError('exited journal changed during capture')
        result=parse_durable_peaks(raw,identity,finished=finished,exit_code=code)
        if not finished and process_identity(child)!=identity:raise ValueError('child changed during journal capture')
        result.update(process=identity,exitCode=code,waitCompleted=finished,rawBytes=len(raw),
                      journalDevice=before.st_dev,journalInode=before.st_ino,rawFile='durable-peaks.raw')
        return result
    finally:
        (output/'durable-peaks.raw').write_bytes(raw)
