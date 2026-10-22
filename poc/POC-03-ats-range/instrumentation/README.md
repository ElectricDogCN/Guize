# Proposed live-buffer observation in an instrumented ATS build

Design in progress; no measurement-domain or new experiment approval exists.
Stock source8e73173 diagnostics are retained separately. Its final pool capacity
73,363,200bytes cannot prove a below64MiB upper bound: unused retained pool slots
are not live media payload. No frozen checker/threshold or prototype8MiB value is
changed here.

The alternative is a task-owned source patch against the already byte-verified
Ubuntu9.2.3+ds source archives and Debian patch series. Build and run as ordinary
UID1000 in a new private prefix. Retain every archive/patch/source/toolchain/config
and resulting binary identity. Instrumented performance is not stock performance.

The proposed domain is live capacity of user-space buffers on this controlled ATS
HTTP/Slice/CRR/cache-export path, including shared IOBufferData payload and native
cache aggregation buffers. Kernel sockets/page cache and origin/gateway/client
are distinct domains; any end-to-end claim must add their justified bounds.
The proposed media domain covers protected source payload, including native
cache export copies. Slice-generated 416/502 error text is separate generated
content: its temporary std::string allocation before copying into TSIOBuffer is
not counted here. This ledger does not establish a bound for all HTTP bodies.

Required accounting properties:

- Count payload once in the owning IOBufferData lifecycle; cloning a block or
  adding a reader does not allocate another payload. Count fast and non-fast
  allocations. Empty freelist reservations are excluded.
- Conservatively add capacity **before** acquiring payload; remove it **after**
  the payload is actually released. Concurrent overlap may overcount; it must
  never undercount. Failed allocation or accounting violations invalidate results.
- Update current/highwater and any generation reset under one shared lock. A
  reset retains all currently live baseline buffers; no baseline subtraction.
- Include per-Vol aggregation buffers. Either instrument recovery/direct media
  buffers or prove they are absent throughout the declared post-cache-ready
  observation window. Never claim an entire-process-lifetime bound from a
  steady-state window.
- Identify external/wrapped payload paths. Uncovered external payload activity
  must invalidate qualification for the process lifetime, rather than silently
  contribute zero bytes. Wrapper release does not prove external owner release;
  resetting a measurement window cannot clear the unknown-external risk.
- Bind reset/snapshot records to actual owned PID/start ticks, native HTTP cache
  readiness, source/build identity and the observed request window. A missing,
  unhealthy, reset or mixed-build record cannot establish an upper bound.

Actual allocator tests must exercise shared ownership, baseline retention,
concurrent overlap/highwater, non-fast allocations and failure handling. Actual
instrumented ATS experiments require fresh concrete independent approval of
source/configuration/inputs/resources/window and subsequent result review.

Read-only cgroup research was stopped without any bootstrap or mutation. The
matching WSL kernel implements a racy high-water update and permits transient
limit overshoot; its memory.peak is useful observation, not the required strict
upper-bound proof. It does not replace the missing ATS lifecycle accounting.

The generated unified patch is retained as an exact byte artifact. A blank context line starts with the required patch space; scoped binary attributes preserve that patch stream and its reviewed SHA without changing any source whitespace, checker or threshold.
