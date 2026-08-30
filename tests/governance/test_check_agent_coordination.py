import os
import subprocess
import sys
import tempfile
import unittest

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-agent-coordination.py")
SCHEMA = os.path.join(REPO_ROOT, "specs", "coordination", "active-work.schema.yaml")


def task(
    task_id,
    branch,
    *,
    risk="medium",
    group="g",
    exclusive=None,
    shared=None,
    order=1,
    depends=None,
    expires="2026-09-02T00:00:00Z",
    status="in_progress",
    implementer="agent-a",
    reviewer="agent-b",
):
    return {
        "taskId": task_id,
        "issue": int(task_id.split("-")[1]),
        "title": f"Task {task_id}",
        "status": status,
        "riskLevel": risk,
        "owner": "owner-a",
        "coordinator": "coordinator-a",
        "implementer": implementer,
        "reviewer": reviewer,
        "integrator": "integrator-a",
        "agentRole": "implementer",
        "branch": branch,
        "baseBranch": "main",
        "baseSha": "a" * 40,
        "workPackage": "WP-TEST",
        "programPlan": "specs/coordination/program-plan.yaml",
        "programTaskId": task_id,
        "programWave": "W1",
        "requirementIds": ["REQ-V1-0001"],
        "moduleIds": ["MOD-TEST"],
        "producesContracts": [],
        "consumesContracts": [],
        "coordinationGroup": group,
        "dependsOn": depends or [],
        "exclusivePaths": exclusive or [],
        "sharedPaths": shared or [],
        "handoffPath": f"evidence/{task_id}/handoff.md",
        "integrationStrategy": "merge",
        "integrationOrder": order,
        "lease": {"acquiredAt": "2026-08-29T00:00:00Z", "expiresAt": expires},
    }


