import os
import subprocess
import sys
import tempfile
import unittest

from .fixtures import SCRIPTS_DIR, write_task_spec


class TestRenderAgentPrompt(unittest.TestCase):
    def _run(self, tmpdir, template_path, output_path, task_id="GZ-001", branch="chore/GZ-001-test"):
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "render-agent-prompt.py"),
            "--task",
            task_id,
            "--branch",
            branch,
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
            with open(template_path, "w", encoding="utf-8") as handle:
                handle.write("Task: {{TASK_ID}}, Title: {{TASK_TITLE}}, Evidence: {{EVIDENCE_PATH}}")
            output_path = os.path.join(tmpdir, "out.md")
            result = self._run(tmpdir, template_path, output_path)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            with open(output_path, "r", encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("Task: GZ-001", content)
            self.assertIn("Title: Test Task", content)
            self.assertIn("Evidence: evidence/GZ-001", content)

    def test_unknown_template_variables_warn(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir)
            template_path = os.path.join(tmpdir, "template.md")
            with open(template_path, "w", encoding="utf-8") as handle:
                handle.write("Task: {{TASK_ID}}, Unknown: {{UNKNOWN_VAR}}")
            output_path = os.path.join(tmpdir, "out.md")
            result = self._run(tmpdir, template_path, output_path)
            self.assertIn("UNKNOWN_VAR", result.stderr)

    def test_v2_collaboration_variables_render(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            task_id = "GZ-101"
            spec_dir = os.path.join(tmpdir, "specs", "tasks")
            evidence_dir = os.path.join(tmpdir, "evidence", task_id)
            os.makedirs(spec_dir, exist_ok=True)
            os.makedirs(evidence_dir, exist_ok=True)
            with open(os.path.join(evidence_dir, "handoff.md"), "w", encoding="utf-8") as handle:
                handle.write("# Handoff\n")
            task_content = f"""---
schemaVersion: 2
id: {task_id}
title: Coordinated Task
titleZh: 协作任务
type: feat
status: in_progress
baseBranch: main
baseSha: {'a' * 40}
workBranch: feat/{task_id}-test
evidencePath: evidence/{task_id}
issue: 101
workPackage: WP-TEST
taskOwner: owner-a
agentRole: implementer
riskLevel: high
coordinationMode: registry
coordinationGroup: contract
dependsOn: GZ-003
handoffPath: evidence/{task_id}/handoff.md
integrationStrategy: merge
---

## 允许范围

- `contracts/test/**`

## 禁止范围

- `deployment/**`

## 依赖与集成顺序

- 依赖 GZ-003，integrationOrder=1。

## 独占写范围

- `contracts/test/**`

## 共享修改范围

- 无。

## 协作与交接

- Implementer 交给独立 Reviewer。

## 验收标准

- [ ] 完成协作变量渲染。

## 必须执行的测试

```bash
python -m pytest
```
"""
            with open(os.path.join(spec_dir, f"{task_id}.md"), "w", encoding="utf-8") as handle:
                handle.write(task_content)
            template_path = os.path.join(tmpdir, "template.md")
            with open(template_path, "w", encoding="utf-8") as handle:
                handle.write(
                    "Role={{AGENT_ROLE}} Risk={{RISK_LEVEL}} Base={{BASE_SHA}} "
                    "Group={{COORDINATION_GROUP}} Handoff={{HANDOFF_PATH}} "
                    "Exclusive={{EXCLUSIVE_SCOPE}}"
                )
            output_path = os.path.join(tmpdir, "out.md")
            result = self._run(tmpdir, template_path, output_path, task_id, f"feat/{task_id}-test")
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)
            with open(output_path, "r", encoding="utf-8") as handle:
                content = handle.read()
            self.assertIn("Role=implementer", content)
            self.assertIn("Risk=high", content)
            self.assertIn("Base=" + "a" * 40, content)
            self.assertIn("Group=contract", content)
            self.assertIn(f"Handoff=evidence/{task_id}/handoff.md", content)
            self.assertIn("contracts/test/**", content)


if __name__ == "__main__":
    unittest.main()
