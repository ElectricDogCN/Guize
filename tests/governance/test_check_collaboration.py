import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check-collaboration.py"
SCHEMA = REPO_ROOT / "specs" / "collaboration" / "task-coordination.schema.yaml"


class CollaborationFixture:
    task_id = "GZ-100"

    def __init__(self, root: Path):
        self.root = root
        self._run_git("init")
        self._run_git("config", "user.email", "test@example.invalid")
        self._run_git("config", "user.name", "Guize Test")
        (root / "AGENTS.md").write_text("# Rules\n", encoding="utf-8")
        schema_dir = root / "specs" / "collaboration"
        schema_dir.mkdir(parents=True)
        shutil.copyfile(SCHEMA, schema_dir / "task-coordination.schema.yaml")
        self._run_git("add", ".")
        self._run_git("commit", "-m", "baseline")
        self.base_commit = self._git_output("rev-parse", "HEAD")
        self.write_valid_task()
        self.write_valid_descriptor()
        self.write_valid_handoff()
        owned = root / "owned" / "result.txt"
        owned.parent.mkdir(parents=True)
        owned.write_text("result\n", encoding="utf-8")
        self.commit("valid task")

    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args], cwd=self.root, capture_output=True, text=True, check=True
        )

    def _git_output(self, *args: str) -> str:
        return self._run_git(*args).stdout.strip()

    def commit(self, message: str) -> None:
        self._run_git("add", ".")
        self._run_git("commit", "-m", message)

    @property
    def task_path(self) -> Path:
        return self.root / "specs" / "tasks" / f"{self.task_id}.md"

    @property
    def descriptor_path(self) -> Path:
        return (
            self.root
            / "specs"
            / "collaboration"
            / "tasks"
            / f"{self.task_id}.yaml"
        )

    @property
    def handoff_path(self) -> Path:
        return self.root / "evidence" / self.task_id / "handoff.md"

    def write_valid_task(self, reviewer: str = "review-agent", base: str = None) -> None:
        self.task_path.parent.mkdir(parents=True, exist_ok=True)
        base_commit = base or self.base_commit
        self.task_path.write_text(
            f"""---
id: {self.task_id}
title: Test collaboration
titleZh: 测试协作
type: chore
status: approved
baseBranch: main
workBranch: chore/{self.task_id}-test
evidencePath: evidence/{self.task_id}
coordinationMode: multi-agent
ownerRole: owner-agent
reviewRole: {reviewer}
baseCommit: {base_commit}
coordinationPath: specs/collaboration/tasks/{self.task_id}.yaml
handoffPath: evidence/{self.task_id}/handoff.md
dependsOn: GZ-001
---

# Task

## 允许范围

- `owned/**`

## 禁止范围

- `forbidden/**`

## 验收标准

- [ ] valid

## 必须执行的测试

```bash
python scripts/check-collaboration.py --task {self.task_id} --base HEAD~1
```
""",
            encoding="utf-8",
        )

    def descriptor(self, reviewer: str = "review-agent", base: str = None) -> dict:
        return {
            "taskId": self.task_id,
            "mode": "multi-agent",
            "status": "active",
            "workstream": "WS-TEST",
            "baseCommit": base or self.base_commit,
            "roles": {
                "owner": "owner-agent",
                "reviewer": reviewer,
                "integrator": "integration-agent",
            },
            "dependencies": ["GZ-001"],
            "paths": {
                "exclusive": [
                    "owned/**",
                    f"specs/tasks/{self.task_id}.md",
                    f"specs/collaboration/tasks/{self.task_id}.yaml",
                    f"evidence/{self.task_id}/**",
                ],
                "shared": [],
            },
            "contracts": {"inputs": ["AGENTS.md"], "outputs": ["owned/**"]},
            "integration": {
                "order": 100,
                "mergePolicy": "contract-first",
                "rebasePolicy": "revalidate-on-base-change",
            },
            "handoff": {
                "required": True,
                "path": f"evidence/{self.task_id}/handoff.md",
            },
        }

    def write_descriptor(self, descriptor: dict) -> None:
        self.descriptor_path.parent.mkdir(parents=True, exist_ok=True)
        self.descriptor_path.write_text(
            yaml.safe_dump(descriptor, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )

    def write_valid_descriptor(self, reviewer: str = "review-agent", base: str = None) -> None:
        self.write_descriptor(self.descriptor(reviewer=reviewer, base=base))

    def write_valid_handoff(self) -> None:
        self.handoff_path.parent.mkdir(parents=True, exist_ok=True)
        self.handoff_path.write_text(
            """# Handoff

## Baseline

- base

## Delivered Outputs

- output

## Validation

- command executed

## Integration Notes

- order

## Known Gaps

- none

## Rollback

- revert
""",
            encoding="utf-8",
        )

    def run_checker(self, *extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--task",
                self.task_id,
                "--base",
                self.base_commit,
                "--repo-root",
                str(self.root),
                *extra,
            ],
            capture_output=True,
            text=True,
            check=False,
        )


class TestCheckCollaboration(unittest.TestCase):
    def test_valid_coordination_contract_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = CollaborationFixture(Path(tmp))
            result = fixture.run_checker()
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("Collaboration contract passed", result.stdout)

    def test_owner_and_reviewer_must_differ(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = CollaborationFixture(Path(tmp))
            fixture.write_valid_task(reviewer="owner-agent")
            fixture.write_valid_descriptor(reviewer="owner-agent")
            result = fixture.run_checker("--skip-diff")
            self.assertEqual(result.returncode, 1)
            self.assertIn("Owner and final reviewer", result.stdout)

    def test_missing_handoff_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = CollaborationFixture(Path(tmp))
            fixture.handoff_path.unlink()
            result = fixture.run_checker("--skip-diff")
            self.assertEqual(result.returncode, 1)
            self.assertIn("Handoff file does not exist", result.stdout)

    def test_invalid_base_commit_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = CollaborationFixture(Path(tmp))
            invalid = "f" * 40
            fixture.write_valid_task(base=invalid)
            fixture.write_valid_descriptor(base=invalid)
            result = fixture.run_checker("--skip-diff")
            self.assertEqual(result.returncode, 1)
            self.assertIn("baseCommit does not exist", result.stdout)

    def test_undeclared_changed_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = CollaborationFixture(Path(tmp))
            path = fixture.root / "outside" / "unexpected.txt"
            path.parent.mkdir(parents=True)
            path.write_text("unexpected\n", encoding="utf-8")
            fixture.commit("out of coordination scope")
            result = fixture.run_checker()
            self.assertEqual(result.returncode, 1)
            self.assertIn("outside coordination path ownership", result.stdout)

    def test_active_exclusive_path_overlap_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = CollaborationFixture(Path(tmp))
            other = fixture.descriptor()
            other["taskId"] = "GZ-101"
            other["baseCommit"] = fixture.base_commit
            other["roles"]["owner"] = "other-owner"
            other["paths"] = {"exclusive": ["owned/**"], "shared": []}
            other["handoff"] = {
                "required": False,
                "path": "evidence/GZ-101/handoff.md",
            }
            other_path = (
                fixture.root
                / "specs"
                / "collaboration"
                / "tasks"
                / "GZ-101.yaml"
            )
            other_path.write_text(
                yaml.safe_dump(other, sort_keys=False), encoding="utf-8"
            )
            result = fixture.run_checker("--skip-diff")
            self.assertEqual(result.returncode, 1)
            self.assertIn("Exclusive path conflict with GZ-101", result.stdout)


if __name__ == "__main__":
    unittest.main()
