# GZ-001 Repository Baseline, Agent Execution Harness and Governance Gate Initialization Spec

## Why

The current 归泽・Guize repository is a document-only solution repository. It lacks an executable agent task harness, governance check scripts, CI gates, dynamic prompt generation, structured evidence framework, and repository baseline configurations (Makefile, .editorconfig, .gitignore, .gitattributes). This prevents Codex, Trae Solo/Work and other agents from executing tasks in a controlled, verifiable and reproducible manner. This task converts the repository into a formal engineering repository without implementing any business capabilities.

## What Changes

- Create formal task specification at `specs/tasks/GZ-001-repository-baseline.md`
- Create Evidence directory `evidence/GZ-001/` with required files from real execution
- Create dynamic prompt system under `prompts/` (README, archive, templates)
- Create prompt renderer `scripts/render-agent-prompt.py` with tests
- Create governance check scripts under `scripts/`:
  - `check-task-file.py`
  - `check-task-scope.py`
  - `check-evidence.py`
  - `check-pr-task-link.py`
  - `check-spec-sync.py`
- Create governance script tests under `tests/governance/`
- Create or improve root `Makefile` with `help`, `docs-check`, `schema-check`, `secret-scan`, `governance-test`, `agent-prompt`, `task-verify`, `verify`
- Create or improve `.editorconfig`, `.gitattributes`, `.gitignore`
- Create or improve GitHub Issue templates (agent-task, poc, bug, feature, architecture-decision, security)
- Create or improve PR template
- Create governance CI `.github/workflows/governance-gate.yml`
- Create ADR for repository-native agent task harness if new long-term decisions are formed
- Update `rules/never-rules.md` and `rules/never-rules-changelog.md` only if new never-rules are discovered
- Create `.agent/.gitkeep` and ignore `.agent/*.md` in `.gitignore`
- Record any document conflicts in `evidence/GZ-001/conflicts.md`

## Impact

- Affected capabilities: All future agent-driven tasks, CI gates, PR reviews, evidence collection
- Affected files/systems: Root configuration, `scripts/`, `tests/governance/`, `prompts/`, `.github/`, `evidence/GZ-001/`, `adr/`, `rules/`, `specs/tasks/`

## ADDED Requirements

### Requirement: Task Specification
The system SHALL provide a machine-readable task specification at `specs/tasks/GZ-001-repository-baseline.md` containing id, title, titleZh, type, status, baseBranch, workBranch, evidencePath, background, goals, allowed scope, forbidden scope, implementation requirements, acceptance criteria, required tests, risks, rollback method and follow-up task boundaries.

#### Scenario: Valid task spec
- **WHEN** a user or agent reads `specs/tasks/GZ-001-repository-baseline.md`
- **THEN** all required fields are present and consistent with this spec

### Requirement: Dynamic Prompt System
The system SHALL provide a `prompts/` directory with a README, an archive directory, and templates for task-execution, task-fix-ci, task-review, poc-execution, and release-verification.

#### Scenario: Task execution template renders correctly
- **WHEN** `scripts/render-agent-prompt.py` is invoked with valid parameters
- **THEN** it produces a prompt file substituting `{{TASK_ID}}`, `{{TASK_FILE}}`, `{{ISSUE_REFERENCE}}`, `{{BRANCH_NAME}}`, `{{BASE_BRANCH}}`, `{{EXECUTION_MODE}}`

### Requirement: Prompt Renderer Script
The system SHALL provide `scripts/render-agent-prompt.py` using Python standard library, supporting CLI arguments `--task`, `--branch`, `--base`, `--mode`, `--issue`, `--output`, reading task metadata from the task spec, validating required files, returning non-zero on missing fields, and outputting a generation summary.

### Requirement: Governance Check Scripts
The system SHALL provide five governance scripts under `scripts/`:
1. `check-task-file.py` — validate required fields, ID format, branch name, evidence path, scope, acceptance criteria, validation commands
2. `check-task-scope.py` — validate changed files against task allowed/forbidden scope using git diff, support directory wildcards, exit non-zero on out-of-scope changes
3. `check-evidence.py` — validate evidence directory contains non-empty required files with task ID, test results with commands and exit codes, rollback with executable steps
4. `check-pr-task-link.py` — validate PR title/body/branch contain task ID, task file exists, branch matches task file, evidence path exists; work locally without GitHub API dependency
5. `check-spec-sync.py` — check spec synchronization for contracts, events, deployment, rules, ADR, workflows changes

All scripts SHALL have clear help, explicit exit codes, structured errors, unit tests, run on Windows/Linux common Python environments, and not depend on real GitHub tokens.

