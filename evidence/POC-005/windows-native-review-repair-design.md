# Windows native review repair — design before implementation

This forward repair stays within POC-005's owned experimental runtime. The
independent review of the uncommitted Windows core on parent fc04cf6 rejected
two P2 defects on 2026-10-22T22:17:54Z; no original13 qualification was accepted.

1. Creating a suspended process and only then assigning it to a kill-on-close
   Job leaves a parent-exit gap. The reviewer actually reproduced a surviving
   disposable child and terminated/waited for it. Replace that sequence with
   CreateProcessW/STARTUPINFOEXW and PROC_THREAD_ATTRIBUTE_JOB_LIST plus the
   explicit inherited standard-handle list. Configure the Job limit first;
   unsupported creation attributes must reject creation, without falling back
   to the leaking sequence. An actual regression must exit the parent at the
   native creation return, before identity publication or any ResumeThread.
2. A resumed child can enter before the parent takes its post-call sample.
   The reviewer reproduced this with an actual 300ms parent observation delay.
   Retain actual QPC/UTC samples before and after ResumeThread separately.
   Require entry no earlier than the pre-call lower bound; never require it
   after the post-call upper bound or relabel that sample as the resume instant.

The original failure records and tests remain. Add real Win32 regressions for
both cases, retain raw outputs and exact file hashes, and obtain independent
review of the repaired content. Linux process/counter behavior and frozen
timing, memory, source, input and original13 qualification rules are unchanged.

Primary API references:

- https://learn.microsoft.com/en-us/windows/desktop/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute
- https://learn.microsoft.com/en-us/windows/win32/api/winbase/ns-winbase-startupinfoexw
- https://learn.microsoft.com/en-us/windows/win32/procthread/process-creation-flags

This is development scope, not approval for a provider or scale experiment.
