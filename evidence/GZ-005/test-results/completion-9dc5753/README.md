# Prior actual Completion execution 9dc5753

Source:9dc57530c773c2753cc7047762a85ac00b381501

Tree:14163ff7a756ab2889ba5a3dce9ddc6d352d2900

Base:8f2beb00c568ecb79c8ae0204f36fe445599fc37

All15 exit0; full make527 passed in717.57s, nonempty527-case JUnit zero failures/errors/skips. Official CI639 run38058113810/job114230632954 attempt1 success:527 passed in683.45s, no test skips and every job step successful. Synthetic checkout26c8459fca48c4000a050c9fc598766cf3dc2f0f is not actual main.

These are actual execution facts only. Three evidence findings require correction; source9dc is not finally approved for integration. Successor tests/CI remain pending. Full V1/runtime/POCs remain incomplete.

Original physical bytes are retained in raw-results.bundle.json, not loose files. Recover originalPhysicalBytesZlibBase64 using Base64 then zlib; verify originalPhysicalSize and originalPhysicalSha256. The first content receipt is historical and does not override the subsequent thread disposition.

## Executed commands

- task: python scripts/check-task-file.py --task GZ-005; Exit Code:0.
- readiness: python scripts/check-project-readiness.py; Exit Code:0.
- schemas: python scripts/check-schemas.py; Exit Code:0.
- integrity: python scripts/check-program-plan-integrity.py --base-ref 8f2beb00c568ecb79c8ae0204f36fe445599fc37; Exit Code:0.
- history: python scripts/check-program-plan-history.py --base-ref 8f2beb00c568ecb79c8ae0204f36fe445599fc37 --head-ref HEAD --task GZ-005 --branch-name chore/GZ-005-openapi-completion; Exit Code:0.
- transitions: python scripts/check-program-plan-transitions.py --base-ref 8f2beb00c568ecb79c8ae0204f36fe445599fc37 --head-ref HEAD --task GZ-005 --branch-name chore/GZ-005-openapi-completion; Exit Code:0.
- finalization: python scripts/check-program-plan-finalization.py --base-ref 8f2beb00c568ecb79c8ae0204f36fe445599fc37 --task GZ-005; Exit Code:0.
- raw-lifecycle: python scripts/check-program-lifecycle-guards.py --base-ref 8f2beb00c568ecb79c8ae0204f36fe445599fc37 --head-ref HEAD --task GZ-005 --branch-name chore/GZ-005-openapi-completion; Exit Code:0.
- lifecycle: python scripts/run-program-lifecycle-gate.py --base-ref 8f2beb00c568ecb79c8ae0204f36fe445599fc37 --head-ref HEAD --task GZ-005 --branch-name chore/GZ-005-openapi-completion; Exit Code:0.
- coordination: python scripts/run-agent-coordination-gate.py --base-ref 8f2beb00c568ecb79c8ae0204f36fe445599fc37 --head-ref HEAD --task GZ-005 --branch-name chore/GZ-005-openapi-completion; Exit Code:0.
- scope: python scripts/run-task-scope-gate.py --task GZ-005 --base 8f2beb00c568ecb79c8ae0204f36fe445599fc37; Exit Code:0.
- evidence: python scripts/check-evidence.py --task GZ-005; Exit Code:0.
- unaffected: git diff --exit-code 8f2beb00c568ecb79c8ae0204f36fe445599fc37 HEAD -- specs/tasks/GZ-010.md evidence/GZ-010 specs/tasks/OPS-003.md evidence/OPS-003 specs/tasks/OPS-004.md evidence/OPS-004 specs/poc poc/README.md specs/requirements contracts specs/contracts scripts tests AGENTS.md; Exit Code:0.
- verify: make verify TASK=GZ-005 BASE=8f2beb00c568ecb79c8ae0204f36fe445599fc37 HEAD_REF=HEAD BRANCH=chore/GZ-005-openapi-completion; Exit Code:0.
- docs: python scripts/check-markdown.py; Exit Code:0.

## Exact original byte inventory

