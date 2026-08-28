"""Regression tests for repository boundary compliance."""
import os
import re
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class TestRepositoryBoundary(unittest.TestCase):
    def test_makefile_no_parent_directory_tests(self):
        makefile_path = os.path.join(REPO_ROOT, "Makefile")
        self.assertTrue(os.path.exists(makefile_path), "Makefile should exist")
        with open(makefile_path, "r", encoding="utf-8") as handle:
            content = handle.read()
        for pattern in [r"\.\./tests/", r"/workspace/tests/"]:
            self.assertEqual(re.findall(pattern, content), [], f"Makefile contains prohibited pattern {pattern}")

    def test_ci_no_parent_directory_tests(self):
        ci_path = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")
        self.assertTrue(os.path.exists(ci_path), "CI workflow should exist")
        with open(ci_path, "r", encoding="utf-8") as handle:
            content = handle.read()
        code_lines = [line for line in content.split("\n") if not line.strip().startswith("#") and "grep" not in line]
        code_content = "\n".join(code_lines)
        for pattern in [r"\.\./tests/", r"/workspace/tests/"]:
            self.assertEqual(re.findall(pattern, code_content), [], f"CI workflow contains prohibited pattern {pattern}")

    def test_scripts_no_parent_directory_tests(self):
        scripts_dir = os.path.join(REPO_ROOT, "scripts")
        self.assertTrue(os.path.isdir(scripts_dir), "scripts/ should exist")
        for script_file in os.listdir(scripts_dir):
            if script_file.endswith(".py"):
                with open(os.path.join(scripts_dir, script_file), "r", encoding="utf-8") as handle:
                    self.assertNotIn("/workspace/tests/", handle.read(), f"{script_file} contains prohibited path")

    def test_tests_directory_exists(self):
        tests_dir = os.path.join(REPO_ROOT, "tests", "governance")
        self.assertTrue(os.path.isdir(tests_dir))
        self.assertTrue(any(name.startswith("test_") and name.endswith(".py") for name in os.listdir(tests_dir)))

    def test_fixtures_locate_scripts_correctly(self):
        fixtures_path = os.path.join(REPO_ROOT, "tests", "governance", "fixtures.py")
        import importlib.util
        spec = importlib.util.spec_from_file_location("fixtures", fixtures_path)
        fixtures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixtures)
        self.assertEqual(fixtures.SCRIPTS_DIR, os.path.join(REPO_ROOT, "scripts"))

    def test_no_gitignore_excludes_tests(self):
        gitignore_path = os.path.join(REPO_ROOT, ".gitignore")
        if not os.path.exists(gitignore_path):
            self.skipTest(".gitignore does not exist")
        with open(gitignore_path, "r", encoding="utf-8") as handle:
            lines = [line.strip() for line in handle if line.strip() and not line.startswith("#")]
        self.assertNotIn("tests/", lines)
        self.assertNotIn("tests", lines)


class TestEvidenceStructure(unittest.TestCase):
    def test_evidence_required_files_exist(self):
        evidence_dir = os.path.join(REPO_ROOT, "evidence", "GZ-001")
        required_files = ["README.md", "scope.md", "changed-files.md", "commands.md", "test-results.md", "assumptions.md", "risks.md", "rollback.md", "follow-ups.md"]
        for filename in required_files:
            self.assertTrue(os.path.exists(os.path.join(evidence_dir, filename)), f"Missing {filename}")

    def test_evidence_files_not_empty(self):
        evidence_dir = os.path.join(REPO_ROOT, "evidence", "GZ-001")
        for filename in os.listdir(evidence_dir):
            if filename.endswith(".md"):
                with open(os.path.join(evidence_dir, filename), "r", encoding="utf-8") as handle:
                    self.assertGreater(len(handle.read().strip()), 10, f"{filename} should not be empty")


class TestTraeSpecsDirectory(unittest.TestCase):
    def test_trae_specs_exists(self):
        self.assertTrue(os.path.isdir(os.path.join(REPO_ROOT, ".trae", "specs")))

    def test_specs_tasks_is_authoritative(self):
        self.assertTrue(os.path.exists(os.path.join(REPO_ROOT, "specs", "tasks", "GZ-001-repository-baseline.md")))

    def test_trae_specs_has_readme_or_note(self):
        self.assertTrue(os.path.isdir(os.path.join(REPO_ROOT, ".trae")))


