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
                                capture_output=True,
                                env=dict(os.environ if env is None else env, GIT_LFS_SKIP_SMUDGE='1'))
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
    # Keep every Git object and ref. Only omit unrelated historical media
    # from fixture worktrees; real P/H CLIs still prove the complete history.
    graph.git('sparse-checkout', 'set', '--no-cone', '/scripts/', '/specs/', '/tests/',
              '/rules/', '/.github/', '/docs/', '/evidence/OPS-019/',
              '/evidence/POC-003/', '/evidence/POC-005/handoff.md',
              '/.gitattributes', '/.gitignore', '/README.md',
              '/requirements-governance.txt', '/Makefile')
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
    assert PROOF.changed(str(graph.repo), graph.base, head) == {PROOF.ACTIVE, PROOF.TASK}
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


@pytest.mark.parametrize('mutation', ['valid', 'malformed-task', 'missing-handoff', 'registry-drift'])
def test_sparse_historical_task_keeps_real_validation(tmp_path, mutation):
    graph = clone(ROOT, tmp_path/'snapshot-source', PROOF.REGISTRATION)
    entry = PROOF.rows(graph.read(PROOF.ACTIVE))[PROOF.OWNER]
    if mutation == 'malformed-task':
        target = 'specs/tasks/OPS-019.md'
        graph.write(target, (graph.repo/target).read_bytes().replace(b'schemaVersion: 2', b'schemaVersion: 99'))
    elif mutation == 'missing-handoff':
        graph.git('rm', 'evidence/OPS-019/handoff.md')
    elif mutation == 'registry-drift':
        # The real linkage validator must reject this proposed entry against
        # the actual historical Task, even though the physical checkout is small.
        entry = dict(entry, reviewer='/root/not-the-registered-reviewer')
    head = PROOF.REGISTRATION if mutation in {'valid', 'registry-drift'} else graph.commit('Invalid historical Task input')
    history = PROOF.history_module()
    errors = []
    history.historical_task_snapshot(str(graph.repo), head, PROOF.OWNER, entry, 'OPS019 real snapshot', errors)
    if mutation == 'valid':
        assert errors == []
    else:
        assert errors
        expected = {'malformed-task': 'schemaVersion', 'missing-handoff': 'handoffPath',
                    'registry-drift': 'does not match'}[mutation]
        assert expected in '\n'.join(errors)


def test_other_task_snapshot_stays_dense(tmp_path):
    repo = tmp_path/'dense-source'
    repo.mkdir()
    def git_at(directory, *args):
        result = subprocess.run(['git', '-C', str(directory), *args], capture_output=True,
                                env=dict(os.environ, GIT_LFS_SKIP_SMUDGE='1'))
        assert result.returncode == 0, result.stderr.decode()
        return result.stdout.decode().strip()
    git_at(repo, 'init', '--quiet')
    git_at(repo, 'config', 'user.name', 'Dense snapshot fixture')
    git_at(repo, 'config', 'user.email', 'fixture@example.invalid')
    evidence = repo/'evidence/OTHER/unrelated.txt'
    evidence.parent.mkdir(parents=True)
    evidence.write_text('must remain in every other task snapshot\n', encoding='utf-8')
    git_at(repo, 'add', '.')
    git_at(repo, 'commit', '--quiet', '-m', 'Original dense snapshot input')
    head = git_at(repo, 'rev-parse', 'HEAD')
    snapshot = tmp_path/'dense-snapshot'
    git_at(repo, 'clone', '--shared', '--no-checkout', '--quiet', str(repo), str(snapshot))
    history = PROOF.history_module()
    result = history.checkout_task_snapshot(str(snapshot), head, 'OPS-017')
    assert result.returncode == 0
    assert git_at(snapshot, 'rev-parse', 'HEAD') == head
    assert (snapshot/'evidence/OTHER/unrelated.txt').read_bytes() == evidence.read_bytes()
    sparse = subprocess.run(['git', '-C', str(snapshot), 'config', '--get', 'core.sparseCheckout'],
                            capture_output=True)
    assert sparse.returncode == 1


