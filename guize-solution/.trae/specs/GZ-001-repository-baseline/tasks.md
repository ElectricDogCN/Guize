# Tasks for GZ-001 Repository Baseline and Agent Execution Harness

- [ ] Task 1: Prepare execution understanding and establish work branch
  - [ ] SubTask 1.1: Read authoritative files (AGENTS.md, README.md, MANIFEST.md, Never Rules, key docs)
  - [ ] SubTask 1.2: Check Git status and create branch `chore/GZ-001-repository-baseline`
  - [ ] SubTask 1.3: Output execution understanding (goals, current state, allowed/forbidden scope, steps, acceptance criteria, risks)
  - [ ] SubTask 1.4: Record any document conflicts in `evidence/GZ-001/conflicts.md`

- [ ] Task 2: Create formal task specification and Evidence skeleton
  - [ ] SubTask 2.1: Create `specs/tasks/GZ-001-repository-baseline.md` with full YAML front matter and sections
  - [ ] SubTask 2.2: Create `evidence/GZ-001/` skeleton (README.md, scope.md, changed-files.md, commands.md, test-results.md, assumptions.md, risks.md, rollback.md, follow-ups.md)

- [ ] Task 3: Create dynamic prompt system
  - [ ] SubTask 3.1: Create `prompts/README.md`
  - [ ] SubTask 3.2: Create `prompts/archive/GZ-001-project-bootstrap.md`
  - [ ] SubTask 3.3: Create `prompts/templates/task-execution.md` with required variables
  - [ ] SubTask 3.4: Create `prompts/templates/task-fix-ci.md`
  - [ ] SubTask 3.5: Create `prompts/templates/task-review.md`
  - [ ] SubTask 3.6: Create `prompts/templates/poc-execution.md`
  - [ ] SubTask 3.7: Create `prompts/templates/release-verification.md`

- [ ] Task 4: Create prompt renderer and agent directory
  - [ ] SubTask 4.1: Create `scripts/render-agent-prompt.py` with CLI, template rendering, validation, and summary output
  - [ ] SubTask 4.2: Create `.agent/.gitkeep`
  - [ ] SubTask 4.3: Update `.gitignore` to ignore `.agent/*.md` but keep `.gitkeep`

- [ ] Task 5: Create governance check scripts
  - [ ] SubTask 5.1: Create `scripts/check-task-file.py`
  - [ ] SubTask 5.2: Create `scripts/check-task-scope.py`
  - [ ] SubTask 5.3: Create `scripts/check-evidence.py`
  - [ ] SubTask 5.4: Create `scripts/check-pr-task-link.py`
  - [ ] SubTask 5.5: Create `scripts/check-spec-sync.py`

- [ ] Task 6: Create governance script tests
  - [ ] SubTask 6.1: Create `tests/governance/` with fixtures
  - [ ] SubTask 6.2: Implement tests for all 11 required scenarios

- [ ] Task 7: Create Makefile and repository baseline configs
  - [ ] SubTask 7.1: Create root `Makefile` with all required targets
  - [ ] SubTask 7.2: Create/improve `.editorconfig`
  - [ ] SubTask 7.3: Create/improve `.gitattributes`
  - [ ] SubTask 7.4: Create/improve `.gitignore`

- [ ] Task 8: Create GitHub templates
  - [ ] SubTask 8.1: Create `.github/ISSUE_TEMPLATE/agent-task.yml`
  - [ ] SubTask 8.2: Create `.github/ISSUE_TEMPLATE/poc.yml`
  - [ ] SubTask 8.3: Create `.github/ISSUE_TEMPLATE/bug.yml`
  - [ ] SubTask 8.4: Create `.github/ISSUE_TEMPLATE/feature.yml`
  - [ ] SubTask 8.5: Create `.github/ISSUE_TEMPLATE/architecture-decision.yml`
  - [ ] SubTask 8.6: Create `.github/ISSUE_TEMPLATE/security.yml`
  - [ ] SubTask 8.7: Create/improve `.github/pull_request_template.md`

- [ ] Task 9: Create governance CI
  - [ ] SubTask 9.1: Create `.github/workflows/governance-gate.yml`

- [ ] Task 10: Create ADR and update rules if needed
  - [ ] SubTask 10.1: Create `adr/0012-adopt-repository-native-agent-task-harness.md`
  - [ ] SubTask 10.2: Only update `rules/never-rules.md` and `rules/never-rules-changelog.md` if new never-rules are discovered

- [ ] Task 11: Execute verification and populate Evidence
  - [ ] SubTask 11.1: Run `make agent-prompt TASK=GZ-001`
  - [ ] SubTask 11.2: Run `make task-verify TASK=GZ-001`
  - [ ] SubTask 11.3: Run `make verify`
  - [ ] SubTask 11.4: Run `git status`, `git diff --stat main...HEAD`, `git diff main...HEAD`
  - [ ] SubTask 11.5: Fix any in-scope issues
  - [ ] SubTask 11.6: Update all Evidence files with real execution data

- [ ] Task 12: Final report and stop
  - [ ] SubTask 12.1: Output final report in required format
  - [ ] SubTask 12.2: Stop without executing next task

# Task Dependencies

- Task 2 depends on Task 1
- Task 3 depends on Task 2
- Task 4 depends on Task 3
- Task 5 depends on Task 2
- Task 6 depends on Task 5
- Task 7 can run in parallel with Tasks 3-6 once Task 2 is done
- Task 8 can run in parallel with Tasks 3-7 once Task 2 is done
- Task 9 depends on Task 5 and Task 6
- Task 10 depends on Tasks 3-9
- Task 11 depends on Tasks 4-10
- Task 12 depends on Task 11
