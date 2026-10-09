"""Exercise real committed lifecycle diffs through raw and actual CI gates."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys

import pytest
import yaml


REPO = Path(__file__).resolve().parents[2]
RESERVATION = "413a6a4dd91b5d79a3d2b7d1e5f03f8121848170"
TASK = "GZ-005"
BRANCH = "chore/GZ-005-openapi-baseline"
PLAN = "specs/coordination/program-plan.yaml"
ACTIVE = "specs/coordination/active-work.yaml"
SPEC = "specs/tasks/GZ-005.md"


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True).stdout.strip()


def commit(root, message):
    git(root, "add", ".")
    git(root, "commit", "--allow-empty", "-m", message)
    return git(root, "rev-parse", "HEAD")


def read(root, path):
    return yaml.safe_load((root / path).read_text(encoding="utf-8"))


def write(root, path, value):
    (root / path).write_text(yaml.safe_dump(value, allow_unicode=True, sort_keys=False), encoding="utf-8")


def own_plan(plan):
    return next(item for item in plan["tasks"] if item["taskId"] == TASK)


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    """Use real reservation history and current validators, with a fresh lease.

    Changes occur only in an isolated clone. Real completed provenance is kept;
    no remote API fixture, bypass argument or fake validator is used.
    """
    root = tmp_path_factory.mktemp("active-metadata-baseline")
    git(root, "clone", "--shared", "--no-checkout", str(REPO), ".")
    git(root, "config", "user.name", "Metadata regression fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "checkout", "-B", "main", RESERVATION)
    for name in ["check-agent-coordination.py", "check-task-scope.py"]:
        shutil.copyfile(REPO / "scripts" / name, root / "scripts" / name)
    now = datetime.now(timezone.utc).replace(microsecond=0)
    expires = (now + timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    active = read(root, ACTIVE)
    active["tasks"][0]["lease"] = {
        "acquiredAt": now.isoformat().replace("+00:00", "Z"), "expiresAt": expires,
    }
    write(root, ACTIVE, active)
    text = (root / SPEC).read_text(encoding="utf-8")
    text = re.sub(r"^leaseExpiresAt:.*$", "leaseExpiresAt: " + expires, text, flags=re.M)
    (root / SPEC).write_text(text, encoding="utf-8")
    commit(root, "Isolated regression baseline with current validators and live lease")
    return root


@pytest.fixture
def candidate(tmp_path, baseline):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "clone", "--shared", "--no-checkout", str(baseline), ".")
    git(root, "config", "user.name", "Metadata regression fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "checkout", "-b", BRANCH, "main")
    base = git(root, "rev-parse", "HEAD")
    transition(root, "in_progress", base)
    return root, base


def transition(root, status, base, role="implementer"):
    plan = read(root, PLAN)
    own_plan(plan)["status"] = status
    write(root, PLAN, plan)
    active = read(root, ACTIVE)
    entry = next(item for item in active["tasks"] if item["taskId"] == TASK)
    entry.update(status=status, agentRole=role, baseSha=base)
    write(root, ACTIVE, active)
    text = (root / SPEC).read_text(encoding="utf-8")
    for name, value in [("status", status), ("agentRole", role), ("baseSha", base)]:
        text = re.sub(r"^" + name + r":.*$", name + ": " + value, text, count=1, flags=re.M)
    (root / SPEC).write_text(text, encoding="utf-8")


def gates(root, base):
    # Fixture repositories have their own actual branches; the enclosing PR
    # branch must not replace that identity in child scope checks.
    env = os.environ.copy()
    env.pop("GITHUB_HEAD_REF", None)
    common = ["--repo-root", str(root), "--task", TASK, "--base-ref", base,
              "--head-ref", "HEAD", "--branch-name", BRANCH]
    commands = [
        ["scripts/check-agent-coordination.py", *common],
        ["scripts/run-agent-coordination-gate.py", *common],
        ["scripts/check-task-scope.py", "--repo-root", str(root), "--task", TASK, "--base", base],
        ["scripts/run-task-scope-gate.py", "--repo-root", str(root), "--task", TASK, "--base", base],
    ]
    return [(cmd[0], subprocess.run([sys.executable, *cmd], cwd=root, capture_output=True, text=True, env=env))
            for cmd in commands]


@pytest.mark.parametrize("kind", ["activation", "activation-and-claimed-code", "review", "integration", "evidence-only"])
def test_legal_own_metadata_through_raw_and_ci_gates(candidate, kind):
    root, base = candidate
    if kind == "activation-and-claimed-code":
        target = root / "contracts/openapi/regression-example.txt"
        target.write_text("isolated declared implementation\n", encoding="utf-8")
    if kind in {"review", "integration", "evidence-only"}:
        base = commit(root, "Actual isolated activation")
        if kind in {"review", "integration"}:
            transition(root, "review", base, "reviewer")
        if kind == "integration":
            base = commit(root, "Actual isolated review")
            transition(root, "integration", base, "integrator")
        if kind == "evidence-only":
            (root / "evidence/GZ-005/regression-note.md").write_text("# GZ-005 evidence update\n", encoding="utf-8")
    commit(root, "Actual isolated legal candidate")
    for name, result in gates(root, base):
        assert result.returncode == 0, name + "\n" + result.stdout + result.stderr


def test_scope_respects_explicit_ci_branch(candidate):
    root, base = candidate
    commit(root, "Actual isolated activation with mismatched CI branch")
    env = os.environ.copy()
    env["GITHUB_HEAD_REF"] = "chore/OPS-004-lifecycle-repair-implementation"
    for name in ["check-task-scope.py", "run-task-scope-gate.py"]:
        result = subprocess.run(
            [sys.executable, "scripts/" + name, "--repo-root", str(root),
             "--task", TASK, "--base", base],
            cwd=root, capture_output=True, text=True, env=env,
        )
        assert result.returncode != 0, name
        assert "Actual branch does not carry task ID GZ-005" in result.stdout + result.stderr


@pytest.mark.parametrize("attack", [
    "other-task-status", "program-policy", "own-plan-risk", "registry-claims",
    "registry-risk", "reviewer-is-implementer", "task-risk", "task-id",
    "illegal-transition", "ledger", "unclaimed-code", "rename-source", "expired-lease", "dirty-metadata",
    "lease-too-long", "task-issue",
])
def test_metadata_permission_rejects_unauthorized_changes(candidate, attack):
    root, base = candidate
    plan, active = read(root, PLAN), read(root, ACTIVE)
    entry = active["tasks"][0]
    if attack == "other-task-status":
        next(item for item in plan["tasks"] if item["taskId"] == "GZ-006")["status"] = "in_progress"
    elif attack == "program-policy":
        plan["parallelPolicy"]["maxHighRiskTasks"] = 2
    elif attack == "own-plan-risk":
        own_plan(plan)["riskLevel"] = "medium"
    elif attack == "registry-claims":
        entry["exclusivePaths"].append("backend/**")
    elif attack == "registry-risk":
        entry["riskLevel"] = "medium"
    elif attack == "reviewer-is-implementer":
        entry["reviewer"] = entry["implementer"]
    elif attack == "task-risk":
        text = (root / SPEC).read_text(encoding="utf-8").replace("riskLevel: high", "riskLevel: medium", 1)
        (root / SPEC).write_text(text, encoding="utf-8")
    elif attack == "task-id":
        text = (root / SPEC).read_text(encoding="utf-8").replace("id: GZ-005", "id: GZ-006", 1)
        (root / SPEC).write_text(text, encoding="utf-8")
    elif attack == "task-issue":
        text = (root / SPEC).read_text(encoding="utf-8").replace("issue: 68", "issue: 999999", 1)
        (root / SPEC).write_text(text, encoding="utf-8")
    elif attack == "illegal-transition":
        transition(root, "review", base, "reviewer")
        plan, active = read(root, PLAN), read(root, ACTIVE)
    elif attack == "ledger":
        ledger = read(root, "specs/coordination/task-completions.yaml")
        ledger["records"][0]["issue"] = 999999
        write(root, "specs/coordination/task-completions.yaml", ledger)
    elif attack == "unclaimed-code":
        (root / "backend").mkdir(exist_ok=True)
        (root / "backend/unclaimed.txt").write_text("unauthorized\n", encoding="utf-8")
    elif attack == "rename-source":
        git(root, "mv", "README.md", "evidence/GZ-005/copied-readme.md")
    elif attack == "expired-lease":
        now = datetime.now(timezone.utc).replace(microsecond=0)
        expired = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        entry["lease"] = {"acquiredAt": (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z"), "expiresAt": expired}
        text = re.sub(r"^leaseExpiresAt:.*$", "leaseExpiresAt: " + expired,
                      (root / SPEC).read_text(encoding="utf-8"), flags=re.M)
        (root / SPEC).write_text(text, encoding="utf-8")
    elif attack == "lease-too-long":
        now = datetime.now(timezone.utc).replace(microsecond=0)
        expires = (now + timedelta(hours=169)).isoformat().replace("+00:00", "Z")
        entry["lease"] = {"acquiredAt": now.isoformat().replace("+00:00", "Z"), "expiresAt": expires}
        text = re.sub(r"^leaseExpiresAt:.*$", "leaseExpiresAt: " + expires,
                      (root / SPEC).read_text(encoding="utf-8"), flags=re.M)
        (root / SPEC).write_text(text, encoding="utf-8")
    write(root, PLAN, plan)
    write(root, ACTIVE, active)
    commit(root, "Actual isolated attack candidate")
    if attack == "dirty-metadata":
        plan["parallelPolicy"]["maxHighRiskTasks"] = 2
        write(root, PLAN, plan)
    for name, result in gates(root, base):
        assert result.returncode != 0, name + " accepted " + attack + "\n" + result.stdout + result.stderr


def test_no_task_global_coordination_keeps_real_capacity_limit(candidate):
    root, _ = candidate
    active = read(root, ACTIVE)
    other = dict(active["tasks"][0])
    other.update(taskId="GZ-006", branch="chore/GZ-006-test", handoffPath="evidence/GZ-006/handoff.md")
    other["exclusivePaths"] = ["contracts/events/**"]
    active["tasks"].append(other)
    write(root, ACTIVE, active)
    result = subprocess.run([sys.executable, "scripts/check-agent-coordination.py", "--repo-root", str(root)],
                            cwd=root, capture_output=True, text=True)
    assert result.returncode != 0
    assert "High/critical active task count 2 exceeds limit 1" in result.stdout
