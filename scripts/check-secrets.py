#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys

def run_grep(pattern, repo_root):
    cmd = ["git", "grep", "-n", "-E", pattern, "--", ":(exclude)*test*.py", ":(exclude)*tests/*"]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=repo_root)
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

def main():
    parser = argparse.ArgumentParser(description="Scan for common secret patterns")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()
    repo_root = os.path.abspath(args.repo_root)

    high_risk_patterns = [
        ("AWS Access Key", r"AKIA[0-9A-Z]{16}"),
        ("GitHub Token", r"ghp_[a-zA-Z0-9]{36}"),
        ("Stripe Key", r"sk-[a-zA-Z0-9]{20,}"),
        ("Google API Key", r"AIza[0-9A-Za-z_-]{35}"),
        ("Private Key", r"BEGIN (RSA |DSA |EC |OPENSSH )?PRIVATE KEY"),
    ]

    results = {"highRisk": [], "mediumRisk": [], "errors": [], "valid": True}

    for name, pattern in high_risk_patterns:
        rc, stdout, stderr = run_grep(pattern, repo_root)
        if rc == 0 and stdout:
            for line in stdout.splitlines():
                results["highRisk"].append({"pattern": name, "line": line.strip()})
            results["valid"] = False
        elif rc > 1:
            results["errors"].append(f"grep error for '{name}': {stderr}")

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        if results["highRisk"]:
            print("HIGH RISK SECRETS FOUND:")
            for item in results["highRisk"]:
                print(f"  - {item['pattern']}: {item['line']}")
        if results["errors"]:
            print("ERRORS:")
            for err in results["errors"]:
                print(f"  - {err}")
        if results["valid"]:
            print("OK: No high-risk secrets detected")
        else:
            print("FAIL: High-risk secrets detected")

    sys.exit(0 if results["valid"] else 1)

if __name__ == "__main__":
    main()
