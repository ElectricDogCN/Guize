import os
import pathlib
import importlib.util
import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

import yaml
import jsonschema


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-program-plan-history.py")


class TestProgramPlanHistory(unittest.TestCase):
    def write_yaml(self, root, path, value):
        if path == "specs/coordination/program-plan.yaml" and getattr(self, "foundation_fixture", False):
            with open(os.path.join(REPO_ROOT, path), encoding="utf-8") as handle:
                document = yaml.safe_load(handle)
            document["foundationTasks"] = copy.deepcopy(value["foundationTasks"])
            for item in document["foundationTasks"]:
                item.setdefault("title", "Lifecycle fixture " + item["taskId"])
            if value.get("tasks"):
                document["tasks"] = copy.deepcopy(value["tasks"])
            else:
                document["tasks"] = [item for item in document["tasks"] if item["taskId"] != "GZ-014"]
                for item in document["tasks"]:
                    item["status"] = "planned"
            document.update({key: item for key, item in value.items() if key not in {"foundationTasks", "tasks"}})
            value = document
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
        self.foundation_fixture = True
        def build_registry(items):
            document = self.registry(items)
            if mode in {'original_nonconflicting_claim', 'working_nonconflicting_claim'}:
                for peer in other_entries:
                    if not any(item['taskId'] == peer['taskId'] for item in document['tasks']):
                        document['tasks'].append(copy.deepcopy(peer))
            return document

        with open(os.path.join(REPO_ROOT, "specs/coordination/program-plan.schema.yaml"), encoding="utf-8") as handle:
            self.write_text(root, "specs/coordination/program-plan.schema.yaml", handle.read())
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
        self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry(other_entries))
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
        registry = build_registry([entry, dict(entry)] if mode == "duplicate_entry" else [entry])
        registry["tasks"].extend(peer for peer in other_entries if not any(item["taskId"] == peer["taskId"] for item in registry["tasks"]))
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
            self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([transient]))
            self.commit(root, "GZ-014 temporarily invalid stable identity")
            self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry]))
            self.commit(root, "GZ-014 restore stable identity")
        if mode == "duplicate_introduction":
            self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([]))
            self.commit(root, "GZ-014 remove original lease")
            self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry]))
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
        self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry]))
        self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "in_progress", entry["branch"], reservation))
        activation = self.commit(root, "GZ-014 activation (#21)")
        if mode in {"working_exclusive_conflict", "working_shared_conflict", "working_nonconflicting_claim"}:
            other = self.entry("OPS-100", activation, "reserved", "chore/OPS-100-other")
            other["riskLevel"] = "medium"
            other["exclusivePaths"] = ["scripts/other.py"] if mode == "working_nonconflicting_claim" else ["scripts/**"]
            if mode == "working_shared_conflict":
                other["sharedPaths"], other["exclusivePaths"] = other["exclusivePaths"], []
            if mode == 'working_nonconflicting_claim':
                # This is an approved peer input, not a change introduced by
                # the tested implementation. Preserve its exact registration.
                other.update(agentRole='coordinator', lease=copy.deepcopy(entry['lease']))
                other_entries.append(other)
                materialized = yaml.safe_load(pathlib.Path(root, 'specs/coordination/program-plan.yaml').read_text(encoding='utf-8'))
                row = copy.deepcopy(materialized['tasks'][0])
                row.update(taskId=other['taskId'], title=other['title'], kind='governance', status='reserved', riskLevel='medium', wave='W1', integrationOrder=other['integrationOrder'], dependsOn=[], requirementIds=other['requirementIds'], moduleIds=other['moduleIds'], outputPaths=other['exclusivePaths'], sharedPaths=[], producesContracts=[], consumesContracts=[], issue=other['issue'], coordinationGroup=other['coordinationGroup'], workPackage=other['workPackage'], branchPattern='chore/OPS-100-*')
                materialized['tasks'].append(row)
                plan = materialized
                foundation = next(item for item in plan['foundationTasks'] if item['taskId'] == task_id)
                self.write_yaml(root, 'specs/coordination/program-plan.yaml', plan)
                self.write_text(root, 'specs/tasks/OPS-100.md', self.task_spec(other, 'reserved', other['branch'], activation))
                self.write_text(root, 'evidence/OPS-100/handoff.md', '# Registered nonconflicting peer input\n')
            self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry, other]))
            peer_main = self.commit(root, "OPS-100 later active registration (#29)")
            if mode == 'working_nonconflicting_claim':
                entry['baseSha'] = peer_main
                self.write_yaml(root, 'specs/coordination/active-work.yaml', build_registry([entry]))
                self.write_text(root, f'specs/tasks/{task_id}.md', self.task_spec(entry, 'in_progress', entry['branch'], peer_main))
                self.commit(root, 'GZ-014 adopt approved peer main baseline (#28)')
        if mode in {"separate_scope_amendment", "blocked_implementation_parent"}:
            if mode == "separate_scope_amendment":
                entry["exclusivePaths"].append("scripts/new-repair.py")
            else:
                entry["status"] = foundation["status"] = "blocked"
                self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
            self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry]))
            self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, entry["status"], entry["branch"], reservation))
            self.commit(root, "GZ-014 separate scope or blocked metadata (#26)")
            if mode == "blocked_implementation_parent":
                entry["status"] = foundation["status"] = "in_progress"
                self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
                self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry]))
                self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "in_progress", entry["branch"], reservation))
        if mode in {"same_commit_scope_expansion", "separate_scope_amendment"}:
            if mode == "same_commit_scope_expansion":
                entry["exclusivePaths"].append("scripts/new-repair.py")
                self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry]))
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
                    self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry]))
                    self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "in_progress", entry["branch"], reservation))
                    self.commit(root, "GZ-014 formerly live short lease (#27)", timestamp=(now-timedelta(minutes=2)).isoformat())
                    entry["lease"] = valid_entry["lease"]
                else:
                    entry["lease"] = short
            self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry]))
            self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "in_progress", entry["branch"], reservation))
            if mode == "metadata_only_lease_renewal":
                self.commit(root, "GZ-014 metadata-only lease renewal (#28)")
        if mode in {"rebase_earlier_unclaimed", "rebase_unclaimed_reverted", "merge_earlier_unclaimed", "merge_unclaimed_reverted", "merge_same_commit_base_change", "merge_separate_base_advance", "merge_separate_base_advance_after_revert"}:
            self.write_text(root, "backend/unclaimed.py", "# earlier unclaimed rebased change\n")
            self.commit(root, "GZ-014 early rebased change (#22)")
            if mode in {"rebase_unclaimed_reverted", "merge_unclaimed_reverted"}:
                os.remove(os.path.join(root, "backend/unclaimed.py"))
            elif mode == "merge_same_commit_base_change":
                early = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
                entry['baseSha'] = early
                self.write_yaml(root, 'specs/coordination/active-work.yaml', build_registry([entry]))
                self.write_text(root, f'specs/tasks/{task_id}.md', self.task_spec(entry, 'in_progress', entry['branch'], early))
        if mode in {"merge_separate_base_advance", "merge_separate_base_advance_after_revert"}:
            if mode == "merge_separate_base_advance_after_revert":
                os.remove(os.path.join(root, "backend/unclaimed.py"))
                self.commit(root, "GZ-014 restore early unclaimed file before base advance (#27)")
            early = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
            entry['baseSha'] = early
            self.write_yaml(root, 'specs/coordination/active-work.yaml', build_registry([entry]))
            self.write_text(root, f'specs/tasks/{task_id}.md', self.task_spec(entry, 'in_progress', entry['branch'], early))
            self.commit(root, "GZ-014 separate metadata-only base advance (#28)")
        if mode == "rebase_ledger_reverted":
            self.write_text(root, "specs/coordination/task-completions.yaml", "records: []\n# unauthorized ledger change\n")
            self.commit(root, "GZ-014 early rebased ledger change (#22)")
            self.write_yaml(root, "specs/coordination/task-completions.yaml", {"records": []})
        if mode in {"implementation_ledger_only", "implementation_with_ledger"}:
            entry["exclusivePaths"].append("specs/coordination/task-completions.yaml")
            self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry]))
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
            self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry]))
            self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "review", entry["branch"], reservation))
        implementation = self.commit(root, "GZ-014 repair (#22)")
        if mode.startswith("implementation_post_"):
            entry["lease"] = valid_entry["lease"]
        if mode in {"rebase_evidence_tip", "rebase_shortened_base", "rebase_reviewer_evidence_tip"}:
            if mode == "rebase_reviewer_evidence_tip":
                entry["status"] = foundation["status"] = "review"
                entry["agentRole"] = "reviewer"
                self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
                self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry]))
                self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "review", entry["branch"], reservation))
            if mode == "rebase_shortened_base":
                entry["baseSha"] = implementation
                self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry]))
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
            self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry]))
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
        implementation_registry = yaml.safe_load(pathlib.Path(root, "specs/coordination/active-work.yaml").read_text(encoding="utf-8"))
        implementation_entries = [item for item in implementation_registry["tasks"] if item["taskId"] == task_id]
        already_integrated = len(implementation_entries) == 1 and implementation_entries[0]["status"] == "integration"
        if with_review and not already_integrated:
            foundation["status"] = "in_progress"
            review_target = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
            entry.update({"status": "review", "agentRole": "reviewer", "baseSha": review_target, "branch": "chore/GZ-014-review"})
            foundation["status"] = "review"
            self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
            self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([entry]))
            self.write_text(root, f"specs/tasks/{task_id}.md", self.task_spec(entry, "review", entry["branch"], review_target))
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
        self.write_yaml(root, "specs/coordination/active-work.yaml", build_registry([]))
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


    def create_postclaim_completion(self, root, scenario):
        root = pathlib.Path(root)
        original = self.commit
        old_registry, old_write = self.registry, self.write_yaml
        foreign = {}

        def git(*args):
            return subprocess.check_output(['git', *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()

        def load(path):
            return yaml.safe_load((root / path).read_text(encoding='utf-8'))

        def registry(items):
            value = old_registry(items)
            if foreign and not any(item['taskId'] == 'GZ-099' for item in value['tasks']):
                value['tasks'].append(copy.deepcopy(foreign['entry']))
            return value

        def write(location, path, value):
            if path == 'specs/coordination/program-plan.yaml' and foreign:
                value = copy.deepcopy(value)
                if not any(item.get('taskId') == 'GZ-099' for item in value.get('tasks', [])):
                    value['tasks'] = load(path)['tasks']
            old_write(location, path, value)

        def rewrite(entry, state, base):
            plan = load('specs/coordination/program-plan.yaml')
            next(item for item in plan['foundationTasks'] if item['taskId'] == 'GZ-014')['status'] = state
            entry.update(status=state, baseSha=base)
            self.write_yaml(root, 'specs/coordination/program-plan.yaml', plan)
            self.write_yaml(root, 'specs/coordination/active-work.yaml', self.registry([entry]))
            self.write_text(root, 'specs/tasks/GZ-014.md', self.task_spec(entry, state, entry['branch'], base))

        def hook(location, message, timestamp=None):
            if message != 'GZ-014 independent Review (#24)':
                return original(location, message, timestamp)
            entry = copy.deepcopy(load('specs/coordination/active-work.yaml')['tasks'][0])
            parent = git('rev-parse', 'HEAD')
            if scenario in {'missing_review_base', 'stale_review_base', 'direct_integration', 'review_implementer_role'}:
                state, base = 'review', parent
                if scenario == 'missing_review_base':
                    base = 'f' * 40
                elif scenario == 'stale_review_base':
                    base = git('rev-parse', parent + '~2')
                elif scenario == 'direct_integration':
                    state, entry['agentRole'] = 'integration', 'integrator'
                else:
                    entry['agentRole'] = 'implementer'
                rewrite(entry, state, base)
                bad = original(location, message, timestamp)
                if scenario in {'missing_review_base', 'stale_review_base'}:
                    rewrite(entry, 'review', bad)
                    return original(location, 'GZ-014 restore actual Review target (#25)')
                return bad
            if scenario == 'review_unclaimed_code':
                self.write_text(root, 'backend/x.py', '# never claimed code bundled with Own Review\n')
            review = original(location, message, timestamp)
            if scenario == 'review_unclaimed_code':
                return review
            if scenario == 'same_node_peer_claim_code_restore':
                saved = load('specs/coordination/active-work.yaml')
                malformed = copy.deepcopy(saved)
                peer = self.entry('OPS-100', review, 'reserved', 'chore/OPS-100-fabricated')
                peer.update(riskLevel='medium', agentRole='coordinator', exclusivePaths=['backend/x.py'])
                malformed['tasks'].append(peer)
                self.write_yaml(root, 'specs/coordination/active-work.yaml', malformed)
                self.write_text(root, 'backend/x.py', '# fabricated same-node claim cannot authorize code\n')
                original(location, 'OPS-100 fabricated same-node claim and code (#25)')
                self.write_yaml(root, 'specs/coordination/active-work.yaml', saved)
                (root / 'backend/x.py').unlink()
                return original(location, 'OPS-100 restore fabricated registration and code (#26)')

            if scenario == 'scalar_registry_peer':
                saved = load('specs/coordination/active-work.yaml')
                malformed = copy.deepcopy(saved)
                malformed['tasks'].append(None)
                self.write_yaml(root, 'specs/coordination/active-work.yaml', malformed)
                self.write_text(root, 'backend/scalar-diagnostic.py', '# unclaimed work with malformed peer\n')
                original(location, 'GZ-014 malformed historical scalar peer (#25)')
                self.write_yaml(root, 'specs/coordination/active-work.yaml', saved)
                (root / 'backend/scalar-diagnostic.py').unlink()
                return original(location, 'GZ-014 restore malformed peer and work (#26)')
            if scenario in {'side_bad_base', 'side_bad_edge', 'side_owner_identity', 'side_foreign_definition'}:
                git('checkout', '-b', 'late-metadata-side', review)
                saved_entry = copy.deepcopy(entry)
                state = 'in_progress' if scenario == 'side_bad_edge' else 'review'
                base = 'f' * 40 if scenario == 'side_bad_base' else parent
                rewrite(entry, state, base)
                saved_plan = load('specs/coordination/program-plan.yaml')
                if scenario == 'side_owner_identity':
                    entry['owner'] = 'other-valid-owner'
                    rewrite(entry, 'review', base)
                elif scenario == 'side_foreign_definition':
                    changed = copy.deepcopy(saved_plan)
                    changed['tasks'][0]['title'] = 'Unapproved changed frozen task title'
                    changed['tasks'][0]['outputPaths'] = ['backend/unapproved-foreign-output.py']
                    self.write_yaml(root, 'specs/coordination/program-plan.yaml', changed)
                original(location, 'GZ-014 invalid later side metadata (#25)')
                self.write_yaml(root, 'specs/coordination/program-plan.yaml', saved_plan)
                rewrite(saved_entry, 'review', saved_entry['baseSha'])
                side = original(location, 'GZ-014 restore earlier side metadata (#26)')
                git('checkout', '-B', 'main', review)
                git('merge', '--no-ff', '-m', 'GZ-014 merge restored metadata side (#27)', side)
                self.assertEqual(git('diff', '--name-only', review, 'HEAD'), '')
                return git('rev-parse', 'HEAD')
            if scenario == 'shrink_scope_restore':
                entry['exclusivePaths'] = ['scripts/fixture-repair.py', 'scripts/second-repair.py']
                rewrite(entry, 'review', parent)
                original(location, 'GZ-014 retain two own claims (#25)')
                saved = copy.deepcopy(entry)
                before = (root / 'scripts/fixture-repair.py').read_text(encoding='utf-8')
                entry['exclusivePaths'] = ['scripts/second-repair.py']
                rewrite(entry, 'review', parent)
                original(location, 'GZ-014 narrow own scope (#26)')
                self.write_text(root, 'scripts/fixture-repair.py', '# unreviewed work after narrowing own scope\n')
                original(location, 'GZ-014 unclaimed former own file (#27)')
                self.write_text(root, 'scripts/fixture-repair.py', before)
                original(location, 'GZ-014 restore former own file (#28)')
                rewrite(saved, 'review', parent)
                return original(location, 'GZ-014 restore original claims (#29)')
            if scenario == 'integration_implementer_role':
                entry['agentRole'] = 'implementer'
                rewrite(entry, 'integration', review)
                return original(location, 'GZ-014 Integration metadata (#25)')
            if scenario == 'legal_rework_metadata':
                for state in ['blocked', 'in_progress', 'review']:
                    rewrite(entry, state, git('rev-parse', 'HEAD'))
                    original(location, 'GZ-014 legal metadata rework ' + state + ' (#25)')
                return git('rev-parse', 'HEAD')
            if scenario in {'foreign_disjoint', 'foreign_disjoint_side', 'foreign_owner_restore'}:
                if scenario == 'foreign_disjoint_side':
                    git('checkout', '-b', 'foreign-task-side', review)
                other = self.entry('GZ-099', review, 'in_progress', 'chore/GZ-099-other')
                other.update(agentRole='implementer', riskLevel='medium', programWave='W1', exclusivePaths=['scripts/other-task.py'], lease=copy.deepcopy(entry['lease']))
                plan = load('specs/coordination/program-plan.yaml')
                row = copy.deepcopy(plan['tasks'][0])
                row.update(taskId='GZ-099', title=other['title'], kind='governance', status='in_progress', riskLevel='medium', wave='W1', integrationOrder=other['integrationOrder'], dependsOn=[], requirementIds=other['requirementIds'], moduleIds=other['moduleIds'], outputPaths=other['exclusivePaths'], sharedPaths=[], producesContracts=[], consumesContracts=[], issue=other['issue'], coordinationGroup=other['coordinationGroup'], workPackage=other['workPackage'], branchPattern='chore/GZ-099-*')
                plan['tasks'].append(row)
                foreign['entry'] = other
                self.write_yaml(root, 'specs/coordination/program-plan.yaml', plan)
                self.write_yaml(root, 'specs/coordination/active-work.yaml', self.registry([entry, other]))
                self.write_text(root, 'specs/tasks/GZ-099.md', self.task_spec(other, 'in_progress', other['branch'], review))
                original(location, 'GZ-099 disjoint registered context (#29)')
                self.write_text(root, 'scripts/other-task.py', '# separately registered disjoint task work\n')
                work = original(location, 'GZ-099 disjoint implementation (#30)')
                if scenario == 'foreign_owner_restore':
                    saved = copy.deepcopy(other)
                    other['owner'] = 'temporary-foreign-owner'
                    foreign['entry'] = other
                    self.write_yaml(root, 'specs/coordination/active-work.yaml', self.registry([entry, other]))
                    self.write_text(root, 'specs/tasks/GZ-099.md', self.task_spec(other, 'in_progress', other['branch'], review))
                    original(location, 'GZ-099 unapproved peer owner rewrite (#31)')
                    other.clear(); other.update(saved)
                    foreign['entry'] = other
                    self.write_yaml(root, 'specs/coordination/active-work.yaml', self.registry([entry, other]))
                    self.write_text(root, 'specs/tasks/GZ-099.md', self.task_spec(other, 'in_progress', other['branch'], review))
                    return original(location, 'GZ-099 restore original peer owner (#32)')
                if scenario == 'foreign_disjoint_side':
                    other.update(status='review', agentRole='reviewer', baseSha=work)
                    other['lease']['expiresAt'] = entry['lease']['expiresAt']
                    next(item for item in plan['tasks'] if item['taskId'] == 'GZ-099')['status'] = 'review'
                    self.write_yaml(root, 'specs/coordination/program-plan.yaml', plan)
                    self.write_yaml(root, 'specs/coordination/active-work.yaml', self.registry([entry, other]))
                    self.write_text(root, 'specs/tasks/GZ-099.md', self.task_spec(other, 'review', other['branch'], work))
                    side = original(location, 'GZ-099 independent peer Review metadata (#31)')
                    git('checkout', '-B', 'main', review)
                    git('merge', '--no-ff', '-m', 'GZ-099 integrate peer side work (#32)', side)
                    return git('rev-parse', 'HEAD')
                return work
            if scenario in {'root_freeze_bad_source', 'root_thaw_missing_proof', 'root_recovery_same_status_restore'}:
                saved_plan = load('specs/coordination/program-plan.yaml')
                frozen = copy.deepcopy(saved_plan)
                frozen['status'] = 'frozen'
                frozen['recovery'] = {
                    'taskId': 'GZ-014', 'reason': 'Repair completed provenance conflict',
                    'affectedTasks': ['GZ-003'], 'sourceCommit': 'f' * 40 if scenario == 'root_freeze_bad_source' else review,
                    'frozenAt': (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace('+00:00', 'Z'),
                    'verificationPath': 'evidence/GZ-014/recovery-proof.json',
                }
                self.write_yaml(root, 'specs/coordination/program-plan.yaml', frozen)
                frozen_commit = original(location, 'GZ-014 postclaim root freeze (#25)')
                if scenario == 'root_thaw_missing_proof':
                    spec = importlib.util.spec_from_file_location('postclaim_valid_freeze', SCRIPT)
                    history = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(history)
                    freeze_errors = []
                    self.assertEqual(history.RECOVERY.validate_recovery_transition(str(root), review, frozen_commit, freeze_errors), 'GZ-014')
                    self.assertEqual(freeze_errors, [])
                if scenario == 'root_recovery_same_status_restore':
                    changed = copy.deepcopy(frozen)
                    changed['recovery']['reason'] = 'Unapproved replacement of the frozen incident reason'
                    self.write_yaml(root, 'specs/coordination/program-plan.yaml', changed)
                    original(location, 'GZ-014 rewrite frozen event without a transition (#27)')
                    self.write_yaml(root, 'specs/coordination/program-plan.yaml', frozen)
                    original(location, 'GZ-014 restore frozen event (#28)')
                self.write_yaml(root, 'specs/coordination/program-plan.yaml', saved_plan)
                restored = original(location, 'GZ-014 restore active root without validated repair proof (#26)')
                self.assertEqual(git('diff', '--name-only', review, restored), '')
                return restored
            if scenario == 'own_evidence':
                self.write_text(root, 'evidence/GZ-014/reviewer-findings.md', '# Independent review evidence\n')
                return original(location, 'GZ-014 own Evidence archive (#25)')
            path = 'scripts/fixture-repair.py'
            before = (root / path).read_text(encoding='utf-8')
            if scenario in {'late_side_restore', 'missing_own_registration', 'second_parent_missing_registration'}:
                review_plan = load('specs/coordination/program-plan.yaml')
                if scenario == 'second_parent_missing_registration':
                    reservation = git('rev-parse', parent + '~2')
                    seed = git('rev-parse', parent + '~3')
                    git('checkout', '-b', 'late-reviewer-side', seed)
                    git('merge', '--no-ff', '--no-commit', reservation)
                    self.write_yaml(root, 'specs/coordination/active-work.yaml', self.registry([]))
                    merged = original(location, 'GZ-014 late second-parent reservation without own entry (#25)')
                    self.assertEqual(git('show', '-s', '--format=%P', merged).split(), [seed, reservation])
                else:
                    git('checkout', '-b', 'late-reviewer-side', review)
                if scenario == 'missing_own_registration':
                    self.write_yaml(root, 'specs/coordination/active-work.yaml', self.registry([]))
                    original(location, 'GZ-014 temporarily remove own side registration (#25)')
                self.write_text(root, path, '# later code omitted from claimed implementation\n')
                original(location, 'GZ-014 late Reviewer work (#26)')
                self.write_text(root, path, before)
                original(location, 'GZ-014 restore earlier code (#27)')
                if scenario in {'missing_own_registration', 'second_parent_missing_registration'}:
                    self.write_yaml(root, 'specs/coordination/program-plan.yaml', review_plan)
                    self.write_yaml(root, 'specs/coordination/active-work.yaml', self.registry([entry]))
                    self.write_text(root, 'specs/tasks/GZ-014.md', self.task_spec(entry, 'review', entry['branch'], entry['baseSha']))
                    original(location, 'GZ-014 restore own side registration (#28)')
                side = git('rev-parse', 'HEAD')
                git('checkout', '-B', 'main', review)
                git('merge', '--no-ff', '-m', 'GZ-014 merge restored side (#29)', side)
                self.assertEqual(git('diff', '--name-only', review, 'HEAD'), '')
                return git('rev-parse', 'HEAD')
            self.write_text(root, path, '# unreviewed later Reviewer code\n')
            return original(location, 'GZ-014 later Reviewer code (#25)')

        self.commit, self.registry, self.write_yaml = hook, registry, write
        try:
            sources = self.create_foundation_completion(root, 'original_dependency_completed' if scenario in {'root_freeze_bad_source', 'root_thaw_missing_proof', 'root_recovery_same_status_restore'} else 'valid')
            if scenario == 'shrink_scope_restore':
                registered = yaml.safe_load(git('show', sources['base'] + ':specs/coordination/active-work.yaml'))['tasks'][0]
                self.write_text(root, 'specs/tasks/GZ-014.md', self.task_spec(registered, 'completed', 'chore/GZ-014-completion', sources['base']))
                original(root, 'GZ-014 bind Completion to restored exact scope (#23)')
            return sources
        finally:
            self.commit, self.registry, self.write_yaml = original, old_registry, old_write

    def assert_postclaim_history(self, scenario, accepted, message=''):
        with tempfile.TemporaryDirectory() as root:
            self.create_postclaim_completion(root, scenario)
            result = self._run_checker(root, 'GZ-014', 'chore/GZ-014-completion')
            if accepted:
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            else:
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn(message, result.stdout)

    def test_foundation_postclaim_recovery_same_status_restore(self):
        self.assert_postclaim_history('root_recovery_same_status_restore', False, 'Program recovery metadata may only change in freeze/thaw transitions')

    def test_foundation_postclaim_accepts_validated_clean_freeze_import(self):
        with tempfile.TemporaryDirectory() as root:
            sources = self.create_foundation_completion(root, 'original_dependency_completed')
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
            git('checkout', '-B', 'main', sources['base'])
            git('checkout', '-b', 'valid-freeze-side')
            self.write_text(root, 'evidence/GZ-014/side.md', '# Side review evidence\n')
            side_base = self.commit(root, 'GZ-014 side review evidence (#25)')
            plan = yaml.safe_load(pathlib.Path(root, 'specs/coordination/program-plan.yaml').read_text(encoding='utf-8'))
            plan['status'] = 'frozen'
            plan['recovery'] = {
                'taskId': 'GZ-014', 'reason': 'Repair completed provenance conflict',
                'affectedTasks': ['GZ-003'], 'sourceCommit': side_base,
                'frozenAt': (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace('+00:00', 'Z'),
                'verificationPath': 'evidence/GZ-014/recovery-proof.json',
            }
            self.write_yaml(root, 'specs/coordination/program-plan.yaml', plan)
            side = self.commit(root, 'GZ-014 registered side freeze (#26)')
            spec = importlib.util.spec_from_file_location('postclaim_clean_freeze', SCRIPT)
            history = importlib.util.module_from_spec(spec);spec.loader.exec_module(history)
            freeze_errors = []
            self.assertEqual(history.RECOVERY.validate_recovery_transition(root, side_base, side, freeze_errors), 'GZ-014')
            self.assertEqual(freeze_errors, [])
            git('checkout', 'main')
            self.write_text(root, 'evidence/GZ-014/main.md', '# Main review evidence\n')
            self.commit(root, 'GZ-014 main review evidence (#27)')
            git('merge', '--no-ff', '-m', 'GZ-014 clean import of validated side freeze (#28)', side)
            merged = git('rev-parse', 'HEAD')
            self.assertEqual(git('rev-parse', merged + ':specs/coordination/program-plan.yaml'), git('rev-parse', side + ':specs/coordination/program-plan.yaml'))
            errors = []
            history.foundation_post_implementation(root, 'GZ-014', sources['implementation'], sources['reservation'], merged, errors)
            self.assertEqual(errors, [])

    def test_foundation_postclaim_foreign_owner_restore(self):
        self.assert_postclaim_history('foreign_owner_restore', False, 'changed stable Registry identity or scope for GZ-099')

    def test_foundation_postclaim_invalid_freeze_restore(self):
        self.assert_postclaim_history('root_freeze_bad_source', False, 'Freeze sourceCommit must equal the actual target base')

    def test_foundation_postclaim_invalid_thaw_after_valid_freeze(self):
        self.assert_postclaim_history('root_thaw_missing_proof', False, 'historical recovery rejected')

    def test_foundation_postclaim_missing_review_base(self):
        self.assert_postclaim_history('missing_review_base', False, 'baseSha must identify a real ancestor')

    def test_foundation_postclaim_stale_review_base(self):
        self.assert_postclaim_history('stale_review_base', False, 'audited main Review baseSha must equal')

    def test_foundation_postclaim_direct_integration(self):
        self.assert_postclaim_history('direct_integration', False, 'forbidden historical lifecycle transition in_progress -> integration')

    def test_foundation_postclaim_review_implementer_role(self):
        self.assert_postclaim_history('review_implementer_role', True, '')

    def test_foundation_postclaim_integration_implementer_role(self):
        self.assert_postclaim_history('integration_implementer_role', True, '')

    def test_foundation_postclaim_legal_rework_metadata(self):
        self.assert_postclaim_history('legal_rework_metadata', True, '')

    def test_foundation_postclaim_foreign_disjoint(self):
        self.assert_postclaim_history('foreign_disjoint', True, '')

    def test_foundation_postclaim_own_evidence(self):
        self.assert_postclaim_history('own_evidence', True, '')

    def test_foundation_postclaim_late_side_restore(self):
        self.assert_postclaim_history('late_side_restore', False, 'own code changes after claimed implementation')

    def test_foundation_postclaim_missing_own_registration(self):
        self.assert_postclaim_history('missing_own_registration', False, 'own code changes after claimed implementation')

    def test_foundation_postclaim_late_reviewer_code(self):
        self.assert_postclaim_history('late_reviewer_code', False, 'own code changes after claimed implementation')

    def test_foundation_postclaim_second_parent_missing_registration(self):
        self.assert_postclaim_history('second_parent_missing_registration', False, 'own code changes after claimed implementation')

    def test_foundation_postclaim_side_bad_base(self):
        self.assert_postclaim_history('side_bad_base', False, 'baseSha must identify a real ancestor')

    def test_foundation_postclaim_side_bad_edge(self):
        self.assert_postclaim_history('side_bad_edge', False, 'forbidden historical lifecycle transition review -> in_progress')

    def test_foundation_postclaim_side_owner_identity(self):
        self.assert_postclaim_history('side_owner_identity', False, 'changed stable identity in post-implementation history')

    def test_foundation_postclaim_side_foreign_definition(self):
        self.assert_postclaim_history('side_foreign_definition', False, 'changed frozen ordinary Task definition')

    def test_foundation_postclaim_shrink_scope_restore(self):
        self.assert_postclaim_history('shrink_scope_restore', False, 'own code changes after claimed implementation')

    def test_foundation_rejects_old_ledger_rewrite_restored_before_baseline_advance(self):
        # Scope: existing record immutability, not full peer historical Gate.
        with tempfile.TemporaryDirectory() as folder:
            root = pathlib.Path(folder)
            self.create_regular_completion(folder)
            subprocess.run(['git', 'checkout', '-B', 'main', 'HEAD'], cwd=root, check=True, capture_output=True)
            ledger_path = 'specs/coordination/task-completions.yaml'
            original_ledger = yaml.safe_load((root / ledger_path).read_text(encoding='utf-8'))
            original_bytes = (root / ledger_path).read_bytes()
            self.assertEqual(original_ledger['records'][0]['taskId'], 'GZ-004')
            ordinary_completion = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
            original_commit, original_write = self.commit, self.write_yaml
            observations = {}

            def write(location, path, value):
                # Foundation fixture seeds an empty Ledger; retain the actual
                # previously created ordinary completion record instead.
                if path == ledger_path and value == {'records': []}:
                    value = copy.deepcopy(original_ledger)
                original_write(location, path, value)

            def hook(location, message, timestamp=None):
                if message != 'GZ-014 repair (#22)':
                    return original_commit(location, message, timestamp)
                code_path = root / 'scripts/fixture-repair.py'
                code = code_path.read_bytes()
                code_path.unlink()  # repair file is staged only at claimed code.
                before = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
                changed = copy.deepcopy(original_ledger)
                changed['records'][0]['completionRef'] = 'PR-999'
                original_write(folder, ledger_path, changed)
                bad = original_commit(folder, 'GZ-014 rewrite old Ledger (#26)', timestamp)
                (root / ledger_path).write_bytes(original_bytes)
                restored = original_commit(folder, 'GZ-014 restore old Ledger (#27)', timestamp)
                entry = yaml.safe_load((root / 'specs/coordination/active-work.yaml').read_text(encoding='utf-8'))['tasks'][0]
                entry['baseSha'] = restored
                self.write_yaml(folder, 'specs/coordination/active-work.yaml', self.registry([entry]))
                self.write_text(folder, 'specs/tasks/GZ-014.md', self.task_spec(entry, entry['status'], entry['branch'], restored))
                advance = original_commit(folder, 'GZ-014 metadata baseline advance (#28)', timestamp)
                code_path.write_bytes(code)
                claimed = original_commit(location, message, timestamp)
                observations.update(before=before, bad=bad, restored=restored, advance=advance, claimed=claimed)
                return claimed

            self.write_yaml, self.commit = write, hook
            try:
                sources = self.create_foundation_completion(folder, 'valid')
                result = self._run_checker(folder, 'GZ-014', 'chore/GZ-014-completion')
            finally:
                self.write_yaml, self.commit = original_write, original_commit
            self.assertTrue(ordinary_completion)
            self.assertEqual(subprocess.check_output(['git', 'diff', '--name-only', observations['before'], observations['bad']], cwd=root, text=True).strip(), ledger_path)
            self.assertEqual(subprocess.check_output(['git', 'diff', observations['before'], observations['claimed'], '--', ledger_path], cwd=root, text=True), '')
            self.assertEqual((root / ledger_path).read_bytes(), original_bytes)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('changed immutable Ledger record GZ-004', result.stdout)


    def test_foundation_merge_separate_base_advance(self):
        self.reject_foundation_history('merge_separate_base_advance', 'outside its prior registered scope')

    def test_foundation_merge_separate_base_advance_after_revert(self):
        self.reject_foundation_history('merge_separate_base_advance_after_revert', 'outside its prior registered scope')

    def assert_post_disjoint_peer_old_lease(self, own_work=False):
        """Scope/history classification fixture, not full peer Admission/Gate."""
        spec = importlib.util.spec_from_file_location("peer_old_lease_history", SCRIPT)
        h = importlib.util.module_from_spec(spec); spec.loader.exec_module(h)
        now = datetime.now(timezone.utc); early = (now-timedelta(minutes=30)).isoformat()
        short = {"acquiredAt": (now-timedelta(hours=1)).isoformat(), "expiresAt": (now-timedelta(minutes=10)).isoformat()}; rec = {}
        with tempfile.TemporaryDirectory(prefix='ops004-oldlease-case-') as folder:
         root=pathlib.Path(folder);case=self;original=case.commit;future={}
         def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True,encoding='utf-8',stderr=subprocess.DEVNULL).strip()
         def load(p):return yaml.safe_load((root/p).read_text(encoding='utf-8'))
         def hook(location,message,timestamp=None):
          if message=='GZ-014 completion metadata (#23)':return original(location,message,timestamp)
          if (root/h.ACTIVE).exists():
           doc=load(h.ACTIVE);own=next((x for x in doc['tasks'] if x['taskId']=='GZ-014'),None)
           if own:
            if not future:future.update(copy.deepcopy(own['lease']))
            own['lease']=copy.deepcopy(short);case.write_yaml(folder,h.ACTIVE,doc);case.write_text(folder,'specs/tasks/GZ-014.md',case.task_spec(own,own['status'],own['branch'],own['baseSha']))
          if message!='GZ-014 independent Review (#24)':return original(location,message,early)
          review=original(location,message,early);rec['review']=review
          subprocess.run(['git','checkout','-b','peer-side',review],cwd=root,check=True,capture_output=True)
          reg=load(h.ACTIVE);peer=next(x for x in reg['tasks'] if x['taskId']=='OPS-100');peer.update(status='in_progress',agentRole='implementer',baseSha=review);case.write_yaml(folder,h.ACTIVE,reg);plan=load(h.PLAN);next(x for x in plan['tasks'] if x['taskId']=='OPS-100')['status']='in_progress';case.write_yaml(folder,h.PLAN,plan);case.write_text(folder,'specs/tasks/OPS-100.md',case.task_spec(peer,peer['status'],peer['branch'],peer['baseSha']));activate=original(folder,'OPS-100 side activation (#30)',(now-timedelta(minutes=20)).isoformat());case.write_text(folder,'scripts/other.py','# disjoint peer code, own registry/task unchanged\n');
          if own_work:case.write_text(folder,'scripts/fixture-repair.py','# own code using expired own side lease\n')
          work=original(folder,'OPS-100 disjoint code after own old lease expiry (#31)',now.isoformat());rec.update(peerActivation=activate,peerWork=work,peerWorkPaths=git('diff','--name-only',activate,work).splitlines(),workOwnEntry=copy.deepcopy(next(x for x in load(h.ACTIVE)['tasks'] if x['taskId']=='GZ-014')))
          subprocess.run(['git','checkout','--detach',review],cwd=root,check=True,capture_output=True)
          reg=load(h.ACTIVE);own=next(x for x in reg['tasks'] if x['taskId']=='GZ-014');own['lease']=copy.deepcopy(future);case.write_yaml(folder,h.ACTIVE,reg);case.write_text(folder,'specs/tasks/GZ-014.md',case.task_spec(own,own['status'],own['branch'],own['baseSha']));renew=original(folder,'GZ-014 main lease renewal (#32)',(now-timedelta(minutes=15)).isoformat());env=os.environ.copy();env.update(GIT_AUTHOR_DATE=now.isoformat(),GIT_COMMITTER_DATE=now.isoformat());merge=subprocess.run(['git','merge','--no-ff','-m','OPS-100 merge disjoint peer preserving main renewal (#33)',work],cwd=root,env=env,capture_output=True,text=True);rec['normalMergeExit']=merge.returncode;rec['normalMergeStdout']=merge.stdout;rec['normalMergeStderr']=merge.stderr
          if merge.returncode:raise RuntimeError('unexpected merge conflict '+merge.stdout+merge.stderr)
          tip=git('rev-parse','HEAD');subprocess.run(['git','branch','-f','main',tip],cwd=root,check=True,capture_output=True);rec.update(renewal=renew,renewalPaths=git('diff','--name-only',review,renew).splitlines(),merged=tip,mergedOwnEntry=copy.deepcopy(next(x for x in load(h.ACTIVE)['tasks'] if x['taskId']=='GZ-014')),mainSideParents=git('show','-s','--format=%P',tip).split());return tip
         case.commit=hook;sources=case.create_foundation_completion(folder,'working_nonconflicting_claim');case.commit=original
         # Builder-local peer row remains its old input; retain exact actually merged
         # peer metadata so the final completion changes only the completing task.
         base=sources['base'];baseplan=h.load_ref(folder,base,h.PLAN);current=load(h.PLAN);own=next(x for x in current['foundationTasks'] if x['taskId']=='GZ-014');baseplan['foundationTasks']=[own if x['taskId']=='GZ-014' else x for x in baseplan['foundationTasks']];case.write_yaml(folder,h.PLAN,baseplan);basereg=h.load_ref(folder,base,h.ACTIVE);basereg['tasks']=[x for x in basereg['tasks'] if x['taskId']!='GZ-014'];case.write_yaml(folder,h.ACTIVE,basereg);subprocess.run(['git','add','.'],cwd=root,check=True,capture_output=True);subprocess.run(['git','commit','--amend','--no-edit'],cwd=root,check=True,capture_output=True)
         result=case._run_checker(folder,'GZ-014','chore/GZ-014-completion');pe=[];h.foundation_post_implementation(folder,'GZ-014',sources['implementation'],sources['reservation'],base,pe);rec.update(sources=sources,historyExit=result.returncode,stdout=result.stdout,stderr=result.stderr,postErrors=pe,finalCompletionPaths=git('diff','--name-only',base,'HEAD').splitlines(),oldLease=short,newLease=future,peerAdmissionBoundary='Real disjoint peer Git lifecycle fixture for history classification only; not a claim of full peer Admission/Transitions/Gate',firstParentHistory=git('log','--first-parent','--format=%H %ct %s','main').splitlines())
         self.assertEqual(rec["normalMergeExit"], 0)
         self.assertEqual(rec["mergedOwnEntry"]["lease"], future)
         if own_work:
          self.assertEqual(result.returncode, 1, result.stdout)
          self.assertIn("own code changes after claimed implementation", result.stdout)
         else:
          self.assertEqual(result.returncode, 0, result.stdout)


    def test_foundation_post_disjoint_peer_old_own_lease(self):
        self.assert_post_disjoint_peer_old_lease()

    def test_foundation_post_own_work_old_side_lease_rejected(self):
        self.assert_post_disjoint_peer_old_lease(own_work=True)


    def test_foundation_implementation_scalar_program_reports_schema_failure(self):
        with tempfile.TemporaryDirectory() as root:
            original = self.commit
            def commit(location, message, timestamp=None):
                if message != 'GZ-014 repair (#22)':
                    return original(location, message, timestamp)
                path = 'specs/coordination/program-plan.yaml'
                saved = yaml.safe_load((pathlib.Path(root) / path).read_text(encoding='utf-8'))
                malformed = copy.deepcopy(saved)
                malformed['tasks'].append(None)
                self.write_yaml(root, path, malformed)
                implementation = original(location, message, timestamp)
                self.write_yaml(root, path, saved)
                original(location, 'GZ-014 restore Program scalar after implementation (#26)', timestamp)
                return implementation
            self.commit = commit
            try:
                self.create_foundation_completion(root, 'valid')
            finally:
                self.commit = original
            result = self._run_checker(root, 'GZ-014', 'chore/GZ-014-completion')
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('Program schema violation', result.stdout)
            self.assertNotIn('Traceback', result.stdout + result.stderr)
            self.assertTrue(all(json.loads(line)['status'] == 'FAIL' for line in result.stdout.splitlines()))

    def test_foundation_postclaim_new_peer_claim_cannot_authorize_same_node_code(self):
        # Malformed/fabricated peer is intentional; no claim of Peer Admission.
        self.assert_postclaim_history('same_node_peer_claim_code_restore', False,
            'post-implementation working node changed paths outside its prior registered scope')

    def test_foundation_scalar_registry_peer_reports_schema_failure(self):
        # Intentionally malformed historical input; no claim of peer Admission.
        with tempfile.TemporaryDirectory() as root:
            self.create_postclaim_completion(root, 'scalar_registry_peer')
            result = self._run_checker(root, 'GZ-014', 'chore/GZ-014-completion')
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('Registry schema violation', result.stdout)
            self.assertNotIn('Traceback', result.stdout + result.stderr)
            self.assertTrue(all(json.loads(line)['status'] == 'FAIL' for line in result.stdout.splitlines()))

    def test_foundation_postclaim_review_unclaimed_code(self):
        self.assert_postclaim_history('review_unclaimed_code', False, 'post-implementation working node changed paths outside its prior registered scope')

    def test_foundation_merge_earlier_unclaimed(self):
        self.reject_foundation_history('merge_earlier_unclaimed', 'outside its historical registered scope')

    def test_foundation_merge_unclaimed_reverted(self):
        self.reject_foundation_history('merge_unclaimed_reverted', 'outside its prior registered scope')

    def test_foundation_merge_same_commit_base_change(self):
        self.reject_foundation_history('merge_same_commit_base_change', 'outside its historical registered scope')

    def test_foundation_postclaim_foreign_disjoint_side(self):
        self.assert_postclaim_history('foreign_disjoint_side', True)

    def create_combined_registry_sync_completion(self, folder):
        root = pathlib.Path(folder)
        case = self
        original = case.commit
        oldreg = case.registry
        oldwrite = case.write_yaml
        other_entry = None
        other_task = None
        enabled = False
        record = {}

        def git(*args):
            p = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, encoding='utf-8')
            if p.returncode:
                raise RuntimeError(p.stdout + p.stderr)
            return p.stdout.strip()

        def load(p):
            return yaml.safe_load((root / p).read_text(encoding='utf-8'))

        def registry(entries):
            result = oldreg(entries)
            if enabled and (not any((e['taskId'] == 'GZ-099' for e in result['tasks']))):
                result['tasks'].append(copy.deepcopy(other_entry))
            return result

        def write(location, path, value):
            if path == 'specs/coordination/program-plan.yaml' and enabled:
                oldwrite(location, path, value)
                doc = load(path)
                doc['tasks'].append(copy.deepcopy(other_task))
                case.write_text(location, path, yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
                return
            oldwrite(location, path, value)
        case.registry = registry
        case.write_yaml = write

        def hook(location, message, timestamp=None):
            nonlocal enabled, other_entry, other_task
            if message != 'GZ-014 repair (#22)':
                return original(location, message, timestamp)
            activation = git('rev-parse', 'HEAD')
            pending = root / 'scripts/fixture-repair.py'
            code = pending.read_text(encoding='utf-8')
            pending.unlink()
            reg = load('specs/coordination/active-work.yaml')
            own = copy.deepcopy(reg['tasks'][0])
            git('checkout', '-b', 'side-work', activation)
            renew = copy.deepcopy(own)
            from datetime import datetime, timedelta
            renew['lease']['expiresAt'] = (datetime.fromisoformat(own['lease']['expiresAt']) + timedelta(hours=1)).isoformat()
            case.write_yaml(location, 'specs/coordination/active-work.yaml', oldreg([renew]))
            case.write_text(location, 'specs/tasks/GZ-014.md', case.task_spec(renew, 'in_progress', renew['branch'], renew['baseSha']))
            renewal = original(location, 'GZ-014 metadata-only lease renewal (#28)')
            pending.write_text(code, encoding='utf-8')
            implemented = original(location, message, timestamp)
            git('checkout', '-B', 'main', activation)
            other_entry = case.entry('GZ-099', activation, 'reserved', 'chore/GZ-099-medium')
            other_entry.update(agentRole='coordinator', riskLevel='medium', programWave='W1', exclusivePaths=['scripts/other.py'])
            other_entry['lease'] = copy.deepcopy(own['lease'])
            doc = load('specs/coordination/program-plan.yaml')
            other_task = copy.deepcopy(doc['tasks'][0])
            other_task.update(taskId='GZ-099', title=other_entry['title'], kind='governance', status='reserved', riskLevel='medium', wave='W1', integrationOrder=other_entry['integrationOrder'], dependsOn=[], requirementIds=other_entry['requirementIds'], moduleIds=other_entry['moduleIds'], outputPaths=other_entry['exclusivePaths'], sharedPaths=[], producesContracts=[], consumesContracts=[], issue=other_entry['issue'], coordinationGroup=other_entry['coordinationGroup'], workPackage=other_entry['workPackage'], branchPattern='chore/GZ-099-*')
            enabled = True
            case.write_yaml(location, 'specs/coordination/active-work.yaml', case.registry([own]))
            doc['tasks'].append(other_task)
            case.write_text(location, 'specs/coordination/program-plan.yaml', yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
            case.write_text(location, 'specs/tasks/GZ-099.md', case.task_spec(other_entry, 'reserved', other_entry['branch'], other_entry['baseSha']))
            latest = original(location, 'GZ-099 medium task reservation (#29)')
            git('checkout', 'side-work')
            merging = subprocess.run(['git', 'merge', '--no-ff', latest, '-m', 'GZ-014 synchronize medium-task reservation'], cwd=root, capture_output=True, text=True)
            record['automaticMergeExit'] = merging.returncode
            record['automaticMergeStdout'] = merging.stdout
            if merging.returncode:
                conflicts = git('diff', '--name-only', '--diff-filter=U').splitlines()
                assert conflicts == ['specs/coordination/active-work.yaml'], conflicts
                record['resolvedOnlyOwnRenewalAgainstApprovedForeignRegistry'] = True
                case.write_yaml(location, 'specs/coordination/active-work.yaml', case.registry([renew]))
                original(location, 'GZ-014 retain own renewed lease and import approved foreign registry')
            sync = git('rev-parse', 'HEAD')
            record.update(activation=activation, renewal=renewal, implemented=implemented, latestMain=latest, synchronization=sync, registryCombinedWithOwnRenewal=True)
            git('checkout', 'main')
            git('merge', '--no-ff', 'side-work', '-m', message)
            merge = git('rev-parse', 'HEAD')
            record['netDiffPaths'] = git('diff', '--name-only', latest, merge).splitlines()
            return merge
        case.commit = hook
        try:
            case.create_foundation_completion(folder)
        finally:
            case.commit = original
            case.registry = oldreg
            case.write_yaml = oldwrite
        return (case._run_checker(folder, 'GZ-014', 'chore/GZ-014-completion'), record)

    def test_foundation_own_renewal_with_main_foreign_registry_conflict(self):
        with tempfile.TemporaryDirectory() as root:
            result, record = self.create_combined_registry_sync_completion(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(record['automaticMergeExit'], 1)
            self.assertTrue(record['resolvedOnlyOwnRenewalAgainstApprovedForeignRegistry'])

    def create_foreign_conflict_completion(self, folder):
        root = pathlib.Path(folder)
        case = self
        original = case.commit
        oldreg = case.registry
        oldwrite = case.write_yaml
        other_entry = None
        other_task = None
        enabled = False
        record = {}

        def git(*args, allow=False):
            p = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, encoding='utf-8')
            if p.returncode and (not allow):
                raise RuntimeError(p.stdout + p.stderr)
            return p if allow else p.stdout.strip()

        def load(p):
            return yaml.safe_load((root / p).read_text(encoding='utf-8'))

        def registry(entries):
            result = oldreg(entries)
            if enabled and (not any((e['taskId'] == 'GZ-099' for e in result['tasks']))):
                result['tasks'].append(copy.deepcopy(other_entry))
            return result

        def write(location, path, value):
            if path == 'specs/coordination/program-plan.yaml' and enabled:
                oldwrite(location, path, value)
                doc = load(path)
                doc['tasks'].append(copy.deepcopy(other_task))
                case.write_text(location, path, yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
                return
            oldwrite(location, path, value)
        case.registry = registry
        case.write_yaml = write

        def hook(location, message, timestamp=None):
            nonlocal enabled, other_entry, other_task
            if message != 'GZ-014 repair (#22)':
                return original(location, message, timestamp)
            activation = git('rev-parse', 'HEAD')
            pending = root / 'scripts/fixture-repair.py'
            code = pending.read_text(encoding='utf-8')
            pending.unlink()
            own = copy.deepcopy(load('specs/coordination/active-work.yaml')['tasks'][0])
            other_entry = case.entry('GZ-099', activation, 'reserved', 'chore/GZ-099-medium')
            other_entry.update(agentRole='coordinator', riskLevel='medium', programWave='W1', exclusivePaths=['scripts/other.py'])
            other_entry['lease'] = copy.deepcopy(own['lease'])
            doc = load('specs/coordination/program-plan.yaml')
            other_task = copy.deepcopy(doc['tasks'][0])
            other_task.update(taskId='GZ-099', title=other_entry['title'], kind='governance', status='reserved', riskLevel='medium', wave='W1', integrationOrder=other_entry['integrationOrder'], dependsOn=[], requirementIds=other_entry['requirementIds'], moduleIds=other_entry['moduleIds'], outputPaths=other_entry['exclusivePaths'], sharedPaths=[], producesContracts=[], consumesContracts=[], issue=other_entry['issue'], coordinationGroup=other_entry['coordinationGroup'], workPackage=other_entry['workPackage'], branchPattern='chore/GZ-099-*')
            enabled = True

            def write_foreign():
                case.write_yaml(location, 'specs/coordination/active-work.yaml', case.registry([own]))
                case.write_text(location, 'specs/tasks/GZ-099.md', case.task_spec(other_entry, 'reserved', other_entry['branch'], other_entry['baseSha']))
            write_foreign()
            doc['tasks'].append(other_task)
            case.write_text(location, 'specs/coordination/program-plan.yaml', yaml.safe_dump(doc, allow_unicode=True, sort_keys=False))
            common = original(location, 'GZ-099 medium task reservation (#29)')
            base_entry = copy.deepcopy(other_entry)
            git('checkout', '-B', 'main', common)
            other_entry['lease']['expiresAt'] = (datetime.fromisoformat(base_entry['lease']['expiresAt']) + timedelta(hours=2)).isoformat()
            current_entry = copy.deepcopy(other_entry)
            write_foreign()
            prior = original(location, 'GZ-099 current main lease renewal (#30)')
            git('checkout', '-b', 'other-older', common)
            other_entry = copy.deepcopy(base_entry)
            other_entry['lease']['expiresAt'] = (datetime.fromisoformat(base_entry['lease']['expiresAt']) + timedelta(hours=1)).isoformat()
            older_entry = copy.deepcopy(other_entry)
            write_foreign()
            older = original(location, 'GZ-099 earlier independent lease renewal (#31)')
            git('checkout', 'main')
            p = git('merge', '--no-ff', older, '-m', 'GZ-099 integrate earlier renewal preserving current lease', allow=True)
            assert p.returncode == 1
            record['approvedMainConflictPaths'] = git('diff', '--name-only', '--diff-filter=U').splitlines()
            other_entry = copy.deepcopy(current_entry)
            write_foreign()
            latest = original(location, 'GZ-099 approved current lease resolution (#32)')
            git('checkout', '-b', 'side-work', prior)
            pending.write_text(code, encoding='utf-8')
            implemented = original(location, message, timestamp)
            p = git('merge', '--no-ff', older, '-m', 'GZ-014 select earlier foreign renewal', allow=True)
            assert p.returncode == 1
            record['sideConflictPaths'] = git('diff', '--name-only', '--diff-filter=U').splitlines()
            other_entry = copy.deepcopy(older_entry)
            write_foreign()
            bad = original(location, 'GZ-014 unauthorized foreign lease conflict resolution (#33)')
            p = git('merge', '--no-ff', latest, '-m', 'GZ-014 restore approved foreign lease', allow=True)
            if p.returncode:
                assert p.returncode == 1
                other_entry = copy.deepcopy(current_entry)
                write_foreign()
                original(location, 'GZ-014 restore approved current foreign lease (#34)')
            other_entry = copy.deepcopy(current_entry)
            git('checkout', 'main')
            git('merge', '--no-ff', 'side-work', '-m', message)
            merge = git('rev-parse', 'HEAD')
            record.update(common=common, prior=prior, older=older, latestMain=latest, working=implemented, staleConflictResolution=bad, rootMerge=merge, netDiffPaths=git('diff', '--name-only', latest, merge).splitlines())
            return merge
        case.commit = hook
        try:
            case.create_foundation_completion(folder)
        finally:
            case.commit = original
            case.registry = oldreg
            case.write_yaml = oldwrite
        return (case._run_checker(folder, 'GZ-014', 'chore/GZ-014-completion'), record)

    def test_foundation_rejects_foreign_registry_conflict_restored_later(self):
        with tempfile.TemporaryDirectory() as root:
            result, record = self.create_foreign_conflict_completion(root)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('changed another identity or policy', result.stdout)
            self.assertIn('specs/coordination/active-work.yaml', record['sideConflictPaths'])
            self.assertNotIn('specs/coordination/active-work.yaml', record['netDiffPaths'])

    def create_program_sync_completion(self, folder, scenario):
        root = pathlib.Path(folder)
        case = self
        orig = self.commit
        oldwrite = self.write_yaml
        record = {}
        with open(os.path.join(REPO_ROOT, 'specs/coordination/program-plan.schema.yaml'), encoding='utf-8') as handle:
            validator = jsonschema.Draft202012Validator(yaml.safe_load(handle), format_checker=jsonschema.FormatChecker())

        def git(*args, allow=False):
            result = subprocess.run(['git', *args], cwd=root, capture_output=True, text=True, encoding='utf-8')
            if result.returncode and not allow:
                raise RuntimeError(result.stdout + result.stderr)
            return result if allow else result.stdout.strip()

        def hook(location, message, timestamp=None):
            if message == 'GZ-014 early repair before reservation (#22)':
                case.write_text(location, 'backend/main-unrelated.py', 'version0\n')
            if message != 'GZ-014 repair (#22)':
                return orig(location, message, timestamp)
            activation = git('rev-parse', 'HEAD')
            pending = root / 'scripts/fixture-repair.py'
            code = pending.read_text(encoding='utf-8')
            pending.unlink()
            if scenario in {'legitimate_old_main_sync', 'conflicted_stale_resolution'}:
                git('checkout', '-B', 'main', activation)
                if scenario == 'legitimate_old_main_sync':
                    case.write_text(location, 'backend/main-unrelated.py', 'version1\n')
                    older = orig(location, 'OTHER-001 older main update (#29)')
                    git('checkout', '-b', 'side-review', activation)
                    pending.write_text(code, encoding='utf-8')
                    orig(location, message, timestamp)
                    git('merge', '--no-ff', older, '-m', 'GZ-014 clean synchronize older main')
                    old_sync = git('rev-parse', 'HEAD')
                    git('checkout', 'main')
                    case.write_text(location, 'backend/main-unrelated.py', 'version2\n')
                    latest = orig(location, 'OTHER-001 later main update (#30)')
                    git('checkout', 'side-review')
                    git('merge', '--no-ff', latest, '-m', 'GZ-014 clean synchronize later main')
                    latest_sync = git('rev-parse', 'HEAD')
                    record.update(older=older, latest=latest, oldSynchronization=old_sync, laterSynchronization=latest_sync, olderSynchronizationWasClean=True)
                else:
                    case.write_text(location, 'backend/main-unrelated.py', 'version2\n')
                    prior = orig(location, 'OTHER-001 current main update (#30)')
                    git('checkout', '-b', 'other-older', activation)
                    case.write_text(location, 'backend/main-unrelated.py', 'version1\n')
                    older = orig(location, 'OTHER-001 earlier independent main update (#29)')
                    git('checkout', 'main')
                    conflict = git('merge', '--no-ff', older, '-m', 'OTHER-001 approved resolution retains current version', allow=True)
                    assert conflict.returncode == 1 and git('diff', '--name-only', '--diff-filter=U') == 'backend/main-unrelated.py'
                    case.write_text(location, 'backend/main-unrelated.py', 'version2\n')
                    latest = orig(location, 'OTHER-001 approved main resolution (#31)')
                    git('checkout', '-b', 'side-review', prior)
                    pending.write_text(code, encoding='utf-8')
                    orig(location, message, timestamp)
                    bad = git('merge', '--no-ff', older, '-m', 'GZ-014 resolve foreign path to older content', allow=True)
                    assert bad.returncode == 1 and git('diff', '--name-only', '--diff-filter=U') == 'backend/main-unrelated.py'
                    case.write_text(location, 'backend/main-unrelated.py', 'version1\n')
                    old_sync = orig(location, 'GZ-014 unauthorized foreign conflict resolution (#32)')
                    restore = git('merge', '--no-ff', latest, '-m', 'GZ-014 synchronize final approved main', allow=True)
                    if restore.returncode:
                        assert git('diff', '--name-only', '--diff-filter=U') == 'backend/main-unrelated.py'
                        case.write_text(location, 'backend/main-unrelated.py', 'version2\n')
                        orig(location, 'GZ-014 restore approved main content (#33)')
                    latest_sync = git('rev-parse', 'HEAD')
                    record.update(older=older, latest=latest, oldSynchronization=old_sync, laterSynchronization=latest_sync, staleMergeHadRealConflict=True, foreignPath='backend/main-unrelated.py', oldSyncBlob=git('show', old_sync + ':backend/main-unrelated.py'), finalMainBlob=git('show', latest + ':backend/main-unrelated.py'))
                git('checkout', 'main')
                git('merge', '--no-ff', 'side-review', '-m', message)
                node = git('rev-parse', 'HEAD')
                record['netDiffPaths'] = git('diff', '--name-only', latest, node).splitlines()
                return node
            if scenario in {'invalid_own_program', 'duplicate_own_program', 'forged_own_reference', 'premature_own_merge', 'duplicate_ordinary', 'missing_program_schema'}:
                plan = yaml.safe_load((root / 'specs/coordination/program-plan.yaml').read_text(encoding='utf-8'))
                own = next((e for e in plan['foundationTasks'] if e['taskId'] == 'GZ-014'))
                record['baselineSchemaErrors'] = [e.message for e in validator.iter_errors(plan)]
                if scenario == 'invalid_own_program':
                    own['completionRef'] = 123
                elif scenario == 'duplicate_own_program':
                    plan['foundationTasks'].append(copy.deepcopy(own))
                elif scenario == 'forged_own_reference':
                    own['completionRef'] = 'PR-999'
                elif scenario == 'premature_own_merge':
                    own['mergeCommit'] = activation
                elif scenario == 'duplicate_ordinary':
                    plan['tasks'].append(copy.deepcopy(plan['tasks'][0]))
                oldwrite(location, 'specs/coordination/program-plan.yaml', plan)
                record['changedSchemaErrors'] = [e.message for e in validator.iter_errors(plan)]
                record['ownFoundationCount'] = sum((e['taskId'] == 'GZ-014' for e in plan['foundationTasks']))
            if scenario == 'missing_program_schema':
                (root / 'specs/coordination/program-plan.schema.yaml').unlink()
            pending.write_text(code, encoding='utf-8')
            node = orig(location, message, timestamp)
            record['workingNode'] = node
            return node
        self.commit = hook
        try:
            self.create_foundation_completion(folder)
        finally:
            self.commit = orig
        return self._run_checker(folder, 'GZ-014', 'chore/GZ-014-completion'), record

    def test_foundation_program_sync_valid_full_program(self):
        with tempfile.TemporaryDirectory() as root:
            result, record = self.create_program_sync_completion(root, 'valid_full_program')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_foundation_program_sync_legitimate_old_main_sync(self):
        with tempfile.TemporaryDirectory() as root:
            result, record = self.create_program_sync_completion(root, 'legitimate_old_main_sync')
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_foundation_program_sync_conflicted_stale_resolution(self):
        with tempfile.TemporaryDirectory() as root:
            result, record = self.create_program_sync_completion(root, 'conflicted_stale_resolution')
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('outside its prior registered scope', result.stdout)
            self.assertTrue(record['staleMergeHadRealConflict'])
            self.assertNotIn(record['foreignPath'], record['netDiffPaths'])

    def test_foundation_program_sync_invalid_own_program(self):
        with tempfile.TemporaryDirectory() as root:
            result, record = self.create_program_sync_completion(root, 'invalid_own_program')
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('Program schema violation', result.stdout)
            self.assertEqual(record['baselineSchemaErrors'], [])

    def test_foundation_program_sync_duplicate_own_program(self):
        with tempfile.TemporaryDirectory() as root:
            result, record = self.create_program_sync_completion(root, 'duplicate_own_program')
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('Program task identities must be unique', result.stdout)
            self.assertEqual(record['baselineSchemaErrors'], [])

    def test_foundation_program_sync_forged_own_reference(self):
        with tempfile.TemporaryDirectory() as root:
            result, record = self.create_program_sync_completion(root, 'forged_own_reference')
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('ISSUE registration', result.stdout)
            self.assertEqual(record['baselineSchemaErrors'], [])

    def test_foundation_program_sync_premature_own_merge(self):
        with tempfile.TemporaryDirectory() as root:
            result, record = self.create_program_sync_completion(root, 'premature_own_merge')
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('no completion merge', result.stdout)
            self.assertEqual(record['baselineSchemaErrors'], [])

    def test_foundation_program_sync_duplicate_ordinary(self):
        with tempfile.TemporaryDirectory() as root:
            result, record = self.create_program_sync_completion(root, 'duplicate_ordinary')
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('Program task identities must be unique', result.stdout)
            self.assertEqual(record['baselineSchemaErrors'], [])

    def test_foundation_program_sync_missing_program_schema(self):
        with tempfile.TemporaryDirectory() as root:
            result, record = self.create_program_sync_completion(root, 'missing_program_schema')
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn('Applicable Program schema is missing', result.stdout)
            self.assertEqual(record['baselineSchemaErrors'], [])

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
            if scenario in {'main_sync', 'main_sync_new_registered_base'}:
                pending.write_text(code, encoding='utf-8')
                side_code = original(location, message, timestamp)
                git('checkout', '-B', 'main', activation)
                case.write_text(location, 'backend/main-unrelated.py', '# already integrated latest-main change\n')
                latest = original(location, 'OTHER-001 main baseline update (#29)')
                if scenario == 'main_sync_new_registered_base':
                    refreshed = copy.deepcopy(registry)
                    refreshed['tasks'][0]['baseSha'] = latest
                    case.write_yaml(location, 'specs/coordination/active-work.yaml', refreshed)
                    case.write_text(location, 'specs/tasks/GZ-014.md', case.task_spec(refreshed['tasks'][0], 'in_progress', own['branch'], latest))
                    latest = original(location, 'GZ-014 registered latest-main baseline (#30)')
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
                reviewed_main_entry.update(agentRole='reviewer', status='review', baseSha=activation)
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
                target.update(agentRole='integrator', status='integration', baseSha=review_baseline)
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

    def test_foundation_context_approved_main_sync_new_registered_base(self):
        with tempfile.TemporaryDirectory() as root:
            self.create_context_completion(root, 'main_sync_new_registered_base')
            result = self._run_checker(root, "GZ-014", "chore/GZ-014-completion")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_foundation_side_review_retains_real_main_target(self):
        with tempfile.TemporaryDirectory() as root:
            sources = self.create_foundation_completion(root)
            activation = subprocess.check_output(['git', 'rev-parse', sources['implementation'] + '^1'], cwd=root, text=True).strip()
            subprocess.run(['git', 'checkout', '-B', 'chore/GZ-014-repair', activation], cwd=root, check=True, capture_output=True)
            registry = yaml.safe_load(pathlib.Path(root, 'specs/coordination/active-work.yaml').read_text(encoding='utf-8'))
            entry = registry['tasks'][0]
            entry['baseSha'] = activation
            self.write_yaml(root, 'specs/coordination/active-work.yaml', registry)
            self.write_text(root, 'specs/tasks/GZ-014.md', self.task_spec(entry, 'in_progress', entry['branch'], activation))
            self.write_text(root, 'scripts/fixture-repair.py', '# side implementation while main stays at activation\n')
            work = self.commit(root, 'GZ-014 side implementation (#22)')
            plan = yaml.safe_load(pathlib.Path(root, 'specs/coordination/program-plan.yaml').read_text(encoding='utf-8'))
            next(item for item in plan['foundationTasks'] if item['taskId'] == 'GZ-014')['status'] = 'review'
            entry.update(status='review', agentRole='reviewer')
            self.write_yaml(root, 'specs/coordination/program-plan.yaml', plan)
            self.write_yaml(root, 'specs/coordination/active-work.yaml', registry)
            self.write_text(root, 'specs/tasks/GZ-014.md', self.task_spec(entry, 'review', entry['branch'], activation))
            reviewed = self.commit(root, 'GZ-014 side Review against actual main (#24)')
            spec = importlib.util.spec_from_file_location('side_review_history', SCRIPT)
            history = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(history)
            errors = []
            history.historical_registration_context(root, reviewed, reviewed, 'GZ-014', registry, sources['reservation'], registry['policy'], 'Legal side Review', errors)
            self.assertEqual(errors, [])
            self.assertNotEqual(entry['baseSha'], work)
            raw = subprocess.run([sys.executable, os.path.join(REPO_ROOT, 'scripts/check-program-lifecycle-guards.py'), '--repo-root', root, '--base-ref', activation, '--head-ref', reviewed, '--task', 'GZ-014', '--branch-name', entry['branch']], capture_output=True, text=True)
            self.assertEqual(raw.returncode, 0, raw.stdout + raw.stderr)

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



    def followup_owner_capacity_fixture(self, case):
        # Real Git fixtures only: fixture dates test exact boundaries and are
        # never timestamps or PASS claims for a published implementation.
        facts = json.loads(pathlib.Path(REPO_ROOT, "evidence/OPS-004/followup-event-facts.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(prefix="guize-followup-capacity-") as temporary:
            root = os.path.join(temporary, "repo")
            subprocess.run(["git", "clone", "--shared", "--no-checkout", "--quiet", "--", REPO_ROOT, root], check=True, capture_output=True)
            base = "413a6a4dd91b5d79a3d2b7d1e5f03f8121848170" if case == "missing_anchor" else facts["anchor"]
            subprocess.run(["git", "checkout", "--detach", "--quiet", base], cwd=root, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.name", "Fixture"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "fixture@example.com"], cwd=root, check=True)
            def at_anchor(path):
                return subprocess.check_output(["git", "show", facts["anchor"] + ":" + path], cwd=root, text=True)
            registry = yaml.safe_load(at_anchor("specs/coordination/active-work.yaml"))
            plan = yaml.safe_load(at_anchor("specs/coordination/program-plan.yaml"))
            owner = at_anchor("evidence/OPS-004/owner-decision.md")
            document = pathlib.Path(REPO_ROOT, facts["document"]).read_text(encoding="utf-8")
            own = next(item for item in registry["tasks"] if item["taskId"] == "OPS-004")
            other = next(item for item in registry["tasks"] if item["taskId"] == "GZ-005")
            if case == "review":
                own.update(status="review", agentRole="reviewer", branch="chore/OPS-004-followup-review", baseSha=facts["anchor"])
            elif case == "document": document += "\nUnapproved change\n"
            elif case == "original_document": owner += "\nChanged original decision\n"
            elif case == "third_task":
                registry["tasks"].append({**copy.deepcopy(other), "taskId": "OTHER-001", "riskLevel": "medium"})
            elif case == "other_entry": other["status"] = "in_progress"
            elif case == "own_lease": own["lease"]["expiresAt"] = "2026-10-17T13:09:31Z"
            elif case == "own_claims": own["exclusivePaths"].append("backend/**")
            elif case == "policy": registry["policy"]["maxActiveTasks"] = 4
            elif case == "frozen": plan["status"] = "frozen"
            stamp = datetime.fromisoformat(facts["start"].replace("Z", "+00:00"))
            if case == "before_start": stamp -= timedelta(seconds=1)
            elif case == "deadline": stamp = datetime.fromisoformat(facts["deadline"].replace("Z", "+00:00"))
            self.write_yaml(root, "specs/coordination/active-work.yaml", registry)
            # Write exact documents directly; avoid the unrelated generic
            # foundation-fixture rewrite used by older tests.
            self.write_text(root, "specs/coordination/program-plan.yaml", yaml.safe_dump(plan, sort_keys=False, allow_unicode=True))
            self.write_text(root, "evidence/OPS-004/owner-decision.md", owner)
            self.write_text(root, facts["document"], document)
            source = self.commit(root, "Finite followup fixture " + case, stamp.isoformat())
            spec = importlib.util.spec_from_file_location("followup_capacity_fixture", SCRIPT)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            errors = []
            module.historical_capacity(root, "OTHER-001" if case == "other_task" else "OPS-004", registry, registry["policy"], "d0e9e256552f9d1d47fb24d2e5a4530476b19a5f", source, "fixture", errors)
            if case in {"start", "review"}:
                self.assertEqual(errors, [])
                audit = module.AUDITED_OWNER_CAPACITY_FAILURES["fixture"]
                self.assertEqual(audit["event"], facts["event"])
                self.assertEqual(audit["capacityResult"], "FAIL")
                self.assertEqual((audit["highCount"], audit["maxHighRiskTasks"]), (2, 1))
            else:
                self.assertEqual(errors, ["fixture exceeds historical active/high capacity limits"])
                self.assertNotIn("fixture", module.AUDITED_OWNER_CAPACITY_FAILURES)

    def test_foundation_followup_capacity_start(self):
        self.followup_owner_capacity_fixture("start")

    def test_foundation_followup_capacity_review(self):
        self.followup_owner_capacity_fixture("review")

    def test_foundation_followup_capacity_document(self):
        self.followup_owner_capacity_fixture("document")

    def test_foundation_followup_capacity_original_document(self):
        self.followup_owner_capacity_fixture("original_document")

    def test_foundation_followup_capacity_third_task(self):
        self.followup_owner_capacity_fixture("third_task")

    def test_foundation_followup_capacity_other_entry(self):
        self.followup_owner_capacity_fixture("other_entry")

    def test_foundation_followup_capacity_own_lease(self):
        self.followup_owner_capacity_fixture("own_lease")

    def test_foundation_followup_capacity_own_claims(self):
        self.followup_owner_capacity_fixture("own_claims")

    def test_foundation_followup_capacity_policy(self):
        self.followup_owner_capacity_fixture("policy")

    def test_foundation_followup_capacity_frozen(self):
        self.followup_owner_capacity_fixture("frozen")

    def test_foundation_followup_capacity_before_start(self):
        self.followup_owner_capacity_fixture("before_start")

    def test_foundation_followup_capacity_deadline(self):
        self.followup_owner_capacity_fixture("deadline")

    def test_foundation_followup_capacity_missing_anchor(self):
        self.followup_owner_capacity_fixture("missing_anchor")

    def test_foundation_followup_capacity_other_task(self):
        self.followup_owner_capacity_fixture("other_task")


if __name__ == "__main__":
    unittest.main()
