import os
import pathlib
import importlib.util
import copy
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-program-plan-history.py")


class TestProgramPlanHistory(unittest.TestCase):
    def write_yaml(self, root, path, value):
        target = os.path.join(root, path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            yaml.safe_dump(value, handle, sort_keys=False, allow_unicode=True)

    def write_text(self, root, path, value):
        target = os.path.join(root, path)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(value)

    def init_git(self, root):
        subprocess.run(
            ["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=root,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=root, check=True
        )

    def commit(self, root, message, timestamp=None):
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", message],
            cwd=root,
            check=True,
            capture_output=True,
            env={**os.environ, "GIT_AUTHOR_DATE": timestamp, "GIT_COMMITTER_DATE": timestamp} if timestamp else None,
        )
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    def registry(self, tasks):
        return {
            "version": 1,
            "policy": {
                "maxActiveTasks": 3,
                "maxHighRiskTasks": 1,
                "leaseMaxHours": 168,
                "bootstrapTasks": ["GZ-003"],
            },
            "tasks": tasks,
        }

    def entry(self, task_id, base_sha, status, branch):
        return {
            "taskId": task_id,
            "issue": 30,
            "title": f"Task {task_id}",
            "status": status,
            "riskLevel": "high",
            "owner": "owner",
            "coordinator": "coordinator",
            "implementer": "implementer",
            "reviewer": "reviewer",
            "integrator": "integrator",
            "agentRole": "implementer",
            "branch": branch,
            "baseBranch": "main",
            "baseSha": base_sha,
            "workPackage": "WP-TEST",
            "programPlan": "specs/coordination/program-plan.yaml",
            "programTaskId": task_id,
            "programWave": "W1" if task_id != "GZ-014" else "FOUNDATION",
            "requirementIds": ["REQ-V1-0001"],
            "moduleIds": ["MOD-GOV"],
            "producesContracts": [],
            "consumesContracts": [],
            "coordinationGroup": "test",
            "dependsOn": [],
            "exclusivePaths": ["docs/test/**"],
            "sharedPaths": [],
            "handoffPath": f"evidence/{task_id}/handoff.md",
            "integrationStrategy": "merge",
            "integrationOrder": 1,
            "lease": {
                "acquiredAt": "2026-08-29T00:00:00Z",
                "expiresAt": "2026-09-02T00:00:00Z",
            },
        }

    def task_spec(self, item, status, branch, base_sha):
        front = {
            "schemaVersion": 2,
            "id": item["taskId"],
            "title": "Task",
            "titleZh": item["title"],
            "type": "chore",
            "status": status,
            "baseBranch": item["baseBranch"],
            "baseSha": base_sha,
            "workBranch": branch,
            "evidencePath": f"evidence/{item['taskId']}",
            "issue": item["issue"],
            "workPackage": item["workPackage"],
            "programPlan": item["programPlan"],
            "programTaskId": item["programTaskId"],
            "wave": item["programWave"],
            "requirementIds": item["requirementIds"],
            "moduleIds": item["moduleIds"],
            "producesContracts": item["producesContracts"],
            "consumesContracts": item["consumesContracts"],
            "taskOwner": item["owner"],
            "coordinator": item["coordinator"],
            "implementer": item["implementer"],
            "reviewer": item["reviewer"],
            "integrator": item["integrator"],
            "agentRole": item["agentRole"],
            "riskLevel": item["riskLevel"],
            "coordinationMode": "registry",
            "coordinationGroup": item["coordinationGroup"],
            "dependsOn": item["dependsOn"],
            "handoffPath": item["handoffPath"],
            "integrationStrategy": item["integrationStrategy"],
            "integrationOrder": item["integrationOrder"],
            "leaseExpiresAt": item.get("lease", {}).get("expiresAt", "MISSING"),
        }
        return (
            "---\n"
            + "\n".join(key+": "+((", ".join(str(part) for part in value) or "[]") if isinstance(value, list) else str(value)) for key, value in front.items()) + "\n"
            + "---\n\n## 依赖与集成顺序\n\n- 无。\n\n## 独占写范围\n\n"
            + "\n".join('- `'+path+'`' for path in item["exclusivePaths"]) + "\n\n"
            + "## 共享修改范围\n\n" + ("\n".join('- `'+path+'`' for path in item["sharedPaths"]) or '- 无。') + "\n\n"
            + "## 协作与交接\n\n- 独立 Reviewer 与 Implementer。\n"
            + "\n## 允许范围\n\n- 已登记路径与自身 canonical metadata。\n"
            + "\n## 禁止范围\n\n- backend/** 与其他任务。\n"
            + "\n## 验收标准\n\n- [ ] 验证真实来源与历史基线。\n"
            + "\n## 必须执行的测试\n\n```bash\npython scripts/check-task-file.py --task "+item["taskId"]+"\n```\n"
        )

    def _run_checker(self, root, task="", branch="", base_ref="main"):
        command = [
            sys.executable,
            SCRIPT,
            "--repo-root",
            root,
            "--base-ref",
            base_ref,
            "--head-ref",
            "HEAD",
        ]
        if task:
            command += ["--task", task, "--branch-name", branch]
        return subprocess.run(command, capture_output=True, text=True)

    def create_regular_completion(self, root, unrelated=False):
        self.init_git(root)
        self.write_text(root, "seed.txt", "seed\n")
        seed = self.commit(root, "seed")

        task_id = "GZ-004"
        reserved = self.entry(task_id, seed, "reserved", "chore/GZ-004-implementation")
        plan = {
            "foundationTasks": [],
            "tasks": [{"taskId": task_id, "status": "reserved", "exitGate": "verified"}],
        }
        self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
        self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([reserved]))
        self.write_yaml(root, "specs/coordination/task-completions.yaml", {"records": []})
        self.write_text(
            root,
            f"specs/tasks/{task_id}.md",
            self.task_spec(reserved, "reserved", reserved["branch"], seed),
        )
        self.write_text(root, f"evidence/{task_id}/handoff.md", "# Handoff\n")
        reservation = self.commit(root, "GZ-004 reservation (#30)")

        active = dict(reserved)
        active["status"] = "integration"
        plan["tasks"][0]["status"] = "integration"
        self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
        self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([active]))
        self.write_text(
            root,
            f"specs/tasks/{task_id}.md",
            self.task_spec(active, "integration", active["branch"], seed),
        )
        implementation = self.commit(root, "GZ-004 implementation (#31)")

        subprocess.run(
            ["git", "checkout", "-b", "chore/GZ-004-completion"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        plan["tasks"][0]["status"] = "completed"
        self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
        self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([]))
        self.write_yaml(
            root,
            "specs/coordination/task-completions.yaml",
            {
                "records": [
                    {
                        "taskId": task_id,
                        "reservationRef": "PR-30",
                        "reservationCommit": reservation,
                        "completionRef": "PR-31",
                        "mergeCommit": implementation,
                        "taskSpec": f"specs/tasks/{task_id}.md",
                        "evidencePath": f"evidence/{task_id}",
                        "handoffPath": f"evidence/{task_id}/handoff.md",
                    }
                ]
            },
        )
        self.write_text(
            root,
            f"specs/tasks/{task_id}.md",
            self.task_spec(active, "completed", "chore/GZ-004-completion", implementation),
        )
        if unrelated:
            self.write_text(root, "README.md", "unrelated\n")
        self.commit(root, "GZ-004 completion metadata (#32)")
        return reservation

    def create_foundation_completion(self, root, mode="valid", with_review=True):
        self.init_git(root)
        self.write_text(root, "seed.txt", "seed\n")
        old_foundations = []
        stale_base = self.commit(root, "Earlier baseline") if mode == "stale_reservation_base" else None
        if mode.startswith("atomic_freeze"):
            bootstrap = self.commit(root, "GZ-003 bootstrap (#11)")
            old_foundations = [{"taskId": "GZ-003", "status": "completed", "completionRef": "PR-11", "mergeCommit": bootstrap}]
        if mode == "external_rename":
            self.write_text(root, "docs/foreign.md", "external baseline content that cannot become own metadata\n")
        if mode.startswith("original_dependency_"):
            dependency_merge = self.commit(root, "GZ-003 prerequisite implementation (#19)")
            if mode == "original_dependency_unintegrated":
                tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
                dependency_merge = subprocess.check_output(["git", "commit-tree", tree, "-m", "GZ-003 detached prerequisite (#19)"], cwd=root, text=True).strip()
            old_foundations = [{"taskId": "GZ-003", "status": "reserved" if mode == "original_dependency_incomplete" else "completed", "completionRef": "PR-19", "mergeCommit": None if mode == "original_dependency_no_identity" else dependency_merge}]
        previous_plan = {"status": "active", "foundationTasks": old_foundations, "tasks": []}
        self.write_yaml(root, "specs/designs/module-ownership.yaml", {"modules": [{"id": "MOD-GOV", "ownedPaths": ["scripts/**", "tests/governance/**", "specs/coordination/**"]}]})
        with open(os.path.join(REPO_ROOT, "specs/coordination/active-work.schema.yaml"), encoding="utf-8") as schema:
            self.write_text(root, "specs/coordination/active-work.schema.yaml", schema.read())
        if mode == "preexisting_handoff":
            self.write_text(root, "evidence/GZ-014/handoff.md", "# Existing task-bound reservation handoff\n")
        self.write_yaml(root, "specs/coordination/program-plan.yaml", previous_plan)
        other_entries = []
        if mode in {"original_exclusive_conflict", "original_shared_conflict", "original_nonconflicting_claim"}:
            other = self.entry("GZ-003", "f" * 40, "reserved", "chore/GZ-003-other")
            other["riskLevel"] = "medium"
            other["exclusivePaths"] = ["scripts/other.py"] if mode == "original_nonconflicting_claim" else ["scripts/**"]
            if mode == "original_shared_conflict":
                other["sharedPaths"], other["exclusivePaths"] = other["exclusivePaths"], []
            other_entries.append(other)
        if mode in {"original_high_capacity", "original_active_capacity"}:
            for index in range(1 if mode == "original_high_capacity" else 3):
                other = self.entry(f"OPS-{100+index}", "f" * 40, "reserved", f"chore/OPS-{100+index}-other")
                other["riskLevel"] = "high" if mode == "original_high_capacity" else "medium"
                other["exclusivePaths"] = [f"scripts/other-{index}.py"]
                other_entries.append(other)
        self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry(other_entries))
        self.write_yaml(root, "specs/coordination/task-completions.yaml", {"records": []})
        seed = self.commit(root, "GZ-014 early repair before reservation (#22)")
        task_id = "GZ-014"
        entry = self.entry(task_id, seed, "reserved", "chore/GZ-014-repair")
        entry["agentRole"] = "coordinator"
        now = datetime.now(timezone.utc)
        entry["exclusivePaths"] = ["scripts/fixture-repair.py"]
        entry["lease"] = {"acquiredAt": (now-timedelta(hours=1)).isoformat(), "expiresAt": (now+timedelta(days=1)).isoformat()}
        if mode.startswith("original_dependency_"):
            entry["dependsOn"] = ["GZ-003"]
        if mode.startswith("rebase_"):
            entry["integrationStrategy"] = "rebase"
        if mode == "original_schema_issue_string":
            entry["issue"] = str(entry["issue"])
        if mode == "original_schema_unknown_property":
            entry["unknownProperty"] = "persistent schema-invalid identity"
        valid_entry = copy.deepcopy(entry)
        if mode.startswith("original_placeholder_"):
            entry[mode.removeprefix("original_placeholder_")] = "unassigned"
        if mode == "invalid_reservation_status":
            entry["status"] = "in_progress"
        if mode == "invalid_reservation_base":
            entry["baseSha"] = "f" * 40
        if mode == "stale_reservation_base":
            entry["baseSha"] = stale_base
        if mode == "original_lease_missing":
            entry.pop("lease")
        if mode in {"original_lease_expired", "historically_valid_expired_lease"}:
            entry["lease"] = {"acquiredAt": (now-timedelta(days=2)).isoformat(), "expiresAt": (now-timedelta(days=1)).isoformat()}
        if mode == "original_lease_overlong":
            entry["lease"]["expiresAt"] = (now+timedelta(hours=168)).isoformat()
        if mode == "original_lease_future_acquisition":
            entry["lease"]["acquiredAt"] = (now+timedelta(minutes=5)).isoformat()
        if mode == "original_lease_same_second":
            entry["lease"]["acquiredAt"] = now.isoformat()
        if mode == "original_claim_root":
            entry["exclusivePaths"] = ["**"]
        if mode == "original_claim_foreign":
            entry["exclusivePaths"] = ["backend/**"]
        if mode == "original_claim_shared":
            entry["sharedPaths"] = ["scripts/shared.py"]
        foundation = {
                    "taskId": task_id,
                    "title": entry["title"],
                    "status": entry["status"],
                    "completionRef": "ISSUE-30",
                    "mergeCommit": None,
                }
        plan = {
            "status": "active",
            "foundationTasks": old_foundations + [foundation],
            "tasks": [],
        }
        if mode.startswith("atomic_freeze"):
            plan["status"] = "frozen"
            plan["recovery"] = {
                "taskId": task_id,
                "reason": "Repair verified governance provenance conflict",
                "affectedTasks": ["GZ-003"],
                "sourceCommit": seed,
                "frozenAt": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z"),
                "verificationPath": "evidence/GZ-014/recovery-proof.json",
            }
            if mode == "atomic_freeze_bad_descriptor":
                plan["recovery"]["reason"] = "short"
            if mode == "atomic_freeze_wrong_owner":
                plan["recovery"]["taskId"] = "GZ-003"
        self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
        registry = self.registry([entry, dict(entry)] if mode == "duplicate_entry" else [entry])
        registry["tasks"].extend(other_entries)
        if mode == "registration_policy_change":
            registry["policy"]["maxActiveTasks"] = 2
        if mode == "atomic_freeze_other_lease":
            registry["tasks"].append(self.entry("GZ-003", seed, "reserved", "chore/GZ-003-other"))
        self.write_yaml(root, "specs/coordination/active-work.yaml", registry)
        original_spec = self.task_spec(entry, entry["status"], entry["branch"], entry["baseSha"])
        if mode == "wrong_original_task":
            original_spec = original_spec.replace("id: GZ-014", "id: GZ-015")
        if mode == "wrong_original_branch":
            original_spec = original_spec.replace("workBranch: chore/GZ-014-repair", "workBranch: chore/GZ-014-other")
        task_mutations = {
            "original_task_bootstrap": ("coordinationMode: registry", "coordinationMode: bootstrap"),
            "original_task_program": ("programPlan: specs/coordination/program-plan.yaml", "programPlan: unrelated.yaml"),
            "original_task_program_id": ("programTaskId: GZ-014", "programTaskId: OTHER-001"),
            "original_task_evidence": ("evidencePath: evidence/GZ-014", "evidencePath: evidence/OTHER-001"),
        }
        if mode in task_mutations:
            before, after = task_mutations[mode]
            assert before in original_spec
            original_spec = original_spec.replace(before, after)
        if mode == "original_task_expiry":
            original_spec = re.sub(r'^leaseExpiresAt:.*$', 'leaseExpiresAt: 2026-01-01T00:00:00Z', original_spec, flags=re.M)
        self.write_text(
            root,
            f"specs/tasks/{task_id}.md",
            original_spec,
        )
        if mode not in {"original_missing_handoff", "preexisting_handoff"}:
            self.write_text(root, f"evidence/{task_id}/handoff.md", "# Handoff\n")
        if mode == "external_rename":
            os.rename(os.path.join(root, "docs/foreign.md"), os.path.join(root, f"evidence/{task_id}/foreign.md"))
        if mode == "atomic_freeze_ledger_change":
            self.write_yaml(root, "specs/coordination/task-completions.yaml", {"records": [{"taskId": "GZ-003"}]})
        if mode == "production_reservation":
            self.write_text(root, "scripts/premature.py", "print('not metadata')\n")
        timestamp = (now-timedelta(minutes=2)).isoformat() if mode == "atomic_freeze_future_at_commit" else None
        if mode == "historically_valid_expired_lease":
            timestamp = (now-timedelta(hours=36)).isoformat()
        reservation = self.commit(root, "GZ-014 metadata reservation (#20)", timestamp=timestamp)
        if mode in {"intermediate_identity_restore", "intermediate_roles_restore"}:
            transient = copy.deepcopy(entry)
            if mode == "intermediate_identity_restore":transient["owner"] = "temporary-other-owner"
            else:transient["reviewer"] = transient["implementer"]
            self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([transient]))
            self.commit(root, "GZ-014 temporarily invalid stable identity")
            self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
            self.commit(root, "GZ-014 restore stable identity")
        if mode == "duplicate_introduction":
            self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([]))
            self.commit(root, "GZ-014 remove original lease")
            self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
            self.commit(root, "GZ-014 reintroduce lease")
        entry.update({"status": "reserved" if mode == "implementation_reserved_state" else "in_progress", "agentRole": "implementer", "baseSha": reservation, "lease": valid_entry["lease"], "exclusivePaths": valid_entry["exclusivePaths"], "sharedPaths": []})
        if mode == "original_missing_handoff":
            self.write_text(root, f"evidence/{task_id}/handoff.md", "# Added too late\n")
        if mode == "changed_stable_identity":
            entry["owner"] = "different-owner"
        foundation["status"] = "in_progress"
        if mode == "original_dependency_incomplete":
            old_foundations[0]["status"] = "completed"
        if mode == "atomic_freeze_ledger_change":
            self.write_yaml(root, "specs/coordination/task-completions.yaml", {"records": []})
        self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
        self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
        self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "in_progress", entry["branch"], reservation))
        activation = self.commit(root, "GZ-014 activation (#21)")
        if mode in {"working_exclusive_conflict", "working_shared_conflict", "working_nonconflicting_claim"}:
            other = self.entry("OPS-100", activation, "reserved", "chore/OPS-100-other")
            other["riskLevel"] = "medium"
            other["exclusivePaths"] = ["scripts/other.py"] if mode == "working_nonconflicting_claim" else ["scripts/**"]
            if mode == "working_shared_conflict":
                other["sharedPaths"], other["exclusivePaths"] = other["exclusivePaths"], []
            self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry, other]))
            self.commit(root, "OPS-100 later active registration (#29)")
        if mode in {"separate_scope_amendment", "blocked_implementation_parent"}:
            if mode == "separate_scope_amendment":
                entry["exclusivePaths"].append("scripts/new-repair.py")
            else:
                entry["status"] = foundation["status"] = "blocked"
                self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
            self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
            self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, entry["status"], entry["branch"], reservation))
            self.commit(root, "GZ-014 separate scope or blocked metadata (#26)")
            if mode == "blocked_implementation_parent":
                entry["status"] = foundation["status"] = "in_progress"
                self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
                self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
                self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "in_progress", entry["branch"], reservation))
        if mode in {"same_commit_scope_expansion", "separate_scope_amendment"}:
            if mode == "same_commit_scope_expansion":
                entry["exclusivePaths"].append("scripts/new-repair.py")
                self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
            self.write_text(root, "scripts/new-repair.py", "# newly claimed work\n")
        if mode in {"implementation_post_expired_lease", "implementation_post_missing_lease", "implementation_post_future_lease", "implementation_post_overlong_lease", "metadata_only_lease_renewal", "implementation_prior_expired_lease"}:
            if mode == "implementation_post_missing_lease":
                entry.pop("lease")
            elif mode == "implementation_post_future_lease":
                entry["lease"] = {"acquiredAt": (now+timedelta(hours=1)).isoformat(), "expiresAt": (now+timedelta(days=1)).isoformat()}
            elif mode == "implementation_post_overlong_lease":
                entry["lease"] = {"acquiredAt": (now-timedelta(hours=1)).isoformat(), "expiresAt": (now+timedelta(days=8)).isoformat()}
            else:
                # Valid when the historical activation is integrated; expired
                # by the later code/metadata node, all timestamps are explicit.
                short = {"acquiredAt": (now-timedelta(hours=2)).isoformat(), "expiresAt": (now-timedelta(minutes=1)).isoformat()}
                if mode in {"metadata_only_lease_renewal", "implementation_prior_expired_lease"}:
                    entry["lease"] = short
                    self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
                    self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "in_progress", entry["branch"], reservation))
                    self.commit(root, "GZ-014 formerly live short lease (#27)", timestamp=(now-timedelta(minutes=2)).isoformat())
                    entry["lease"] = valid_entry["lease"]
                else:
                    entry["lease"] = short
            self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
            self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "in_progress", entry["branch"], reservation))
            if mode == "metadata_only_lease_renewal":
                self.commit(root, "GZ-014 metadata-only lease renewal (#28)")
        if mode in {"rebase_earlier_unclaimed", "rebase_unclaimed_reverted"}:
            self.write_text(root, "backend/unclaimed.py", "# earlier unclaimed rebased change\n")
            self.commit(root, "GZ-014 early rebased change (#22)")
            if mode == "rebase_unclaimed_reverted":
                os.remove(os.path.join(root, "backend/unclaimed.py"))
        if mode == "rebase_ledger_reverted":
            self.write_text(root, "specs/coordination/task-completions.yaml", "records: []\n# unauthorized ledger change\n")
            self.commit(root, "GZ-014 early rebased ledger change (#22)")
            self.write_yaml(root, "specs/coordination/task-completions.yaml", {"records": []})
        if mode in {"implementation_ledger_only", "implementation_with_ledger"}:
            entry["exclusivePaths"].append("specs/coordination/task-completions.yaml")
            self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
            self.write_text(root, "specs/coordination/task-completions.yaml", "records: []\n# ledger-only implementation cannot prove repair\n")
        if mode != "implementation_ledger_only":
            self.write_text(root, "scripts/fixture-repair.py", "# actual fixture repair\n")
        if mode == "implementation_unclaimed_path":
            self.write_text(root, "backend/unclaimed.py", "# outside historical claims\n")
        if mode == "working_task_reserved":
            self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "reserved", entry["branch"], reservation))
        working_task_mutations = {
            "working_task_bootstrap": ("coordinationMode: registry", "coordinationMode: bootstrap"),
            "working_task_expiry": ("leaseExpiresAt: " + str((entry.get("lease") or {}).get("expiresAt", "MISSING")), "leaseExpiresAt: 2026-01-01T00:00:00Z"),
            "working_task_wave": ("wave: FOUNDATION", "wave: W1"),
            "working_task_title": ("titleZh: " + entry["title"], "titleZh: Unrelated task"),
            "working_task_schema": ("schemaVersion: 2", "schemaVersion: 1"),
            "working_task_evidence": ("evidencePath: evidence/GZ-014", "evidencePath: evidence/OTHER-001"),
            "working_task_program_identity": ("programTaskId: GZ-014", "programTaskId: OTHER-001"),
        }
        if mode in working_task_mutations:
            old, new = working_task_mutations[mode]
            self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "in_progress", entry["branch"], reservation).replace(old, new))
        if mode == "working_program_reserved":
            foundation["status"] = "reserved"
            self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
        if mode == "working_reviewer_code":
            entry["status"] = foundation["status"] = "review"
            entry["agentRole"] = "reviewer"
            self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
            self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
            self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "review", entry["branch"], reservation))
        implementation = self.commit(root, "GZ-014 repair (#22)")
        if mode.startswith("implementation_post_"):
            entry["lease"] = valid_entry["lease"]
        if mode in {"rebase_evidence_tip", "rebase_shortened_base", "rebase_reviewer_evidence_tip"}:
            if mode == "rebase_reviewer_evidence_tip":
                entry["status"] = foundation["status"] = "review"
                entry["agentRole"] = "reviewer"
                self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
                self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
                self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "review", entry["branch"], reservation))
            if mode == "rebase_shortened_base":
                entry["baseSha"] = implementation
                self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
                self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "in_progress", entry["branch"], implementation))
            self.write_text(root, f"evidence/{task_id}/summary.md", "# archive after rebased work\n")
            implementation = self.commit(root, "GZ-014 final rebased archive (#22)")
        if mode in {"implementation_side_before_reservation", "valid_implementation_merge"}:
            tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
            side = subprocess.check_output(["git", "commit-tree", tree, "-p", seed if mode == "implementation_side_before_reservation" else reservation, "-m", "GZ-014 implementation branch (#22)"], cwd=root, text=True).strip()
            implementation = subprocess.check_output(["git", "commit-tree", tree, "-p", activation, "-p", side, "-m", "GZ-014 integrated repair (#22)"], cwd=root, text=True).strip()
            subprocess.run(["git", "reset", "--hard", implementation], cwd=root, check=True, capture_output=True)
        if mode in {"implementation_side_late_registration", "implementation_side_old_work_second_parent"}:
            subprocess.run(["git", "checkout", "-b", "pre-registration-side", seed], cwd=root, check=True, capture_output=True)
            self.write_text(root, "scripts/fixture-repair.py", "# actual fixture repair\n")
            old_work = self.commit(root, "GZ-014 unregistered side work (#22)")
            if mode == "implementation_side_old_work_second_parent":
                subprocess.run(["git", "checkout", "--detach", reservation], cwd=root, check=True, capture_output=True)
                late_parent = old_work
            else:
                late_parent = reservation
            subprocess.run(["git", "merge", "--no-ff", "-m", "GZ-014 synchronize late registration (#22)", late_parent], cwd=root, check=True, capture_output=True)
            self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
            self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
            self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "in_progress", entry["branch"], reservation))
            side = self.commit(root, "GZ-014 late side activation (#22)")
            subprocess.run(["git", "checkout", "--detach", activation], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "merge", "--no-ff", "-m", "GZ-014 integrated repair (#22)", side], cwd=root, check=True, capture_output=True)
            implementation = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            subprocess.run(["git", "checkout", "-B", "main", implementation], cwd=root, check=True, capture_output=True)
        evidence_commit = None
        if mode == "merge_is_evidence_only":
            self.write_text(root, f"evidence/{task_id}/summary.md", "# Evidence archive only\n")
            evidence_commit = self.commit(root, "GZ-014 Evidence-only archive (#25)")
        if with_review:
            foundation["status"] = "in_progress"
            entry.update({"status": "review", "agentRole": "reviewer", "baseSha": implementation, "branch": "chore/GZ-014-review"})
            foundation["status"] = "review"
            self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
            self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
            self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "review", entry["branch"], implementation))
            audited_base = self.commit(root, "GZ-014 independent Review (#24)")
        else:
            audited_base = implementation
        claimed_implementation = implementation
        completion_ref = "PR-22"
        if mode == "merge_before_reservation":
            claimed_implementation = seed
        elif mode == "merge_is_reservation":
            claimed_implementation = reservation
            completion_ref = "PR-20"
        elif mode == "merge_is_activation":
            claimed_implementation = activation
            completion_ref = "PR-21"
        elif mode == "merge_is_review":
            claimed_implementation = audited_base
            completion_ref = "PR-24"
        elif mode == "merge_is_evidence_only":
            claimed_implementation = evidence_commit
            completion_ref = "PR-25"
        elif mode in {"unreachable_merge", "candidate_side_parent"}:
            tree = subprocess.check_output(["git", "rev-parse", f"{implementation}^{{tree}}"], cwd=root, text=True).strip()
            claimed_implementation = subprocess.check_output(
                ["git", "commit-tree", tree, "-p", reservation, "-m", "GZ-014 detached implementation (#22)"], cwd=root, text=True
            ).strip()

        subprocess.run(
            ["git", "checkout", "-b", "chore/GZ-014-completion"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        foundation.update(
            {"status": "completed", "completionRef": completion_ref, "mergeCommit": claimed_implementation}
        )
        self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
        self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([]))
        self.write_text(
            root,
            f"specs/tasks/{task_id}.md",
            self.task_spec(entry, "completed", "chore/GZ-014-completion", audited_base),
        )
        self.commit(root, "GZ-014 completion metadata (#23)")
        if mode == "candidate_side_parent":
            # An object reachable only through the proposed candidate must not
            # become an integrated implementation on the audited main history.
            current_tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], cwd=root, text=True).strip()
            candidate = subprocess.check_output(
                ["git", "commit-tree", current_tree, "-p", audited_base, "-p", claimed_implementation, "-m", "GZ-014 candidate with archive parent (#23)"], cwd=root, text=True
            ).strip()
            subprocess.run(["git", "reset", "--soft", candidate], cwd=root, check=True, capture_output=True)
        return {"seed": seed, "reservation": reservation, "implementation": implementation, "base": audited_base}

    def create_context_completion(self, folder, scenario, side_metadata=False):
        # All branch/merge mutations happen in a disposable real Git fixture.
        root = pathlib.Path(folder)
        case = self
        original = case.commit
        record = {}

        def git(*arguments):
            return subprocess.check_output(['git', *arguments], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()

        def load(path):
            return yaml.safe_load((root / path).read_text(encoding='utf-8'))

        old_entry = case.entry
        if scenario.endswith('_squash'):
            def entry(*arguments, **kwargs):
                item = old_entry(*arguments, **kwargs)
                if item['taskId'] == 'GZ-014':
                    item['integrationStrategy'] = 'squash'
                return item
            case.entry = entry

        def hook(location, message, timestamp=None):
            if message != 'GZ-014 repair (#22)':
                return original(location, message, timestamp)
            activation = git('rev-parse', 'HEAD')
            if side_metadata:
                git('checkout', '-b', 'registered-side-metadata', activation)
            registry = load('specs/coordination/active-work.yaml')
            plan = load('specs/coordination/program-plan.yaml')
            own = copy.deepcopy(next(item for item in registry['tasks'] if item['taskId'] == 'GZ-014'))
            pending = root / 'scripts/fixture-repair.py'
            code = pending.read_text(encoding='utf-8')
            pending.unlink()
            if scenario == 'main_sync':
                pending.write_text(code, encoding='utf-8')
                side_code = original(location, message, timestamp)
                git('checkout', '-B', 'main', activation)
                case.write_text(location, 'backend/main-unrelated.py', '# already integrated latest-main change\n')
                latest = original(location, 'OTHER-001 main baseline update (#29)')
                git('checkout', '-b', 'side-review', side_code)
                git('merge', '--no-ff', latest, '-m', 'GZ-014 synchronize latest main')
                synchronization = git('rev-parse', 'HEAD')
                git('checkout', 'main')
                git('merge', '--no-ff', synchronization, '-m', message)
                merge = git('rev-parse', 'HEAD')
                record.update(latestMain=latest, sideSynchronization=synchronization, rootMerge=merge)
                return merge
            if scenario in {'metadata_task', 'metadata_program'}:
                if scenario == 'metadata_task':
                    altered_spec = case.task_spec(own, own['status'], own['branch'], own['baseSha'])
                    altered_spec = re.sub(r'^leaseExpiresAt:.*$', 'leaseExpiresAt: 2026-01-01T00:00:00Z', altered_spec, flags=re.M)
                    case.write_text(location, 'specs/tasks/GZ-014.md', altered_spec)
                else:
                    altered = copy.deepcopy(plan)
                    next(item for item in altered['foundationTasks'] if item['taskId'] == 'GZ-014')['status'] = 'reserved'
                    case.write_yaml(location, 'specs/coordination/program-plan.yaml', altered)
                original(location, 'GZ-014 invalid metadata-only canonical binding (#26)')
                case.write_yaml(location, 'specs/coordination/program-plan.yaml', plan)
                case.write_text(location, 'specs/tasks/GZ-014.md', case.task_spec(own, own['status'], own['branch'], own['baseSha']))
                original(location, 'GZ-014 restore canonical binding (#27)')
            elif scenario in {'metadata_conflict', 'metadata_ownership'}:
                altered = copy.deepcopy(registry)
                target = altered['tasks'][0]
                target['exclusivePaths'].append('scripts/foreign.py' if scenario == 'metadata_conflict' else 'backend/unowned.py')
                other = case.entry('OPS-100', activation, 'reserved', 'chore/OPS-100-other')
                other['riskLevel'] = 'medium'
                other['exclusivePaths'] = ['scripts/foreign.py']
                altered['tasks'].append(other)
                case.write_yaml(location, 'specs/coordination/active-work.yaml', altered)
                case.write_text(location, 'specs/tasks/GZ-014.md', case.task_spec(target, target['status'], target['branch'], target['baseSha']))
                bad = original(location, 'GZ-014 invalid metadata-only scope amendment (#26)')
                ownership = load('specs/designs/module-ownership.yaml')
                case.write_yaml(location, 'specs/coordination/active-work.yaml', registry)
                case.write_text(location, 'specs/tasks/GZ-014.md', case.task_spec(own, own['status'], own['branch'], own['baseSha']))
                original(location, 'GZ-014 restore scope metadata (#27)')
            elif scenario == 'temporary_capacity_policy':
                altered = copy.deepcopy(registry)
                altered['policy']['maxHighRiskTasks'] = 2
                case.write_yaml(location, 'specs/coordination/active-work.yaml', altered)
                bad = original(location, 'GZ-014 temporary metadata capacity increase (#26)')
                other = case.entry('OPS-100', activation, 'reserved', 'chore/OPS-100-other')
                other['exclusivePaths'] = ['scripts/other.py']
                altered['tasks'].append(other)
                case.write_yaml(location, 'specs/coordination/active-work.yaml', altered)
                original(location, 'OPS-100 competing high risk registration (#29)')
                errors = []
                record.update(invalidMetadataCommit=bad, existingTransitionErrors=errors, duringWorkHighCount=2, originalMaxHigh=1, temporaryMaxHigh=2)
            elif scenario == 'foreign_registry':
                altered = copy.deepcopy(registry)
                foreign = next(item for item in altered['tasks'] if item['taskId'] != 'GZ-014')
                record['foreignBefore'] = copy.deepcopy(foreign)
                foreign['reviewer'] = 'different-unapproved-reviewer'
                case.write_yaml(location, 'specs/coordination/active-work.yaml', altered)
                record['foreignAfter'] = copy.deepcopy(foreign)
            elif scenario == 'foreign_program':
                altered = copy.deepcopy(plan)
                foreign = next(item for item in altered['foundationTasks'] if item['taskId'] != 'GZ-014')
                record['foreignBefore'] = copy.deepcopy(foreign)
                foreign['completionRef'] = 'PR-999'
                case.write_yaml(location, 'specs/coordination/program-plan.yaml', altered)
                record['foreignAfter'] = copy.deepcopy(foreign)
            elif scenario.startswith('integrator_'):
                reviewed_main_registry, reviewed_main_plan = copy.deepcopy(registry), copy.deepcopy(plan)
                reviewed_main_entry = reviewed_main_registry['tasks'][0]
                reviewed_main_entry.update(agentRole='reviewer', status='review')
                next(item for item in reviewed_main_plan['foundationTasks'] if item['taskId'] == 'GZ-014')['status'] = 'review'
                case.write_yaml(location, 'specs/coordination/active-work.yaml', reviewed_main_registry)
                case.write_yaml(location, 'specs/coordination/program-plan.yaml', reviewed_main_plan)
                case.write_text(location, 'specs/tasks/GZ-014.md', case.task_spec(reviewed_main_entry, 'review', reviewed_main_entry['branch'], reviewed_main_entry['baseSha']))
                review_baseline = original(location, 'GZ-014 review baseline metadata (#24)')
                record['integrationReviewBaseline'] = review_baseline
                if scenario == 'integrator_reviewed_squash':
                    git('checkout', '--detach', activation)
                    pending.write_text(code, encoding='utf-8')
                    implemented = original(location, 'GZ-014 independently implemented source (#22)')
                    reviewed_registry, reviewed_plan = copy.deepcopy(registry), copy.deepcopy(plan)
                    review_entry = reviewed_registry['tasks'][0]
                    review_entry.update(status='review', agentRole='reviewer', baseSha=implemented, branch='chore/GZ-014-source-review')
                    next(item for item in reviewed_plan['foundationTasks'] if item['taskId'] == 'GZ-014')['status'] = 'review'
                    case.write_yaml(location, 'specs/coordination/active-work.yaml', reviewed_registry)
                    case.write_yaml(location, 'specs/coordination/program-plan.yaml', reviewed_plan)
                    case.write_text(location, 'specs/tasks/GZ-014.md', case.task_spec(review_entry, 'review', review_entry['branch'], implemented))
                    reviewed = original(location, 'GZ-014 source Review metadata (#24)')
                    git('branch', 'reviewed-source', reviewed)
                    git('checkout', '-B', 'main', review_baseline)
                    squash = subprocess.run(['git', 'merge', '--squash', reviewed], cwd=root, capture_output=True, text=True)
                    if squash.returncode:
                        conflicts = git('diff', '--name-only', '--diff-filter=U').splitlines()
                        if not conflicts or any(path not in {'specs/coordination/program-plan.yaml', 'specs/coordination/active-work.yaml', 'specs/tasks/GZ-014.md'} for path in conflicts):
                            raise RuntimeError(squash.stdout + squash.stderr)
                        record['squashOwnMetadataConflictsResolved'] = conflicts
                    record.update(implementedSource=implemented, reviewMetadataSource=reviewed, reviewProofBoundary='STRUCTURAL SOURCE/REVIEW METADATA ONLY; NOT REAL HUMAN REVIEW OR GATE PASS')
                altered, altered_plan = copy.deepcopy(registry), copy.deepcopy(plan)
                target = altered['tasks'][0]
                target.update(agentRole='integrator', status='integration')
                next(item for item in altered_plan['foundationTasks'] if item['taskId'] == 'GZ-014')['status'] = 'integration'
                case.write_yaml(location, 'specs/coordination/active-work.yaml', altered)
                case.write_yaml(location, 'specs/coordination/program-plan.yaml', altered_plan)
                case.write_text(location, 'specs/tasks/GZ-014.md', case.task_spec(target, 'integration', target['branch'], target['baseSha']))
                record['integrationStrategy'] = target['integrationStrategy']
            pending.write_text(code, encoding='utf-8')
            node = original(location, message, timestamp)
            record.update(workingNode=node, parents=git('show', '-s', '--format=%P', node).split())
            if scenario in {'foreign_registry', 'foreign_program'} or scenario.startswith('integrator_'):
                errors = []
                record['existingTransitionErrors'] = errors
            if scenario == 'integrator_reviewed_squash':
                record['reviewedCodeBlobEqual'] = git('rev-parse', record['reviewMetadataSource'] + ':scripts/fixture-repair.py') == git('rev-parse', node + ':scripts/fixture-repair.py')
            if side_metadata:
                git('checkout', 'main')
                git('merge', '--no-ff', node, '-m', message)
                node = git('rev-parse', 'HEAD')
            return node
        case.commit = hook
        mode = 'working_nonconflicting_claim' if scenario == 'foreign_registry' else 'original_dependency_completed' if scenario == 'foreign_program' else 'valid'
        try:
            return case.create_foundation_completion(folder, mode)
        finally:
            case.commit = original
            case.entry = old_entry

    def test_foundation_context_main_sync(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'main_sync', side_metadata=False)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_foundation_context_metadata_conflict(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'metadata_conflict', side_metadata=False)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('claims conflict with active task', result.stdout)

    def test_foundation_context_metadata_conflict_introduced_side(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'metadata_conflict', side_metadata=True)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('claims conflict with active task', result.stdout)

    def test_foundation_context_metadata_ownership(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'metadata_ownership', side_metadata=False)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('invalid historical governance claims', result.stdout)

    def test_foundation_context_metadata_ownership_introduced_side(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'metadata_ownership', side_metadata=True)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('invalid historical governance claims', result.stdout)

    def test_foundation_context_foreign_registry(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'foreign_registry', side_metadata=False)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('changed another identity or policy', result.stdout)

    def test_foundation_context_foreign_program(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'foreign_program', side_metadata=False)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('changed another identity or policy', result.stdout)

    def test_foundation_context_temporary_capacity_policy(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'temporary_capacity_policy', side_metadata=False)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('changed the original registered capacity policy', result.stdout)

    def test_foundation_context_temporary_capacity_policy_introduced_side(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'temporary_capacity_policy', side_metadata=True)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('changed the original registered capacity policy', result.stdout)

    def test_foundation_context_metadata_task(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'metadata_task', side_metadata=False)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Task Registry binding', result.stdout)

    def test_foundation_context_metadata_task_introduced_side(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'metadata_task', side_metadata=True)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('Task Registry binding', result.stdout)

    def test_foundation_context_metadata_program(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'metadata_program', side_metadata=False)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('lifecycle documents must match', result.stdout)

    def test_foundation_context_metadata_program_introduced_side(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'metadata_program', side_metadata=True)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('lifecycle documents must match', result.stdout)

    def test_foundation_context_integrator_single_parent(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'integrator_single_parent', side_metadata=False)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_foundation_context_integrator_single_parent_squash(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'integrator_single_parent_squash', side_metadata=False)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_foundation_context_integrator_reviewed_squash(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'integrator_reviewed_squash', side_metadata=False)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def assert_owned_freeze_context(self, foreign_change=False):
        with tempfile.TemporaryDirectory() as root:
            original_entry = self.entry
            def entry(*args, **kwargs):
                value = original_entry(*args, **kwargs)
                if value['taskId'] == 'GZ-014':
                    value['integrationStrategy'] = 'rebase'
                return value
            self.entry = entry
            try:
                sources = self.create_foundation_completion(root, 'original_dependency_completed')
            finally:
                self.entry = original_entry
            subprocess.run(['git', 'checkout', '--detach', sources['implementation']], cwd=root, check=True, capture_output=True)
            plan = yaml.safe_load(pathlib.Path(root, 'specs/coordination/program-plan.yaml').read_text(encoding='utf-8'))
            plan['status'] = 'frozen'
            plan['recovery'] = {
                'taskId': 'GZ-014', 'reason': 'Repair verified completed provenance conflict',
                'affectedTasks': ['GZ-003'], 'sourceCommit': sources['implementation'],
                'frozenAt': (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace('+00:00', 'Z'),
                'verificationPath': 'evidence/GZ-014/recovery-proof.json',
            }
            if foreign_change:
                plan['foundationTasks'][0]['completionRef'] = 'PR-999'
            self.write_yaml(root, 'specs/coordination/program-plan.yaml', plan)
            self.commit(root, 'GZ-014 registered metadata-only freeze (#26)')
            self.write_text(root, 'scripts/fixture-repair.py', '# registered repair after freeze\n')
            implemented = self.commit(root, 'GZ-014 continuation repair (#22)')
            spec = importlib.util.spec_from_file_location('owned_freeze_history', SCRIPT)
            history = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(history)
            errors = []
            history.foundation_implementation(root, 'GZ-014', implemented, sources['reservation'], errors)
            if foreign_change:
                self.assertTrue(any('historical recovery rejected' in error and 'unrelated Program identities' in error for error in errors), errors)
            else:
                self.assertEqual(errors, [])

    def test_foundation_context_accepts_validated_registered_freeze(self):
        self.assert_owned_freeze_context()

    def test_foundation_context_rejects_freeze_disguising_foreign_identity_change(self):
        self.assert_owned_freeze_context(foreign_change=True)

    def test_regular_completion_transition_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_regular_completion(root)
            result = self._run_checker(root, "GZ-004", "chore/GZ-004-completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_completion_rejects_unrelated_file(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_regular_completion(root, unrelated=True)
            result = self._run_checker(root, "GZ-004", "chore/GZ-004-completion")
            self.assertIn("changed unrelated files", result.stdout)

    def test_reservation_commit_must_introduce_active_work(self):
        with tempfile.TemporaryDirectory() as root:
            reservation = self.create_regular_completion(root)
            path = os.path.join(root, "specs/coordination/task-completions.yaml")
            with open(path, encoding="utf-8") as handle:
                ledger = yaml.safe_load(handle)
            ledger["records"][0]["reservationCommit"] = subprocess.run(
                ["git", "rev-parse", f"{reservation}^"],
                cwd=root,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            self.write_yaml(root, "specs/coordination/task-completions.yaml", ledger)
            self.commit(root, "tamper reservation")
            result = self._run_checker(root, "GZ-004", "chore/GZ-004-completion")
            self.assertIn("reservation commit", result.stdout)

    def test_foundation_completion_transition_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_foundation_completion(root)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_foundation_without_review_still_requires_real_reservation(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_foundation_completion(root, with_review=False)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_foundation_review_base_can_equal_real_implementation_merge(self):
        with tempfile.TemporaryDirectory() as root:
            sources = self.create_foundation_completion(root)
            text = subprocess.check_output(["git", "show", "main:specs/coordination/active-work.yaml"], cwd=root, text=True)
            self.assertEqual(yaml.safe_load(text)["tasks"][0]["baseSha"], sources["implementation"])
            reserved = subprocess.check_output(["git", "show", sources["reservation"] + ":specs/coordination/active-work.yaml"], cwd=root, text=True)
            self.assertEqual(yaml.safe_load(reserved)["tasks"][0]["baseSha"], sources["seed"])
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def accept_foundation_history(self, mode):
        with tempfile.TemporaryDirectory() as root:
            self.create_foundation_completion(root, mode)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def reject_foundation_history(self, mode, message):
        with tempfile.TemporaryDirectory() as root:
            self.create_foundation_completion(root, mode)
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(message, result.stdout)

    def test_foundation_rejects_non_reserved_introduction(self):
        self.reject_foundation_history("invalid_reservation_status", "original reservation identity is invalid")

    def test_foundation_rejects_unknown_reservation_base(self):
        self.reject_foundation_history("invalid_reservation_base", "baseSha must be a strict ancestor")

    def test_foundation_rejects_cross_task_original_spec(self):
        self.reject_foundation_history("wrong_original_task", "Task Spec id does not match")

    def test_foundation_rejects_original_spec_branch_mismatch(self):
        self.reject_foundation_history("wrong_original_branch", "Task Spec workBranch does not match")

    def test_foundation_rejects_duplicate_original_entries(self):
        self.reject_foundation_history("duplicate_entry", "duplicate historical Registry entries")

    def test_foundation_rejects_removal_and_reintroduction(self):
        self.reject_foundation_history("duplicate_introduction", "exactly one original reservation")

    def test_foundation_rejects_production_in_registration(self):
        self.reject_foundation_history("production_reservation", "reservation must be metadata-only")

    def test_foundation_rejects_external_rename_into_registration_evidence(self):
        self.reject_foundation_history("external_rename", "reservation must be metadata-only")

    def test_foundation_accepts_verified_atomic_freeze_registration(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_foundation_completion(root, "atomic_freeze")
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_foundation_rejects_atomic_freeze_bad_descriptor(self):
        self.reject_foundation_history("atomic_freeze_bad_descriptor", "original atomic freeze rejected")

    def test_foundation_rejects_atomic_freeze_other_task_lease(self):
        self.reject_foundation_history("atomic_freeze_other_lease", "original atomic freeze rejected")

    def test_foundation_rejects_atomic_freeze_ledger_change(self):
        self.reject_foundation_history("atomic_freeze_ledger_change", "original atomic freeze rejected")

    def test_foundation_rejects_atomic_freeze_wrong_owner(self):
        self.reject_foundation_history("atomic_freeze_wrong_owner", "reservation changed another identity or policy")

    def test_foundation_rejects_registration_policy_changes(self):
        self.reject_foundation_history("registration_policy_change", "reservation changed another identity or policy")

    def test_foundation_rejects_changed_stable_owner(self):
        self.reject_foundation_history("changed_stable_identity", "does not match current stable identity")

    def test_foundation_rejects_implementation_before_reservation(self):
        self.reject_foundation_history("merge_before_reservation", "implementation must strictly follow original reservation")

    def test_foundation_rejects_reservation_as_implementation(self):
        self.reject_foundation_history("merge_is_reservation", "implementation must strictly follow original reservation")

    def test_foundation_rejects_unreachable_implementation(self):
        self.reject_foundation_history("unreachable_merge", "is not reachable from HEAD")

    def test_foundation_rejects_candidate_only_archive_parent(self):
        self.reject_foundation_history("candidate_side_parent", "implementation is not integrated on audited first-parent history")

    def test_foundation_rejects_original_missing_lease(self):
        self.reject_foundation_history("original_lease_missing", "original reservation lease is invalid")

    def test_foundation_rejects_original_expired_lease_later_renewed(self):
        self.reject_foundation_history("original_lease_expired", "original reservation lease is invalid")

    def test_foundation_rejects_original_overlong_lease_later_shortened(self):
        self.reject_foundation_history("original_lease_overlong", "original reservation lease is invalid")

    def test_foundation_rejects_original_future_lease_acquisition(self):
        self.reject_foundation_history("original_lease_future_acquisition", "original reservation lease is invalid")

    def test_foundation_accepts_same_second_subsecond_lease_acquisition(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_foundation_completion(root, "original_lease_same_second")
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_foundation_accepts_original_lease_valid_then_expired_today(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_foundation_completion(root, "historically_valid_expired_lease")
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_foundation_rejects_original_root_claim_later_narrowed(self):
        self.reject_foundation_history("original_claim_root", "original reservation may not claim the entire repository")

    def test_foundation_rejects_original_foreign_claim_later_narrowed(self):
        self.reject_foundation_history("original_claim_foreign", "original reservation claims are outside governance ownership subsets")

    def test_foundation_rejects_original_shared_claim_later_removed(self):
        self.reject_foundation_history("original_claim_shared", "original reservation requires exclusive governance claims")

    def test_foundation_rejects_stale_original_base_later_refreshed(self):
        self.reject_foundation_history("stale_reservation_base", "original reservation baseSha must equal integration parent")

    def test_foundation_rejects_original_bootstrap_mode_later_corrected(self):
        self.reject_foundation_history("original_task_bootstrap", "Task Spec canonical binding is invalid")

    def test_foundation_rejects_original_program_path_later_corrected(self):
        self.reject_foundation_history("original_task_program", "Task Spec canonical binding is invalid")

    def test_foundation_rejects_original_program_identity_later_corrected(self):
        self.reject_foundation_history("original_task_program_id", "Task Spec canonical binding is invalid")

    def test_foundation_rejects_original_foreign_evidence_path(self):
        self.reject_foundation_history("original_task_evidence", "Task Spec canonical binding is invalid")

    def test_foundation_rejects_original_task_lease_expiry_mismatch(self):
        self.reject_foundation_history("original_task_expiry", "Task Spec lease is invalid")

    def test_foundation_rejects_handoff_created_after_reservation(self):
        self.reject_foundation_history("original_missing_handoff", "Original reservation Evidence/handoff does not exist")

    def test_foundation_accepts_readable_preexisting_task_bound_handoff(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_foundation_completion(root, "preexisting_handoff")
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_foundation_rejects_transient_stable_identity_later_restored(self):
        self.reject_foundation_history("intermediate_identity_restore", "changed stable identity in audited history")

    def test_foundation_rejects_transient_collapsed_roles_later_restored(self):
        self.reject_foundation_history("intermediate_roles_restore", "lost independent roles in audited history")

    def test_foundation_rejects_freeze_future_at_commit_but_past_today(self):
        self.reject_foundation_history("atomic_freeze_future_at_commit", "Original freeze occurred after its integration commit")

    def test_foundation_rejects_original_placeholder_owner(self):
        self.reject_foundation_history("original_placeholder_owner", "original reservation requires assigned roles")

    def test_foundation_rejects_original_placeholder_coordinator(self):
        self.reject_foundation_history("original_placeholder_coordinator", "original reservation requires assigned roles")

    def test_foundation_rejects_original_placeholder_implementer(self):
        self.reject_foundation_history("original_placeholder_implementer", "original reservation requires assigned roles")

    def test_foundation_rejects_original_placeholder_reviewer(self):
        self.reject_foundation_history("original_placeholder_reviewer", "original reservation requires assigned roles")

    def test_foundation_rejects_original_placeholder_integrator(self):
        self.reject_foundation_history("original_placeholder_integrator", "original reservation requires assigned roles")

    def test_foundation_rejects_activation_as_implementation_identity(self):
        self.reject_foundation_history("merge_is_activation", "contains only lifecycle metadata or Evidence")

    def test_foundation_rejects_review_as_implementation_identity(self):
        self.reject_foundation_history("merge_is_review", "contains only lifecycle metadata or Evidence")

    def test_foundation_rejects_evidence_archive_as_implementation_identity(self):
        self.reject_foundation_history("merge_is_evidence_only", "contains only lifecycle metadata or Evidence")

    def test_foundation_rejects_unclaimed_implementation_path(self):
        self.reject_foundation_history("implementation_unclaimed_path", "outside its historical registered scope")

    def test_foundation_rejects_code_while_implementation_still_reserved(self):
        self.reject_foundation_history("implementation_reserved_state", "requires an active registered implementation state")

    def test_foundation_rejects_ledger_only_implementation(self):
        self.reject_foundation_history("implementation_ledger_only", "claimed implementation must not modify the ordinary ledger")

    def test_foundation_rejects_implementation_with_ledger_change(self):
        self.reject_foundation_history("implementation_with_ledger", "claimed implementation must not modify the ordinary ledger")

    def test_foundation_rejects_pre_registration_implementation_side(self):
        self.reject_foundation_history("implementation_side_before_reservation", "implementation-side history must descend from original reservation")

    def test_foundation_accepts_registered_implementation_merge(self):
        self.accept_foundation_history("valid_implementation_merge")

    def test_foundation_rejects_original_exclusive_claim_conflict(self):
        self.reject_foundation_history("original_exclusive_conflict", "original reservation claims conflict with active task")

    def test_foundation_rejects_original_shared_claim_conflict(self):
        self.reject_foundation_history("original_shared_conflict", "original reservation claims conflict with active task")

    def test_foundation_accepts_original_nonconflicting_claim(self):
        self.accept_foundation_history("original_nonconflicting_claim")

    def test_foundation_accepts_original_completed_dependency(self):
        self.accept_foundation_history("original_dependency_completed")

    def test_foundation_rejects_original_incomplete_dependency(self):
        self.reject_foundation_history("original_dependency_incomplete", "original reservation has incomplete dependency")

    def test_foundation_rejects_dependency_without_completion_identity(self):
        self.reject_foundation_history("original_dependency_no_identity", "lacks an integrated completion identity")

    def test_foundation_rejects_unintegrated_dependency_identity(self):
        self.reject_foundation_history("original_dependency_unintegrated", "lacks an integrated completion identity")

    def test_foundation_rejects_same_commit_scope_expansion(self):
        self.reject_foundation_history("same_commit_scope_expansion", "outside its historical registered scope")

    def test_foundation_accepts_separate_scope_amendment(self):
        self.accept_foundation_history("separate_scope_amendment")

    def test_foundation_accepts_blocked_implementation_parent(self):
        self.accept_foundation_history("blocked_implementation_parent")

    def test_foundation_rejects_expired_working_post_lease(self):
        self.reject_foundation_history("implementation_post_expired_lease", "audited history at")

    def test_foundation_rejects_missing_working_post_lease(self):
        self.reject_foundation_history("implementation_post_missing_lease", "audited history at")

    def test_foundation_rejects_future_working_post_lease(self):
        self.reject_foundation_history("implementation_post_future_lease", "audited history at")

    def test_foundation_rejects_overlong_working_post_lease(self):
        self.reject_foundation_history("implementation_post_overlong_lease", "audited history at")

    def test_foundation_rejects_code_with_expired_prior_lease(self):
        self.reject_foundation_history("implementation_prior_expired_lease", "working node prior registration at")

    def test_foundation_accepts_metadata_only_lease_renewal(self):
        self.accept_foundation_history("metadata_only_lease_renewal")

    def test_foundation_rejects_earlier_unclaimed_rebased_change(self):
        self.reject_foundation_history("rebase_earlier_unclaimed", "outside its historical registered scope")

    def test_foundation_accepts_rebase_with_evidence_only_tip(self):
        self.accept_foundation_history("rebase_evidence_tip")

    def test_foundation_rejects_rebase_ledger_change_even_if_reverted(self):
        self.reject_foundation_history("rebase_ledger_reverted", "claimed implementation must not modify the ordinary ledger")

    def test_foundation_rejects_same_tip_shortening_rebase_range(self):
        self.reject_foundation_history("rebase_shortened_base", "rebase integration base must match")

    def test_foundation_rejects_original_high_capacity_excess(self):
        self.reject_foundation_history("original_high_capacity", "exceeds historical active/high capacity limits")

    def test_foundation_rejects_original_active_capacity_excess(self):
        self.reject_foundation_history("original_active_capacity", "exceeds historical active/high capacity limits")

    def test_foundation_rejects_original_string_issue_schema(self):
        self.reject_foundation_history("original_schema_issue_string", "Registry schema violation")

    def test_foundation_rejects_original_unknown_schema_property(self):
        self.reject_foundation_history("original_schema_unknown_property", "Registry schema violation")

    def test_foundation_rejects_working_exclusive_path_conflict(self):
        self.reject_foundation_history("working_exclusive_conflict", "working node prior registration at")

    def test_foundation_rejects_working_shared_path_conflict(self):
        self.reject_foundation_history("working_shared_conflict", "working node prior registration at")

    def test_foundation_accepts_working_nonconflicting_claim(self):
        self.accept_foundation_history("working_nonconflicting_claim")

    def test_foundation_rejects_working_reserved_task(self):
        self.reject_foundation_history("working_task_reserved", "working lifecycle documents must match")

    def test_foundation_rejects_working_reserved_program(self):
        self.reject_foundation_history("working_program_reserved", "working lifecycle documents must match")

    def test_foundation_rejects_reviewer_writing_implementation(self):
        self.reject_foundation_history("working_reviewer_code", "working node requires implementer or integrator role")

    def test_foundation_accepts_reviewer_rebase_evidence_tip(self):
        self.accept_foundation_history("rebase_reviewer_evidence_tip")

    def test_foundation_rejects_working_bootstrap_task(self):
        self.reject_foundation_history("working_task_bootstrap", "working Task Spec canonical binding")

    def test_foundation_rejects_working_task_expiry_mismatch(self):
        self.reject_foundation_history("working_task_expiry", "Task Registry binding")

    def test_foundation_rejects_working_task_wave_mismatch(self):
        self.reject_foundation_history("working_task_wave", "Task Registry binding")

    def test_foundation_rejects_working_task_title_mismatch(self):
        self.reject_foundation_history("working_task_title", "Task Registry binding")

    def test_foundation_rejects_working_task_schema_one(self):
        self.reject_foundation_history("working_task_schema", "working Task Spec canonical binding")

    def test_foundation_rejects_working_foreign_evidence(self):
        self.reject_foundation_history("working_task_evidence", "working Task Spec canonical binding")

    def test_foundation_rejects_working_program_identity_mismatch(self):
        self.reject_foundation_history("working_task_program_identity", "Task Registry binding")

    def test_foundation_rejects_rebased_unclaimed_change_even_if_reverted(self):
        self.reject_foundation_history("rebase_unclaimed_reverted", "working node changed paths outside its prior registered scope")

    def test_foundation_rejects_side_work_before_late_reservation_merge(self):
        self.reject_foundation_history("implementation_side_late_registration", "working node predates its original reservation")

    def test_foundation_rejects_old_work_merged_as_registration_side_parent(self):
        self.reject_foundation_history("implementation_side_old_work_second_parent", "working node predates its original reservation")

    def test_completed_foundation_is_immutable(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_foundation_completion(root)
            subprocess.run(
                ["git", "checkout", "main"], cwd=root, check=True, capture_output=True
            )
            subprocess.run(
                ["git", "merge", "--ff-only", "chore/GZ-014-completion"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "checkout", "-b", "tamper"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            path = os.path.join(root, "specs/coordination/program-plan.yaml")
            with open(path, encoding="utf-8") as handle:
                plan = yaml.safe_load(handle)
            plan["foundationTasks"][0]["completionRef"] = "PR-999"
            self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
            self.commit(root, "tamper foundation")
            result = self._run_checker(root, base_ref="HEAD^")
            self.assertIn("provenance is immutable", result.stdout)

    def test_initial_empty_ledger_migration_passes(self):
        result = subprocess.run(
            [
                sys.executable,
                SCRIPT,
                "--repo-root",
                REPO_ROOT,
                "--base-ref",
                "origin/main",
                "--head-ref",
                "HEAD",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