class RecoveryGraph(Graph):
    """The second authority starts from its real, separately admitted reservation."""
    def lifecycle(self, status, role, base):
        plan, active = self.read(PROOF.PLAN), self.read(PROOF.ACTIVE)
        next(row for row in plan['foundationTasks'] if row['taskId'] == PROOF.RECOVERY_OWNER)['status'] = status
        next(row for row in active['tasks'] if row['taskId'] == PROOF.RECOVERY_OWNER).update(
            status=status, agentRole=role, baseSha=base, branch='chore/OPS-020-fixture')
        self.dump(PROOF.PLAN, plan)
        self.dump(PROOF.ACTIVE, active)
        target = 'specs/tasks/OPS-020.md'
        raw = (self.repo/target).read_text(encoding='utf-8')
        for key, value in dict(status=status, agentRole=role, baseSha=base,
                               workBranch='chore/OPS-020-fixture').items():
            raw = re.sub(r'^'+key+r':.*$', key+': '+value, raw, count=1, flags=re.M)
        self.write(target, raw)

    def approval_record(self, implementation):
        before = PROOF.rows(self.read(PROOF.ACTIVE))[PROOF.TARGET]
        return dict(schemaVersion=1, kind='conditional_prospective_blocked_work_branch_recovery',
            authorityTaskId=PROOF.RECOVERY_OWNER, taskId=PROOF.TARGET,
            reservation=PROOF.RECOVERY_REGISTRATION, implementationCommit=implementation,
            intentSha256=PROOF.RECOVERY_INTENT_SHA256, oldBranch=PROOF.OLD,
            newBranch=PROOF.RECOVERY_NEW, originalCreationBase=PROOF.CREATION,
            oldUnmergedCandidate=PROOF.RETIRED[0],
            beforeRegistrySha256=hashlib.sha256(json.dumps(before, sort_keys=True,
                separators=(',', ':'), ensure_ascii=False).encode()).hexdigest(),
            beforeTaskSha256=hashlib.sha256((self.repo/PROOF.TASK).read_bytes()).hexdigest(),
            reviewer='/root/independent_review', approvedAt=(self.clock+timedelta(seconds=1)).isoformat(),
            decision='approved',
            condition='normal_authority_completion_full_ci_capacity_release_and_fresh_main')

    def recover(self):
        for path, replace in ((PROOF.ACTIVE, PROOF.recovery_registry_replacement),
                              (PROOF.TASK, PROOF.recovery_task_replacement),
                              (PROOF.PLAN, PROOF.recovery_program_replacement)):
            self.write(path, replace((self.repo/path).read_bytes()))
        handoff = 'evidence/POC-003/handoff.md'
        self.write(handoff, (self.repo/handoff).read_bytes()+b'\n\nFixture exact blocked recovery.\n')
        self.write(PROOF.RECOVERY_PREFIX+'README.md', '# Exact metadata recovery fixture\n')
        return self.commit('POC-003 exact prospective blocked recovery')


def recovery_clone(source, destination, ref):
    result = clone(source, destination, ref)
    assert result.git('config', '--bool', '--get', 'core.sparseCheckoutCone') == 'false'
    result.git('sparse-checkout', 'add', '/evidence/OPS-020/', '/poc/POC-03-ats-range/')
    return RecoveryGraph(destination)


