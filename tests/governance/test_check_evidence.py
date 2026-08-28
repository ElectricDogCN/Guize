import os
import subprocess
import sys
import tempfile
import unittest

from .fixtures import SCRIPTS_DIR, write_evidence_file, write_task_spec


class TestCheckEvidence(unittest.TestCase):
    def _run(self, repo_root, task_id="GZ-001"):
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "check-evidence.py"),
            "--task",
            task_id,
            "--repo-root",
            repo_root,
        ]
        return subprocess.run(cmd, capture_output=True, text=True)

    def _write_support_files(self, tmpdir):
        for name in ["scope.md", "changed-files.md", "assumptions.md", "risks.md", "follow-ups.md"]:
            write_evidence_file(tmpdir, "GZ-001", name, f"# {name}\nGZ-001\n")

    def _write_compatibility_contract(self, tmpdir, missing_mapping=None):
        rows = {
            "summary.md": ("README.md", "历史摘要入口"),
            "commands.txt": ("commands.md", "结构化命令和退出码"),
            "test-results/": ("test-results.md", "治理测试结果"),
            "screenshots/": ("N/A", "本任务无 UI 验收"),
            "api-samples/": ("N/A", "本任务无业务 API"),
            "migration-report/": ("migration.md", "仓库迁移记录"),
            "performance/": ("N/A", "本任务无性能验收"),
            "security/": ("test-results.md", "包含 Secret scan"),
            "rollback-verification/": ("rollback.md", "回滚步骤和验证"),
        }
        if missing_mapping:
            rows.pop(missing_mapping)
        lines = [
            "# Evidence Structure — GZ-001",
            "",
            "| AGENTS.md 规范路径 | GZ-001 兼容引用 | 说明 |",
            "|---|---|---|",
        ]
        for source, (target, reason) in rows.items():
            lines.append(f"| `{source}` | `{target}` | {reason} |" if target != "N/A" else f"| `{source}` | N/A | {reason} |")
        write_evidence_file(tmpdir, "GZ-001", "EVIDENCE-STRUCTURE.md", "\n".join(lines) + "\n")

    def _write_legacy_compatible_bundle(self, tmpdir, missing_mapping=None):
        self._write_support_files(tmpdir)
        write_evidence_file(tmpdir, "GZ-001", "README.md", "# Summary\nGZ-001\n")
        write_evidence_file(
            tmpdir,
            "GZ-001",
            "commands.md",
            "# Commands\nGZ-001\ncommand: python -m pytest\nexit code: 0\n",
        )
        write_evidence_file(tmpdir, "GZ-001", "test-results.md", "# Tests\nGZ-001\ncommand: pytest\nexit code: 0\n")
        write_evidence_file(tmpdir, "GZ-001", "migration.md", "# Migration\nGZ-001\n")
        write_evidence_file(tmpdir, "GZ-001", "rollback.md", "# Rollback\nGZ-001\n```bash\ngit revert HEAD\n```\n")
        self._write_compatibility_contract(tmpdir, missing_mapping=missing_mapping)

    def test_missing_evidence_contract_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir)
            self._write_support_files(tmpdir)
            write_evidence_file(tmpdir, "GZ-001", "README.md", "GZ-001\n")
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Missing canonical evidence", result.stdout)

    def test_explicit_legacy_compatibility_passes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir)
            self._write_legacy_compatible_bundle(tmpdir)
            result = self._run(tmpdir)
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_missing_canonical_mapping_fails(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir)
            self._write_legacy_compatible_bundle(tmpdir, missing_mapping="security/")
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("security/", result.stdout)

    def test_na_mapping_requires_reason(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_task_spec(tmpdir)
            self._write_legacy_compatible_bundle(tmpdir)
            structure = os.path.join(tmpdir, "evidence", "GZ-001", "EVIDENCE-STRUCTURE.md")
            with open(structure, "r", encoding="utf-8") as handle:
                content = handle.read()
            content = content.replace("| `screenshots/` | N/A | 本任务无 UI 验收 |", "| `screenshots/` | N/A | - |")
            with open(structure, "w", encoding="utf-8") as handle:
                handle.write(content)
            result = self._run(tmpdir)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must include a reason", result.stdout)


if __name__ == "__main__":
    unittest.main()
