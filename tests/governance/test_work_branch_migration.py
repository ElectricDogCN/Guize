"""Real Git histories for the single prospective POC-003 work branch change."""
from datetime import timedelta
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('work_branch_migration_tests',
                                              ROOT/'scripts/work-branch-migration.py')
PROOF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROOF)


class Graph:
    def __init__(self, repo):
        self.repo = repo
        self.clock = PROOF.commit_time(str(repo), 'HEAD')+timedelta(seconds=30)

    def git(self, *args, env=None):
        result = subprocess.run(['git', '-c', 'core.longpaths=true', '-C', str(self.repo), *args],
                                capture_output=True, env=env)
        assert result.returncode == 0, result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace')
        return result.stdout.decode().strip()

    def write(self, path, value):
        target = self.repo/path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value if isinstance(value, bytes) else value.encode())

    def read(self, path):
        return yaml.safe_load((self.repo/path).read_bytes())

    def dump(self, path, value):
        self.write(path, yaml.safe_dump(value, sort_keys=False, allow_unicode=True))

    def environment(self):
        self.clock += timedelta(seconds=2)
        return dict(os.environ, GIT_AUTHOR_DATE=self.clock.isoformat(), GIT_COMMITTER_DATE=self.clock.isoformat(),
                    GIT_LFS_SKIP_SMUDGE='1')

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '--quiet', '-m', message, env=self.environment())
        return self.git('rev-parse', 'HEAD')

    def merge(self, branch, message):
        self.git('merge', '--no-ff', '-m', message, branch, env=self.environment())
        return self.git('rev-parse', 'HEAD')

    def lifecycle(self, status, role, base):
        plan, active = self.read(PROOF.PLAN), self.read(PROOF.ACTIVE)
        next(row for row in plan['foundationTasks'] if row['taskId'] == PROOF.OWNER)['status'] = status
        next(row for row in active['tasks'] if row['taskId'] == PROOF.OWNER).update(
            status=status, agentRole=role, baseSha=base, branch='chore/OPS-019-fixture')
        self.dump(PROOF.PLAN, plan)
        self.dump(PROOF.ACTIVE, active)
        target = 'specs/tasks/OPS-019.md'
        raw = (self.repo/target).read_text(encoding='utf-8')
        for key, value in dict(status=status, agentRole=role, baseSha=base,
                               workBranch='chore/OPS-019-fixture').items():
            raw = re.sub(r'^'+key+r':.*$', key+': '+value, raw, count=1, flags=re.M)
        self.write(target, raw)

    def approval(self, implementation):
        before = PROOF.rows(self.read(PROOF.ACTIVE))[PROOF.TARGET]
        record = dict(schemaVersion=1, kind='conditional_prospective_work_branch_migration',
            authorityTaskId=PROOF.OWNER, taskId=PROOF.TARGET, reservation=PROOF.REGISTRATION,
            implementationCommit=implementation, intentSha256=PROOF.INTENT_SHA256,
            oldBranch=PROOF.OLD, newBranch=PROOF.NEW, originalCreationBase=PROOF.CREATION,
            oldUnmergedCandidate=PROOF.RETIRED[0],
            beforeRegistrySha256=hashlib.sha256(json.dumps(before, sort_keys=True,
                separators=(',', ':'), ensure_ascii=False).encode()).hexdigest(),
            beforeTaskSha256=hashlib.sha256((self.repo/PROOF.TASK).read_bytes()).hexdigest(),
            reviewer='/root/independent_review', approvedAt=(self.clock+timedelta(seconds=1)).isoformat(),
            decision='approved',
            condition='normal_authority_completion_full_ci_capacity_release_and_fresh_main')
        self.write(PROOF.APPROVAL, json.dumps(record, indent=2)+'\n')

    def migrate(self):
        self.write(PROOF.ACTIVE, PROOF.registry_replacement((self.repo/PROOF.ACTIVE).read_bytes()))
        self.write(PROOF.TASK, PROOF.task_replacement((self.repo/PROOF.TASK).read_bytes()))
        return self.commit('POC-003 exact prospective work branch migration')


