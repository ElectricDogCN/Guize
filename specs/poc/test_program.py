#!/usr/bin/env python3
"""Positive and negative tests for POC-PROTOCOL-V1."""

from __future__ import annotations
import importlib.util, shutil, tempfile, unittest
from pathlib import Path
import yaml

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location("poc_check_program",HERE/"check_program.py")
CHECK=importlib.util.module_from_spec(SPEC);assert SPEC and SPEC.loader;SPEC.loader.exec_module(CHECK)

def load_yaml(path:Path):
    with path.open("r",encoding="utf-8") as f:return yaml.safe_load(f)
def write_yaml(path:Path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",encoding="utf-8") as f:yaml.safe_dump(data,f,sort_keys=False,allow_unicode=True,width=120)

class TestPocProgram(unittest.TestCase):
    def setUp(self):self.repo=HERE.parents[1]
    def temp_repo(self):
        temp=tempfile.TemporaryDirectory();root=Path(temp.name)
        shutil.copytree(self.repo/"specs"/"poc",root/"specs"/"poc")
        (root/"specs"/"coordination").mkdir(parents=True)
        shutil.copy2(self.repo/"specs"/"coordination"/"program-plan.yaml",root/"specs"/"coordination"/"program-plan.yaml")
        return temp,root
    def assert_invalid(self,mutator,needle=None):
        temp,root=self.temp_repo()
        try:
            mutator(root);errors=CHECK.validate_repository(root);self.assertTrue(errors,"negative mutation unexpectedly passed")
            if needle:self.assertTrue(any(needle in e for e in errors),"\n".join(errors))
        finally:temp.cleanup()
    def plan_path(self,r,tid):return r/"specs"/"poc"/"plans"/f"{tid}.yaml"
    def index_path(self,r):return r/"specs"/"poc"/"results-index.yaml"
    def pp_path(self,r):return r/"specs"/"coordination"/"program-plan.yaml"
    def make_terminal(self,root,tid="POC-003",status="pass"):
        plan=load_yaml(self.plan_path(root,tid));ev=root/plan["evidencePath"];ev.mkdir(parents=True,exist_ok=True)
        raw=f"{plan['evidencePath']}/raw/execution.log";(root/raw).parent.mkdir(parents=True,exist_ok=True);(root/raw).write_text("bounded raw output\n",encoding="utf-8")
        samples=[]
        for sid in plan["sampleIds"]:
            ar=f"{plan['evidencePath']}/approvals/{sid}.yaml";(root/ar).parent.mkdir(parents=True,exist_ok=True);(root/ar).write_text("approved: true\n",encoding="utf-8")
            samples.append({"id":sid,"immutableId":f"fixture-{sid.lower()}","checksum":"sha256:"+"a"*64,"approved":True,"approvalRef":ar})
        env={k:({"fixed":"value"} if k=="inference_parameters" else f"captured-{k}") for k in plan["environment"]["captureBeforeExecution"]}
        measurements=[]
        for m in plan["protocol"]["measurements"]:
            actual=True if str(m["unit"]).lower()=="boolean" else 1
            if status!="pass" and str(m["unit"]).lower()=="boolean":actual=False
            measurements.append({"id":m["id"],"actual":actual})
        provenance={}
        if plan["pocId"]=="POC-02":provenance={"input_sha256":"sha256:"+"b"*64,"output_sha256":"sha256:"+"c"*64,"encoder_parameters":{"codec":"av1","crf":30,"preset":"medium"}}
        xr=f"{plan['evidencePath']}/execution.yaml";execution={"schemaVersion":1,"pocId":plan["pocId"],"taskId":tid,"evidencePath":plan["evidencePath"],"executor":"task-owner-agent","environmentCaptured":env,"commands":["bounded-test-command --fixture approved"],"rawOutputRefs":[raw],"samples":samples,"measurements":measurements,"provenance":provenance,"notes":None};write_yaml(root/xr,execution)
        rr=f"{plan['evidencePath']}/result.yaml";result={"schemaVersion":1,"pocId":plan["pocId"],"taskId":tid,"status":status,"evidencePath":plan["evidencePath"],"executionRef":xr,"decision":status,"rationale":"fixture result backed by existing raw evidence and complete measurements","reviewer":"independent-review-agent","approvedAt":"2026-09-03T00:00:00Z","approval":"approved"};write_yaml(root/rr,result)
        idx=load_yaml(self.index_path(root));entry=next(e for e in idx["entries"] if e["taskId"]==tid);entry.update({"status":status,"resultRef":rr,"decision":status,"reviewer":"independent-review-agent","approvedAt":"2026-09-03T00:00:00Z"});write_yaml(self.index_path(root),idx)
        return plan,root/xr,root/rr

    def test_01_positive_baseline(self):self.assertEqual(CHECK.validate_repository(self.repo),[])
    def test_02_missing_plan(self):self.assert_invalid(lambda r:self.plan_path(r,"POC-001").unlink(),"missing POC plan")
    def test_03_poc_task_mismatch(self):
        def m(r):p=self.plan_path(r,"POC-001");d=load_yaml(p);d["taskId"]="POC-002";write_yaml(p,d)
        self.assert_invalid(m,"POC↔Task mismatch")
    def test_04_wrong_risk(self):
        def m(r):p=self.plan_path(r,"POC-003");d=load_yaml(p);d["riskLevel"]="high";write_yaml(p,d)
        self.assert_invalid(m,"riskLevel")
    def test_05_wrong_wave(self):
        def m(r):p=self.plan_path(r,"POC-005");d=load_yaml(p);d["wave"]="W9";write_yaml(p,d)
        self.assert_invalid(m,"wave")
    def test_06_wrong_requirement(self):
        def m(r):p=self.plan_path(r,"POC-006");d=load_yaml(p);d["requirementIds"]=["REQ-V1-0002"];write_yaml(p,d)
        self.assert_invalid(m,"requirementIds")
    def test_07_wrong_module(self):
        def m(r):p=self.plan_path(r,"POC-008");d=load_yaml(p);d["moduleIds"]=["MOD-AI"];write_yaml(p,d)
        self.assert_invalid(m,"moduleIds")
    def test_08_wrong_evidence_path(self):
        def m(r):p=self.plan_path(r,"POC-009");d=load_yaml(p);d["evidencePath"]="evidence/POC-008";write_yaml(p,d)
        self.assert_invalid(m,"evidencePath")
    def test_09_wrong_dependency(self):
        def m(r):p=self.plan_path(r,"POC-002");d=load_yaml(p);d["dependsOn"]=["GZ-010"];write_yaml(p,d)
        self.assert_invalid(m,"dependsOn")
    def test_10_duplicate_evidence_path(self):
        def m(r):p=self.plan_path(r,"POC-002");d=load_yaml(p);d["evidencePath"]="evidence/POC-001";write_yaml(p,d)
        self.assert_invalid(m,"duplicate POC evidence path")
    def test_11_unknown_resource(self):
        def m(r):p=self.plan_path(r,"POC-003");d=load_yaml(p);d["resourceIds"]=["RES-UNKNOWN"];write_yaml(p,d)
        self.assert_invalid(m,"unknown resource")
    def test_12_unknown_sample(self):
        def m(r):p=self.plan_path(r,"POC-004");d=load_yaml(p);d["sampleIds"]=["SAMPLE-UNKNOWN"];write_yaml(p,d)
        self.assert_invalid(m,"unknown sample")
    def test_13_plan_status_is_immutable(self):
        def m(r):p=self.plan_path(r,"POC-003");d=load_yaml(p);d["status"]="running";d["resultStatus"]="running";write_yaml(p,d)
        self.assert_invalid(m,"canonical plan")
    def test_14_prefilled_plan_command_rejected(self):
        def m(r):p=self.plan_path(r,"POC-005");d=load_yaml(p);d["protocol"]["commands"]=["x"];write_yaml(p,d)
        self.assert_invalid(m,"canonical plan")
    def test_15_prefilled_plan_measurement_rejected(self):
        def m(r):p=self.plan_path(r,"POC-009");d=load_yaml(p);d["protocol"]["measurements"][0]["actual"]=1;write_yaml(p,d)
        self.assert_invalid(m,"canonical plan")
    def test_16_prefilled_plan_decision_rejected(self):
        def m(r):p=self.plan_path(r,"POC-010");d=load_yaml(p);d["decision"]["status"]="pass";write_yaml(p,d)
        self.assert_invalid(m,"canonical plan")
    def test_17_prefilled_plan_reviewer_rejected(self):
        def m(r):p=self.plan_path(r,"POC-008");d=load_yaml(p);d["review"]["reviewer"]="x";write_yaml(p,d)
        self.assert_invalid(m,"canonical plan")
    def test_18_catalogue_sample_must_remain_pending(self):
        def m(r):p=r/"specs/poc/samples.yaml";d=load_yaml(p);d["samples"][0]["approvalState"]="approved";write_yaml(p,d)
        self.assert_invalid(m,"approvalState must remain pending")
    def test_19_catalogue_sample_identity_must_remain_tbd(self):
        def m(r):p=r/"specs/poc/samples.yaml";d=load_yaml(p);d["samples"][0]["immutableId"]="fixture-sample";write_yaml(p,d)
        self.assert_invalid(m,"immutableId must remain TBD")
    def test_20_required_measurement_cannot_be_removed(self):
        def m(r):p=self.plan_path(r,"POC-001");d=load_yaml(p);d["protocol"]["measurements"]=[x for x in d["protocol"]["measurements"] if x["id"]!="vm_reboot_recovery"];write_yaml(p,d)
        self.assert_invalid(m,"missing frozen required measurements")
    def test_21_poc002_encode_provenance_gate_cannot_be_removed(self):
        def m(r):p=self.plan_path(r,"POC-002");d=load_yaml(p);d["protocol"]["measurements"]=[x for x in d["protocol"]["measurements"] if x["id"]!="encode_provenance_complete"];write_yaml(p,d)
        self.assert_invalid(m,"missing frozen required measurements")
    def test_22_poc010_secret_roundtrip_gate_cannot_be_removed(self):
        def m(r):p=self.plan_path(r,"POC-010");d=load_yaml(p);d["protocol"]["measurements"]=[x for x in d["protocol"]["measurements"] if x["id"]!="secret_value_roundtrip"];write_yaml(p,d)
        self.assert_invalid(m,"missing frozen required measurements")
    def test_23_ai_provenance_capture_cannot_be_removed(self):
        def m(r):p=self.plan_path(r,"POC-009");d=load_yaml(p);d["environment"]["captureBeforeExecution"].remove("prompt_template_version");write_yaml(p,d)
        self.assert_invalid(m,"missing required environment provenance fields")
    def test_24_downstream_task_must_own_evidence_path(self):
        def m(r):p=self.pp_path(r);d=load_yaml(p);t=next(x for x in d["tasks"] if x["taskId"]=="POC-003");t["outputPaths"]=[x for x in t["outputPaths"] if not x.startswith("evidence/POC-003")];write_yaml(p,d)
        self.assert_invalid(m,"must own its Evidence path")
    def test_25_downstream_task_must_share_results_index(self):
        def m(r):p=self.pp_path(r);d=load_yaml(p);t=next(x for x in d["tasks"] if x["taskId"]=="POC-003");t["sharedPaths"]=[x for x in t.get("sharedPaths",[]) if x!="specs/poc/results-index.yaml"];write_yaml(p,d)
        self.assert_invalid(m,"must share specs/poc/results-index.yaml")
    def test_26_terminal_pass_fixture_is_valid(self):
        temp,root=self.temp_repo()
        try:self.make_terminal(root);self.assertEqual(CHECK.validate_repository(root),[])
        finally:temp.cleanup()
    def test_27_terminal_result_ref_must_exist(self):
        def m(r):_,_,result=self.make_terminal(r);result.unlink()
        self.assert_invalid(m,"terminal resultRef must point to an existing file")
    def test_28_terminal_execution_ref_must_exist(self):
        def m(r):_,execution,_=self.make_terminal(r);execution.unlink()
        self.assert_invalid(m,"executionRef must point to an existing file")
    def test_29_raw_evidence_must_exist(self):
        def m(r):_,execution,_=self.make_terminal(r);d=load_yaml(execution);(r/d["rawOutputRefs"][0]).unlink()
        self.assert_invalid(m,"raw evidence file must exist")
    def test_30_approval_ref_must_exist(self):
        def m(r):_,execution,_=self.make_terminal(r);d=load_yaml(execution);(r/d["samples"][0]["approvalRef"]).unlink()
        self.assert_invalid(m,"approvalRef must exist")
    def test_31_bad_checksum_rejected(self):
        def m(r):_,execution,_=self.make_terminal(r);d=load_yaml(execution);d["samples"][0]["checksum"]="x";write_yaml(execution,d)
        self.assert_invalid(m,"checksum must be sha256")
    def test_32_placeholder_immutable_id_rejected(self):
        def m(r):_,execution,_=self.make_terminal(r);d=load_yaml(execution);d["samples"][0]["immutableId"]="TBD";write_yaml(execution,d)
        self.assert_invalid(m,"immutableId")
    def test_33_empty_environment_value_rejected(self):
        def m(r):_,execution,_=self.make_terminal(r);d=load_yaml(execution);k=next(iter(d["environmentCaptured"]));d["environmentCaptured"][k]="";write_yaml(execution,d)
        self.assert_invalid(m,"empty/placeholder environment values")
    def test_34_placeholder_environment_value_rejected(self):
        def m(r):_,execution,_=self.make_terminal(r);d=load_yaml(execution);k=next(iter(d["environmentCaptured"]));d["environmentCaptured"][k]="TBD";write_yaml(execution,d)
        self.assert_invalid(m,"empty/placeholder environment values")
    def test_35_empty_string_measurement_rejected(self):
        def m(r):_,execution,_=self.make_terminal(r);d=load_yaml(execution);d["measurements"][0]["actual"]="";write_yaml(execution,d)
        self.assert_invalid(m,"invalid/placeholder measurement values")
    def test_36_nonfinite_measurement_rejected(self):
        def m(r):_,execution,_=self.make_terminal(r);d=load_yaml(execution);d["measurements"][0]["actual"]=float("inf");write_yaml(execution,d)
        self.assert_invalid(m,"invalid/placeholder measurement values")
    def test_37_pass_false_boolean_gate_rejected(self):
        def m(r):_,execution,_=self.make_terminal(r);d=load_yaml(execution);target=next(x for x in d["measurements"] if isinstance(x["actual"],bool));target["actual"]=False;write_yaml(execution,d)
        self.assert_invalid(m,"PASS has false/non-true boolean gates")
    def test_38_missing_measurement_rejected(self):
        def m(r):_,execution,_=self.make_terminal(r);d=load_yaml(execution);d["measurements"].pop();write_yaml(execution,d)
        self.assert_invalid(m,"measurement IDs must exactly match plan")
    def test_39_poc002_missing_input_hash_rejected(self):
        def m(r):_,execution,_=self.make_terminal(r,"POC-002");d=load_yaml(execution);d["provenance"].pop("input_sha256");write_yaml(execution,d)
        self.assert_invalid(m,"missing required provenance fields")
    def test_40_poc002_invalid_output_hash_rejected(self):
        def m(r):_,execution,_=self.make_terminal(r,"POC-002");d=load_yaml(execution);d["provenance"]["output_sha256"]="sha256:x";write_yaml(execution,d)
        self.assert_invalid(m,"provenance output_sha256")
    def test_41_poc002_empty_encoder_parameters_rejected(self):
        def m(r):_,execution,_=self.make_terminal(r,"POC-002");d=load_yaml(execution);d["provenance"]["encoder_parameters"]={};write_yaml(execution,d)
        self.assert_invalid(m,"encoder_parameters")
    def test_42_wrong_executor_rejected(self):
        def m(r):_,execution,_=self.make_terminal(r);d=load_yaml(execution);d["executor"]="independent-review-agent";write_yaml(execution,d)
        self.assert_invalid(m,"executor")
    def test_43_self_review_rejected(self):
        def m(r):_,execution,result=self.make_terminal(r);rd=load_yaml(result);rd["reviewer"]="task-owner-agent";write_yaml(result,rd);idx=load_yaml(self.index_path(r));e=next(x for x in idx["entries"] if x["taskId"]=="POC-003");e["reviewer"]="task-owner-agent";write_yaml(self.index_path(r),idx)
        self.assert_invalid(m,"reviewer")
    def test_44_result_index_metadata_mismatch_rejected(self):
        def m(r):self.make_terminal(r);idx=load_yaml(self.index_path(r));e=next(x for x in idx["entries"] if x["taskId"]=="POC-003");e["approvedAt"]="2026-09-04T00:00:00Z";write_yaml(self.index_path(r),idx)
        self.assert_invalid(m,"approvedAt")
    def test_45_nonterminal_fields_must_be_null(self):
        def m(r):idx=load_yaml(self.index_path(r));e=next(x for x in idx["entries"] if x["taskId"]=="POC-003");e["status"]="blocked";e["decision"]="pass";write_yaml(self.index_path(r),idx)
        self.assert_invalid(m,"nonterminal blocked decision must be null")
    def test_46_compound_secret_key_rejected(self):
        def m(r):p=r/"specs/poc/resources.yaml";d=load_yaml(p);d["resources"][0]["productionApiKeyValue"]="opaque";write_yaml(p,d)
        self.assert_invalid(m,"secret-like key")
    def test_47_compound_auth_token_key_rejected(self):
        def m(r):p=r/"specs/poc/resources.yaml";d=load_yaml(p);d["resources"][0]["authTokenValue"]="opaque";write_yaml(p,d)
        self.assert_invalid(m,"secret-like key")
    def test_48_secret_value_rejected(self):
        def m(r):_,execution,_=self.make_terminal(r);d=load_yaml(execution);d["commands"]=["tool --token=super-secret-value"];write_yaml(execution,d)
        self.assert_invalid(m,"secret-like value")
    def test_49_result_path_escape_rejected(self):
        def m(r):self.make_terminal(r);idx=load_yaml(self.index_path(r));e=next(x for x in idx["entries"] if x["taskId"]=="POC-003");e["resultRef"]="evidence/POC-003/../POC-999/result.yaml";write_yaml(self.index_path(r),idx)
        self.assert_invalid(m,"terminal resultRef")
    def test_50_raw_path_escape_rejected(self):
        def m(r):_,execution,_=self.make_terminal(r);d=load_yaml(execution);d["rawOutputRefs"]=["evidence/POC-003/../POC-999/raw.log"];write_yaml(execution,d)
        self.assert_invalid(m,"raw evidence file must exist")
    def test_51_symlink_escape_rejected(self):
        temp,root=self.temp_repo()
        try:
            _,execution,_=self.make_terminal(root);outside=root/"outside.log";outside.write_text("outside",encoding="utf-8");link=root/"evidence/POC-003/raw/link.log";link.unlink(missing_ok=True)
            try:link.symlink_to(outside)
            except OSError:self.skipTest("symlinks unavailable")
            d=load_yaml(execution);d["rawOutputRefs"]=["evidence/POC-003/raw/link.log"];write_yaml(execution,d);errors=CHECK.validate_repository(root);self.assertTrue(any("raw evidence file must exist" in x for x in errors),"\n".join(errors))
        finally:temp.cleanup()
    def test_52_fail_terminal_allows_false_boolean_gate(self):
        temp,root=self.temp_repo()
        try:self.make_terminal(root,"POC-003","fail");self.assertEqual(CHECK.validate_repository(root),[])
        finally:temp.cleanup()
    def test_53_program_manifest_requires_record_contracts(self):
        def m(r):p=r/"specs/poc/program.yaml";d=load_yaml(p);d["executionRecordSchema"]="wrong.yaml";write_yaml(p,d)
        self.assert_invalid(m,"executionRecordSchema")
    def test_54_policy_requires_immutable_plans(self):
        def m(r):p=r/"specs/poc/policy.yaml";d=load_yaml(p);d["canonicalPlansImmutable"]=False;write_yaml(p,d)
        self.assert_invalid(m,"canonicalPlansImmutable")

if __name__=="__main__":unittest.main(verbosity=2)
