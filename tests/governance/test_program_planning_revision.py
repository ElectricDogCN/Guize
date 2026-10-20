"""Real Git histories for registered planning and baseline admission."""
import copy
import importlib.util
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import jsonschema
import yaml
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
MODULE_SPEC = importlib.util.spec_from_file_location("planning_revision_tests", ROOT / "scripts/program-planning-revision.py")
PLANNING = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(PLANNING)
# This accepted predecessor has no OPS009 reservation. Its reachable completed
# task histories remain real, so the fixtures do not manufacture old PASS data.
PREDECESSOR = "bf0e5cbf51c1f8991986f503e22d1312ac9b5836"
ORIGINAL_RESERVATION = "82ceeaf0b6f6d31e7614de9dbdd89a5853d9386b"
OWNER = "OPS-777"
EDGE_ADMISSION = "39afaf007d800bab43d7703ac082df2bbc7e8e87"
EDGE_FIRST_USE = "evidence/OPS-011/agent-edge-104-first-use.json"
EDGE_FIRST_USE_SHA256 = "2815479d0d322abc8afdf94e73518f0b9a0fa23fbcc0a5bd39c9e9daaa6017d9"


class History:
    def __init__(self, root, *, ordinary=False, merge_registration=True):
        self.root = root / "repo"
        subprocess.run(["git", "clone", "--shared", "--no-checkout", "--quiet", str(ROOT), str(self.root)], check=True, capture_output=True)
        self.git("config", "user.name", "Planning fixture")
        self.git("config", "user.email", "fixture@example.com")
        self.git("config", "core.autocrlf", "false")
        self.git("checkout", "-B", "main", PREDECESSOR)
        self.owner = "GZ-777" if ordinary else OWNER
        self.branch = f"chore/{self.owner}-planning-revision-admission"
        self.plan = self.read(PLANNING.PLAN)
        self.active = self.read(PLANNING.ACTIVE)
        self.manifest = json.loads((ROOT / "evidence/OPS-009/planning-revision.json").read_text(encoding="utf-8"))
        self.manifest["taskId"] = self.owner
        self.manifest["targets"][0]["after"]["dependsOn"][-1] = self.owner
        # Keep the original nine-claim fixture stable after the real project
        # adopts its tenth claim; the tests must exercise an actual expansion.
        self.entry = copy.deepcopy(PLANNING.document(str(ROOT), ORIGINAL_RESERVATION, PLANNING.ACTIVE)["tasks"][0])
        self.entry.update(taskId=self.owner, programTaskId=self.owner, issue=777, status="reserved", agentRole="coordinator", branch=self.branch, dependsOn=[])
        now = datetime.now(timezone.utc)
        self.entry["lease"] = {"acquiredAt": (now-timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ"), "expiresAt": (now+timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        raw_task = PLANNING.blob(str(ROOT), ORIGINAL_RESERVATION, "specs/tasks/OPS-009.md").decode("utf-8").split("---", 2)
        self.front = yaml.safe_load(raw_task[1])
        self.body = raw_task[2].replace("OPS-009", self.owner)
        self.front.update(id=self.owner, programTaskId=self.owner, issue=777, status="reserved", agentRole="coordinator", workBranch=self.branch, dependsOn="", leaseExpiresAt=self.entry["lease"]["expiresAt"])
        self.task_path = f"specs/tasks/{self.owner}.md"
        for path in [PLANNING.PROGRAM_SCHEMA, PLANNING.MANIFEST_SCHEMA, "scripts/program-planning-revision.py", "scripts/check-program-plan-transitions.py", "scripts/check-program-lifecycle-guards.py", "scripts/check-program-plan-history.py"]:
            self.write(path, (ROOT / path).read_text(encoding="utf-8"))
        if ordinary:
            self.entry["moduleIds"] = ["MOD-GOV", "MOD-PLATFORM"]
            self.entry["exclusivePaths"] = [PLANNING.PLAN, "docs/00-guize-engineering-design-baseline.md"]
            exact_claims = "\n".join(f"- `{path}`" for path in self.entry["exclusivePaths"])
            for heading in ("允许范围", "独占写范围"):
                self.body = re.sub(rf"(?ms)^## {heading}\r?\n.*?(?=^## |\Z)", f"## {heading}\n\n{exact_claims}\n\n", self.body)
            self.front["moduleIds"] = "MOD-GOV, MOD-PLATFORM"
            self.entry["programWave"] = self.front["wave"] = "W2"
            planner = copy.deepcopy(self.manifest["targets"][0]["after"])
            planner.update(taskId=self.owner, title=self.entry["title"], workPackage=self.entry["workPackage"], dependsOn=[], moduleIds=self.entry["moduleIds"], requirementIds=self.entry["requirementIds"], outputPaths=self.entry["exclusivePaths"], consumesContracts=self.entry["consumesContracts"], producesContracts=self.entry["producesContracts"], coordinationGroup=self.entry["coordinationGroup"], integrationOrder=self.entry["integrationOrder"], branchPattern=f"chore/{self.owner}-*")
            self.plan["tasks"].append(planner)
            final = next(t for t in self.plan["tasks"] if t["taskId"] == "GZ-020")
            final["dependsOn"].append(self.owner)
            edit = self.manifest["targets"][1]
            edit["before"] = copy.deepcopy(final)
            edit["after"] = copy.deepcopy(final)
            edit["after"]["dependsOn"].append("GZ-021")
            edit["originalDefinitionSha256"] = hashlib.sha256(json.dumps(final, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
            self.dump(PLANNING.PLAN, self.plan)
        self.base = self.commit("Fixture adopted typed mechanism baseline")
        self.entry["baseSha"] = self.front["baseSha"] = self.base
        self.manifest["reservationParent"] = self.base
        self.git("checkout", "-b", "reservation")
        if ordinary:
            next(t for t in self.plan["tasks"] if t["taskId"] == self.owner).update(status="reserved", issue=777)
        else:
            self.plan["foundationTasks"].append({"taskId": self.owner, "title": self.entry["title"], "status": "reserved", "completionRef": "ISSUE-777", "mergeCommit": None})
        self.active["tasks"].append(self.entry)
        self.save()
        self.dump(f"evidence/{self.owner}/planning-revision.json", self.manifest)
        self.commit(f"Reserve {self.owner} #777")
        if merge_registration:
            self.git("checkout", "main")
            self.git("merge", "--no-ff", "--no-edit", "reservation")
        self.registration = self.git("rev-parse", "HEAD")
        self.git("checkout", "-b", self.branch)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE, encoding="utf-8").strip()

    def read(self, path):
        return yaml.safe_load((self.root / path).read_text(encoding="utf-8"))

    def write(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")

    def dump(self, path, value):
        text = json.dumps(value, ensure_ascii=False, indent=2)+"\n" if path.endswith(".json") else yaml.safe_dump(value, sort_keys=False, allow_unicode=True)
        self.write(path, text)

    def save(self):
        self.dump(PLANNING.PLAN, self.plan)
        self.dump(PLANNING.ACTIVE, self.active)
        self.write(self.task_path, "---\n"+yaml.safe_dump(self.front, sort_keys=False, allow_unicode=True)+"---"+self.body)

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "--allow-empty", "-m", message)
        return self.git("rev-parse", "HEAD")

    def apply(self):
        section = "tasks" if self.owner.startswith("GZ-") else "foundationTasks"
        next(t for t in self.plan[section] if t["taskId"] == self.owner)["status"] = "in_progress"
        self.entry.update(status="in_progress", agentRole="implementer", baseSha=self.registration)
        self.front.update(status="in_progress", agentRole="implementer", baseSha=self.registration)
        for target in self.manifest["targets"]:
            if target["kind"] == "add-planned-task":
                self.plan["tasks"].append(copy.deepcopy(target["after"]))
            elif target["kind"] == "edit-planned-task":
                self.plan["tasks"] = [copy.deepcopy(target["after"]) if row["taskId"] == target["id"] else row for row in self.plan["tasks"]]
            else:
                self.plan.setdefault("planningBaselines", []).append(copy.deepcopy(target["after"]))

    def finish(self):
        self.save()
        return self.commit(f"Implement exact transaction {self.owner} #778")

    def decision(self, *, base=None, owner_hint=None, observed_at=None):
        base = base or self.registration
        head = self.git("rev-parse", "HEAD")
        errors = []
        decision = PLANNING.classifier(str(self.root), base, head, PLANNING.document(str(self.root), base, PLANNING.PLAN), self.read(PLANNING.PLAN), errors, owner_hint=owner_hint or self.owner, observed_at=observed_at)
        return decision, errors

    def gate(self, script, *, task=True):
        args = [sys.executable, "-X", "utf8", str(ROOT / "scripts" / script), "--repo-root", str(self.root), "--base-ref", self.registration, "--head-ref", "HEAD", "--branch-name", self.branch]
        if task:
            args.extend(["--task", self.owner])
        return subprocess.run(args, capture_output=True, text=True, encoding="utf-8")

    def scope_amendment(self, *, case="valid", merged=True):
        self.git("checkout", "main")
        self.plan = self.read(PLANNING.PLAN)
        self.active = self.read(PLANNING.ACTIVE)
        self.entry = next(row for row in self.active["tasks"] if row["taskId"] == self.owner)
        self.front = yaml.safe_load((self.root/self.task_path).read_text(encoding="utf-8").split("---", 2)[1])
        self.entry["baseSha"] = self.front["baseSha"] = self.git("rev-parse", "HEAD")
        self.entry["exclusivePaths"].append("scripts/check-project-readiness.py")
        self.git("checkout", "-b", "scope-amendment")
        if case == "code":
            self.write("scripts/check-project-readiness.py", "# scope and code in the same amendment\n")
        elif case == "foreign_program":
            self.plan["tasks"][0]["title"] += " unauthorized"
        elif case == "policy":
            self.active["policy"]["leaseMaxHours"] = 167
        elif case == "identity":
            self.entry["reviewer"] = self.front["reviewer"] = "different-reviewer"
        elif case == "lease":
            self.entry["lease"]["expiresAt"] = (datetime.now(timezone.utc)+timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.front["leaseExpiresAt"] = self.entry["lease"]["expiresAt"]
        elif case == "manifest":
            amended = copy.deepcopy(self.manifest)
            amended["targets"][0]["after"]["title"] += " unauthorized"
            self.dump(f"evidence/{self.owner}/planning-revision.json", amended)
        self.save()
        self.commit(f"Own metadata scope amendment {self.owner}")
        if merged:
            self.git("checkout", "main")
            self.git("merge", "--no-ff", "--no-edit", "scope-amendment")
            self.registration = self.git("rev-parse", "HEAD")
        self.git("checkout", "-B", self.branch, self.registration)


@pytest.fixture
def history(tmp_path):
    return History(tmp_path)


def test_exact_three_target_transaction(history):
    history.apply()
    history.finish()
    result, errors = history.decision()
    assert not errors
    assert result["registration"] == history.registration
    assert result["targetTaskIds"] == {"GZ-021", "GZ-020"}
    assert "planningBaselines" not in result["projectedPlan"]
    assert len(PLANNING.frontier(history.plan, history.plan["planningBaselines"][0]["requiredBy"])) == 23


def test_ordinary_requirements_planner_with_business_module(tmp_path):
    history = History(tmp_path, ordinary=True)
    history.apply()
    history.finish()
    result, errors = history.decision()
    assert not errors
    assert result["owner"] == "GZ-777"


@pytest.mark.parametrize("script", ["check-program-plan-transitions.py", "check-program-lifecycle-guards.py", "check-program-plan-history.py"])
def test_ordinary_document_planner_through_actual_checkers(tmp_path, script):
    history = History(tmp_path, ordinary=True)
    history.apply()
    history.finish()
    result = history.gate(script)
    assert result.returncode == 0, result.stdout + result.stderr


def test_prior_canonical_metadata_scope_authorizes_claims(history):
    original = history.registration
    history.scope_amendment()
    history.apply()
    history.finish()
    result, errors = history.decision()
    assert not errors
    assert result["registration"] == original
    assert "scripts/check-project-readiness.py" in history.entry["exclusivePaths"]


@pytest.mark.parametrize("case", ["code", "foreign_program", "policy", "identity", "lease", "manifest"])
def test_invalid_prior_scope_amendment_never_authorizes(history, case):
    history.scope_amendment(case=case)
    history.apply()
    history.finish()
    result, errors = history.decision()
    assert result is None and errors


def test_scope_on_unmerged_side_branch_does_not_authorize(history):
    history.scope_amendment(merged=False)
    history.apply()
    history.finish()
    result, errors = history.decision()
    assert result is None and errors


def test_ordinary_planner_cannot_expand_scope_on_main(tmp_path):
    history = History(tmp_path, ordinary=True)
    history.scope_amendment()
    history.apply()
    history.finish()
    result, errors = history.decision()
    assert result is None
    assert any("Ordinary planner" in error for error in errors)


def test_scope_on_head_code_commit_does_not_authorize(history):
    history.entry["exclusivePaths"].append("scripts/check-project-readiness.py")
    history.apply()
    history.finish()
    result, errors = history.decision()
    assert result is None
    assert any("prior registered claims" in error for error in errors)


def test_later_canonical_scope_is_not_retroactive(history):
    admitted = history.registration
    history.entry["exclusivePaths"].append("scripts/check-project-readiness.py")
    history.apply()
    code = history.finish()
    history.scope_amendment()
    history.git("checkout", "--detach", code)
    result, errors = history.decision(base=admitted)
    assert result is None
    assert any("prior registered claims" in error for error in errors)


@pytest.mark.parametrize("script", ["check-program-plan-transitions.py", "check-program-lifecycle-guards.py", "check-program-plan-history.py"])
def test_three_checkers_accept_prior_scope(history, script):
    history.scope_amendment()
    history.apply()
    history.finish()
    result = history.gate(script)
    assert result.returncode == 0, result.stdout+result.stderr


@pytest.mark.parametrize("script", ["check-program-plan-transitions.py", "check-program-lifecycle-guards.py", "check-program-plan-history.py"])
@pytest.mark.parametrize("task", [True, False])
def test_three_checkers_accept_declared_first_use(history, script, task):
    history.apply()
    history.finish()
    result = history.gate(script, task=task)
    assert result.returncode == 0, result.stdout+result.stderr


@pytest.mark.parametrize("case", ["missing_target", "extra_task", "policy", "frozen", "wrong_role", "review_phase", "expired", "claims", "manifest", "already_started", "alternate_task_spec", "root_registry", "ledger", "working_tree_view"])
def test_invalid_transactions_never_project(history, case):
    history.apply()
    if case == "missing_target":
        history.plan.pop("planningBaselines")
    elif case == "extra_task":
        history.plan["tasks"][0]["title"] += " undeclared"
    elif case == "policy":
        history.plan["releasePolicy"]["requiredFinalTask"] = "GZ-021"
    elif case == "frozen":
        history.plan["status"] = "frozen"
    elif case == "wrong_role":
        history.entry["agentRole"] = history.front["agentRole"] = "reviewer"
    elif case == "review_phase":
        history.entry["status"] = history.front["status"] = "review"
        next(t for t in history.plan["foundationTasks"] if t["taskId"] == history.owner)["status"] = "review"
    elif case == "expired":
        history.entry["lease"]["expiresAt"] = (datetime.now(timezone.utc)-timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    elif case == "claims":
        history.entry["exclusivePaths"].append("backend/**")
    elif case == "manifest":
        changed = copy.deepcopy(history.manifest)
        changed["targets"][0]["after"]["title"] += " changed"
        history.dump(f"evidence/{history.owner}/planning-revision.json", changed)
    elif case == "already_started":
        next(t for t in history.plan["tasks"] if t["taskId"] == "POC-003")["status"] = "reserved"
    elif case == "alternate_task_spec":
        history.write("specs/tasks/POC-003-hidden-spec.md", "---\nid: POC-003\n---\n")
    elif case == "root_registry":
        history.active["policy"]["leaseMaxHours"] = 167
    elif case == "ledger":
        changed = history.read(PLANNING.LEDGER)
        changed["records"][0]["completionRef"] = "PR-999"
        history.dump(PLANNING.LEDGER, changed)
    history.finish()
    if case == "working_tree_view":
        history.plan["tasks"][-1]["title"] += " uncommitted"
        history.dump(PLANNING.PLAN, history.plan)
    decision, errors = history.decision()
    assert decision is None and errors


def test_registration_on_unmerged_sibling_is_not_authority(tmp_path):
    history = History(tmp_path, merge_registration=False)
    history.apply()
    history.finish()
    result, errors = history.decision()
    assert result is None
    assert any("canonical main" in error for error in errors)


def test_registration_and_implementation_in_same_candidate(history):
    history.apply()
    history.finish()
    result, errors = history.decision(base=history.base)
    assert result is None and errors


@pytest.mark.parametrize("case", ["unknown_consumer", "duplicate_consumer", "self_edge", "cycle", "duplicate_id", "unknown_field"])
def test_invalid_baseline_graphs(history, case):
    history.apply()
    baseline = history.plan["planningBaselines"][0]
    if case == "unknown_consumer":
        baseline["requiredBy"].append("GZ-999")
    elif case == "duplicate_consumer":
        baseline["requiredBy"].append(baseline["requiredBy"][0])
    elif case == "self_edge":
        baseline["requiredBy"].append("GZ-021")
    elif case == "cycle":
        next(t for t in history.plan["tasks"] if t["taskId"] == "GZ-021")["dependsOn"].append("GZ-006")
    elif case == "duplicate_id":
        history.plan["planningBaselines"].append(copy.deepcopy(baseline))
    else:
        baseline["optionalBy"] = []
    with pytest.raises(PLANNING.PlanningError):
        PLANNING.validate_baselines(history.plan)


@pytest.mark.parametrize("consumer", ["GZ-006", "POC-003", "POC-005"])
def test_pending_producer_blocks_explicit_consumers(history, consumer):
    history.apply()
    installed = history.finish()
    errors = []
    PLANNING.enforce_consumers(str(history.root), installed, installed, history.plan, history.plan, {consumer}, set(), errors)
    assert any("pending real completed producer" in error for error in errors)


def test_pending_producer_blocks_no_task_code_owner(history):
    history.apply()
    installed = history.finish()
    consumer = next(t for t in history.plan["tasks"] if t["taskId"] == "POC-003")
    claim = next(p for p in consumer["outputPaths"] if not p.startswith("evidence/"))
    path = claim.replace("**", "unauthorized.py").replace("*", "unauthorized")
    history.write(path, "# unregistered consumer code\n")
    head = history.commit("Unregistered POC-003 code")
    errors, affected = [], set()
    PLANNING.enforce_consumers(str(history.root), installed, head, history.plan, history.plan, affected, {path}, errors)
    assert "POC-003" in affected and errors


@pytest.mark.parametrize("case", ["remove", "narrow", "substitute"])
def test_existing_baseline_cannot_be_changed(history, case):
    history.apply()
    installed = history.finish()
    if case == "remove":
        history.plan.pop("planningBaselines")
    elif case == "narrow":
        history.plan["planningBaselines"][0]["requiredBy"].pop()
    else:
        history.plan["planningBaselines"][0]["taskId"] = "GZ-005"
    history.dump(PLANNING.PLAN, history.plan)
    head = history.commit("Attempt to weaken existing baseline")
    errors = []
    result = PLANNING.classifier(str(history.root), installed, head, PLANNING.document(str(history.root), installed, PLANNING.PLAN), history.plan, errors)
    assert result is None and errors


def test_actual_completed_producer_provenance_retained(history):
    assert PLANNING.completed_producer(str(history.root), history.registration, "GZ-005")
    assert not PLANNING.completed_producer(str(history.root), history.registration, "GZ-021")


def readiness(history):
    return subprocess.run([sys.executable, "-X", "utf8", str(ROOT / "scripts/check-project-readiness.py"), "--repo-root", str(history.root)], capture_output=True, text=True, encoding="utf-8")


def install_serial_baseline(history):
    history.apply()
    return history.finish()


def test_readiness_authenticated_baseline_and_inherited_history(history):
    install_serial_baseline(history)
    result = readiness(history)
    assert result.returncode == 0, result.stdout + result.stderr
    history.write(f"evidence/{history.owner}/later.md", "Later evidence without a new authority grant.\n")
    history.commit("Later evidence")
    result = readiness(history)
    assert result.returncode == 0, result.stdout + result.stderr
    errors = []
    pairs = PLANNING.serial_baseline_pairs(str(history.root), "HEAD", history.plan, errors)
    assert not errors and len(pairs) == 23
    assert frozenset(("GZ-021", "POC-003")) in pairs
    assert frozenset(("GZ-021", "POC-005")) in pairs
    assert frozenset(("POC-003", "POC-005")) not in pairs


def test_readiness_legacy_and_missing_baseline_keep_conflicts(history):
    result = readiness(history)
    assert result.returncode == 0, result.stdout + result.stderr
    history.apply()
    history.plan.pop("planningBaselines")
    history.finish()
    result = readiness(history)
    assert result.returncode != 0
    assert "output path conflict" in result.stdout and "POC-003" in result.stdout and "POC-005" in result.stdout


@pytest.mark.parametrize("case", ["forged", "unbound", "narrowed", "unknown", "cycle"])
def test_readiness_rejects_unauthenticated_serialization(history, case):
    install_serial_baseline(history)
    if case == "forged":
        altered = copy.deepcopy(history.manifest)
        altered["targets"][0]["after"]["title"] += " forged"
        history.dump(f"evidence/{history.owner}/planning-revision.json", altered)
    elif case == "unbound":
        history.plan["tasks"][-1]["title"] += " dirty"
    elif case == "narrowed":
        history.plan["planningBaselines"][0]["requiredBy"].pop()
    elif case == "unknown":
        history.plan["planningBaselines"][0]["requiredBy"].append("GZ-999")
    else:
        next(t for t in history.plan["tasks"] if t["taskId"] == "GZ-021")["dependsOn"].append("GZ-006")
    history.save()
    if case != "unbound":
        history.commit("Invalid serial grant")
    result = readiness(history)
    assert result.returncode != 0
    assert "baseline authentication rejected" in result.stdout


@pytest.mark.parametrize("case", ["reserved", "in_progress", "lease", "task_spec", "both_active", "dirty_lease", "dirty_task_spec"])
def test_readiness_does_not_waive_live_consumer_conflicts(history, case):
    install_serial_baseline(history)
    consumer = next(t for t in history.plan["tasks"] if t["taskId"] == "POC-003")
    if case in {"reserved", "in_progress", "both_active"}:
        consumer["status"] = "reserved" if case == "reserved" else "in_progress"
    if case in {"lease", "both_active", "dirty_lease"}:
        entry = copy.deepcopy(history.entry)
        entry.update(taskId="POC-003", programTaskId="POC-003")
        history.active["tasks"].append(entry)
    if case == "both_active":
        next(t for t in history.plan["tasks"] if t["taskId"] == "GZ-021")["status"] = "in_progress"
    if case in {"task_spec", "dirty_task_spec"}:
        history.write("specs/tasks/POC-003-other-name.md", "---\nid: POC-003\n---\n")
    history.save()
    if not case.startswith("dirty_"):
        history.commit("Consumer has started")
    result = readiness(history)
    assert result.returncode != 0
    assert "output path conflict" in result.stdout and "POC-003" in result.stdout


@pytest.mark.parametrize("case,message", [
    ("unrelated", "output path conflict"),
    ("capacity", "concurrent task capacity"),
    ("high_risk", "high-risk task capacity"),
    ("critical", "critical task that is not standalone"),
    ("ownership", "without declaring MOD-ASSET"),
    ("wave", "later-wave task"),
    ("mirror", "POC"),
])
def test_readiness_serialization_retains_other_guards(history, case, message):
    install_serial_baseline(history)
    consumer = next(t for t in history.plan["tasks"] if t["taskId"] == "POC-003")
    if case == "unrelated":
        consumer["outputPaths"].append("poc/POC-05-metadata-scale/**")
    elif case == "capacity":
        next(w for w in history.plan["waves"] if w["id"] == "W2")["maxConcurrent"] = 1
    elif case == "high_risk":
        consumer["riskLevel"] = "high"
    elif case == "critical":
        consumer["riskLevel"] = "critical"
    elif case == "ownership":
        consumer["outputPaths"].append("backend/guize-asset-catalog/escape.py")
    elif case == "wave":
        consumer["dependsOn"].append("GZ-019")
    else:
        consumer["pocIds"] = []
    history.dump(PLANNING.PLAN, history.plan)
    history.commit("Unrelated readiness violation")
    result = readiness(history)
    assert result.returncode != 0
    assert message in result.stdout, result.stdout + result.stderr


def test_unrelated_legacy_callback_supplies_no_planning_projection(history):
    install_serial_baseline(history)
    # Existing Foundation-history fixtures remove unrelated Foundation rows
    # from both snapshots; focused lifecycle callbacks supply no permission
    # to edit ordinary definitions or execute baseline consumers.
    history.plan["foundationTasks"] = [r for r in history.plan["foundationTasks"] if r["taskId"] != history.owner]
    history.dump(PLANNING.PLAN, history.plan)
    base = history.commit("Legacy focused history baseline")
    errors = []
    result = PLANNING.classifier(str(history.root), base, base, history.plan, history.plan, errors)
    assert result is None and not errors
    PLANNING.enforce_consumers(str(history.root), base, base, history.plan, history.plan, {"GZ-014"}, set(), errors)
    assert not errors
    # A relevant execution still performs the complete graph checks.
    PLANNING.enforce_consumers(str(history.root), base, base, history.plan, history.plan, {"GZ-006"}, set(), errors)
    assert any("Unknown dependency" in e for e in errors)
    history.plan["tasks"][-1]["title"] += " unapproved"
    history.dump(PLANNING.PLAN, history.plan)
    head = history.commit("Attempt ordinary definition change")
    errors = []
    result = PLANNING.classifier(str(history.root), base, head, PLANNING.document(str(history.root), base, PLANNING.PLAN), history.plan, errors)
    assert result is None and errors


def test_no_task_parameter_spec_identity_still_detects_consumer_start(history):
    base = install_serial_baseline(history)
    path = "specs/tasks/alternate-filename.md"
    history.write(path, "---\nid: GZ-006\n---\n")
    head = history.commit("Consumer Task Spec without Program or Registry change")
    errors = []
    PLANNING.enforce_consumers(str(history.root), base, head, history.plan, history.plan, set(), {path}, errors)
    assert any("pending real completed producer" in e and "GZ-006" in e for e in errors)


def test_immutable_data_cache_does_not_cache_aliases_or_mutable_views(history):
    install_serial_baseline(history)
    path = f"evidence/{history.owner}/planning-revision.json"
    original = PLANNING.blob(str(history.root), "HEAD", path)
    view = PLANNING.document(str(history.root), "HEAD", PLANNING.PLAN)
    view["planningBaselines"][0]["requiredBy"].clear()
    assert PLANNING.document(str(history.root), "HEAD", PLANNING.PLAN) == history.plan
    changed = copy.deepcopy(history.manifest)
    changed["targets"][0]["after"]["title"] += " forged"
    history.dump(path, changed)
    history.commit("Alias advances to changed manifest")
    assert PLANNING.blob(str(history.root), "HEAD", path) != original
    errors = []
    assert not PLANNING.serial_baseline_pairs(str(history.root), "HEAD", history.plan, errors)
    assert any("original manifest changed" in e for e in errors)


def test_immutable_data_cache_never_reuses_lease_decisions(history):
    install_serial_baseline(history)
    assert history.decision()[0] is not None
    expired = datetime.fromisoformat(history.entry["lease"]["expiresAt"].replace("Z", "+00:00")) + timedelta(seconds=1)
    result, errors = history.decision(observed_at=expired)
    assert result is None and any("lease expired" in e for e in errors)


def test_completed_unchanged_context_does_not_replace_real_owner(history):
    install_serial_baseline(history)
    result, errors = history.decision(owner_hint="GZ-014")
    assert not errors and result["owner"] == history.owner


@pytest.mark.parametrize("case", ["unknown", "own_evidence", "own_task_body"])
def test_wrong_or_modified_completed_context_cannot_filter_owner(history, case):
    install_serial_baseline(history)
    hint = "GZ-999" if case == "unknown" else "GZ-014"
    if case == "own_evidence":
        history.write("evidence/GZ-014/extra.md", "Unrelated completed evidence change.\n")
        history.commit("Mixed completed Evidence")
    elif case == "own_task_body":
        path, _ = PLANNING.spec(str(history.root), "HEAD", hint)
        history.write(path, (history.root/path).read_text(encoding="utf-8")+"\nUnrelated body change.\n")
        history.commit("Mixed completed Task body")
    result, errors = history.decision(owner_hint=hint)
    assert result is None and errors


def test_original_consumer_closure_survives_dependency_removal(history):
    installed = install_serial_baseline(history)
    original = copy.deepcopy(history.plan)
    row = original["planningBaselines"][0]
    assert len(PLANNING.original_consumers(str(history.root), installed, row)) == 23
    next(t for t in history.plan["tasks"] if t["taskId"] == "GZ-007")["dependsOn"].remove("GZ-006")
    assert len(PLANNING.frontier(history.plan, row["requiredBy"])) == 22
    with pytest.raises(PLANNING.PlanningError, match="original consumer closure was narrowed"):
        PLANNING.preserve_consumer_closures(str(history.root), installed, history.plan, {row["id"]: row})
    history.dump(PLANNING.PLAN, history.plan)
    narrowed = history.commit("Narrow descendant dependency without changing baseline row")
    errors = []
    # This predicate denies narrowing; it does not pretend the old immutable
    # manifest authorizes a new planning transaction.
    PLANNING.enforce_consumers(str(history.root), installed, narrowed, original, history.plan, {"GZ-007"}, set(), errors)
    assert any("original consumer closure was narrowed" in e for e in errors)
    errors = []
    PLANNING.enforce_consumers(str(history.root), narrowed, narrowed, history.plan, history.plan, {"GZ-007"}, set(), errors)
    assert errors
    result = readiness(history)
    assert result.returncode != 0 and "original consumer closure was narrowed" in result.stdout


def test_original_consumer_closure_allows_superset_without_authorizing_changes(history):
    installed = install_serial_baseline(history)
    row = history.plan["planningBaselines"][0]
    proposed = copy.deepcopy(history.plan)
    task = copy.deepcopy(next(t for t in proposed["tasks"] if t["taskId"] == "GZ-007"))
    task["taskId"] = "GZ-998"
    proposed["tasks"].append(task)
    assert len(PLANNING.frontier(proposed, row["requiredBy"])) == 24
    PLANNING.preserve_consumer_closures(str(history.root), installed, proposed, {row["id"]: row})
    assert "GZ-998" not in PLANNING.original_consumers(str(history.root), installed, row)


@pytest.mark.parametrize("identity", ["status", "task_spec", "lease", "completion"])
def test_new_baseline_consumers_require_unstarted_identity(history, identity):
    installed = install_serial_baseline(history)
    before = copy.deepcopy(history.plan)
    row = before["planningBaselines"][0]
    proposed = copy.deepcopy(before)
    task = copy.deepcopy(next(t for t in proposed["tasks"] if t["taskId"] == "GZ-007"))
    task["taskId"] = "GZ-998"
    proposed["tasks"].append(task)
    if identity == "status":
        task["status"] = "in_progress"
    elif identity == "task_spec":
        history.write("specs/tasks/alternate-new-consumer.md", "---\nid: GZ-998\n---\n")
    elif identity == "lease":
        history.active["tasks"].append(dict(history.entry, taskId="GZ-998"))
        history.dump(PLANNING.ACTIVE, history.active)
    else:
        ledger = history.read(PLANNING.LEDGER)
        ledger["records"].append({"taskId": "GZ-998"})
        history.dump(PLANNING.LEDGER, ledger)
    history.dump(PLANNING.PLAN, proposed)
    head = history.commit("New consumer identity predicate fixture")
    # A predicate test supplies no authority for a planning transaction.
    with pytest.raises(PLANNING.PlanningError, match="GZ-998"):
        PLANNING.validate_new_consumers(str(history.root), installed, head, before, proposed, {row["id"]: row})


def test_unstarted_new_consumer_predicate_accepts_without_planning_permission(history):
    installed = install_serial_baseline(history)
    before = copy.deepcopy(history.plan)
    row = before["planningBaselines"][0]
    task = copy.deepcopy(next(t for t in history.plan["tasks"] if t["taskId"] == "GZ-007"))
    task["taskId"] = "GZ-998"
    history.plan["tasks"].append(task)
    history.dump(PLANNING.PLAN, history.plan)
    head = history.commit("Unstarted superset predicate fixture")
    PLANNING.validate_new_consumers(str(history.root), installed, head, before, history.plan, {row["id"]: row})


def test_existing_consumer_identity_transition_is_not_new_enrollment(history):
    installed = install_serial_baseline(history)
    before = copy.deepcopy(history.plan)
    row = before["planningBaselines"][0]
    next(t for t in history.plan["tasks"] if t["taskId"] == "GZ-007")["status"] = "in_progress"
    history.write("specs/tasks/consumer.md", "---\nid: GZ-007\n---\n")
    history.dump(PLANNING.PLAN, history.plan)
    head = history.commit("Existing consumer identity delta predicate fixture")
    # This delta check does not waive normal producer-completion admission.
    PLANNING.validate_new_consumers(str(history.root), installed, head, before, history.plan, {row["id"]: row})


@pytest.mark.parametrize("claim", ["backend/guize-platform-api/**", "backend/guize-platform-api/Main.java", "docs/**", "specs/requirements/v1/*.yaml", "scripts/program-planning-revision.py"])
def test_ordinary_planner_rejects_runtime_or_glob_claims(tmp_path, claim):
    history = History(tmp_path, ordinary=True)
    entry = copy.deepcopy(history.entry)
    entry["exclusivePaths"].append(claim)
    with pytest.raises(PLANNING.PlanningError, match="Ordinary planner"):
        PLANNING.ownership(str(history.root), history.registration, entry)


def test_ordinary_planner_keeps_exact_business_validators_and_schemas(tmp_path):
    history = History(tmp_path, ordinary=True)
    entry = copy.deepcopy(history.entry)
    original = history.manifest["targets"][0]["after"]
    entry["moduleIds"] = original["moduleIds"]
    entry["exclusivePaths"] = original["outputPaths"]
    PLANNING.ownership(str(history.root), history.registration, entry)


@pytest.mark.parametrize("wave", ["W10", "UNKNOWN"])
def test_baseline_semantic_edges_enforce_wave_order(history, wave):
    install_serial_baseline(history)
    next(t for t in history.plan["tasks"] if t["taskId"] == "GZ-021")["wave"] = wave
    with pytest.raises(PLANNING.PlanningError, match="wave"):
        PLANNING.validate_baselines(history.plan)


@pytest.mark.parametrize("script", ["check-program-plan-transitions.py", "check-program-lifecycle-guards.py", "check-program-plan-history.py"])
def test_manifest_mutation_restoration_cannot_disappear(history, script):
    installed = install_serial_baseline(history)
    path = f"evidence/{history.owner}/planning-revision.json"
    original = PLANNING.blob(str(history.root), installed, path).decode("utf-8")
    changed = copy.deepcopy(history.manifest)
    changed["targets"][0]["after"]["title"] += " tampered"
    history.dump(path, changed)
    altered = history.commit("Intermediate manifest mutation")
    history.write(path, original)
    restored = history.commit("Restore manifest before review")
    for base, head in [(installed, altered), (altered, restored)]:
        errors = []
        result = PLANNING.classifier(str(history.root), base, head, history.plan, history.plan, errors, admitted_base_ref=history.registration)
        assert result is None and any("manifest changed in history" in e for e in errors)
    result = readiness(history)
    assert result.returncode != 0 and "intermediate history" in result.stdout
    result = history.gate(script, task=False)
    if script == "check-program-plan-history.py":
        assert result.returncode != 0 and "manifest changed in history" in result.stdout
    else:
        # Endpoint-only transition/lifecycle checks may see restored bytes;
        # the mandatory history and Readiness checks enforce intervening nodes.
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("alias", ["main", "origin/main"])
def test_new_reservation_manifest_base_alias_matches_immutable_sha(tmp_path, alias):
    proposal = History(tmp_path, ordinary=True, merge_registration=False)
    proposal.git("update-ref", "refs/remotes/origin/main", proposal.base)
    assert proposal.git("rev-parse", alias) == proposal.base
    for base in (alias, proposal.base):
        PLANNING.audit_changed_manifests(str(proposal.root), base, proposal.registration)
        errors = []
        decision = PLANNING.classifier(
            str(proposal.root), base, proposal.registration,
            PLANNING.document(str(proposal.root), base, PLANNING.PLAN),
            PLANNING.document(str(proposal.root), proposal.registration, PLANNING.PLAN),
            errors,
        )
        assert decision is None and not errors  # Valid metadata supplies no planning permission.


@pytest.mark.parametrize("authority", ["missing", "sibling", "unmerged_head"])
def test_manifest_base_alias_rejects_invalid_or_noncanonical_authority(tmp_path, authority):
    proposal = History(tmp_path, ordinary=True, merge_registration=False)
    proposal.git("update-ref", "refs/remotes/origin/main", proposal.base)
    if authority == "missing":
        selected = "refs/heads/missing-admission-base"
    elif authority == "sibling":
        selected = proposal.git("commit-tree", proposal.git("rev-parse", proposal.base + "^{tree}"), "-p", PREDECESSOR, "-m", "Noncanonical sibling")
    else:
        selected = proposal.registration
    with pytest.raises(PLANNING.PlanningError):
        PLANNING.audit_changed_manifests(
            str(proposal.root), proposal.base, proposal.registration,
            admitted_base_ref=selected,
        )


def test_manifest_base_alias_is_resolved_fresh_after_ref_moves(tmp_path):
    proposal = History(tmp_path, ordinary=True, merge_registration=False)
    proposal.git("update-ref", "refs/remotes/origin/main", proposal.base)
    selected = "refs/heads/selected-admission-base"
    proposal.git("update-ref", selected, proposal.base)
    PLANNING.audit_changed_manifests(str(proposal.root), proposal.base, proposal.registration, admitted_base_ref=selected)
    sibling = proposal.git("commit-tree", proposal.git("rev-parse", proposal.base + "^{tree}"), "-p", PREDECESSOR, "-m", "Moved alias to noncanonical sibling")
    proposal.git("update-ref", selected, sibling)
    with pytest.raises(PLANNING.PlanningError, match="admitted canonical base"):
        PLANNING.audit_changed_manifests(str(proposal.root), proposal.base, proposal.registration, admitted_base_ref=selected)


def test_manifest_base_alias_still_rejects_registered_manifest_rewrite(tmp_path):
    registered = History(tmp_path)
    changed = copy.deepcopy(registered.manifest)
    changed["targets"][0]["after"]["title"] += " unauthorized rewrite"
    registered.dump(f"evidence/{registered.owner}/planning-revision.json", changed)
    head = registered.commit("Mutate original registered manifest")
    with pytest.raises(PLANNING.PlanningError, match="Original registered planning manifest changed in history"):
        PLANNING.audit_changed_manifests(str(registered.root), registered.registration, head, admitted_base_ref="main")


def edge_planning_plan():
    """Apply the real reserved intent to its accepted, unmodified baseline."""
    plan = PLANNING.document(str(ROOT), EDGE_ADMISSION, PLANNING.PLAN)
    manifest = json.loads(PLANNING.blob(str(ROOT), EDGE_ADMISSION, EDGE_FIRST_USE))
    for target in manifest["targets"]:
        if target["kind"] == "add-fixed-scope-boundary":
            plan["scopeBoundary"] = copy.deepcopy(target["after"])
        elif target["kind"] == "add-planned-task":
            plan["tasks"].append(copy.deepcopy(target["after"]))
        else:
            plan.setdefault("planningBaselines", []).append(copy.deepcopy(target["after"]))
    return plan


class FirstUseHistory(History):
    """Reuse the real canonical reservation and its accepted scope amendment.

    Current code is introduced only in the subsequent implementation commit.
    The original reservation, historical lease and declaration stay untouched.
    """
    def __init__(self, root):
        self.root = root / "repo"
        subprocess.run(["git", "clone", "--shared", "--no-checkout", "--quiet", str(ROOT), str(self.root)], check=True, capture_output=True)
        for key, value in (("user.name", "First use fixture"), ("user.email", "fixture@example.com"), ("core.autocrlf", "false"), ("core.longpaths", "true")):
            self.git("config", key, value)
        self.git("checkout", "-B", "main", EDGE_ADMISSION)
        self.owner = "OPS-011"
        self.branch = "chore/OPS-011-agent-edge-104-scope"
        self.base = self.registration = EDGE_ADMISSION
        self.plan = self.read(PLANNING.PLAN)
        self.active = self.read(PLANNING.ACTIVE)
        self.entry = next(row for row in self.active["tasks"] if row["taskId"] == self.owner)
        self.task_path = "specs/tasks/OPS-011.md"
        raw_task = (self.root / self.task_path).read_text(encoding="utf-8").split("---", 2)
        self.front, self.body = yaml.safe_load(raw_task[1]), raw_task[2]
        raw = PLANNING.blob(str(self.root), EDGE_ADMISSION, EDGE_FIRST_USE)
        assert hashlib.sha256(raw).hexdigest() == EDGE_FIRST_USE_SHA256
        self.manifest = json.loads(raw)
        self.git("checkout", "-B", self.branch, self.registration)
        for path in (PLANNING.PROGRAM_SCHEMA, PLANNING.MANIFEST_SCHEMA, "scripts/program-planning-revision.py"):
            self.write(path, (ROOT / path).read_text(encoding="utf-8"))

    def apply(self):
        self.plan = edge_planning_plan()
        next(row for row in self.plan["foundationTasks"] if row["taskId"] == self.owner)["status"] = "in_progress"
        now = datetime.now(timezone.utc)
        self.entry.update(status="in_progress", agentRole="implementer", baseSha=self.registration)
        self.entry["lease"] = {"acquiredAt": (now-timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ"), "expiresAt": (now+timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        self.front.update(status="in_progress", agentRole="implementer", baseSha=self.registration, leaseExpiresAt=self.entry["lease"]["expiresAt"])


def test_fixed_first_use_authenticates_real_canonical_reservation(tmp_path):
    history = FirstUseHistory(tmp_path)
    before = copy.deepcopy(history.plan)
    history.apply()
    history.finish()
    result, errors = history.decision()
    assert not errors and result is not None
    assert result["owner"] == "OPS-011"
    assert result["registration"] == "1d2cb080d56176e26375a7b373a3cf3ef548b3dd"
    expected_projection = copy.deepcopy(before)
    next(row for row in expected_projection["foundationTasks"] if row["taskId"] == "OPS-011")["status"] = "in_progress"
    assert result["projectedPlan"] == expected_projection
    assert history.plan["scopeBoundary"]["v1TaskIds"] == history.manifest["originalV1TaskIds"]
    assert history.plan["pocs"] == before["pocs"] and len(before["pocs"]) == 10
    assert history.plan["releasePolicy"] == before["releasePolicy"]
    baseline = next(row for row in history.plan["planningBaselines"] if row["id"] == "BASELINE-GZ-022")
    assert baseline["requiredBy"] == ["POC-003", "POC-005"]
    assert PLANNING.frontier(history.plan, baseline["requiredBy"]) == {"POC-003", "POC-005", "GZ-011", "GZ-013", "GZ-015", "GZ-016", "GZ-017", "GZ-018", "GZ-019", "GZ-020"}


@pytest.mark.parametrize("case", ["rewritten_original", "absent_original", "late_definition", "extra_program_edit"])
def test_fixed_first_use_cannot_borrow_or_rewrite_authority(tmp_path, case):
    history = FirstUseHistory(tmp_path)
    history.apply()
    if case == "rewritten_original":
        changed = copy.deepcopy(history.manifest)
        changed["targets"][1]["after"]["title"] += " rewritten"
        history.dump(EDGE_FIRST_USE, changed)
    elif case == "absent_original":
        (history.root / EDGE_FIRST_USE).unlink()
    elif case == "late_definition":
        # A newly written GZ022 v2 document cannot enlarge OPS011's original
        # three-target transaction or stand in for GZ022's own reservation.
        scope = history.plan["scopeBoundary"]["agentEdge104"]
        before_scope = copy.deepcopy(scope)
        scope.update(state="defined", taskIds=["GZ-022", "GZ-023"], requiredFinalTask="GZ-023")
        final = copy.deepcopy(next(row for row in history.plan["tasks"] if row["taskId"] == "GZ-022"))
        final.update(taskId="GZ-023", kind="release", riskLevel="critical", wave="W3", dependsOn=["GZ-022"], requirementIds=["REQ-EDGE-104-0001"], acceptanceIds=["AC-EDGE-104-0001"])
        history.plan["tasks"].append(final)
        requirements = {
            "schemaVersion": 1, "scopeId": "AGENT-EDGE-104", "sourceIssue": 104,
            "requirements": [{"id": "REQ-EDGE-104-0001", "title": "One complete late delivery",
                              "requirementPath": "specs/requirements/agent-edge-104.md#req-edge-104-0001",
                              "moduleIds": ["MOD-WORKER"], "taskIds": ["GZ-023"], "acceptanceIds": ["AC-EDGE-104-0001"]}],
        }
        acceptances = {
            "schemaVersion": 1, "scopeId": "AGENT-EDGE-104", "sourceIssue": 104,
            "acceptances": [{"id": "AC-EDGE-104-0001", "title": "One complete late acceptance",
                             "requirementIds": ["REQ-EDGE-104-0001"], "taskIds": ["GZ-023"],
                             "verification": "Run the declared acceptance.", "evidencePath": "evidence/GZ-023/acceptance.json"}],
        }
        declaration = {
            "schemaVersion": 2, "kind": "agent-edge-104-definition", "taskId": "GZ-022", "scopeId": "AGENT-EDGE-104",
            "issue": 222, "reservationParent": history.registration, "programPlan": PLANNING.PLAN,
            "requirementIndex": requirements, "acceptanceIndex": acceptances,
            "targets": [{"kind": "define-fixed-scope", "id": "AGENT-EDGE-104", "before": before_scope, "after": copy.deepcopy(scope)},
                        {"kind": "add-edge-planned-task", "id": "GZ-023", "before": None, "after": final}],
        }
        program_schema = history.read(PLANNING.PROGRAM_SCHEMA)
        manifest_schema = history.read(PLANNING.MANIFEST_SCHEMA)
        registry = Registry().with_resources([(program_schema["$id"], Resource.from_contents(program_schema)), (manifest_schema["$id"], Resource.from_contents(manifest_schema))])
        jsonschema.Draft202012Validator({"$ref": manifest_schema["$id"]+"#/$defs/agentEdge104Definition"}, registry=registry).validate(declaration)
        history.dump("evidence/GZ-022/agent-edge-104-definition.json", declaration)
        history.dump("specs/requirements/agent-edge-104.yaml", requirements)
        history.dump("specs/acceptance/agent-edge-104.yaml", acceptances)
        history.write("specs/requirements/agent-edge-104.md", "# Agent Edge\n\n## REQ-EDGE-104-0001\n\nOne complete delivery.\n")
    else:
        history.plan["tasks"][0]["title"] += " undeclared"
    history.finish()
    result, errors = history.decision()
    assert result is None and errors


def test_planning_scope_has_no_runtime_completion_or_index_permission(tmp_path):
    plan = edge_planning_plan()
    PLANNING.validate_scope_boundary(plan)
    assert {PLANNING.task_scope(plan, tid) for tid in plan["scopeBoundary"]["v1TaskIds"]} == {"V1"}
    assert PLANNING.task_scope(plan, "GZ-022") == "AGENT-EDGE-104"
    assert PLANNING.task_scope(plan, "OPS-011") == "FOUNDATION"
    assert PLANNING.validate_edge_indexes(tmp_path, plan) == {"requirements": {}, "acceptances": {}}
    with pytest.raises(PLANNING.PlanningError):
        PLANNING.task_scope(plan, "GZ-999")
    next(row for row in plan["tasks"] if row["taskId"] == "GZ-022")["status"] = "completed"
    with pytest.raises(PLANNING.PlanningError):
        PLANNING.validate_scope_boundary(plan)


@pytest.mark.parametrize("case", ["v1_member_escape", "planning_final", "defined_empty_final", "program_completed"])
def test_fixed_scope_membership_and_completion_are_not_state_flags(case):
    plan = edge_planning_plan()
    scope = plan["scopeBoundary"]["agentEdge104"]
    if case == "v1_member_escape":
        plan["scopeBoundary"]["v1TaskIds"].remove("GZ-004")
        scope["taskIds"].append("GZ-004")
    elif case == "planning_final":
        scope["requiredFinalTask"] = "GZ-022"
    elif case == "defined_empty_final":
        scope["state"] = "defined"
    else:
        plan["status"] = "completed"
    with pytest.raises(PLANNING.PlanningError):
        PLANNING.validate_scope_boundary(plan)


def test_legacy_manifest_refs_keep_legacy_requirement_and_target_permissions():
    program_schema = yaml.safe_load((ROOT / PLANNING.PROGRAM_SCHEMA).read_text(encoding="utf-8"))
    schema = yaml.safe_load((ROOT / PLANNING.MANIFEST_SCHEMA).read_text(encoding="utf-8"))
    registry = Registry().with_resource(program_schema["$id"], Resource.from_contents(program_schema))
    validator = jsonschema.Draft202012Validator(schema, registry=registry)
    manifest = json.loads((ROOT / "evidence/OPS-009/planning-revision.json").read_text(encoding="utf-8"))
    validator.validate(manifest)
    changed = copy.deepcopy(manifest)
    changed["targets"][0]["after"]["requirementIds"] = ["REQ-EDGE-104-0001"]
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(changed)
    typed_first_use = json.loads(PLANNING.blob(str(ROOT), EDGE_ADMISSION, EDGE_FIRST_USE))
    with pytest.raises(jsonschema.ValidationError):
        validator.validate(typed_first_use)


@pytest.mark.parametrize("case", ["orphan_business_member", "planner_only_completed"])
def test_defined_scope_requires_its_complete_nonempty_release_closure(case):
    plan = edge_planning_plan()
    planner = next(row for row in plan["tasks"] if row["taskId"] == "GZ-022")
    worker = copy.deepcopy(planner)
    worker.update(taskId="GZ-023", kind="scaffold", riskLevel="medium", wave="W3", dependsOn=["GZ-022"], requirementIds=["REQ-EDGE-104-0001"])
    final = copy.deepcopy(worker)
    final.update(taskId="GZ-024", kind="release", riskLevel="critical", wave="W4", dependsOn=["GZ-023"])
    plan["tasks"].extend([worker, final])
    plan["scopeBoundary"]["agentEdge104"].update(state="defined", taskIds=["GZ-022", "GZ-023", "GZ-024"], requiredFinalTask="GZ-024")
    PLANNING.validate_scope_boundary(plan)
    if case == "orphan_business_member":
        final["dependsOn"] = ["GZ-022"]
    else:
        for task in plan["tasks"]:
            if task["taskId"] in plan["scopeBoundary"]["v1TaskIds"] or task["taskId"] == "GZ-022":
                task["status"] = "completed"
        plan["status"] = "completed"
    with pytest.raises(PLANNING.PlanningError):
        PLANNING.validate_scope_boundary(plan)


@pytest.mark.parametrize("risks", [["low"]*4, ["high", "high"], ["critical", "low"]])
def test_fixed_scopes_keep_one_global_capacity_pool(risks):
    plan = edge_planning_plan()
    registry = {"policy": {"maxActiveTasks": 3, "maxHighRiskTasks": 1}, "tasks": [{"taskId": tid, "riskLevel": risk} for tid, risk in zip(["GZ-006", "GZ-022", "GZ-007", "POC-003"], risks)]}
    with pytest.raises(PLANNING.PlanningError):
        PLANNING.capacity(registry, plan)


def edge_index_documents():
    """Index inputs for a plain temporary directory, without admission authority."""
    plan = edge_planning_plan()
    planner = next(row for row in plan["tasks"] if row["taskId"] == "GZ-022")
    requirement_ids = ["REQ-EDGE-104-0001", "REQ-EDGE-104-0002"]
    acceptance_ids = ["AC-EDGE-104-0001", "AC-EDGE-104-0002"]
    worker = copy.deepcopy(planner)
    worker.update(taskId="GZ-023", kind="scaffold", riskLevel="medium", wave="W3", dependsOn=["GZ-022"],
                  requirementIds=requirement_ids[:], acceptanceIds=acceptance_ids[:], moduleIds=["MOD-WORKER", "MOD-AI"])
    final = copy.deepcopy(worker)
    final.update(taskId="GZ-024", kind="release", riskLevel="critical", wave="W4", dependsOn=["GZ-023"], moduleIds=["MOD-WORKER"])
    plan["tasks"].extend([worker, final])
    plan["scopeBoundary"]["agentEdge104"].update(state="defined", taskIds=["GZ-022", "GZ-023", "GZ-024"], requiredFinalTask="GZ-024")
    requirements = {
        "schemaVersion": 1, "scopeId": "AGENT-EDGE-104", "sourceIssue": 104,
        "requirements": [{"id": rid, "title": f"Requirement {index+1}",
                          "requirementPath": "specs/requirements/agent-edge-104.md#"+rid.lower(),
                          "moduleIds": ["MOD-WORKER"] if index == 0 else ["MOD-WORKER", "MOD-AI"],
                          "taskIds": ["GZ-023", "GZ-024"], "acceptanceIds": [acceptance_ids[index]]}
                         for index, rid in enumerate(requirement_ids)],
    }
    acceptances = {
        "schemaVersion": 1, "scopeId": "AGENT-EDGE-104", "sourceIssue": 104,
        "acceptances": [{"id": aid, "title": f"Acceptance {index+1}", "requirementIds": [requirement_ids[index]],
                         "taskIds": ["GZ-023", "GZ-024"], "verification": "Run the fixed delivery acceptance.",
                         "evidencePath": f"evidence/GZ-023/acceptance-{index+1}.json"}
                        for index, aid in enumerate(acceptance_ids)],
    }
    return plan, requirements, acceptances


def write_edge_index_documents(root, requirements, acceptances, *, active=None):
    documents = {
        "specs/requirements/agent-edge-104.yaml": requirements,
        "specs/acceptance/agent-edge-104.yaml": acceptances,
        PLANNING.ACTIVE: active if active is not None else {"tasks": []},
        "specs/designs/module-ownership.yaml": {"modules": [
            {"id": "MOD-WORKER", "ownedPaths": ["services/guize-worker-agent/**"]},
            {"id": "MOD-AI", "ownedPaths": ["services/guize-ai-agent-service/**"]},
        ]},
    }
    for relative, document in documents.items():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    (root / "specs/requirements/agent-edge-104.md").write_text("# Agent Edge\n\n## REQ-EDGE-104-0001\n\nWorker delivery.\n\n## REQ-EDGE-104-0002\n\nAI delivery.\n", encoding="utf-8")


def test_defined_scope_reads_independent_indexes_and_exact_delivery_joins(tmp_path):
    plan, requirements, acceptances = edge_index_documents()
    write_edge_index_documents(tmp_path, requirements, acceptances)
    result = PLANNING.validate_edge_indexes(tmp_path, plan)
    assert set(result["requirements"]) == {"REQ-EDGE-104-0001", "REQ-EDGE-104-0002"}
    assert set(result["acceptances"]) == {"AC-EDGE-104-0001", "AC-EDGE-104-0002"}
    # The final acceptance orchestrates both deliveries. Actual module coverage
    # is supplied by their union; the final task need not own every AI module.
    assert next(row for row in plan["tasks"] if row["taskId"] == "GZ-024")["moduleIds"] == ["MOD-WORKER"]


def test_defined_indexes_bind_all_reads_to_the_selected_git_snapshot(tmp_path):
    # These are data snapshots on an unrelated local branch. They provide no
    # canonical reservation, declaration authority or Completion evidence.
    plan, requirements, acceptances = edge_index_documents()
    write_edge_index_documents(tmp_path, requirements, acceptances)
    (tmp_path / PLANNING.PLAN).write_text(yaml.safe_dump(plan, sort_keys=False), encoding="utf-8")
    def git(*args):
        return subprocess.check_output(["git", "-C", str(tmp_path), *args], stderr=subprocess.PIPE, encoding="utf-8").strip()
    git("init", "-b", "index-snapshots")
    git("config", "user.name", "Index snapshot fixture")
    git("config", "user.email", "fixture@example.com")
    git("config", "core.autocrlf", "false")
    git("add", ".")
    git("commit", "-m", "Valid index data snapshot")
    valid = git("rev-parse", "HEAD")
    requirements["requirements"][1]["moduleIds"].append("MOD-UNKNOWN")
    write_edge_index_documents(tmp_path, requirements, acceptances)
    git("add", ".")
    git("commit", "-m", "Invalid module index data snapshot")
    invalid = git("rev-parse", "HEAD")
    (tmp_path / "specs/requirements/agent-edge-104.md").write_text("# Missing requirement anchors\n", encoding="utf-8")
    (tmp_path / PLANNING.ACTIVE).write_text(yaml.safe_dump({"tasks": [{"taskId": "GZ-004", "requirementIds": ["REQ-EDGE-104-0001"]}]}), encoding="utf-8")
    (tmp_path / "specs/designs/module-ownership.yaml").write_text("modules: []\n", encoding="utf-8")
    snapshot_plan = PLANNING.document(str(tmp_path), valid, PLANNING.PLAN)
    result = PLANNING.validate_edge_indexes(str(tmp_path), snapshot_plan, ref=valid)
    assert set(result["requirements"]) == {"REQ-EDGE-104-0001", "REQ-EDGE-104-0002"}
    with pytest.raises(PLANNING.PlanningError, match="Unknown EDGE requirement binding"):
        PLANNING.validate_edge_indexes(str(tmp_path), snapshot_plan, ref=invalid)
    with pytest.raises(PLANNING.PlanningError, match="Non-EDGE registry task"):
        PLANNING.validate_edge_indexes(str(tmp_path), snapshot_plan)


@pytest.mark.parametrize("case,message", [
    ("asymmetric_join", "join differs"),
    ("unknown_module", "Unknown EDGE requirement binding"),
    ("v1_registry_edge", "Non-EDGE registry task cannot consume EDGE requirements"),
    ("final_missing_coverage", "final task must directly cover"),
])
def test_defined_scope_rejects_unbound_indexes_and_incomplete_final(tmp_path, case, message):
    plan, requirements, acceptances = edge_index_documents()
    active = {"tasks": []}
    if case == "asymmetric_join":
        acceptances["acceptances"][1]["requirementIds"] = ["REQ-EDGE-104-0001"]
    elif case == "unknown_module":
        requirements["requirements"][1]["moduleIds"].append("MOD-UNKNOWN")
    elif case == "v1_registry_edge":
        active["tasks"].append({"taskId": "GZ-004", "requirementIds": ["REQ-EDGE-104-0001"]})
    else:
        # Keep every bidirectional per-task join valid, while leaving the
        # second delivery outside the final task's direct acceptance coverage.
        requirements["requirements"][1]["taskIds"] = ["GZ-023"]
        acceptances["acceptances"][1]["taskIds"] = ["GZ-023"]
        final = next(row for row in plan["tasks"] if row["taskId"] == "GZ-024")
        final["requirementIds"] = ["REQ-EDGE-104-0001"]
        final["acceptanceIds"] = ["AC-EDGE-104-0001"]
    write_edge_index_documents(tmp_path, requirements, acceptances, active=active)
    with pytest.raises(PLANNING.PlanningError, match=message):
        PLANNING.validate_edge_indexes(tmp_path, plan)


@pytest.mark.parametrize("task_id,field,message", [
    ("GZ-006", "title", None),
    ("GZ-009", "title", "only its eight registered V1 tasks"),
    ("GZ-006", "requirementIds", "rewrote existing V1 obligations"),
])
def test_edge_definition_v1_edits_require_registered_touchpoint_and_obligations(task_id, field, message):
    plan = PLANNING.document(str(ROOT), EDGE_ADMISSION, PLANNING.PLAN)
    before = copy.deepcopy(next(row for row in plan["tasks"] if row["taskId"] == task_id))
    assert before["status"] == "planned" and before["issue"] is None
    after = copy.deepcopy(before)
    if field == "title":
        after["title"] += " with explicit follow-up handoff"
    else:
        assert "REQ-V1-9999" not in before["requirementIds"]
        after["requirementIds"].append("REQ-V1-9999")
    target = {
        "kind": "edit-planned-task", "id": task_id,
        "originalDefinitionSha256": hashlib.sha256(json.dumps(before, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest(),
        "allowedFields": [field], "before": before, "after": after,
    }
    program_schema = yaml.safe_load((ROOT / PLANNING.PROGRAM_SCHEMA).read_text(encoding="utf-8"))
    manifest_schema = yaml.safe_load((ROOT / PLANNING.MANIFEST_SCHEMA).read_text(encoding="utf-8"))
    registry = Registry().with_resources([(program_schema["$id"], Resource.from_contents(program_schema)), (manifest_schema["$id"], Resource.from_contents(manifest_schema))])
    # All three edits satisfy the same closed legacy edit fragment. Permission
    # to amend a task still comes from the bounded follow-up semantic guard.
    jsonschema.Draft202012Validator({"$ref": manifest_schema["$id"]+"#/$defs/editTask"}, registry=registry).validate(target)
    if message is None:
        PLANNING.validate_edge_v1_edit(target)
    else:
        with pytest.raises(PLANNING.PlanningError, match=message):
            PLANNING.validate_edge_v1_edit(target)


class SimulatedCatalogHistory(FirstUseHistory):
    """Private protocol simulation: real Git, no external registration or CI.

    Local Issue/PR identities below are fixture values. Role transitions model
    the normal protocol; this does not execute or claim full Completion gates.
    """
    def __init__(self, root):
        seed = root / "accepted-seed"
        subprocess.run(["git", "clone", "--shared", "--no-checkout", "--quiet", str(ROOT), str(seed)], check=True, capture_output=True)
        for key, value in (("core.autocrlf", "false"), ("core.longpaths", "true")):
            subprocess.run(["git", "-C", str(seed), "config", key, value], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(seed), "checkout", "-B", "main", EDGE_ADMISSION], check=True, capture_output=True)
        self.root = root / "repo"
        subprocess.run(["git", "clone", "--shared", "--no-checkout", "--quiet", str(seed), str(self.root)], check=True, capture_output=True)
        for key, value in (("user.name", "Private protocol simulation"), ("user.email", "simulation@example.com"), ("core.autocrlf", "false"), ("core.longpaths", "true")):
            self.git("config", key, value)
        self.git("checkout", "-B", "main", EDGE_ADMISSION)
        assert Path(self.git("remote", "get-url", "origin")).resolve() == seed.resolve()
        assert self.git("rev-parse", "origin/main") == EDGE_ADMISSION
        self.owner, self.branch = "OPS-011", "chore/OPS-011-agent-edge-104-scope"
        self.base = self.registration = EDGE_ADMISSION
        self.plan, self.active = self.read(PLANNING.PLAN), self.read(PLANNING.ACTIVE)
        inherited_ledger = PLANNING.blob(str(self.root), EDGE_ADMISSION, PLANNING.LEDGER)
        self.entry = next(row for row in self.active["tasks"] if row["taskId"] == self.owner)
        self.task_path = "specs/tasks/OPS-011.md"
        raw_task = (self.root/self.task_path).read_text(encoding="utf-8").split("---", 2)
        self.front, self.body = yaml.safe_load(raw_task[1]), raw_task[2]
        raw = PLANNING.blob(str(self.root), EDGE_ADMISSION, EDGE_FIRST_USE)
        assert hashlib.sha256(raw).hexdigest() == EDGE_FIRST_USE_SHA256
        self.manifest = json.loads(raw)
        self.git("checkout", "-B", self.branch, EDGE_ADMISSION)
        for path in (PLANNING.PROGRAM_SCHEMA, PLANNING.MANIFEST_SCHEMA, "scripts/program-planning-revision.py"):
            self.write(path, (ROOT/path).read_text(encoding="utf-8"))
        FirstUseHistory.apply(self)
        self.save()
        self.commit("SIMULATION OPS-011 exact first-use implementation")
        foundation_code = self.merge_current("SIMULATION OPS-011 implementation (#900011)")
        self.phase("review", "reviewer", "chore/OPS-011-simulated-review")
        self.git("checkout", "-b", "chore/OPS-011-simulated-completion", "main")
        row = next(row for row in self.plan["foundationTasks"] if row["taskId"] == self.owner)
        row.update(status="completed", completionRef="PR-900011", mergeCommit=foundation_code)
        self.active["tasks"] = [row for row in self.active["tasks"] if row["taskId"] != self.owner]
        self.front.update(status="completed", agentRole="integrator", baseSha=self.git("rev-parse", "main"))
        self.save()
        self.commit("SIMULATION OPS-011 completion metadata")
        foundation_completed = self.merge_current("SIMULATION OPS-011 completion phase")
        # Foundation completion remains in foundationTasks, never the ordinary
        # Completion Ledger. These are private simulated Git identities only.
        assert PLANNING.blob(str(self.root), foundation_completed, PLANNING.LEDGER) == inherited_ledger
        foundation = PLANNING.records(PLANNING.document(str(self.root), foundation_completed, PLANNING.PLAN)["foundationTasks"])["OPS-011"]
        assert foundation["status"] == "completed" and foundation["completionRef"] == "PR-900011"
        assert foundation["mergeCommit"] == foundation_code
        assert foundation_code in self.git("rev-list", "--first-parent", "main").splitlines()
        assert "OPS-011" in self.git("show", "-s", "--format=%B", foundation_code)
        assert "#900011" in self.git("show", "-s", "--format=%B", foundation_code)
        assert "OPS-011" not in PLANNING.records(PLANNING.document(str(self.root), foundation_completed, PLANNING.ACTIVE)["tasks"])
        completed_spec = PLANNING.spec(str(self.root), foundation_completed, "OPS-011")
        assert completed_spec is not None and completed_spec[1]["status"] == "completed"
        self.reserve_definition()

    def merge_current(self, message):
        branch = self.git("branch", "--show-current")
        self.git("checkout", "main")
        self.git("merge", "--no-ff", "-m", message, branch)
        return self.git("rev-parse", "HEAD")

    def phase(self, status, role, branch):
        self.git("checkout", "-b", branch, "main")
        base = self.git("rev-parse", "main")
        section = "foundationTasks" if self.owner == "OPS-011" else "tasks"
        next(row for row in self.plan[section] if row["taskId"] == self.owner)["status"] = status
        self.entry.update(status=status, agentRole=role, baseSha=base)
        self.front.update(status=status, agentRole=role, baseSha=base)
        self.save()
        self.commit(f"SIMULATION {self.owner} {status} metadata")
        return self.merge_current(f"SIMULATION {self.owner} {status} phase")

    def reserve_definition(self):
        parent = self.git("rev-parse", "main")
        planner = next(row for row in self.plan["tasks"] if row["taskId"] == "GZ-022")
        self.owner, self.branch = "GZ-022", "chore/GZ-022-simulated-definition"
        self.task_path = "specs/tasks/GZ-022.md"
        self.entry = copy.deepcopy(self.entry)
        self.entry.update(taskId=self.owner, programTaskId=self.owner, issue=900022, title=planner["title"],
                          status="reserved", agentRole="coordinator", branch=self.branch, baseSha=parent,
                          owner="private-protocol-simulation", coordinator="simulated-coordinator",
                          implementer=planner["ownerRole"], reviewer=planner["reviewerRole"], integrator="simulated-integrator",
                          programWave=planner["wave"], exclusivePaths=copy.deepcopy(planner["outputPaths"]),
                          handoffPath="evidence/GZ-022/handoff.md")
        for key in ("workPackage", "riskLevel", "requirementIds", "moduleIds", "producesContracts", "consumesContracts", "coordinationGroup", "dependsOn", "sharedPaths", "integrationOrder"):
            self.entry[key] = copy.deepcopy(planner[key])
        now = datetime.now(timezone.utc)
        self.entry["lease"] = {"acquiredAt": (now-timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ"), "expiresAt": (now+timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        self.front = copy.deepcopy(self.front)
        self.front.update(id=self.owner, programTaskId=self.owner, issue=900022, title=planner["title"],
                          status="reserved", agentRole="coordinator", workBranch=self.branch, baseSha=parent,
                          evidencePath="evidence/GZ-022", wave=planner["wave"], exitGate=planner["exitGate"],
                          taskOwner=self.entry["owner"], handoffPath=self.entry["handoffPath"], leaseExpiresAt=self.entry["lease"]["expiresAt"])
        for key in ("workPackage", "riskLevel", "coordinator", "implementer", "reviewer", "integrator", "coordinationGroup", "integrationOrder"):
            self.front[key] = self.entry[key]
        for key in ("requirementIds", "moduleIds", "producesContracts", "consumesContracts", "dependsOn"):
            self.front[key] = ", ".join(self.entry[key]) if self.entry[key] else []
        claims = "\n".join("- "+path for path in self.entry["exclusivePaths"])
        self.body = (
            "\n# Private GZ-022 protocol simulation\n\nNo external registration, CI or runtime acceptance.\n\n"
            "## Allowed scope\n\n"+claims+"\n- evidence/GZ-022/**\n\n"
            "## Forbidden scope\n\n- Runtime implementation and external publication.\n\n"
            "## Acceptance criteria\n\n- [ ] Exercise private protocol data without claiming external acceptance.\n\n"
            "## Validation commands\n\n- Python test target: `python -m pytest tests/governance/test_program_planning_revision.py`\n\n"
            "## Dependencies and integration order\n\n- GZ-021 and OPS-011 precede this simulated reservation.\n\n"
            "## Exclusive write scope\n\n"+claims+"\n\n"
            "## Shared modification scope\n\n- None.\n\n"
            "## Collaboration and handoff\n\n- Independent simulated implementer and reviewer; handoff is local fixture data.\n"
        )
        self.requirements = {"schemaVersion": 1, "scopeId": "AGENT-EDGE-104", "sourceIssue": 104, "requirements": [
            {"id": "REQ-EDGE-104-0001", "title": "Simulated worker delivery", "requirementPath": "specs/requirements/agent-edge-104.md#req-edge-104-0001",
             "moduleIds": ["MOD-WORKER"], "taskIds": ["GZ-023"], "acceptanceIds": ["AC-EDGE-104-0001"]}]}
        self.acceptances = {"schemaVersion": 1, "scopeId": "AGENT-EDGE-104", "sourceIssue": 104, "acceptances": [
            {"id": "AC-EDGE-104-0001", "title": "Simulated delivery acceptance", "requirementIds": ["REQ-EDGE-104-0001"], "taskIds": ["GZ-023"],
             "verification": "Protocol simulation data only; no runtime result.", "evidencePath": "evidence/GZ-023/simulated-acceptance.json"}]}
        final = copy.deepcopy(planner)
        final.update(taskId="GZ-023", title="Simulated final delivery", kind="release", riskLevel="critical", wave="W3", integrationOrder=1,
                     ownerRole="simulated-worker", reviewerRole="simulated-worker-reviewer", coordinationGroup="simulated-edge-release",
                     dependsOn=["GZ-022"], requirementIds=["REQ-EDGE-104-0001"], acceptanceIds=["AC-EDGE-104-0001"], moduleIds=["MOD-WORKER"],
                     outputPaths=["evidence/GZ-023/**"], sharedPaths=[], producesContracts=[], consumesContracts=[], pocIds=[], issue=None,
                     branchPattern="chore/GZ-023-*", exitGate="Private protocol simulation; no runtime acceptance.")
        before_scope = copy.deepcopy(self.plan["scopeBoundary"]["agentEdge104"])
        after_scope = copy.deepcopy(before_scope)
        after_scope.update(state="defined", taskIds=["GZ-022", "GZ-023"], requiredFinalTask="GZ-023")
        self.manifest = {"schemaVersion": 2, "kind": "agent-edge-104-definition", "taskId": self.owner, "scopeId": "AGENT-EDGE-104",
                         "issue": 900022, "reservationParent": parent, "programPlan": PLANNING.PLAN,
                         "requirementIndex": self.requirements, "acceptanceIndex": self.acceptances,
                         "targets": [{"kind": "define-fixed-scope", "id": "AGENT-EDGE-104", "before": before_scope, "after": after_scope},
                                     {"kind": "add-edge-planned-task", "id": "GZ-023", "before": None, "after": final}]}
        self.git("checkout", "-b", "chore/GZ-022-simulated-reservation", "main")
        planner.update(status="reserved", issue=900022)
        self.active["tasks"].append(self.entry)
        self.save()
        self.dump("evidence/GZ-022/agent-edge-104-definition.json", self.manifest)
        self.write("evidence/GZ-022/handoff.md", "# Private protocol simulation\n\nNo external reservation or CI acceptance.\n")
        self.commit("SIMULATION GZ-022 original metadata-only reservation")
        self.registration = self.merge_current("SIMULATION GZ-022 reservation (#900022)")
        self.git("checkout", "-b", self.branch, self.registration)

    def implement_definition(self):
        next(row for row in self.plan["tasks"] if row["taskId"] == self.owner)["status"] = "in_progress"
        self.entry.update(status="in_progress", agentRole="implementer", baseSha=self.registration)
        self.front.update(status="in_progress", agentRole="implementer", baseSha=self.registration)
        self.plan["scopeBoundary"]["agentEdge104"] = copy.deepcopy(self.manifest["targets"][0]["after"])
        self.plan["tasks"].append(copy.deepcopy(self.manifest["targets"][1]["after"]))
        self.dump("specs/requirements/agent-edge-104.yaml", self.requirements)
        self.dump("specs/acceptance/agent-edge-104.yaml", self.acceptances)
        self.write("specs/requirements/agent-edge-104.md", "# Private protocol simulation\n\n## REQ-EDGE-104-0001\n\nSimulated delivery only.\n")
        self.save()
        return self.commit("SIMULATION GZ-022 exact catalog definition")

    def complete_planner(self, code):
        self.phase("review", "reviewer", "chore/GZ-022-simulated-review")
        self.git("checkout", "-b", "chore/GZ-022-simulated-completion", "main")
        next(row for row in self.plan["tasks"] if row["taskId"] == self.owner)["status"] = "completed"
        self.active["tasks"] = [row for row in self.active["tasks"] if row["taskId"] != self.owner]
        self.front.update(status="completed", agentRole="integrator", baseSha=self.git("rev-parse", "main"))
        ledger = self.read(PLANNING.LEDGER)
        inherited = copy.deepcopy(ledger["records"])
        ledger["records"].append({"taskId": self.owner, "reservationRef": "PR-900022", "reservationCommit": self.registration,
                                  "completionRef": "PR-900023", "mergeCommit": code, "taskSpec": self.task_path,
                                  "evidencePath": "evidence/GZ-022", "handoffPath": "evidence/GZ-022/handoff.md"})
        assert ledger["records"][:-1] == inherited
        self.dump(PLANNING.LEDGER, ledger)
        self.save()
        self.commit("SIMULATION GZ-022 completion metadata")
        return self.merge_current("SIMULATION GZ-022 completion phase")


def test_simulated_original_catalog_admission_tampering_and_released_intro(tmp_path):
    history = SimulatedCatalogHistory(tmp_path)
    history.implement_definition()
    decision, errors = history.decision()
    assert not errors and decision is not None and decision["owner"] == "GZ-022"
    code = history.merge_current("SIMULATION GZ-022 implementation (#900023)")
    history.git("checkout", "-b", "chore/GZ-022-simulated-catalog-tamper", "main")
    changed = copy.deepcopy(history.requirements)
    changed["requirements"][0]["title"] += " undeclared"
    history.dump("specs/requirements/agent-edge-104.yaml", changed)
    tampered = history.commit("SIMULATION catalog-only drift attempt")
    assert PLANNING.changed_paths(str(history.root), code, tampered) == {"specs/requirements/agent-edge-104.yaml"}
    decision, errors = history.decision(base=code)
    assert decision is None and any("differs from complete original registered records" in error for error in errors)
    history.git("checkout", "main")
    completed = history.complete_planner(code)
    actual = PLANNING.document(str(history.root), completed, PLANNING.PLAN)
    assert "GZ-022" not in PLANNING.records(PLANNING.document(str(history.root), completed, PLANNING.ACTIVE)["tasks"])
    assert PLANNING.completed_producer(str(history.root), completed, "GZ-022")
    PLANNING.validate_frozen_edge_catalogs(str(history.root), completed, completed, actual)
    assert history.git("rev-parse", "origin/main") == EDGE_ADMISSION
