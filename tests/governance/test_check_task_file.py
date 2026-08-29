import os
import subprocess
import sys
import tempfile
import unittest

from .fixtures import SCRIPTS_DIR, ensure_evidence_dir, write_task_spec


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


class TestCheckTaskFile(unittest.TestCase):
    def _run(self, repo_root, task_id="GZ-001"):
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "check-task-file.py"),
            "--task",
            task_id,
            "--repo-root",
            repo_root,
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    def _copy_registry_task(self, root, transform=None):
        source = os.path.join(REPO_ROOT, "specs", "tasks", "GZ-014.md")
        with open(source, "r", encoding="utf-8") as handle:
            text = handle.read()
        if transform:
            text = transform(text)
        target = os.path.join(root, "specs", "tasks", "GZ-014.md")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8") as handle:
            handle.write(text)
        evidence = os.path.join(root, "evidence", "GZ-014")
        os.makedirs(evidence, exist_ok=True)
        with open(os.path.join(evidence, "handoff.md"), "w", encoding="utf-8") as handle:
            handle.write("# Handoff\n")

    def test_valid_task_file_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir)
            ensure_evidence_dir(tmpdir)
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_missing_task_id_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir, id=None)
            ensure_evidence_dir(tmpdir)
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)

    def test_invalid_branch_name_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir, workBranch="feature/invalid-branch")
            ensure_evidence_dir(tmpdir)
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)

    def test_empty_acceptance_section_fails_even_if_other_checklist_exists(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_task_spec(tmpdir, acceptance_criteria="")
            ensure_evidence_dir(tmpdir)
            with open(path, "a", encoding="utf-8") as handle:
                handle.write("\n## 其他清单\n\n- [ ] unrelated\n")
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Acceptance criteria section", result.stdout)

    def test_empty_validation_commands_fail(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir, validation_commands="```bash\n```")
            ensure_evidence_dir(tmpdir)
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Validation commands section", result.stdout)

    def test_registry_v2_requires_program_plan_identity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._copy_registry_task(
                tmpdir,
                transform=lambda text: text.replace(
                    "programPlan: specs/coordination/program-plan.yaml\n",
                    "",
                    1,
                ),
            )
            result = self._run(tmpdir, "GZ-014")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing or empty registry coordination field: programPlan", result.stdout)

    def test_registry_v2_requires_valid_requirement_ids(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._copy_registry_task(
                tmpdir,
                transform=lambda text: text.replace(
                    "requirementIds: REQ-V1-0010",
                    "requirementIds: REQUIREMENT-10",
                    1,
                ),
            )
            result = self._run(tmpdir, "GZ-014")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Invalid requirementIds entry", result.stdout)

    def test_registry_v2_program_task_id_must_match_task_id(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self._copy_registry_task(
                tmpdir,
                transform=lambda text: text.replace(
                    "programTaskId: GZ-014",
                    "programTaskId: GZ-999",
                    1,
                ),
            )
            result = self._run(tmpdir, "GZ-014")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("programTaskId must equal", result.stdout)


if __name__ == "__main__":
    unittest.main()
