"""Real Git histories prove bounded repair admission and preserve existing denial."""
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
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


class TestFoundationCleanImports(unittest.TestCase):
    """Real, small Git graphs reproduce both POC main-import shapes.

    These are classifier fixtures, not production admission certificates.
    The actual POC source still has to pass its independent complete gates.
    """

    own_task = 'specs/tasks/OPS-014.md'
    peer_task = 'specs/tasks/POC-005.md'
    claims = sorted(PROOF.REPAIR_PATHS)

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.repo), *args],
                                       stderr=subprocess.STDOUT).decode().strip()

    def write(self, path, value):
        target = self.repo/path
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(value, dict):
            value = yaml.safe_dump(value, allow_unicode=True, sort_keys=False)
        target.write_text(value, encoding='utf-8', newline='\n')

    def commit(self, message):
        self.git('add', '.')
        self.git('commit', '--quiet', '-m', message)
        return self.git('rev-parse', 'HEAD')

    def document(self, ref, path):
        return yaml.safe_load(self.git('show', ref+':'+path))

    def own_row(self, status):
        return dict(taskId='OPS-014', status=status, agentRole='reviewer' if status == 'review' else 'implementer',
                    exclusivePaths=self.claims, sharedPaths=[], issue=2004,
                    implementer='fixture-implementer', reviewer='fixture-reviewer',
                    lease=dict(acquiredAt='2026-10-24T00:00:00Z', expiresAt='2026-10-31T00:00:00Z'))

    def accepted_snapshot(self, status, count):
        plan = self.document(self.common, PROOF.PLAN)
        plan['foundationTasks'] = [dict(taskId='OPS-014', title='Fixture Foundation', status=status,
                                       completionRef='ISSUE-2004', mergeCommit=None)]
        plan['recovery'] = dict(taskId='OPS-014', sourceCommit=self.common, reason='fixture retained recovery')
        active = self.document(self.common, PROOF.ACTIVE)
        active['tasks'].append(self.own_row(status))
        self.write(PROOF.PLAN, plan)
        self.write(PROOF.ACTIVE, active)
        self.write(self.own_task, '---\nid: OPS-014\nstatus: '+status+'\n---\nComplete fixture Task body.\n')
        for index in range(count):
            self.write(f'evidence/OPS-014/{status}-{index:03}.txt', f'Admitted {status} evidence {index}\n')
        for path in self.claims:
            self.write(path, '# Admitted immutable contract repair.\n')
        return self.commit('Fixture admitted main '+status)

    def merge_main(self, incoming, *, resolve_own_task=False, drop_recovery=False):
        previous = self.git('rev-parse', 'HEAD')
        merged = subprocess.run(['git', '-C', str(self.repo), 'merge', '--no-commit', '--no-ff', incoming],
                                capture_output=True)
        self.assertIn(merged.returncode, (0, 1), merged.stderr)
        conflicts = set(self.git('diff', '--name-only', '--diff-filter=U').splitlines())
        self.assertLessEqual(conflicts, {PROOF.PLAN, PROOF.ACTIVE, self.own_task})
        for path, collection in ((PROOF.PLAN, 'tasks'), (PROOF.ACTIVE, 'tasks')):
            actual = self.document(incoming, path)
            peer = next(row for row in self.document(previous, path)[collection] if row['taskId'] == 'POC-005')
            actual[collection] = [peer if row['taskId'] == 'POC-005' else row for row in actual[collection]]
            if path == PROOF.PLAN and drop_recovery:
                actual['recovery'] = None
            self.write(path, actual)
        if resolve_own_task:
            self.write(self.own_task, self.git('show', incoming+':'+self.own_task)+'\n')
        self.git('add', '.')
        self.git('commit', '--quiet', '-m', 'Fixture peer imports admitted main')
        return self.git('rev-parse', 'HEAD')

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='guize-clean-import-')
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.git('init', '--quiet', '-b', 'main')
        for key, value in [('user.name', 'Clean import fixture'), ('user.email', 'fixture@example.invalid'),
                           ('core.autocrlf', 'false')]:
            self.git('config', key, value)
        peer = dict(taskId='POC-005', status='reserved', exclusivePaths=['poc/POC-05-metadata-scale/**'])
        self.write(PROOF.PLAN, dict(status='active', recovery=None, foundationTasks=[], tasks=[peer]))
        self.write(PROOF.ACTIVE, dict(tasks=[peer]))
        self.write(PROOF.LEDGER, dict(records=[]))
        self.write(self.peer_task, '---\nid: POC-005\nstatus: reserved\n---\nPeer fixture.\n')
        for path in self.claims:
            self.write(path, '# Original fixture contract.\n')
        self.common = self.commit('Fixture accepted reservation base')
        self.git('switch', '-c', 'peer')
        for path in (PROOF.PLAN, PROOF.ACTIVE):
            value = self.document(self.common, path)
            value['tasks'][0]['status'] = 'in_progress'
            self.write(path, value)
        self.write(self.peer_task, '---\nid: POC-005\nstatus: in_progress\n---\nPeer implementation.\n')
        self.write('poc/POC-05-metadata-scale/fixture.py', '# Actual peer work.\n')
        self.peer_work = self.commit('Fixture independently owned peer work')
        self.git('switch', 'main')
        self.incoming_first = self.accepted_snapshot('in_progress', 143)
        self.incoming_review = self.accepted_snapshot('review', 25)
        self.base = self.incoming_review
        self.git('switch', 'peer')
        self.first_import = self.merge_main(self.incoming_first)
        self.tip = self.merge_main(self.incoming_review)
        self.history = PROOF.history_module()

    def selected(self, *, hint='POC-005', branch='chore/POC-005-fixture', base=None, head='HEAD'):
        base = base or self.base
        before = next((row for row in self.document(base, PROOF.PLAN)['foundationTasks']
                       if row['taskId'] == 'OPS-014'), None)
        after = next(row for row in self.document(head, PROOF.PLAN)['foundationTasks'] if row['taskId'] == 'OPS-014')
        errors = []
        result = self.history.foundation_preflight_needed(str(self.repo), 'OPS-014', base, head,
            before, after, self.document(base, PROOF.ACTIVE), hint, branch, errors)
        self.assertEqual(errors, [])
        return result

    def test_two_admitted_imports_with_all_evidence_contracts_and_mixed_yaml_are_peer_work(self):
        self.assertEqual(self.git('show', '-s', '--format=%P', self.first_import).split()[1], self.incoming_first)
        for hint, branch in [('POC-005', 'chore/POC-005-fixture'), ('', 'main')]:
            with self.subTest(hint=hint, branch=branch):
                self.assertFalse(self.selected(hint=hint, branch=branch))

    def test_actual_foundation_identity_remains_a_positive_signal(self):
        self.assertTrue(self.selected(hint='OPS-014'))
        self.assertTrue(self.selected(hint='', branch='chore/OPS-014-fixture'))

    def test_nonimported_task_evidence_claim_and_complete_own_rows_remain_signals(self):
        cases = [('task', self.own_task), ('evidence', 'evidence/OPS-014/review-000.txt'),
                 ('claim', self.claims[0]), ('registry', PROOF.ACTIVE), ('plan', PROOF.PLAN), ('recovery', PROOF.PLAN)]
        for kind, path in cases:
            with self.subTest(kind=kind):
                self.git('checkout', '--detach', self.tip)
                if kind in {'task', 'evidence', 'claim'}:
                    self.write(path, (self.repo/path).read_text(encoding='utf-8')+'Own local mutation.\n')
                else:
                    value = self.document(self.tip, path)
                    if kind == 'registry':
                        next(row for row in value['tasks'] if row['taskId'] == 'OPS-014')['lease']['expiresAt'] = '2026-11-01T00:00:00Z'
                    elif kind == 'plan':
                        value['foundationTasks'][0]['title'] = 'Hidden own semantic change'
                    else:
                        value['recovery']['reason'] = 'Changed recovery under peer hint'
                    self.write(path, value)
                self.commit('Fixture own change under a peer hint')
                self.assertTrue(self.selected())

    def test_temporary_own_change_restored_at_tip_is_not_erased(self):
        raw = (self.repo/self.own_task).read_bytes()
        self.write(self.own_task, 'Temporary forbidden own Task.\n')
        self.commit('Fixture temporary own mutation')
        (self.repo/self.own_task).write_bytes(raw)
        self.commit('Fixture restoration does not erase own history')
        self.assertEqual(self.git('rev-parse', 'HEAD^{tree}'), self.git('rev-parse', self.tip+'^{tree}'))
        self.assertTrue(self.selected())

    def test_conflicted_own_task_resolved_to_incoming_is_not_a_clean_import(self):
        self.git('checkout', '--detach', self.peer_work)
        self.write(self.own_task, 'Own conflicting Task before accepted import.\n')
        previous = self.commit('Fixture own add/add conflict')
        node = self.merge_main(self.incoming_first, resolve_own_task=True)
        self.merge_main(self.incoming_review)
        imports = self.history.clean_synchronization_paths(str(self.repo), node, {self.own_task}, [self.incoming_first])
        self.assertNotIn(self.own_task, imports)
        self.assertTrue(self.selected())
        self.assertNotEqual(previous, self.peer_work)

    def test_unadmitted_secondary_parent_cannot_authorize_its_own_import(self):
        self.assertTrue(self.selected(base=self.common))

    def test_import_cannot_drop_owned_incoming_recovery_then_restore_it(self):
        self.git('checkout', '--detach', self.peer_work)
        missing = self.merge_main(self.incoming_first, drop_recovery=True)
        self.assertTrue(self.selected(head=missing))
        self.merge_main(self.incoming_review)
        self.assertEqual(self.document('HEAD', PROOF.PLAN)['recovery'],
                         self.document(self.base, PROOF.PLAN)['recovery'])
        self.assertTrue(self.selected())

    def test_duplicate_and_unreadable_own_projection_fail_closed(self):
        for broken in ['duplicate', 'unreadable']:
            with self.subTest(broken=broken):
                self.git('checkout', '--detach', self.tip)
                if broken == 'duplicate':
                    value = self.document(self.tip, PROOF.ACTIVE)
                    value['tasks'].append(copy.deepcopy(next(row for row in value['tasks'] if row['taskId'] == 'OPS-014')))
                    self.write(PROOF.ACTIVE, value)
                else:
                    self.write(PROOF.ACTIVE, 'tasks: [broken\n')
                self.commit('Fixture ambiguous own metadata')
                self.assertTrue(self.selected())

    def test_renamed_claim_keeps_both_sides_as_local_work(self):
        renamed = 'poc/POC-05-metadata-scale/renamed-contract.py'
        self.git('mv', self.claims[0], renamed)
        self.commit('Fixture claimed-code rename under peer hint')
        paths = self.history.RECOVERY.changed_paths(str(self.repo), self.tip, 'HEAD')
        self.assertIn(self.claims[0], paths)
        self.assertIn(renamed, paths)
        self.assertTrue(self.selected())

    def test_task_blob_line_endings_and_mode_are_real_own_changes(self):
        for kind in ['crlf', 'mode']:
            with self.subTest(kind=kind):
                self.git('checkout', '--detach', self.tip)
                if kind == 'crlf':
                    raw = (self.repo/self.own_task).read_bytes()
                    (self.repo/self.own_task).write_bytes(raw.replace(b'\n', b'\r\n'))
                    self.commit('Fixture raw Task line-ending mutation')
                else:
                    self.git('update-index', '--chmod=+x', self.own_task)
                    self.git('commit', '--quiet', '-m', 'Fixture raw Task mode mutation')
                self.assertTrue(self.selected())