def build_recovery_authority(destination, approval, approval_companion=False):
    graph = recovery_clone(ROOT, destination, PROOF.RECOVERY_REGISTRATION)
    existing = subprocess.run(['git', '-C', str(graph.repo), 'rev-parse', '--verify', 'refs/heads/main'],
                              capture_output=True)
    if existing.returncode == 0:
        # CI push checkouts inherit the current real main, which can be later
        # than the fixed reservation. Preserve it inside this new fixture;
        # construct the synthetic proof on a separate main starting at R.
        backup = subprocess.run(['git', '-C', str(graph.repo), 'rev-parse', '--verify',
                                 'refs/heads/recovery-inherited-main'], capture_output=True)
        assert backup.returncode != 0
        graph.git('branch', '-m', 'main', 'recovery-inherited-main')
        assert graph.git('rev-parse', 'recovery-inherited-main') == existing.stdout.decode().strip()
    graph.git('branch', 'main', PROOF.RECOVERY_REGISTRATION)
    graph.git('checkout', 'main')
    graph.git('checkout', '-b', 'recovery-implementation')
    graph.lifecycle('in_progress', 'implementer', PROOF.RECOVERY_REGISTRATION)
    graph.commit('OPS-020 fixture activation')
    for path in PROOF.RECOVERY_CLAIMS:
        graph.write(path, (ROOT/path).read_bytes())
    graph.commit('OPS-020 nonempty registered implementation (#9101)')
    graph.git('checkout', 'main')
    implementation = graph.merge('recovery-implementation', 'OPS-020 implementation (#9101)')
    graph.git('checkout', '-b', 'recovery-review')
    graph.lifecycle('review', 'reviewer', implementation)
    graph.commit('OPS-020 independent normal Review (#9102)')
    graph.git('checkout', 'main')
    review = graph.merge('recovery-review', 'OPS-020 admitted independent Review (#9102)')
    graph.git('checkout', '-b', 'recovery-completion')
    if approval:
        graph.write(PROOF.RECOVERY_APPROVAL, json.dumps(graph.approval_record(implementation), indent=2)+'\n')
        if approval_companion:
            graph.write('evidence/OPS-020/invalid-approval-companion.md', '# Unapproved creator companion\n')
        graph.commit('OPS-020 separate preceding independent conditional approval')
    graph.lifecycle('completed', 'integrator', review)
    plan, active = graph.read(PROOF.PLAN), graph.read(PROOF.ACTIVE)
    next(row for row in plan['foundationTasks'] if row['taskId'] == PROOF.RECOVERY_OWNER).update(
        completionRef='PR-9101', mergeCommit=implementation)
    active['tasks'] = [row for row in active['tasks'] if row['taskId'] != PROOF.RECOVERY_OWNER]
    graph.dump(PROOF.PLAN, plan)
    graph.dump(PROOF.ACTIVE, active)
    completion_source = graph.commit('OPS-020 normal Completion (#9103)')
    graph.git('checkout', 'main')
    base = graph.merge('recovery-completion', 'OPS-020 ordinary Completion (#9103)')
    graph.base, graph.implementation, graph.review = base, implementation, review
    graph.completion_source = completion_source
    return graph


@pytest.fixture(scope='module')
def recovery_completed(tmp_path_factory):
    return build_recovery_authority(tmp_path_factory.mktemp('blocked-recovery-authority')/'repo', True)


@pytest.fixture(scope='module')
def recovery_unapproved(tmp_path_factory):
    return build_recovery_authority(tmp_path_factory.mktemp('blocked-recovery-unapproved')/'repo', False)


RECOVERY_TEMPLATE_ENV_BEFORE = os.environ.get('GIT_TEMPLATE_DIR')


@pytest.fixture
def recovery_metadata_clone_template(tmp_path, monkeypatch):
    """Materialize only real metadata inputs in newly created proof clones.

    This controls disposable test clone inputs, not the production H function.
    The checker, exact Git objects/refs, HEAD and all authority checks remain
    real. Original legacy tests and the actual ROOT binary probe stay outside
    this function-scoped environment.
    """
    template = tmp_path/'metadata-clone-template'
    (template/'info').mkdir(parents=True)
    (template/'config').write_text('[core]\n\tsparseCheckout = true\n\tsparseCheckoutCone = false\n', encoding='utf-8')
    patterns = ['/scripts/', '/specs/', '/rules/', '/.github/', '/docs/', '/tests/',
                '/evidence/OPS-020/', '/AGENTS.md', '/.gitattributes', '/.gitignore',
                '/README.md', '/requirements-governance.txt', '/Makefile']
    (template/'info/sparse-checkout').write_text('\n'.join(patterns)+'\n', encoding='utf-8')
    assert {p.relative_to(template).as_posix() for p in template.rglob('*') if p.is_file()} == {'config', 'info/sparse-checkout'}
    monkeypatch.setenv('GIT_TEMPLATE_DIR', str(template))
    yield template


