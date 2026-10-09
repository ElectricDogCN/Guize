"""Exercise recovery gates against real Git endpoints and adversarial evidence."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]


def module(name, script):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / script)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


GUARD = module("forward_recovery_guard", "check-program-lifecycle-guards.py")
TRANSITIONS = module("forward_recovery_transitions", "check-program-plan-transitions.py")
WRAPPER = module("forward_recovery_wrapper", "run-program-lifecycle-gate.py")


class Repository:
    def __init__(self, root, owner=True):
        self.root = str(root)
        self.plan = {"status": "active", "foundationTasks": [], "tasks": [
            {"taskId": "GZ-004", "status": "completed", "issue": 14},
            {"taskId": "GZ-010", "status": "in_progress", "riskLevel": "medium", "dependsOn": ["GZ-004"]},
        ], "waves": [], "pocs": [], "externalBlockers": []}
        self.active = {"policy": {"leaseMaxHours": 168}, "tasks": []}
        self.ledger = {"records": [{"taskId": "GZ-004", "mergeCommit": "a" * 40}]}
        self.ownership = {"modules": [{"id": "MOD-GOV", "ownedPaths": ["scripts/**", "tests/governance/**", "specs/coordination/**", "AGENTS.md"]}]}
        self.write_yaml(GUARD.OWNERSHIP, self.ownership)
        self.write("scripts/repair.py", "print('original')\n")
        self.write("business/file.txt", "existing implementation\n")
        self.write("evidence/GZ-004/summary.md", "Existing completed evidence\n")
        self.write("specs/tasks/GZ-004.md", "---\nid: GZ-004\nstatus: completed\nissue: 14\nevidencePath: evidence/GZ-004\nhandoffPath: evidence/GZ-004/handoff.md\n---\nImmutable body\n")
        self.write("specs/tasks/GZ-010.md", "---\nid: GZ-010\nstatus: in_progress\n---\n")
        if owner:
            self.add_owner("in_progress")
        self.save()
        self.git("init", "-b", "main")
        self.git("config", "user.email", "recovery-test@example.com")
        self.git("config", "user.name", "Recovery test")
        self.git("config", "core.autocrlf", "false")
        self.base = self.commit("Existing canonical state")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()

    def write(self, relative, text):
        path = Path(self.root, relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def write_yaml(self, relative, value):
        self.write(relative, yaml.safe_dump(value, sort_keys=False))

    def save(self):
        self.write_yaml(GUARD.PLAN, self.plan)
        self.write_yaml(GUARD.ACTIVE, self.active)
        self.write_yaml(GUARD.LEDGER, self.ledger)

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def add_owner(self, status):
        now = datetime.now(timezone.utc)
        entry = {
            "taskId": "OPS-003", "issue": 64, "title": "Recovery", "status": status,
            "riskLevel": "high", "owner": "owner", "coordinator": "coordinator",
            "implementer": "implementer", "reviewer": "independent-reviewer", "integrator": "integrator",
            "agentRole": "coordinator" if status == "reserved" else "implementer",
            "branch": "chore/OPS-003-recovery", "baseBranch": "main", "baseSha": getattr(self, "base", "a" * 40),
            "workPackage": "WP-M0-01", "programPlan": GUARD.PLAN, "programTaskId": "OPS-003", "programWave": "FOUNDATION",
            "requirementIds": ["REQ-V1-0010"], "moduleIds": ["MOD-GOV"], "producesContracts": [], "consumesContracts": [],
            "coordinationGroup": "recovery", "dependsOn": [], "exclusivePaths": ["scripts/repair.py"], "sharedPaths": [],
            "handoffPath": "evidence/OPS-003/handoff.md", "integrationStrategy": "merge", "integrationOrder": 3,
            "lease": {"acquiredAt": (now - timedelta(minutes=1)).isoformat(), "expiresAt": (now + timedelta(hours=24)).isoformat()},
        }
        self.plan["foundationTasks"].append({"taskId": "OPS-003", "title": "Recovery", "status": status, "completionRef": "ISSUE-64", "mergeCommit": None})
        self.active["tasks"].append(entry)
        self.owner_spec(entry)
        return entry

    def owner_spec(self, entry):
        front = copy.deepcopy(entry)
        front.update({"id": entry["taskId"], "taskOwner": entry["owner"], "workBranch": entry["branch"], "titleZh": entry["title"]})
        self.write("specs/tasks/OPS-003.md", "---\n" + yaml.safe_dump(front, sort_keys=False) + "---\n## Exclusive write scope\n" + "".join(f"- `{p}`\n" for p in entry["exclusivePaths"]) + "## Shared modification scope\n- none\n")

    def freeze(self):
        self.plan["status"] = "frozen"
        self.recovery = {"taskId": "OPS-003", "reason": "A completed contract needs forward correction", "affectedTasks": ["GZ-004"], "sourceCommit": self.base, "frozenAt": datetime.now(timezone.utc).isoformat(), "verificationPath": "evidence/OPS-003/recovery.json"}
        self.plan["recovery"] = self.recovery
        self.active["tasks"][0]["baseSha"] = self.base
        self.owner_spec(self.active["tasks"][0])
        self.save()
        self.frozen = self.commit("Freeze metadata only")
        return self.frozen

    def proof(self):
        self.write("scripts/repair.py", "print('forward repair')\n")
        self.source = self.commit("Governance repair on frozen base")
        common = f"--base-ref {self.frozen} --head-ref {self.source} --task OPS-003 --branch-name chore/OPS-003-recovery"
        self.junit = "evidence/OPS-003/governance.xml"
        commands = {
            "programIntegrity": f"python scripts/check-program-plan-integrity.py --base-ref {self.frozen}",
            "lifecycle": f"python scripts/run-program-lifecycle-gate.py {common}",
            "coordination": f"python scripts/run-agent-coordination-gate.py {common}",
            "governance": f"python -m pytest tests/governance -q --junitxml={self.junit}",
            "verify": f"make verify TASK=OPS-003 BASE={self.frozen} HEAD_REF={self.source} BRANCH=chore/OPS-003-recovery",
        }
        self.proof_document = {"taskId": "OPS-003", "frozenSourceCommit": self.base, "validatedCommit": self.source, "commands": {}, "junitPath": self.junit}
        for label, command in commands.items():
            path = f"evidence/OPS-003/{label}.txt"
            messages = {"programIntegrity": ["Program Plan execution and completion integrity passed"], "lifecycle": ["Program lifecycle scope, Foundation ownership, rename and Evidence guards passed", "Exact lifecycle diff and Completion Issue verification passed"], "coordination": ["Agent coordination valid: 2 active tasks, 1 high/critical"]}
            body = "\n".join(json.dumps({"status": "PASS", "message": message}) for message in messages.get(label, []))
            if label in {"governance", "verify"}:
                body = "1 passed in 0.01s\n"
            if label == "verify":
                body += "\n".join(f"=== {target} ===" for target in ("docs-check", "schema-check", "secret-scan", "task-verify", "governance-test")) + "\n"
            log = f"Source Commit: {self.source}\nCommand: {command}\n{body}\nExit Code: 0\n"
            self.write(path, log)
            self.proof_document["commands"][label] = {"command": command, "exitCode": 0, "logPath": path, "sha256": hashlib.sha256(log.encode()).hexdigest()}
        self.write(self.junit, '<testsuites><testsuite tests="1" failures="0" errors="0" skipped="0"><testcase name="fixture"/></testsuite></testsuites>')
        self.save_proof()
        return self.commit("Archive simulated unit fixture proof")

    def save_proof(self):
        self.proof_document["junitSha256"] = hashlib.sha256(Path(self.root, self.junit).read_bytes()).hexdigest()
        self.write(self.recovery["verificationPath"], json.dumps(self.proof_document))


@pytest.fixture
def repo(tmp_path):
    return Repository(tmp_path)


def errors_for(repo, function, base=None):
    errors = []
    function(repo.root, base or repo.base, "HEAD", errors)
    return errors


def test_freeze_metadata_and_governance_repair_pass(repo):
    frozen = repo.freeze()
    assert errors_for(repo, GUARD.validate_recovery_transition) == []
    repo.write("scripts/repair.py", "print('forward repair')\n")
    repo.commit("Declared governance repair")
    assert errors_for(repo, GUARD.validate_frozen_changes, frozen) == []


@pytest.mark.parametrize("path", ["business/file.txt", "evidence/GZ-004/summary.md"])
def test_frozen_rejects_ordinary_implementation_and_completed_evidence(repo, path):
    frozen = repo.freeze()
    repo.write(path, "Forbidden while frozen\n")
    repo.commit("Forbidden change")
    assert errors_for(repo, GUARD.validate_frozen_changes, frozen)


@pytest.mark.parametrize("status", ["reserved", "review", "completed"])
def test_frozen_rejects_ordinary_activation_or_completion(repo, status):
    frozen = repo.freeze()
    repo.plan["tasks"][1]["status"] = status
    repo.save()
    repo.commit("Ordinary transition")
    assert errors_for(repo, GUARD.validate_frozen_changes, frozen)


@pytest.mark.parametrize("field,value", [("dependsOn", []), ("riskLevel", "low"), ("outputPaths", ["business/**"])])
def test_frozen_block_cannot_change_identity_without_task_argument(repo, field, value):
    frozen = repo.freeze()
    repo.plan["tasks"][1].update({"status": "blocked", field: value})
    repo.save()
    repo.commit("Blocked with hidden identity drift")
    assert errors_for(repo, GUARD.validate_frozen_changes, frozen)
    result = subprocess.run([sys.executable, str(REPO / "scripts/check-program-plan-transitions.py"), "--repo-root", repo.root, "--base-ref", frozen], capture_output=True, text=True)
    assert result.returncode != 0 and "identity or scope" in result.stdout


def test_thaw_requires_merged_proof_and_separate_ordinary_activation(repo):
    repo.freeze()
    archive = repo.proof()
    repo.plan["status"] = "active"
    repo.save()
    repo.commit("Thaw only")
    assert errors_for(repo, GUARD.validate_recovery_transition, archive) == []
    repo.plan["tasks"][1]["status"] = "review"
    repo.save()
    repo.commit("Mixed ordinary activation")
    assert errors_for(repo, GUARD.validate_frozen_changes, archive)


@pytest.mark.parametrize("attack", ["hash", "echo", "wrong_source", "wrong_event", "missing_check", "bool_exit", "failure_node", "skip", "empty_junit", "false_count", "code_after_validation", "proof_not_in_base", "one_pass", "wrong_pytest_count"])
def test_thaw_rejects_forged_or_incomplete_proof(repo, attack):
    repo.freeze()
    archive = repo.proof()
    doc = repo.proof_document
    if attack == "hash":
        doc["commands"]["verify"]["sha256"] = "0" * 64
    elif attack == "echo":
        doc["commands"]["verify"]["command"] = "echo " + doc["commands"]["verify"]["command"]
    elif attack == "wrong_source":
        path = doc["commands"]["verify"]["logPath"]
        raw = Path(repo.root, path).read_text().replace(repo.source, repo.base)
        repo.write(path, raw)
        doc["commands"]["verify"]["sha256"] = hashlib.sha256(raw.encode()).hexdigest()
    elif attack == "wrong_event":
        doc["frozenSourceCommit"] = repo.frozen
    elif attack == "missing_check":
        doc["commands"].pop("coordination")
    elif attack == "bool_exit":
        doc["commands"]["verify"]["exitCode"] = False
    elif attack in {"one_pass", "wrong_pytest_count"}:
        item = doc["commands"]["governance"]
        body = "PASS" if attack == "one_pass" else "999 passed in 0.01s"
        raw = f"Source Commit: {repo.source}\nCommand: {item['command']}\n{body}\nExit Code: 0\n"
        repo.write(item["logPath"], raw)
        item["sha256"] = hashlib.sha256(raw.encode()).hexdigest()
    elif attack in {"failure_node", "skip", "empty_junit", "false_count"}:
        xml = '<testsuite tests="1" failures="0" errors="0" skipped="0"><testcase><failure/></testcase></testsuite>' if attack == "failure_node" else '<testsuite tests="1" failures="0" errors="0" skipped="1"><testcase><skipped/></testcase></testsuite>' if attack == "skip" else '<testsuite tests="0"/>' if attack == "empty_junit" else '<testsuite tests="2"><testcase/></testsuite>'
        repo.write(repo.junit, xml)
    elif attack == "code_after_validation":
        repo.write("scripts/repair.py", "print('unvalidated code')\n")
    elif attack == "proof_not_in_base":
        archive = repo.source
    repo.save_proof()
    if attack != "proof_not_in_base":
        archive = repo.commit("Adversarial archive")
    errors = []
    GUARD.validate_thaw_proof(repo.root, archive, repo.recovery, errors)
    assert errors, attack


def test_completed_evidence_repair_does_not_require_old_lease_or_branch(repo):
    repo.write("evidence/GZ-004/correction.md", "Evidence amendment\n")
    repo.commit("Evidence only")
    errors = []
    with patch.object(GUARD, "github_issue", return_value={"number": 14, "state": "closed", "state_reason": "completed"}):
        GUARD.validate_evidence_repair(repo.root, repo.base, "HEAD", "GZ-004", "fix/GZ-004-evidence", errors)
    assert errors == []


@pytest.mark.parametrize("path", [GUARD.PLAN, GUARD.ACTIVE, GUARD.LEDGER, "specs/tasks/GZ-004.md", "evidence/GZ-010/correction.md", "business/file.txt"])
def test_completed_evidence_repair_rejects_metadata_and_cross_task_changes(repo, path):
    Path(repo.root, path).parent.mkdir(parents=True, exist_ok=True)
    with Path(repo.root, path).open("a", encoding="utf-8") as output:
        output.write("\n# forbidden amendment\n")
    repo.commit("Forbidden amendment")
    errors = []
    GUARD.validate_evidence_repair(repo.root, repo.base, "HEAD", "GZ-004", "fix/GZ-004-evidence", errors)
    assert errors


@pytest.mark.parametrize("issue", [{"number": 14, "state": "open", "state_reason": None}, {"number": 14, "state": "closed", "state_reason": "not_planned"}, {"number": 99, "state": "closed", "state_reason": "completed"}, {"number": 14, "state": "closed", "state_reason": "completed", "pull_request": {}}])
def test_completed_evidence_repair_rejects_wrong_issue_in_shared_validator(repo, issue):
    repo.write("evidence/GZ-004/correction.md", "Amendment\n")
    repo.commit("Evidence only")
    errors = []
    with patch.object(GUARD, "github_issue", return_value=issue):
        GUARD.validate_evidence_repair(repo.root, repo.base, "HEAD", "GZ-004", "fix/GZ-004-evidence", errors)
    assert errors


def test_raw_lifecycle_main_enforces_evidence_issue_without_task_argument(repo):
    repo.write("evidence/GZ-004/correction.md", "Amendment\n")
    repo.commit("Evidence only")
    args = ["guard", "--repo-root", repo.root, "--base-ref", repo.base, "--branch-name", "main"]
    with patch.object(sys, "argv", args), patch.object(GUARD, "github_issue", return_value={"number": 14, "state": "open"}):
        assert GUARD.main() == 1


def test_completed_evidence_rename_cannot_hide_business_origin(repo):
    repo.git("mv", "business/file.txt", "evidence/GZ-004/file.txt")
    repo.commit("Rename out of business")
    errors = []
    GUARD.validate_evidence_repair(repo.root, repo.base, "HEAD", "GZ-004", "fix/GZ-004-evidence", errors)
    assert errors


@pytest.mark.parametrize("attack", [None, "broad_claim", "business_claim", "shared_claim", "expired", "same_reviewer", "policy", "implementation", "ledger", "completion"])
def test_new_foundation_registration_is_metadata_only_and_strict(tmp_path, attack):
    repo = Repository(tmp_path, owner=False)
    entry = repo.add_owner("reserved")
    if attack == "broad_claim":
        entry["exclusivePaths"] = ["specs/**"]
    elif attack == "business_claim":
        entry["exclusivePaths"] = ["business/**"]
    elif attack == "shared_claim":
        entry["sharedPaths"] = ["scripts/repair.py"]
    elif attack == "expired":
        entry["lease"]["expiresAt"] = entry["lease"]["acquiredAt"]
    elif attack == "same_reviewer":
        entry["reviewer"] = entry["implementer"]
    elif attack == "policy":
        repo.active["policy"]["leaseMaxHours"] = 999
    elif attack == "implementation":
        repo.write("scripts/repair.py", "Premature implementation\n")
    elif attack == "ledger":
        repo.ledger["records"].append({"taskId": "OPS-003"})
    elif attack == "completion":
        repo.plan["foundationTasks"][0]["mergeCommit"] = repo.base
    repo.owner_spec(entry)
    repo.save()
    repo.commit("New governance reservation")
    errors = []
    TRANSITIONS.validate_foundation_registration(repo.root, repo.base, "HEAD", "OPS-003", GUARD.load_ref(repo.root, repo.base, GUARD.PLAN), repo.plan, GUARD.load_ref(repo.root, repo.base, GUARD.ACTIVE), repo.active, errors)
    assert bool(errors) == (attack is not None), errors


def test_existing_foundation_cannot_expand_claim_after_registration(repo):
    entry = repo.active["tasks"][0]
    entry.update({"baseSha": repo.base, "exclusivePaths": ["specs/**"]})
    errors = []
    GUARD.validate_foundation_claims("OPS-003", entry, repo.ownership, repo.base, errors)
    assert errors


def test_frozen_existing_active_snapshot_can_remain(repo):
    frozen = repo.freeze()
    repo.commit("No ordinary work")
    assert errors_for(repo, GUARD.validate_frozen_changes, frozen) == []


@pytest.mark.parametrize("field,value", [("sourceCommit", "f" * 40), ("affectedTasks", ["GZ-010"]), ("frozenAt", "2999-01-01T00:00:00Z")])
def test_frozen_snapshot_revalidates_descriptor_references(repo, field, value):
    repo.freeze()
    repo.plan["recovery"][field] = value
    repo.save()
    repo.commit("Invalid descriptor")
    errors = []
    GUARD.validate_frozen_snapshot(repo.root, repo.plan, errors)
    assert errors


@pytest.mark.parametrize("status", ["blocked", "cancelled"])
def test_frozen_block_or_cancel_cannot_keep_stale_task_status(repo, status):
    frozen = repo.freeze()
    repo.plan["tasks"][1]["status"] = status
    repo.save()
    repo.commit("Stale Task Spec")
    errors = errors_for(repo, GUARD.validate_frozen_changes, frozen)
    assert any("Task Spec must match" in e for e in errors)


def test_completed_evidence_api_unavailable_fails_closed(repo):
    repo.write("evidence/GZ-004/correction.md", "Amendment\n")
    repo.commit("Evidence only")
    errors = []
    with patch.object(GUARD, "github_issue", side_effect=RuntimeError("API unavailable")):
        GUARD.validate_evidence_repair(repo.root, repo.base, "HEAD", "GZ-004", "fix/GZ-004-evidence", errors)
    assert any("cannot be verified" in e for e in errors)


@pytest.mark.parametrize("document", ["program", "registry"])
def test_no_task_frozen_root_or_registry_policy_drift_is_rejected(repo, document):
    frozen = repo.freeze()
    if document == "program":
        repo.plan["releasePolicy"] = {"allowUnverified": True}
    else:
        repo.active["policy"]["leaseMaxHours"] = 999
    repo.save()
    repo.commit("Pure policy drift")
    assert errors_for(repo, GUARD.validate_frozen_changes, frozen)


def test_no_task_frozen_code_derives_recovery_owner_and_rejects_stale_base(repo):
    frozen = repo.freeze()
    repo.write("scripts/repair.py", "Changed without updated audited base\n")
    repo.commit("Pure code diff")
    assert GUARD.frozen_repair_task_ids(repo.root, frozen, "HEAD") == {"OPS-003"}
    args = ["guard", "--repo-root", repo.root, "--base-ref", frozen, "--branch-name", "main"]
    with patch.object(sys, "argv", args):
        assert GUARD.main() == 1