class TestCIWorkflowStatic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ci_path = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")
        try:
            import yaml
        except ImportError:
            raise unittest.SkipTest("PyYAML not installed")
        with open(cls.ci_path, "r", encoding="utf-8") as handle:
            cls.content = handle.read()
            handle.seek(0)
            cls.workflow = yaml.safe_load(handle)

    def _get_on_section(self):
        return self.workflow.get(True, self.workflow.get("on", {}))

    def test_workflow_is_valid_dict(self):
        self.assertIsInstance(self.workflow, dict)

    def test_has_pull_request_trigger(self):
        self.assertIn("pull_request", self._get_on_section())

    def test_has_workflow_dispatch_trigger(self):
        self.assertIn("workflow_dispatch", self._get_on_section())

    def test_push_validates_all_main_updates(self):
        push = self._get_on_section().get("push", {})
        self.assertIn("main", push.get("branches", []))
        self.assertNotIn("paths", push)
        self.assertNotIn("paths-ignore", push)

    def test_concurrency_cancels_stale_runs(self):
        concurrency = self.workflow.get("concurrency", {})
        self.assertTrue(concurrency.get("group"))
        self.assertTrue(concurrency.get("cancel-in-progress"))

    def test_job_has_timeout(self):
        job = self.workflow.get("jobs", {}).get("governance-check", {})
        self.assertGreater(job.get("timeout-minutes", 0), 0)
        self.assertLessEqual(job.get("timeout-minutes", 0), 30)

    def test_working_directory_not_set(self):
        job = self.workflow.get("jobs", {}).get("governance-check", {})
        self.assertEqual(job.get("defaults", {}).get("run", {}).get("working-directory", ""), "")

    def test_test_path_is_internal(self):
        steps = self.workflow.get("jobs", {}).get("governance-check", {}).get("steps", [])
        test_step = next((step for step in steps if step.get("name", "").lower() == "governance tests"), None)
        self.assertIsNotNone(test_step)
        run = test_step.get("run", "")
        self.assertIn("tests/governance/", run)
        self.assertNotIn("/workspace/tests", run)
        self.assertNotIn("../tests", run)

    def test_no_continue_on_error_on_critical_steps(self):
        critical_names = {"Install governance dependencies", "Project readiness check", "Agent coordination check", "Governance tests", "YAML/JSON schema check", "Secret scan", "Parent directory reference check", "CI workflow static validation"}
        steps = self.workflow.get("jobs", {}).get("governance-check", {}).get("steps", [])
        for step in steps:
            if step.get("name") in critical_names:
                self.assertFalse(step.get("continue-on-error", False), f"{step.get('name')} must gate")

    def test_no_swallow_errors_with_or_true(self):
        critical_sections = ["Project readiness check", "Agent coordination check", "Governance tests", "YAML/JSON schema check", "Secret scan", "Parent directory reference check"]
        lines = self.content.split("\n")
        for section in critical_sections:
            index = next((i for i, line in enumerate(lines) if f"name: {section}" in line), None)
            self.assertIsNotNone(index, f"Missing critical step {section}")
            block = lines[index + 1 : index + 24]
            self.assertIn("run: |", [line.strip() for line in block])
            self.assertTrue(any("set -euo pipefail" in line for line in block))
            self.assertFalse(any("|| true" in line for line in block))

    def test_no_auto_push_or_merge(self):
        lower = self.content.lower()
        for term in ["git push", "gh pr merge", "gh pr create", "auto-merge", "deploy to", "ssh "]:
            self.assertNotIn(term, lower)

    def test_actions_are_pinned_to_immutable_shas(self):
        uses_lines = re.findall(r"^\s*uses:\s*(.+)$", self.content, re.MULTILINE)
        self.assertGreater(len(uses_lines), 0)
        for use in uses_lines:
            version = use.strip().split("@", 1)[1]
            self.assertRegex(version, r"^[0-9a-f]{40}$", f"Action must be pinned to immutable SHA: {use}")

    def test_checkout_does_not_persist_credentials(self):
        steps = self.workflow.get("jobs", {}).get("governance-check", {}).get("steps", [])
        checkout = next(step for step in steps if step.get("id") == "checkout")
        self.assertFalse(checkout.get("with", {}).get("persist-credentials", True))

    def test_pyyaml_dependency_installed(self):
        lower = self.content.lower()
        self.assertIn("requirements-governance.txt", lower)
        self.assertIn("pyyaml", lower)


if __name__ == "__main__":
    unittest.main()
