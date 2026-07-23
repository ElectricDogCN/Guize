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
	@if [ -z "$(GIT)" ]; then echo "MISSING: git is required but not installed"; exit 1; fi
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@echo "-- Checking for trailing whitespace in changed Markdown files --"
	@changed_md=$$(git diff --name-only $(BASE)...HEAD -- '*.md' 2>/dev/null || git diff --name-only $(BASE) -- '*.md' 2>/dev/null); \
	if [ -n "$$changed_md" ]; then \
		found=0; \
		for f in $$changed_md; do \
			if git show HEAD:"$$f" 2>/dev/null | grep -n '[[:space:]]$$' > /dev/null 2>&1; then :; fi; \
			if [ -f "$$f" ] && grep -n '[[:space:]]$$' "$$f" > /dev/null 2>&1; then \
				echo "FAIL: $$f has trailing whitespace"; \
				found=1; \
			fi; \
		done; \
		if [ "$$found" = "1" ]; then exit 1; else echo "OK: No trailing whitespace in changed Markdown files"; fi; \
	else \
		echo "INFO: No changed Markdown files to check for trailing whitespace"; \
	fi
	@echo "-- Checking for broken internal links in Markdown files --"
	@printf '%s\n' \
		'import os, re, subprocess, sys' \
		'def get_md_files():' \
		'    try:' \
		'        return [f for f in subprocess.check_output(["git", "ls-files", "*.md"]).decode().strip().splitlines() if f]' \
		'    except Exception:' \
		'        return [os.path.join(dp, f) for dp, dn, filenames in os.walk(".") for f in filenames if f.endswith(".md")]' \
		'files = get_md_files()' \
		'link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")' \
		'errors = 0' \
		'for f in files:' \
		'    d = os.path.dirname(f)' \
		'    try:' \
		'        with open(f, "r", encoding="utf-8") as fh:' \
		'            content = fh.read()' \
		'    except Exception as e:' \
		'        print(f"SKIP: {f} - {e}")' \
		'        continue' \
		'    for m in link_pattern.finditer(content):' \
		'        link = m.group(2)' \
		'        if link.startswith("http") or link.startswith("#") or link.startswith("mailto:"):' \
		'            continue' \
		'        target = os.path.normpath(os.path.join(d, link)) if not link.startswith("/") else link.lstrip("/")' \
		'        if not os.path.exists(target):' \
		'            print(f"BROKEN LINK: {f} -> {link}")' \
		'            errors += 1' \
		'if errors:' \
		'    print(f"FAIL: {errors} broken internal link(s)")' \
		'    sys.exit(1)' \
		'else:' \
		'    print("OK: No broken internal links")' \
		> /tmp/guize-docs-check.py
	@$(PYTHON) /tmp/guize-docs-check.py
	@rm -f /tmp/guize-docs-check.py
	@if [ -z "$(MARKDOWNLINT)" ]; then \
		echo "MISSING: markdownlint is not installed, skipping markdownlint check"; \
	else \
		echo "-- Running markdownlint --"; \
		$(MARKDOWNLINT) '**/*.md' || true; \
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
	@if [ -z "$(GIT)" ]; then echo "MISSING: git is required but not installed"; exit 1; fi
	@echo "-- Scanning with git grep for common secret patterns --"
	@found=0; \
	git grep -n -E "AKIA[0-9A-Z]{16}" -- '*.py' '*.yaml' '*.yml' '*.json' '*.md' '*.sh' && { echo "POTENTIAL SECRET: AWS Access Key ID pattern found"; found=1; } || true; \
	git grep -n -i -E "aws_secret_access_key|aws_access_key_id" -- '*.py' '*.yaml' '*.yml' '*.json' '*.md' '*.sh' | grep -v 'git grep' | grep -v 'POTENTIAL SECRET' && { echo "POTENTIAL SECRET: AWS key pattern found"; found=1; } || true; \
	git grep -n -E "BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY" -- '*.py' '*.yaml' '*.yml' '*.json' '*.md' '*.sh' && { echo "POTENTIAL SECRET: Private key pattern found"; found=1; } || true; \
	git grep -n -i -E "password[[:space:]]*=[[:space:]]*['\"][^'\"]+['\"]" -- '*.py' '*.yaml' '*.yml' '*.json' '*.sh' && { echo "POTENTIAL SECRET: Password pattern found"; found=1; } || true; \
	git grep -n -i -E "api[_-]?key[[:space:]]*=[[:space:]]*['\"][^'\"]+['\"]" -- '*.py' '*.yaml' '*.yml' '*.json' '*.sh' && { echo "POTENTIAL SECRET: API key pattern found"; found=1; } || true; \
	git grep -n -i -E "api[_-]?token[[:space:]]*=[[:space:]]*['\"][^'\"]+['\"]" -- '*.py' '*.yaml' '*.yml' '*.json' '*.sh' && { echo "POTENTIAL SECRET: API token pattern found"; found=1; } || true; \
	if [ "$$found" = "1" ]; then echo "FAIL: Potential secrets detected"; exit 1; else echo "OK: No common secret patterns found"; fi
	@if [ -n "$(DETECT_SECRETS)" ]; then \
		echo "-- Running detect-secrets --"; \
		$(DETECT_SECRETS) scan || true; \
	else \
		echo "MISSING: detect-secrets is not installed, skipping"; \
	fi
	@if [ -n "$(GITLEAKS)" ]; then \
		echo "-- Running gitleaks --"; \
		$(GITLEAKS) detect --source . -v || true; \
	else \
		echo "MISSING: gitleaks is not installed, skipping"; \
	fi

governance-test:
	@echo "=== governance-test ==="
	@if [ -z "$(PYTHON)" ]; then echo "MISSING: python is required but not installed"; exit 1; fi
	@if [ -d tests/governance ]; then \
		test_count=$$(find tests/governance -name "*.py" | wc -l); \
		if [ "$$test_count" -eq 0 ]; then \
			echo "MISSING: no test files found in tests/governance/"; \
		else \
			if [ -n "$(PYTEST)" ]; then \
				echo "-- Running pytest on tests/governance/ --"; \
				$(PYTEST) tests/governance/ -v; \
			else \
				echo "MISSING: pytest is not installed, falling back to unittest"; \
				$(PYTHON) -m unittest discover -s tests/governance -v; \
			fi; \
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
