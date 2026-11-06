"""Real cold snapshot comparisons; original validation remains the oracle."""
import importlib.util
import itertools
import os
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SERIAL = itertools.count()


def load_module(path, prefix):
    name = prefix + str(next(SERIAL))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


FIXTURES = load_module(ROOT / "tests/governance/test_program_plan_history.py", "snapshot_fixture_")


def git(root, *args, data=None):
    result = subprocess.run(["git", "-C", str(root), *args], input=data,
                            capture_output=True, check=False)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout.decode().strip()


def state(root):
    return (git(root, "rev-parse", "HEAD"),
            git(root, "for-each-ref", "--format=%(refname) %(objectname)"),
            git(root, "status", "--porcelain=v1", "--untracked-files=all"))


@pytest.fixture
def make_history(tmp_path, monkeypatch):
    # Isolate these tiny histories from caller attributes and CI range hints.
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    for key in ("GITHUB_HEAD_REF", "GITHUB_BASE_REF", "GITHUB_EVENT_NAME",
                "GITHUB_REF_NAME", "PUSH_BEFORE", "BASE_SHA", "HEAD_SHA"):
        monkeypatch.delenv(key, raising=False)

    def build(task="OPS-021", status="reserved", mutation=None):
        root = tmp_path / ("history-" + str(next(SERIAL)))
        root.mkdir()
        helper = FIXTURES.TestProgramPlanHistory()
        helper.foundation_fixture = True
        helper.init_git(str(root))
        for path in ("specs/coordination/active-work.schema.yaml",
                     "specs/coordination/program-plan.schema.yaml",
                     "specs/designs/module-ownership.yaml"):
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / path).read_bytes())
        plan = {"status": "active", "foundationTasks": [], "tasks": []}
        helper.write_yaml(str(root), "specs/coordination/program-plan.yaml", plan)
        helper.write_yaml(str(root), "specs/coordination/active-work.yaml", helper.registry([]))
        helper.write_yaml(str(root), "specs/coordination/task-completions.yaml", {"records": []})
        helper.write_text(str(root), "payload/unrelated.bin", "unrelated payload\n")
        seed = helper.commit(str(root), "Fixture integration parent")
        branch = "chore/" + task + "-snapshot-fixture"
        entry = helper.entry(task, seed, status, branch)
        entry.update(agentRole="coordinator" if status == "reserved" else "reviewer",
                     programWave="FOUNDATION", workPackage="WP-M0-01",
                     requirementIds=["REQ-V1-0010"],
                     exclusivePaths=["scripts/snapshot-fixture.py"])
        now = datetime.now(timezone.utc)
        entry["lease"] = {"acquiredAt": (now - timedelta(hours=1)).isoformat(),
                          "expiresAt": (now + timedelta(days=1)).isoformat()}
        plan["foundationTasks"] = [{"taskId": task, "title": entry["title"],
                                    "status": status, "completionRef": "ISSUE-30",
                                    "mergeCommit": None}]
        helper.write_yaml(str(root), "specs/coordination/program-plan.yaml", plan)
        helper.write_yaml(str(root), "specs/coordination/active-work.yaml", helper.registry([entry]))
        task_path = root / ("specs/tasks/" + task + ".md")
        helper.write_text(str(root), str(task_path.relative_to(root)),
                          helper.task_spec(entry, status, branch, seed))
        helper.write_text(str(root), "evidence/" + task + "/handoff.md", "# Fixture handoff\n")
        if mutation:
            mutation(root, task_path, entry)
        commit = helper.commit(str(root), "Original metadata reservation")
        return root, commit, entry

    return build


def compare_snapshot(root, commit, task, entry):
    before = state(root)
    outcomes = []
    for optimized in (False, True):
        history = load_module(ROOT / "scripts/check-program-plan-history.py", "snapshot_checker_")
        original = history.checkout_task_snapshot
        materialized = []

        def checkout(snapshot, revision, identity):
            result = (original(snapshot, revision, identity) if optimized else
                      history.git(snapshot, "checkout", "--detach", "--quiet", revision))
            if result.returncode == 0:
                materialized.append({"head": git(snapshot, "rev-parse", "HEAD"),
                                     "shallow": git(snapshot, "rev-parse", "--is-shallow-repository"),
                                     "payload": (Path(snapshot) / "payload/unrelated.bin").exists()})
            return result

        history.checkout_task_snapshot = checkout
        errors = []
        history.historical_task_snapshot(str(root), commit, task, entry, "snapshot", errors)
        # The actual YAML parser includes each distinct temporary checkout name.
        # Compare the refusal itself while retaining every other diagnostic field.
        errors = [re.sub(r"guize-foundation-task-[A-Za-z0-9_]+",
                         "guize-foundation-task-<TEMP>", error) for error in errors]
        outcomes.append((errors, materialized, len(history.VALIDATED_TASK_SNAPSHOTS)))
    assert state(root) == before
    assert outcomes[0][0] == outcomes[1][0]
    return outcomes


