> 既有9a428c6组件通过14项纯测试、62项读取回归及4项隔离原生控制用例。后续源码已把instrumented lab接入专用单线程owner，通过源码级审查及30项纯测试独立接受；新owner/ATS实际执行尚未运行，完整媒体与POC仍待。旧结果不转移到新字节；状态和失败修复见[当前交接](../../../evidence/POC-003/handoff.md)。原件见[控制用例档案](../../../evidence/POC-003/single-exec-control-v1/index.json)及[owner集成档案](../../../evidence/POC-003/single-owner-integration-v1/index.json)。

# 固定首次执行交接：实现边界与待接入事项

本文件承接 `86732caf` 的有限可行性审查。`single_exec_filter.py` 已实现固定 BPF、原生 UAPI、监听描述符交接及一次 CONTINUE 的底层检查。`OwnedEpoch` 已提供默认关闭的 `fixed_single_exec` 路径，四项真实单线程控制用例已实际选择该路径；现有 lab 保持原调用，不能把多线程 lab 自动接入。解释器、gate、policy 均须纳入同一固定组件清单，安装前后的完整交接与真实 abort/wait 由调用方负责。完整接入审查、资源批准和真实内核控制用例仍待，不能将本实现或纯 BPF 测试称为运行能力、完整进程族或媒体上界证明。

## 固定规则与 ABI

仅支持 native x86_64、小端、64位指针，拒绝 compat/x32。fork/vfork、未设 CLONE_THREAD 的 clone，以及后续 seccomp 与 prctl(PR_SET_SECCOMP) 均返回 EPERM；clone3 返回 ENOSYS，实际目标 libc 的线程回退仍须实测。execve/execveat 产生通知，父进程只允许本次已验证 execveat(fd, empty-path, argv, env, AT_EMPTY_PATH)。其他系统调用保持既有行为。结构尺寸必须与真实 GET_NOTIF_SIZES 一致，安装返回值是监听 FD，不能按返回0判断成功；不使用 TSYNC 或额外权限。

## 调用方必须落实的可信前缀

新 gate 须保留当前 -I/-S、父进程/出生绑定、只读已验证 ELF FD、有限 GO+EOF 和错误管道。它在安装前只能读取控制元数据及固定代码，不能读媒体、调用插件、生成子进程或启动线程；安装前重置为默认信号、空信号屏蔽，并核对单线程、四组UID、零capabilities。已有 gate 的任意stdin/环境不能未经说明地继承为新能力。ELF须固定为64位x86_64，父端先保存 device/inode/size/mtimeNs/ctimeNs/hash，且启动目录与代码在本次窗口内无其他写入者。

仅当以上前缀源代码和真实状态成立，指针验证才有有限依据。不能用 ID_VALID 代替锁，也不能把 USER_NOTIF 描述为处理任意恶意代码的安全边界。[内核说明](https://docs.kernel.org/userspace-api/seccomp_filter.html)与[通知机制手册](https://man7.org/linux/man-pages/man2/seccomp_unotify.2.html)明确其适用限制。

## 一次描述符与状态交接

1. 父端创建一个私有 CLOEXEC AF_UNIX/SOCK_SEQPACKET socketpair，只传gate端；普通 Popen close_fds，不额外传播监听 FD。父端须禁止在持有监听 FD 时并发spawn或传递该 FD，当前多线程lab须通过具体调用图另证。
2. gate验证前缀、查询ABI、设置 NoNewPrivs 并安装固定过滤器；发单个 `L` 消息附一个 SCM_RIGHTS，关闭自己的监听引用，再发送 `C` 并关闭socket，之后才报告READY。
3. 父端以 MSG_CMSG_CLOEXEC 接收，所有消息共用一个不超过5秒的截止。异常/截断/多FD均关闭已收到FD；只有唯一FD、`C`与空EOF均成立才取得所有权。父端还须实际检查gate不再持有监听或socket引用。
4. 父端实际绑定Popen/pidfd与出生、目标ELF和同一PID namespace，再发送原有限GO并关闭控制写端。gate只能执行固定描述符，不能回退到路径execve。
5. 调用 `continue_initial` 前须把监听FD从调用方cleanup集合中移出；此函数消费该唯一引用，并在所有结局关闭它。接收通知后核ID/TID/birth/parent/singleton/defaultsignals/capabilities/NoNewPrivs/Seccomp、实际ELF及完整有界argv/env。SEND之前再查ID和单线程。设置不可撤销grant-attempt后只调用一次CONTINUE，任何失败、EINTR/ENOENT或超时均不得重试。
6. 当前 helper 仅接受真实 `/proc/self/task` 单线程、native TID 等于 PID、主线程未屏蔽 SIGALRM 且没有已有alarm/handler的父端，再以可中断的原生ioctl执行有限交接。Python MainThread 标签本身不能证明这一条件。当前多线程lab不满足时必须拒绝，其接入须另行解决可定向至实际控制线程的可靠截止或具有完整所有权的单线程控制路径，不能绕过此检查。成功SEND后立即关闭最后监听引用。内核中首次已回复请求和未回复/后续请求的实际行为仍须用所选内核实测。
7. 调用方仍须在异常时真实结束并wait本次拥有的scope；没有错误管道消息或SEND成功均不等于exec成功。原目标身份、真实退出、完整新journal及所有原验收保持。

## 必须补齐的实测与接入

纯规则测试仅在内存中解释29条BPF并核结构布局，不安装过滤器、创建子进程或执行媒体。下一步须独立审查调用方接入后的完整源代码，再固定普通UID1000、caps0、私有PID namespace、已有镜像与有限资源预算，验证真实listener可用性、首次FDexec、排队及关闭后的再次exec拒绝、fork/clone拒绝、pthread回退、FD重复/丢失、信号取消、超时及完整owned清理。失败不允许增加capabilities或改为unconfined。真实ATS helper/start/restart/stop及未跟踪请求延迟、所有媒体所有者仍各自验收。
