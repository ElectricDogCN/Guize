"""Cold real validators and real ancestry graphs for equivalent read costs."""
import importlib.util
import os
from pathlib import Path
import re
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "historical_read_cost_fixtures", ROOT / "tests/governance/test_historical_task_snapshot.py")
FIXTURES = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = FIXTURES
SPEC.loader.exec_module(FIXTURES)
git, load_module = FIXTURES.git, FIXTURES.load_module
make_history, mutate_case, state = FIXTURES.make_history, FIXTURES.mutate_case, FIXTURES.state


def compare(root, commit, task, entry, caller="task"):
    before = state(root)
    outcomes = []
    for narrow in (False, True):
        history = load_module(ROOT / "scripts/check-program-plan-history.py", "read_cost_")
        original = history.checkout_task_snapshot
        observed = []

        def checkout(snapshot, revision, identity):
            result = (original(snapshot, revision, identity) if narrow else
                      history.git(snapshot, "checkout", "--detach", "--quiet", revision))
            if result.returncode == 0:
                files = {p.relative_to(snapshot).as_posix() for p in Path(snapshot).rglob("*")
                         if p.is_file() and ".git" not in p.relative_to(snapshot).parts}
                observed.append(dict(head=git(snapshot, "rev-parse", "HEAD"), files=files,
                                     shallow=git(snapshot, "rev-parse", "--is-shallow-repository")))
            return result

        history.checkout_task_snapshot = checkout
        errors = []
        if caller == "task":
            history.historical_task_snapshot(str(root), commit, task, entry, "metadata", errors)
        else:
            history.foundation_reservation(str(root), task, commit, entry, errors)
        errors = [re.sub(r"guize-foundation-task-[A-Za-z0-9_]+", "guize-foundation-task-<TEMP>", x)
                  for x in errors]
        outcomes.append((errors, observed))
    assert outcomes[0][0] == outcomes[1][0]
    assert state(root) == before
    return outcomes


@pytest.mark.parametrize("task", ["OPS-019", "OPS-020", "OPS-021", "OPS-022"])
@pytest.mark.parametrize("status", ["reserved", "review"])
def test_cold_task_validation_uses_only_four_proven_inputs(make_history, task, status):
    root, commit, entry = make_history(task, status)
    dense, narrow = compare(root, commit, task, entry)
    assert dense[0] == narrow[0] == []
    assert "payload/unrelated.bin" in dense[1][0]["files"]
    assert narrow[1] == [dict(head=commit, shallow="false", files={
        "specs/tasks/" + task + ".md", "specs/coordination/program-plan.yaml",
        "specs/coordination/active-work.yaml", entry["handoffPath"]})]


def test_cold_original_reservation_runs_its_real_validator_on_four_inputs(make_history):
    root, commit, entry = make_history("OPS-022")
    dense, narrow = compare(root, commit, "OPS-022", entry, "reservation")
    assert dense[0] == narrow[0] == []
    assert "payload/unrelated.bin" in dense[1][-1]["files"]
    assert narrow[1][-1]["files"] == {
        "specs/tasks/OPS-022.md", "specs/coordination/program-plan.yaml",
        "specs/coordination/active-work.yaml", entry["handoffPath"]}


@pytest.mark.parametrize("caller", ["task", "reservation"])
@pytest.mark.parametrize("case", ["missing-task", "ambiguous-task", "bad-task-schema", "bad-program",
                                  "missing-handoff", "missing-evidence", "wrong-registry-owner"])
def test_new_task_bad_inputs_keep_real_cold_refusals(make_history, caller, case):
    root, commit, entry = make_history("OPS-022", mutation=mutate_case(case))
    dense, narrow = compare(root, commit, "OPS-022", entry, caller)
    assert dense[0] and narrow[0]