@pytest.fixture
def recovery_graph(recovery_completed, tmp_path, recovery_metadata_clone_template):
    graph = recovery_clone(recovery_completed.repo, tmp_path/'repo', recovery_completed.base)
    graph.base, graph.implementation = recovery_completed.base, recovery_completed.implementation
    return graph


def test_blocked_recovery_requires_its_new_completed_authority():
    with pytest.raises(PROOF.MigrationError, match='normally complete and release'):
        PROOF.authority(str(ROOT), PROOF.RECOVERY_REGISTRATION, _recovery=True)


def test_blocked_recovery_source_virtual_and_actual_merge_are_one_event(recovery_graph):
    graph = recovery_graph
    graph.git('checkout', '-b', PROOF.RECOVERY_NEW)
    head = graph.recover()
    expected = {PROOF.TARGET: PROOF.FIELDS}
    assert PROOF.validate_range(str(graph.repo), graph.base, head) == expected
    graph.git('checkout', '-b', 'recovery-virtual', graph.base)
    virtual = graph.merge(PROOF.RECOVERY_NEW, 'POC-003 virtual ordinary merge')
    graph.git('checkout', 'main')
    actual = graph.merge(PROOF.RECOVERY_NEW, 'POC-003 actual ordinary merge (#9104)')
    for ref in (head, virtual, actual):
        assert PROOF.validate_range(str(graph.repo), graph.base, ref) == expected
        for script in ('check-program-plan-transitions.py', 'check-program-plan-history.py'):
            result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts'/script), '--repo-root', str(graph.repo),
                '--base-ref', graph.base, '--head-ref', ref, '--task', PROOF.TARGET,
                '--branch-name', PROOF.RECOVERY_NEW], capture_output=True, text=True)
            assert result.returncode == 0, result.stdout+result.stderr


@pytest.mark.parametrize('mutation', ['lease', 'actor', 'creation', 'role', 'task-body', 'foreign', 'code', 'oversized-readme'])
def test_blocked_recovery_rejects_unapproved_fields(recovery_graph, mutation):
    graph = recovery_graph
    graph.git('checkout', '-b', PROOF.RECOVERY_NEW)
    graph.recover()
    if mutation in {'lease', 'actor', 'creation', 'role'}:
        active = graph.read(PROOF.ACTIVE)
        row = PROOF.rows(active)[PROOF.TARGET]
        if mutation == 'lease':
            row['lease']['expiresAt'] = '2099-01-01T00:00:00Z'
        elif mutation == 'actor':
            row['reviewer'] = '/root'
        elif mutation == 'creation':
            row['baseSha'] = '0'*40
        else:
            row['agentRole'] = 'reviewer'
        graph.dump(PROOF.ACTIVE, active)
    elif mutation == 'task-body':
        graph.write(PROOF.TASK, (graph.repo/PROOF.TASK).read_bytes()+b'\nChanged original body.\n')
    elif mutation == 'foreign':
        path = 'specs/tasks/POC-005.md'
        graph.write(path, (graph.repo/path).read_bytes()+b'\nForeign change.\n')
    elif mutation == 'code':
        graph.write('poc/POC-03-ats-range/unapproved.py', '# forbidden recovery code\n')
    else:
        graph.write(PROOF.RECOVERY_PREFIX+'README.md', 'x'*8193)
    head = graph.commit('Unapproved recovery companion change')
    if mutation == 'code':
        assert 'poc/POC-03-ats-range/unapproved.py' in PROOF.changed(str(graph.repo), graph.base, head)
    with pytest.raises(PROOF.MigrationError):
        PROOF.validate_range(str(graph.repo), graph.base, head)


