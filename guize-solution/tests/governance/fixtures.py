import os
import subprocess


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SCRIPTS_DIR = os.path.join(REPO_ROOT, "scripts")


def write_task_spec(directory, task_id="GZ-001", **kwargs):
    """Write a task spec file to <directory>/specs/tasks/<task_id>.md."""
    fields = {
        "id": task_id,
        "title": "Test Task",
        "titleZh": "测试任务",
        "type": "chore",
        "status": "draft",
        "baseBranch": "main",
        "workBranch": f"{kwargs.get('type', 'chore')}/{task_id}-test",
        "evidencePath": f"evidence/{task_id}",
    }
    for key in list(fields.keys()):
        if key in kwargs:
            fields[key] = kwargs[key]

    front_lines = []
    for k, v in fields.items():
        if v is not None:
            front_lines.append(f"{k}: {v}")

    allowed_scope = kwargs.get("allowed_scope", "- `scripts/*.py`\n- `tests/**`")
    forbidden_scope = kwargs.get("forbidden_scope", "- `deployment/**`")
    acceptance_criteria = kwargs.get("acceptance_criteria", "- [ ] 完成测试\n- [ ] 通过门禁")
    validation_commands = kwargs.get("validation_commands", "```bash\npython -m pytest\n```")

    content = f"""---
{'\n'.join(front_lines)}
---

## 允许范围

{allowed_scope}

## 禁止范围

{forbidden_scope}

## 验收标准

{acceptance_criteria}

## 必须执行的测试

{validation_commands}
"""

    spec_dir = os.path.join(directory, "specs", "tasks")
    os.makedirs(spec_dir, exist_ok=True)
    path = os.path.join(spec_dir, f"{task_id}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def ensure_evidence_dir(directory, task_id="GZ-001"):
    """Create the evidence directory for a task."""
    evidence_dir = os.path.join(directory, "evidence", task_id)
    os.makedirs(evidence_dir, exist_ok=True)
    return evidence_dir


def write_evidence_file(directory, task_id, filename, content):
    """Write a single evidence file."""
    evidence_dir = os.path.join(directory, "evidence", task_id)
    os.makedirs(evidence_dir, exist_ok=True)
    path = os.path.join(evidence_dir, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def init_git_repo(directory, branch="main"):
    """Initialize a git repo with an initial commit on *branch*."""
    subprocess.run(["git", "init"], cwd=directory, check=True, capture_output=True)
    subprocess.run(["git", "checkout", "-b", branch], cwd=directory, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=directory, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=directory, check=True, capture_output=True)
    keep = os.path.join(directory, ".gitkeep")
    with open(keep, "w", encoding="utf-8") as f:
        pass
    subprocess.run(["git", "add", "."], cwd=directory, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=directory, check=True, capture_output=True)


def stage_file(directory, filename, content):
    """Create or overwrite *filename* in *directory* and stage it in git."""
    path = os.path.join(directory, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    subprocess.run(["git", "add", filename], cwd=directory, check=True, capture_output=True)
