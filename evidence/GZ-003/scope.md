# GZ-003 Scope Evidence

## Allowed

- Requirements/design audit documents;
- collaboration specifications, schemas, descriptors and program plan;
- GZ-003 Task Spec and Evidence;
- multi-agent prompt templates and renderer;
- collaboration checker, tests and independent workflow;
- README collaboration entry;
- multi-agent work package Issue template.

## Forbidden

- Business implementation;
- existing business machine-contract changes under `contracts/**`;
- runtime deployment changes under `deployment/**`;
- rewriting ADR history;
- weakening the existing Governance Gate;
- direct changes to `main`.

The authoritative path list is in `specs/tasks/GZ-003.md` and `specs/collaboration/tasks/GZ-003.yaml`. Final changed-file verification must use Git diff against `origin/main`.
