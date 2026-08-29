# GZ-014 Test Results

## Reservation phase

### Initial reservation run

Result: failed.

Observed failures:

- Project Readiness: four Requirement/Module mappings were not symmetric.
- Agent Coordination: the “no shared path” sentence included inline code and was parsed as a fake path.

These failures were retained as defect evidence and fixed; the checks were not skipped or weakened.

### Governance Gate run #109

Result: success.

Observed successful checks:

- task context and Task Spec;
- Project Readiness;
- Agent Coordination;
- 121 governance tests and skip audit;
- Markdown;
- Schema;
- Secret scan;
- Evidence and Evidence integrity;
- PR/task linkage;
- Scope;
- Spec Sync;
- repository boundary and workflow static validation.

Reservation PR #18 then merged as `d731ce09fbf2535948bc1864490539d06ce1f139`.

## Implementation phase

### Governance Gate run #111

Result: failed.

All checks passed except Schema Validation. The exact failure was:

```text
specs/coordination/active-work.yaml violates
specs/coordination/active-work.schema.yaml at tasks/0/lease/acquiredAt:
2026-08-29 02:07:00+00:00 is not of type 'string'
```

Root cause: unquoted ISO timestamps were converted by PyYAML into `datetime` objects. The fix quoted `acquiredAt` and `expiresAt` in the registry. The Schema remains string-only.

### Latest implementation run

The authoritative result is the GitHub Actions Governance Gate attached to the latest PR #21 HEAD. At the time this file is written, later evidence-only commits have triggered another run; no success is claimed until that run completes.

## Tests still required before integration

```bash
python scripts/check-task-file.py --task GZ-014
python scripts/check-agent-coordination.py --task GZ-014 --base-ref origin/main --head-ref HEAD --branch-name chore/GZ-014-program-plan-reconciliation
python scripts/check-project-readiness.py
python scripts/check-schemas.py
python -m pytest tests/governance/ -v
python scripts/check-evidence.py --task GZ-014
make verify TASK=GZ-014 BASE=origin/main BRANCH=chore/GZ-014-program-plan-reconciliation
```

Independent Review, review-thread resolution and an expected-HEAD merge check are also required.