class TestSourceCompatibilityRepairAdmission(unittest.TestCase):
    """Real isolated Git graphs; these fixtures never certify project completion."""
    git = classmethod(TestBoundPocContractRepair.git.__func__)
    write = staticmethod(TestBoundPocContractRepair.write)
    commit = classmethod(TestBoundPocContractRepair.commit.__func__)
    front_fields = staticmethod(TestBoundPocContractRepair.front_fields)
    lifecycle = classmethod(TestBoundPocContractRepair.lifecycle.__func__)
    reservation = 'dcfefbeca496b43d40c4145c751191bdd386375d'

    @classmethod
    def complete_authority(cls, root, code, *, review=True):
        previous = code
        if review:
            cls.lifecycle(root,'OPS-017','review','reviewer',code,'chore/OPS-017-fixture-review')
            previous = cls.commit(root,'OPS-017 fixture independent Review (#2012)')
        cls.lifecycle(root,'OPS-017','completed','integrator',previous,'chore/OPS-017-fixture-completion')
        plan = yaml.safe_load(Path(root,PROOF.PLAN).read_bytes())
        next(x for x in plan['foundationTasks'] if x['taskId']=='OPS-017').update(completionRef='PR-2011',mergeCommit=code)
        active = yaml.safe_load(Path(root,PROOF.ACTIVE).read_bytes())
        active['tasks'] = [x for x in active['tasks'] if x['taskId'] != 'OPS-017']
        cls.write(root,PROOF.PLAN,plan);cls.write(root,PROOF.ACTIVE,active)
        return cls.commit(root,'OPS-017 fixture normal Completion (#2013)')

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='guize-source-admission-')
        cls.fixture = Path(cls.temporary.name,'fixture')
        subprocess.run(['git','clone','--shared','--quiet',str(ROOT),str(cls.fixture)],check=True,capture_output=True)
        cls.git(cls.fixture,'checkout','--detach',cls.reservation)
        for key,value in [('user.email','test@example.com'),('user.name','Source admission fixture'),('core.autocrlf','false')]:
            cls.git(cls.fixture,'config',key,value)
        cls.lifecycle(cls.fixture,'OPS-017','in_progress','implementer',cls.reservation,'chore/OPS-017-fixture-implementation')
        cls.activation = cls.commit(cls.fixture,'OPS-017 fixture separate activation')
        for path in sorted(PROOF.SOURCE_COMPATIBILITY.claims):
            with Path(cls.fixture,path).open('a',encoding='utf-8') as stream:
                stream.write('\n# Fixture nonempty registered implementation coverage.\n')
        cls.code = cls.commit(cls.fixture,'OPS-017 fixture four-claim implementation (#2011)')
        cls.completed = cls.complete_authority(cls.fixture,cls.code)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def setUp(self):
        self.working = tempfile.TemporaryDirectory(prefix='guize-source-admission-case-')
        self.addCleanup(self.working.cleanup)
        self.repo = Path(self.working.name,'repo')
        subprocess.run(['git','clone','--shared','--quiet',str(self.fixture),str(self.repo)],check=True,capture_output=True)
        self.git(self.repo,'checkout','--detach',self.completed)
        for key,value in [('user.email','test@example.com'),('user.name','Source admission case'),('core.autocrlf','false')]:
            self.git(self.repo,'config',key,value)
        self.entry = copy.deepcopy(PROOF.entry_at(str(self.repo),self.reservation,'OPS-017'))
        now = datetime.now(timezone.utc).replace(microsecond=0)
        utc = lambda value:value.isoformat().replace('+00:00','Z')
        self.entry.update(taskId='OPS-018',programTaskId='OPS-018',issue=2014,title='Fixture versioned compatibility repair',
            branch='chore/OPS-018-fixture-repair',baseSha=self.completed,dependsOn=['OPS-017'],
            handoffPath='evidence/OPS-018/handoff.md',exclusivePaths=sorted(PROOF.SOURCE_COMPATIBILITY.paths),integrationOrder=14,
            lease={'acquiredAt':utc(now-timedelta(minutes=1)),'expiresAt':utc(now+timedelta(days=1))})

    def claims(self, *, base=None, entry=None, observed=None):
        return PROOF.prove_claims(str(self.repo),'OPS-018',entry or self.entry,base or self.completed,observed_ref=observed)

    def register(self):
        plan = yaml.safe_load(Path(self.repo,PROOF.PLAN).read_bytes())
        plan['foundationTasks'].append(dict(taskId='OPS-018',title=self.entry['title'],status='reserved',completionRef='ISSUE-2014',mergeCommit=None))
        active = yaml.safe_load(Path(self.repo,PROOF.ACTIVE).read_bytes());active['tasks'].append(self.entry)
        self.write(self.repo,PROOF.PLAN,plan);self.write(self.repo,PROOF.ACTIVE,active)
        front,body = Path(self.repo,'specs/tasks/OPS-017.md').read_text(encoding='utf-8')[4:].split('\n---\n',1)
        front = self.front_fields(front,dict(id='OPS-018',titleZh=self.entry['title'],status='reserved',issue=2014,
            agentRole='coordinator',baseSha=self.entry['baseSha'],workBranch=self.entry['branch'],
            evidencePath='evidence/OPS-018',programTaskId='OPS-018',dependsOn='OPS-017',
            handoffPath='evidence/OPS-018/handoff.md',integrationOrder=14,leaseExpiresAt=self.entry['lease']['expiresAt']))
        start = body.index('## 独占写范围\n');end = body.index('\n## ',start+4)
        body = body[:start]+'## 独占写范围\n\n'+''.join('- `'+p+'`\n' for p in sorted(PROOF.SOURCE_COMPATIBILITY.paths))+body[end:]
        self.write(self.repo,'specs/tasks/OPS-018.md','---\n'+front+'\n---\n'+body)
        self.write(self.repo,'evidence/OPS-018/handoff.md','# Synthetic fixture handoff only\n')
        return self.commit(self.repo,'OPS-018 fixture independent metadata reservation (#2014)')

    def test_real_new_authority_admits_exact_five_and_preserves_legacy_configuration(self):
        self.assertEqual(self.claims(),PROOF.SOURCE_COMPATIBILITY.paths)
        self.assertEqual(PROOF.contract('OPS-014').paths,frozenset(PROOF.REPAIR_PATHS))
        self.assertEqual(PROOF.authenticated_claims(str(self.repo),'OPS-099',self.entry,self.completed),set())
        self.assertEqual(self.claims(),PROOF.SOURCE_COMPATIBILITY.paths)

    def test_original_uncompleted_or_side_completion_cannot_grant_new_scope(self):
        with self.assertRaisesRegex(PROOF.AdmissionError,'not normally completed'):
            self.claims(base=self.reservation,entry=dict(self.entry,baseSha=self.reservation))
        self.assertEqual(PROOF.authenticated_claims(None,'OPS-018',self.entry,self.completed),set())

    def test_flat_intent_requires_exact_paths_parent_kind_and_real_boolean_values(self):
        intent = yaml.safe_load(PROOF.blob(str(self.repo),self.reservation,PROOF.SOURCE_COMPATIBILITY.intent))
        original_parent = PROOF.parent(str(self.repo),self.reservation)
        for key,value in [('kind','one_poc_contract_repair_authorization_intent'),('reservationParent',self.completed),
                          ('repairPaths',sorted(PROOF.REPAIR_PATHS)),('oldIndexStrictRulePreserved','true'),
                          ('historicalExecutionRebindingAllowed',0)]:
            with self.subTest(field=key):
                altered = dict(intent,**{key:value})
                with self.assertRaises(PROOF.AdmissionError):
                    PROOF.approved_paths(str(self.repo),original_parent,altered,PROOF.SOURCE_COMPATIBILITY)

    def test_each_original_target_baseline_is_bound_before_admission(self):
        target = 'docs/18-testing-and-acceptance.md'
        with Path(self.repo,target).open('a',encoding='utf-8') as stream:stream.write('\nPremature fixture target change.\n')
        changed = self.commit(self.repo,'Fixture changed one of five original baseline targets')
        with self.assertRaisesRegex(PROOF.AdmissionError,'approved contract'):
            self.claims(base=changed,entry=dict(self.entry,baseSha=changed))

    def test_missing_cumulative_claim_or_metadata_only_code_reference_is_denied(self):
        self.git(self.repo,'checkout','--detach',self.activation)
        with Path(self.repo,'AGENTS.md').open('a',encoding='utf-8') as stream:stream.write('\nFixture only one claim.\n')
        one = self.commit(self.repo,'OPS-017 fixture incomplete implementation (#2011)')
        completed = self.complete_authority(self.repo,one)
        with self.assertRaisesRegex(PROOF.AdmissionError,'complete registered implementation'):
            self.claims(base=completed,entry=dict(self.entry,baseSha=completed))
        self.git(self.repo,'checkout','--detach',self.code)
        self.write(self.repo,'evidence/OPS-017/metadata-only-code-reference.txt','Not an implementation.\n')
        metadata = self.commit(self.repo,'OPS-017 fixture metadata-only claimed code reference (#2011)')
        completed = self.complete_authority(self.repo,metadata)
        with self.assertRaisesRegex(PROOF.AdmissionError,'claimed implementation contains only lifecycle metadata or Evidence'):
            self.claims(base=completed,entry=dict(self.entry,baseSha=completed))

    def test_later_real_subset_rework_retains_cumulative_four_claim_coverage(self):
        self.git(self.repo,'checkout','--detach',self.code)
        with Path(self.repo,'AGENTS.md').open('a',encoding='utf-8') as stream:stream.write('\nFixture later nonempty subset rework.\n')
        rework = self.commit(self.repo,'OPS-017 fixture real incremental implementation (#2011)')
        completed = self.complete_authority(self.repo,rework)
        self.assertEqual(self.claims(base=completed,entry=dict(self.entry,baseSha=completed)),PROOF.SOURCE_COMPATIBILITY.paths)

    def test_direct_completion_without_independent_review_is_denied(self):
        self.git(self.repo,'checkout','--detach',self.code)
        completed = self.complete_authority(self.repo,self.code,review=False)
        with self.assertRaisesRegex(PROOF.AdmissionError,'independent Review'):
            self.claims(base=completed,entry=dict(self.entry,baseSha=completed))

    def test_new_intent_changed_then_restored_remains_denied(self):
        p = Path(self.repo,PROOF.SOURCE_COMPATIBILITY.intent);raw = p.read_bytes()
        p.write_bytes(raw+b'\n');self.commit(self.repo,'Fixture forbidden new intent edit')
        p.write_bytes(raw);restored = self.commit(self.repo,'Fixture restore cannot erase authorization history')
        with self.assertRaisesRegex(PROOF.AdmissionError,'intent changed'):
            self.claims(base=restored,entry=dict(self.entry,baseSha=restored))

    def test_successor_exact_claims_roles_lease_and_capacity_remain_mandatory(self):
        variants = [dict(self.entry,exclusivePaths=sorted(PROOF.REPAIR_PATHS)),
                    dict(self.entry,sharedPaths=['specs/poc/**']),dict(self.entry,dependsOn=['OPS-013']),
                    dict(self.entry,reviewer=self.entry['implementer']),
                    dict(self.entry,lease={'acquiredAt':'2020-01-01T00:00:00Z','expiresAt':'2020-01-02T00:00:00Z'})]
        for entry in variants:
            with self.subTest(entry=entry):
                with self.assertRaises(PROOF.AdmissionError):self.claims(entry=entry)
        active = yaml.safe_load(Path(self.repo,PROOF.ACTIVE).read_bytes())
        other = copy.deepcopy(self.entry);other.update(taskId='OPS-099',programTaskId='OPS-099',exclusivePaths=['scripts/unrelated.py'])
        active['tasks'].append(other);self.write(self.repo,PROOF.ACTIVE,active)
        occupied = self.commit(self.repo,'Fixture another high slot is occupied')
        with self.assertRaisesRegex(PROOF.AdmissionError,'capacity'):
            self.claims(base=occupied,entry=dict(self.entry,baseSha=occupied))

    def frozen_repair(self):
        registration = self.register()
        plan = yaml.safe_load(Path(self.repo,PROOF.PLAN).read_bytes())
        plan.update(status='frozen',recovery=dict(taskId='OPS-018',reason='Fixture real completed contract recovery',
            affectedTasks=['GZ-021'],sourceCommit=registration,
            frozenAt=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z'),
            verificationPath='evidence/OPS-018/recovery-proof.json'))
        self.write(self.repo,PROOF.PLAN,plan);frozen = self.commit(self.repo,'OPS-018 fixture preceding metadata freeze')
        self.lifecycle(self.repo,'OPS-018','in_progress','implementer',frozen,self.entry['branch'])
        activation = self.commit(self.repo,'OPS-018 fixture separate metadata activation')
        return registration,frozen,activation

    def test_separate_real_freeze_admits_all_five_paths(self):
        _,_,activation = self.frozen_repair()
        with Path(self.repo,'docs/18-testing-and-acceptance.md').open('a',encoding='utf-8') as stream:stream.write('\nFixture lawful bounded repair.\n')
        code = self.commit(self.repo,'OPS-018 fixture code after preceding freeze')
        errors=[];PROOF.validate_repair_changes(str(self.repo),activation,code,'OPS-018',{'docs/18-testing-and-acceptance.md'},errors)
        self.assertEqual(errors,[])

    def test_same_tip_intent_mutation_is_included_in_observed_protected_audit(self):
        _,_,activation = self.frozen_repair()
        with Path(self.repo,'docs/18-testing-and-acceptance.md').open('a',encoding='utf-8') as stream:stream.write('\nFixture repair plus intent attack.\n')
        p=Path(self.repo,PROOF.SOURCE_COMPATIBILITY.intent);p.write_bytes(p.read_bytes()+b'\n')
        code=self.commit(self.repo,'OPS-018 fixture code and forbidden intent edit in same head')
        errors=[];PROOF.validate_repair_changes(str(self.repo),activation,code,'OPS-018',{'docs/18-testing-and-acceptance.md',PROOF.SOURCE_COMPATIBILITY.intent},errors)
        self.assertTrue(any('intent changed' in error for error in errors),errors)

    def test_actual_no_task_lifecycle_denies_contract_edit_without_preceding_freeze(self):
        registration = self.register()
        self.lifecycle(self.repo,'OPS-018','in_progress','implementer',registration,self.entry['branch'])
        self.commit(self.repo,'OPS-018 fixture working activation without freeze')
        with Path(self.repo,'docs/18-testing-and-acceptance.md').open('a',encoding='utf-8') as stream:stream.write('\nFixture premature repair.\n')
        code=self.commit(self.repo,'OPS-018 fixture illegal active-state contract edit')
        result=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'scripts/check-program-lifecycle-guards.py'),'--repo-root',str(self.repo),
            '--base-ref',registration,'--head-ref',code,'--branch-name',self.entry['branch']],capture_output=True,text=True,encoding='utf-8')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('preceding unchanged frozen recovery event',result.stdout+result.stderr)

    def test_actual_no_task_lifecycle_accepts_real_registered_frozen_repair(self):
        _,frozen,_ = self.frozen_repair()
        with Path(self.repo,'docs/18-testing-and-acceptance.md').open('a',encoding='utf-8') as stream:stream.write('\nFixture real bounded contract repair.\n')
        code=self.commit(self.repo,'OPS-018 fixture valid repair after real freeze')
        result=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'scripts/check-program-lifecycle-guards.py'),
            '--repo-root',str(self.repo),'--base-ref',frozen,'--head-ref',code,'--branch-name',self.entry['branch']],
            capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_wrong_owner_producer_and_post_thaw_edits_remain_denied_for_new_scope(self):
        _,_,activation = self.frozen_repair()
        for mutation in ['owner','producer','thawed']:
            with self.subTest(mutation=mutation):
                self.git(self.repo,'checkout','--detach',activation)
                plan=yaml.safe_load(Path(self.repo,PROOF.PLAN).read_bytes())
                if mutation=='owner':plan['recovery']['taskId']='OPS-014'
                elif mutation=='producer':plan['recovery']['affectedTasks']=['GZ-022']
                else:plan['status']='active'
                self.write(self.repo,PROOF.PLAN,plan)
                bad_base=self.commit(self.repo,'OPS-018 fixture wrong preceding recovery '+mutation)
                with Path(self.repo,'docs/18-testing-and-acceptance.md').open('a',encoding='utf-8') as stream:stream.write('\nFixture impermissible recovery.\n')
                code=self.commit(self.repo,'OPS-018 fixture forbidden edit '+mutation)
                errors=[];PROOF.validate_repair_changes(str(self.repo),bad_base,code,'OPS-018',{'docs/18-testing-and-acceptance.md'},errors)
                self.assertTrue(errors,mutation)

    def test_original_new_successor_reservation_cannot_already_edit_frozen_contract(self):
        # Put the target change in the very first registered successor snapshot.
        with Path(self.repo,'docs/18-testing-and-acceptance.md').open('a',encoding='utf-8') as stream:stream.write('\nFixture premature same-reservation code.\n')
        registration=self.register()
        with self.assertRaisesRegex(PROOF.AdmissionError,'metadata-only'):
            self.claims(base=registration)

    def test_intermediate_new_successor_claim_expansion_cannot_be_erased(self):
        self.register()
        active=yaml.safe_load(Path(self.repo,PROOF.ACTIVE).read_bytes())
        own=next(x for x in active['tasks'] if x['taskId']=='OPS-018')
        original=copy.deepcopy(own)
        own['exclusivePaths'].append('specs/poc/policy.yaml')
        self.write(self.repo,PROOF.ACTIVE,active);self.commit(self.repo,'OPS-018 fixture forbidden intermediate expansion')
        own['exclusivePaths']=original['exclusivePaths']
        self.write(self.repo,PROOF.ACTIVE,active);restored=self.commit(self.repo,'OPS-018 fixture restored final claims')
        with self.assertRaisesRegex(PROOF.AdmissionError,'exact declared paths'):
            self.claims(base=restored)

    def test_actual_metadata_only_tip_and_net_empty_restore_audit_authority_intent(self):
        registration=self.register()
        p=Path(self.repo,PROOF.SOURCE_COMPATIBILITY.intent);original=p.read_bytes()
        p.write_bytes(original+b'\n')
        altered=self.commit(self.repo,'OPS-017 fixture forbidden metadata-only authorization correction')
        result=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'scripts/check-program-lifecycle-guards.py'),
            '--repo-root',str(self.repo),'--base-ref',registration,'--head-ref',altered,'--branch-name','chore/OPS-017-fixture-evidence-correction'],
            capture_output=True,text=True,encoding='utf-8')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('Authorization intent changed after registration',result.stdout+result.stderr)
        p.write_bytes(original)
        restored=self.commit(self.repo,'OPS-017 fixture restored bytes cannot erase metadata history')
        self.assertEqual(PROOF.changed(str(self.repo),registration,restored),set())
        errors=[];PROOF.validate_repair_changes(str(self.repo),registration,restored,'OPS-018',set(),errors)
        self.assertTrue(any('Authorization intent changed after registration' in error for error in errors),errors)

    def test_clean_peer_import_authenticates_the_admitted_successor_history(self):
        registration=self.register()
        self.git(self.repo,'checkout','--detach',self.activation)
        self.write(self.repo,'evidence/POC-003/peer-import-fixture.txt','Independent peer work before authority Completion.\n')
        self.commit(self.repo,'POC-003 fixture work before completed authority')
        self.git(self.repo,'merge','--no-ff','--no-edit',registration)
        imported=self.git(self.repo,'rev-parse','HEAD')
        self.assertEqual(self.git(self.repo,'show','-s','--format=%P',imported).split()[1],registration)
        paths=PROOF.changed(str(self.repo),registration,imported)
        errors=[];PROOF.validate_repair_changes(str(self.repo),registration,imported,'OPS-018',paths,errors)
        self.assertEqual(errors,[])
        self.assertEqual(self.claims(base=registration,observed=imported),PROOF.SOURCE_COMPATIBILITY.paths)

    def test_peer_import_cannot_erase_a_local_authority_intent_attack(self):
        registration=self.register()
        self.git(self.repo,'checkout','--detach',self.activation)
        path=Path(self.repo,PROOF.SOURCE_COMPATIBILITY.intent);raw=path.read_bytes()
        path.write_bytes(raw+b'\n');self.commit(self.repo,'Fixture peer temporarily changes immutable authority')
        path.write_bytes(raw);self.commit(self.repo,'Fixture peer restores authority before importing main')
        self.git(self.repo,'merge','--no-ff','--no-edit',registration)
        imported=self.git(self.repo,'rev-parse','HEAD')
        errors=[];PROOF.validate_repair_changes(str(self.repo),registration,imported,'OPS-018',PROOF.changed(str(self.repo),registration,imported),errors)
        self.assertTrue(errors)
        self.assertEqual(PROOF.authenticated_claims(str(self.repo),'OPS-018',self.entry,registration,observed_ref=imported),set())

    def test_peer_cannot_admit_a_successor_from_an_unadmitted_side_parent(self):
        registration=self.register()
        self.git(self.repo,'checkout','--detach',self.activation)
        self.write(self.repo,'evidence/POC-003/unadmitted-peer-fixture.txt','No admitted successor on comparison base.\n')
        self.commit(self.repo,'Fixture peer work before importing unadmitted side reservation')
        self.git(self.repo,'merge','--no-ff','--no-edit',registration)
        imported=self.git(self.repo,'rev-parse','HEAD')
        errors=[];PROOF.validate_repair_changes(str(self.repo),self.reservation,imported,'OPS-018',PROOF.changed(str(self.repo),self.reservation,imported),errors)
        self.assertTrue(errors)

    def test_target_edit_restore_between_completion_and_successor_reservation_is_denied(self):
        path=Path(self.repo,'docs/18-testing-and-acceptance.md');raw=path.read_bytes()
        path.write_bytes(raw+b'\nPremature post-Completion target change.\n')
        self.commit(self.repo,'Fixture target changed after authority Completion')
        path.write_bytes(raw)
        restored=self.commit(self.repo,'Fixture target restored before successor admission')
        self.entry['baseSha']=restored
        registration=self.register()
        with self.assertRaisesRegex(PROOF.AdmissionError,'frozen repair target before admission'):
            self.claims(base=registration)

    def test_actual_pre_successor_intent_attack_is_rejected_when_submitted(self):
        path=Path(self.repo,PROOF.SOURCE_COMPATIBILITY.intent);raw=path.read_bytes()
        path.write_bytes(raw+b'\n')
        altered=self.commit(self.repo,'OPS-017 fixture intent attack before successor registration')
        result=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'scripts/check-program-lifecycle-guards.py'),
            '--repo-root',str(self.repo),'--base-ref',self.completed,'--head-ref',altered,
            '--branch-name','chore/OPS-017-fixture-evidence-correction'],capture_output=True,text=True,encoding='utf-8')
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('Authorization intent changed after registration',result.stdout+result.stderr)
        path.write_bytes(raw)
        restored=self.commit(self.repo,'OPS-017 fixture restoration before successor registration')
        result=subprocess.run([sys.executable,'-X','utf8','-B',str(ROOT/'scripts/check-program-lifecycle-guards.py'),
            '--repo-root',str(self.repo),'--base-ref',self.completed,'--head-ref',restored,
            '--branch-name','chore/OPS-017-fixture-evidence-correction'],capture_output=True,text=True,encoding='utf-8')
        self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('Authorization intent changed after registration',result.stdout+result.stderr)