@pytest.mark.parametrize('grant', ['legacy-only', 'private-only'])
def test_old_or_private_grants_cannot_authorize_blocked_recovery(recovery_unapproved, tmp_path, grant):
    graph = recovery_clone(recovery_unapproved.repo, tmp_path/'repo', recovery_unapproved.base)
    if grant == 'legacy-only':
        assert PROOF.blob(str(graph.repo), recovery_unapproved.base, PROOF.APPROVAL)
    else:
        (tmp_path/'private-approval.json').write_text(json.dumps(graph.approval_record(recovery_unapproved.implementation)), encoding='utf-8')
    graph.git('checkout', '-b', PROOF.RECOVERY_NEW)
    head = graph.recover()
    with pytest.raises(PROOF.MigrationError):
        PROOF.validate_range(str(graph.repo), recovery_unapproved.base, head)


def test_recovery_approval_cannot_be_created_after_completion(recovery_unapproved, tmp_path):
    graph = recovery_clone(recovery_unapproved.repo, tmp_path/'repo', recovery_unapproved.base)
    graph.write(PROOF.RECOVERY_APPROVAL, json.dumps(graph.approval_record(recovery_unapproved.implementation))+'\n')
    graph.commit('Late approval after authority Completion')
    graph.git('checkout', '-b', PROOF.RECOVERY_NEW)
    head = graph.recover()
    with pytest.raises(PROOF.MigrationError):
        PROOF.validate_range(str(graph.repo), recovery_unapproved.base, head)


@pytest.mark.parametrize('path', [PROOF.RECOVERY_INTENT, PROOF.RECOVERY_APPROVAL])
def test_recovery_protected_rewrite_restore_rejected_without_branch_change(recovery_graph, path):
    original = (recovery_graph.repo/path).read_bytes()
    recovery_graph.write(path, b'{}\n')
    recovery_graph.commit('Protected recovery side edit')
    recovery_graph.write(path, original)
    head = recovery_graph.commit('Restore protected recovery metadata')
    with pytest.raises(PROOF.MigrationError):
        PROOF.validate_range(str(recovery_graph.repo), recovery_graph.base, head)


def test_recovery_restore_and_second_transaction_are_rejected(recovery_graph):
    graph = recovery_graph
    graph.git('checkout', '-b', PROOF.RECOVERY_NEW)
    graph.recover()
    for path in (PROOF.ACTIVE, PROOF.TASK, PROOF.PLAN):
        graph.write(path, PROOF.blob(str(graph.repo), graph.base, path))
    graph.commit('Unapproved restoration of blocked tuple')
    head = graph.recover()
    with pytest.raises(PROOF.MigrationError):
        PROOF.validate_range(str(graph.repo), graph.base, head)


@pytest.mark.parametrize('late', ['source', 'merge'])
def test_recovery_source_and_actual_merge_must_precede_poc_lease_expiry(recovery_graph, late):
    graph = recovery_graph
    expires = PROOF.instant(PROOF.rows(graph.read(PROOF.ACTIVE))[PROOF.TARGET]['lease']['expiresAt'])
    graph.git('checkout', '-b', PROOF.RECOVERY_NEW)
    if late == 'source':
        graph.clock = expires
    head = graph.recover()
    if late == 'merge':
        graph.git('checkout', 'main')
        graph.clock = expires
        head = graph.merge(PROOF.RECOVERY_NEW, 'Recovery merge after lease expiry')
    with pytest.raises(PROOF.MigrationError):
        PROOF.validate_range(str(graph.repo), graph.base, head)