@pytest.mark.parametrize("task", ["OPS-020", "OPS-021"])
@pytest.mark.parametrize("status", ["reserved", "review"])
def test_cold_historical_snapshot_matches_dense_without_unrelated_payload(make_history, task, status):
    root, commit, entry = make_history(task, status)
    dense, bounded = compare_snapshot(root, commit, task, entry)
    assert dense[0] == bounded[0] == []
    assert dense[1] == [{"head": commit, "shallow": "false", "payload": True}]
    assert bounded[1] == [{"head": commit, "shallow": "false", "payload": False}]
    assert dense[2] == bounded[2] == 1


def mutate_case(case):
    def mutate(root, path, entry):
        if case == "missing-task":
            path.unlink()
        elif case == "ambiguous-task":
            raw = path.read_bytes()
            path.unlink()
            (path.parent / (entry["taskId"] + "-one.md")).write_bytes(raw)
            (path.parent / (entry["taskId"] + "-two.md")).write_bytes(raw)
        elif case == "bad-task-schema":
            path.write_bytes(path.read_bytes().replace(b"schemaVersion: 2", b"schemaVersion: invalid", 1))
        elif case == "bad-program":
            (root / "specs/coordination/program-plan.yaml").write_text("foundationTasks: [\n", encoding="utf-8")
        elif case == "missing-handoff":
            (root / entry["handoffPath"]).unlink()
        elif case == "missing-evidence":
            handoff = root / entry["handoffPath"]
            handoff.unlink()
            handoff.parent.rmdir()
        elif case == "wrong-registry-owner":
            entry["owner"] = "another-owner"
        else:
            raise AssertionError(case)
    return mutate


@pytest.mark.parametrize("case", ["missing-task", "ambiguous-task", "bad-task-schema",
                                  "bad-program", "missing-handoff", "missing-evidence",
                                  "wrong-registry-owner"])
def test_cold_bad_historical_inputs_match_dense_refusal(make_history, case):
    root, commit, entry = make_history("OPS-020", mutation=mutate_case(case))
    dense, bounded = compare_snapshot(root, commit, "OPS-020", entry)
    assert dense[0] and bounded[0]
    assert dense[2] == bounded[2] == 0


@pytest.mark.parametrize("missing_handoff", [False, True])
def test_real_original_reservation_uses_same_cold_metadata_validation(make_history, missing_handoff):
    mutation = mutate_case("missing-handoff") if missing_handoff else None
    root, commit, entry = make_history(mutation=mutation)
    before = state(root)
    outcomes = []
    for optimized in (False, True):
        history = load_module(ROOT / "scripts/check-program-plan-history.py", "reservation_checker_")
        if not optimized:
            history.checkout_task_snapshot = lambda snapshot, revision, task: history.git(
                snapshot, "checkout", "--detach", "--quiet", revision)
        errors = []
        result = history.foundation_reservation(str(root), "OPS-021", commit, entry, errors)
        outcomes.append((result, errors))
    assert state(root) == before
    assert outcomes[0] == outcomes[1]
    if missing_handoff:
        assert outcomes[0][1]
    else:
        assert outcomes[0][0][0] == commit and outcomes[0][1] == []


