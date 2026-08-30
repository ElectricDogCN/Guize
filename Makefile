SHELL := /bin/sh
PYTHON ?= $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
TASK ?= GZ-001
BRANCH ?= $(shell git branch --show-current 2>/dev/null)
BASE ?= origin/main
HEAD_REF ?= HEAD
MODE ?= implement
ISSUE ?=

.PHONY: help docs-check schema-check secret-scan readiness-check program-integrity-check coordination-check governance-test agent-prompt task-verify verify

help:
	@echo "Guize governance commands"
	@echo "  make docs-check"
	@echo "  make schema-check"
	@echo "  make secret-scan"
	@echo "  make readiness-check"
	@echo "  make program-integrity-check TASK=GZ-003 BASE=origin/main HEAD_REF=HEAD BRANCH=chore/GZ-003-name"
	@echo "  make coordination-check TASK=GZ-003 BASE=origin/main HEAD_REF=HEAD BRANCH=chore/GZ-003-name"
	@echo "  make governance-test"
	@echo "  make agent-prompt TASK=GZ-003 [BRANCH=...] [BASE=...] [MODE=...]"
	@echo "  make task-verify TASK=GZ-003 [BRANCH=...] [BASE=...] [HEAD_REF=...]"
	@echo "  make verify TASK=GZ-003 [BRANCH=...] [BASE=...] [HEAD_REF=...]"

docs-check:
	@echo "=== docs-check ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ ! -f scripts/check-markdown.py ]; then echo "MISSING: scripts/check-markdown.py not found"; exit 1; fi
	$(PYTHON) scripts/check-markdown.py

schema-check:
	@echo "=== schema-check ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ ! -f scripts/check-schemas.py ]; then echo "MISSING: scripts/check-schemas.py not found"; exit 1; fi
	$(PYTHON) scripts/check-schemas.py

secret-scan:
	@echo "=== secret-scan ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ ! -f scripts/check-secrets.py ]; then echo "MISSING: scripts/check-secrets.py not found"; exit 1; fi
	$(PYTHON) scripts/check-secrets.py

readiness-check:
	@echo "=== readiness-check ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ ! -f scripts/check-project-readiness.py ]; then echo "MISSING: scripts/check-project-readiness.py not found"; exit 1; fi
	$(PYTHON) scripts/check-project-readiness.py

program-integrity-check:
	@echo "=== program-integrity-check (TASK=$(TASK), BASE=$(BASE), HEAD_REF=$(HEAD_REF)) ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ ! -f scripts/check-program-plan-integrity.py ]; then echo "MISSING: scripts/check-program-plan-integrity.py not found"; exit 1; fi
	@if [ ! -f scripts/check-program-plan-history.py ]; then echo "MISSING: scripts/check-program-plan-history.py not found"; exit 1; fi
	@if [ ! -f scripts/check-program-plan-finalization.py ]; then echo "MISSING: scripts/check-program-plan-finalization.py not found"; exit 1; fi
	$(PYTHON) scripts/check-program-plan-integrity.py --base-ref $(BASE)
	@if [ -n "$(TASK)" ]; then \
		$(PYTHON) scripts/check-program-plan-history.py \
			--base-ref $(BASE) \
			--head-ref $(HEAD_REF) \
			--task $(TASK) \
			--branch-name $(BRANCH); \
		$(PYTHON) scripts/check-program-plan-finalization.py \
			--base-ref $(BASE) \
			--head-ref $(HEAD_REF) \
			--task $(TASK); \
	else \
		$(PYTHON) scripts/check-program-plan-history.py \
			--base-ref $(BASE) \
			--head-ref $(HEAD_REF); \
		$(PYTHON) scripts/check-program-plan-finalization.py \
			--base-ref $(BASE) \
			--head-ref $(HEAD_REF); \
	fi

coordination-check:
	@echo "=== coordination-check (TASK=$(TASK), BASE=$(BASE), HEAD_REF=$(HEAD_REF)) ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ ! -f scripts/run-agent-coordination-gate.py ]; then echo "MISSING: scripts/run-agent-coordination-gate.py not found"; exit 1; fi
	@if [ -n "$(TASK)" ]; then \
		$(PYTHON) scripts/run-agent-coordination-gate.py \
			--task $(TASK) \
			--base-ref $(BASE) \
			--head-ref $(HEAD_REF) \
			--branch-name $(BRANCH); \
	else \
		$(PYTHON) scripts/run-agent-coordination-gate.py; \
	fi

