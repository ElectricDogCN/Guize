import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "render-multi-agent-prompt.py"
TEMPLATE = REPO_ROOT / "prompts" / "templates" / "multi-agent-task-execution.md"


class TestRenderMultiAgentPrompt(unittest.TestCase):
    def build_repo(self, root: Path) -> None:
        (root / "rules").mkdir(parents=True)
        (root / "specs" / "tasks").mkdir(parents=True)
        (root / "specs" / "collaboration" / "tasks").mkdir(parents=True)
        (root / "prompts" / "templates").mkdir(parents=True)
        (root / "contracts").mkdir(parents=True)

        (root / "AGENTS.md").write_text("# AGENTS\n\nAuthority rules.\n", encoding="utf-8")
        (root / "rules" / "never-rules.md").write_text(
            "# Never Rules\n\nDo not fabricate.\n", encoding="utf-8"
        )
        (root / "specs" / "collaboration" / "README.md").write_text(
            "# Collaboration\n\nSingle writer.\n", encoding="utf-8"
        )
        shutil.copyfile(TEMPLATE, root / "prompts" / "templates" / TEMPLATE.name)
        (root / "contracts" / "input.yaml").write_text(
            "contract: approved\n", encoding="utf-8"
        )

        task_id = "GZ-200"
        (root / "specs" / "tasks" / f"{task_id}.md").write_text(
            f"""---
id: {task_id}
title: Render test
titleZh: 渲染测试
type: chore
status: approved
baseBranch: main
workBranch: chore/{task_id}-render
evidencePath: evidence/{task_id}
coordinationMode: multi-agent
ownerRole: implementation-agent
reviewRole: independent-review-agent
baseCommit: {'a' * 40}
coordinationPath: specs/collaboration/tasks/{task_id}.yaml
handoffPath: evidence/{task_id}/handoff.md
dependsOn: GZ-001
---

# Task
""",
            encoding="utf-8",
        )
        descriptor = {
            "taskId": task_id,
            "mode": "multi-agent",
            "status": "active",
            "baseCommit": "a" * 40,
            "roles": {
                "owner": "implementation-agent",
                "reviewer": "independent-review-agent",
                "integrator": "integration-agent",
            },
            "dependencies": ["GZ-001"],
            "paths": {"exclusive": ["backend/module/**"], "shared": ["README.md"]},
            "contracts": {
                "inputs": ["contracts/input.yaml"],
                "outputs": ["backend/module/**"],
            },
            "integration": {
                "order": 100,
                "mergePolicy": "contract-first",
                "rebasePolicy": "revalidate-on-base-change",
            },
            "handoff": {
                "required": True,
                "path": f"evidence/{task_id}/handoff.md",
            },
        }
        (root / "specs" / "collaboration" / "tasks" / f"{task_id}.yaml").write_text(
            yaml.safe_dump(descriptor, sort_keys=False), encoding="utf-8"
        )

    def run_renderer(self, root: Path, role: str = None):
        output = root / "out.md"
        command = [
            sys.executable,
            str(SCRIPT),
            "--task",
            "GZ-200",
            "--repo-root",
            str(root),
            "--output",
            str(output),
        ]
        if role:
            command.extend(["--role", role])
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        return result, output

    def test_owner_prompt_contains_repository_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_repo(root)
            result, output = self.run_renderer(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            text = output.read_text(encoding="utf-8")
            self.assertIn("implementation-agent", text)
            self.assertIn("backend/module/**", text)
            self.assertIn('context path="AGENTS.md"', text)
            self.assertIn('context path="contracts/input.yaml"', text)
            self.assertIn("NOT AVAILABLE", text)
            self.assertNotIn("{{", text)

    def test_declared_reviewer_role_can_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_repo(root)
            result, output = self.run_renderer(root, "independent-review-agent")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("independent-review-agent", output.read_text(encoding="utf-8"))

    def test_undeclared_role_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.build_repo(root)
            result, output = self.run_renderer(root, "unknown-agent")
            self.assertEqual(result.returncode, 2)
            self.assertFalse(output.exists())
            self.assertIn("not declared", result.stderr)


if __name__ == "__main__":
    unittest.main()
