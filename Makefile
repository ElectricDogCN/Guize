# Guize Solution — GZ-001 Repository Baseline Makefile
# Usage: make verify [TASK=GZ-001]

TASK ?= GZ-001
BASE ?= main
MODE ?= implement
ISSUE ?= $(TASK)
BRANCH ?= chore/$(TASK)-repository-baseline

PYTHON := $(shell command -v python 2>/dev/null || command -v python3 2>/dev/null)
GIT := $(shell command -v git 2>/dev/null)
MARKDOWNLINT := $(shell command -v markdownlint 2>/dev/null || command -v markdownlint-cli 2>/dev/null)
PYTEST := $(shell command -v pytest 2>/dev/null)
DETECT_SECRETS := $(shell command -v detect-secrets 2>/dev/null)
GITLEAKS := $(shell command -v gitleaks 2>/dev/null)

.PHONY: help docs-check schema-check secret-scan governance-test agent-prompt task-verify verify

help:
	@echo "Available targets:"
	@echo "  help           Print available targets with descriptions"
	@echo "  docs-check     Run basic Markdown checks (trailing whitespace, broken internal links)"
	@echo "  schema-check   Validate YAML/JSON schema files under contracts/"
	@echo "  secret-scan    Scan for common secret patterns in the repository"
	@echo "  governance-test Run governance script tests"
	@echo "  agent-prompt   Generate agent prompt for TASK (default: GZ-001)"
	@echo "  task-verify    Run task verification checks for TASK"
	@echo "  verify         Run all baseline gates for TASK (default: GZ-001)"

docs-check:
	@echo "=== docs-check ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ -f scripts/check-markdown.py ]; then \
		$(PYTHON) scripts/check-markdown.py; \
	else \
		echo "MISSING: scripts/check-markdown.py not found"; \
		exit 1; \
	fi
	@if [ -n "$(MARKDOWNLINT)" ]; then \
		echo "-- Running markdownlint --"; \
		$(MARKDOWNLINT) '**/*.md' || true; \
	else \
		echo "MISSING: markdownlint is not installed, skipping"; \
	fi

schema-check:
	@echo "=== schema-check ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@echo "-- Validating schema files under contracts/ --"
	@printf '%s\n' \
		'import json, os, sys' \
		'has_yaml = False' \
		'try:' \
		'    import yaml' \
		'    has_yaml = True' \
		'except ImportError:' \
		'    pass' \
		'errors = 0' \
		'warnings = 0' \
		'for root, dirs, files in os.walk("contracts"):' \
		'    for f in files:' \
		'        path = os.path.join(root, f)' \
		'        if f.endswith(".json"):' \
		'            try:' \
		'                with open(path, "r", encoding="utf-8") as fh:' \
		'                    json.load(fh)' \
		'                print(f"OK: {path}")' \
		'            except Exception as e:' \
		'                print(f"FAIL: {path} - {e}")' \
		'                errors += 1' \
		'        elif f.endswith(".yaml") or f.endswith(".yml"):' \
		'            if has_yaml:' \
		'                try:' \
		'                    with open(path, "r", encoding="utf-8") as fh:' \
		'                        yaml.safe_load(fh)' \
		'                    print(f"OK: {path}")' \
		'                except Exception as e:' \
		'                    print(f"FAIL: {path} - {e}")' \
		'                    errors += 1' \
		'            else:' \
		'                print(f"MISSING: {path} - PyYAML not installed, cannot validate YAML")' \
		'                warnings += 1' \
		'        else:' \
		'            continue' \
		'if warnings:' \
		'    print(f"WARNING: {warnings} YAML file(s) could not be validated (PyYAML missing)")' \
		'if errors:' \
		'    sys.exit(1)' \
		'else:' \
		'    print("OK: Schema validation complete")' \
		> /tmp/guize-schema-check.py
	@$(PYTHON) /tmp/guize-schema-check.py
	@rm -f /tmp/guize-schema-check.py

secret-scan:
	@echo "=== secret-scan ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@$(PYTHON) scripts/check-secrets.py

governance-test:
	@echo "=== governance-test ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ -d tests/governance ]; then \
		test_count=$$(find tests/governance -name "*.py" | wc -l); \
		if [ "$$test_count" -eq 0 ]; then \
			echo "MISSING: no test files found in tests/governance/"; \
		else \
			echo "-- Running pytest on tests/governance/ --"; \
			$(PYTHON) -m pytest tests/governance/ -v; \
		fi; \
	else \
		echo "MISSING: tests/governance/ directory not found"; \
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
	fi
	@echo "-- check-task-scope --"
	@if [ -f scripts/check-task-scope.py ]; then \
		$(PYTHON) scripts/check-task-scope.py --task $(TASK) --base $(BASE); \
	else \
		echo "MISSING: scripts/check-task-scope.py not found"; \
	fi
	@echo "-- check-evidence --"
	@if [ -f scripts/check-evidence.py ]; then \
		$(PYTHON) scripts/check-evidence.py --task $(TASK); \
	else \
		echo "MISSING: scripts/check-evidence.py not found"; \
	fi
	@echo "-- check-pr-task-link --"
	@if [ -f scripts/check-pr-task-link.py ]; then \
		$(PYTHON) scripts/check-pr-task-link.py --branch $(BRANCH); \
	else \
		echo "MISSING: scripts/check-pr-task-link.py not found"; \
	fi
	@echo "-- check-spec-sync --"
	@if [ -f scripts/check-spec-sync.py ]; then \
		$(PYTHON) scripts/check-spec-sync.py --base $(BASE); \
	else \
		echo "MISSING: scripts/check-spec-sync.py not found"; \
	fi
	$(MAKE) governance-test

verify:
	@echo "=== verify (TASK=$(TASK)) ==="
	$(MAKE) docs-check
	$(MAKE) schema-check
	$(MAKE) secret-scan
	$(MAKE) governance-test
	$(MAKE) task-verify TASK=$(TASK)