### Requirement: Governance Tests
The system SHALL provide tests under `tests/governance/` covering at least:
- Valid task file passes
- Missing task ID fails
- Invalid branch name fails
- In-scope changes pass
- Out-of-scope changes fail
- Missing evidence files fail
- Empty evidence files fail
- Prompt renders correctly
- Unknown template variables fail
- Never Rules updated but changelog not updated fails
- PR missing task ID fails

Tests SHALL use temporary directories and fixtures, not depend on real repository state.

### Requirement: Makefile
The system SHALL provide a root `Makefile` with targets:
- `help` — show available targets
- `docs-check` — basic docs validation
- `schema-check` — schema validation
- `secret-scan` — secret scanning
- `governance-test` — run governance script tests
- `agent-prompt TASK=GZ-001` — generate agent prompt
- `task-verify TASK=GZ-001` — run task file, scope, evidence, spec-sync checks and governance tests
- `verify` — run all available baseline gates

`make verify` SHALL clearly show missing optional tools, fail for required missing tools, and never auto-download untrusted remote scripts.

### Requirement: Repository Baseline Configuration
The system SHALL provide `.editorconfig`, `.gitattributes`, `.gitignore` enforcing:
- UTF-8 for text files
- Explicit line ending rules
- Ignore common build artifacts
- Ignore `.agent/*.md` but keep `.agent/.gitkeep`
- Ignore `.env`, do not ignore `.env.example`
- Ignore local IDE, Python cache, temporary test artifacts
- Do not ignore formal Evidence, Schema and docs

### Requirement: GitHub Templates
The system SHALL provide:
- `.github/ISSUE_TEMPLATE/agent-task.yml` requiring: task ID, requirement source, goal, allowed scope, forbidden scope, acceptance criteria, test method, risk, rollback, evidence path
- `.github/ISSUE_TEMPLATE/poc.yml`
- `.github/ISSUE_TEMPLATE/bug.yml`
- `.github/ISSUE_TEMPLATE/feature.yml`
- `.github/ISSUE_TEMPLATE/architecture-decision.yml`
- `.github/ISSUE_TEMPLATE/security.yml`
- `.github/pull_request_template.md` containing: linked issue, task ID, change summary, changed files, out-of-scope changes, API impact, DB impact, config impact, security impact, test commands, test results, evidence, rollback, doc sync status, ADR needed, Never Rules evolution needed, human review checklist

### Requirement: Governance CI
The system SHALL provide `.github/workflows/governance-gate.yml` triggered on PR, push to governance files, and manually. It SHALL include steps for: checkout, setup Python, task file validation, governance script tests, Markdown basic check, Markdown relative link check, YAML/JSON schema check, secret scan, evidence check, task-branch linkage check, scope check, and governance report generation. It SHALL NOT hardcode real secrets, auto-deploy to production, or auto-merge PRs.

### Requirement: Evidence
The system SHALL create `evidence/GZ-001/` containing real execution artifacts:
- `README.md` — summary
- `scope.md` — what was in scope
- `changed-files.md` — added/modified/deleted categorization
- `commands.md` — commands with timestamp, directory, exit code, key output
- `test-results.md` — table of check item, command, exit code, result, notes
- `assumptions.md` — explicit assumptions
- `conflicts.md` — document conflicts discovered
- `risks.md` — risks
- `rollback.md` — safe rollback steps
- `follow-ups.md` — follow-up tasks

### Requirement: ADR and Never Rules
If new long-term architecture decisions are formed (task spec format, prompt template mechanism, evidence directory structure, task scope check mechanism, Makefile governance entry), the system SHALL add a new ADR `adr/0012-adopt-repository-native-agent-task-harness.md` with context, decision, alternatives, consequences, risks, rollback/alternative conditions. The system SHALL NOT rewrite old ADRs to hide new decisions.

If `rules/never-rules.md` is updated, `rules/never-rules-changelog.md` MUST be synchronized, with automated checking.

## MODIFIED Requirements

None.

## REMOVED Requirements

None.

## Known Conflicts

1. **Evidence structure**: `AGENTS.md` Section 13 prescribes `summary.md`, `commands.txt`, `test-results/`, etc. The task prompt requires `README.md`, `scope.md`, `changed-files.md`, `commands.md`, `test-results.md`, `assumptions.md`, `risks.md`, `rollback.md`, `follow-ups.md`. Resolution: GZ-001 will create the prompt-required files. The `commands.md` serves the same purpose as `commands.txt` with richer structure. Future tasks may reconcile the two structures via ADR if needed. This conflict is recorded in `evidence/GZ-001/conflicts.md`.
