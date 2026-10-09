import os
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
        previous_plan = {"status": "active", "foundationTasks": old_foundations, "tasks": []}
        self.write_yaml(root, "specs/designs/module-ownership.yaml", {"modules": [{"id": "MOD-GOV", "ownedPaths": ["scripts/**", "tests/governance/**", "specs/coordination/**"]}]})
        if mode == "preexisting_handoff":
            self.write_text(root, "evidence/GZ-014/handoff.md", "# Existing task-bound reservation handoff\n")
        self.write_yaml(root, "specs/coordination/program-plan.yaml", previous_plan)
        self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([]))
        self.write_yaml(root, "specs/coordination/task-completions.yaml", {"records": []})
        seed = self.commit(root, "GZ-014 early repair before reservation (#22)")
        task_id = "GZ-014"
        entry = self.entry(task_id, seed, "reserved", "chore/GZ-014-repair")
        entry["agentRole"] = "coordinator"
        now = datetime.now(timezone.utc)
        entry["exclusivePaths"] = ["scripts/fixture-repair.py"]
        entry["lease"] = {"acquiredAt": (now-timedelta(hours=1)).isoformat(), "expiresAt": (now+timedelta(days=1)).isoformat()}
        valid_entry = copy.deepcopy(entry)
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
        entry.update({"status": "in_progress", "agentRole": "implementer", "baseSha": reservation, "lease": valid_entry["lease"], "exclusivePaths": valid_entry["exclusivePaths"], "sharedPaths": []})
        if mode == "original_missing_handoff":
            self.write_text(root, f"evidence/{task_id}/handoff.md", "# Added too late\n")
        if mode == "changed_stable_identity":
            entry["owner"] = "different-owner"
        foundation["status"] = "in_progress"
        if mode == "atomic_freeze_ledger_change":
            self.write_yaml(root, "specs/coordination/task-completions.yaml", {"records": []})
        self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
        self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
        self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "in_progress", entry["branch"], reservation))
        self.commit(root, "GZ-014 activation (#21)")
        self.write_text(root, "scripts/fixture-repair.py", "# actual fixture repair\n")
        implementation = self.commit(root, "GZ-014 repair (#22)")
        if with_review:
            entry.update({"status": "review", "agentRole": "reviewer", "baseSha": implementation, "branch": "chore/GZ-014-review"})
            foundation["status"] = "review"
            self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
            self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
            self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "review", entry["branch"], implementation))
            audited_base = self.commit(root, "GZ-014 independent Review (#24)")
        else:
            audited_base = implementation
        claimed_implementation = implementation
        if mode == "merge_before_reservation":
            claimed_implementation = seed
        elif mode == "merge_is_reservation":
            claimed_implementation = reservation
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
            {"status": "completed", "completionRef": "PR-20" if mode == "merge_is_reservation" else "PR-22", "mergeCommit": claimed_implementation}
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
