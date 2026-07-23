"""Regression tests for repository root layout compliance."""
import os
import re
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class TestRepositoryRootLayout(unittest.TestCase):
    """Tests to ensure repository root has correct structure after migration."""

    def test_agents_md_exists_at_root(self):
        """AGENTS.md must exist at repository root."""
        path = os.path.join(REPO_ROOT, "AGENTS.md")
        self.assertTrue(os.path.exists(path), "AGENTS.md should exist at repository root")

    def test_makefile_exists_at_root(self):
        """Makefile must exist at repository root."""
        path = os.path.join(REPO_ROOT, "Makefile")
        self.assertTrue(os.path.exists(path), "Makefile should exist at repository root")

    def test_readme_exists_at_root(self):
        """README.md must exist at repository root."""
        path = os.path.join(REPO_ROOT, "README.md")
        self.assertTrue(os.path.exists(path), "README.md should exist at repository root")

    def test_specs_tasks_exists_at_root(self):
        """specs/tasks/ must exist at repository root."""
        path = os.path.join(REPO_ROOT, "specs", "tasks")
        self.assertTrue(os.path.isdir(path), "specs/tasks/ should exist at repository root")

    def test_scripts_exists_at_root(self):
        """scripts/ must exist at repository root."""
        path = os.path.join(REPO_ROOT, "scripts")
        self.assertTrue(os.path.isdir(path), "scripts/ should exist at repository root")

    def test_tests_governance_exists_at_root(self):
        """tests/governance/ must exist at repository root."""
        path = os.path.join(REPO_ROOT, "tests", "governance")
        self.assertTrue(os.path.isdir(path), "tests/governance/ should exist at repository root")

    def test_github_workflows_exists_at_root(self):
        """.github/workflows/governance-gate.yml must exist at repository root."""
        path = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")
        self.assertTrue(os.path.exists(path), ".github/workflows/governance-gate.yml should exist")

    def test_github_issue_template_exists_at_root(self):
        """.github/ISSUE_TEMPLATE/ must exist at repository root."""
        path = os.path.join(REPO_ROOT, ".github", "ISSUE_TEMPLATE")
        self.assertTrue(os.path.isdir(path), ".github/ISSUE_TEMPLATE/ should exist")

    def test_no_guize_solution_github_workflows(self):
        """guize-solution/.github/workflows must NOT exist."""
        path = os.path.join(REPO_ROOT, "guize-solution", ".github", "workflows")
        self.assertFalse(os.path.exists(path), "guize-solution/.github/workflows must not exist")

    def test_no_guize_solution_agents_md(self):
        """guize-solution/AGENTS.md must NOT exist."""
        path = os.path.join(REPO_ROOT, "guize-solution", "AGENTS.md")
        self.assertFalse(os.path.exists(path), "guize-solution/AGENTS.md must not exist")

    def test_no_guize_solution_makefile(self):
        """guize-solution/Makefile must NOT exist."""
        path = os.path.join(REPO_ROOT, "guize-solution", "Makefile")
        self.assertFalse(os.path.exists(path), "guize-solution/Makefile must not exist")

    def test_no_guize_solution_wrapper_directory(self):
        """guize-solution/ wrapper directory must NOT exist."""
        path = os.path.join(REPO_ROOT, "guize-solution")
        self.assertFalse(os.path.exists(path), "guize-solution/ wrapper directory must not exist")

    def test_workflow_no_working_directory_guize_solution(self):
        """Workflow must not contain 'working-directory: guize-solution'."""
        ci_path = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")
        with open(ci_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertNotIn("working-directory: guize-solution", content,
            "Workflow must not set working-directory to guize-solution")

    def test_workflow_checkout_has_full_history(self):
        """Workflow checkout must use fetch-depth: 0 for full Git history."""
        ci_path = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")
        with open(ci_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("fetch-depth: 0", content,
            "Workflow checkout must use fetch-depth: 0")

    def test_workflow_scope_check_uses_main(self):
        """Workflow scope check must reference main branch."""
        ci_path = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")
        with open(ci_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("--base main", content,
            "Workflow scope check must reference main branch")

    def test_workflow_secret_scan_no_always_true(self):
        """Secret scan section must not use '|| true' pattern."""
        ci_path = os.path.join(REPO_ROOT, ".github", "workflows", "governance-gate.yml")
        with open(ci_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        lines = content.split('\n')
        in_secret_scan = False
        found_or_true = False
        
        for line in lines:
            if "name: Secret scan" in line:
                in_secret_scan = True
            elif in_secret_scan and line.strip().startswith('- name:'):
                break
            elif in_secret_scan and "|| true" in line:
                found_or_true = True
                break
        
        self.assertFalse(found_or_true,
            "Secret scan section must not use || true to swallow errors")

    def test_github_config_at_root(self):
        """GitHub configuration files must be at repository root."""
        expected = [
            ".github/workflows/governance-gate.yml",
            ".github/ISSUE_TEMPLATE/agent-task.yml",
            ".github/ISSUE_TEMPLATE/bug.yml",
            ".github/ISSUE_TEMPLATE/feature.yml",
            ".github/ISSUE_TEMPLATE/poc.yml",
            ".github/ISSUE_TEMPLATE/security.yml",
            ".github/ISSUE_TEMPLATE/architecture-decision.yml",
            ".github/pull_request_template.md",
        ]
        for rel_path in expected:
            full_path = os.path.join(REPO_ROOT, rel_path)
            self.assertTrue(os.path.exists(full_path),
                f"{rel_path} should exist at repository root")

    def test_prompts_no_guize_solution_reference(self):
        """Prompt files must not reference guize-solution path."""
        prompts_dir = os.path.join(REPO_ROOT, "prompts")
        for root, dirs, files in os.walk(prompts_dir):
            for f in files:
                if f.endswith('.md'):
                    path = os.path.join(root, f)
                    with open(path, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    self.assertNotIn("guize-solution/", content,
                        f"Prompt {path} must not reference guize-solution/")

    def test_make_verify_executable_from_root(self):
        """make verify must be executable from repository root."""
        makefile_path = os.path.join(REPO_ROOT, "Makefile")
        self.assertTrue(os.path.exists(makefile_path), "Makefile must exist")
        with open(makefile_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("verify:", content, "Makefile must have a verify target")


if __name__ == "__main__":
    unittest.main()