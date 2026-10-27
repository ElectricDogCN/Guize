"""Real isolated Git graphs for the exact prospective actor transactions."""
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('actor_amendment_tests', ROOT/'scripts/reservation-role-amendment.py')
PROOF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROOF)


class Graph:
    def __init__(self, temporary):
        self.repo = temporary/'repo'
        subprocess.run(['git', '-c', 'core.longpaths=true', 'clone', '--shared', '--no-checkout', '--quiet', str(ROOT), str(self.repo)], check=True, capture_output=True)
        self.git('config', 'user.name', 'Actor fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        self.git('checkout', '-b', 'actor-fixture-main', PROOF.REGISTRATION)
        self.clock = PROOF.commit_time(str(self.repo), PROOF.REGISTRATION)+timedelta(minutes=1)
        self.git('checkout', '-b', 'implementation')
        self.lifecycle('in_progress', 'implementer', PROOF.REGISTRATION)
        self.commit('OPS-015 fixture activation')
        for path in PROOF.CLAIMS:
            self.write(path, (ROOT/path).read_bytes())
        self.commit('OPS-015 fixture nonempty implementation (#9001)')
        self.git('checkout', 'actor-fixture-main')
        implementation = self.merge('implementation', 'OPS-015 implementation (#9001)')
        self.git('checkout', '-b', 'review')
        self.lifecycle('review', 'reviewer', implementation)
        self.commit('OPS-015 independent fixture Review (#9002)')
        self.git('checkout', 'actor-fixture-main')
        self.merge('review', 'OPS-015 normal Review (#9002)')
        self.git('checkout', '-b', 'completion')
        self.lifecycle('completed', 'integrator', self.git('rev-parse', 'HEAD'))
        plan = self.read(PROOF.PLAN)
        own = next(row for row in plan['foundationTasks'] if row['taskId'] == 'OPS-015')
        own.update(completionRef='PR-9001', mergeCommit=implementation)
        self.dump(PROOF.PLAN, plan)
        active = self.read(PROOF.ACTIVE)
        active['tasks'] = [row for row in active['tasks'] if row['taskId'] != 'OPS-015']
        self.dump(PROOF.ACTIVE, active)
        self.commit('OPS-015 normal Completion (#9003)')
        self.git('checkout', 'actor-fixture-main')
        self.base = self.merge('completion', 'OPS-015 normal Completion (#9003)')

    def git(self, *args, env=None):
        result = subprocess.run(['git', '-c', 'core.longpaths=true', '-C', str(self.repo), *args], capture_output=True, env=env)
        if result.returncode:
            raise AssertionError(result.stdout.decode(errors='replace')+result.stderr.decode(errors='replace'))
        return result.stdout.decode().strip()

    def environment(self):
        self.clock += timedelta(seconds=2)
        stamp = self.clock.isoformat()
        return dict(os.environ, GIT_AUTHOR_DATE=stamp, GIT_COMMITTER_DATE=stamp)

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '--quiet', '-m', message, env=self.environment())
        return self.git('rev-parse', 'HEAD')

    def merge(self, branch, message):
        self.git('merge', '--no-ff', '-m', message, branch, env=self.environment())
        return self.git('rev-parse', 'HEAD')

    def write(self, path, value):
        p = self.repo/path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(value if isinstance(value, bytes) else value.encode())

    def read(self, path):
        return yaml.safe_load((self.repo/path).read_bytes())

    def dump(self, path, value):
        self.write(path, yaml.safe_dump(value, sort_keys=False, allow_unicode=True))

    def lifecycle(self, status, role, base):
        plan, active = self.read(PROOF.PLAN), self.read(PROOF.ACTIVE)
        next(row for row in plan['foundationTasks'] if row['taskId'] == 'OPS-015')['status'] = status
        next(row for row in active['tasks'] if row['taskId'] == 'OPS-015').update(status=status, agentRole=role, baseSha=base, branch='chore/OPS-015-fixture')
        self.dump(PROOF.PLAN, plan)
        self.dump(PROOF.ACTIVE, active)
        path = 'specs/tasks/OPS-015.md'
        raw = (self.repo/path).read_text(encoding='utf-8')
        import re
        for key, value in dict(status=status, agentRole=role, baseSha=base, workBranch='chore/OPS-015-fixture').items():
            raw = re.sub(r'^'+key+r':.*$', key+': '+value, raw, count=1, flags=re.M)
        self.write(path, raw)

    def approval(self, target, mutate=None, *, commit=True):
        intent = json.loads((self.repo/PROOF.INTENT).read_bytes())
        old = dict(zip(('implementer', 'reviewer'), intent['oldProgramRoleValues']))
        record = dict(schemaVersion=1, kind='prospective_poc_actor_amendment', taskId=target,
                      admittedMain=self.base, oldActors=old, newActors=intent['futureActualActors'][target],
                      reviewer=intent['futureActualActors'][target]['reviewer'],
                      approvedAt=(self.clock+timedelta(seconds=1)).isoformat(), decision='approved')
        if mutate:
            mutate(record)
        self.write('evidence/'+target+'/actor-amendment-v1/approval.json', json.dumps(record, indent=2)+'\n')
        if commit:
            self.commit(target+' prospective independent approval')

    def roles(self, target, *, reverse=False):
        intent = json.loads((self.repo/PROOF.INTENT).read_bytes())
        old = dict(zip(('implementer', 'reviewer'), intent['oldProgramRoleValues']))
        new = intent['futureActualActors'][target]
        if reverse:
            old, new = new, old
        path = 'specs/tasks/'+target+'.md'
        self.write(path, PROOF.task_replacement((self.repo/path).read_bytes(), old, new))
        self.write(PROOF.ACTIVE, PROOF.registry_replacement((self.repo/PROOF.ACTIVE).read_bytes(), target, old, new))

    def amend(self, target='POC-003', mutate=None, *, approval_commit=True):
        self.git('checkout', '-b', 'chore/'+target+'-actor-metadata')
        self.approval(target, mutate, commit=approval_commit)
        self.roles(target)
        return self.commit(target+' prospective concrete actors')


