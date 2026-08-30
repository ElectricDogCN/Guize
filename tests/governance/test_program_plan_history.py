import os
import subprocess
import sys
import tempfile
import unittest

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

    def commit(self, root, message):
        subprocess.run(["git", "add", "."], cwd=root, check=True)
        subprocess.run(
            ["git", "commit", "--allow-empty", "-m", message],
            cwd=root,
            check=True,
            capture_output=True,
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
            "leaseExpiresAt": item["lease"]["expiresAt"],
        }
        return (
            "---\n"
            + yaml.safe_dump(front, sort_keys=False, allow_unicode=True)
            + "---\n\n## 独占写范围\n\n- `docs/test/**`\n\n"
            + "## 共享修改范围\n\n- 无。\n"
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

    def create_foundation_completion(self, root):
        self.init_git(root)
        self.write_text(root, "seed.txt", "seed\n")
        seed = self.commit(root, "seed")
        task_id = "GZ-014"
        entry = self.entry(task_id, seed, "in_progress", "chore/GZ-014-repair")
        plan = {
            "foundationTasks": [
                {
                    "taskId": task_id,
                    "status": "in_progress",
                    "completionRef": "ISSUE-17",
                    "mergeCommit": None,
                }
            ],
            "tasks": [],
        }
        self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
        self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([entry]))
        self.write_yaml(root, "specs/coordination/task-completions.yaml", {"records": []})
        self.write_text(
            root,
            f"specs/tasks/{task_id}.md",
            self.task_spec(entry, "in_progress", entry["branch"], seed),
        )
        self.write_text(root, f"evidence/{task_id}/handoff.md", "# Handoff\n")
        implementation = self.commit(root, "GZ-014 repair (#22)")

        subprocess.run(
            ["git", "checkout", "-b", "chore/GZ-014-completion"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        plan["foundationTasks"][0].update(
            {"status": "completed", "completionRef": "PR-22", "mergeCommit": implementation}
        )
        self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
        self.write_yaml(root, "specs/coordination/active-work.yaml", self.registry([]))
        self.write_text(
            root,
            f"specs/tasks/{task_id}.md",
            self.task_spec(entry, "completed", "chore/GZ-014-completion", implementation),
        )
        self.commit(root, "GZ-014 completion metadata (#23)")

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