def clone(source, destination, ref):
    subprocess.run(['git', '-c', 'core.longpaths=true', 'clone', '--shared', '--no-checkout', '--quiet',
                    str(source), str(destination)], check=True, capture_output=True)
    graph = Graph.__new__(Graph)
    graph.repo = destination
    graph.git('config', 'user.name', 'Migration fixture')
    graph.git('config', 'user.email', 'fixture@example.invalid')
    graph.git('config', 'core.autocrlf', 'false')
    existing = subprocess.run(['git', '-C', str(destination), 'rev-parse', '--verify',
                               'refs/heads/migration-fixture-main'], capture_output=True)
    if existing.returncode == 0:
        assert existing.stdout.decode().strip() == graph.git('rev-parse', ref)
        graph.git('checkout', '--quiet', 'migration-fixture-main',
                  env=dict(os.environ, GIT_LFS_SKIP_SMUDGE='1'))
    else:
        graph.git('checkout', '--quiet', '-b', 'migration-fixture-main', ref,
                  env=dict(os.environ, GIT_LFS_SKIP_SMUDGE='1'))
    return Graph(destination)


@pytest.fixture(scope='module')
def completed(tmp_path_factory):
    graph = clone(ROOT, tmp_path_factory.mktemp('migration-authority')/'repo', PROOF.REGISTRATION)
    graph.git('checkout', '-b', 'implementation')
    graph.lifecycle('in_progress', 'implementer', PROOF.REGISTRATION)
    graph.commit('OPS-019 fixture activation')
    for path in PROOF.CLAIMS:
        graph.write(path, (ROOT/path).read_bytes())
    graph.write(PROOF.GRAPH, (ROOT/PROOF.GRAPH).read_bytes())
    graph.commit('OPS-019 nonempty registered fixture implementation (#9001)')
    graph.git('checkout', 'migration-fixture-main')
    implementation = graph.merge('implementation', 'OPS-019 implementation (#9001)')
    graph.git('checkout', '-b', 'review')
    graph.lifecycle('review', 'reviewer', implementation)
    graph.approval(implementation)
    graph.commit('OPS-019 independent normal Review and conditional approval (#9002)')
    graph.git('checkout', 'migration-fixture-main')
    graph.merge('review', 'OPS-019 normal independent Review (#9002)')
    graph.git('checkout', '-b', 'completion')
    graph.lifecycle('completed', 'integrator', graph.git('rev-parse', 'HEAD'))
    plan = graph.read(PROOF.PLAN)
    next(row for row in plan['foundationTasks'] if row['taskId'] == PROOF.OWNER).update(
        completionRef='PR-9001', mergeCommit=implementation)
    graph.dump(PROOF.PLAN, plan)
    active = graph.read(PROOF.ACTIVE)
    active['tasks'] = [row for row in active['tasks'] if row['taskId'] != PROOF.OWNER]
    graph.dump(PROOF.ACTIVE, active)
    graph.commit('OPS-019 normal Completion (#9003)')
    graph.git('checkout', 'migration-fixture-main')
    base = graph.merge('completion', 'OPS-019 normal Completion (#9003)')
    return graph, base, implementation


@pytest.fixture
def graph(completed, tmp_path):
    original, base, _ = completed
    result = clone(original.repo, tmp_path/'repo', base)
    result.base = base
    return result


def test_real_lfs_probe_materialized_and_pointer_tracked():
    assert PROOF.verify_probe(str(ROOT))


def test_normal_authority_is_incomplete_at_real_reservation():
    with pytest.raises(PROOF.MigrationError, match='normally complete and release'):
        PROOF.authority(str(ROOT), PROOF.REGISTRATION)


def test_exact_source_virtual_and_actual_merge_are_one_event(graph):
    graph.git('checkout', '-b', PROOF.NEW)
    head = graph.migrate()
    assert PROOF.validate_range(str(graph.repo), graph.base, head) == {PROOF.TARGET: PROOF.FIELDS}
    for script in ('check-program-plan-transitions.py', 'check-program-plan-history.py'):
        result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts'/script), '--repo-root', str(graph.repo),
            '--base-ref', graph.base, '--head-ref', head, '--task', PROOF.TARGET,
            '--branch-name', PROOF.NEW], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout+result.stderr
    graph.git('checkout', 'migration-fixture-main')
    merged = graph.merge(PROOF.NEW, 'POC-003 ordinary exact-tree merge (#9004)')
    assert PROOF.validate_range(str(graph.repo), graph.base, merged) == {PROOF.TARGET: PROOF.FIELDS}


