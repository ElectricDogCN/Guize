"""Exercise ordinary Completion with real reservation and completion Git history."""
import copy
import importlib.util
from pathlib import Path
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "poc_completion_history_fixtures",
    ROOT / "tests/governance/test_program_plan_history.py",
)
_fixtures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_fixtures)


def completion_history(root, *, task_id="POC-003", mutate=None):
    """Build an ordinary ledger-bound lifecycle, keeping the checker real."""
    case = _fixtures.TestProgramPlanHistory()
    case.init_git(root)
    case.write_text(root, "seed.txt", "seed\n")
    seed = case.commit(root, "seed")
    branch = f"chore/{task_id}-implementation"
    reserved = case.entry(task_id, seed, "reserved", branch)
    plan = {
        "foundationTasks": [],
        "tasks": [
            {"taskId": task_id, "status": "reserved", "exitGate": "verified"},
            {"taskId": "POC-005", "status": "planned", "exitGate": "foreign"},
        ],
        "pocs": [
            {"taskId": "POC-005", "pocId": "POC-05", "status": "planned"},
        ],
        "externalBlockers": [{"id": "BRANCH-PROTECTION", "status": "open"}],
    }
    if task_id == "POC-003":
        plan["pocs"].insert(
            0, {"taskId": task_id, "pocId": "POC-03", "status": "reserved"}
        )
    case.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
    case.write_yaml(root, "specs/coordination/active-work.yaml", case.registry([reserved]))
    case.write_yaml(root, "specs/coordination/task-completions.yaml", {"records": []})
    case.write_text(
        root, f"specs/tasks/{task_id}.md",
        case.task_spec(reserved, "reserved", branch, seed),
    )
    case.write_text(root, f"evidence/{task_id}/handoff.md", "# Handoff\n")
    reservation = case.commit(root, f"{task_id} reservation (#30)")

    active = dict(reserved, status="integration")
    plan["tasks"][0]["status"] = "integration"
    if task_id == "POC-003":
        plan["pocs"][0]["status"] = "integration"
    case.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
    case.write_yaml(root, "specs/coordination/active-work.yaml", case.registry([active]))
    case.write_text(
        root, f"specs/tasks/{task_id}.md",
        case.task_spec(active, "integration", branch, seed),
    )
    implementation = case.commit(root, f"{task_id} implementation (#31)")
    completion_branch = f"chore/{task_id}-completion"
    subprocess.run(
        ["git", "checkout", "-b", completion_branch],
        cwd=root, check=True, capture_output=True,
    )
    plan["tasks"][0]["status"] = "completed"
    if task_id == "POC-003":
        plan["pocs"][0]["status"] = "completed"
    if mutate is not None:
        mutate(plan)
    case.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
    case.write_yaml(root, "specs/coordination/active-work.yaml", case.registry([]))
    case.write_yaml(root, "specs/coordination/task-completions.yaml", {
        "records": [{
            "taskId": task_id, "reservationRef": "PR-30",
            "reservationCommit": reservation, "completionRef": "PR-31",
            "mergeCommit": implementation, "taskSpec": f"specs/tasks/{task_id}.md",
            "evidencePath": f"evidence/{task_id}",
            "handoffPath": f"evidence/{task_id}/handoff.md",
        }],
    })
    case.write_text(
        root, f"specs/tasks/{task_id}.md",
        case.task_spec(active, "completed", completion_branch, implementation),
    )
    case.commit(root, f"{task_id} completion metadata (#32)")
    return case._run_checker(root, task_id, completion_branch)


def test_poc_completion_accepts_its_synchronized_status_mirror(tmp_path):
    result = completion_history(tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr


def invalid_completion(plan, scenario):
    own = plan["pocs"][0]
    if scenario == "missing-own-row":
        plan["pocs"].pop(0)
    elif scenario == "missing-own-status":
        own.pop("status")
    elif scenario == "wrong-own-status":
        own["status"] = "integration"
    elif scenario == "own-poc-metadata":
        own["pocId"] = "POC-99"
    elif scenario == "foreign-poc-status":
        plan["pocs"][1]["status"] = "completed"
    elif scenario == "foreign-task-status":
        plan["tasks"][1]["status"] = "completed"
    elif scenario == "poc-row-order":
        plan["pocs"].reverse()
    elif scenario == "unrelated-root-field":
        plan["newPolicy"] = True
    elif scenario == "external-blocker":
        plan["externalBlockers"][0]["status"] = "resolved"
    elif scenario == "own-task-nonstatus":
        plan["tasks"][0]["exitGate"] = "weakened"
    elif scenario == "duplicate-own-row":
        plan["pocs"].append(copy.deepcopy(own))
    else:
        raise AssertionError(scenario)


@pytest.mark.parametrize("scenario", [
    "missing-own-row", "missing-own-status", "wrong-own-status",
    "own-poc-metadata", "foreign-poc-status", "foreign-task-status",
    "poc-row-order", "unrelated-root-field", "external-blocker",
    "own-task-nonstatus", "duplicate-own-row",
])
def test_poc_completion_rejects_changes_beyond_its_mirror(tmp_path, scenario):
    result = completion_history(
        tmp_path, mutate=lambda plan: invalid_completion(plan, scenario),
    )
    assert result.returncode != 0
    assert "Completion task POC-003 may only change its Program status" in result.stdout


def test_non_poc_completion_keeps_its_existing_behavior(tmp_path):
    result = completion_history(tmp_path, task_id="GZ-004")
    assert result.returncode == 0, result.stdout + result.stderr


def test_completion_cannot_resolve_even_its_owned_external_blocker(tmp_path):
    # The broader lifecycle comparator permits this owner to resolve this blocker.
    # Ordinary Completion must retain its stricter original boundary.
    result = completion_history(
        tmp_path, task_id="GZ-018",
        mutate=lambda plan: plan["externalBlockers"][0].update(status="resolved"),
    )
    assert result.returncode != 0
    assert "Completion task GZ-018 may only change its Program status" in result.stdout


def test_completion_comparison_does_not_mutate_either_plan():
    spec = importlib.util.spec_from_file_location(
        "poc_completion_history_checker", ROOT / "scripts/check-program-plan-history.py",
    )
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    base = {
        "tasks": [{"taskId": "POC-003", "status": "integration"}],
        "pocs": [{"taskId": "POC-003", "status": "integration"}],
    }
    current = copy.deepcopy(base)
    current["tasks"][0]["status"] = current["pocs"][0]["status"] = "completed"
    original_base, original_current = copy.deepcopy(base), copy.deepcopy(current)
    assert checker.only_regular_completion_status_changed(base, current, "POC-003")
    assert base == original_base
    assert current == original_current