@pytest.fixture
def graph(tmp_path):
    return Graph(tmp_path)


@pytest.mark.parametrize('target', ['POC-003', 'POC-005'])
def test_original_metadata_transaction_and_real_callers(graph, target):
    head = graph.amend(target)
    assert PROOF.validate_range(str(graph.repo), graph.base, head) == {target: PROOF.FIELDS}
    for script in ('check-program-plan-transitions.py', 'check-program-plan-history.py'):
        result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts'/script), '--repo-root', str(graph.repo),
            '--base-ref', graph.base, '--head-ref', head, '--task', target,
            '--branch-name', 'chore/'+target+'-actor-metadata'], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout+result.stderr


@pytest.mark.parametrize('change', [
    lambda r: r.update(reviewer='/root'),
    lambda r: r.update(taskId='POC-009'),
    lambda r: r.update(extra='unapproved'),
    lambda r: r.update(approvedAt='2099-01-01T00:00:00Z'),
    lambda r: r['newActors'].update(reviewer='/root'),
    lambda r: r['newActors'].update(implementer='task-owner-agent'),
    lambda r: r['newActors'].update(implementer='/root/independent_review', reviewer='/root'),
    lambda r: r['oldActors'].update(implementer='someone-else'),
    lambda r: r.update(admittedMain=PROOF.REGISTRATION),
])
def test_rejects_invalid_independent_prospective_approval(graph, change):
    head = graph.amend(mutate=change)
    with pytest.raises(PROOF.AmendmentError):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_approval_in_same_commit_is_not_prospective(graph):
    head = graph.amend(approval_commit=False)
    with pytest.raises(PROOF.AmendmentError, match='preceding Git commit'):
        PROOF.validate_range(str(graph.repo), graph.base, head)


@pytest.mark.parametrize('field,value', [('branch', 'chore/POC-003-other'), ('riskLevel', 'high'),
    ('baseSha', PROOF.REGISTRATION), ('status', 'in_progress'), ('agentRole', 'implementer'),
    ('exclusivePaths', ['other/**']), ('dependsOn', []), ('integrationOrder', 99),
    ('lease', {'acquiredAt': '2026-10-27T05:00:00Z', 'expiresAt': '2099-01-01T00:00:00Z'})])
