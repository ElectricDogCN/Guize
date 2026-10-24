"""Real Git histories prove bounded repair admission and preserve existing denial."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('poc_repair_test',ROOT/'scripts/poc-contract-repair-admission.py')
PROOF = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROOF)
RESERVATION_MAIN = '3eb9bb69b4fb1df85a359750b73356b953429540'


class TestBoundPocContractRepair(unittest.TestCase):
    @classmethod
    def git(cls, root, *args):
        return subprocess.check_output(['git','-C',str(root),*args],stderr=subprocess.STDOUT).decode().strip()

    @staticmethod
    def write(root, path, value):
        target = Path(root,path)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(yaml.safe_dump(value,allow_unicode=True,sort_keys=False) if isinstance(value,dict) else value,
                          encoding='utf-8',newline='\n')

    @classmethod
    def commit(cls, root, message):
        cls.git(root,'add','.')
        cls.git(root,'commit','--quiet','-m',message)
        return cls.git(root,'rev-parse','HEAD')

    @classmethod
    def lifecycle(cls, root, task_id, status, role, base, branch):
        active = yaml.safe_load(Path(root,PROOF.ACTIVE).read_bytes())
        own = next(x for x in active['tasks'] if x['taskId'] == task_id)
        own.update(status=status,agentRole=role,baseSha=base,branch=branch)
        plan = yaml.safe_load(Path(root,PROOF.PLAN).read_bytes())
        next(x for x in plan['foundationTasks'] if x['taskId']==task_id)['status'] = status
        cls.write(root,PROOF.ACTIVE,active)
        cls.write(root,PROOF.PLAN,plan)
        path = Path(root,'specs/tasks/'+task_id+'.md')
        front,body = path.read_text(encoding='utf-8')[4:].split('\n---\n',1)
        fields = yaml.safe_load(front)
        fields.update(status=status,agentRole=role,baseSha=base,workBranch=branch)
        cls.write(root,'specs/tasks/'+task_id+'.md','---\n'+yaml.safe_dump(fields,allow_unicode=True,sort_keys=False)+'---\n'+body)

    @classmethod
    def setUpClass(cls):
        # Start from the actual immutable intent and canonical reservation.
        # Subsequent commits are isolated test history, never production proof.
        cls.temporary = tempfile.TemporaryDirectory(prefix='guize-poc-admission-')
        cls.fixture = Path(cls.temporary.name,'fixture')
        subprocess.run(['git','clone','--shared','--quiet',str(ROOT),str(cls.fixture)],check=True,capture_output=True)
        cls.git(cls.fixture,'checkout','--detach',RESERVATION_MAIN)
        cls.git(cls.fixture,'config','user.email','test@example.com')
        cls.git(cls.fixture,'config','user.name','Bound repair test')
        cls.git(cls.fixture,'config','core.autocrlf','false')
        cls.lifecycle(cls.fixture,'OPS-013','in_progress','implementer',RESERVATION_MAIN,'chore/OPS-013-contract-repair-admission')
        with Path(cls.fixture,'AGENTS.md').open('a',encoding='utf-8') as stream:
            stream.write('\nTest fixture nonempty registered implementation.\n')
        cls.code = cls.commit(cls.fixture,'OPS-013 fixture implementation (#2001)')
        cls.lifecycle(cls.fixture,'OPS-013','review','reviewer',cls.code,'chore/OPS-013-fixture-review')
        cls.review = cls.commit(cls.fixture,'OPS-013 independent fixture Review (#2002)')
        cls.lifecycle(cls.fixture,'OPS-013','completed','integrator',cls.review,'chore/OPS-013-fixture-completion')
        plan = yaml.safe_load(Path(cls.fixture,PROOF.PLAN).read_bytes())
        next(x for x in plan['foundationTasks'] if x['taskId']=='OPS-013').update(completionRef='PR-2001',mergeCommit=cls.code)
        active = yaml.safe_load(Path(cls.fixture,PROOF.ACTIVE).read_bytes())
        active['tasks'] = [x for x in active['tasks'] if x['taskId'] != 'OPS-013']
        cls.write(cls.fixture,PROOF.PLAN,plan)
        cls.write(cls.fixture,PROOF.ACTIVE,active)
        cls.completed = cls.commit(cls.fixture,'OPS-013 fixture normal Completion (#2003)')

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.working = tempfile.TemporaryDirectory(prefix='guize-poc-repair-case-')
        self.addCleanup(self.working.cleanup)
        self.repo = Path(self.working.name,'repo')
        subprocess.run(['git','clone','--shared','--quiet',str(self.fixture),str(self.repo)],check=True,capture_output=True)
        self.git(self.repo,'checkout','--detach',self.completed)
        self.git(self.repo,'config','user.email','test@example.com')
        self.git(self.repo,'config','user.name','Bound repair case')
        self.git(self.repo,'config','core.autocrlf','false')
        original = PROOF.entry_at(str(self.repo),RESERVATION_MAIN,'OPS-013')
        now = datetime.now(timezone.utc).replace(microsecond=0)
        self.entry = copy.deepcopy(original)
        self.entry.update(taskId='OPS-014',programTaskId='OPS-014',issue=2004,title='Bound contract repair',
            branch='chore/OPS-014-contract-repair',baseSha=self.completed,dependsOn=['OPS-013'],
            exclusivePaths=sorted(PROOF.REPAIR_PATHS),integrationOrder=10,
            lease={'acquiredAt':(now-timedelta(minutes=1)).isoformat().replace('+00:00','Z'),
                   'expiresAt':(now+timedelta(days=1)).isoformat().replace('+00:00','Z')})

    def claims(self, *, base=None, entry=None):
        return PROOF.prove_claims(str(self.repo),'OPS-014',entry or self.entry,base or self.completed)

    def register(self, *, contract_edit=False):
        plan = yaml.safe_load(Path(self.repo,PROOF.PLAN).read_bytes())
        plan['foundationTasks'].append(dict(taskId='OPS-014',title=self.entry['title'],status='reserved',completionRef='ISSUE-2004',mergeCommit=None))
        active = yaml.safe_load(Path(self.repo,PROOF.ACTIVE).read_bytes())
        active['tasks'].append(self.entry)
        self.write(self.repo,PROOF.PLAN,plan)
        self.write(self.repo,PROOF.ACTIVE,active)
        text = Path(self.repo,'specs/tasks/OPS-013.md').read_text(encoding='utf-8')
        front,body = text[4:].split('\n---\n',1)
        front = yaml.safe_load(front)
        front.update(id='OPS-014',titleZh=self.entry['title'],status='reserved',issue=2004,
            agentRole='coordinator',baseSha=self.completed,workBranch=self.entry['branch'],
            evidencePath='evidence/OPS-014',programTaskId='OPS-014',dependsOn='OPS-013',
            handoffPath='evidence/OPS-014/handoff.md',integrationOrder=10,
            leaseExpiresAt=self.entry['lease']['expiresAt'])
        start = body.index('## 独占写范围\n')
        end = body.index('\n## ',start+4)
        body = body[:start]+'## 独占写范围\n\n'+''.join('- `'+p+'`\n' for p in sorted(PROOF.REPAIR_PATHS))+body[end:]
        self.write(self.repo,'specs/tasks/OPS-014.md','---\n'+yaml.safe_dump(front,allow_unicode=True,sort_keys=False)+'---\n'+body)
        self.write(self.repo,'evidence/OPS-014/handoff.md','# Fixture handoff\n')
        if contract_edit:
            with Path(self.repo,'specs/poc/check_program.py').open('a',encoding='utf-8') as stream:
                stream.write('\n# premature fixture contract edit\n')
        return self.commit(self.repo,'OPS-014 fixture metadata reservation (#2004)')

    def test_actual_uncompleted_authority_cannot_grant_scope(self):
        with self.assertRaisesRegex(PROOF.AdmissionError,'not normally completed'):
            PROOF.authority(str(self.repo),RESERVATION_MAIN)

    def test_completed_authority_admits_only_declared_prospective_reservation(self):
        self.assertEqual(self.claims(),PROOF.REPAIR_PATHS)

    def test_candidate_or_sibling_completion_is_not_projected_into_base(self):
        entry = dict(self.entry,baseSha=RESERVATION_MAIN)
        with self.assertRaisesRegex(PROOF.AdmissionError,'not normally completed'):
            self.claims(base=RESERVATION_MAIN,entry=entry)

    def test_task_id_or_missing_repository_context_does_not_grant_scope(self):
        self.assertEqual(PROOF.authenticated_claims(None,'OPS-014',self.entry,self.completed),set())
        self.assertEqual(PROOF.authenticated_claims(str(self.repo),'OPS-099',self.entry,self.completed),set())
        self.assertEqual(PROOF.authenticated_claims(str(self.repo),'OPS-014',{},self.completed),set())

    def test_widened_claims_are_rejected(self):
        for extra in ['specs/poc/**','scripts/**','specs/designs/module-ownership.yaml']:
            with self.subTest(extra=extra), self.assertRaisesRegex(PROOF.AdmissionError,'exact declared paths'):
                self.claims(entry=dict(self.entry,exclusivePaths=self.entry['exclusivePaths']+[extra]))

    def test_nonindependent_or_unassigned_roles_are_rejected(self):
        for role in [self.entry['implementer'],'unassigned']:
            with self.subTest(role=role), self.assertRaisesRegex(PROOF.AdmissionError,'independent roles'):
                self.claims(entry=dict(self.entry,reviewer=role))

    def test_expired_and_overlong_leases_are_rejected(self):
        now = datetime.now(timezone.utc)
        for left,right in [(now-timedelta(days=2),now-timedelta(days=1)),(now-timedelta(minutes=1),now+timedelta(days=8))]:
            with self.subTest(end=right), self.assertRaisesRegex(PROOF.AdmissionError,'lease is invalid'):
                self.claims(entry=dict(self.entry,lease={'acquiredAt':left.isoformat(),'expiresAt':right.isoformat()}))

    def test_unregistered_working_state_is_rejected(self):
        with self.assertRaisesRegex(PROOF.AdmissionError,'Unregistered repair cannot implement'):
            self.claims(entry=dict(self.entry,status='in_progress',agentRole='implementer'))

    def test_worktree_intent_does_not_override_committed_authority(self):
        self.write(self.repo,PROOF.INTENT,'{}\n')
        self.assertEqual(self.claims(),PROOF.REPAIR_PATHS)

    def test_committed_authority_tamper_is_rejected(self):
        self.write(self.repo,PROOF.INTENT,'{}\n')
        tampered = self.commit(self.repo,'fixture altered immutable intent')
        with self.assertRaisesRegex(PROOF.AdmissionError,'intent changed'):
            self.claims(base=tampered,entry=dict(self.entry,baseSha=tampered))

    def test_changed_original_contract_baseline_is_rejected(self):
        with Path(self.repo,'specs/poc/check_program.py').open('a',encoding='utf-8') as stream:
            stream.write('\n# fixture different contract before reservation\n')
        altered = self.commit(self.repo,'fixture old contract differs')
        with self.assertRaisesRegex(PROOF.AdmissionError,'approved contract'):
            self.claims(base=altered,entry=dict(self.entry,baseSha=altered))

    def test_real_original_repair_registration_is_required_for_working_claims(self):
        registration = self.register()
        working = dict(self.entry,status='in_progress',agentRole='implementer',baseSha=registration)
        self.assertEqual(self.claims(base=registration,entry=working),PROOF.REPAIR_PATHS)

    def test_original_registration_cannot_already_edit_contract(self):
        registration = self.register(contract_edit=True)
        with self.assertRaisesRegex(PROOF.AdmissionError,'not metadata-only'):
            self.claims(base=registration)

    def test_active_program_does_not_authorize_contract_change(self):
        registration = self.register()
        with Path(self.repo,'specs/poc/check_program.py').open('a',encoding='utf-8') as stream:
            stream.write('\n# fixture active-contract edit\n')
        code = self.commit(self.repo,'OPS-014 fixture premature code')
        errors = []
        PROOF.validate_repair_changes(str(self.repo),registration,code,'OPS-014',PROOF.REPAIR_PATHS,errors)
        self.assertTrue(any('preceding unchanged frozen' in e for e in errors),errors)

    def test_authority_does_not_change_ordinary_or_legacy_claim_results(self):
        guards = PROOF.history_module().RECOVERY
        ownership = {'modules':[{'id':'MOD-GOV','ownedPaths':['scripts/**']} ]}
        entry = dict(self.entry,taskId='OPS-099',programTaskId='OPS-099',exclusivePaths=['specs/poc/check_program.py'])
        self.assertFalse(guards.foundation_claims_valid(str(self.repo),'OPS-099',entry,ownership,self.completed))
        legacy = dict(entry,taskId='GZ-014',exclusivePaths=['AGENTS.md'])
        self.assertTrue(guards.foundation_claims_valid(str(self.repo),'GZ-014',legacy,ownership,self.completed))
