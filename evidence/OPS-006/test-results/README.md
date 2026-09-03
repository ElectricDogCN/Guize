# OPS-006 Registration Test Results

## Phase

Metadata-only bootstrap Registration. No Registration implementation test is reported as PASS in this file.

## Exact run

- Source HEAD: `b216f84368b54e631dce0b57b46b14cf5424e068`
- Pull request: #53
- Workflow run: `33720823036`
- Job: `100539417786`
- Workflow result: failure, as expected for a baseline without Registration support

## Passed controls

The exact run passed checkout, dependency installation, Python import/compile, pytest collection, Task context, skip audit, Markdown, YAML/Schema, secret scanning, Evidence, Evidence integrity, Task/branch linkage, spec sync, parent-directory checks, CI static checks, Program Plan schema, Program Plan integrity, Program Plan history and Program Plan transition checks.

The governance suite collected 259 tests; 257 passed.

## Classified failures

1. `check-task-file.py` rejects `status: planned` for a schemaVersion 2 Registry Task.
2. `run-agent-coordination-gate.py` rejects `planned` as an unsupported dispatcher state.
3. `run-task-scope-gate.py` rejects `planned` as an unsupported dispatcher state.
4. `check-program-lifecycle-guards.py` treats the append-only GZ-020 dependency attachment as an ordinary mutation and requires a current GZ-020 Task Spec.
5. `check-project-readiness.py` counts completed GZ-004 against W1 capacity, so GZ-004 + GZ-010 + planned OPS-006 exceed two slots.
6. The only two failing governance tests are repository-state assertions reflecting items 4 and 5.

## Contract refinement

OPS-006 future implementation now covers Project Readiness. The accepted rule is not “ignore planned tasks” and not “increase capacity.” Only terminal `completed` and `cancelled` tasks release structural Wave occupancy. All other states remain counted, and Active Work/Reservation concurrency enforcement remains unchanged.

## Blocker rule

Any final-HEAD failure outside these explicitly registered Registration surfaces—including schema, Program Integrity, Evidence, secret, syntax, collection, unrelated tests, unexpected paths or identity drift—is a blocker. The exact final HEAD must be rerun and reclassified after metadata amendments.