| Logical entry | Bytes | SHA-256 |
|---|---:|---|
| clean-after.txt | 102 | 81f3f5d021706fe76e3f29937433ff39bbbf4688854317af5d639a756538aa69 |
| clean-before.txt | 102 | 81f3f5d021706fe76e3f29937433ff39bbbf4688854317af5d639a756538aa69 |
| coordination.txt | 533 | 90fb410f964c20f3ed901699d0d3e8cf30e5b14d5d280780c034a361e1970e87 |
| docs.txt | 164 | 0b7b80e0299b2244add71f4d90703b4dd9b5514fc27df2fb40ca57d56aaf71e3 |
| evidence.txt | 196 | 79f7f4fe2760ea46a8fcbdeb56eef9e56afcc15526991db7a6d81d53a41741d1 |
| finalization.txt | 343 | 23054d74c7449f0d7a7372ec348a4375e0e0375861e70815013c94ad827396a5 |
| history.txt | 475 | b5415b6e6d94251563abc9c0838b517971629f8415fe51938cca2ba1294f416d |
| integrity.txt | 418 | 8b0a58b8654b289ca0f7f583dfbe71216a68592b293dafaed031f73b592529b5 |
| lifecycle.txt | 584 | 8bb834cc8092e1fc3f359dff2bb7a3332821bfb26f4be60140b4122cf4940c4c |
| live-official-api.json | 950 | 59896f8b05a84f3b3a996ba2076ccd4e77ed6b5a24cbdba1b879d69a9a6b9d13 |
| make-governance.xml | 82917 | 33eacf72eb69cc15026948c56d467aec660c786a6563ecdfdfd33772dccadeaa |
| raw-lifecycle.txt | 493 | 535008381e4d9c775bdfb4905097e078f1be177ca878cca400d2b5d619fbf19c |
| readiness.txt | 660 | f2015b3c46ce63619b4770706ca1d71cfb2e85656e3150190e369acfee62973e |
| schemas.txt | 1681 | 1e8100c7d48b2a1327f367180c9857456bd0066b9f4dd04634609df3fdc93a24 |
| scope.txt | 316 | 351d1d67073f31493c0fb99eb9fae2c80ede777e844681475fc0713a8eaa15c1 |
| source.txt | 41 | cf9f6c34980ff5717b249f86df056f4ccb4f96bcd244d77d82255cc6acfe9998 |
| status.json | 263 | 2b9a40f85246b86a8e2040411e5bfcca2553545332101d24ea61677e10218ee3 |
| task.txt | 260 | 55cb0db61283bd3b2396eeda40db2bb6be6b851c9c53670b5b5d6a16791f2781 |
| transitions.txt | 427 | db744f719b918d0e691ce0d5ac7e2996331315e412905cfe7e858845517e798a |
| tree.txt | 41 | d51a46f792a9e9e7bd2eb7b88d9f5182489b4dd8e27da87b7674ce09c2b52850 |
| unaffected.txt | 360 | 225b95be62c89a789ab8d7ad3f74d46f2b007a7ef223c76d35f7fcac733ddb4e |
| verification-worktrees.json | 1813 | 46fdcbefa7610ad1aa34be4818dd4e878b69924cd484b88e0b327db7aedba05a |
| verify.txt | 77906 | eafb69ba1887cd5cbaffb18132e4f3eb3f2be85face6f6fbf838f675bc709351 |
| gz005-ci639.txt | 230140 | abcc8618b6e991fe86812181a14ab95f1ed064f4fd7a837377f9e585de86b28e |
| gz005-ci639-proof.json | 1179 | 204896b315749c3d77aeeba71ab66ef24a3bceeab90f384f72354ecdd0d7efda |
| gz005-ci639-official-run.json | 14656 | 2ecdc5048b587e0063061e7f4e9e2a28face33be1e68204321339179aad20262 |
| gz005-ci639-official-job.json | 7255 | 8b58e818b4b6c70564c32993a4071dfb55b7125309a6dfafa07aef17fcc076c7 |
| gz005-pr84-9dc5753-three-threads.json | 5499 | a1ff22d2d11df70f60ded700aefc0e711d8a414e6666fa10ee16c2d3b6899e4b |
| gz005-independent-9dc5753-actual-source-content-proof.json | 3351 | 1beff284bfb7d3a6b9349253ff683233eee059ce4e90800ec5b2df13fafa5e00 |
| gz005-independent-9dc5753-pr84-three-thread-disposition.json | 9367 | acacd6c084f9916173f25b07df3e08a2d2f1382bbb32ff1d47a231473cc5307a |
