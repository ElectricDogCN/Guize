# {{TASK_ID}} Multi-Agent Execution Prompt

## Assigned role

- Role: `{{ROLE}}`
- Task: `{{TASK_ID}}`
- Base commit: `{{BASE_COMMIT}}`
- Work branch: `{{WORK_BRANCH}}`
- Coordination mode: `{{COORDINATION_MODE}}`

## Non-negotiable execution order

1. Read the embedded `AGENTS.md` and Never Rules first.
2. Resolve all facts using the repository authority precedence.
3. Verify `HEAD`, base commit, task branch and dependency state before writing.
4. Modify only declared exclusive/shared paths.
5. Treat contract inputs as read-only unless they are listed as task outputs and within scope.
6. Stop rather than guess when requirements, contracts or ADRs conflict.
7. Execute the Task Spec validation commands and preserve real outputs.
8. Update Handoff and canonical Evidence before requesting review.
9. Do not merge, deploy, push production changes or weaken gates without explicit authorization.

## Path ownership

### Exclusive

{{EXCLUSIVE_PATHS}}

### Shared integration paths

{{SHARED_PATHS}}

Shared paths are written only by the declared Integrator or in the recorded integration order.

## Dependencies

{{DEPENDENCIES}}

## Contract inputs

{{CONTRACT_INPUTS}}

## Contract outputs

{{CONTRACT_OUTPUTS}}

## Role-specific responsibility

{{ROLE_RESPONSIBILITY}}

## Required handoff

Write `{{HANDOFF_PATH}}` with:

- Baseline;
- Delivered Outputs;
- Validation with commands and observed results;
- Integration Notes;
- Known Gaps;
- Rollback.

## Embedded repository context

{{EMBEDDED_CONTEXT}}