@pytest.mark.parametrize("task", ["OPS-019", "OPS-022"])
@pytest.mark.parametrize("shape", ["different-handoff", "filtered", "executable", "missing-active", "duplicate-foundation"])
def test_unproved_inputs_keep_their_previous_checkout_route(make_history, task, shape):
    marker = "evidence/" + task + "/unrelated.bin"

    def mutate(root, path, entry):
        (root / marker).write_text("preserved fallback evidence\n", encoding="utf8")
        if shape == "different-handoff":
            other = "evidence/" + task + "/alternative-handoff.md"
            (root / other).write_text("# Another handoff\n", encoding="utf8")
            path.write_bytes(path.read_bytes().replace(entry["handoffPath"].encode(), other.encode()))
            entry["handoffPath"] = other
        elif shape == "filtered":
            (root / ".gitattributes").write_text("specs/tasks/" + task + ".md filter=unproved\n", encoding="utf8")
        elif shape == "missing-active":
            (root / "specs/coordination/active-work.yaml").unlink()
        elif shape == "duplicate-foundation":
            plan_file = root / "specs/coordination/program-plan.yaml"
            plan = yaml.safe_load(plan_file.read_bytes())
            plan["foundationTasks"].append(dict(plan["foundationTasks"][0]))
            plan_file.write_text(yaml.safe_dump(plan, sort_keys=False), encoding="utf8")

    root, commit, entry = make_history(task, mutation=mutate)
    if shape == "executable":
        git(root, "update-index", "--chmod=+x", "specs/tasks/" + task + ".md")
        git(root, "commit", "--quiet", "-m", "Executable input retains original route")
        commit = git(root, "rev-parse", "HEAD")
    dense, fallback = compare(root, commit, task, entry)
    assert marker in fallback[1][0]["files"]
    # OPS019's old route was bounded; OPS022's old default was dense.
    assert ("payload/unrelated.bin" in fallback[1][0]["files"]) is (task != "OPS-019")
    assert "payload/unrelated.bin" in dense[1][0]["files"]


def test_unknown_canonical_task_stays_dense(make_history):
    root, commit, entry = make_history("OPS-999")
    dense, fallback = compare(root, commit, "OPS-999", entry)
    assert dense[0] == fallback[0] == []
    assert "payload/unrelated.bin" in fallback[1][0]["files"]


@pytest.fixture
def ancestry(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.delenv("GIT_TEMPLATE_DIR", raising=False)
    repo = tmp_path / "ancestry"
    repo.mkdir()
    git(repo, "init", "--quiet")
    git(repo, "config", "user.name", "Ancestry fixture")
    git(repo, "config", "user.email", "fixture@example.invalid")
    git(repo, "checkout", "--quiet", "-b", "main")

    def commit(text):
        (repo / (text + ".txt")).write_text(text, encoding="utf8")
        git(repo, "add", ".")
        git(repo, "commit", "--quiet", "-m", text)
        return git(repo, "rev-parse", "HEAD")

    initial = commit("initial")
    git(repo, "checkout", "--quiet", "-b", "creator")
    creator = commit("creator")
    git(repo, "checkout", "--quiet", "main")
    before = commit("main-work")
    git(repo, "merge", "--no-ff", "--quiet", "-m", "Admit side creator", "creator")
    admitted = git(repo, "rev-parse", "HEAD")
    proof = load_module(ROOT / "scripts/work-branch-migration.py", "ancestor_cost_")
    return repo, proof, initial, creator, before, admitted


@pytest.mark.parametrize("case", ["merged-side", "unmerged-side", "tip", "empty"])
def test_creator_check_matches_real_complete_first_parent_chain(ancestry, case, monkeypatch):
    repo, proof, initial, creator, before, admitted = ancestry
    canonical = proof.chain(str(repo), before if case == "unmerged-side" else admitted)
    if case == "tip":
        creator = admitted
    elif case == "empty":
        canonical = []
    original = any(proof.ancestor(str(repo), creator, node) for node in canonical)
    real_ancestor = proof.ancestor
    calls = []

    def observe(root, left, right):
        calls.append((left, right))
        return real_ancestor(root, left, right)

    monkeypatch.setattr(proof, "ancestor", observe)
    assert proof.creator_in_history(str(repo), creator, canonical) is original
    assert calls == ([(creator, canonical[-1])] if canonical else [])
    if case == "merged-side":
        assert creator not in canonical and original
    if case == "unmerged-side":
        assert not original


def test_creator_check_preserves_real_git_failure(ancestry):
    repo, proof, _, _, _, admitted = ancestry
    with pytest.raises(proof.MigrationError, match="Cannot establish migration ancestry"):
        proof.creator_in_history(str(repo), "f" * 40, proof.chain(str(repo), admitted))
