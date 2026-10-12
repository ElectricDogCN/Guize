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
import yaml

ROOT = Path(__file__).resolve().parents[2]
MODULE_SPEC = importlib.util.spec_from_file_location("planning_revision_tests", ROOT / "scripts/program-planning-revision.py")
PLANNING = importlib.util.module_from_spec(MODULE_SPEC)
MODULE_SPEC.loader.exec_module(PLANNING)
# This accepted predecessor has no OPS009 reservation. Its reachable completed
# task histories remain real, so the fixtures do not manufacture old PASS data.
PREDECESSOR = "bf0e5cbf51c1f8991986f503e22d1312ac9b5836"
ORIGINAL_RESERVATION = "82ceeaf0b6f6d31e7614de9dbdd89a5853d9386b"
OWNER = "OPS-777"


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
