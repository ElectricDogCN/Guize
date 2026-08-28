SHELL := /bin/sh
PYTHON ?= $(shell command -v python3 2>/dev/null || command -v python 2>/dev/null)
TASK ?= GZ-001
BRANCH ?= $(shell git branch --show-current 2>/dev/null)
BASE ?= origin/main
MODE ?= implement
ISSUE ?=

.PHONY: help docs-check schema-check secret-scan governance-test agent-prompt task-verify verify

help:
	@echo "Guize governance commands"
	@echo "  make docs-check"
	@echo "  make schema-check"
	@echo "  make secret-scan"
	@echo "  make governance-test"
	@echo "  make agent-prompt TASK=GZ-001 [BRANCH=...] [BASE=...] [MODE=...]"
	@echo "  make task-verify TASK=GZ-001 [BRANCH=...] [BASE=...]"
	@echo "  make verify TASK=GZ-001"

docs-check:
	@echo "=== docs-check ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ ! -f scripts/check-markdown.py ]; then \
		echo "MISSING: scripts/check-markdown.py not found"; \
		exit 1; \
	fi
	$(PYTHON) scripts/check-markdown.py

schema-check:
	@echo "=== schema-check ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@$(PYTHON) - <<'PY'
import glob
import json
import sys
try:
    import yaml
except ImportError:
    print("MISSING: PyYAML is required for schema-check")
    sys.exit(1)
exit_code = 0
for path in glob.glob('.github/workflows/*.yml') + glob.glob('.github/workflows/*.yaml'):
    try:
        with open(path, encoding='utf-8') as handle:
            yaml.safe_load(handle)
        print(f"OK YAML: {path}")
    except Exception as exc:
        print(f"FAIL YAML: {path}: {exc}")
        exit_code = 1
for path in glob.glob('contracts/**/*.json', recursive=True):
    try:
        with open(path, encoding='utf-8') as handle:
            json.load(handle)
        print(f"OK JSON: {path}")
    except Exception as exc:
        print(f"FAIL JSON: {path}: {exc}")
        exit_code = 1
for path in glob.glob('contracts/**/*.yaml', recursive=True) + glob.glob('contracts/**/*.yml', recursive=True):
    try:
        with open(path, encoding='utf-8') as handle:
            yaml.safe_load(handle)
        print(f"OK YAML: {path}")
    except Exception as exc:
        print(f"FAIL YAML: {path}: {exc}")
        exit_code = 1
sys.exit(exit_code)
PY

secret-scan:
	@echo "=== secret-scan ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ ! -f scripts/check-secrets.py ]; then \
		echo "MISSING: scripts/check-secrets.py not found"; \
		exit 1; \
	fi
	$(PYTHON) scripts/check-secrets.py

governance-test:
	@echo "=== governance-test ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ -d tests/governance ]; then \
		$(PYTHON) -m pytest tests/governance/ -v; \
	else \
		echo "MISSING: tests/governance/ directory not found"; \
		exit 1; \
	fi

agent-prompt:
	@echo "=== agent-prompt (TASK=$(TASK)) ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ ! -f scripts/render-agent-prompt.py ]; then \
		echo "MISSING: scripts/render-agent-prompt.py not found"; \
		exit 1; \
	fi
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
	@if [ -f scripts/check-task-file.py ]; then \
		$(PYTHON) scripts/check-task-file.py --task $(TASK); \
	else \
		echo "MISSING: scripts/check-task-file.py not found"; \
		exit 1; \
	fi
	@echo "-- check-task-scope --"
	@if [ -f scripts/check-task-scope.py ]; then \
		$(PYTHON) scripts/check-task-scope.py --task $(TASK) --base $(BASE); \
	else \
		echo "MISSING: scripts/check-task-scope.py not found"; \
		exit 1; \
	fi
	@echo "-- check-evidence --"
	@if [ -f scripts/check-evidence.py ]; then \
		$(PYTHON) scripts/check-evidence.py --task $(TASK); \
	else \
		echo "MISSING: scripts/check-evidence.py not found"; \
		exit 1; \
	fi
	@echo "-- check-pr-task-link --"
	@if [ -f scripts/check-pr-task-link.py ]; then \
		$(PYTHON) scripts/check-pr-task-link.py --branch $(BRANCH); \
	else \
		echo "MISSING: scripts/check-pr-task-link.py not found"; \
		exit 1; \
	fi
	@echo "-- check-spec-sync --"
	@if [ -f scripts/check-spec-sync.py ]; then \
		$(PYTHON) scripts/check-spec-sync.py --base $(BASE); \
	else \
		echo "MISSING: scripts/check-spec-sync.py not found"; \
		exit 1; \
	fi
	$(MAKE) governance-test

verify:
	@echo "=== verify (TASK=$(TASK)) ==="
	$(MAKE) docs-check
	$(MAKE) schema-check
	$(MAKE) secret-scan
	$(MAKE) governance-test
	$(MAKE) task-verify TASK=$(TASK)