def test_rejects_other_stable_fields_or_start_in_actor_pr(graph, field, value):
    graph.amend()
    active = graph.read(PROOF.ACTIVE)
    next(row for row in active['tasks'] if row['taskId'] == 'POC-003')[field] = value
    graph.dump(PROOF.ACTIVE, active)
    head = graph.commit('Unapproved accompanying field')
    with pytest.raises(PROOF.AmendmentError):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_bad_earlier_edit_is_not_cured_by_restore_and_later_approval(graph):
    graph.git('checkout', '-b', 'bad-history')
    graph.roles('POC-003')
    graph.commit('Unauthorized early actor edit')
    graph.roles('POC-003', reverse=True)
    graph.commit('Restore old actors')
    graph.approval('POC-003')
    graph.roles('POC-003')
    head = graph.commit('Later apparently valid actors')
    with pytest.raises(PROOF.AmendmentError):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_later_business_work_cannot_hide_in_original_actor_pr(graph):
    graph.amend()
    graph.write('poc/POC-03-ats-range/extra.py', 'print("not metadata")\n')
    head = graph.commit('Extra business work')
    with pytest.raises(PROOF.AmendmentError, match='unrelated'):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_approval_rewrite_and_later_noop_cannot_launder_the_original(graph):
    graph.amend()
    path = 'evidence/POC-003/actor-amendment-v1/approval.json'
    original = (graph.repo/path).read_text()
    graph.write(path, original.replace('"schemaVersion": 1', '"schemaVersion": 2'))
    graph.commit('Rewrite committed approval')
    graph.write(path, original)
    graph.commit('Restore original approval')
    graph.write('evidence/POC-003/actor-amendment-v1/note.md', 'Later note\n')
    head = graph.commit('Later evidence cannot erase rewrite')
    with pytest.raises(PROOF.AmendmentError, match='cannot be rewritten'):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_mutated_task_before_actor_edit_is_not_the_approved_reservation(graph):
    graph.git('checkout', '-b', 'mutated-task')
    graph.approval('POC-003')
    path = 'specs/tasks/POC-003.md'
    graph.write(path, (graph.repo/path).read_bytes()+b'\nUnapproved Task body.\n')
    graph.commit('Alter Task before identity change')
    graph.roles('POC-003')
    head = graph.commit('Actors on wrong Task baseline')
    with pytest.raises(PROOF.AmendmentError, match='unchanged reservation'):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_task_and_registry_cannot_disagree(graph):
    graph.git('checkout', '-b', 'mismatched-task')
    graph.approval('POC-003')
    original = (graph.repo/'specs/tasks/POC-003.md').read_bytes()
    graph.roles('POC-003')
    graph.write('specs/tasks/POC-003.md', original)
    head = graph.commit('Mismatched actors')
    with pytest.raises(PROOF.AmendmentError):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_task_only_temporary_actor_mismatch_cannot_be_restored_away(graph):
    path = 'specs/tasks/POC-003.md'
    original = (graph.repo/path).read_bytes()
    graph.write(path, original.replace(b'implementer: task-owner-agent', b'implementer: /root', 1))
    graph.commit('Task-only unauthorized actor')
    graph.write(path, original)
    head = graph.commit('Restore Task actor')
    with pytest.raises(PROOF.AmendmentError, match='Task/Registry actor mismatch'):
        PROOF.validate_range(str(graph.repo), graph.base, head)


