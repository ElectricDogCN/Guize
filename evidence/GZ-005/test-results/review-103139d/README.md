# GZ-005 Review103 and actual Review-main evidence index

Original source: 103139d9093bc61cdcc6da1f874a9b79988dbad8 / tree e78c639f13781c129dabe8f33502d852c3b1297a. Actual Review merge/main: 8f2beb00c568ecb79c8ae0204f36fe445599fc37. Code completion identity remains PR82 / 95dc9d7cec927a753e8017cd3b509ebfee681b72.

Actual Review14 all exit0; no local governance or API rerun on that pure Review source. Official same-head CI637 attempt2: 527 passed in 1151.44s, zero test skips, all steps successful. Attempt1 retains 527 passed but overall cancelled for the official 20m0s timeout and is NOT accepted. Actual Review-main has its own push/main execution; inspect actual-review-main-ci-proof.json in the bundle for its run, exact checkout/tree and full527 result. No old results are transferred to the pending Completion source.

All originals are preserved losslessly in raw-results.bundle.json; the logical filenames below are bundle entries, not separate Git files. SHA-256 applies to the original physical bytes, including original line endings. Decode each originalPhysicalBytesZlibBase64 with Base64 then zlib, verify originalPhysicalSize and originalPhysicalSha256 before viewing/export. Bundle compression changes storage only; no tests or gates are disabled.

## Executed Review14 commands

- task: `python scripts/check-task-file.py --task GZ-005`; Exit Code: 0.
- readiness: `python scripts/check-project-readiness.py`; Exit Code: 0.
- schemas: `python scripts/check-schemas.py`; Exit Code: 0.
- integrity: `python scripts/check-program-plan-integrity.py --base-ref 95dc9d7cec927a753e8017cd3b509ebfee681b72`; Exit Code: 0.
- history: `python scripts/check-program-plan-history.py --base-ref 95dc9d7cec927a753e8017cd3b509ebfee681b72 --head-ref HEAD --task GZ-005 --branch-name chore/GZ-005-openapi-baseline`; Exit Code: 0.
- transitions: `python scripts/check-program-plan-transitions.py --base-ref 95dc9d7cec927a753e8017cd3b509ebfee681b72 --head-ref HEAD --task GZ-005 --branch-name chore/GZ-005-openapi-baseline`; Exit Code: 0.
- finalization: `python scripts/check-program-plan-finalization.py --base-ref 95dc9d7cec927a753e8017cd3b509ebfee681b72 --task GZ-005`; Exit Code: 0.
- raw-lifecycle: `python scripts/check-program-lifecycle-guards.py --base-ref 95dc9d7cec927a753e8017cd3b509ebfee681b72 --head-ref HEAD --task GZ-005 --branch-name chore/GZ-005-openapi-baseline`; Exit Code: 0.
- lifecycle: `python scripts/run-program-lifecycle-gate.py --base-ref 95dc9d7cec927a753e8017cd3b509ebfee681b72 --head-ref HEAD --task GZ-005 --branch-name chore/GZ-005-openapi-baseline`; Exit Code: 0.
- coordination: `python scripts/run-agent-coordination-gate.py --base-ref 95dc9d7cec927a753e8017cd3b509ebfee681b72 --head-ref HEAD --task GZ-005 --branch-name chore/GZ-005-openapi-baseline`; Exit Code: 0.
- scope: `python scripts/run-task-scope-gate.py --task GZ-005 --base 95dc9d7cec927a753e8017cd3b509ebfee681b72`; Exit Code: 0.
- evidence: `python scripts/check-evidence.py --task GZ-005`; Exit Code: 0.
- unaffected: `git diff --exit-code 95dc9d7cec927a753e8017cd3b509ebfee681b72 HEAD -- specs/coordination/task-completions.yaml specs/tasks/GZ-010.md evidence/GZ-010 specs/tasks/OPS-003.md evidence/OPS-003 specs/tasks/OPS-004.md evidence/OPS-004 specs/poc specs/requirements scripts tests AGENTS.md`; Exit Code: 0.
- docs: `python scripts/check-markdown.py`; Exit Code: 0.

## Exact original byte inventory

