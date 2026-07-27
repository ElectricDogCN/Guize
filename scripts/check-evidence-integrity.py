#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Tuple, Optional

def run_command(cmd: List[str], cwd: str = None) -> Tuple[int, str, str]:
    try:
        result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

def find_commits_in_report(report_path: str) -> List[str]:
    commits = []
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
        sha_pattern = re.compile(r'\b([0-9a-f]{7,40})\b')
        for match in sha_pattern.finditer(content):
            commits.append(match.group(1))
    except Exception as e:
        print(f"Error reading report: {e}")
    return commits

def verify_commit_exists(sha: str, cwd: str = None) -> bool:
    rc, _, _ = run_command(["git", "cat-file", "-e", f"{sha}^{{commit}}"], cwd=cwd)
    return rc == 0

def verify_commit_reachable(sha: str, cwd: str = None) -> bool:
    rc, _, _ = run_command(["git", "merge-base", "--is-ancestor", sha, "HEAD"], cwd=cwd)
    return rc == 0

def get_current_head(cwd: str = None) -> str:
    rc, stdout, _ = run_command(["git", "rev-parse", "HEAD"], cwd=cwd)
    return stdout if rc == 0 else ""

def get_git_status(cwd: str = None) -> str:
    rc, stdout, _ = run_command(["git", "status", "--porcelain"], cwd=cwd)
    return stdout if rc == 0 else ""

def check_report_head(report_path: str) -> Optional[str]:
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'verifiedHead:\s*([0-9a-f]{40})', content)
        if match:
            return match.group(1)
    except Exception:
        pass
    return None

def check_remote_pushed_claim(report_path: str) -> bool:
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "remotePushed: true" in content:
            return True
    except Exception:
        pass
    return False

def verify_remote_contains(sha: str, remote: str = "origin", cwd: str = None) -> bool:
    rc, stdout, _ = run_command(["git", "branch", "-a", "--contains", sha], cwd=cwd)
    if rc != 0:
        return False
    remote_branches = [b for b in stdout.splitlines() if remote + "/" in b]
    return len(remote_branches) > 0

def main():
    parser = argparse.ArgumentParser(description="Check evidence integrity for governance reports")
    parser.add_argument("--task", required=True, help="Task ID")
    parser.add_argument("--report", required=True, help="Path to evidence report")
    parser.add_argument("--cwd", default=None, help="Working directory")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    results: Dict = {"task": args.task, "report": args.report, "valid": True, "errors": [], "warnings": [], "checks": []}
    cwd = args.cwd or os.getcwd()

    if not os.path.exists(args.report):
        results["valid"] = False
        results["errors"].append(f"Report file not found: {args.report}")
        print(json.dumps(results, indent=2, ensure_ascii=False))
        sys.exit(1)

    current_head = get_current_head(cwd)
    report_head = check_report_head(args.report)
    git_status = get_git_status(cwd)
    is_clean = len(git_status) == 0

    results["currentHead"] = current_head
    results["reportHead"] = report_head
    results["workspaceClean"] = is_clean
    results["gitStatus"] = git_status

    if report_head:
        if report_head == current_head:
            passed = True
            detail = "Report head matches current HEAD"
        elif verify_commit_exists(report_head, cwd):
            passed = True
            detail = f"Report head exists in git database"
        else:
            passed = False
            detail = f"Report head does not exist in git database"
        results["checks"].append({"name": "reportHeadValid", "passed": passed, "detail": detail})
        if not passed:
            results["valid"] = False
            results["errors"].append(detail)

    commits = find_commits_in_report(args.report)
    results["commitsFound"] = len(commits)
    results["commits"] = []

    for sha in commits:
        exists = verify_commit_exists(sha, cwd)
        reachable = verify_commit_reachable(sha, cwd) if exists else False
        commit_result = {"sha": sha, "exists": exists, "reachable": reachable}
        results["commits"].append(commit_result)
        if not exists:
            results["valid"] = False
            results["errors"].append(f"Commit {sha} does not exist")
        if exists and not reachable:
            results["warnings"].append(f"Commit {sha} exists but not reachable (may be amended)")

    if check_remote_pushed_claim(args.report):
        for commit in results["commits"]:
            if commit["exists"]:
                remote_contains = verify_remote_contains(commit["sha"], cwd=cwd)
                commit["remoteContains"] = remote_contains
                if not remote_contains:
                    results["valid"] = False
                    results["errors"].append(f"Report claims pushed but commit {commit['sha']} is not in remote")

    claims_clean = False
    try:
        with open(args.report, "r", encoding="utf-8") as f:
            content = f.read()
            if "工作区干净" in content or "workspace clean" in content.lower():
                claims_clean = True
    except Exception:
        pass

    if claims_clean and not is_clean:
        results["valid"] = False
        results["errors"].append("Report claims workspace is clean but git status shows changes")

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(f"Evidence Integrity Check for {args.task}")
        print(f"Current HEAD: {current_head}")
        print(f"Report HEAD: {report_head or 'NOT FOUND'}")
        print(f"Workspace Clean: {is_clean}")
        print(f"Commits Found: {len(commits)}")
        for commit in results["commits"]:
            status = "OK" if commit["exists"] else "MISSING"
            print(f"  {commit['sha']}: {status}")
        if results["errors"]:
            print("ERRORS:")
            for err in results["errors"]:
                print(f"  - {err}")
        if results["warnings"]:
            print("WARNINGS:")
            for warn in results["warnings"]:
                print(f"  - {warn}")
        print(f"Overall: {'PASS' if results['valid'] else 'FAIL'}")

    sys.exit(0 if results["valid"] else 1)

if __name__ == "__main__":
    main()
