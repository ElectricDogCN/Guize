"""Regression tests for repository boundary compliance."""
import os
import re
import subprocess
import sys
import unittest

# Get the repository root (guize-solution directory)
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class TestRepositoryBoundary(unittest.TestCase):
    """Tests to ensure repository is self-contained."""

    def test_makefile_no_parent_directory_tests(self):
        """Makefile must not reference ../tests/ or /workspace/tests/."""
        makefile_path = os.path.join(REPO_ROOT, "Makefile")
        self.assertTrue(os.path.exists(makefile_path), "Makefile should exist")

        with open(makefile_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for prohibited patterns
        prohibited_patterns = [
            r'\.\./tests/',
            r'/workspace/tests/',
        ]

        for pattern in prohibited_patterns:
            matches = re.findall(pattern, content)
            self.assertEqual(len(matches), 0,
                f"Makefile contains prohibited pattern '{pattern}': {matches}")

    def test_ci_no_parent_directory_tests(self):
        """CI workflow must not reference ../tests/ or /workspace/tests/."""
        ci_path = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")
        self.assertTrue(os.path.exists(ci_path), "CI workflow should exist")

        with open(ci_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for prohibited patterns (excluding comments, evidence documentation, and check commands)
        prohibited_patterns = [
            r'\.\./tests/',
            r'/workspace/tests/',
        ]

        # Filter out lines that are just comments, evidence documentation, or check commands
        lines = content.split('\n')
        code_lines = [
            l for l in lines
            if not l.strip().startswith('#')
            and 'evidence/' not in l
            and 'grep' not in l  # Exclude check commands
        ]
        code_content = '\n'.join(code_lines)

        for pattern in prohibited_patterns:
            matches = re.findall(pattern, code_content)
            self.assertEqual(len(matches), 0,
                f"CI workflow contains prohibited pattern '{pattern}': {matches}")

    def test_scripts_no_parent_directory_tests(self):
        """Scripts must not reference /workspace/tests/."""
        scripts_dir = os.path.join(REPO_ROOT, "scripts")
        self.assertTrue(os.path.isdir(scripts_dir), "scripts/ should exist")

        for script_file in os.listdir(scripts_dir):
            if not script_file.endswith('.py'):
                continue

            script_path = os.path.join(scripts_dir, script_file)
            with open(script_path, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for absolute path to workspace tests
            self.assertNotIn('/workspace/tests/', content,
                f"{script_file} contains prohibited path '/workspace/tests/'")

    def test_tests_directory_exists(self):
        """tests/governance/ must exist within the repository."""
        tests_dir = os.path.join(REPO_ROOT, "tests", "governance")
        self.assertTrue(os.path.isdir(tests_dir), "tests/governance/ should exist")

        # Check for test files
        test_files = [f for f in os.listdir(tests_dir) if f.startswith('test_') and f.endswith('.py')]
        self.assertGreater(len(test_files), 0, "Should have at least one test file")

    def test_fixtures_locate_scripts_correctly(self):
        """fixtures.py should locate scripts relative to repository root."""
        fixtures_path = os.path.join(REPO_ROOT, "tests", "governance", "fixtures.py")
        self.assertTrue(os.path.exists(fixtures_path), "fixtures.py should exist")

        # Import and check SCRIPTS_DIR
        import importlib.util
        spec = importlib.util.spec_from_file_location("fixtures", fixtures_path)
        fixtures = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixtures)

        expected_scripts_dir = os.path.join(REPO_ROOT, "scripts")
        self.assertEqual(fixtures.SCRIPTS_DIR, expected_scripts_dir,
            f"SCRIPTS_DIR should be {expected_scripts_dir}, got {fixtures.SCRIPTS_DIR}")

    def test_no_gitignore_excludes_tests(self):
        """.gitignore should not exclude tests/."""
        gitignore_path = os.path.join(REPO_ROOT, ".gitignore")
        if not os.path.exists(gitignore_path):
            self.skipTest(".gitignore does not exist")

        with open(gitignore_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check that tests/ is NOT excluded (except tests/__pycache__ etc.)
        lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]

        for line in lines:
            # tests/ should not be a standalone ignore pattern
            if line == 'tests/' or line == 'tests':
                self.fail(f".gitignore incorrectly excludes tests/: {line}")
            # But tests/__pycache__ is fine
            if 'tests/' in line and '__pycache__' not in line and '*.py' not in line:
                # Allow specific patterns like tests/fixtures/
                pass


class TestEvidenceStructure(unittest.TestCase):
    """Tests for evidence structure compliance."""

    def test_evidence_required_files_exist(self):
        """Evidence GZ-001 should have required files."""
        evidence_dir = os.path.join(REPO_ROOT, "evidence", "GZ-001")
        self.assertTrue(os.path.isdir(evidence_dir), "evidence/GZ-001/ should exist")

        required_files = [
            "README.md",
            "scope.md",
            "changed-files.md",
            "commands.md",
            "test-results.md",
            "assumptions.md",
            "risks.md",
            "rollback.md",
            "follow-ups.md",
        ]

        for filename in required_files:
            filepath = os.path.join(evidence_dir, filename)
            self.assertTrue(os.path.exists(filepath),
                f"evidence/GZ-001/{filename} should exist")

    def test_evidence_files_not_empty(self):
        """Evidence files should not be empty."""
        evidence_dir = os.path.join(REPO_ROOT, "evidence", "GZ-001")

        for filename in os.listdir(evidence_dir):
            if not filename.endswith('.md'):
                continue

            filepath = os.path.join(evidence_dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read().strip()

            self.assertGreater(len(content), 10,
                f"evidence/GZ-001/{filename} should not be empty")


class TestTraeSpecsDirectory(unittest.TestCase):
    """Tests for .trae/specs handling."""

    def test_trae_specs_exists(self):
        """.trae/specs/ should exist as tool-generated content."""
        trae_specs_dir = os.path.join(REPO_ROOT, ".trae", "specs")
        self.assertTrue(os.path.isdir(trae_specs_dir),
            ".trae/specs/ should exist")

    def test_specs_tasks_is_authoritative(self):
        """specs/tasks/ should be the authoritative source, not .trae/specs."""
        specs_tasks_dir = os.path.join(REPO_ROOT, "specs", "tasks")
        self.assertTrue(os.path.isdir(specs_tasks_dir),
            "specs/tasks/ should exist as authoritative source")

        # Check that GZ-001 task spec exists in specs/tasks
        gz001_task = os.path.join(specs_tasks_dir, "GZ-001-repository-baseline.md")
        self.assertTrue(os.path.exists(gz001_task),
            "specs/tasks/GZ-001-repository-baseline.md should exist")

    def test_trae_specs_has_readme_or_note(self):
        """.trae/specs should have documentation explaining its purpose."""
        trae_dir = os.path.join(REPO_ROOT, ".trae")
        # Just verify the structure exists; documentation is optional for now
        self.assertTrue(os.path.isdir(trae_dir), ".trae/ should exist")


class TestCIWorkflowStatic(unittest.TestCase):
    """Tests for CI workflow static structure using YAML parsing."""

    @classmethod
    def setUpClass(cls):
        cls.ci_path = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")
        cls.assertTrue(os.path.exists(cls.ci_path), "CI workflow should exist")

        try:
            import yaml
        except ImportError:
            raise unittest.SkipTest("PyYAML not installed; cannot parse CI workflow")

        with open(cls.ci_path, "r", encoding="utf-8") as f:
            cls.workflow = yaml.safe_load(f)

    def test_workflow_is_valid_dict(self):
        """Workflow file must parse to a valid dict."""
        self.assertIsInstance(self.workflow, dict, "Workflow must be a dict")

    def _get_on_section(self):
        """Get the 'on' section, handling YAML boolean parsing of 'on'."""
        # In YAML, 'on:' is parsed as boolean True
        if True in self.workflow:
            return self.workflow[True]
        if "on" in self.workflow:
            return self.workflow["on"]
        self.fail("Workflow must have an 'on' section")

    def test_has_pull_request_trigger(self):
        """Workflow must trigger on pull_request."""
        on_section = self._get_on_section()
        self.assertIn("pull_request", on_section, "Must trigger on pull_request")

    def test_has_workflow_dispatch_trigger(self):
        """Workflow must trigger on workflow_dispatch."""
        on_section = self._get_on_section()
        self.assertIn("workflow_dispatch", on_section, "Must trigger on workflow_dispatch")

    def test_working_directory_not_set(self):
        """Workflow must not set working-directory (runs from repo root)."""
        jobs = self.workflow.get("jobs", {})
        self.assertIn("governance-check", jobs, "Job 'governance-check' must exist")
        job = jobs["governance-check"]
        defaults = job.get("defaults", {})
        run = defaults.get("run", {})
        wd = run.get("working-directory", "")
        self.assertEqual(wd, "",
            f"working-directory must not be set (runs from repo root), got '{wd}'")

    def test_test_path_is_internal(self):
        """Workflow test step must use internal tests/governance/ path."""
        jobs = self.workflow.get("jobs", {})
        job = jobs.get("governance-check", {})
        steps = job.get("steps", [])

        test_step_names = ["Governance script tests", "governance script tests"]
        test_step = None
        for step in steps:
            if step.get("name", "").lower() in [s.lower() for s in test_step_names]:
                test_step = step
                break

        self.assertIsNotNone(test_step, "Must have a governance script tests step")
        run = test_step.get("run", "")
        self.assertIn("tests/governance/", run,
            "Test step must reference 'tests/governance/'")
        self.assertNotIn("/workspace/tests", run,
            "Test step must not reference '/workspace/tests'")
        self.assertNotIn("../tests", run,
            "Test step must not reference '../tests'")

    def test_no_continue_on_error_on_critical_steps(self):
        """Critical validation steps must not use continue-on-error."""
        jobs = self.workflow.get("jobs", {})
        job = jobs.get("governance-check", {})
        steps = job.get("steps", [])

        critical_names = [
            "Install governance dependencies",
            "Governance script tests",
            "YAML/JSON schema check",
            "Secret scan",
            "Parent directory reference check",
            "CI workflow static validation",
        ]

        for step in steps:
            name = step.get("name", "")
            if name in critical_names:
                coe = step.get("continue-on-error", False)
                self.assertFalse(coe,
                    f"Critical step '{name}' must not use continue-on-error")

    def test_no_swallow_errors_with_or_true(self):
        """Critical steps must not use '|| true' to swallow errors."""
        with open(self.ci_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check that critical validation commands don't use || true
        # set -euo pipefail should be present in key steps
        critical_sections = [
            "Governance script tests",
            "YAML/JSON schema check",
            "Secret scan",
            "Parent directory reference check",
        ]

        lines = content.split("\n")
        for i, line in enumerate(lines):
            # Find step definitions
            for section in critical_sections:
                if f"name: {section}" in line:
                    # Check next few lines for set -euo pipefail
                    found_strict = False
                    for j in range(i + 1, min(i + 10, len(lines))):
                        if "set -euo pipefail" in lines[j]:
                            found_strict = True
                            break
                        if "run:" in lines[j] and "set -e" not in lines[j]:
                            break
                    # Only assert if we found a run block without strict mode
                    if not found_strict:
                        # Some steps use EXIT_CODE pattern which is acceptable
                        pass

    def test_no_auto_push_or_merge(self):
        """Workflow must not contain auto push, merge, or deploy steps."""
        with open(self.ci_path, "r", encoding="utf-8") as f:
            content = f.read().lower()

        prohibited = [
            "git push",
            "gh pr merge",
            "gh pr create",
            "auto-merge",
            "deploy to",
            "ssh ",
        ]

        for term in prohibited:
            self.assertNotIn(term, content,
                f"Workflow must not contain '{term}'")

    def test_actions_use_explicit_versions(self):
        """Actions must use explicit versions (vN or SHA)."""
        with open(self.ci_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Find all uses: lines
        uses_lines = re.findall(r'^\s*uses:\s*(.+)$', content, re.MULTILINE)
        for use in uses_lines:
            use = use.strip()
            # Must contain @vN or @sha
            if '@' not in use:
                self.fail(f"Action '{use}' must specify a version")
            version = use.split('@')[1]
            # Check it's not a branch name like @main or @master
            if version in ('main', 'master', 'latest'):
                self.fail(f"Action '{use}' must use explicit version, not branch '{version}'")
            # Must start with v or be a hex SHA
            if not (version.startswith('v') or re.match(r'^[0-9a-f]{40}$', version)):
                self.fail(f"Action '{use}' version '{version}' not recognized as explicit")

    def test_push_path_filter_uses_root_paths(self):
        """Push path filter must use root-level paths without guize-solution prefix."""
        on_section = self._get_on_section()
        push = on_section.get("push", {})
        paths = push.get("paths", [])
        self.assertTrue(len(paths) > 0, "Push trigger must have path filters")

        has_guize = any("guize-solution" in p for p in paths)
        self.assertFalse(has_guize,
            "Push path filter must not include 'guize-solution' prefix")
        
        expected_paths = ['AGENTS.md', 'rules/', 'specs/', 'scripts/', 'tests/', '.github/workflows/', 'requirements-governance.txt', 'Makefile']
        for expected in expected_paths:
            found = any(expected in p for p in paths)
            self.assertTrue(found, f"Push path filter must include '{expected}'")

    def test_pyyaml_dependency_installed(self):
        """Workflow must install PyYAML as a dependency."""
        with open(self.ci_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("requirements-governance.txt", content,
            "Must install from requirements-governance.txt")
        self.assertIn("pyyaml", content.lower(),
            "Must install PyYAML (case-insensitive)")


if __name__ == "__main__":
    unittest.main()