@pytest.mark.parametrize('mode', ['100755', '120000'])
def test_approval_mode_cannot_change_with_identical_blob(graph, mode):
    graph.amend()
    path = 'evidence/POC-003/actor-amendment-v1/approval.json'
    sha = graph.git('rev-parse', 'HEAD:'+path)
    graph.git('update-index', '--cacheinfo', mode+','+sha+','+path)
    graph.git('commit', '--quiet', '-m', 'Same bytes wrong approval mode', env=graph.environment())
    head = graph.git('rev-parse', 'HEAD')
    with pytest.raises(PROOF.AmendmentError, match='regular metadata'):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_missing_approval_is_not_an_assignment(graph):
    graph.roles('POC-003')
    head = graph.commit('No approval exists')
    with pytest.raises(PROOF.AmendmentError):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_reservation_or_same_candidate_cannot_supply_completed_authority(graph):
    graph.git('checkout', '--detach', PROOF.REGISTRATION)
    graph.base = PROOF.REGISTRATION
    head = graph.amend()
    with pytest.raises(PROOF.AmendmentError, match='normally complete'):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_original_intent_edit_is_not_cured_by_restore(graph):
    original = (graph.repo/PROOF.INTENT).read_bytes()
    graph.write(PROOF.INTENT, original+b' ')
    graph.commit('Alter immutable intent')
    graph.write(PROOF.INTENT, original)
    head = graph.commit('Restore original intent')
    with pytest.raises(PROOF.AmendmentError, match='intent changed'):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def test_foreign_post_implementation_comparison_consumes_only_proved_actors(graph):
    head = graph.amend()
    spec = importlib.util.spec_from_file_location('actor_foreign_history', ROOT/'scripts/check-program-plan-history.py')
    history = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(history)
    errors = []
    history.historical_post_metadata(str(graph.repo), graph.base, head, 'OPS-014',
        PROOF.changed(str(graph.repo), graph.base, head), errors, graph.base, set(), admitted_base=graph.base)
    assert not errors


@pytest.mark.parametrize('path', [PROOF.PLAN, PROOF.LEDGER, 'evidence/POC-005/unrelated.md'])
def test_root_or_foreign_changes_cannot_accompany_actor_transaction(graph, path):
    graph.amend()
    previous = (graph.repo/path).read_bytes() if (graph.repo/path).exists() else b''
    graph.write(path, previous+b'\n# Unrelated edit\n')
    head = graph.commit('Foreign or root mutation')
    with pytest.raises(PROOF.AmendmentError):
        PROOF.validate_range(str(graph.repo), graph.base, head)


def accepted_hybrid(graph):
    graph.git('checkout', '-b', 'feature')
    path = 'specs/tasks/POC-003.md'
    raw = (graph.repo/path).read_bytes().replace(b'status: reserved', b'status: in_progress', 1)
    graph.write(path, raw+b'\nLocal feature implementation context.\n')
    active = graph.read(PROOF.ACTIVE)
    next(row for row in active['tasks'] if row['taskId'] == 'POC-003')['status'] = 'in_progress'
    graph.dump(PROOF.ACTIVE, active)
    graph.commit('POC-003 local feature context')
    graph.git('checkout', 'actor-fixture-main')
    graph.amend()
    graph.git('checkout', 'actor-fixture-main')
    accepted = graph.merge('chore/POC-003-actor-metadata', 'POC-003 accepted actor metadata (#9010)')
    graph.git('checkout', 'feature')
    head = graph.merge('actor-fixture-main', 'Import accepted main actors')
    assert PROOF.validate_range(str(graph.repo), accepted, head, accepted) == {}
    assert (graph.repo/path).read_bytes().endswith(b'Local feature implementation context.\n')
    return accepted, head, path


def test_real_accepted_main_hybrid_import_retains_feature_body_and_state(graph):
    accepted_hybrid(graph)


def test_two_accepted_poc_actor_updates_import_into_real_feature_and_callers(graph):
    feature = 'chore/POC-005-metadata-scale'
    graph.git('checkout', '-b', feature)
    path = 'specs/tasks/POC-005.md'
    raw = (graph.repo/path).read_text(encoding='utf-8')
    import re
    for key, value in dict(status='in_progress', agentRole='implementer', baseSha=graph.base).items():
        raw = re.sub(r'^'+key+r':.*$', key+': '+value, raw, count=1, flags=re.M)
    graph.write(path, raw+'\nLocal POC005 implementation body.\n')
    active = graph.read(PROOF.ACTIVE)
    next(row for row in active['tasks'] if row['taskId'] == 'POC-005').update(status='in_progress', agentRole='implementer', baseSha=graph.base)
    graph.dump(PROOF.ACTIVE, active)
    plan = graph.read(PROOF.PLAN)
    for section in ('tasks', 'pocs'):
        next(row for row in plan[section] if row['taskId'] == 'POC-005')['status'] = 'in_progress'
    graph.dump(PROOF.PLAN, plan)
    graph.commit('POC-005 real local lifecycle')
    graph.git('checkout', 'actor-fixture-main')
    for target in ('POC-003', 'POC-005'):
        graph.amend(target)
        graph.git('checkout', 'actor-fixture-main')
        graph.base = graph.merge('chore/'+target+'-actor-metadata', target+' accepted metadata (#9010)')
    accepted = graph.base
    graph.git('checkout', feature)
    head = graph.merge('actor-fixture-main', 'Import both accepted main actor pairs')
    assert PROOF.validate_range(str(graph.repo), accepted, head, accepted) == {}
    assert (graph.repo/path).read_text().endswith('Local POC005 implementation body.\n')
    for script in ('check-program-plan-transitions.py', 'check-program-plan-history.py'):
        result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts'/script), '--repo-root', str(graph.repo),
            '--base-ref', accepted, '--head-ref', head, '--task', 'POC-005', '--branch-name', feature],
            capture_output=True, text=True)
        assert result.returncode == 0, result.stdout+result.stderr


