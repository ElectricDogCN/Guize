# POC-003 isolated ATS sandbox

Implementation in progress. No formal experiment, sample/resource approval or POC acceptance is supplied by these sources.

The initial implementation imports actual historical local prototypes; provenance and known failures are retained in Evidence. lab.py owns only its explicit loopback sandbox and ATS child, collect.py retains raw observed requests, and cache_export.cc uses the actual ATS cache API. HTTP response copies and opaque disk allocation do not establish cached payload export.

Required completion: original fifteen measurements/formal checker, a separate real warm-cache revocation test, and independent result review. The revocation test must reject stale credentials within their original valid interval before any ATS/cache/origin read.

Build the observer with `python poc/POC-03-ats-range/build_observer.py --include <actual-ATS9.2.3-SDK-usr/include> --out <new-private-build-dir>`. It retains compiler output, actual source/header/binary hashes and exit status. This is compilation, not experiment execution.

Before any serve/matrix command, obtain independent approval of the actual source, inputs, configuration, resources and applicable measurement domains. Supply real paths and hashes in an explicit reviewed config; the example contains deliberate placeholders and is not executable approval. Use a new ordinary-user native runroot, never a system ATS instance. The Origin port is fixed18231 to match the observer allowlist. prepare fixes public grant metadata and private sandbox keys; serve refuses changed implementation bytes, input bytes or plugin bytes. Runtime keys remain only in the private runroot.

After the approved sandbox starts, the mandatory direct command `python poc/POC-03-ats-range/test_warm_cache_revocation.py` requires GUIZE_POC003_RUN_DIR and GUIZE_POC003_REVOCATION_OUT (a new output directory); explicit --run-dir/--output-dir arguments are also supported. Missing real sandbox/observer is a failure. It primes and actually hits the old cache, revokes the same still-unexpired grant, then requires403/zero bytes, zero ATS lookup/export activity and zero origin I/O during the denial interval. A separately identified privileged control AFTER that interval proves the original cache still holds the same bytes. This control is not an authorized request under the revoked grant or a production IAM exception.

`python poc/POC-03-ats-range/test_lab.py` runs eight offline boundary tests. Those do not establish real ATS behavior, original15 measurements, full-V1 acceptance, or sample approval. `collect.py` still emits raw, unassessed observations; formal typed assembly, actual stage cache exports/discard proof, actual ATS buffering interpretation and independently approved results remain unfinished. No request marker is normalized to expected PASS/PARTIAL states.
