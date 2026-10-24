"""Real Git histories prove bounded repair admission and preserve existing denial."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from unittest import mock

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
    def commit(cls, root, message, *, timestamp=None):
        cls.git(root,'add','.')
        environment = dict(os.environ)
        if timestamp is not None:
            environment.update(GIT_AUTHOR_DATE=timestamp,GIT_COMMITTER_DATE=timestamp)
        subprocess.run(['git','-C',str(root),'commit','--quiet','-m',message],
                       env=environment,check=True,capture_output=True)
        return cls.git(root,'rev-parse','HEAD')

    @staticmethod
    def front_fields(front, fields):
        # Task front matter uses the repository's scalar-line parser, not YAML.
        # Preserve its exact unquoted timestamp/list representation.
        for key,value in fields.items():
            front,count = re.subn(r'^'+re.escape(key)+r':.*$',key+': '+str(value),front,flags=re.M)
            if count != 1:
                raise AssertionError('Missing fixture Task field '+key)
        return front

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
        front = cls.front_fields(front,dict(status=status,agentRole=role,baseSha=base,workBranch=branch,
                      leaseExpiresAt=own['lease']['expiresAt']))
        cls.write(root,'specs/tasks/'+task_id+'.md','---\n'+front+'\n---\n'+body)

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
        cls.activation = cls.commit(cls.fixture,'OPS-013 fixture metadata activation')
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
            handoffPath='evidence/OPS-014/handoff.md',
            exclusivePaths=sorted(PROOF.REPAIR_PATHS),integrationOrder=10,
            lease={'acquiredAt':(now-timedelta(minutes=1)).isoformat().replace('+00:00','Z'),
                   'expiresAt':(now+timedelta(days=1)).isoformat().replace('+00:00','Z')})

    def claims(self, *, base=None, entry=None):
        return PROOF.prove_claims(str(self.repo),'OPS-014',entry or self.entry,base or self.completed)

    def register(self, *, contract_edit=False, timestamp=None):
        plan = yaml.safe_load(Path(self.repo,PROOF.PLAN).read_bytes())
        plan['foundationTasks'].append(dict(taskId='OPS-014',title=self.entry['title'],status='reserved',completionRef='ISSUE-2004',mergeCommit=None))
        active = yaml.safe_load(Path(self.repo,PROOF.ACTIVE).read_bytes())
        active['tasks'].append(self.entry)
        self.write(self.repo,PROOF.PLAN,plan)
        self.write(self.repo,PROOF.ACTIVE,active)
        text = Path(self.repo,'specs/tasks/OPS-013.md').read_text(encoding='utf-8')
        front,body = text[4:].split('\n---\n',1)
        front = self.front_fields(front,dict(id='OPS-014',titleZh=self.entry['title'],status='reserved',issue=2004,
            agentRole='coordinator',baseSha=self.completed,workBranch=self.entry['branch'],
            evidencePath='evidence/OPS-014',programTaskId='OPS-014',dependsOn='OPS-013',
            handoffPath='evidence/OPS-014/handoff.md',integrationOrder=10,
            leaseExpiresAt=self.entry['lease']['expiresAt']))
        start = body.index('## 独占写范围\n')
        end = body.index('\n## ',start+4)
        body = body[:start]+'## 独占写范围\n\n'+''.join('- `'+p+'`\n' for p in sorted(PROOF.REPAIR_PATHS))+body[end:]
        self.write(self.repo,'specs/tasks/OPS-014.md','---\n'+front+'\n---\n'+body)
        self.write(self.repo,'evidence/OPS-014/handoff.md','# Fixture handoff\n')
        if contract_edit:
            with Path(self.repo,'specs/poc/check_program.py').open('a',encoding='utf-8') as stream:
                stream.write('\n# premature fixture contract edit\n')
        return self.commit(self.repo,'OPS-014 fixture metadata reservation (#2004)',timestamp=timestamp)

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

    def test_high_risk_capacity_is_not_added_by_authorization(self):
        active = yaml.safe_load(Path(self.repo,PROOF.ACTIVE).read_bytes())
        peer = dict(self.entry,taskId='OPS-099',programTaskId='OPS-099',exclusivePaths=['scripts/other-repair.py'])
        active['tasks'].append(peer)
        self.write(self.repo,PROOF.ACTIVE,active)
        crowded = self.commit(self.repo,'fixture existing independent high-risk lease')
        with self.assertRaisesRegex(PROOF.AdmissionError,'capacity'):
            self.claims(base=crowded,entry=dict(self.entry,baseSha=crowded))

    def test_declared_frozen_recovery_precedes_actual_contract_edit(self):
        registration = self.register()
        plan = yaml.safe_load(Path(self.repo,PROOF.PLAN).read_bytes())
        plan.update(status='frozen',recovery=dict(taskId='OPS-014',reason='Fixture real completed contract recovery',
            affectedTasks=['GZ-021'],sourceCommit=registration,
            frozenAt=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
            verificationPath='evidence/OPS-014/recovery-proof.json'))
        self.write(self.repo,PROOF.PLAN,plan)
        frozen = self.commit(self.repo,'OPS-014 fixture independent metadata freeze')
        self.lifecycle(self.repo,'OPS-014','in_progress','implementer',frozen,self.entry['branch'])
        activation = self.commit(self.repo,'OPS-014 fixture separate metadata activation')
        with Path(self.repo,'specs/poc/check_program.py').open('a',encoding='utf-8') as stream:
            stream.write('\n# fixture registered frozen contract repair\n')
        code = self.commit(self.repo,'OPS-014 fixture repair after freeze')
        errors = []
        PROOF.validate_repair_changes(str(self.repo),activation,code,'OPS-014',PROOF.REPAIR_PATHS,errors)
        self.assertEqual(errors,[])

    def test_false_parent_baseline_cannot_reserve_repair(self):
        with self.assertRaisesRegex(PROOF.AdmissionError,'Unregistered repair'):
            self.claims(entry=dict(self.entry,baseSha=RESERVATION_MAIN))

    def test_intermediate_claim_expansion_is_rejected_after_restoration(self):
        self.register()
        active = yaml.safe_load(Path(self.repo,PROOF.ACTIVE).read_bytes())
        own = next(x for x in active['tasks'] if x['taskId']=='OPS-014')
        own['exclusivePaths'] = own['exclusivePaths']+['scripts/**']
        self.write(self.repo,PROOF.ACTIVE,active)
        self.commit(self.repo,'OPS-014 fixture impermissible intermediate claim')
        own['exclusivePaths'] = list(self.entry['exclusivePaths'])
        self.write(self.repo,PROOF.ACTIVE,active)
        restored = self.commit(self.repo,'OPS-014 fixture restored final claims')
        with self.assertRaisesRegex(PROOF.AdmissionError,'exact declared paths'):
            self.claims(base=restored)

    def test_rename_keeps_both_paths_and_cannot_hide_active_contract_change(self):
        registration = self.register()
        destination = 'evidence/OPS-014/renamed-contract.py'
        self.git(self.repo,'mv','specs/poc/check_program.py',destination)
        renamed = self.commit(self.repo,'OPS-014 fixture contract rename into Evidence')
        paths = PROOF.changed(str(self.repo),registration,renamed)
        self.assertIn('specs/poc/check_program.py',paths)
        self.assertIn(destination,paths)
        errors = []
        PROOF.validate_repair_changes(str(self.repo),registration,renamed,'OPS-014',paths,errors)
        self.assertTrue(errors)

    def test_original_diagnostic_evidence_cannot_change_after_registration(self):
        Path(self.repo,'evidence/OPS-013/unsatisfiable-response.bin').write_bytes(b'')
        altered = self.commit(self.repo,'fixture altered the declared original 416 response')
        with self.assertRaisesRegex(PROOF.AdmissionError,'defect evidence changed'):
            self.claims(base=altered,entry=dict(self.entry,baseSha=altered))

    def test_completion_without_independent_review_does_not_grant_authority(self):
        self.git(self.repo,'checkout','--detach',self.code)
        for name in [PROOF.PLAN,PROOF.ACTIVE,'specs/tasks/OPS-013.md']:
            self.write(self.repo,name,PROOF.blob(str(self.repo),self.completed,name).decode())
        premature = self.commit(self.repo,'OPS-013 fixture direct Completion without Review')
        with self.assertRaisesRegex(PROOF.AdmissionError,'independent Review'):
            self.claims(base=premature,entry=dict(self.entry,baseSha=premature))

    def test_authority_does_not_change_ordinary_or_legacy_claim_results(self):
        guards = PROOF.history_module().RECOVERY
        ownership = {'modules':[{'id':'MOD-GOV','ownedPaths':['scripts/**']} ]}
        entry = dict(self.entry,taskId='OPS-099',programTaskId='OPS-099',exclusivePaths=['specs/poc/check_program.py'])
        self.assertFalse(guards.foundation_claims_valid(str(self.repo),'OPS-099',entry,ownership,self.completed))
        legacy = dict(entry,taskId='GZ-014',exclusivePaths=['AGENTS.md'])
        self.assertTrue(guards.foundation_claims_valid(str(self.repo),'GZ-014',legacy,ownership,self.completed))

    def test_historical_reservation_remains_valid_after_expiry_and_renewal(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        utc = lambda value: value.isoformat().replace('+00:00','Z')
        self.entry['lease'] = dict(acquiredAt=utc(now-timedelta(minutes=1)),
                                  expiresAt=utc(now+timedelta(minutes=10)))
        original = copy.deepcopy(self.entry)
        registration = self.register()
        renewed = copy.deepcopy(original)
        renewed['lease'] = dict(acquiredAt=utc(now+timedelta(minutes=5)),
                                expiresAt=utc(now+timedelta(days=1)))
        active = yaml.safe_load(Path(self.repo,PROOF.ACTIVE).read_bytes())
        next(x for x in active['tasks'] if x['taskId']=='OPS-014')['lease'] = renewed['lease']
        self.write(self.repo,PROOF.ACTIVE,active)
        task = Path(self.repo,'specs/tasks/OPS-014.md')
        front,body = task.read_text(encoding='utf-8')[4:].split('\n---\n',1)
        front = self.front_fields(front,dict(leaseExpiresAt=renewed['lease']['expiresAt']))
        self.write(self.repo,'specs/tasks/OPS-014.md','---\n'+front+'\n---\n'+body)
        renewal = self.commit(self.repo,'OPS-014 fixture metadata-only lease renewal',
                              timestamp=utc(now+timedelta(minutes=6)))

        class AfterOriginalExpiry(datetime):
            @classmethod
            def now(cls, tz=None):
                return (now+timedelta(minutes=20)).astimezone(tz)

        # Simulate later audit time without changing any machine clock. The
        # original and renewed snapshots retain their real Git timestamps.
        with mock.patch.object(PROOF,'datetime',AfterOriginalExpiry):
            self.assertEqual(PROOF.prove_claims(str(self.repo),'OPS-014',original,
                             self.completed,observed_ref=registration),PROOF.REPAIR_PATHS)
            self.assertEqual(self.claims(base=renewal,entry=renewed),PROOF.REPAIR_PATHS)
            with self.assertRaisesRegex(PROOF.AdmissionError,'lease is invalid'):
                self.claims(entry=original)

    def integrated_authority(self, *, role='integrator', forge_task_role=False):
        self.git(self.repo,'checkout','--detach',self.activation)
        self.lifecycle(self.repo,'OPS-013','review','reviewer',self.activation,
                       'chore/OPS-013-fixture-review-baseline')
        baseline = self.commit(self.repo,'OPS-013 fixture review baseline (#2002)')
        # The source includes separately registered implementation and Review
        # commits. Retain it under a ref even though the integration is squash.
        self.git(self.repo,'branch','fixture-reviewed-source',self.review)
        squash = subprocess.run(['git','-C',str(self.repo),'merge','--squash',self.review],
                                capture_output=True)
        if squash.returncode:
            conflicts = set(self.git(self.repo,'diff','--name-only','--diff-filter=U').splitlines())
            self.assertTrue(conflicts)
            self.assertLessEqual(conflicts,{PROOF.PLAN,PROOF.ACTIVE,'specs/tasks/OPS-013.md'})
        for path in [PROOF.PLAN,PROOF.ACTIVE,'specs/tasks/OPS-013.md']:
            self.write(self.repo,path,PROOF.blob(str(self.repo),baseline,path).decode())
        self.lifecycle(self.repo,'OPS-013','integration',role,baseline,
                       'chore/OPS-013-fixture-integration')
        if forge_task_role:
            path = 'specs/tasks/OPS-013.md'
            text = Path(self.repo,path).read_text(encoding='utf-8')
            self.write(self.repo,path,text.replace('agentRole: integrator','agentRole: reviewer'))
        implementation = self.commit(self.repo,'OPS-013 fixture reviewed source integration (#2001)')
        self.assertEqual(PROOF.blob(str(self.repo),implementation,'AGENTS.md'),
                         PROOF.blob(str(self.repo),self.review,'AGENTS.md'))
        self.lifecycle(self.repo,'OPS-013','completed','integrator',implementation,
                       'chore/OPS-013-fixture-completion')
        plan = yaml.safe_load(Path(self.repo,PROOF.PLAN).read_bytes())
        next(x for x in plan['foundationTasks'] if x['taskId']=='OPS-013').update(
            completionRef='PR-2001',mergeCommit=implementation)
        active = yaml.safe_load(Path(self.repo,PROOF.ACTIVE).read_bytes())
        active['tasks'] = [x for x in active['tasks'] if x['taskId']!='OPS-013']
        self.write(self.repo,PROOF.PLAN,plan)
        self.write(self.repo,PROOF.ACTIVE,active)
        return self.commit(self.repo,'OPS-013 fixture immediate normal Completion (#2003)')

    def test_reviewed_integration_can_complete_without_extra_review_commit(self):
        completed = self.integrated_authority()
        self.assertEqual(self.claims(base=completed,entry=dict(self.entry,baseSha=completed)),
                         PROOF.REPAIR_PATHS)

    def test_implementation_role_cannot_impersonate_integrator_review(self):
        completed = self.integrated_authority(role='implementer')
        with self.assertRaisesRegex(PROOF.AdmissionError,'independent Review'):
            self.claims(base=completed,entry=dict(self.entry,baseSha=completed))

    def test_integration_label_does_not_bypass_normal_history_binding(self):
        completed = self.integrated_authority(forge_task_role=True)
        with self.assertRaisesRegex(PROOF.AdmissionError,'Normal authority Foundation history rejected'):
            self.claims(base=completed,entry=dict(self.entry,baseSha=completed))

    def test_fractional_acquisition_uses_only_historical_git_second_tolerance(self):
        observed = datetime.now(timezone.utc).replace(microsecond=0)
        utc = lambda value:value.isoformat().replace('+00:00','Z')
        self.entry['lease'] = dict(acquiredAt=utc(observed+timedelta(microseconds=500000)),
                                  expiresAt=utc(observed+timedelta(days=1)))
        original = copy.deepcopy(self.entry)
        registration = self.register(timestamp=utc(observed))

        class AtGitSecond(datetime):
            @classmethod
            def now(cls, tz=None):
                return observed.astimezone(tz)

        with mock.patch.object(PROOF,'datetime',AtGitSecond):
            # A half-second future lease remains invalid for wall-clock admission.
            with self.assertRaisesRegex(PROOF.AdmissionError,'lease is invalid'):
                self.claims(entry=original)
            # Git loses only fractional precision, never a whole second or expiry.
            for lease in [dict(acquiredAt=utc(observed+timedelta(seconds=1)),expiresAt=utc(observed+timedelta(days=1))),
                          dict(acquiredAt=utc(observed-timedelta(seconds=1)),expiresAt=utc(observed))]:
                with self.subTest(lease=lease),self.assertRaisesRegex(PROOF.AdmissionError,'lease is invalid'):
                    PROOF.prove_claims(str(self.repo),'OPS-014',dict(original,lease=lease),
                                       self.completed,observed_ref=registration)
            self.assertEqual(PROOF.prove_claims(str(self.repo),'OPS-014',original,
                             self.completed,observed_ref=registration),PROOF.REPAIR_PATHS)
        renewed = copy.deepcopy(original)
        renewed['lease']['acquiredAt'] = utc(observed+timedelta(seconds=1,microseconds=500000))
        active = yaml.safe_load(Path(self.repo,PROOF.ACTIVE).read_bytes())
        next(x for x in active['tasks'] if x['taskId']=='OPS-014')['lease'] = renewed['lease']
        self.write(self.repo,PROOF.ACTIVE,active)
        renewal = self.commit(self.repo,'OPS-014 fixture fractional metadata renewal',
                              timestamp=utc(observed+timedelta(seconds=1)))

        class AfterRenewal(datetime):
            @classmethod
            def now(cls, tz=None):
                return (observed+timedelta(seconds=2)).astimezone(tz)

        with mock.patch.object(PROOF,'datetime',AfterRenewal):
            self.assertEqual(self.claims(base=renewal,entry=renewed),PROOF.REPAIR_PATHS)

    def test_intent_edit_and_restoration_after_successor_registration_is_rejected(self):
        registration = self.register()
        original = PROOF.blob(str(self.repo),registration,PROOF.INTENT)
        self.write(self.repo,PROOF.INTENT,'{}\n')
        self.commit(self.repo,'OPS-014 fixture forbidden post-registration intent edit')
        Path(self.repo,PROOF.INTENT).write_bytes(original)
        restored = self.commit(self.repo,'OPS-014 fixture restored intent does not erase history')
        with self.assertRaisesRegex(PROOF.AdmissionError,'intent changed'):
            self.claims(base=restored)

    def test_diagnostic_edit_after_successor_registration_is_rejected(self):
        self.register()
        Path(self.repo,'evidence/OPS-013/unsatisfiable-response.bin').write_bytes(b'altered diagnostic\n')
        altered = self.commit(self.repo,'OPS-014 fixture forbidden post-registration diagnostic edit')
        with self.assertRaisesRegex(PROOF.AdmissionError,'defect evidence changed'):
            self.claims(base=altered)
