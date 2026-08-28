# GZ-001-R3: Repository Root Migration

## Migration Summary

### Before Migration
```
/
├── README.md (placeholder)
└── guize-solution/
    ├── .agent/
    ├── .github/
    │   ├── ISSUE_TEMPLATE/
    │   ├── workflows/
    │   └── pull_request_template.md
    ├── .trae/
    ├── AGENTS.md
    ├── MANIFEST.md
    ├── Makefile
    ├── requirements-governance.txt
    ├── adr/
    ├── contracts/
    ├── deployment/
    ├── docs/
    ├── evidence/
    ├── prompts/
    ├── rules/
    ├── scripts/
    ├── specs/
    └── tests/
```

### After Migration
```
/
├── .agent/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   ├── workflows/
│   └── pull_request_template.md
├── .trae/
├── AGENTS.md
├── MANIFEST.md
├── README.md (complete)
├── Makefile
├── requirements-governance.txt
├── adr/
├── contracts/
├── deployment/
├── docs/
├── evidence/
├── prompts/
├── rules/
├── scripts/
├── specs/
└── tests/
    └── governance/
```

## Files Migrated

| Source | Target | Action |
|--------|--------|--------|
| guize-solution/AGENTS.md | AGENTS.md | moved |
| guize-solution/MANIFEST.md | MANIFEST.md | moved |
| guize-solution/Makefile | Makefile | moved |
| guize-solution/README.md | README.md | moved (replaced placeholder) |
| guize-solution/requirements-governance.txt | requirements-governance.txt | moved |
| guize-solution/.github/ | .github/ | moved |
| guize-solution/.agent/ | .agent/ | moved |
| guize-solution/.trae/ | .trae/ | moved |
| guize-solution/adr/ | adr/ | moved |
| guize-solution/contracts/ | contracts/ | moved |
| guize-solution/deployment/ | deployment/ | moved |
| guize-solution/docs/ | docs/ | moved |
| guize-solution/evidence/ | evidence/ | moved |
| guize-solution/prompts/ | prompts/ | moved |
| guize-solution/rules/ | rules/ | moved |
| guize-solution/scripts/ | scripts/ | moved |
| guize-solution/specs/ | specs/ | moved |
| guize-solution/tests/ | tests/ | moved |

## Path References Updated

- `.github/workflows/governance-gate.yml`: Removed `working-directory: guize-solution`, updated path filters
- `Makefile`: Updated paths to remove `guize-solution/` prefix
- `scripts/check-task-scope.py`: Updated default paths
- `scripts/check-evidence.py`: Updated default paths
- `scripts/check-spec-sync.py`: Updated paths
- `tests/governance/test_repository_boundary.py`: Updated assertions
- `prompts/*.md`: Updated path references

## Verification

- [x] All files successfully moved
- [x] `guize-solution/` directory deleted
- [x] All path references updated
- [x] Governance tests pass (52 tests)
- [x] `make verify` passes
- [x] Temporary Git clone verification passes

## Migration Impact

1. **GitHub Recognition**: `.github/` directory now correctly recognized by GitHub for workflows, issue templates, and PR templates
2. **Agent Discovery**: `AGENTS.md` at root enables proper agent discovery
3. **Path Simplicity**: All commands now executed from repository root without directory prefix
4. **CI Correctness**: Workflow now runs from root with proper path filters

## Rollback

See `rollback.md` for detailed rollback instructions.