| Logical entry | Bytes | Physical SHA-256 |
|---|---:|---|
| clean-after.txt | 102 | e288ada274643a33d139afe46dba8c7fc0aa9d6531ce699882e05f11338d745e |
| clean-before.txt | 102 | e288ada274643a33d139afe46dba8c7fc0aa9d6531ce699882e05f11338d745e |
| coordination.txt | 384 | e35798eb0b637f97768863b02eeaca466bc942ddd8918637640ba95f552f3dc0 |
| docs.txt | 164 | f1f5801944da08cc3423b8021174bb0244da768eeba0e1f7ff22a29cec06fa7c |
| evidence.txt | 196 | d46f467bf517c115c9d22cfc116ed8a9d18c9d216960a87b94605000ec77fb1b |
| finalization.txt | 343 | 7f436344cd2909947a3b84e9fa975582b217fb79211caeab25cbf456bedf934d |
| history.txt | 473 | 0baeb142718b2a2f2ee2bba05e13f4cecdb245d0cfbd1409a767c88d7ee49ec6 |
| integrity.txt | 418 | 9232fa55230ab24067ccf919375d6d2bf04849c1d06eaeb3097e8f0d61b7ca66 |
| lifecycle.txt | 582 | b687679fae54be34ac8381428e70e74725c04aa06c60f02d6dd2a3a79c271ea8 |
| raw-lifecycle.txt | 491 | 4ac7458a5afc2139f77d500b7fca4278c1713673d64e440f9a6283a506c49512 |
| readiness.txt | 660 | b2dff8dd431622a4e109d156fcab9fd5d4f4c69bf1a2fef9fa48d65fa667ca0b |
| schemas.txt | 1747 | fc43efeb843d1df0403ce41be8ff25eebcb0bb91e5781b7af2e45fd9ed1f9e6b |
| scope.txt | 5394 | 7ea90875ed3b02e7414ec4e1b76c50294d17cc096cf9abec80206fbe3566858b |
| source.txt | 41 | 1412c611c5d40271520b7ae9c41c02b565671507c83a71bdc8a85747e6668757 |
| status.json | 248 | f05a083a43750fdec43fe6cb958fd7e648833f51db982e7e571c80a1e2f62833 |
| task.txt | 260 | 45d63fa4e2e32debde7460cd8398ab697c8613714bc80647adde9fcdbd333578 |
| transitions.txt | 425 | ecbeda122ac2a7c2ec46f538a6868e71520ca58cd56879371afcccf26780f60a |
| tree.txt | 41 | e948d0a44033a9f68329ab2569d7f35e26898817c4e42def6bc61ff3c6afe7be |
| unaffected.txt | 361 | 2fc2977fa90f46b8396ded778422f6d30a4c0d07b3bdb12ae06049c6f70c1c18 |
| verification-worktrees-before.json | 961 | 5637cb2a2fa99deef3c899cf501d046c5cd9e3d13acdcd16b659d4c0ec8c7c4a |
| verification-worktrees.json | 946 | dfa8fbeba73e7f0d4aff1548ebda2f0547326462a2a607d27853f034bf6e2182 |
| gz005-ci637.txt | 235077 | c44299fc061b5da4b0a096403f85ef490c253bd8f65a0e17d5efc2a28b93d08f |
| gz005-ci637-proof.json | 8946 | 10f52963fd8977f9ab8d7db0dd8a3cd3e14725dcecb6a5507b1f8cd440c06cb6 |
| gz005-ci637-official-run.json | 14679 | 20250e00eb48f5d5f6c975004a25d05509ed6c223a6aea0e8ca9805f6f498f18 |
| gz005-ci637-official-job.json | 7505 | 30a42e832d974589eb68568475ffa3c8c8360d8c6769fa78283e09482f4752fa |
| gz005-ci637-attempt1-cancelled.txt | 235076 | fb1dd3d5d3fcc41ca713dad95421df00906691c7ecc6e9cd2af2b0bb9e0ba7a0 |
| gz005-ci637-attempt1-cancelled-proof.json | 1036 | 8c5aab622a481d5df6df1fcc190e6fb330e0100da23abcb62428fd1e8ab1f0ba |
| gz005-ci637-attempt1-cancelled-official-run.json | 14597 | 7e35699886f447fbf565087690d64b03bfc5bd6558f0a7c231990afac0132fba |
| gz005-ci637-attempt1-cancelled-official-job.json | 7505 | b18512ccfe6d4e0c9b85554cbde03176583ab451c8f0c1455da0959f2efb2de9 |
| gz005-independent-review-dirty-proof.json | 32635 | 01831ea80d8745769865a1842af404d6ffefd466c19288db07a025c9f1ae6192 |
| gz005-independent-103139d-review-source-proof.json | 13400 | c2b71e4c8f7dcea4c607fccc6c09eabeb8f57eccbabdf2bc8dc64f1605c5c7af |
| gz005-independent-103139d-final-integration-proof.json | 4858 | adb099c51ec709578b6c64242590e1886a84170090cee7aac94069e798e5f1c4 |
| gz005-pr83-actual-merge.json | 123 | 3877b771d47070e5fd9f48b583795dbef3eba1f92375aa3fc4304bca0882c18f |
| gz005-reservation-pr70-official-receipt.json | 2278 | ca081bd9eb49bed40548b22930f19c522317aee6cece0722b15bfbe3e8d63783 |
| gz005-ci637-attempt1-check-annotations.json | 1550 | c0d16f1efef91e77408c9a8dbddb01897e2eaa4f47bcdd6f8f03a1017ae32a62 |
| actual-review-main-acceptance.json | 9206 | a49e8fae9e1ef117318ed13db5d0cb51633beb39d8e758f70f975dfbce20da73 |
| actual-review-main-ci.txt | 221858 | 7810a4b90fc200871c4e81c7319b3f98c8ac9f70cbd888761a04e80765009884 |
| actual-review-main-ci-proof.json | 9519 | 2f3822ae14fb55f77c040cdb13db21fa3b137dd69f7338ed3682c6f2072f2e0c |

## Verify and read the bundle

```python
import base64, hashlib, json, zlib
from pathlib import Path
bundle = json.loads(Path("raw-results.bundle.json").read_text(encoding="utf-8"))
for record in bundle["records"]:
    original = zlib.decompress(base64.b64decode(record["originalPhysicalBytesZlibBase64"]))
    assert len(original) == record["originalPhysicalSize"]
    assert hashlib.sha256(original).hexdigest() == record["originalPhysicalSha256"]
    print(record["path"], "verified")
    # original contains the exact retained source bytes for inspection/export.
```