governance-test:
	@echo "=== governance-test ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ ! -d tests/governance ]; then echo "MISSING: tests/governance/ directory not found"; exit 1; fi
	$(PYTHON) -m pytest tests/governance/ -v

agent-prompt:
	@echo "=== agent-prompt (TASK=$(TASK)) ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ ! -f scripts/render-agent-prompt.py ]; then echo "MISSING: scripts/render-agent-prompt.py not found"; exit 1; fi
	@mkdir -p .agent
	$(PYTHON) scripts/render-agent-prompt.py \
		--task $(TASK) \
		--branch $(BRANCH) \
		--base $(BASE) \
		--mode $(MODE) \
		--issue $(ISSUE) \
		--output .agent/$(TASK)-prompt.md

task-verify:
	@echo "=== task-verify (TASK=$(TASK)) ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@echo "-- check-task-file --"
	@if [ ! -f scripts/check-task-file.py ]; then echo "MISSING: scripts/check-task-file.py not found"; exit 1; fi
	$(PYTHON) scripts/check-task-file.py --task $(TASK)
	@echo "-- check-program-integrity --"
	$(MAKE) program-integrity-check TASK=$(TASK) BASE=$(BASE) HEAD_REF=$(HEAD_REF) BRANCH=$(BRANCH)
	@echo "-- check-agent-coordination --"
	$(MAKE) coordination-check TASK=$(TASK) BASE=$(BASE) HEAD_REF=$(HEAD_REF) BRANCH=$(BRANCH)
	@echo "-- check-project-readiness --"
	$(MAKE) readiness-check
	@echo "-- check-task-scope --"
	@if [ ! -f scripts/run-task-scope-gate.py ]; then echo "MISSING: scripts/run-task-scope-gate.py not found"; exit 1; fi
	$(PYTHON) scripts/run-task-scope-gate.py --task $(TASK) --base $(BASE)
	@echo "-- check-evidence --"
	@if [ ! -f scripts/check-evidence.py ]; then echo "MISSING: scripts/check-evidence.py not found"; exit 1; fi
	$(PYTHON) scripts/check-evidence.py --task $(TASK)
	@echo "-- check-evidence-integrity --"
	@if [ ! -f scripts/check-evidence-integrity.py ]; then echo "MISSING: scripts/check-evidence-integrity.py not found"; exit 1; fi
	@REPORT=""; \
	if [ -f "evidence/$(TASK)/final-report-r5-clean-recovery.md" ]; then \
		REPORT="evidence/$(TASK)/final-report-r5-clean-recovery.md"; \
	else \
		REPORT=$$(find "evidence/$(TASK)" -maxdepth 1 -type f -name 'final-report-r*.md' -print 2>/dev/null | sort -V | tail -n 1); \
	fi; \
	if [ -z "$$REPORT" ] && [ -f "evidence/$(TASK)/final-report.md" ]; then REPORT="evidence/$(TASK)/final-report.md"; fi; \
	if [ -n "$$REPORT" ]; then \
		$(PYTHON) scripts/check-evidence-integrity.py --task $(TASK) --report "$$REPORT"; \
	else \
		echo "No final-report*.md exists for $(TASK); no commit claims require integrity validation."; \
	fi
	@echo "-- check-pr-task-link --"
	@if [ ! -f scripts/check-pr-task-link.py ]; then echo "MISSING: scripts/check-pr-task-link.py not found"; exit 1; fi
	$(PYTHON) scripts/check-pr-task-link.py --branch $(BRANCH)
	@echo "-- check-spec-sync --"
	@if [ ! -f scripts/check-spec-sync.py ]; then echo "MISSING: scripts/check-spec-sync.py not found"; exit 1; fi
	$(PYTHON) scripts/check-spec-sync.py --base $(BASE)
	$(MAKE) governance-test

verify:
	@echo "=== verify (TASK=$(TASK)) ==="
	$(MAKE) docs-check
	$(MAKE) schema-check
	$(MAKE) secret-scan
	$(MAKE) task-verify TASK=$(TASK) BRANCH=$(BRANCH) BASE=$(BASE) HEAD_REF=$(HEAD_REF)