@pytest.mark.parametrize('variant', ['body', 'mode'])
def test_manual_merge_result_cannot_masquerade_as_automatic_import(graph, variant):
    accepted, good, path = accepted_hybrid(graph)
    before, incoming = PROOF.parents(str(graph.repo), good)
    if variant == 'body':
        graph.write(path, (graph.repo/path).read_bytes()+b'Manual merge body change.\n')
        graph.git('add', path)
    else:
        sha = graph.git('rev-parse', good+':'+path)
        graph.git('update-index', '--cacheinfo', '100755,'+sha+','+path)
    tree = graph.git('write-tree')
    bad = graph.git('commit-tree', tree, '-p', before, '-p', incoming,
                    '-m', 'Synthetic manual merge, preserving original graph', env=graph.environment())
    with pytest.raises(PROOF.AmendmentError):
        PROOF.validate_range(str(graph.repo), accepted, bad, accepted)


def test_unmerged_actor_parent_is_not_an_accepted_main_import(graph):
    graph.git('checkout', '-b', 'unadmitted-feature')
    path = 'specs/tasks/POC-003.md'
    graph.write(path, (graph.repo/path).read_bytes().replace(b'status: reserved', b'status: in_progress', 1))
    active = graph.read(PROOF.ACTIVE)
    next(row for row in active['tasks'] if row['taskId'] == 'POC-003')['status'] = 'in_progress'
    graph.dump(PROOF.ACTIVE, active)
    graph.commit('Local feature before any accepted actor metadata')
    graph.git('checkout', 'actor-fixture-main')
    graph.amend()
    graph.git('checkout', 'unadmitted-feature')
    head = graph.merge('chore/POC-003-actor-metadata', 'Unaccepted actor side parent')
    with pytest.raises(PROOF.AmendmentError):
        PROOF.validate_range(str(graph.repo), graph.base, head, graph.base)


@pytest.fixture
def schema_history(tmp_path):
    """Use the real accepted registration with this checkout's actual checker."""
    spec = importlib.util.spec_from_file_location('actor_history_schema_tests', ROOT/'scripts/check-program-plan-history.py')
    history = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(history)
    repo = tmp_path/'schema-history'
    subprocess.run(['git','clone','--shared','--no-checkout','--quiet',str(ROOT),str(repo)],check=True,capture_output=True)
    def git(*args):
        return subprocess.check_output(['git','-C',str(repo),*args],stderr=subprocess.DEVNULL).decode().strip()
    git('checkout','--detach',PROOF.REGISTRATION)
    git('config','user.name','Schema history fixture')
    git('config','user.email','schema@example.invalid')
    def commit(path, text):
        (repo/path).write_text(text,encoding='utf-8')
        git('add',path)
        git('commit','--quiet','-m','Actual schema fixture update')
    return history,repo,git,commit


