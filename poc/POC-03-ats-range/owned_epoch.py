"""Bind one owned ELF target's birth before exec, never attest a process family.

An empty CLOEXEC error pipe is only an outcome observation. Completion also
requires actual wait0 and a fresh trusted native journal for the bound birth.
"""
import hashlib,json,os,re,select,signal,stat,subprocess,sys,time
from pathlib import Path
from buffer_probe import process_identity

class EpochLaunchError(ValueError):pass

class TargetView:
    """Use the actual target argv without rewriting the gate's Popen metadata."""
    def __init__(self,process,command):self._process=process;self.args=list(command)
    def __getattr__(self,name):return getattr(self._process,name)

class OwnedEpoch:
    def __init__(self,command,expected_sha256,journal_directory,output,*,env,cwd,
                 stdout,stderr,components,stdin=subprocess.DEVNULL):
        self.command=list(command);self.expected_sha256=expected_sha256
        self.directory=Path(journal_directory).absolute();self.output=Path(output).absolute()
        self.env=dict(env);self.cwd=str(cwd);self.stdout=stdout;self.stderr=stderr;self.stdin=stdin
        self.components=dict(components)
        self.process=None;self.pidfd=None;self._fds=set();self.control=None;self.error_fd=None
        self.released=False;self.error_eof=False;self.launch_identity=None;self.view=None
        self.record=dict(kind='OWNED_TOP_PROCESS_EPOCH_NOT_FAMILY_PROOF',targetCommand=self.command,
            targetExecAttestedByNativeJournal=False,completeTrackedProcessEpoch=False,
            allDescendantsCovered=False,noSubsequentExecProven=False,fullMediaBufferBoundProven=False,
            startedAtUnixNs=time.time_ns(),state='not-started')
    def _save(self):
        (self.output/'launch.json').write_text(json.dumps(self.record,indent=2)+'\n',encoding='utf-8')
    def _close(self,fd):
        if fd in self._fds:
            self._fds.remove(fd)
            try:os.close(fd)
            except OSError:pass
    def _pipe(self):
        pair=os.pipe2(os.O_CLOEXEC);self._fds.update(pair);return pair
    def _verify_components(self):
        if not self.components:raise EpochLaunchError('pinned target core components required')
        rows={}
        for name,expected in self.components.items():
            path=Path(name)
            if not path.is_absolute() or not re.fullmatch('[0-9a-f]{64}',expected):
                raise EpochLaunchError('absolute pinned component identity required')
            digest=hashlib.sha256()
            fd=os.open(path.resolve(strict=True),os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW|os.O_CLOEXEC)
            with os.fdopen(fd,'rb') as stream:
                before=os.fstat(stream.fileno())
                if not stat.S_ISREG(before.st_mode):raise EpochLaunchError('regular pinned component required')
                for block in iter(lambda:stream.read(65536),b''):digest.update(block)
                after=os.fstat(stream.fileno())
            if digest.hexdigest()!=expected or any(getattr(before,k)!=getattr(after,k)
                    for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns')):
                raise EpochLaunchError('pinned core component changed')
            rows[name]=dict(sha256=expected,bytes=before.st_size,device=before.st_dev,inode=before.st_ino)
        return rows
    def _read_pipe(self,fd,name,timeout,*,ready=False):
        deadline=time.monotonic()+timeout;raw=bytearray();eof=False
        try:
            while time.monotonic()<deadline:
                if not select.select([fd],[],[],max(0,deadline-time.monotonic()))[0]:break
                chunk=os.read(fd,256-len(raw)+1)
                if not chunk:eof=True;break
                raw.extend(chunk)
                if len(raw)>256:raise EpochLaunchError('gate outcome byte limit')
                if ready and b'\n' in raw:break
            if ready:
                if raw!=b'READY\n':raise EpochLaunchError('missing exact gate readiness')
            elif not eof:raise TimeoutError('gate outcome deadline')
            return bytes(raw),eof
        finally:
            (self.output/name).write_bytes(raw)
            self.record[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),eof=eof)
            if not ready:self.error_eof=eof;self.record['execErrorPipeEOF']=eof
            self._save()
    def prepare(self,timeout=5):
        if (os.name!='posix' or os.geteuid()==0 or not hasattr(os,'pidfd_open')
                or not hasattr(signal,'pidfd_send_signal') or self.process is not None
                or not self.command or any(not isinstance(arg,str) or '\0' in arg for arg in self.command)
                or not Path(self.command[0]).is_absolute() or not re.fullmatch('[0-9a-f]{64}',self.expected_sha256)
                or any(arg in ('-f','-F','--disable_freelist','--disable_pfreelist') for arg in self.command)
                or self.env.get('LD_PRELOAD') or self.env.get('LD_AUDIT')
                or self.env.get('GUIZE_POC003_PEAK_JOURNAL_DIR')!=str(self.directory)):
            raise EpochLaunchError('ordinary Linux owned ELF launch required')
        if (self.directory==self.output or self.directory.resolve()!=self.directory
                or self.directory.parent.resolve()!=self.directory.parent
                or self.output.parent.resolve()!=self.output.parent):
            raise EpochLaunchError('separate canonical launch directories required')
        if self.directory.exists() or self.directory.is_symlink():
            raise EpochLaunchError('new per-launch journal directory required')
        self.output.mkdir(mode=0o700);self._save()
        try:
            self.directory.mkdir(mode=0o700)
            for path in (self.output,self.directory):
                info=path.lstat()
                if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.geteuid() or stat.S_IMODE(info.st_mode)!=0o700:
                    raise EpochLaunchError('private owned launch directories required')
            self.record['componentsBeforeExec']=self._verify_components()
            executable=os.open(Path(self.command[0]).resolve(strict=True),os.O_RDONLY|os.O_NONBLOCK|os.O_NOFOLLOW|os.O_CLOEXEC)
            self._fds.add(executable);before=os.fstat(executable)
            if not stat.S_ISREG(before.st_mode) or before.st_mode&(stat.S_ISUID|stat.S_ISGID):
                raise EpochLaunchError('ordinary regular executable required')
            if os.read(executable,4)!=b'\x7fELF':raise EpochLaunchError('only pinned native ELF targets')
            os.lseek(executable,0,os.SEEK_SET);digest=hashlib.sha256()
            while True:
                block=os.read(executable,65536)
                if not block:break
                digest.update(block)
            after=os.fstat(executable)
            if (digest.hexdigest()!=self.expected_sha256 or any(getattr(before,k)!=getattr(after,k)
                    for k in ('st_dev','st_ino','st_size','st_mtime_ns','st_ctime_ns'))):
                raise EpochLaunchError('target executable changed or hash mismatch')
            self.record['targetExecutable']=dict(sha256=digest.hexdigest(),bytes=before.st_size,
                device=before.st_dev,inode=before.st_ino,openedDescriptor=executable)
            control_read,self.control=self._pipe();ready_read,ready_write=self._pipe()
            error_read,error_write=self._pipe();self.error_fd=error_read
            control_pipe=os.fstat(control_read);error_pipe=os.fstat(error_write)
            gate=Path(__file__).resolve().parent/'instrumentation/exec_gate.py'
            gate_sha=hashlib.sha256(gate.read_bytes()).hexdigest()
            argv=[sys.executable,'-I','-S','-B',str(gate),str(executable),str(control_read),
                  str(ready_write),str(error_write),str(os.getpid()),json.dumps(self.command)]
            self.process=subprocess.Popen(argv,env=self.env,cwd=self.cwd,stdin=self.stdin,stdout=self.stdout,
                stderr=self.stderr,close_fds=True,pass_fds=(executable,control_read,ready_write,error_write))
            self.record.update(gateArgv=argv,gateSourceSha256=gate_sha,pid=self.process.pid,state='gate-created')
            for fd in (executable,control_read,ready_write,error_write):self._close(fd)
            self.record['parentExecErrorWriterClosed']=True
            os.set_blocking(ready_read,False);os.set_blocking(error_read,False)
            self._read_pipe(ready_read,'ready.raw',timeout,ready=True);self._close(ready_read)
            launch=process_identity(self.process)
            python_info=Path(sys.executable).resolve().stat()
            if (launch['executableDevice'],launch['executableInode'])!=(python_info.st_dev,python_info.st_ino):
                raise EpochLaunchError('gate interpreter identity mismatch')
            inherited=Path('/proc')/str(self.process.pid)/'fd'/str(executable)
            inherited_info=inherited.stat()
            if (inherited_info.st_dev,inherited_info.st_ino)!=(before.st_dev,before.st_ino):
                raise EpochLaunchError('gate inherited ELF descriptor mismatch')
            for label,fd,expected in [('executable',executable,before),('control',control_read,control_pipe),
                                      ('exec-error',error_write,error_pipe)]:
                actual=(Path('/proc')/str(self.process.pid)/'fd'/str(fd)).stat()
                raw=(Path('/proc')/str(self.process.pid)/'fdinfo'/str(fd)).read_bytes()
                (self.output/('gate-'+label+'-fdinfo.raw')).write_bytes(raw)
                flags=int(next(line.split()[1] for line in raw.splitlines() if line.startswith(b'flags:')),8)
                if (actual.st_dev,actual.st_ino)!=(expected.st_dev,expected.st_ino) or not flags&os.O_CLOEXEC:
                    raise EpochLaunchError('gate descriptor identity/CLOEXEC mismatch')
            try:(Path('/proc')/str(self.process.pid)/'fd'/str(ready_write)).lstat()
            except FileNotFoundError:pass
            else:raise EpochLaunchError('gate readiness writer remained open')
            self.pidfd=os.pidfd_open(self.process.pid);self._fds.add(self.pidfd)
            if process_identity(self.process)!=launch or hashlib.sha256(gate.read_bytes()).hexdigest()!=gate_sha:
                raise EpochLaunchError('gate changed before GO')
            self.launch_identity=launch;self.view=TargetView(self.process,self.command)
            self.record.update(launchIdentity=launch,inheritedTargetDescriptorVerified=True,
                childDescriptorsCloexecVerified=True,parentExecErrorWriterClosed=True,state='prepared')
            self._save();return self
        except BaseException as error:
            self.record['error']=type(error).__name__+': '+str(error);self.abort();raise
    @property
    def birth_identity(self):
        if self.launch_identity is None:raise EpochLaunchError('no bound process birth')
        return {key:self.launch_identity[key] for key in ('pid','startTicks')}
    def activate(self,timeout=5):
        try:
            if self.released or self.launch_identity is None or process_identity(self.process)!=self.launch_identity:
                raise EpochLaunchError('only the prepared live gate may receive GO')
            if self._verify_components()!=self.record['componentsBeforeExec']:
                raise EpochLaunchError('pinned components replaced before GO')
            birth=self.birth_identity
            path=self.directory/('peak-'+str(birth['pid'])+'-'+str(birth['startTicks'])+'.jsonl')
            try:path.lstat()
            except FileNotFoundError:pass
            else:raise EpochLaunchError('target journal already exists before GO')
            if os.write(self.control,b'G')!=1:raise EpochLaunchError('short GO write')
            self._close(self.control);self.released=True
            self.record.update(state='released',journalAbsentBeforeGo=True,goMonotonicNs=time.monotonic_ns())
            raw,_=self._read_pipe(self.error_fd,'exec-error.raw',timeout)
            self._close(self.error_fd)
            if raw:raise EpochLaunchError('target exec failed: '+raw.decode('ascii',errors='replace').strip())
            # EOF is deliberately NOT named exec success. finish_journal must
            # also establish actual wait0 and matching native initialization.
            self.record['execErrorPipeClosedWithoutMessage']=True;self._save();return self.view
        except BaseException as error:
            self.record['error']=type(error).__name__+': '+str(error);self.abort();raise
    def target_identity(self):
        if not self.released:raise EpochLaunchError('target has not been released')
        identity=process_identity(self.view);expected=self.record['targetExecutable']
        if ({k:identity[k] for k in ('pid','startTicks')}!=self.birth_identity
                or (identity['executableDevice'],identity['executableInode'])!=(expected['device'],expected['inode'])):
            raise EpochLaunchError('target birth or executable mismatch')
        self.record['actualTargetIdentity']=identity;self._save();return identity
    def finish_journal(self,output):
        try:
            if not self.released or not self.error_eof or not self.record.get('execErrorPipeClosedWithoutMessage'):
                raise EpochLaunchError('GO and closed outcome pipe required before completion')
            if self.process.poll() is None:raise EpochLaunchError('actual target exit still pending')
            code=self.process.wait(timeout=0);self.record.update(exitCode=code,waitCompleted=True)
            from durable_peak_probe import capture_peak_journal
            result=capture_peak_journal(self.process,self.directory,output,self.birth_identity,finished=True)
            self.record['componentsAfterExit']=self._verify_components()
            if self.record['componentsAfterExit']!=self.record['componentsBeforeExec']:
                raise EpochLaunchError('pinned components replaced during target epoch')
            self.record.update(state='completed',targetExecAttestedByNativeJournal=True,
                completeTrackedProcessEpoch=True,journalSha256=result['rawSha256'])
            self._save();return result
        except BaseException as error:
            self.record.update(state='not-accepted',error=type(error).__name__+': '+str(error))
            self._save();raise
        finally:
            if self.process is not None and self.process.poll() is not None:self.close_channels()
    def close_channels(self):
        for fd in list(self._fds):self._close(fd)
        if self.process is not None and self.process.stdin is not None and not self.process.stdin.closed:
            self.process.stdin.close()
    def abort(self):
        try:
            if self.process is not None:
                if self.process.poll() is None:
                    if self.pidfd is not None:signal.pidfd_send_signal(self.pidfd,signal.SIGKILL)
                    else:self.process.kill()
                code=self.process.wait(timeout=5)
                self.record.update(exitCode=code,waitCompleted=True)
                if self.error_fd in self._fds and 'exec-error.raw' not in self.record:
                    try:self._read_pipe(self.error_fd,'exec-error.raw',0.2)
                    except (EpochLaunchError,TimeoutError,OSError):pass
            self.record.update(state='aborted',targetExecAttestedByNativeJournal=False,completeTrackedProcessEpoch=False)
            self._save()
        finally:self.close_channels()
