# GZ-001-R3: Commands Executed

## Repository Status Commands

```bash
pwd
git rev-parse --show-toplevel
git status --short
git branch --show-current
git remote -v
git fetch origin
git log --oneline --decorate -15
git log --oneline main..HEAD
git rev-parse HEAD
git rev-parse origin/chore/GZ-001-repository-baseline 2>&1 || echo "Remote branch not found"
```

## Migration Commands

```bash
# Move files from guize-solution/ to root
mv guize-solution/AGENTS.md .
mv guize-solution/MANIFEST.md .
mv guize-solution/Makefile .
mv guize-solution/README.md .
mv guize-solution/requirements-governance.txt .
mv guize-solution/.github .
mv guize-solution/.agent .
mv guize-solution/.trae .
mv guize-solution/adr .
mv guize-solution/contracts .
mv guize-solution/deployment .
mv guize-solution/docs .
mv guize-solution/evidence .
mv guize-solution/prompts .
mv guize-solution/rules .
mv guize-solution/scripts .
mv guize-solution/specs .
mv guize-solution/tests .

# Remove empty wrapper directory
rmdir guize-solution

# Verify migration
ls -la
git status --short
```

## Verification Commands

```bash
# Install dependencies
python -m pip install -r requirements-governance.txt

# Run governance tests
python -m pytest tests/governance/ -v

# Run make commands
make governance-test
make agent-prompt TASK=GZ-001
make task-verify TASK=GZ-001
make verify

# Root structure checks
test -f AGENTS.md && echo "AGENTS.md exists"
test -f .github/workflows/governance-gate.yml && echo "Workflow exists"
test -f Makefile && echo "Makefile exists"
test -d tests/governance && echo "tests/governance exists"
test ! -d guize-solution && echo "guize-solution deleted"

# Old path checks
git grep -n "working-directory: guize-solution" || echo "No working-directory references"
git grep -n "/workspace/guize-solution" || echo "No /workspace/guize-solution references"
git grep -n "guize-solution/.github" || echo "No guize-solution/.github references"
```

## Temporary Git Clone Verification

```bash
tmpdir="$(mktemp -d)"
git clone --no-local . "$tmpdir/Guize"
cd "$tmpdir/Guize"
git checkout chore/GZ-001-repository-baseline
python -m pip install -r requirements-governance.txt
python -m pytest tests/governance/ -v
make verify

# Cleanup
cd -
rm -rf "$tmpdir"
```

## Git Commit Commands (for reference only - not executed)

```bash
# R3 commits (to be executed manually)
git add -A
git commit -m "refactor(repo): normalize governance repository root"
git commit -m "fix(ci): move GitHub workflows to repository root"
git commit -m "test(governance): add repository root layout checks"
git commit -m "docs(governance): record GZ-001 R3 migration evidence"
```
