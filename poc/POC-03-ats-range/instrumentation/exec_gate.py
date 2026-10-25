"""Private same-PID ELF exec gate; stdin/stdout belong to the eventual target."""
import json,os,select,stat,sys,time

def main():
    error_fd=None
    try:
        if len(sys.argv)!=7:raise ValueError('gate argument count')
        executable,control,ready,error_fd,parent=map(int,sys.argv[1:6])
        command=json.loads(sys.argv[6])
        if (os.geteuid()==0 or os.getppid()!=parent or not isinstance(command,list) or not command
                or any(not isinstance(arg,str) or '\0' in arg for arg in command)
                or not os.path.isabs(command[0]) or len({executable,control,ready,error_fd})!=4
                or min(executable,control,ready,error_fd)<3):
            raise ValueError('gate ownership or command')
        if not stat.S_ISREG(os.fstat(executable).st_mode):raise ValueError('ELF descriptor required')
        for fd in (control,ready,error_fd):
            if not stat.S_ISFIFO(os.fstat(fd).st_mode):raise ValueError('private pipe required')
        for fd in (executable,control,ready,error_fd):os.set_inheritable(fd,False)
        if os.write(ready,b'READY\n')!=6:raise ValueError('short readiness write')
        os.close(ready)
        deadline=time.monotonic()+5;message=bytearray()
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0 or not select.select([control],[],[],remaining)[0]:
                raise ValueError('missing bounded GO EOF')
            block=os.read(control,2-len(message))
            if not block:
                if message!=b'G':raise ValueError('exact complete GO required')
                break
            message.extend(block)
            if len(message)>1:raise ValueError('extra GO bytes')
        os.close(control)
        # The already-open, parent-hashed ELF inode is executed. Its descriptor
        # and the outcome pipe close on exec; no intermediary child is created.
        os.execve(executable,command,os.environ)
    except BaseException as error:
        if error_fd is not None:
            try:os.write(error_fd,('ERROR errno='+str(getattr(error,'errno',0) or 0)+'\n').encode())
            except OSError:pass
    os._exit(71)

if __name__=='__main__':main()
