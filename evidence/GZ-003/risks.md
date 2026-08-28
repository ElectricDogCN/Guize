# GZ-003 Risks

## R1 Contract-free parallel coding

Multiple agents may independently invent fields, states and errors before OpenAPI/Event/DDL/Workflow contracts are frozen.

Mitigation: contract-first waves and Collaboration Gate.

## R2 Cross-branch path conflict

Git does not provide a real-time repository-wide file lock across branches.

Mitigation: one descriptor per task, planned descriptors merged before implementation, exclusive/shared path declarations and integration ownership.

## R3 Central coordination bottleneck

A single frequently edited registry would create merge conflicts.

Mitigation: per-task descriptors; Program Plan changes only through orchestration tasks.

## R4 Stale base and stale contracts

A long-running branch may pass local tests against obsolete contracts.

Mitigation: fixed base SHA, dependency checks, revalidation after base changes and small-batch integration.

## R5 Self-review

The same agent may implement and approve its own assumptions.

Mitigation: Owner and final Reviewer must be different declared roles and execution subjects.

## R6 Fabricated handoff

A generated summary may claim tests, commits or CI that did not occur.

Mitigation: Handoff requires observed commands/results; Evidence and GitHub remain authoritative.

## R7 Workflow adoption gap

The new Collaboration Gate does not execute for the PR that first introduces it because the workflow is not yet on the base branch.

Mitigation: GZ-003 is validated by the existing Governance Gate, direct checker execution, regression tests and independent review; the new gate becomes active for subsequent PRs after merge.

## R8 Over-constraining small fixes

A full multi-agent contract could be excessive for a tiny change.

Mitigation: `single-agent` mode remains available, but it still requires fixed scope, independent review and truthful Evidence.