@pytest.mark.parametrize('kind', ['squash', 'wrong-tree'])
def test_recovery_integration_requires_ordinary_exact_tree_merge(recovery_graph, kind):
    graph = recovery_graph
    graph.git('checkout', '-b', PROOF.RECOVERY_NEW)
    graph.recover()
    graph.git('checkout', 'main')
    if kind == 'squash':
        graph.git('merge', '--squash', PROOF.RECOVERY_NEW)
    else:
        graph.git('merge', '--no-ff', '--no-commit', PROOF.RECOVERY_NEW)
        graph.write(PROOF.RECOVERY_PREFIX+'README.md', '# Different actual merge tree\n')
    head = graph.commit('Forbidden recovery integration form')
    with pytest.raises(PROOF.MigrationError):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_recovery_cannot_start_from_unadmitted_completion_source(recovery_completed, tmp_path):
    graph = recovery_clone(recovery_completed.repo, tmp_path/'repo', recovery_completed.completion_source)
    graph.git('checkout', '-b', PROOF.RECOVERY_NEW)
    head = graph.recover()
    with pytest.raises(PROOF.MigrationError, match='source must follow'):
        PROOF.validate_range(str(graph.repo), recovery_completed.completion_source, head, recovery_completed.base)


@pytest.mark.parametrize('field,value', [('kind', 'conditional_prospective_work_branch_migration'),
                                       ('authorityTaskId', 'OPS-019'), ('unexpectedPermission', True)])
def test_recovery_grant_kind_owner_and_field_set_are_exact(recovery_graph, field, value):
    record = json.loads((recovery_graph.repo/PROOF.RECOVERY_APPROVAL).read_bytes())
    record[field] = value
    with pytest.raises(PROOF.MigrationError):
        PROOF.recovery_approval_record(str(recovery_graph.repo), json.dumps(record).encode())


def test_recovery_rejects_the_retired_large_media_ancestry(recovery_graph):
    import base64
    graph = recovery_graph
    graph.git('checkout', '-b', PROOF.RECOVERY_NEW)
    source = graph.recover()
    retired = json.loads((ROOT/PROOF.GRAPH).read_bytes())
    for entry in retired['nodes']:
        result = subprocess.run(['git', '-C', str(graph.repo), 'hash-object', '-t', 'commit', '-w', '--stdin'],
            input=base64.b64decode(entry['rawBase64']), capture_output=True)
        assert result.returncode == 0 and result.stdout.decode().strip() == entry['sha']
    head = graph.git('commit-tree', graph.git('rev-parse', source+'^{tree}'), '-p', source,
                     '-p', PROOF.RETIRED[0], '-m', 'Retired large-media parent', env=graph.environment())
    with pytest.raises(PROOF.MigrationError, match='large-delivery ancestor'):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_recovery_rejects_approval_edit_restore_in_already_admitted_side_history(recovery_graph):
    graph = recovery_graph
    original = (graph.repo/PROOF.RECOVERY_APPROVAL).read_bytes()
    graph.git('checkout', '-b', 'hidden-approval-edit')
    graph.write(PROOF.RECOVERY_APPROVAL, b'{}\n')
    graph.commit('Side edit of previously admitted approval')
    graph.write(PROOF.RECOVERY_APPROVAL, original)
    restored = graph.commit('Restore exact approval bytes on side branch')
    graph.git('checkout', 'main')
    admitted = graph.merge('hidden-approval-edit', 'Admit TREESAME side history')
    assert graph.git('rev-parse', admitted+'^{tree}') == graph.git('rev-parse', graph.base+'^{tree}')
    assert graph.git('rev-parse', admitted+'^{tree}') == graph.git('rev-parse', restored+'^{tree}')
    graph.git('checkout', '-b', PROOF.RECOVERY_NEW)
    head = graph.recover()
    with pytest.raises(PROOF.MigrationError):
        PROOF.validate_range(str(graph.repo), admitted, head, admitted)


