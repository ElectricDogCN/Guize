import os
import subprocess
import sys
import unittest

from .test_program_task_registration import RegistrationFixture


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TASK_CHECKER = os.path.join(REPO_ROOT, "scripts", "check-task-file.py")
COORDINATION = os.path.join(REPO_ROOT, "scripts", "run-agent-coordination-gate.py")
SCOPE = os.path.join(REPO_ROOT, "scripts", "run-task-scope-gate.py")


class TestProgramRegistrationDispatch(unittest.TestCase):
    def fixture(self):
        fixture = RegistrationFixture()
        self.addCleanup(fixture.close)
        return fixture

    def run_task_checker(self, fixture):
        return subprocess.run(
            [
                sys.executable,
                TASK_CHECKER,
                "--repo-root",
                fixture.root,
                "--task",
                fixture.task_id,
            ],
            capture_output=True,
            text=True,
        )

    def run_coordination(self, fixture, *extra, env=None):
        return subprocess.run(
            [
                sys.executable,
                COORDINATION,
                "--repo-root",
                fixture.root,
                *extra,
            ],
            capture_output=True,
            text=True,
            env=env,
        )

    def run_scope(self, fixture, *extra):
        return subprocess.run(
            [
                sys.executable,
                SCOPE,
                "--repo-root",
                fixture.root,
                *extra,
            ],
            capture_output=True,
            text=True,
        )

    def test_task_file_accepts_registration_without_lease(self):
        fixture = self.fixture()
        result = self.run_task_checker(fixture)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_task_file_rejects_registration_lease(self):
        fixture = self.fixture()
        fixture.rewrite_task_front(
            lambda document: document.__setitem__(
                "leaseExpiresAt", "2026-10-01T00:00:00Z"
            )
        )
        result = self.run_task_checker(fixture)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not contain leaseExpiresAt", result.stdout)

    def test_task_file_rejects_medium_registration(self):
        fixture = self.fixture()
        fixture.rewrite_task_front(
            lambda document: document.__setitem__("riskLevel", "medium")
        )
        result = self.run_task_checker(fixture)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("high or critical", result.stdout)

    def test_task_file_rejects_registry_planned_alias(self):
        fixture = self.fixture()

        def mutate(document):
            document["coordinationMode"] = "registry"
            document["leaseExpiresAt"] = "2026-10-01T00:00:00Z"

        fixture.rewrite_task_front(mutate)
        result = self.run_task_checker(fixture)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Registry task has invalid status", result.stdout)

    def test_coordination_routes_planned_to_canonical_validator(self):
        fixture = self.fixture()
        result = self.run_coordination(
            fixture,
            "--task",
            fixture.task_id,
            "--base-ref",
            "main",
            "--head-ref",
            "HEAD",
            "--branch-name",
            fixture.branch,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Program Task Registration", result.stdout)
        self.assertNotIn("ordinary coordination", result.stdout)

    def test_coordination_registration_requires_authoritative_branch(self):
        fixture = self.fixture()
        result = self.run_coordination(
            fixture,
            "--task",
            fixture.task_id,
            "--base-ref",
            "main",
            "--head-ref",
            "HEAD",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("authoritative branch", result.stdout)

    def test_scope_routes_planned_to_canonical_validator(self):
        fixture = self.fixture()
        result = self.run_scope(
            fixture,
            "--task",
            fixture.task_id,
            "--base",
            "main",
            "--head-ref",
            "HEAD",
            "--branch-name",
            fixture.branch,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Program Task Registration", result.stdout)
        self.assertNotIn("ordinary scope", result.stdout)

    def test_scope_registration_requires_authoritative_branch(self):
        fixture = self.fixture()
        result = self.run_scope(
            fixture,
            "--task",
            fixture.task_id,
            "--base",
            "main",
            "--head-ref",
            "HEAD",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("authoritative branch", result.stdout)

    def test_no_task_push_coordination_uses_shared_validator(self):
        fixture = self.fixture()
        fixture.merge_to_main()
        env = os.environ.copy()
        env.update(
            {
                "EVENT_NAME": "push",
                "PUSH_BEFORE": fixture.base_sha,
                "GITHUB_REF_NAME": "main",
            }
        )
        result = self.run_coordination(fixture, env=env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Program Task Registration", result.stdout)
        self.assertIn("push/no-task", result.stdout)
        self.assertNotIn("ordinary coordination", result.stdout)

    def test_no_task_direct_push_fails_closed(self):
        fixture = self.fixture()
        fixture.git("checkout", "main")
        fixture.git("merge", "--ff-only", fixture.branch)
        env = os.environ.copy()
        env.update(
            {
                "EVENT_NAME": "push",
                "PUSH_BEFORE": fixture.base_sha,
                "GITHUB_REF_NAME": "main",
            }
        )
        result = self.run_coordination(fixture, env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("two-parent merge", result.stdout)

    def test_registration_script_override_is_absent_from_coordination_cli(self):
        result = subprocess.run(
            [sys.executable, COORDINATION, "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("--registration-script", result.stdout)
        rejected = subprocess.run(
            [sys.executable, COORDINATION, "--registration-script", "fake.py"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("unrecognized arguments", rejected.stderr)

    def test_registration_script_override_is_absent_from_scope_cli(self):
        result = subprocess.run(
            [sys.executable, SCOPE, "--help"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("--registration-script", result.stdout)
        rejected = subprocess.run(
            [
                sys.executable,
                SCOPE,
                "--task",
                "OPS-006",
                "--base",
                "main",
                "--registration-script",
                "fake.py",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(rejected.returncode, 2)
        self.assertIn("unrecognized arguments", rejected.stderr)


if __name__ == "__main__":
    unittest.main()