def test_different_entry_and_commit_revalidate_and_failures_are_not_cached(make_history):
    root, commit, entry = make_history()
    history = load_module(ROOT / "scripts/check-program-plan-history.py", "cache_checker_")
    errors = []
    history.historical_task_snapshot(str(root), commit, "OPS-021", entry, "valid", errors)
    assert errors == [] and len(history.VALIDATED_TASK_SNAPSHOTS) == 1
    changed = dict(entry, owner="different-owner")
    errors = []
    history.historical_task_snapshot(str(root), commit, "OPS-021", changed, "changed entry", errors)
    assert errors and len(history.VALIDATED_TASK_SNAPSHOTS) == 1
    (root / entry["handoffPath"]).unlink()
    git(root, "add", "-A")
    git(root, "commit", "--quiet", "-m", "Missing handoff at another commit")
    changed_commit = git(root, "rev-parse", "HEAD")
    for _ in range(2):
        errors = []
        history.historical_task_snapshot(str(root), changed_commit, "OPS-021", entry, "changed commit", errors)
        assert errors and len(history.VALIDATED_TASK_SNAPSHOTS) == 1


@pytest.mark.parametrize("task,excluded", [("OPS-019", True), ("OPS-999", False)])
def test_legacy_and_unknown_task_paths_preserve_caller_and_root_probe(make_history, monkeypatch, task, excluded):
    root, commit, _ = make_history(task)
    probe = ROOT / "evidence/OPS-019/implementation-v1/lfs-probe.bin"
    original_probe = probe.read_bytes()
    monkeypatch.setenv("GIT_LFS_SKIP_SMUDGE", "caller-sentinel")
    history = load_module(ROOT / "scripts/check-program-plan-history.py", "fallback_checker_")
    target = root.parent / ("checkout-" + str(next(SERIAL)))
    git(root, "clone", "--shared", "--no-checkout", "--quiet", str(root), str(target))
    before = state(root)
    result = history.checkout_task_snapshot(str(target), commit, task)
    assert result.returncode == 0 and git(target, "rev-parse", "HEAD") == commit
    assert (target / "payload/unrelated.bin").exists() is not excluded
    assert os.environ["GIT_LFS_SKIP_SMUDGE"] == "caller-sentinel"
    assert probe.read_bytes() == original_probe and state(root) == before


@pytest.mark.parametrize("shape", ["alternative-handoff", "filtered-input", "executable-input", "symlink-handoff"])
def test_unproved_historical_shapes_retain_original_dense_behavior(make_history, shape):
    def mutate(root, path, entry):
        if shape == "alternative-handoff":
            target = "payload/alternative-handoff.md"
            (root / target).write_text("# Alternative handoff\n", encoding="utf-8")
            path.write_bytes(path.read_bytes().replace(entry["handoffPath"].encode(), target.encode()))
            entry["handoffPath"] = target
        elif shape == "filtered-input":
            (root / ".gitattributes").write_text("specs/tasks/OPS-021.md filter=unproved\n", encoding="utf-8")
        elif shape == "symlink-handoff":
            (root / "payload/handoff-target.md").write_text("# Actual handoff target\n", encoding="utf-8")

    root, commit, entry = make_history(mutation=mutate)
    if shape == "executable-input":
        git(root, "update-index", "--chmod=+x", "specs/tasks/OPS-021.md")
        git(root, "commit", "--quiet", "-m", "Executable historical Task metadata")
        commit = git(root, "rev-parse", "HEAD")
    elif shape == "symlink-handoff":
        target_blob = git(root, "hash-object", "-w", "--stdin", data=b"../../payload/handoff-target.md")
        git(root, "update-index", "--add", "--cacheinfo", "120000," + target_blob + "," + entry["handoffPath"])
        git(root, "commit", "--quiet", "-m", "Historical handoff with an external payload target")
        git(root, "checkout", "--", entry["handoffPath"])
        commit = git(root, "rev-parse", "HEAD")
    dense, bounded = compare_snapshot(root, commit, "OPS-021", entry)
    # Alternative handoff is invalid under the actual Task checker in both paths.
    if shape == "alternative-handoff":
        assert dense[0] and bounded[0]
    else:
        assert dense[0] == bounded[0] == []
    assert dense[1][0]["payload"] and bounded[1][0]["payload"]


def test_invalid_checkout_commit_is_rejected(make_history):
    root, _, _ = make_history()
    history = load_module(ROOT / "scripts/check-program-plan-history.py", "failed_checkout_")
    target = root.parent / "invalid-checkout"
    git(root, "clone", "--shared", "--no-checkout", "--quiet", str(root), str(target))
    result = history.checkout_task_snapshot(str(target), "0" * 40, "OPS-021")
    assert result.returncode != 0