@pytest.mark.parametrize('mutation', ['wrong-branch', 'lease', 'role', 'code', 'task-only'])
def test_rejects_unapproved_transaction_fields(graph, mutation):
    graph.git('checkout', '-b', PROOF.NEW)
    graph.migrate()
    if mutation == 'wrong-branch':
        graph.write(PROOF.ACTIVE, (graph.repo/PROOF.ACTIVE).read_bytes().replace(PROOF.NEW.encode(), b'chore/POC-003-other'))
        graph.write(PROOF.TASK, (graph.repo/PROOF.TASK).read_bytes().replace(PROOF.NEW.encode(), b'chore/POC-003-other'))
    elif mutation in {'lease', 'role'}:
        registry = graph.read(PROOF.ACTIVE)
        target = PROOF.rows(registry)[PROOF.TARGET]
        if mutation == 'lease':
            target['lease']['expiresAt'] = '2099-01-01T00:00:00Z'
        else:
            target['reviewer'] = '/root'
        graph.dump(PROOF.ACTIVE, registry)
    elif mutation == 'code':
        graph.write('scripts/forbidden-foreign-code.py', '# no\n')
    else:
        graph.write(PROOF.ACTIVE, PROOF.blob(str(graph.repo), graph.base, PROOF.ACTIVE))
    head = graph.commit('Unapproved accompanying change')
    with pytest.raises(PROOF.MigrationError):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_rejects_second_migration_and_restore_reapply(graph):
    graph.git('checkout', '-b', PROOF.NEW)
    first = graph.migrate()
    graph.write(PROOF.ACTIVE, PROOF.blob(str(graph.repo), graph.base, PROOF.ACTIVE))
    graph.write(PROOF.TASK, PROOF.blob(str(graph.repo), graph.base, PROOF.TASK))
    graph.commit('Unapproved restoration')
    head = graph.migrate()
    with pytest.raises(PROOF.MigrationError, match='one-way pair'):
        PROOF.validate_range(str(graph.repo), graph.base, head)
    with pytest.raises(PROOF.MigrationError):
        PROOF.validate_range(str(graph.repo), first, head, graph.base)


def test_rejects_rewritten_prospective_approval(graph):
    record = json.loads((graph.repo/PROOF.APPROVAL).read_bytes())
    record['reviewer'] = '/root'
    graph.write(PROOF.APPROVAL, json.dumps(record)+'\n')
    graph.commit('Invalid approval rewrite')
    head = graph.migrate()
    with pytest.raises(PROOF.MigrationError, match='approval'):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_complete_ancestry_and_original_retired_commit_graph(graph):
    PROOF.verify_retired_graph(str(graph.repo), graph.base)
    assert PROOF.BASE in PROOF.complete_ancestry(str(graph.repo), graph.base)
    # Real Git commit objects, including intermediate delivery ancestors, are
    # sufficient to exercise whole-history exclusion without loading media.
    original = json.loads((graph.repo/PROOF.GRAPH).read_bytes())
    for row in reversed(original['nodes']):
        raw = __import__('base64').b64decode(row['rawBase64'])
        result = subprocess.run(['git', '-C', str(graph.repo), 'hash-object', '-t', 'commit', '-w', '--stdin'],
                                input=raw, capture_output=True, check=True)
        assert result.stdout.decode().strip() == row['sha']
        # rev-list needs trees only for path-limited traversal, not ancestry.
        with pytest.raises(PROOF.MigrationError, match='old large-delivery ancestor'):
            PROOF.complete_ancestry(str(graph.repo), row['sha'])
    graph.write(PROOF.GRAPH, b'{}\n')
    graph.commit('Alter original small graph')
    with pytest.raises(PROOF.MigrationError, match='graph changed'):
        PROOF.verify_retired_graph(str(graph.repo), 'HEAD')


