"""One actual OPS-011 implementation source, fifteen gates, no publication or POC run."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET

import yaml

PYTHON = "/home/sur/.cache/guize-takeover/governance-venv/bin/python"
REPOSITORY = "/home/sur/.cache/guize-takeover/ops011-scope-verification-4d38068"
BASE = "39afaf007d800bab43d7703ac082df2bbc7e8e87"
BRANCH = "chore/OPS-011-agent-edge-104-scope"
IMPLEMENTATION = "chore/OPS-011-agent-edge-104-scope"
AUTHORING = Path(__file__).resolve().parent / "gz021-hls-publication-worktree"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def utc():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def main():
    global SOURCE, TREE, PARENT
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("repo", "source", "tree", "parent", "base", "branch", "output"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    require(sys.platform.startswith("linux") and sys.executable == PYTHON, "Use the existing native governance venv")
    require(args.base == BASE and args.parent == "20366b0546c09a2ec776ab801f8efa2aea45713f" and args.branch == BRANCH and args.source not in {BASE, args.parent}, "Implementation regression successor requires sole parent at 203 and the unchanged accepted actual main base")
    require(all(re.fullmatch(r"[0-9a-f]{40}", value) for value in (args.source, args.tree, args.parent)), "Actual source, tree and parent must be immutable Git identities")
    SOURCE, TREE, PARENT = args.source, args.tree, args.parent
    repo, output = Path(args.repo), Path(args.output)
    require(repo.is_absolute() and str(repo.resolve()) == REPOSITORY, "Unexpected native repository")
    repo = repo.resolve()
    require(output.is_absolute(), "Output must be an absolute new directory")
    output = output.resolve()
    require(not output.exists() and output != repo and repo not in output.parents and output != AUTHORING and AUTHORING not in output.parents, "Output exists or is within an authoring/verification repository")
    filesystem = subprocess.check_output(["stat", "-f", "-c", "%T", str(repo)], text=True).strip()
    temporary_filesystem = subprocess.check_output(["stat", "-f", "-c", "%T", "/tmp"], text=True).strip()
    require(filesystem not in {"v9fs", "9p", "drvfs"} and temporary_filesystem not in {"v9fs", "9p", "drvfs"}, "Repository and test temporary files must use native filesystems")

    def git_at(where, *arguments):
        prefix = ["/mnt/c/Program Files/Git/cmd/git.exe", "-C", str(where).replace("/mnt/c/", "C:/")] if where == AUTHORING else ["git", "-C", str(where)]
        return subprocess.check_output([*prefix, "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false", *arguments], env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})

    def git(*arguments):
        return git_at(repo, *arguments)

    def text_at(where, *arguments):
        return git_at(where, *arguments).decode("utf-8").strip()

    physical_paths = ("specs/tasks/OPS-011.md", "specs/coordination/program-plan.yaml", "specs/coordination/active-work.yaml", "evidence/OPS-011/agent-edge-104-first-use.json", "evidence/OPS-011/commands.txt")

    def snapshot():
        result = {}
        for label, where in (("authoring", AUTHORING), ("verification", repo)):
            physical = {}
            for path in physical_paths:
                raw = (where / path).read_bytes()
                require(raw.replace(b"\r\n", b"\n") == git_at(where, "show", SOURCE + ":" + path), "Physical source blob differs: " + label + "/" + path)
                physical[path] = {"sha256": sha(raw), "canonicalLfSha256": sha(raw.replace(b"\r\n", b"\n"))}
            result[label] = {"path": str(where), "source": text_at(where, "rev-parse", "HEAD"), "tree": text_at(where, "rev-parse", "HEAD^{tree}"), "parent": text_at(where, "show", "-s", "--format=%P", "HEAD"), "branch": text_at(where, "branch", "--show-current"), "main": text_at(where, "rev-parse", "refs/heads/main"), "status": text_at(where, "status", "--porcelain=v1", "--untracked-files=all"), "physicalFiles": physical}
        return result

    before = snapshot()
    for label, point in before.items():
        require((point["source"], point["tree"], point["parent"], point["branch"], point["main"], point["status"]) == (SOURCE, TREE, PARENT, BRANCH, BASE, ""), "Source/sole-parent/branch/main/clean preflight failed: " + label)
    for path in physical_paths:
        require((repo / path).read_bytes().replace(b"\r\n", b"\n") == git("show", SOURCE + ":" + path), "Physical file differs from source blob: " + path)
    task = (repo / "specs/tasks/OPS-011.md").read_text(encoding="utf-8")
    require(task.startswith("---\n"), "Task front matter missing")
    front = yaml.safe_load(task.split("---", 2)[1])
    plan = yaml.safe_load((repo / "specs/coordination/program-plan.yaml").read_bytes())
    active = yaml.safe_load((repo / "specs/coordination/active-work.yaml").read_bytes())
    rows = [row for row in plan["foundationTasks"] if row["taskId"] == "OPS-011"]
    entries = [row for row in active["tasks"] if row["taskId"] == "OPS-011"]
    require(len(rows) == len(entries) == 1 and rows[0]["status"] == "in_progress" and rows[0]["completionRef"] == "ISSUE-108" and rows[0]["mergeCommit"] is None, "Own implementation Foundation identity differs")
    entry = entries[0]
    require(front["schemaVersion"] == 2 and front["id"] == "OPS-011" and front["issue"] == entry["issue"] == 108 and front["baseSha"] == entry["baseSha"] == BASE, "Task/Registry source identity differs")
    require(front["status"] == entry["status"] == "in_progress" and front["agentRole"] == entry["agentRole"] == "implementer" and front["wave"] == entry["programWave"] == "FOUNDATION", "Implementation role/phase differs")
    require(front["workBranch"] == entry["branch"] == IMPLEMENTATION, "Task/Registry implementation claim differs from the approved reservation identity")
    original_inputs = git("show", BASE + ":evidence/OPS-011/reservation-inputs.json")
    require(sha(original_inputs) == "1f9f8589d296cd72e012ce580b318aa1837344bba42535a604a7b9d045a33677", "Original fifteen-claim input differs")
    claims = json.loads(original_inputs)["reservationInputs"]["exclusivePaths"] + ["scripts/check-program-plan-history.py"]
    require(len(entry["exclusivePaths"]) == len(set(entry["exclusivePaths"])) == 16 and set(entry["exclusivePaths"]) == set(claims) and entry["sharedPaths"] == [], "Exact sixteen implementation claims differ")
    prior_registry = yaml.safe_load(git("show", BASE + ":specs/coordination/active-work.yaml"))
    prior = [row for row in prior_registry["tasks"] if row["taskId"] == "OPS-011"]
    require(len(prior) == 1 and {k: v for k, v in entry.items() if k not in {"baseSha", "status", "agentRole"}} == {k: v for k, v in prior[0].items() if k not in {"baseSha", "status", "agentRole"}}, "Implementation changes stable reservation identity, lease or assigned roles")
    for path in ("specs/coordination/task-completions.yaml", "evidence/OPS-011/agent-edge-104-first-use.json"):
        require(git("show", SOURCE + ":" + path) == git("show", BASE + ":" + path), "Implementation changes protected Ledger/declaration bytes: " + path)
    require(sha(git("show", SOURCE + ":evidence/OPS-011/agent-edge-104-first-use.json")) == "2815479d0d322abc8afdf94e73518f0b9a0fa23fbcc0a5bd39c9e9daaa6017d9", "Original first-use declaration differs")

    common = ["--base-ref", BASE, "--head-ref", "HEAD", "--task", "OPS-011", "--branch-name", BRANCH]
    checks = {
        "diff": ["git", "diff", "--check", BASE + "...HEAD"],
        "task": ["python", "scripts/check-task-file.py", "--task", "OPS-011"],
        "readiness": ["python", "scripts/check-project-readiness.py"],
        "schemas": ["python", "scripts/check-schemas.py"],
        "integrity": ["python", "scripts/check-program-plan-integrity.py", "--base-ref", BASE],
        "history": ["python", "scripts/check-program-plan-history.py", *common],
        "transitions": ["python", "scripts/check-program-plan-transitions.py", *common],
        "finalization": ["python", "scripts/check-program-plan-finalization.py", "--base-ref", BASE, "--head-ref", "HEAD", "--task", "OPS-011"],
        "raw-lifecycle": ["python", "scripts/check-program-lifecycle-guards.py", *common],
        "lifecycle": ["python", "scripts/run-program-lifecycle-gate.py", *common],
        "coordination": ["python", "scripts/run-agent-coordination-gate.py", *common],
        "scope": ["python", "scripts/run-task-scope-gate.py", "--task", "OPS-011", "--base", BASE],
        "evidence": ["python", "scripts/check-evidence.py", "--task", "OPS-011"],
        "verify": ["make", "verify", "TASK=OPS-011", "BASE=" + BASE, "HEAD_REF=HEAD", "BRANCH=" + BRANCH],
        "docs": ["python", "scripts/check-markdown.py"],
    }
    expected_commands = list(checks.values())
    command_text = (repo / "evidence/OPS-011/commands.txt").read_text(encoding="utf-8")
    evidence_commands = [shlex.split(line) for line in command_text.splitlines() if line.startswith(("git ", "python ", "make "))]
    blocks = re.findall(r"```bash\n(.*?)\n```", task, re.S)
    require(len(blocks) == 1, "Task must contain exactly the approved command block")
    task_commands = [shlex.split(line) for line in blocks[0].splitlines() if line.strip()]
    require(len(checks) == 15 and evidence_commands == task_commands == expected_commands, "Published Task/Evidence commands differ from the exact fifteen argv")
    require(snapshot() == before, "Source changed during preflight")
    output.mkdir(parents=True, exist_ok=False)
    save(output / "execution-entry.json", {"kind": "OPS011_IMPLEMENTATION_FIFTEEN_GATES_ENTRY", "source": SOURCE, "tree": TREE, "soleParent": PARENT, "base": BASE, "branch": BRANCH, "taskImplementationBranch": IMPLEMENTATION, "scopeStage": "implementation", "exclusivePaths": entry["exclusivePaths"], "pid": os.getpid(), "argv": [sys.executable, *sys.argv], "startedAt": utc(), "scriptSha256": sha(Path(__file__).read_bytes()), "nativeFilesystemType": filesystem, "temporaryFilesystemType": temporary_filesystem, "executionRepoBefore": before, "commands": checks, "parentExecutionNotTransferred": True, "executionAccepted": False})
    os.environ.update(PATH=str(Path(PYTHON).parent) + ":" + os.environ["PATH"], PYTHONDONTWRITEBYTECODE="1", GITHUB_REPOSITORY="ElectricDogCN/Guize", GITHUB_HEAD_REF=BRANCH, PYTEST_ADDOPTS="--junitxml=" + str(output / "make-governance.xml"))
    from live_github_transport import start_bridge
    start_bridge(output)
    status, executions = {}, []
    save(output / "status.json", status)
    for label, command in checks.items():
        raw_path = output / (label + ".txt")
        row = {"label": label, "argv": command, "cwd": str(repo), "startedAt": utc(), "rawLog": raw_path.name}
        with raw_path.open("x", encoding="utf-8", buffering=1) as log:
            log.write("Source Commit: " + SOURCE + "\nCommand: " + shlex.join(command) + "\n")
            log.flush()
            os.fsync(log.fileno())
            process = subprocess.Popen(command, cwd=repo, stdout=log, stderr=subprocess.STDOUT, text=True)
            row["pid"] = process.pid
            executions.append(row)
            save(output / "command-executions.json", executions)
            code = process.wait()
            row.update(exitCode=code, waitCompleted=True, completedAt=utc())
            log.write("\nExit Code: " + str(code) + "\n")
            log.flush()
            os.fsync(log.fileno())
        raw = raw_path.read_bytes()
        row.update(rawSha256=sha(raw), rawByteCount=len(raw))
        save(output / "command-executions.json", executions)
        status[label] = code
        save(output / "status.json", status)
        print(label + ": exit " + str(code), flush=True)
        if code:
            after = snapshot()
            save(output / "failed-gate-worktrees.json", {"source": SOURCE, "tree": TREE, "base": BASE, "failedGate": label, "exitCode": code, "observedAt": utc(), "executionRepoBefore": before, "executionRepoAfter": after, "unchanged": before == after, "requiredCurrentGatesPassed": False})
            return code
    xml_path = output / "make-governance.xml"
    doc = ET.parse(xml_path).getroot()
    cases = list(doc.iter("testcase"))
    count = len(cases)
    require(count > 0 and all(int(suite.get(key, "0")) == 0 for suite in doc.iter("testsuite") for key in ("failures", "errors", "skipped")), "Governance JUnit is empty or has failures/errors/skips")
    require(not any(case.find(key) is not None for case in cases for key in ("failure", "error", "skipped")), "Governance testcase is not successful")
    passed = re.findall(r"\b([0-9]+) passed(?:, [^\r\n]*?)? in [0-9.]+s\b", (output / "verify.txt").read_text(encoding="utf-8"))
    require(passed == [str(count)], "Actual make verify passed count does not match the nonempty JUnit")
    after = snapshot()
    require(before == after and len(status) == 15 and set(status.values()) == {0}, "Source changed or fifteen current gates did not all pass")
    save(output / "verification-worktrees.json", {"kind": "OPS011_IMPLEMENTATION_FIFTEEN_REQUIRED_CURRENT_GATES", "source": SOURCE, "tree": TREE, "soleParent": PARENT, "base": BASE, "branch": BRANCH, "taskImplementationBranch": IMPLEMENTATION, "scopeStage": "implementation", "exclusivePaths": entry["exclusivePaths"], "executionRepoBefore": before, "executionRepoAfter": after, "allCleanBeforeAndAfter": True, "checks": status, "commandExecutions": executions, "governanceTests": count, "currentExecutionFailuresErrorsSkips": 0, "governanceJunit": {"path": xml_path.name, "sha256": sha(xml_path.read_bytes()), "byteCount": xml_path.stat().st_size}, "requiredCurrentGatesPassed": True, "parentExecutionNotTransferred": True, "currentSourceCiAccepted": False, "formalSourceAccepted": False, "actualMainAccepted": False, "runtimeAccepted": False, "fullV1Complete": False})
    print("OPS-011 implementation: fifteen current commands passed; actual governance JUnit " + str(count) + " cases, zero failures/errors/skips. CI and independent acceptance remain pending.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