class TestAgentCoordination(unittest.TestCase):
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

    def write_yaml(self, root, relative, document):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(document, handle, sort_keys=False, allow_unicode=True)

    def write_text(self, root, relative, text):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def run_script(self, root, registry, task_id="", extra=None):
        self.write_yaml(root, "active-work.yaml", registry)
        command = [
            sys.executable,
            SCRIPT,
            "--repo-root",
            root,
            "--registry",
            "active-work.yaml",
            "--schema",
            SCHEMA,
            "--now",
            "2026-08-30T00:00:00Z",
        ]
        if task_id:
            command += ["--task", task_id]
        if extra:
            command += extra
        return subprocess.run(command, capture_output=True, text=True)

    def write_minimal_specs(self, root, tasks):
        directory = os.path.join(root, "specs", "tasks")
        os.makedirs(directory, exist_ok=True)
        for item in tasks:
            self.write_text(
                root,
                f"specs/tasks/{item['taskId']}.md",
                f"---\nid: {item['taskId']}\n---\n",
            )

    def write_registry_spec(
        self,
        root,
        item,
        *,
        status=None,
        branch=None,
        base_sha=None,
        exclusive=None,
        shared=None,
    ):
        task_id = item["taskId"]
        os.makedirs(os.path.join(root, "evidence", task_id), exist_ok=True)
        self.write_text(root, f"evidence/{task_id}/handoff.md", "# Handoff\n")
        exclusive = item["exclusivePaths"] if exclusive is None else exclusive
        shared = item["sharedPaths"] if shared is None else shared
        exclusive_lines = "\n".join(f"- `{path}`" for path in exclusive) or "- 无。"
        shared_lines = "\n".join(f"- `{path}`" for path in shared) or "- 无。"
        front = {
            "schemaVersion": 2,
            "id": task_id,
            "title": "Registry Task",
            "titleZh": "登记任务",
            "type": "feat",
            "status": status or item["status"],
            "baseBranch": item["baseBranch"],
            "baseSha": base_sha or item["baseSha"],
            "workBranch": branch or item["branch"],
            "evidencePath": f"evidence/{task_id}",
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
        yaml_front = yaml.safe_dump(front, sort_keys=False, allow_unicode=True).rstrip()
        content = (
            f"---\n{yaml_front}\n---\n\n## 独占写范围\n\n{exclusive_lines}\n\n"
            f"## 共享修改范围\n\n{shared_lines}\n"
        )
        self.write_text(root, f"specs/tasks/{task_id}.md", content)

    def init_git(self, root):
        subprocess.run(
            ["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"], cwd=root, check=True
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

    def test_empty_registry_passes(self):
        with tempfile.TemporaryDirectory() as root:
            result = self.run_script(root, self.registry([]))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_exclusive_overlap_fails(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = [
                task("GZ-101", "feat/GZ-101-a", exclusive=["backend/asset/**"]),
                task("GZ-102", "feat/GZ-102-b", exclusive=["backend/asset/domain/**"]),
            ]
            self.write_minimal_specs(root, tasks)
            result = self.run_script(root, self.registry(tasks))
            self.assertIn("Exclusive path conflict", result.stdout)

    def test_high_risk_role_separation_fails(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = [
                task(
                    "GZ-101",
                    "feat/GZ-101-a",
                    risk="high",
                    exclusive=["a/**"],
                    implementer="agent-a",
                    reviewer="agent-a",
                )
            ]
            self.write_minimal_specs(root, tasks)
            result = self.run_script(root, self.registry(tasks))
            self.assertIn("implementer and reviewer must differ", result.stdout)

    def test_expired_lease_fails(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = [
                task(
                    "GZ-101",
                    "feat/GZ-101-a",
                    exclusive=["a/**"],
                    expires="2026-08-29T12:00:00Z",
                )
            ]
            self.write_minimal_specs(root, tasks)
            result = self.run_script(root, self.registry(tasks))
            self.assertIn("lease expired", result.stdout)

    def test_coordinated_shared_paths_pass(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = [
                task(
                    "GZ-101",
                    "feat/GZ-101-a",
                    shared=["contracts/common/**"],
                    group="contract",
                    order=1,
                ),
                task(
                    "GZ-102",
                    "feat/GZ-102-b",
                    shared=["contracts/common/schema/**"],
                    group="contract",
                    order=2,
                ),
            ]
            self.write_minimal_specs(root, tasks)
            result = self.run_script(root, self.registry(tasks))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_dependency_cycle_fails(self):
        with tempfile.TemporaryDirectory() as root:
            tasks = [
                task(
                    "GZ-101",
                    "feat/GZ-101-a",
                    exclusive=["a/**"],
                    depends=["GZ-102"],
                ),
                task(
                    "GZ-102",
                    "feat/GZ-102-b",
                    exclusive=["b/**"],
                    depends=["GZ-101"],
                ),
            ]
            self.write_minimal_specs(root, tasks)
            result = self.run_script(root, self.registry(tasks))
            self.assertIn("dependency graph contains a cycle", result.stdout)

    def test_bootstrap_task_passes_without_registry_entry(self):
        with tempfile.TemporaryDirectory() as root:
            self.write_text(
                root,
                "specs/tasks/GZ-003.md",
                "---\nschemaVersion: 2\nid: GZ-003\ncoordinationMode: bootstrap\n"
                "workBranch: chore/GZ-003-bootstrap\n---\n",
            )
            result = self.run_script(
                root,
                self.registry([]),
                "GZ-003",
                ["--branch-name", "chore/GZ-003-bootstrap"],
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_task_path_claims_must_match_registry(self):
        with tempfile.TemporaryDirectory() as root:
            item = task("GZ-101", "feat/GZ-101-a", exclusive=["backend/a/**"])
            self.write_registry_spec(root, item, exclusive=["backend/b/**"])
            result = self.run_script(root, self.registry([item]), "GZ-101")
            self.assertIn("exclusive path claims do not exactly match", result.stdout)

    def test_unclaimed_changed_file_fails(self):
        with tempfile.TemporaryDirectory() as root:
            self.init_git(root)
            self.write_text(root, "base.txt", "base\n")
            base_sha = self.commit(root, "base")
            subprocess.run(
                ["git", "checkout", "-b", "feat/GZ-101-a"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            item = task("GZ-101", "feat/GZ-101-a", exclusive=["backend/allowed/**"])
            item["baseSha"] = base_sha
            self.write_registry_spec(root, item)
            self.write_text(root, "backend/other/bad.txt", "bad\n")
            self.commit(root, "change")
            result = self.run_script(
                root,
                self.registry([item]),
                "GZ-101",
                [
                    "--base-ref",
                    "main",
                    "--head-ref",
                    "HEAD",
                    "--branch-name",
                    "feat/GZ-101-a",
                ],
            )
            self.assertIn("outside registered path claims", result.stdout)

    def test_stale_branch_fails(self):
        with tempfile.TemporaryDirectory() as root:
            self.init_git(root)
            self.write_text(root, "base.txt", "base\n")
            base_sha = self.commit(root, "base")
            subprocess.run(
                ["git", "checkout", "-b", "feat/GZ-101-a"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            item = task("GZ-101", "feat/GZ-101-a", exclusive=["backend/allowed/**"])
            item["baseSha"] = base_sha
            self.write_registry_spec(root, item)
            self.commit(root, "task")
            subprocess.run(
                ["git", "checkout", "main"], cwd=root, check=True, capture_output=True
            )
            self.write_text(root, "main-new.txt", "new\n")
            self.commit(root, "main advanced")
            subprocess.run(
                ["git", "checkout", "feat/GZ-101-a"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            result = self.run_script(
                root,
                self.registry([item]),
                "GZ-101",
                [
                    "--base-ref",
                    "main",
                    "--head-ref",
                    "HEAD",
                    "--branch-name",
                    "feat/GZ-101-a",
                ],
            )
            self.assertIn("does not contain latest base", result.stdout)

    def completion_repo(self, root, *, second_task=False):
        self.init_git(root)
        item = task(
            "GZ-101",
            "feat/GZ-101-implementation",
            risk="high",
            exclusive=["backend/allowed/**"],
            status="integration",
        )
        base_tasks = [item]
        if second_task:
            base_tasks.append(
                task(
                    "GZ-102",
                    "feat/GZ-102-other",
                    exclusive=["backend/other/**"],
                    status="in_progress",
                )
            )
            self.write_registry_spec(root, base_tasks[1])
        base_registry = self.registry(base_tasks)
        self.write_yaml(
            root, "specs/coordination/active-work.yaml", base_registry
        )
        self.write_yaml(
            root,
            "specs/coordination/program-plan.yaml",
            {"tasks": [{"taskId": "GZ-101", "status": "integration"}]},
        )
        self.write_yaml(
            root,
            "specs/coordination/task-completions.yaml",
            {"records": []},
        )
        self.write_registry_spec(root, item)
        base_sha = self.commit(root, "GZ-101 implementation merged (#40)")
        subprocess.run(
            ["git", "checkout", "-b", "chore/GZ-101-completion"],
            cwd=root,
            check=True,
            capture_output=True,
        )
        current_tasks = base_tasks[1:] if second_task else []
        self.write_yaml(
            root,
            "specs/coordination/active-work.yaml",
            self.registry(current_tasks),
        )
        self.write_yaml(
            root,
            "specs/coordination/program-plan.yaml",
            {"tasks": [{"taskId": "GZ-101", "status": "completed"}]},
        )
        self.write_yaml(
            root,
            "specs/coordination/task-completions.yaml",
            {"records": [{"taskId": "GZ-101"}]},
        )
        self.write_registry_spec(
            root,
            item,
            status="completed",
            branch="chore/GZ-101-completion",
            base_sha=base_sha,
        )
        self.commit(root, "GZ-101 completion metadata (#41)")
        return item, base_sha

    def run_completion(self, root):
        command = [
            sys.executable,
            SCRIPT,
            "--repo-root",
            root,
            "--registry",
            "specs/coordination/active-work.yaml",
            "--schema",
            SCHEMA,
            "--now",
            "2026-08-30T00:00:00Z",
            "--task",
            "GZ-101",
            "--base-ref",
            "main",
            "--head-ref",
            "HEAD",
            "--branch-name",
            "chore/GZ-101-completion",
        ]
        return subprocess.run(command, capture_output=True, text=True)

    def test_completion_metadata_update_passes(self):
        with tempfile.TemporaryDirectory() as root:
            self.completion_repo(root)
            result = self.run_completion(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_completion_requires_all_canonical_files(self):
        with tempfile.TemporaryDirectory() as root:
            self.completion_repo(root)
            subprocess.run(
                [
                    "git",
                    "checkout",
                    "HEAD^",
                    "--",
                    "specs/coordination/task-completions.yaml",
                ],
                cwd=root,
                check=True,
            )
            self.commit(root, "remove completion ledger change")
            result = self.run_completion(root)
            self.assertIn("missing canonical files", result.stdout)

    def test_completion_rejects_unrelated_file(self):
        with tempfile.TemporaryDirectory() as root:
            self.completion_repo(root)
            self.write_text(root, "README.md", "unrelated\n")
            self.commit(root, "unrelated change")
            result = self.run_completion(root)
            self.assertIn("outside registered path claims", result.stdout)

    def test_completion_may_only_remove_own_registry_entry(self):
        with tempfile.TemporaryDirectory() as root:
            self.completion_repo(root, second_task=True)
            with open(
                os.path.join(root, "specs/coordination/active-work.yaml"),
                encoding="utf-8",
            ) as handle:
                current = yaml.safe_load(handle)
            current["tasks"][0]["title"] = "Mutated other task"
            self.write_yaml(root, "specs/coordination/active-work.yaml", current)
            self.commit(root, "mutate other reservation")
            result = self.run_completion(root)
            self.assertIn("may only remove its own", result.stdout)

    def test_completion_requires_prior_reservation(self):
        with tempfile.TemporaryDirectory() as root:
            self.completion_repo(root)
            base = yaml.safe_load(
                subprocess.run(
                    ["git", "show", "main:specs/coordination/active-work.yaml"],
                    cwd=root,
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout
            )
            base["tasks"] = []
            subprocess.run(
                ["git", "checkout", "main"], cwd=root, check=True, capture_output=True
            )
            self.write_yaml(root, "specs/coordination/active-work.yaml", base)
            self.commit(root, "erase prior reservation")
            subprocess.run(
                ["git", "checkout", "chore/GZ-101-completion"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            result = self.run_completion(root)
            self.assertIn("exactly one prior active-work entry", result.stdout)


if __name__ == "__main__":
    unittest.main()