def test_reused_meta_schema_still_checks_each_historical_registry_and_program(schema_history):
    h,repo,git,commit = schema_history
    registry = h.load_ref(str(repo),'HEAD',h.ACTIVE)
    def check(document):
        errors = []
        snapshot = git('rev-parse','HEAD')
        h.historical_registration_context(str(repo),snapshot,snapshot,'OPS-015',document,
            PROOF.REGISTRATION,registry['policy'],'schema fixture',errors)
        return errors
    assert check(registry) == []
    before = h.checked_schema_text.cache_info()
    broken = json.loads(json.dumps(registry))
    next(row for row in broken['tasks'] if row['taskId']=='OPS-015')['riskLevel']='unknown-risk'
    assert any('Registry schema violation' in error for error in check(broken))
    assert h.checked_schema_text.cache_info().misses == before.misses
    plan = h.load_ref(str(repo),'HEAD',h.PLAN)
    plan['status']='unknown-program-state'
    commit(h.PLAN,yaml.safe_dump(plan,sort_keys=False))
    assert any('Program schema violation' in error for error in check(registry))
    assert h.checked_schema_text.cache_info().misses == before.misses


@pytest.mark.parametrize('path',['specs/coordination/active-work.schema.yaml','specs/coordination/program-plan.schema.yaml'])
def test_schema_change_missing_invalid_and_restore_revalidate_actual_head(schema_history,path):
    h,repo,git,commit = schema_history
    original = (repo/path).read_text(encoding='utf-8')
    instance = h.load_ref(str(repo),'HEAD',h.ACTIVE if path==h.REGISTRY_SCHEMA else h.PLAN)
    validate = lambda: h.snapshot_validator(str(repo),'HEAD',path,'missing actual Schema')
    assert not list(validate().iter_errors(instance))
    checked = h.checked_schema_text.cache_info().misses
    commit(path,yaml.safe_dump({'$schema':'https://json-schema.org/draft/2020-12/schema','type':'object','required':['new-required-field']}))
    assert list(validate().iter_errors(instance))
    assert h.checked_schema_text.cache_info().misses == checked+1
    commit(path,'type: 42\n')
    for count in (2,3):
        with pytest.raises(h.jsonschema.SchemaError):
            validate()
        assert h.checked_schema_text.cache_info().misses == checked+count
    # The same physical file remains; the actual Git snapshot lacks it.
    git('update-index','--force-remove',path)
    git('commit','--quiet','-m','Missing schema in actual snapshot')
    with pytest.raises(ValueError,match='missing actual Schema'):
        validate()
    commit(path,original)
    assert not list(validate().iter_errors(instance))
    assert h.checked_schema_text.cache_info().misses == checked+3


def test_schema_reuse_keeps_selected_draft_formats_and_fresh_validator(schema_history):
    h,repo,git,commit = schema_history
    for draft,kind in [('http://json-schema.org/draft-07/schema#',h.jsonschema.Draft7Validator),
                       ('https://json-schema.org/draft/2020-12/schema',h.jsonschema.Draft202012Validator)]:
        schema = {'$schema':draft,'type':'object','required':['address'],'properties':{'address':{'type':'string','format':'ipv4'}}}
        commit(h.REGISTRY_SCHEMA,yaml.safe_dump(schema))
        first = h.snapshot_validator(str(repo),'HEAD',h.REGISTRY_SCHEMA,'missing')
        second = h.snapshot_validator(str(repo),'HEAD',h.REGISTRY_SCHEMA,'missing')
        assert isinstance(first,kind) and first is not second
        assert not list(first.iter_errors({'address':'127.0.0.1'}))
        assert list(second.iter_errors({'address':'999.999.999.999'}))


def test_one_schema_read_binds_validation_to_a_moving_ref(schema_history,monkeypatch):
    h,repo,git,commit = schema_history
    texts = iter(['type: integer\n','type: string\n'])
    reads = []
    def moving(root,ref,path):
        reads.append((root,ref,path))
        return next(texts)
    monkeypatch.setattr(h,'read_ref',moving)
    first = h.snapshot_validator(str(repo),'HEAD',h.REGISTRY_SCHEMA,'missing')
    assert len(reads)==1 and not list(first.iter_errors(1)) and list(first.iter_errors('value'))
    second = h.snapshot_validator(str(repo),'HEAD',h.REGISTRY_SCHEMA,'missing')
    assert len(reads)==2 and list(second.iter_errors(1)) and not list(second.iter_errors('value'))