def test_recovery_rechecks_previously_admitted_approval_creator_scope(tmp_path):
    graph = build_recovery_authority(tmp_path/'repo', True, approval_companion=True)
    graph.git('checkout', '-b', PROOF.RECOVERY_NEW)
    head = graph.recover()
    with pytest.raises(PROOF.MigrationError, match='separate preceding normal Review approval commit'):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_recovery_reused_snapshot_cache_revalidates_changed_entry_and_commit(recovery_graph, monkeypatch):
    graph = recovery_graph
    root = str(graph.repo)
    module = PROOF.recovery_history_module(str(graph.repo.resolve()))
    entry = PROOF.rows(PROOF.document(root, PROOF.RECOVERY_REGISTRATION, PROOF.ACTIVE))[PROOF.RECOVERY_OWNER]
    calls = []
    original = module.checkout_task_snapshot
    def checkout(snapshot, commit, task_id):
        calls.append((commit, task_id))
        result = original(snapshot, commit, task_id)
        assert result.returncode == 0
        assert graph.git('-C', snapshot, 'rev-parse', 'HEAD') == commit
        assert graph.git('-C', snapshot, 'rev-parse', '--is-shallow-repository') == 'false'
        assert Path(snapshot, 'specs/tasks/OPS-020.md').is_file()
        assert Path(snapshot, 'evidence/OPS-020/handoff.md').is_file()
        assert not Path(snapshot, 'evidence/POC-005/profiles').exists()
        return result
    monkeypatch.setattr(module, 'checkout_task_snapshot', checkout)
    for _ in range(2):
        errors = []
        module.historical_task_snapshot(root, PROOF.RECOVERY_REGISTRATION, PROOF.RECOVERY_OWNER,
                                        entry, 'Valid registered snapshot', errors)
        assert errors == []
    assert len(calls) == 1
    errors = []
    module.historical_task_snapshot(root, PROOF.RECOVERY_REGISTRATION, PROOF.RECOVERY_OWNER,
                                    dict(entry, reviewer='/root'), 'Changed entry', errors)
    assert errors and len(calls) == 2
    graph.git('checkout', '-b', 'invalid-new-snapshot', PROOF.RECOVERY_REGISTRATION)
    path = 'specs/tasks/OPS-020.md'
    raw = (graph.repo/path).read_bytes()
    assert raw.count(b'agentRole: coordinator') == 1
    graph.write(path, raw.replace(b'agentRole: coordinator', b'agentRole: implementer'))
    invalid = graph.commit('Invalid Task role at a different immutable commit')
    errors = []
    module.historical_task_snapshot(root, invalid, PROOF.RECOVERY_OWNER, entry,
                                    'Changed commit', errors)
    assert errors and len(calls) == 3


@pytest.mark.parametrize('registration_object', ['absent', 'not-an-ancestor'])
def test_copied_completed_recovery_records_cannot_authorize_an_unregistered_lineage(recovery_completed, tmp_path, registration_object):
    repo = tmp_path/'unrelated'
    repo.mkdir()
    subprocess.run(['git', 'init', '--quiet', str(repo)], check=True)
    graph = RecoveryGraph.__new__(RecoveryGraph)
    graph.repo = repo
    graph.clock = PROOF.commit_time(str(recovery_completed.repo), recovery_completed.base)+timedelta(seconds=30)
    graph.git('config', 'user.name', 'Unrelated history fixture')
    graph.git('config', 'user.email', 'fixture@example.invalid')
    for path in (PROOF.ACTIVE, PROOF.PLAN, PROOF.LEDGER, PROOF.TASK,
                 'specs/tasks/OPS-020.md', 'evidence/POC-003/handoff.md',
                 PROOF.RECOVERY_INTENT, PROOF.RECOVERY_APPROVAL):
        graph.write(path, PROOF.blob(str(recovery_completed.repo), recovery_completed.base, path))
    before = graph.commit('Inert copied completed records without their authority history')
    if registration_object == 'not-an-ancestor':
        objects = Path(graph.git('-C', str(ROOT), 'rev-parse', '--git-path', 'objects'))
        if not objects.is_absolute():
            objects = ROOT/objects
        assert objects.is_dir()
        alternate = repo/'.git/objects/info/alternates'
        alternate.write_text(str(objects.resolve())+'\n', encoding='utf-8')
        assert PROOF.resolve(str(repo), PROOF.RECOVERY_REGISTRATION) == PROOF.RECOVERY_REGISTRATION
        assert not PROOF.ancestor(str(repo), PROOF.RECOVERY_REGISTRATION, before)
    else:
        assert PROOF.git(str(repo), 'rev-parse', '--verify', PROOF.RECOVERY_REGISTRATION+'^{commit}', missing=True) is None
    graph.git('checkout', '-b', PROOF.RECOVERY_NEW)
    head = graph.recover()
    errors = []
    assert PROOF.checked_range(str(repo), before, head, errors) == {}
    assert errors


