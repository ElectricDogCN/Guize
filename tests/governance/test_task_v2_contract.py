import os
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check-task-file.py")


class TestTaskV2Contract(unittest.TestCase):
    def _write_task(self, root, *, base_sha=None, handoff_path=None, include_handoff=True, risk="medium", implementer="agent-a", reviewer="agent-b"):
        task_id = "GZ-101"
        evidence = os.path.join(root, "evidence", task_id)
        os.makedirs(evidence, exist_ok=True)
        handoff_path = handoff_path or f"evidence/{task_id}/handoff.md"
        if include_handoff:
            full_handoff = os.path.join(root, handoff_path)
            os.makedirs(os.path.dirname(full_handoff), exist_ok=True)
            with open(full_handoff, "w", encoding="utf-8") as handle:
                handle.write("# GZ-101 Handoff\n")

        fields = [
            "schemaVersion: 2",
            f"id: {task_id}",
            "title: Test V2 Task",
            "titleZh: 测试 V2 任务",
            "type: feat",
            "status: in_progress",
            "baseBranch: main",
            f"baseSha: {base_sha or 'a' * 40}",
            "workBranch: feat/GZ-101-test",
            f"evidencePath: evidence/{task_id}",
            "issue: 101",
            "workPackage: WP-TEST",
            "taskOwner: owner-a",
            "coordinator: coordinator-a",
            f"implementer: {implementer}",
            f"reviewer: {reviewer}",
            "integrator: integrator-a",
            "agentRole: implementer",
            f"riskLevel: {risk}",
            "coordinationMode: registry",
            "coordinationGroup: test-group",
            "dependsOn: GZ-003",
            f"handoffPath: {handoff_path}",
            "integrationStrategy: merge",
            "integrationOrder: 1",
            "leaseExpiresAt: 2026-09-02T00:00:00Z",
        ]
        content = "---\n" + "\n".join(fields) + "\n---\n\n" + """
## 允许范围

- `backend/test/**`

## 禁止范围

- `deployment/**`

## 依赖与集成顺序

- 依赖 GZ-003 已合并，integrationOrder=1。

## 独占写范围

- `backend/test/**`

## 共享修改范围

- 无。

## 协作与交接

- Implementer 完成后写入 Handoff，Reviewer 独立审查。

## 验收标准

- [ ] V2 Task Spec 可以通过验证。

## 必须执行的测试

```bash
python -m pytest
```
"""
        spec_dir = os.path.join(root, "specs", "tasks")
        os.makedirs(spec_dir, exist_ok=True)
        with open(os.path.join(spec_dir, f"{task_id}.md"), "w", encoding="utf-8") as handle:
            handle.write(content)
        return task_id

    def _run(self, root, task_id):
        return subprocess.run([sys.executable, SCRIPT, "--repo-root", root, "--task", task_id], capture_output=True, text=True)

    def test_valid_v2_task_passes(self):
        with tempfile.TemporaryDirectory() as root:
            task_id = self._write_task(root)
            result = self._run(root, task_id)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("Legacy Task Spec", result.stdout)

    def test_invalid_base_sha_fails(self):
        with tempfile.TemporaryDirectory() as root:
            task_id = self._write_task(root, base_sha="abc123")
            result = self._run(root, task_id)
            self.assertEqual(result.returncode, 1)
            self.assertIn("baseSha must be a 40-character", result.stdout)

    def test_handoff_outside_evidence_fails(self):
        with tempfile.TemporaryDirectory() as root:
            task_id = self._write_task(root, handoff_path="handoff/GZ-101.md")
            result = self._run(root, task_id)
            self.assertEqual(result.returncode, 1)
            self.assertIn("handoffPath must be inside evidencePath", result.stdout)

    def test_missing_handoff_file_fails(self):
        with tempfile.TemporaryDirectory() as root:
            task_id = self._write_task(root, include_handoff=False)
            result = self._run(root, task_id)
            self.assertEqual(result.returncode, 1)
            self.assertIn("handoffPath does not exist", result.stdout)

    def test_high_risk_same_implementer_reviewer_fails(self):
        with tempfile.TemporaryDirectory() as root:
            task_id = self._write_task(root, risk="high", implementer="agent-a", reviewer="agent-a")
            result = self._run(root, task_id)
            self.assertEqual(result.returncode, 1)
            self.assertIn("different implementer and reviewer", result.stdout)


if __name__ == "__main__":
    unittest.main()
