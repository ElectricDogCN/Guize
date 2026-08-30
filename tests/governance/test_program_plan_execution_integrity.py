import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import yaml


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-program-plan-integrity.py")
SCHEMA = os.path.join(
    REPO_ROOT, "specs", "coordination", "task-completions.schema.yaml"
)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        payload = None
        if self.path.endswith("/issues/20"):
            payload = {"state": "closed"}
        elif self.path.endswith("/branches/main"):
            payload = {"protected": True}
        elif self.path.endswith("/rulesets"):
            payload = [{"id": 1}]
        elif self.path.endswith("/rulesets/1"):
            payload = {
                "id": 1,
                "target": "branch",
                "enforcement": "active",
                "bypass_actors": [],
                "conditions": {
                    "ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}
                },
                "rules": [
                    {
                        "type": "pull_request",
                        "parameters": {
                            "required_approving_review_count": 1,
                            "dismiss_stale_reviews_on_push": True,
                            "require_code_owner_review": True,
                            "required_review_thread_resolution": True,
                        },
                    },
                    {
                        "type": "required_status_checks",
                        "parameters": {
                            "required_status_checks": [{"context": "Governance Checks"}]
                        },
                    },
                    {"type": "deletion"},
                    {"type": "non_fast_forward"},
                ],
            }
        if payload is None:
            self.send_response(404)
            self.end_headers()
            return
        data = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class TestIntegrity(unittest.TestCase):
    def write_yaml(self, root, relative, data):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True)

    def write_text(self, root, relative, text):
        path = os.path.join(root, relative)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def documents(self):
        plan = {
            "sourceOfTruth": "specs/coordination/program-plan.yaml",
            "authority": {
                "requirements": "specs/requirements/product-requirements.md",
                "requirementIndex": "specs/requirements/requirements-index.yaml",
                "moduleOwnership": "specs/designs/module-ownership.yaml",
                "collaborationProtocol": "docs/25-multi-agent-collaboration-protocol.md",
            },
            "foundationTasks": [
                {
                    "taskId": "GZ-014",
                    "title": "Foundation",
                    "status": "in_progress",
                    "completionRef": "ISSUE-17",
                    "mergeCommit": None,
                }
            ],
            "waves": [
                {"id": "W1", "order": 1},
                {"id": "W2", "order": 2},
                {"id": "W3", "order": 3},
            ],
            "tasks": [
                {
                    "taskId": "GZ-004",
                    "title": "Requirements",
                    "kind": "requirements",
                    "status": "planned",
                    "riskLevel": "high",
                    "wave": "W1",
                    "dependsOn": ["GZ-014"],
                    "moduleIds": ["MOD-GOV"],
                    "outputPaths": ["docs/governance/gz004/**"],
                    "sharedPaths": [],
                    "exitGate": "Requirements baseline is independently verified.",
                },
                {
                    "taskId": "GZ-005",
                    "title": "Contract",
                    "kind": "contract",
                    "status": "planned",
                    "riskLevel": "high",
                    "wave": "W2",
                    "dependsOn": ["GZ-004"],
                    "moduleIds": ["MOD-GOV"],
                    "outputPaths": ["docs/governance/gz005/**"],
                    "sharedPaths": [],
                    "exitGate": "Contract baseline is independently verified.",
                },
                {
                    "taskId": "GZ-020",
                    "title": "Release",
                    "kind": "release",
                    "status": "planned",
                    "riskLevel": "critical",
                    "wave": "W3",
                    "dependsOn": ["GZ-005"],
                    "moduleIds": ["MOD-GOV"],
                    "outputPaths": ["docs/governance/release/**"],
                    "sharedPaths": [],
                    "exitGate": "Production release is independently approved.",
                },
            ],
            "externalBlockers": [
                {
                    "id": "BRANCH-PROTECTION",
                    "status": "open",
                    "issue": 20,
                    "requiredFor": ["GZ-020"],
                }
            ],
            "releasePolicy": {"requiredFinalTask": "GZ-020"},
        }
        active = {
            "tasks": [
                {
                    "taskId": "GZ-014",
                    "status": "in_progress",
                    "dependsOn": [],
                    "baseSha": "a" * 40,
                }
            ]
        }
        modules = {
            "modules": [
                {
                    "id": "MOD-GOV",
                    "ownedPaths": ["specs/**", "scripts/**", "docs/governance/**"],
                },
                {"id": "MOD-AI", "ownedPaths": ["backend/ai/**"]},
            ],
            "contractNamespaces": [
                {
                    "id": "CONTRACT-AI",
                    "pattern": "contracts/ai/**",
                    "ownerModule": "MOD-AI",
                    "sharedWriterModules": [],
                }
            ],
        }
        ledger = {
            "$schema": "task-completions.schema.yaml",
            "schemaVersion": 1,
            "sourceOfTruth": "specs/coordination/task-completions.yaml",
            "records": [],
        }
        return plan, active, modules, ledger

    def prepare(self, root, plan, active, modules, ledger):
        self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
        self.write_yaml(root, "specs/coordination/active-work.yaml", active)
        self.write_yaml(root, "specs/designs/module-ownership.yaml", modules)
        self.write_yaml(root, "specs/coordination/task-completions.yaml", ledger)
        target = os.path.join(root, "specs/coordination/task-completions.schema.yaml")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copyfile(SCHEMA, target)
        self.write_task(root, "GZ-014", "in_progress")

    def write_task(self, root, task_id, status, exit_gate=None, folded=False):
        if folded and exit_gate:
            first, rest = exit_gate.split(" ", 1)
            gate = f"exitGate: >-\n  {first}\n  {rest}"
        elif exit_gate is not None:
            gate = f"exitGate: {json.dumps(exit_gate)}"
        else:
            gate = ""
        text = (
            f"---\nschemaVersion: 2\nid: {task_id}\nstatus: {status}\n"
            f"{gate}\n---\n# {task_id}\n"
        )
        self.write_text(root, f"specs/tasks/{task_id}.md", text)

    def run_script(self, root, base_ref="", env=None):
        command = [sys.executable, SCRIPT, "--repo-root", root]
        if base_ref != "DEFAULT":
            command += ["--base-ref", base_ref]
        merged = os.environ.copy()
        if env:
            merged.update(env)
        return subprocess.run(command, capture_output=True, text=True, env=merged)

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

    def complete_gz004(
        self,
        root,
        plan,
        active,
        ledger,
        *,
        merge_message="GZ-004 implementation (#31)",
        reservation_message="GZ-004 reservation (#30)",
    ):
        self.init_git(root)
        reservation = self.commit(root, reservation_message)
        self.write_text(root, "marker.txt", "implementation\n")
        merge = self.commit(root, merge_message)
        task = next(item for item in plan["tasks"] if item["taskId"] == "GZ-004")
        task["status"] = "completed"
        task["dependsOn"] = []
        active["tasks"] = []
        self.write_task(root, "GZ-004", "completed", task["exitGate"])
        self.write_text(root, "evidence/GZ-004/handoff.md", "# Handoff\n")
        ledger["records"] = [
            {
                "taskId": "GZ-004",
                "reservationRef": "PR-30",
                "reservationCommit": reservation,
                "completionRef": "PR-31",
                "mergeCommit": merge,
                "taskSpec": "specs/tasks/GZ-004.md",
                "evidencePath": "evidence/GZ-004",
                "handoffPath": "evidence/GZ-004/handoff.md",
            }
        ]
        self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
        self.write_yaml(root, "specs/coordination/active-work.yaml", active)
        self.write_yaml(root, "specs/coordination/task-completions.yaml", ledger)
        self.commit(root, "GZ-004 completion metadata (#32)")
        return reservation, merge

    def test_current_repository_passes(self):
        result = self.run_script(REPO_ROOT, "origin/main")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_active_task_requires_completed_dependencies(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            item = next(task for task in plan["tasks"] if task["taskId"] == "GZ-005")
            item["status"] = "reserved"
            active["tasks"].append(
                {
                    "taskId": "GZ-005",
                    "status": "reserved",
                    "dependsOn": ["GZ-004"],
                    "baseSha": "a" * 40,
                }
            )
            self.prepare(root, plan, active, modules, ledger)
            self.write_task(root, "GZ-005", "reserved", item["exitGate"])
            result = self.run_script(root)
            self.assertIn("dependency GZ-004 is planned", result.stdout)

    def test_open_blocker_rejects_required_task_activation(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            item = next(task for task in plan["tasks"] if task["taskId"] == "GZ-020")
            item["status"] = "reserved"
            item["dependsOn"] = []
            active["tasks"].append(
                {
                    "taskId": "GZ-020",
                    "status": "reserved",
                    "dependsOn": [],
                    "baseSha": "a" * 40,
                }
            )
            self.prepare(root, plan, active, modules, ledger)
            self.write_task(root, "GZ-020", "reserved", item["exitGate"])
            result = self.run_script(root)
            self.assertIn("external blocker BRANCH-PROTECTION is open", result.stdout)

    def test_foundation_commit_must_match_task_and_pr(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            self.prepare(root, plan, active, modules, ledger)
            self.init_git(root)
            sha = self.commit(root, "GZ-001 foundation (#8)")
            plan["foundationTasks"] = [
                {
                    "taskId": "GZ-002",
                    "title": "Foundation",
                    "status": "completed",
                    "completionRef": "PR-9",
                    "mergeCommit": sha,
                }
            ]
            active["tasks"] = []
            self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
            self.write_yaml(root, "specs/coordination/active-work.yaml", active)
            result = self.run_script(root)
            self.assertIn("does not identify GZ-002", result.stdout)
            self.assertIn("does not identify PR-9", result.stdout)

    def test_shared_path_requires_declared_owner_module(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            item = next(task for task in plan["tasks"] if task["taskId"] == "GZ-004")
            item["sharedPaths"] = ["backend/ai/**"]
            self.prepare(root, plan, active, modules, ledger)
            result = self.run_script(root)
            self.assertIn("sharedPaths claim backend/ai/**", result.stdout)
            self.assertIn("without declaring MOD-AI", result.stdout)

    def test_active_task_exit_gate_must_match_program_plan(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            item = next(task for task in plan["tasks"] if task["taskId"] == "GZ-004")
            item["status"] = "reserved"
            item["dependsOn"] = []
            active["tasks"].append(
                {
                    "taskId": "GZ-004",
                    "status": "reserved",
                    "dependsOn": [],
                    "baseSha": "a" * 40,
                }
            )
            self.prepare(root, plan, active, modules, ledger)
            self.write_task(root, "GZ-004", "reserved", "Different exit gate")
            result = self.run_script(root)
            self.assertIn("exitGate does not match Program Plan", result.stdout)

    def test_authority_paths_are_canonical(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            plan["authority"]["moduleOwnership"] = "README.md"
            self.prepare(root, plan, active, modules, ledger)
            result = self.run_script(root)
            self.assertIn("authority.moduleOwnership must be", result.stdout)

    def test_completed_task_requires_completion_ledger(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            item = next(task for task in plan["tasks"] if task["taskId"] == "GZ-004")
            item["status"] = "completed"
            item["dependsOn"] = []
            self.prepare(root, plan, active, modules, ledger)
            result = self.run_script(root)
            self.assertIn("has no completion ledger record", result.stdout)

    def test_final_task_is_canonical_gz020_release(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            plan["releasePolicy"]["requiredFinalTask"] = "GZ-005"
            self.prepare(root, plan, active, modules, ledger)
            result = self.run_script(root)
            self.assertIn("must be canonical task GZ-020", result.stdout)

    def test_minimal_passes(self):
        with tempfile.TemporaryDirectory() as root:
            docs = self.documents()
            self.prepare(root, *docs)
            result = self.run_script(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_final_release_closure(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            plan["tasks"].insert(
                -1,
                {
                    "taskId": "GZ-006",
                    "title": "Orphan",
                    "kind": "contract",
                    "status": "planned",
                    "riskLevel": "medium",
                    "wave": "W2",
                    "dependsOn": ["GZ-004"],
                    "moduleIds": ["MOD-GOV"],
                    "outputPaths": ["docs/governance/gz006/**"],
                    "sharedPaths": [],
                    "exitGate": "Orphan independently verified.",
                },
            )
            self.prepare(root, plan, active, modules, ledger)
            result = self.run_script(root)
            self.assertIn("does not transitively depend", result.stdout)

    def test_completed_exit_gate(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            self.prepare(root, plan, active, modules, ledger)
            self.complete_gz004(root, plan, active, ledger)
            self.write_task(root, "GZ-004", "completed", "Wrong gate")
            result = self.run_script(root)
            self.assertIn("Task Spec exitGate does not match", result.stdout)

    def test_distinct_identity(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            self.prepare(root, plan, active, modules, ledger)
            reservation, _ = self.complete_gz004(root, plan, active, ledger)
            ledger["records"][0]["completionRef"] = "PR-30"
            ledger["records"][0]["mergeCommit"] = reservation
            self.write_yaml(root, "specs/coordination/task-completions.yaml", ledger)
            result = self.run_script(root)
            self.assertIn("reservationRef and completionRef must differ", result.stdout)
            self.assertIn("reservationCommit and mergeCommit must differ", result.stdout)

    def test_exact_pr_token(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            self.prepare(root, plan, active, modules, ledger)
            self.complete_gz004(
                root, plan, active, ledger, merge_message="GZ-004 implementation (#310)"
            )
            result = self.run_script(root)
            self.assertIn("does not identify PR-31", result.stdout)

    def test_evidence_binding(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            self.prepare(root, plan, active, modules, ledger)
            self.complete_gz004(root, plan, active, ledger)
            ledger["records"][0]["evidencePath"] = "evidence/GZ-005"
            ledger["records"][0]["handoffPath"] = "evidence/GZ-005/handoff.md"
            self.write_yaml(root, "specs/coordination/task-completions.yaml", ledger)
            result = self.run_script(root)
            self.assertIn("evidencePath must be evidence/GZ-004", result.stdout)

    def test_append_only(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            self.prepare(root, plan, active, modules, ledger)
            self.complete_gz004(root, plan, active, ledger)
            subprocess.run(["git", "branch", "base"], cwd=root, check=True)
            ledger["records"][0]["completionRef"] = "PR-99"
            self.write_yaml(root, "specs/coordination/task-completions.yaml", ledger)
            self.commit(root, "mutate ledger")
            result = self.run_script(root, "base")
            self.assertIn("immutable", result.stdout)

    def test_dependency_must_predate_activation(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            self.prepare(root, plan, active, modules, ledger)
            self.init_git(root)
            self.commit(root, "base")
            subprocess.run(
                ["git", "checkout", "-b", "feature"],
                cwd=root,
                check=True,
                capture_output=True,
            )
            gz4 = next(item for item in plan["tasks"] if item["taskId"] == "GZ-004")
            gz4["status"] = "completed"
            gz4["dependsOn"] = []
            gz5 = next(item for item in plan["tasks"] if item["taskId"] == "GZ-005")
            gz5["status"] = "reserved"
            active["tasks"] = [
                {
                    "taskId": "GZ-005",
                    "status": "reserved",
                    "dependsOn": ["GZ-004"],
                    "baseSha": "a" * 40,
                }
            ]
            self.write_yaml(root, "specs/coordination/program-plan.yaml", plan)
            self.write_yaml(root, "specs/coordination/active-work.yaml", active)
            self.write_task(root, "GZ-005", "reserved", gz5["exitGate"])
            result = self.run_script(root, "main")
            self.assertIn("not completed in main", result.stdout)

    def test_resolved_blocker_requires_live_ruleset(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            plan["externalBlockers"][0]["status"] = "resolved"
            self.prepare(root, plan, active, modules, ledger)
            env = {
                "GITHUB_REPOSITORY": "owner/repo",
                "GUIZE_GITHUB_API_URL": "http://127.0.0.1:1",
            }
            result = self.run_script(root, env=env)
            self.assertIn("resolution cannot be verified", result.stdout)

    def test_resolved_blocker_accepts_api_confirmed_ruleset(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            plan["externalBlockers"][0]["status"] = "resolved"
            self.prepare(root, plan, active, modules, ledger)
            server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                env = {
                    "GITHUB_REPOSITORY": "owner/repo",
                    "GUIZE_GITHUB_API_URL": f"http://127.0.0.1:{server.server_port}",
                }
                result = self.run_script(root, env=env)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            finally:
                server.shutdown()
                thread.join()

    def test_folded_yaml_exit_gate(self):
        with tempfile.TemporaryDirectory() as root:
            plan, active, modules, ledger = self.documents()
            gz4 = next(item for item in plan["tasks"] if item["taskId"] == "GZ-004")
            gz4["status"] = "reserved"
            gz4["dependsOn"] = []
            active["tasks"].append(
                {
                    "taskId": "GZ-004",
                    "status": "reserved",
                    "dependsOn": [],
                    "baseSha": "a" * 40,
                }
            )
            self.prepare(root, plan, active, modules, ledger)
            self.write_task(root, "GZ-004", "reserved", gz4["exitGate"], folded=True)
            result = self.run_script(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
