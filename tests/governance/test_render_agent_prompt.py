import os
import subprocess
import sys
import tempfile
import unittest

from .fixtures import SCRIPTS_DIR, write_task_spec


class TestRenderAgentPrompt(unittest.TestCase):
    def _run(self, tmpdir, template_path, output_path):
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "render-agent-prompt.py"),
            "--task",
            "GZ-001",
            "--branch",
            "chore/GZ-001-test",
            "--base",
            "main",
            "--mode",
            "implement",
            "--issue",
            "#1",
            "--output",
            output_path,
            "--template",
            template_path,
            "--specs-dir",
            os.path.join(tmpdir, "specs", "tasks"),
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    def test_prompt_renders_correctly(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir)
            template_path = os.path.join(tmpdir, "template.md")
            with open(template_path, "w", encoding="utf-8") as f:
                f.write("Task: {{TASK_ID}}, Title: {{TASK_TITLE}}, Evidence: {{EVIDENCE_PATH}}")
            output_path = os.path.join(tmpdir, "out.md")
            result = self._run(tmpdir, template_path, output_path)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            with open(output_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("Task: GZ-001", content)
            self.assertIn("Title: Test Task", content)
            self.assertIn("Evidence: evidence/GZ-001", content)

    def test_unknown_template_variables_warn(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir)
            template_path = os.path.join(tmpdir, "template.md")
            with open(template_path, "w", encoding="utf-8") as f:
                f.write("Task: {{TASK_ID}}, Unknown: {{UNKNOWN_VAR}}")
            output_path = os.path.join(tmpdir, "out.md")
            result = self._run(tmpdir, template_path, output_path)
            self.assertIn("UNKNOWN_VAR", result.stderr)


if __name__ == "__main__":
    unittest.main()