def test_no_branch_change_does_not_load_authority(graph, monkeypatch):
    def forbidden(*args):
        raise AssertionError('unrelated event performed a full authority/ancestry audit')
    monkeypatch.setattr(PROOF, 'authority', forbidden)
    monkeypatch.setattr(PROOF, 'complete_ancestry', forbidden)
    graph.write('evidence/POC-003/unrelated-small-note.txt', 'ordinary own evidence\n')
    head = graph.commit('POC-003 ordinary own evidence')
    assert PROOF.validate_range(str(graph.repo), graph.base, head) == {}


@pytest.mark.parametrize('side_review', [False, True])
def test_rejects_completion_without_preceding_admitted_review(graph, completed, side_review):
    _, _, implementation = completed
    graph.git('checkout', '--detach', implementation)
    graph.git('checkout', '-b', 'direct-completion-main')
    graph.git('checkout', '-b', 'unadmitted-completion-source')
    if side_review:
        graph.lifecycle('review', 'reviewer', implementation)
        graph.approval(implementation)
        graph.commit('OPS-019 Review only on unadmitted side branch')
    graph.lifecycle('completed', 'integrator', implementation)
    plan = graph.read(PROOF.PLAN)
    PROOF.rows(plan, 'foundationTasks')[PROOF.OWNER].update(
        mergeCommit=implementation, completionRef='PR-9001')
    graph.dump(PROOF.PLAN, plan)
    active = graph.read(PROOF.ACTIVE)
    active['tasks'] = [row for row in active['tasks'] if row['taskId'] != PROOF.OWNER]
    graph.dump(PROOF.ACTIVE, active)
    graph.commit('OPS-019 direct Completion candidate')
    graph.git('checkout', 'direct-completion-main')
    head = graph.merge('unadmitted-completion-source', 'OPS-019 direct actual Completion (#9005)')
    with pytest.raises(PROOF.MigrationError, match='preceding independent admitted main Review'):
        PROOF.authority(str(graph.repo), head)


def test_rejects_migration_from_unadmitted_completion_source(graph):
    source = PROOF.parents(str(graph.repo), graph.base)[1]
    graph.git('checkout', '--detach', source)
    graph.git('checkout', '-b', PROOF.NEW)
    head = graph.migrate()
    with pytest.raises(PROOF.MigrationError, match='actual admitted authority Completion'):
        PROOF.validate_range(str(graph.repo), source, head, graph.base)


@pytest.mark.parametrize('protected', [PROOF.INTENT, PROOF.GRAPH, PROOF.APPROVAL])
def test_protected_metadata_rewrite_restore_rejected_without_branch_edit(graph, protected, monkeypatch):
    original = (graph.repo/protected).read_bytes()
    graph.write(protected, b'{}\n')
    graph.commit('Invalid protected metadata rewrite')
    graph.write(protected, original)
    head = graph.commit('Restoration cannot conceal invalid earlier edge')
    def forbidden(*args):
        raise AssertionError('protected metadata check should not perform a full authority audit')
    monkeypatch.setattr(PROOF, 'authority', forbidden)
    with pytest.raises(PROOF.MigrationError, match='[Pp]rotected'):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_pointer_and_corrupted_data_are_not_hydrated_evidence(tmp_path):
    graph = clone(ROOT, tmp_path/'probe-repo', 'HEAD')
    with pytest.raises(PROOF.MigrationError, match='not hydrated'):
        PROOF.verify_probe(str(graph.repo))
    graph.write(PROOF.PROBE, b'wrong materialized bytes')
    with pytest.raises(PROOF.MigrationError, match='not hydrated'):
        PROOF.verify_probe(str(graph.repo))


def test_authority_rejects_side_intent_rewrite_restored_before_treesame_merge(graph):
    graph.git('checkout', '-b', 'invalid-intent-side')
    original = (graph.repo/PROOF.INTENT).read_bytes()
    graph.write(PROOF.INTENT, b'{}\n')
    graph.commit('Invalid original intent side rewrite')
    graph.write(PROOF.INTENT, original)
    graph.commit('Restore original intent before merge')
    graph.git('checkout', 'migration-fixture-main')
    head = graph.merge('invalid-intent-side', 'TREESAME intent side import')
    assert PROOF.blob(str(graph.repo), head, PROOF.INTENT) == original
    with pytest.raises(PROOF.MigrationError, match='rewritten on a source edge'):
        PROOF.authority(str(graph.repo), head)