def test_recovery_fixture_environment_restored_and_actual_root_probe_preserved():
    assert os.environ.get('GIT_TEMPLATE_DIR') == RECOVERY_TEMPLATE_ENV_BEFORE
    assert PROOF.verify_probe(str(ROOT))



def test_history_yaml_data_cache_isolates_nested_values_and_aliases(monkeypatch):
    module = PROOF.history_module()
    parse = module.yaml.load
    calls = []
    def observed(text, **options):
        calls.append(text)
        return parse(text, **options)
    monkeypatch.setattr(module.yaml, 'load', observed)
    text = 'primary: &same {status: in_progress, claims: [one, two]}\nsecondary: *same\n'
    first = module.load_yaml_text(text)
    second = module.load_yaml_text(text)
    assert first == second and first is not second
    assert first['primary'] is first['secondary']
    assert second['primary'] is second['secondary']
    first['primary']['claims'].append('caller-only')
    assert first['secondary']['claims'] == ['one', 'two', 'caller-only']
    assert second['primary']['claims'] == ['one', 'two']
    assert module.load_yaml_text(text)['primary']['claims'] == ['one', 'two']
    assert calls == [text]


def test_history_yaml_data_cache_preserves_live_worktree_and_symbolic_ref_reads(tmp_path):
    module = PROOF.history_module()
    repo = tmp_path/'yaml-history';repo.mkdir()
    def git(*args):
        result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
        return result.stdout.strip()
    git('init', '--quiet', '-b', 'main')
    git('config', 'user.name', 'YAML data fixture')
    git('config', 'user.email', 'yaml-fixture@example.invalid')
    git('config', 'commit.gpgsign', 'false')
    file = repo/'metadata.yaml'
    file.write_text('value: original\n', encoding='utf-8')
    git('add', 'metadata.yaml');git('commit', '--quiet', '-m', 'Original metadata')
    original = git('rev-parse', 'HEAD')
    assert module.load_ref(str(repo), 'HEAD', 'metadata.yaml') == {'value': 'original'}
    file.write_text('value: changed\n', encoding='utf-8')
    assert module.load_current(str(repo), 'metadata.yaml') == {'value': 'changed'}
    assert module.load_ref(str(repo), 'HEAD', 'metadata.yaml') == {'value': 'original'}
    git('add', 'metadata.yaml');git('commit', '--quiet', '-m', 'Changed metadata')
    assert module.load_ref(str(repo), 'HEAD', 'metadata.yaml') == {'value': 'changed'}
    assert module.load_ref(str(repo), original, 'metadata.yaml') == {'value': 'original'}


def test_history_yaml_data_cache_reparses_errors_and_preserves_none(monkeypatch):
    module = PROOF.history_module()
    parse = module.yaml.load
    calls = []
    def observed(text, **options):
        calls.append(text)
        return parse(text, **options)
    monkeypatch.setattr(module.yaml, 'load', observed)
    assert module.load_yaml_text(None) is None and calls == []
    for _ in range(2):
        assert module.load_yaml_text('[') is None
    assert calls == ['[', '[']
    for _ in range(2):
        assert module.load_yaml_text('null\n') is None
    assert calls == ['[', '[', 'null\n']


def test_history_yaml_data_cache_has_bounded_residency():
    module = PROOF.history_module()
    for number in range(65):
        assert module.load_yaml_text('item: '+str(number)) == {'item': number}
    info = module._parsed_yaml_text.cache_info()
    assert info.maxsize == info.currsize == 64
    assert module.load_yaml_text('item: 0') == {'item': 0}
    assert module._parsed_yaml_text.cache_info().misses == info.misses+1
