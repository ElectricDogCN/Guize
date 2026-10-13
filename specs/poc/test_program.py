#!/usr/bin/env python3
"""Positive and negative tests for POC-PROTOCOL-V1."""

from __future__ import annotations

import importlib.util
import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import zlib
from unittest import mock
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("poc_check_program", HERE / "check_program.py")
CHECK = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(CHECK)


def load_yaml(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def write_yaml(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False, allow_unicode=True, width=120)


class TestPocProgram(unittest.TestCase):
    def setUp(self):
        self.repo = HERE.parents[1]

    def temp_repo(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        shutil.copytree(self.repo / "specs" / "poc", root / "specs" / "poc")
        coordination = root / "specs" / "coordination"
        coordination.mkdir(parents=True)
        shutil.copy2(
            self.repo / "specs" / "coordination" / "program-plan.yaml",
            coordination / "program-plan.yaml",
        )
        active = self.repo / "specs" / "coordination" / "active-work.yaml"
        if active.is_file():
            shutil.copy2(active, coordination / "active-work.yaml")
        requirements = root / "specs/requirements/v1"
        requirements.mkdir(parents=True)
        shutil.copy2(self.repo / "specs/requirements/v1/nfr.yaml", requirements / "nfr.yaml")
        return temp, root

    def assert_invalid(self, mutator, needle=None):
        temp, root = self.temp_repo()
        try:
            baseline_errors = CHECK.validate_repository(root)
            self.assertEqual(
                baseline_errors,
                [],
                "baseline fixture invalid before mutation:\n" + "\n".join(baseline_errors),
            )
            mutator(root)
            errors = CHECK.validate_repository(root)
            self.assertTrue(errors, "negative mutation unexpectedly passed")
            if needle:
                self.assertTrue(
                    any(needle in error for error in errors),
                    "\n".join(errors),
                )
        finally:
            temp.cleanup()

    def plan_path(self, root, task_id):
        return root / "specs" / "poc" / "plans" / f"{task_id}.yaml"

    def index_path(self, root):
        return root / "specs" / "poc" / "results-index.yaml"

    def pp_path(self, root):
        return root / "specs" / "coordination" / "program-plan.yaml"

    def task_path(self, root, task_id):
        return root / "specs" / "tasks" / f"{task_id}.md"

    def write_task_spec(self, root, task_id, implementer=None, reviewer=None):
        implementer = implementer or f"{task_id.lower()}-implementer"
        reviewer = reviewer or f"{task_id.lower()}-reviewer"
        path = self.task_path(root, task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "---\n"
            "schemaVersion: 2\n"
            f"id: {task_id}\n"
            "status: in_progress\n"
            "coordinationMode: registry\n"
            f"implementer: {implementer}\n"
            f"reviewer: {reviewer}\n"
            "---\n\n"
            f"# {task_id} fixture\n",
            encoding="utf-8",
        )
        return implementer, reviewer

    def make_terminal(self, root, task_id="POC-003", status="pass", profile="production"):
        plan = load_yaml(self.plan_path(root, task_id))
        route = CHECK.execution_route(plan, profile)
        implementer, reviewer = self.write_task_spec(root, task_id)
        evidence_dir = root / plan["evidencePath"]
        evidence_dir.mkdir(parents=True, exist_ok=True)

        resource_catalog = {
            item["id"]: item
            for item in load_yaml(root / "specs" / "poc" / "resources.yaml")["resources"]
        }
        resource_bindings = []
        for resource_id in route["resourceIds"]:
            configuration_ref = (
                f"{plan['evidencePath']}/resources/{resource_id}-configuration.yaml"
            )
            write_yaml(
                root / configuration_ref,
                {
                    "schemaVersion": 1,
                    "pocId": plan["pocId"],
                    "taskId": task_id,
                    "resourceId": resource_id,
                    "capturedAt": "2026-09-03T00:00:00Z",
                },
            )
            booking_ref = None
            if resource_catalog[resource_id].get("bookingRequired") is True:
                booking_ref = (
                    f"{plan['evidencePath']}/resources/{resource_id}-booking.yaml"
                )
                write_yaml(
                    root / booking_ref,
                    {
                        "schemaVersion": 1,
                        "pocId": plan["pocId"],
                        "taskId": task_id,
                        "resourceId": resource_id,
                        "status": "approved",
                    },
                )
            resource_bindings.append(
                {
                    "id": resource_id,
                    "configurationRef": configuration_ref,
                    "bookingRef": booking_ref,
                }
            )

        raw_ref = f"{plan['evidencePath']}/raw/execution.log"
        raw_path = root / raw_ref
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text("bounded raw output\n", encoding="utf-8")

        samples = []
        for sample_id in plan["sampleIds"]:
            checksum = "sha256:" + "b" * 64
            immutable_id = f"fixture-{sample_id.lower()}"
            approval_ref = f"{plan['evidencePath']}/approvals/{sample_id}.yaml"
            approval = {
                "schemaVersion": 1,
                "pocId": plan["pocId"],
                "taskId": task_id,
                "sampleId": sample_id,
                "immutableId": immutable_id,
                "checksum": checksum,
                "decision": "approved",
                "approver": f"{task_id.lower()}-sample-approver",
                "approvedAt": "2026-09-03T00:00:00Z",
            }
            write_yaml(root / approval_ref, approval)
            samples.append(
                {
                    "id": sample_id,
                    "immutableId": immutable_id,
                    "checksum": checksum,
                    "approved": True,
                    "approvalRef": approval_ref,
                }
            )

        environment = {
            key: (
                {"fixed": "value"}
                if key == "inference_parameters"
                else f"captured-{key}"
            )
            for key in route["captureBeforeExecution"]
        }
        profile_ref = f"{plan['evidencePath']}/profile-configuration.yaml"
        identity = CHECK.profile_identity(profile)
        environment.update(acceptanceProfile=identity, acceptanceProfileConfigurationRef=profile_ref)
        if task_id == 'POC-001':
            phone = dict(nodeId='fixture-android-node', deviceId='fixture-phone', physicalHostId='fixture-physical-phone', encoderBuild='fixture-av1-encoder', platform='android', isEmulator=False)
            environment['worker_node_inventory'] = [phone]
            environment['android_validation_scope'] = {**phone, 'status':'VALIDATED_ON_DEVICE', 'inputSha256':samples[0]['checksum'], 'outputSha256':'sha256:'+'c'*64, 'rawOutputRef':raw_ref}
            environment['android_thermal_background_observation'] = dict(deviceId=phone['deviceId'], temperaturePeakCelsius=38, powerPeakWatts=3, testDurationSeconds=60, backgroundSurvivedSeconds=60, rawOutputRef=raw_ref)
            if profile == 'local-v1':
                vm = dict(nodeId='fixture-vm-worker', guestId='fixture-android-guest', physicalHostId='fixture-host', encoderBuild='fixture-av1-encoder', hypervisor='fixture-hypervisor', guestOs='android', platform='android', isEmulator=True, isVirtualMachine=True)
                environment['worker_node_inventory'] = [vm]
                environment['vm_validation_scope'] = {**vm, 'status':'VALIDATED_ON_VM', 'physicalMultiHostValidated':False, 'inputSha256':samples[0]['checksum'], 'outputSha256':'sha256:'+'c'*64, 'rawOutputRef':raw_ref}
                environment['android_validation_scope'] = 'ANDROID_DEVICE_NOT_TESTED'
                environment['android_thermal_background_observation'] = 'ANDROID_DEVICE_NOT_TESTED'
        profile_configuration = {
            "pocId": plan['pocId'], "taskId": task_id, "acceptanceProfile": identity,
            "resourceIds": sorted(route['resourceIds']),
            "measurementIds": sorted(m['id'] for m in route['protocol']['measurements']),
        }
        if task_id == 'POC-006':
            scope = 'GENERIC_OPENLIST_SANDBOX' if profile == 'local-v1' else 'BAIDU_PRODUCTION_SANDBOX'
            profile_configuration['sourceValidationScope'] = scope
            environment['source_validation_scope'] = scope
        if task_id == 'POC-004' and profile == 'local-v1':
            capacity = dict(capacityBytes=1000, safetyFloorBytes=100, pauseFreeBytes=200,
                            resumeFreeBytes=300, maxReservedBytes=100)
            profile_configuration['localCapacity'] = capacity
            environment['capacity_watermark_configuration'] = capacity
        write_yaml(root / profile_ref, profile_configuration)

        measurements = []
        for measurement in route["protocol"]["measurements"]:
            actual = True if str(measurement["unit"]).lower() == "boolean" else 1
            if measurement['id'] == 'range_correctness':
                actual = 100
            if measurement['id'] == 'local_minimum_free_bytes':
                actual = 400
            elif measurement['id'] == 'local_maximum_reserved_bytes':
                actual = 50
            if status != "pass" and str(measurement["unit"]).lower() == "boolean":
                actual = False
            measurements.append({"id": measurement["id"], "actual": actual})

        provenance = {}
        if plan["pocId"] == "POC-02":
            provenance = {
                "input_sha256": samples[0]["checksum"],
                "output_sha256": "sha256:" + "c" * 64,
                "encoder_parameters": {
                    "codec": "av1",
                    "crf": 30,
                    "preset": "medium",
                },
            }

        execution_ref = f"{plan['evidencePath']}/execution.yaml"
        execution = {
            "schemaVersion": 1,
            "pocId": plan["pocId"],
            "taskId": task_id,
            "evidencePath": plan["evidencePath"],
            "executor": implementer,
            "resources": resource_bindings,
            "environmentCaptured": environment,
            "commands": [
                {
                    "command": "bounded-test-command --fixture approved",
                    "expectedExitCodes": [0],
                    "exitCode": 0,
                    "outputRef": raw_ref,
                }
            ],
            "rawOutputRefs": [raw_ref],
            "samples": samples,
            "measurements": measurements,
            "provenance": provenance,
            "complianceReviews": [],
            "notes": None,
        }
        required_reviews = [kind for kind in ('privacy','license') if plan['security'].get(kind+'ReviewRequired') is True]
        if required_reviews:
            for kind in required_reviews:
                ref = f"{plan['evidencePath']}/compliance/{kind}.yaml"
                version = CHECK.compliance_subject_version(plan,execution)
                scope = environment['source_validation_scope'] if task_id=='POC-006' else CHECK.PROFILE_SCOPES[profile]
                write_yaml(root/ref, dict(schemaVersion=1,pocId=plan['pocId'],taskId=task_id,
                    type=kind,subjectVersion=version,decision='approved',reviewer='source-compliance-reviewer',
                    approvedAt='2026-09-03T00:00:00Z',scope=scope))
                execution['complianceReviews'].append(dict(type=kind,subjectVersion=version,reviewRef=ref))
        write_yaml(root / execution_ref, execution)

        result_ref = f"{plan['evidencePath']}/result.yaml"
        result = {
            "schemaVersion": 1,
            "pocId": plan["pocId"],
            "taskId": task_id,
            "status": status,
            "evidencePath": plan["evidencePath"],
            "executionRef": execution_ref,
            "decision": status,
            "rationale": "fixture result backed by existing raw evidence and complete measurements",
            "reviewer": reviewer,
            "approvedAt": "2026-09-03T00:00:00Z",
            "approval": "approved",
        }
        write_yaml(root / result_ref, result)

        index = load_yaml(self.index_path(root))
        entry = next(item for item in index["entries"] if item["taskId"] == task_id)
        entry.update(
            {
                "status": status,
                "resultRef": result_ref,
                "decision": status,
                "reviewer": reviewer,
                "approvedAt": "2026-09-03T00:00:00Z",
            }
        )
        write_yaml(self.index_path(root), index)
        fixture_errors = CHECK.validate_repository(root)
        if fixture_errors:
            raise AssertionError(
                "terminal fixture invalid before mutation:\n"
                + "\n".join(fixture_errors)
            )
        return plan, root / execution_ref, root / result_ref

    def approval_path(self, root, execution_path):
        execution = load_yaml(execution_path)
        return root / execution["samples"][0]["approvalRef"]

    def make_profile_slot(self, root, task_id='POC-006', profile='local-v1', status='pass'):
        if not (root/'.git').exists():
            subprocess.run(['git','init','-q',str(root)],check=True)
            subprocess.run(['git','-C',str(root),'config','core.autocrlf','false'],check=True)
            (root/'fixture-tested-source.txt').write_text('Synthetic fixture code revision one; never platform execution evidence.\n',encoding='utf-8')
            for fixture_task in sorted(CHECK.TASKS): self.write_task_spec(root,fixture_task)
            self.write_task_spec(root,'GZ-020')
        plan = load_yaml(self.plan_path(root,task_id))
        ref = CHECK.profile_index_ref(task_id,profile)
        # Build the legacy fixture independently; later qualified slots never mutate its shared progress index.
        fixture,source_root = self.temp_repo()
        self.make_terminal(source_root,task_id,status=status,profile=profile)
        old_prefix = plan['evidencePath']
        source_dir = source_root/old_prefix
        sources = [p for p in source_dir.rglob('*') if p.is_file()]
        new_prefix = str(Path(ref).parent).replace('\\','/')
        folder = root/new_prefix
        production = profile == 'production'
        owner = 'GZ-020' if production else task_id
        implementer,reviewer = self.write_task_spec(root,owner)
        def relocate(value):
            if isinstance(value,dict):
                result = {k:relocate(v) for k,v in value.items()}
                if production:
                    if result.get('taskId') == task_id: result['taskId'] = owner
                    if result.get('evidencePath') == old_prefix: result['evidencePath'] = 'evidence/GZ-020'
                    if 'schemaVersion' in result: result['schemaVersion'] = 2
                    if 'executor' in result: result['executor'] = implementer
                    if 'reviewer' in result and 'executionRef' in result: result['reviewer'] = reviewer
                return result
            if isinstance(value,list): return [relocate(v) for v in value]
            if isinstance(value,str) and value.startswith(old_prefix+'/'):
                return new_prefix+value[len(old_prefix):]
            return value
        try:
            for source in sources:
                target = folder/source.relative_to(source_dir)
                target.parent.mkdir(parents=True,exist_ok=True)
                if source.suffix == '.yaml': write_yaml(target,relocate(load_yaml(source)))
                else: shutil.copy2(source,target)
            execution_path = folder/'execution.yaml'
            execution = load_yaml(execution_path)
            artifact_nodes = {}
            if execution['samples']:
                env=execution['environmentCaptured'];inputs=[]
                for sample in execution['samples']:
                    input_ref=new_prefix+'/inputs/'+sample['id']+'.bin'
                    target=root/input_ref;target.parent.mkdir(parents=True,exist_ok=True)
                    data=b'Synthetic input sample; never an actual experiment. '+sample['id'].encode()
                    target.write_bytes(data);checksum='sha256:'+hashlib.sha256(data).hexdigest()
                    sample['checksum']=checksum
                    approval=load_yaml(root/sample['approvalRef']);approval['checksum']=checksum;write_yaml(root/sample['approvalRef'],approval)
                    inputs.append(dict(sampleId=sample['id'],immutableId=sample['immutableId'],inputArtifactRef=input_ref,byteCount=len(data),sha256=checksum))
                env['inputSampleArtifacts']=inputs
                if task_id=='POC-001':
                    scope=env['android_validation_scope'] if production else env['vm_validation_scope'];scope['inputSha256']=execution['samples'][0]['checksum']
                elif task_id=='POC-002':execution['provenance']['input_sha256']=execution['samples'][0]['checksum']
            if not production:
                env=execution['environmentCaptured']
                if task_id=='POC-002':
                    env['segment_profile']=dict(schemaVersion=1,scope='LOCAL_FULL_V1',codec='av1',container='fmp4',segmentDurationSeconds=4,keyframeAligned=True)
                    env['scheduler_configuration']=dict(schemaVersion=1,scope='LOCAL_FULL_V1',priorities=dict(playback=0,prewarm=3,background=6),maxConcurrentSegments=2,perNodeConcurrency=1)
                elif task_id=='POC-005':
                    env['synthetic_hierarchy_manifest']=dict(schemaVersion=1,scope='LOCAL_FULL_V1',generator=dict(algorithm='deterministic-tree-v1',seed=42,rootPath='fixture-hierarchy',fileCount=1,directoryCount=1,maximumDepth=1))
                elif task_id=='POC-006':
                    observation_ref=new_prefix+'/raw/fault-observation.log'
                    (root/observation_ref).write_text('Synthetic exercised fixture cases: http_429 http_5xx network_disconnect auth_expired; never real POC evidence.\n',encoding='utf8')
                    execution['rawOutputRefs'].append(observation_ref)
                    env['injected_failure_matrix']=dict(schemaVersion=1,scope='LOCAL_FULL_V1',cases=[dict(caseId='fixture-'+fault,fault=fault,parameters=dict(injection='synthetic-only'),observation='exercised',rawOutputRef=observation_ref) for fault in ('http_429','http_5xx','network_disconnect','auth_expired')])
                elif task_id=='POC-007':
                    env['local_tls_path_configuration']=dict(schemaVersion=1,scope='LOCAL_FULL_V1',entryOrigin='https://guize.local',openlistOrigin='http://127.0.0.1:15525',reverseProxy='fixture-proxy-build',certificateIdentity='sha256:'+'c'*64,sandboxId='fixture-local-sandbox')
            if task_id == 'POC-001':
                # A typed synthetic media fixture, never evidence of an actual VM/device encode.
                env=execution['environmentCaptured']
                scope=env['vm_validation_scope'] if profile=='local-v1' else env['android_validation_scope']
                media_ref=new_prefix+'/raw/android-produced-media.bin'
                (root/media_ref).write_bytes(b'Synthetic Android output; never actual encoded media.\n')
                scope['rawOutputRef']=media_ref
                scope['outputSha256']='sha256:'+hashlib.sha256((root/media_ref).read_bytes()).hexdigest()
                artifact_nodes[media_ref]=scope['nodeId']
                execution['rawOutputRefs'].append(media_ref)
                if production:
                    observation_ref=new_prefix+'/raw/android-scope-observation.log'
                    (root/observation_ref).write_text('Synthetic observations only: temperaturePeakCelsius=38 powerPeakWatts=3 testDurationSeconds=60 backgroundSurvivedSeconds=60\n',encoding='utf8')
                    env['android_thermal_background_observation']['rawOutputRef']=observation_ref
                    artifact_nodes[observation_ref]=scope['nodeId']
                    execution['rawOutputRefs'].append(observation_ref)
                    if status=='pass':
                        soak_ref=new_prefix+'/raw/passthrough-soak-observation.log'
                        (root/soak_ref).write_text('Synthetic continuous passthrough fixture only; never actual POC acceptance. Observed 2026-09-03T00:00:00Z through 2026-09-05T00:00:00Z.\n',encoding='utf8')
                        execution['rawOutputRefs'].append(soak_ref)
                        env['productionPassthroughSoak']=dict(schemaVersion=1,configurationRef=execution['resources'][0]['configurationRef'],minimumContinuousDays=2,observedStartedAt='2026-09-03T00:00:00Z',observedFinishedAt='2026-09-05T00:00:00Z',rawOutputRef=soak_ref)
                        next(m for m in execution['measurements'] if m['id']=='multi_day_stability_duration')['actual']=48
            if task_id == 'POC-004' and production:
                next(m for m in execution['measurements'] if m['id']=='minimum_free_space_gib')['actual']=500
            if task_id == 'POC-002':
                # Schema fixtures only: these bytes do not claim to be encoded media.
                env = execution['environmentCaptured']
                nodes = [dict(nodeId='fixture-'+platform,platform=platform,physicalHostId='fixture-same-host',encoderBuild='fixture-av1-build',compatibilityGroupId='fixture-av1-group') for platform in ('windows','linux')]
                env['worker_node_inventory'] = nodes
                env['physical_host_scope'] = dict(physicalHostIds=['fixture-same-host'],physicalMultiHostValidated=False)
                env['encoder_capability_matrix'] = [dict(nodeId=node['nodeId'],encoderBuild=node['encoderBuild'],compatibilityGroupId=node['compatibilityGroupId'],codec='av1',supported=True) for node in nodes]
                media_ref = new_prefix+'/raw/produced-media.bin'
                (root/media_ref).write_bytes(b'Synthetic schema fixture, never actual AV1 media.\n')
                env['producedMediaArtifactRef'] = media_ref
                execution['provenance']['output_sha256'] = 'sha256:'+hashlib.sha256((root/media_ref).read_bytes()).hexdigest()
                execution['rawOutputRefs'].append(media_ref)
                runs = []
                for part_index,node in enumerate(nodes):
                    log_ref = new_prefix+'/raw/'+node['nodeId']+'.txt'
                    output_ref = new_prefix+'/raw/'+node['nodeId']+'.bin'
                    (root/log_ref).write_text('Synthetic node trace, never actual encode execution.\n',encoding='utf8')
                    (root/output_ref).write_bytes(b'Synthetic per-worker media fixture.\n'+node['nodeId'].encode())
                    execution['rawOutputRefs'].extend([log_ref,output_ref])
                    artifact_nodes[log_ref] = artifact_nodes[output_ref] = node['nodeId']
                    runs.append(dict(nodeId=node['nodeId'],encoderBuild=node['encoderBuild'],compatibilityGroupId=node['compatibilityGroupId'],inputSampleId=execution['samples'][0]['id'],inputSha256=execution['samples'][0]['checksum'],sourceStartFrame=part_index*60,sourceEndFrame=(part_index+1)*60,outputSha256='sha256:'+hashlib.sha256((root/output_ref).read_bytes()).hexdigest(),rawOutputRef=log_ref,outputArtifactRef=output_ref,startedAt='2026-09-03T00:00:00Z',finishedAt='2026-09-03T00:01:00Z'))
                env['workerEncodeExecutions'] = runs
                validation_ref=new_prefix+'/raw/assembled-decode-report.yaml'
                parts=[{key:run[key] for key in ('nodeId','outputArtifactRef','outputSha256','sourceStartFrame','sourceEndFrame')} for run in runs]
                assembly=dict(schemaVersion=1,inputSampleId=execution['samples'][0]['id'],inputSha256=execution['samples'][0]['checksum'],sourceFrameCount=120,outputArtifactRef=media_ref,outputSha256=execution['provenance']['output_sha256'],parts=parts,validationRef=validation_ref,decoderBuild='synthetic-fixture-decoder; never actual media validation')
                env['parallelMediaAssembly']=assembly
                report={key:assembly[key] for key in ('schemaVersion','inputSampleId','inputSha256','sourceFrameCount','outputSha256','parts','decoderBuild')}
                report.update(decodedFrameCount=120,decodeErrorCount=0,timelineDiscontinuityCount=0)
                write_yaml(root/validation_ref,report)
                execution['rawOutputRefs'].append(validation_ref)
            if subprocess.run(['git','-C',str(root),'rev-parse','--verify','HEAD'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode:
                # Freeze all prepared fixture inputs, including actual specifications and Task Specs.
                subprocess.run(['git','-C',str(root),'add','--','.'],check=True)
                subprocess.run(['git','-C',str(root),'-c','user.name=POC Fixture','-c','user.email=poc-fixture@guize.invalid','commit','-q','-m','synthetic fixture source'],check=True)
            tested_source = {key:subprocess.check_output(['git','-C',str(root),'rev-parse',ref],text=True).strip() for key,ref in (('commit','HEAD'),('tree','HEAD^{tree}'))}
            execution['environmentCaptured']['testedSource'] = tested_source
            execution['environmentCaptured']['rawExecutionArtifacts'] = [
                dict(ref=raw_ref,artifactType='produced_media' if task_id in ('POC-001','POC-002') and raw_ref.endswith('.bin') else 'scope_observation' if (task_id=='POC-001' and production and raw_ref.endswith('/android-scope-observation.log')) or (task_id=='POC-006' and not production and raw_ref.endswith('/fault-observation.log')) else 'command_output',byteCount=len((root/raw_ref).read_bytes()),
                     sha256='sha256:'+hashlib.sha256((root/raw_ref).read_bytes()).hexdigest(),
                     **({'nodeId':artifact_nodes[raw_ref]} if raw_ref in artifact_nodes else {}))
                for raw_ref in execution['rawOutputRefs']]
            if task_id=='POC-002':
                next(record for record in execution['environmentCaptured']['rawExecutionArtifacts'] if record['ref']==validation_ref)['artifactType']='measurement_output'
            if task_id=='POC-001' and production and status=='pass':
                next(record for record in execution['environmentCaptured']['rawExecutionArtifacts'] if record['ref']==soak_ref)['artifactType']='scope_observation'
            execution['environmentCaptured']['executionWindow'] = dict(startedAt='2026-09-03T00:00:00Z', finishedAt='2026-09-04T00:00:00Z')
            common = dict(schemaVersion=2,pocId=plan['pocId'],taskId=owner,acceptanceProfile=CHECK.profile_identity(profile),status='approved',approvedBy=reviewer,approvedAt='2026-09-02T00:00:00Z',validFrom='2026-09-02T00:00:00Z',validUntil='2026-09-04T00:00:00Z')
            if task_id=='POC-001' and production and status=='pass':
                execution['environmentCaptured']['executionWindow']['finishedAt']='2026-09-05T00:00:00Z'
                common['validUntil']='2026-09-05T00:00:00Z'
            for resource in execution['resources']:
                write_yaml(root/resource['configurationRef'],{**common,'kind':'resource_configuration','resourceId':resource['id'],'configuration':{'build':'fixture-versioned-configuration'}})
                if resource['bookingRef'] is not None:
                    write_yaml(root/resource['bookingRef'],{**common,'kind':'resource_booking','resourceId':resource['id']})
            if task_id=='POC-001' and production and status=='pass':
                floor_path=root/execution['environmentCaptured']['productionPassthroughSoak']['configurationRef']
                floor_record=load_yaml(floor_path)
                floor_record['configuration']['productionPassthroughSoak']=dict(minimumContinuousDays=2)
                write_yaml(floor_path,floor_record)
            selected_route = CHECK.execution_route(plan,profile)
            config_ref = execution['environmentCaptured']['acceptanceProfileConfigurationRef']
            config = load_yaml(root/config_ref)
            config['testedSource'] = tested_source
            config.update(schemaVersion=2,decision='approved',approvedBy=reviewer,approvedAt='2026-09-02T00:00:00Z',capturedSettings={key:execution['environmentCaptured'][key] for key in CHECK.LOCAL_STRUCTURED_CAPTURES.get(plan['pocId'],{})} if not production else {})
            refs = {}
            known = CHECK.NONNEGATIVE_UNITS | {'boolean','percent','ratio','celsius'}
            captured = {key:execution['environmentCaptured'][key] for key in selected_route['captureBeforeExecution']}
            for metric in selected_route['protocol']['measurements']:
                if metric['unit'] in known:
                    continue
                mid = metric['id']
                domain_ref = new_prefix+'/domains/'+mid+'-review.yaml'
                definition_ref = new_prefix+'/domains/'+mid+'-definition.txt'
                (root/definition_ref).parent.mkdir(parents=True,exist_ok=True)
                (root/definition_ref).write_text('Approved synthetic fixture scale; not a production quality threshold.\n',encoding='utf-8')
                domain = dict(mode='finite',minimum=None,maximum=None,integral=False) if mid=='translation_comet' else dict(mode='bounded',minimum=0,maximum=100 if metric['unit']=='VMAF' or mid=='translation_bleu' else 5 if metric['unit']=='ordinal' else 1,integral=False)
                write_yaml(root/domain_ref,dict(schemaVersion=2,kind='measurement_domain_review',pocId=plan['pocId'],taskId=owner,acceptanceProfile=CHECK.profile_identity(profile),measurementId=mid,unit=metric['unit'],environmentCaptured=captured,domain=domain,definitionRef=definition_ref,decision='approved',reviewer=reviewer,approvedAt='2026-09-02T00:00:00Z'))
                refs[mid] = domain_ref
            config['numericDomainReviewRefs'] = refs
            write_yaml(root/config_ref,config)
            write_yaml(execution_path,execution)
            result_path = folder/'result.yaml'
            result = load_yaml(result_path)
            result['approvedAt'] = '2026-09-04T00:02:00Z'
            if task_id=='POC-001' and production and status=='pass':result['approvedAt']='2026-09-05T00:02:00Z'
            write_yaml(result_path,result)
            write_yaml(root/ref,dict(schemaVersion=2,pocId=plan['pocId'],pocTaskId=task_id,
                ownerTask=owner,acceptanceProfile=CHECK.profile_identity(profile),
                resultRef=new_prefix+'/result.yaml'))
        finally:
            fixture.cleanup()
        return root/ref

    def test_01_positive_baseline(self):
        self.assertEqual(CHECK.validate_repository(self.repo), [])

    def test_02_missing_plan(self):
        self.assert_invalid(
            lambda root: self.plan_path(root, "POC-001").unlink(),
            "missing POC plan",
        )

    def test_03_poc_task_mismatch(self):
        def mutate(root):
            path = self.plan_path(root, "POC-001")
            data = load_yaml(path)
            data["taskId"] = "POC-002"
            write_yaml(path, data)
        self.assert_invalid(mutate, "POC↔Task mismatch")

    def test_04_wrong_risk(self):
        def mutate(root):
            path = self.plan_path(root, "POC-003")
            data = load_yaml(path)
            data["riskLevel"] = "high"
            write_yaml(path, data)
        self.assert_invalid(mutate, "riskLevel")

    def test_05_wrong_wave(self):
        def mutate(root):
            path = self.plan_path(root, "POC-005")
            data = load_yaml(path)
            data["wave"] = "W9"
            write_yaml(path, data)
        self.assert_invalid(mutate, "wave")

    def test_06_wrong_requirement(self):
        def mutate(root):
            path = self.plan_path(root, "POC-006")
            data = load_yaml(path)
            data["requirementIds"] = ["REQ-V1-0002"]
            write_yaml(path, data)
        self.assert_invalid(mutate, "requirementIds")

    def test_07_wrong_module(self):
        def mutate(root):
            path = self.plan_path(root, "POC-008")
            data = load_yaml(path)
            data["moduleIds"] = ["MOD-AI"]
            write_yaml(path, data)
        self.assert_invalid(mutate, "moduleIds")

    def test_08_wrong_evidence_path(self):
        def mutate(root):
            path = self.plan_path(root, "POC-009")
            data = load_yaml(path)
            data["evidencePath"] = "evidence/POC-008"
            write_yaml(path, data)
        self.assert_invalid(mutate, "evidencePath")

    def test_09_wrong_dependency(self):
        def mutate(root):
            path = self.plan_path(root, "POC-002")
            data = load_yaml(path)
            data["dependsOn"] = ["GZ-010"]
            write_yaml(path, data)
        self.assert_invalid(mutate, "dependsOn")

    def test_10_duplicate_evidence_path(self):
        def mutate(root):
            path = self.plan_path(root, "POC-002")
            data = load_yaml(path)
            data["evidencePath"] = "evidence/POC-001"
            write_yaml(path, data)
        self.assert_invalid(mutate, "duplicate POC evidence path")

    def test_11_unknown_resource(self):
        def mutate(root):
            path = self.plan_path(root, "POC-003")
            data = load_yaml(path)
            data["resourceIds"] = ["RES-UNKNOWN"]
            write_yaml(path, data)
        self.assert_invalid(mutate, "unknown resource")

    def test_12_unknown_sample(self):
        def mutate(root):
            path = self.plan_path(root, "POC-004")
            data = load_yaml(path)
            data["sampleIds"] = ["SAMPLE-UNKNOWN"]
            write_yaml(path, data)
        self.assert_invalid(mutate, "unknown sample")

    def test_13_plan_status_is_immutable(self):
        def mutate(root):
            path = self.plan_path(root, "POC-003")
            data = load_yaml(path)
            data["status"] = "running"
            data["resultStatus"] = "running"
            write_yaml(path, data)
        self.assert_invalid(mutate, "canonical plan")

    def test_14_prefilled_plan_command_rejected(self):
        def mutate(root):
            path = self.plan_path(root, "POC-005")
            data = load_yaml(path)
            data["protocol"]["commands"] = ["x"]
            write_yaml(path, data)
        self.assert_invalid(mutate, "canonical plan")

    def test_15_prefilled_plan_measurement_rejected(self):
        def mutate(root):
            path = self.plan_path(root, "POC-009")
            data = load_yaml(path)
            data["protocol"]["measurements"][0]["actual"] = 1
            write_yaml(path, data)
        self.assert_invalid(mutate, "canonical plan")

    def test_16_prefilled_plan_decision_rejected(self):
        def mutate(root):
            path = self.plan_path(root, "POC-010")
            data = load_yaml(path)
            data["decision"]["status"] = "pass"
            write_yaml(path, data)
        self.assert_invalid(mutate, "canonical plan")

    def test_17_prefilled_plan_reviewer_rejected(self):
        def mutate(root):
            path = self.plan_path(root, "POC-008")
            data = load_yaml(path)
            data["review"]["reviewer"] = "x"
            write_yaml(path, data)
        self.assert_invalid(mutate, "canonical plan")

    def test_18_catalogue_sample_must_remain_pending(self):
        def mutate(root):
            path = root / "specs" / "poc" / "samples.yaml"
            data = load_yaml(path)
            data["samples"][0]["approvalState"] = "approved"
            write_yaml(path, data)
        self.assert_invalid(mutate, "approvalState must remain pending")

    def test_19_catalogue_sample_identity_must_remain_tbd(self):
        def mutate(root):
            path = root / "specs" / "poc" / "samples.yaml"
            data = load_yaml(path)
            data["samples"][0]["immutableId"] = "fixture-sample"
            write_yaml(path, data)
        self.assert_invalid(mutate, "immutableId must remain TBD")

    def test_20_required_measurement_cannot_be_removed(self):
        def mutate(root):
            path = self.plan_path(root, "POC-001")
            data = load_yaml(path)
            data["protocol"]["measurements"] = [
                item for item in data["protocol"]["measurements"]
                if item["id"] != "vm_reboot_recovery"
            ]
            write_yaml(path, data)
        self.assert_invalid(mutate, "missing frozen required measurements")

    def test_21_poc002_encode_provenance_gate_cannot_be_removed(self):
        def mutate(root):
            path = self.plan_path(root, "POC-002")
            data = load_yaml(path)
            data["protocol"]["measurements"] = [
                item for item in data["protocol"]["measurements"]
                if item["id"] != "encode_provenance_complete"
            ]
            write_yaml(path, data)
        self.assert_invalid(mutate, "missing frozen required measurements")

    def test_22_poc010_secret_roundtrip_gate_cannot_be_removed(self):
        def mutate(root):
            path = self.plan_path(root, "POC-010")
            data = load_yaml(path)
            data["protocol"]["measurements"] = [
                item for item in data["protocol"]["measurements"]
                if item["id"] != "secret_value_roundtrip"
            ]
            write_yaml(path, data)
        self.assert_invalid(mutate, "missing frozen required measurements")

    def test_23_ai_provenance_capture_cannot_be_removed(self):
        def mutate(root):
            path = self.plan_path(root, "POC-009")
            data = load_yaml(path)
            data["environment"]["captureBeforeExecution"].remove("prompt_template_version")
            write_yaml(path, data)
        self.assert_invalid(mutate, "missing required environment provenance fields")

    def test_24_downstream_task_must_own_evidence_path(self):
        def mutate(root):
            path = self.pp_path(root)
            data = load_yaml(path)
            task = next(item for item in data["tasks"] if item["taskId"] == "POC-003")
            task["outputPaths"] = [
                item for item in task["outputPaths"]
                if not item.startswith("evidence/POC-003")
            ]
            write_yaml(path, data)
        self.assert_invalid(mutate, "must own its Evidence path")

    def test_25_downstream_task_must_share_results_index(self):
        def mutate(root):
            path = self.pp_path(root)
            data = load_yaml(path)
            task = next(item for item in data["tasks"] if item["taskId"] == "POC-003")
            task["sharedPaths"] = [
                item for item in task.get("sharedPaths", [])
                if item != "specs/poc/results-index.yaml"
            ]
            write_yaml(path, data)
        self.assert_invalid(mutate, "must share specs/poc/results-index.yaml")

    def test_26_terminal_pass_fixture_is_valid(self):
        temp, root = self.temp_repo()
        try:
            self.make_terminal(root)
            self.assertEqual(CHECK.validate_repository(root), [])
        finally:
            temp.cleanup()

    def test_27_terminal_result_ref_must_exist(self):
        def mutate(root):
            _, _, result = self.make_terminal(root)
            result.unlink()
        self.assert_invalid(mutate, "terminal resultRef must point to an existing file")

    def test_28_terminal_execution_ref_must_exist(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            execution.unlink()
        self.assert_invalid(mutate, "executionRef must point to an existing file")

    def test_29_raw_evidence_must_exist(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            (root / data["rawOutputRefs"][0]).unlink()
        self.assert_invalid(mutate, "raw evidence file must exist")

    def test_30_approval_ref_must_exist(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            self.approval_path(root, execution).unlink()
        self.assert_invalid(mutate, "approvalRef must exist")

    def test_31_bad_checksum_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["samples"][0]["checksum"] = "x"
            write_yaml(execution, data)
        self.assert_invalid(mutate, "checksum must be sha256")

    def test_32_placeholder_immutable_id_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["samples"][0]["immutableId"] = "TBD"
            write_yaml(execution, data)
        self.assert_invalid(mutate, "immutableId")

    def test_33_empty_environment_value_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            key = next(iter(data["environmentCaptured"]))
            data["environmentCaptured"][key] = ""
            write_yaml(execution, data)
        self.assert_invalid(mutate, "empty/placeholder environment values")

    def test_34_placeholder_environment_value_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            key = next(iter(data["environmentCaptured"]))
            data["environmentCaptured"][key] = "TBD"
            write_yaml(execution, data)
        self.assert_invalid(mutate, "empty/placeholder environment values")

    def test_35_empty_string_measurement_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["measurements"][0]["actual"] = ""
            write_yaml(execution, data)
        self.assert_invalid(mutate, "invalid/placeholder measurement values")

    def test_36_nonfinite_measurement_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["measurements"][0]["actual"] = float("inf")
            write_yaml(execution, data)
        self.assert_invalid(mutate, "invalid/placeholder measurement values")

    def test_37_pass_false_boolean_gate_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            target = next(
                item for item in data["measurements"]
                if isinstance(item["actual"], bool)
            )
            target["actual"] = False
            write_yaml(execution, data)
        self.assert_invalid(mutate, "PASS has false/non-true boolean gates")

    def test_38_missing_measurement_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["measurements"].pop()
            write_yaml(execution, data)
        self.assert_invalid(mutate, "measurement IDs must exactly match plan")

    def test_39_poc002_missing_input_hash_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, "POC-002")
            data = load_yaml(execution)
            data["provenance"].pop("input_sha256")
            write_yaml(execution, data)
        self.assert_invalid(mutate, "missing required provenance fields")

    def test_40_poc002_invalid_output_hash_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, "POC-002")
            data = load_yaml(execution)
            data["provenance"]["output_sha256"] = "sha256:x"
            write_yaml(execution, data)
        self.assert_invalid(mutate, "provenance output_sha256")

    def test_41_poc002_empty_encoder_parameters_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, "POC-002")
            data = load_yaml(execution)
            data["provenance"]["encoder_parameters"] = {}
            write_yaml(execution, data)
        self.assert_invalid(mutate, "encoder_parameters")

    def test_42_wrong_executor_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["executor"] = "another-implementer"
            write_yaml(execution, data)
        self.assert_invalid(mutate, "executor")

    def test_43_self_review_rejected(self):
        def mutate(root):
            _, execution, result = self.make_terminal(root)
            executor = load_yaml(execution)["executor"]
            result_data = load_yaml(result)
            result_data["reviewer"] = executor
            write_yaml(result, result_data)
            index = load_yaml(self.index_path(root))
            entry = next(item for item in index["entries"] if item["taskId"] == "POC-003")
            entry["reviewer"] = executor
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "reviewer")

    def test_44_result_index_metadata_mismatch_rejected(self):
        def mutate(root):
            self.make_terminal(root)
            index = load_yaml(self.index_path(root))
            entry = next(item for item in index["entries"] if item["taskId"] == "POC-003")
            entry["approvedAt"] = "2026-09-04T00:00:00Z"
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "approvedAt")

    def test_45_nonterminal_fields_must_be_null(self):
        def mutate(root):
            index = load_yaml(self.index_path(root))
            entry = next(item for item in index["entries"] if item["taskId"] == "POC-003")
            entry["status"] = "blocked"
            entry["decision"] = "pass"
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "nonterminal blocked decision must be null")

    def test_46_compound_secret_key_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "resources.yaml"
            data = load_yaml(path)
            data["resources"][0]["productionApiKeyValue"] = "opaque"
            write_yaml(path, data)
        self.assert_invalid(mutate, "secret-like key")

    def test_47_compound_auth_token_key_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "resources.yaml"
            data = load_yaml(path)
            data["resources"][0]["authTokenValue"] = "opaque"
            write_yaml(path, data)
        self.assert_invalid(mutate, "secret-like key")

    def test_48_secret_value_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["commands"][0]["command"] = "tool --token=super-secret-value"
            write_yaml(execution, data)
        self.assert_invalid(mutate, "secret-like value")

    def test_49_result_path_escape_rejected(self):
        def mutate(root):
            self.make_terminal(root)
            index = load_yaml(self.index_path(root))
            entry = next(item for item in index["entries"] if item["taskId"] == "POC-003")
            entry["resultRef"] = "evidence/POC-003/../POC-999/result.yaml"
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "terminal resultRef")

    def test_50_raw_path_escape_rejected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["rawOutputRefs"] = ["evidence/POC-003/../POC-999/raw.log"]
            write_yaml(execution, data)
        self.assert_invalid(mutate, "raw evidence file must exist")

    def test_51_symlink_escape_rejected(self):
        temp, root = self.temp_repo()
        try:
            _, execution, _ = self.make_terminal(root)
            outside = root / "outside.log"
            outside.write_text("outside", encoding="utf-8")
            link = root / "evidence" / "POC-003" / "raw" / "link.log"
            link.unlink(missing_ok=True)
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("symlinks unavailable")
            data = load_yaml(execution)
            data["rawOutputRefs"] = ["evidence/POC-003/raw/link.log"]
            write_yaml(execution, data)
            errors = CHECK.validate_repository(root)
            self.assertTrue(
                any("raw evidence file must exist" in error for error in errors),
                "\n".join(errors),
            )
        finally:
            temp.cleanup()

    def test_52_fail_terminal_allows_false_boolean_gate(self):
        temp, root = self.temp_repo()
        try:
            self.make_terminal(root, "POC-003", "fail")
            self.assertEqual(CHECK.validate_repository(root), [])
        finally:
            temp.cleanup()

    def test_53_program_manifest_requires_record_contracts(self):
        def mutate(root):
            path = root / "specs" / "poc" / "program.yaml"
            data = load_yaml(path)
            data["executionRecordSchema"] = "wrong.yaml"
            write_yaml(path, data)
        self.assert_invalid(mutate, "executionRecordSchema")

    def test_54_policy_requires_immutable_plans(self):
        def mutate(root):
            path = root / "specs" / "poc" / "policy.yaml"
            data = load_yaml(path)
            data["canonicalPlansImmutable"] = False
            write_yaml(path, data)
        self.assert_invalid(mutate, "canonicalPlansImmutable")

    def test_55_missing_concrete_task_spec_rejected(self):
        def mutate(root):
            self.make_terminal(root)
            self.task_path(root, "POC-003").unlink()
        self.assert_invalid(mutate, "concrete Task Spec is required")

    def test_56_generic_role_labels_rejected(self):
        def mutate(root):
            _, execution, result = self.make_terminal(root)
            self.write_task_spec(
                root,
                "POC-003",
                implementer="task-owner-agent",
                reviewer="independent-review-agent",
            )
            execution_data = load_yaml(execution)
            execution_data["executor"] = "task-owner-agent"
            write_yaml(execution, execution_data)
            result_data = load_yaml(result)
            result_data["reviewer"] = "independent-review-agent"
            write_yaml(result, result_data)
            index = load_yaml(self.index_path(root))
            entry = next(item for item in index["entries"] if item["taskId"] == "POC-003")
            entry["reviewer"] = "independent-review-agent"
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "must not reuse generic Program role labels")

    def test_57_task_spec_self_review_rejected(self):
        def mutate(root):
            _, execution, result = self.make_terminal(root)
            executor = load_yaml(execution)["executor"]
            self.write_task_spec(
                root, "POC-003", implementer=executor, reviewer=executor
            )
            result_data = load_yaml(result)
            result_data["reviewer"] = executor
            write_yaml(result, result_data)
            index = load_yaml(self.index_path(root))
            entry = next(item for item in index["entries"] if item["taskId"] == "POC-003")
            entry["reviewer"] = executor
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "implementer and reviewer must be distinct")

    def test_58_active_work_role_drift_rejected(self):
        def mutate(root):
            self.make_terminal(root)
            path = root / "specs" / "coordination" / "active-work.yaml"
            active = load_yaml(path) if path.is_file() else {
                "version": 1, "policy": {}, "tasks": []
            }
            active.setdefault("tasks", []).append(
                {
                    "taskId": "POC-003",
                    "implementer": "drifted-implementer",
                    "reviewer": "poc-003-reviewer",
                }
            )
            write_yaml(path, active)
        self.assert_invalid(mutate, "Active Work implementer does not match Task Spec")

    def test_59_safe_credential_metadata_requires_false(self):
        def mutate(root):
            path = root / "specs" / "poc" / "resources.yaml"
            data = load_yaml(path)
            data["resources"][0]["credentialsStoredInRepository"] = "opaque-secret"
            write_yaml(path, data)
        self.assert_invalid(mutate, "secret-like key")

    def test_60_approval_decision_must_be_approved(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            path = self.approval_path(root, execution)
            data = load_yaml(path)
            data["decision"] = "denied"
            write_yaml(path, data)
        self.assert_invalid(mutate, "sample approval")

    def test_61_approval_checksum_must_match_execution_sample(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            path = self.approval_path(root, execution)
            data = load_yaml(path)
            data["checksum"] = "sha256:" + "d" * 64
            write_yaml(path, data)
        self.assert_invalid(mutate, "checksum must equal")

    def test_62_approval_approver_must_differ_from_implementer(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            executor = load_yaml(execution)["executor"]
            path = self.approval_path(root, execution)
            data = load_yaml(path)
            data["approver"] = executor
            write_yaml(path, data)
        self.assert_invalid(mutate, "approver must differ")

    def test_63_approval_timestamp_must_be_real_utc_instant(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            path = self.approval_path(root, execution)
            data = load_yaml(path)
            data["approvedAt"] = "2026-99-99T99:99:99Z"
            write_yaml(path, data)
        self.assert_invalid(mutate, "valid UTC instant")

    def test_64_ai_model_identity_must_be_text(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, "POC-009")
            data = load_yaml(execution)
            data["environmentCaptured"]["model_identity"] = True
            write_yaml(execution, data)
        self.assert_invalid(mutate, "AI provenance model_identity")

    def test_65_ai_model_version_must_be_text(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, "POC-009")
            data = load_yaml(execution)
            data["environmentCaptured"]["model_version"] = 1
            write_yaml(execution, data)
        self.assert_invalid(mutate, "AI provenance model_version")

    def test_66_poc002_input_hash_must_match_approved_sample(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, "POC-002")
            data = load_yaml(execution)
            data["provenance"]["input_sha256"] = "sha256:" + "d" * 64
            write_yaml(execution, data)
        self.assert_invalid(mutate, "must match an approved execution sample checksum")

    def test_67_high_risk_running_concurrency_is_limited(self):
        def mutate(root):
            index = load_yaml(self.index_path(root))
            for task_id in ("POC-001", "POC-002"):
                entry = next(item for item in index["entries"] if item["taskId"] == task_id)
                entry["status"] = "running"
                self.write_task_spec(root, task_id)
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "running high/critical POC count")

    def test_68_critical_poc_runs_standalone(self):
        def mutate(root):
            index = load_yaml(self.index_path(root))
            for task_id in ("POC-010", "POC-003"):
                entry = next(item for item in index["entries"] if item["taskId"] == task_id)
                entry["status"] = "running"
                self.write_task_spec(root, task_id)
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "critical POC must run standalone")

    def test_69_duplicate_resource_id_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "resources.yaml"
            data = load_yaml(path)
            data["resources"].append(dict(data["resources"][0]))
            write_yaml(path, data)
        self.assert_invalid(mutate, "duplicate id")

    def test_70_missing_resource_id_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "resources.yaml"
            data = load_yaml(path)
            data["resources"][0].pop("id")
            write_yaml(path, data)
        self.assert_invalid(mutate, "requires nonempty id")

    def test_71_duplicate_sample_id_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "samples.yaml"
            data = load_yaml(path)
            data["samples"].append(dict(data["samples"][0]))
            write_yaml(path, data)
        self.assert_invalid(mutate, "duplicate id")

    def test_72_missing_sample_id_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "samples.yaml"
            data = load_yaml(path)
            data["samples"][0].pop("id")
            write_yaml(path, data)
        self.assert_invalid(mutate, "requires nonempty id")

    def test_73_missing_execution_template_rejected(self):
        def mutate(root):
            (root / "specs" / "poc" / "templates" / "execution-record.yaml").unlink()
        self.assert_invalid(mutate, "executionRecordTemplate")

    def test_74_missing_approval_template_rejected(self):
        def mutate(root):
            (root / "specs" / "poc" / "templates" / "sample-approval.yaml").unlink()
        self.assert_invalid(mutate, "sampleApprovalTemplate")

    def test_75_duplicate_yaml_mapping_key_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "program.yaml"
            with path.open("a", encoding="utf-8") as handle:
                handle.write("executionEnabled: true\n")
        self.assert_invalid(mutate, "duplicate key")

    def test_76_downstream_task_cannot_own_immutable_poc_plan(self):
        def mutate(root):
            path = self.pp_path(root)
            data = load_yaml(path)
            task = next(item for item in data["tasks"] if item["taskId"] == "POC-003")
            task["outputPaths"].append("specs/poc/plans/POC-003.yaml")
            write_yaml(path, data)
        self.assert_invalid(mutate, "may not own immutable specs/poc paths")

    def test_77_result_timestamp_must_be_valid(self):
        def mutate(root):
            _, _, result = self.make_terminal(root)
            result_data = load_yaml(result)
            result_data["approvedAt"] = "2026-99-99T99:99:99Z"
            write_yaml(result, result_data)
            index = load_yaml(self.index_path(root))
            entry = next(item for item in index["entries"] if item["taskId"] == "POC-003")
            entry["approvedAt"] = "2026-99-99T99:99:99Z"
            write_yaml(self.index_path(root), index)
        self.assert_invalid(mutate, "valid UTC instant")

    def test_78_row_ownership_rejects_other_task_change(self):
        base = load_yaml(self.repo / "specs" / "poc" / "results-index.yaml")
        current = yaml.safe_load(yaml.safe_dump(base))
        entry = next(item for item in current["entries"] if item["taskId"] == "POC-004")
        entry["status"] = "running"
        errors = []
        CHECK.validate_result_index_row_ownership(base, current, "POC-003", errors)
        self.assertTrue(any("changed other task rows" in error for error in errors), errors)

    def test_79_row_ownership_allows_only_own_row_change(self):
        base = load_yaml(self.repo / "specs" / "poc" / "results-index.yaml")
        current = yaml.safe_load(yaml.safe_dump(base))
        entry = next(item for item in current["entries"] if item["taskId"] == "POC-003")
        entry["status"] = "running"
        errors = []
        CHECK.validate_result_index_row_ownership(base, current, "POC-003", errors)
        self.assertEqual(errors, [])

    def test_80_template_missing_required_key_rejected(self):
        def mutate(root):
            path = root / "specs" / "poc" / "templates" / "result-record.yaml"
            data = load_yaml(path)
            data.pop("reviewer")
            write_yaml(path, data)
        self.assert_invalid(mutate, "template missing keys")


    def test_81_command_exit_code_must_be_expected(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["commands"][0]["exitCode"] = 9
            write_yaml(execution, data)
        self.assert_invalid(mutate, "exitCode must be one of expectedExitCodes")

    def test_82_command_output_ref_must_be_listed(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["commands"][0]["outputRef"] = data["resources"][0]["configurationRef"]
            write_yaml(execution, data)
        self.assert_invalid(mutate, "outputRef must be listed in rawOutputRefs")

    def test_83_execution_resources_must_match_plan(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            data["resources"][0]["id"] = "RES-ARBITRARY"
            write_yaml(execution, data)
        self.assert_invalid(mutate, "resource IDs must exactly match plan")

    def test_84_resource_configuration_ref_must_exist(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            (root / data["resources"][0]["configurationRef"]).unlink()
        self.assert_invalid(mutate, "configurationRef must point to an existing file")

    def test_85_booking_ref_required_for_booked_resource(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, "POC-002")
            data = load_yaml(execution)
            data["resources"][0]["bookingRef"] = None
            write_yaml(execution, data)
        self.assert_invalid(mutate, "bookingRef must point to an existing file")


    def test_86_every_frozen_measurement_id_is_required(self):
        for poc_id, required_ids in sorted(CHECK.REQUIRED_MEASUREMENTS.items()):
            task_id = f"POC-{int(poc_id.split('-')[1]):03d}"
            for measurement_id in sorted(required_ids):
                with self.subTest(pocId=poc_id, measurementId=measurement_id):
                    temp, root = self.temp_repo()
                    try:
                        baseline = CHECK.validate_repository(root)
                        self.assertEqual(baseline, [], "\n".join(baseline))
                        path = self.plan_path(root, task_id)
                        data = load_yaml(path)
                        data["protocol"]["measurements"] = [
                            item for item in data["protocol"]["measurements"]
                            if item["id"] != measurement_id
                        ]
                        write_yaml(path, data)
                        errors = CHECK.validate_repository(root)
                        self.assertTrue(
                            any("missing frozen required measurements" in error for error in errors),
                            "\n".join(errors),
                        )
                    finally:
                        temp.cleanup()


    def test_87_local_terminal_routes_and_shared_ai_protocol(self):
        for task_id in ("POC-001", "POC-002", "POC-004", "POC-006", "POC-007", "POC-009"):
            with self.subTest(task=task_id):
                temp, root = self.temp_repo()
                try:
                    self.make_terminal(root, task_id, profile="local-v1")
                    self.assertEqual(CHECK.validate_repository(root), [])
                finally:
                    temp.cleanup()

    def test_88_execution_profile_identity_required_and_exact(self):
        for key, value in (("id", "unknown"), ("version", 2), ("version", True),
                           ("bindingRevision", 2), ("scope", "PRODUCTION_RELEASE")):
            with self.subTest(key=key, value=value):
                def mutate(root):
                    _, execution, _ = self.make_terminal(root, "POC-002", profile="local-v1")
                    data = load_yaml(execution)
                    data["environmentCaptured"]["acceptanceProfile"][key] = value
                    write_yaml(execution, data)
                self.assert_invalid(mutate, "acceptanceProfile")

    def test_89_local_result_cannot_be_promoted_to_production(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, "POC-002", profile="local-v1")
            data = load_yaml(execution)
            data["environmentCaptured"]["acceptanceProfile"] = CHECK.profile_identity("production")
            write_yaml(execution, data)
        self.assert_invalid(mutate, "profile configuration must bind")

    def test_90_profile_configuration_binds_task_resources_and_measurements(self):
        for key, value in (("taskId", "POC-004"), ("pocId", "POC-04"),
                           ("resourceIds", ["RES-A380-ENCODE"]), ("measurementIds", [])):
            with self.subTest(key=key):
                def mutate(root):
                    _, execution, _ = self.make_terminal(root, "POC-002", profile="local-v1")
                    ref = load_yaml(execution)["environmentCaptured"]["acceptanceProfileConfigurationRef"]
                    configuration = load_yaml(root / ref)
                    configuration[key] = value
                    write_yaml(root / ref, configuration)
                self.assert_invalid(mutate, "profile configuration must bind")

    def test_91_profile_configuration_must_exist_under_own_evidence(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root)
            data = load_yaml(execution)
            ref = "evidence/POC-002/stolen-profile.yaml"
            write_yaml(root / ref, {"copied": "other task"})
            data["environmentCaptured"]["acceptanceProfileConfigurationRef"] = ref
            write_yaml(execution, data)
        self.assert_invalid(mutate, "acceptanceProfileConfigurationRef must exist under task Evidence")

    def test_92_generic_local_source_route_cannot_be_removed_by_deferral(self):
        def mutate(root):
            path = self.plan_path(root, "POC-006")
            data = load_yaml(path)
            data["localValidation"]["mode"] = "deferred"
            write_yaml(path, data)
        self.assert_invalid(mutate, "mode/version does not match authorized route")

    def test_93_generic_local_source_cannot_claim_baidu_production_scope(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, 'POC-006', profile='local-v1')
            data = load_yaml(execution)
            ref = data['environmentCaptured']['acceptanceProfileConfigurationRef']
            configuration = load_yaml(root / ref)
            configuration['sourceValidationScope'] = 'BAIDU_PRODUCTION_SANDBOX'
            data['environmentCaptured']['source_validation_scope'] = 'BAIDU_PRODUCTION_SANDBOX'
            write_yaml(root / ref, configuration)
            write_yaml(execution, data)
        self.assert_invalid(mutate, 'source_validation_scope must match')

    def test_94_shared_local_security_measurement_cannot_be_removed(self):
        def mutate(root):
            path = self.plan_path(root, "POC-002")
            data = load_yaml(path)
            protocol = data["localValidation"]["protocol"]
            protocol['measurements'] = [m for m in protocol['measurements'] if m['id'] != 'hls_acl_and_revocation']
            write_yaml(path, data)
        self.assert_invalid(mutate, "missing required local measurements")

    def test_95_program_profile_binding_cannot_drift(self):
        def mutate(root):
            path = root / 'specs/poc/program.yaml'
            data = load_yaml(path)
            data['acceptanceProfileBinding']['profiles'][0]['acceptanceIds'][-1] = 'ACCEPT-SOURCE-SYNC'
            write_yaml(path, data)
        self.assert_invalid(mutate, "preserve original full 10 requirements and 12 acceptances")

    def test_96_local_resource_route_cannot_substitute_production_hardware(self):
        def mutate(root):
            path = self.plan_path(root, "POC-004")
            data = load_yaml(path)
            data['localValidation']['resourceIds'] = ['RES-TRUENAS-SANDBOX']
            write_yaml(path, data)
        self.assert_invalid(mutate, "resource IDs must match authorized local route")

    def test_97_local_safety_gate_unit_drift_cannot_bypass_true(self):
        def mutate(root):
            path = self.plan_path(root, 'POC-002')
            plan = load_yaml(path)
            gate = next(m for m in plan['localValidation']['protocol']['measurements'] if m['id'] == 'hls_acl_and_revocation')
            gate['unit'] = 'ordinal'
            write_yaml(path, plan)
        self.assert_invalid(mutate, 'unit must remain boolean')

    def test_98_local_capacity_requires_typed_positive_ordered_watermarks(self):
        for key, value in (('safetyFloorBytes', 0), ('safetyFloorBytes', True),
                           ('pauseFreeBytes', 50), ('resumeFreeBytes', 1200), ('maxReservedBytes', -1)):
            with self.subTest(key=key, value=value):
                def mutate(root):
                    _, execution, _ = self.make_terminal(root, 'POC-004', profile='local-v1')
                    data = load_yaml(execution)
                    ref = data['environmentCaptured']['acceptanceProfileConfigurationRef']
                    configuration = load_yaml(root / ref)
                    configuration['localCapacity'][key] = value
                    data['environmentCaptured']['capacity_watermark_configuration'] = configuration['localCapacity']
                    write_yaml(root / ref, configuration)
                    write_yaml(execution, data)
                self.assert_invalid(mutate, 'local capacity')

    def test_99_local_capacity_measurements_must_preserve_actual_floor(self):
        for measurement, actual in (('local_minimum_free_bytes', 0),
                                    ('local_minimum_free_bytes', 120),
                                    ('local_maximum_reserved_bytes', 101),
                                    ('local_maximum_reserved_bytes', True)):
            with self.subTest(measurement=measurement, actual=actual):
                def mutate(root):
                    _, execution, _ = self.make_terminal(root, 'POC-004', profile='local-v1')
                    data = load_yaml(execution)
                    next(m for m in data['measurements'] if m['id'] == measurement)['actual'] = actual
                    write_yaml(execution, data)
                self.assert_invalid(mutate, 'local capacity')

    def test_100_local_capacity_configuration_must_match_environment(self):
        def mutate(root):
            _, execution, _ = self.make_terminal(root, 'POC-004', profile='local-v1')
            data = load_yaml(execution)
            data['environmentCaptured']['capacity_watermark_configuration']['safetyFloorBytes'] = 50
            write_yaml(execution, data)
        self.assert_invalid(mutate, 'environment capacity configuration must match')

    def test_101_profile_configuration_boolean_versions_are_not_integers(self):
        for key in ('version', 'bindingRevision'):
            with self.subTest(key=key):
                def mutate(root):
                    _, execution, _ = self.make_terminal(root, 'POC-002', profile='local-v1')
                    ref = load_yaml(execution)['environmentCaptured']['acceptanceProfileConfigurationRef']
                    configuration = load_yaml(root / ref)
                    configuration['acceptanceProfile'][key] = True
                    write_yaml(root / ref, configuration)
                self.assert_invalid(mutate, 'profile configuration version/revision must be integers')

    def test_102_local_source_pass_requires_actual_compliance_records(self):
        def mutate(root):
            _,execution,_ = self.make_terminal(root,'POC-006',profile='local-v1')
            data = load_yaml(execution)
            data['complianceReviews'] = []
            write_yaml(execution,data)
        self.assert_invalid(mutate,'PASS requires privacy/license review references')

    def test_103_compliance_records_bind_version_scope_and_file(self):
        for mutation in ('version','scope','missing_file','same_executor'):
            with self.subTest(mutation=mutation):
                def mutate(root):
                    _,execution,_ = self.make_terminal(root,'POC-006',profile='local-v1')
                    data = load_yaml(execution)
                    ref = root/data['complianceReviews'][0]['reviewRef']
                    review = load_yaml(ref)
                    if mutation == 'missing_file':
                        ref.unlink()
                        return
                    if mutation == 'version': review['subjectVersion'] = 'other-version'
                    if mutation == 'scope': review['scope'] = 'BAIDU_PRODUCTION_SANDBOX'
                    if mutation == 'same_executor': review['reviewer'] = data['executor']
                    write_yaml(ref,review)
                self.assert_invalid(mutate,'compliance')

    def test_104_range_pass_requires_complete_correctness_on_both_profiles(self):
        for profile in ('local-v1','production'):
            for actual in (0,-1,99,101):
                with self.subTest(profile=profile,actual=actual):
                    def mutate(root):
                        _,execution,_ = self.make_terminal(root,profile=profile)
                        data = load_yaml(execution)
                        next(m for m in data['measurements'] if m['id']=='range_correctness')['actual'] = actual
                        write_yaml(execution,data)
                    self.assert_invalid(mutate,'Range')

    def test_105_required_local_provenance_cannot_be_dropped(self):
        def mutate(root):
            path = self.plan_path(root,'POC-001')
            data = load_yaml(path)
            data['localValidation']['captureBeforeExecution'].remove('physical_host_scope')
            write_yaml(path,data)
        self.assert_invalid(mutate,'missing required local environment fields')

    def test_106_local_slot_cannot_satisfy_production_contract(self):
        temp,root = self.temp_repo()
        try:
            self.make_profile_slot(root)
            self.assertEqual(CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-06'}),[])
            errors = CHECK.validate_repository(root,'production',True,selected_pocs={'POC-06'})
            self.assertTrue(any('selected profile index is required' in e for e in errors),errors)
        finally: temp.cleanup()

    def test_107_production_slot_coexists_without_replacing_closed_local_evidence(self):
        temp,root = self.temp_repo()
        try:
            local = self.make_profile_slot(root)
            task_spec = self.task_path(root,'POC-006')
            task_spec.write_text(task_spec.read_text(encoding='utf-8').replace('status: in_progress','status: completed'),encoding='utf-8')
            old_files = {str(p.relative_to(root)):p.read_bytes() for p in (root/'evidence/POC-006').rglob('*') if p.is_file()}
            self.make_profile_slot(root,profile='production')
            for ref,content in old_files.items(): self.assertEqual((root/ref).read_bytes(),content)
            self.assertEqual(CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-06'}),[])
            self.assertEqual(CHECK.validate_repository(root,'production',True,selected_pocs={'POC-06'}),[])
        finally: temp.cleanup()

    def test_108_full_production_milestone_cannot_use_subset_or_local_profile(self):
        temp,root = self.temp_repo()
        try:
            self.make_profile_slot(root,profile='production')
            errors = CHECK.validate_repository(root,'production',True,'GZ-020')
            self.assertTrue(any('POC-001/production: selected profile index is required' in e for e in errors),errors)
            errors = CHECK.validate_repository(root,'local-v1',True,'GZ-020',{'POC-06'})
            self.assertTrue(any('milestone must bind' in e for e in errors),errors)
            self.assertTrue(any('cannot select a POC subset' in e for e in errors),errors)
        finally: temp.cleanup()

    def test_109_production_compatibility_measurements_and_owner_are_required(self):
        def mutate(root):
            path = self.plan_path(root,'POC-001')
            data = load_yaml(path)
            data['protocol']['measurements'] = [m for m in data['protocol']['measurements'] if m['id'] != 'android_thermal_background_profiled']
            write_yaml(path,data)
        self.assert_invalid(mutate,'missing production compatibility measurements')

    def test_110_profile_slot_cannot_claim_another_owner_or_scope(self):
        temp,root = self.temp_repo()
        try:
            ref = self.make_profile_slot(root,profile='production')
            self.assertEqual(CHECK.validate_repository(root,'production',True,selected_pocs={'POC-06'}),[])
            data = load_yaml(ref)
            data['ownerTask'] = 'POC-006'
            write_yaml(ref,data)
            errors = CHECK.validate_repository(root,'production',True,selected_pocs={'POC-06'})
            self.assertTrue(any('index must bind exact' in e for e in errors),errors)
        finally: temp.cleanup()

    def test_111_declared_ai_and_recovery_reviews_cannot_be_boolean_only(self):
        for task_id in ('POC-009','POC-010'):
            with self.subTest(task=task_id):
                def mutate(root):
                    _,execution,_ = self.make_terminal(root,task_id,profile='local-v1')
                    data = load_yaml(execution)
                    data['complianceReviews'] = []
                    write_yaml(execution,data)
                self.assert_invalid(mutate,'PASS requires privacy/license review references')


    def test_112_local_storage_requires_authenticated_range_and_hash_gates(self):
        for gate in ('local_authenticated_reads', 'local_range_correctness', 'local_read_hash_verified'):
            with self.subTest(gate=gate):
                def mutate(root):
                    path = self.plan_path(root, 'POC-004')
                    plan = load_yaml(path)
                    self.assertIn(gate, {m['id'] for m in plan['localValidation']['protocol']['measurements']})
                    plan['localValidation']['protocol']['measurements'] = [m for m in plan['localValidation']['protocol']['measurements'] if m['id'] != gate]
                    write_yaml(path, plan)
                self.assert_invalid(mutate, 'missing required local measurements')

    def test_113_local_capacity_pass_requires_exercised_positive_reservations(self):
        for zero_budget in (False, True):
            with self.subTest(zero_budget=zero_budget):
                def mutate(root):
                    _, execution, _ = self.make_terminal(root, 'POC-004', profile='local-v1')
                    data = load_yaml(execution)
                    next(m for m in data['measurements'] if m['id'] == 'local_maximum_reserved_bytes')['actual'] = 0
                    if zero_budget:
                        ref = data['environmentCaptured']['acceptanceProfileConfigurationRef']
                        config = load_yaml(root / ref)
                        config['localCapacity']['maxReservedBytes'] = 0
                        data['environmentCaptured']['capacity_watermark_configuration'] = config['localCapacity']
                        write_yaml(root / ref, config)
                    write_yaml(execution, data)
                self.assert_invalid(mutate, 'local capacity')


    def test_114_local_source_reviews_cannot_survive_openlist_version_drift(self):
        for key in ('openlist_version', 'provider_api_or_sdk_version'):
            with self.subTest(key=key):
                def mutate(root):
                    _, execution, _ = self.make_terminal(root, 'POC-006', profile='local-v1')
                    data = load_yaml(execution)
                    data['environmentCaptured'][key] = 'different-captured-version'
                    write_yaml(execution, data)
                self.assert_invalid(mutate, 'review subjectVersion')


    def test_115_qualified_raw_output_cannot_reference_another_experiment_slot(self):
        for profile in ('local-v1', 'production'):
            with self.subTest(profile=profile):
                temp, root = self.temp_repo()
                try:
                    index_path = self.make_profile_slot(root, profile=profile)
                    self.assertEqual(CHECK.validate_repository(root, profile, True, selected_pocs={'POC-06'}), [])
                    index = load_yaml(index_path)
                    result = load_yaml(root / index['resultRef'])
                    execution_path = root / result['executionRef']
                    execution = load_yaml(execution_path)
                    owner = 'POC-006' if profile == 'local-v1' else 'GZ-020'
                    outside = f'evidence/{owner}/unqualified/raw/unrelated-experiment.log'
                    (root / outside).parent.mkdir(parents=True)
                    (root / outside).write_text('unrelated experiment output', encoding='utf-8')
                    old_ref = execution['rawOutputRefs'][0]
                    execution['rawOutputRefs'][0] = outside
                    for command in execution['commands']:
                        if command['outputRef'] == old_ref:
                            command['outputRef'] = outside
                    write_yaml(execution_path, execution)
                    errors = CHECK.validate_repository(root, profile, True, selected_pocs={'POC-06'})
                    self.assertTrue(any('raw evidence file must exist' in e for e in errors), errors)
                finally:
                    temp.cleanup()


    def test_116_qualified_resource_refs_cannot_escape_selected_slot(self):
        for profile in ('local-v1', 'production'):
            for field in ('configurationRef', 'bookingRef'):
                with self.subTest(profile=profile, field=field):
                    temp, root = self.temp_repo()
                    try:
                        index_path = self.make_profile_slot(root, profile=profile)
                        self.assertEqual(CHECK.validate_repository(root, profile, True, selected_pocs={'POC-06'}), [])
                        result = load_yaml(root / load_yaml(index_path)['resultRef'])
                        execution_path = root / result['executionRef']
                        execution = load_yaml(execution_path)
                        owner = 'POC-006' if profile == 'local-v1' else 'GZ-020'
                        outside = f'evidence/{owner}/unqualified/{field}.yaml'
                        (root / outside).parent.mkdir(parents=True)
                        (root / outside).write_text('record: unrelated experiment\n', encoding='utf-8')
                        execution['resources'][0][field] = outside
                        write_yaml(execution_path, execution)
                        errors = CHECK.validate_repository(root, profile, True, selected_pocs={'POC-06'})
                        self.assertTrue(any(f'{field} must' in e for e in errors), errors)
                    finally:
                        temp.cleanup()


    def test_117_ai_reviews_bind_model_and_tested_tool_stack(self):
        for profile in ('local-v1','production'):
            for key in ('model_identity','model_version','runtime','tool_versions'):
                with self.subTest(profile=profile,key=key):
                    def mutate(root):
                        _, execution, _ = self.make_terminal(root,'POC-009',profile=profile)
                        data = load_yaml(execution)
                        data['environmentCaptured'][key] = 'different-tested-provider-or-build'
                        write_yaml(execution,data)
                    self.assert_invalid(mutate,'review subjectVersion')

    def test_118_qualified_counts_sizes_rates_and_latencies_reject_impossible_values(self):
        for profile in ('local-v1','production'):
            temp,root = self.temp_repo()
            try:
                index = self.make_profile_slot(root,'POC-005',profile)
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-05'}),[])
                result = load_yaml(root/load_yaml(index)['resultRef'])
                path = root/result['executionRef']
                original = path.read_text(encoding='utf-8')
                for mid,value in (('file_count',-1),('file_count',1.5),('directory_count',-1),('directory_depth_max',1.5),('average_file_size',-1),('enumeration_rate',-1),('source_api_quota',-1),('incremental_scan_cost',-1),('memory_peak',-1)):
                    with self.subTest(profile=profile,metric=mid,value=value):
                        path.write_text(original,encoding='utf-8')
                        data = load_yaml(path)
                        next(m for m in data['measurements'] if m['id']==mid)['actual'] = value
                        write_yaml(path,data)
                        errors = CHECK.validate_repository(root,profile,True,selected_pocs={'POC-05'})
                        self.assertTrue(any(mid in e and 'invalid/placeholder measurement values' in e for e in errors),errors)
            finally: temp.cleanup()

    def test_119_local_vm_encoding_and_production_phone_observations_are_distinct(self):
        for profile in ('local-v1','production'):
            temp,root = self.temp_repo()
            try:
                index = self.make_profile_slot(root,'POC-001',profile)
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-01'}),[])
                result = load_yaml(root/load_yaml(index)['resultRef'])
                path = root/result['executionRef']
                original = path.read_text(encoding='utf-8')
                mutations = ('untested','wrong_guest','wrong_hash','phone_claim') if profile == 'local-v1' else ('untested','emulator','wrong_device','empty_background')
                for mutation in mutations:
                    with self.subTest(profile=profile,mutation=mutation):
                        path.write_text(original,encoding='utf-8')
                        data = load_yaml(path);env=data['environmentCaptured']
                        if profile == 'local-v1':
                            if mutation=='untested':env['vm_validation_scope']='VM_NOT_TESTED'
                            elif mutation=='wrong_guest':env['vm_validation_scope']['guestId']='another-guest'
                            elif mutation=='wrong_hash':env['vm_validation_scope']['inputSha256']='sha256:'+'d'*64
                            else:env['android_validation_scope']='VALIDATED_ON_DEVICE'
                        elif mutation=='untested':env['android_validation_scope']='ANDROID_DEVICE_NOT_TESTED'
                        elif mutation=='emulator':env['android_validation_scope']['isEmulator']=True
                        elif mutation=='wrong_device':env['android_thermal_background_observation']['deviceId']='another-phone'
                        else:env['android_thermal_background_observation']['testDurationSeconds']=0
                        write_yaml(path,data)
                        errors = CHECK.validate_repository(root,profile,True,selected_pocs={'POC-01'})
                        self.assertTrue(any(('actual VM' if profile=='local-v1' else 'actual Android') in e for e in errors),errors)
            finally: temp.cleanup()

    def test_120_qualified_resource_records_require_identity_approval_and_execution_validity(self):
        temp,root = self.temp_repo()
        try:
            index = self.make_profile_slot(root,'POC-001','production')
            self.assertEqual(CHECK.validate_repository(root,'production',True,selected_pocs={'POC-01'}),[])
            result = load_yaml(root/load_yaml(index)['resultRef']);execution=load_yaml(root/result['executionRef'])
            resource = execution['resources'][0]
            for field in ('configurationRef','bookingRef'):
                path = root/resource[field];original=path.read_text(encoding='utf-8')
                for mutation in ('rejected','wrong_resource','wrong_owner','wrong_profile','expired','self_approved'):
                    with self.subTest(field=field,mutation=mutation):
                        path.write_text(original,encoding='utf-8');data=load_yaml(path)
                        if mutation=='rejected':data['status']='rejected'
                        elif mutation=='wrong_resource':data['resourceId']='another-resource'
                        elif mutation=='wrong_owner':data['taskId']='POC-001'
                        elif mutation=='wrong_profile':data['acceptanceProfile']=CHECK.profile_identity('local-v1')
                        elif mutation=='self_approved':data['approvedBy']=execution['executor']
                        else:data.update(validFrom='2026-09-01T00:00:00Z',validUntil='2026-09-02T00:00:00Z')
                        write_yaml(path,data)
                        errors=CHECK.validate_repository(root,'production',True,selected_pocs={'POC-01'})
                        self.assertTrue(any('qualified resource' in e for e in errors),errors)
                path.write_text(original,encoding='utf-8')
        finally:temp.cleanup()

    def test_121_metric_domains_preserve_valid_error_ratios_and_model_specific_scores(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-009','local-v1')
            self.assertEqual(CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-09'}),[])
            result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_text(encoding='utf-8')
            for mid,value,valid in (('asr_wer',2.0,True),('asr_cer',2.0,True),('speaker_der',1.2,True),('translation_comet',-0.3,True),('retrieval_recall',1.1,False),('ocr_accuracy',1.1,False),('quality_score',1.1,False)):
                with self.subTest(metric=mid,value=value):
                    path.write_text(original,encoding='utf-8');data=load_yaml(path)
                    next(m for m in data['measurements'] if m['id']==mid)['actual']=value;write_yaml(path,data)
                    errors=CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-09'})
                    self.assertEqual(not errors,valid,errors)
            self.assertTrue(CHECK.good_actual('celsius',-10))
            self.assertTrue(CHECK.good_actual('bytes',1.5,'average_file_size'))
        finally:temp.cleanup()

    def test_122_qualified_window_and_scale_reviews_cannot_be_missing_or_relabelled(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-002','local-v1')
            self.assertEqual(CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-02'}),[])
            result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_text(encoding='utf-8')
            data=load_yaml(path);config_path=root/data['environmentCaptured']['acceptanceProfileConfigurationRef'];config_original=config_path.read_text(encoding='utf-8')
            domain_path=root/load_yaml(config_path)['numericDomainReviewRefs']['av1_quality'];domain_original=domain_path.read_text(encoding='utf-8')
            for mutation in ('bad_window','missing_domain','wrong_environment','late_approval','reversed_bounds'):
                with self.subTest(mutation=mutation):
                    path.write_text(original,encoding='utf-8');config_path.write_text(config_original,encoding='utf-8');domain_path.write_text(domain_original,encoding='utf-8')
                    if mutation=='bad_window':
                        data=load_yaml(path);data['environmentCaptured']['executionWindow']=[];write_yaml(path,data)
                    elif mutation=='missing_domain':
                        data=load_yaml(config_path);data['numericDomainReviewRefs']={};write_yaml(config_path,data)
                    else:
                        data=load_yaml(domain_path)
                        if mutation=='wrong_environment':data['environmentCaptured']['tool_versions']='another-metric-build'
                        elif mutation=='late_approval':data['approvedAt']='2026-09-04T00:00:00Z'
                        else:data['domain'].update(minimum=110,maximum=100)
                        write_yaml(domain_path,data)
                    self.assertTrue(CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-02'}))
        finally:temp.cleanup()


    def test_123_review_environment_preserves_types_and_explicit_model_ranges(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-002','local-v1')
            result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];execution=load_yaml(path)
            config=load_yaml(root/execution['environmentCaptured']['acceptanceProfileConfigurationRef'])
            domain_path=root/config['numericDomainReviewRefs']['av1_quality'];domain=load_yaml(domain_path)
            execution['environmentCaptured']['memory']=1;domain['environmentCaptured']['memory']=1
            write_yaml(path,execution);write_yaml(domain_path,domain)
            self.assertEqual(CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-02'}),[])
            domain['environmentCaptured']['memory']=True;write_yaml(domain_path,domain)
            self.assertTrue(any('bind exact' in e for e in CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-02'})))
            domain['environmentCaptured']['memory']=1;write_yaml(domain_path,domain)
            next(m for m in execution['measurements'] if m['id']=='av1_quality')['actual']=110;write_yaml(path,execution)
            self.assertTrue(any('violates approved numeric domain' in e for e in CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-02'})))
            domain['domain']['maximum']=110;write_yaml(domain_path,domain)
            (root/domain['definitionRef']).write_text('Explicit approved synthetic model range0..110; not a frozen performance target.\n',encoding='utf-8')
            self.assertEqual(CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-02'}),[])
        finally:temp.cleanup()


    def test_124_resource_fail_records_capture_expiry_without_authorizing_pass(self):
        temp, root = self.temp_repo()
        try:
            index = self.make_profile_slot(root, 'POC-001', 'production')
            result = load_yaml(root/load_yaml(index)['resultRef'])
            execution = load_yaml(root/result['executionRef'])
            plan = load_yaml(self.plan_path(root,'POC-001'))
            plan['taskId'] = 'GZ-020'
            for resource in execution['resources']:
                for field in ('configurationRef','bookingRef'):
                    if resource.get(field) is None:
                        continue
                    path = root/resource[field]
                    data = load_yaml(path)
                    data.update(status='expired', validFrom='2026-09-01T00:00:00Z', validUntil='2026-09-02T00:00:00Z')
                    write_yaml(path,data)
            defs = load_yaml(root/'specs/poc/program.schema.yaml')['$defs']
            prefix = str(Path(load_yaml(index)['resultRef']).parent).replace('\\','/')
            window = (CHECK.utc('2026-09-03T00:00:00Z'),CHECK.utc('2026-09-04T00:00:00Z'))
            for status in ('fail','inconclusive'):
                errors = []
                CHECK.validate_qualified_resources(root,plan,execution,{},defs,prefix,result['reviewer'],status,window,errors)
                self.assertEqual(errors,[])
            errors = []
            CHECK.validate_qualified_resources(root,plan,execution,{},defs,prefix,result['reviewer'],'pass',window,errors)
            self.assertTrue(any('validity must cover' in e for e in errors),errors)
            self.assertTrue(any('independent Task reviewer authorization' in e for e in errors),errors)
        finally:
            temp.cleanup()


    def test_125_ai_reviews_cannot_survive_captured_input_sample_version_drift(self):
        for profile in ('local-v1','production'):
            temp,root = self.temp_repo()
            try:
                index = self.make_profile_slot(root,'POC-009',profile)
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-09'}),[])
                result = load_yaml(root/load_yaml(index)['resultRef'])
                path = root/result['executionRef']
                execution = load_yaml(path)
                execution['environmentCaptured']['input_sample_version'] = 'changed-benchmark-revision'
                write_yaml(path,execution)
                errors = CHECK.validate_repository(root,profile,True,selected_pocs={'POC-09'})
                self.assertTrue(any('compliance' in e and 'subject' in e for e in errors),errors)
            finally:
                temp.cleanup()


    def test_126_qualified_source_requires_real_current_objects_and_own_evidence_only_drift(self):
        for profile in ('local-v1','production'):
            temp,root = self.temp_repo()
            try:
                index = self.make_profile_slot(root,'POC-006',profile)
                validate = lambda: CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'})
                self.assertEqual(validate(),[])
                result = load_yaml(root/load_yaml(index)['resultRef'])
                path = root/result['executionRef']
                execution = load_yaml(path)
                config_path = root/execution['environmentCaptured']['acceptanceProfileConfigurationRef']
                config = load_yaml(config_path)
                for mutation in ('missing','fake_matching','wrong_tree','config_mismatch'):
                    with self.subTest(profile=profile,mutation=mutation):
                        data = load_yaml(path);configured = load_yaml(config_path)
                        if mutation=='missing': data['environmentCaptured'].pop('testedSource')
                        elif mutation=='fake_matching':
                            data['environmentCaptured']['testedSource'] = dict(commit='1'*40,tree='2'*40)
                            configured['testedSource'] = data['environmentCaptured']['testedSource']
                        elif mutation=='wrong_tree':
                            data['environmentCaptured']['testedSource']['tree'] = '0'*40
                            configured['testedSource'] = data['environmentCaptured']['testedSource']
                        else: configured['testedSource']['commit'] = '1'*40
                        write_yaml(path,data);write_yaml(config_path,configured)
                        self.assertTrue(any('qualified tested source' in e for e in validate()))
                        write_yaml(path,execution);write_yaml(config_path,config)
                code = root/'fixture-tested-source.txt'
                untracked_code = root/'new_worker.py'
                untracked_code.write_text('print("new untested behavior")\n',encoding='utf-8')
                self.assertTrue(any('current validation context' in e for e in validate()))
                untracked_code.unlink()
                self.assertEqual(validate(),[])
                task_path = self.task_path(root,'POC-006')
                original_task = task_path.read_text(encoding='utf-8')
                for modified in (original_task.replace('status: in_progress','status: completed')+'Changed body.\n',
                                 original_task.replace('implementer: poc-006-implementer','implementer: untested-author'),
                                 original_task+'\n'):
                    task_path.write_text(modified,encoding='utf-8')
                    self.assertTrue(any('current validation context' in e for e in validate()))
                task_path.write_text(original_task,encoding='utf-8')
                unrelated = root/'evidence/POC-007/profiles/local-v1/v1/unrelated.txt'
                unrelated.parent.mkdir(parents=True,exist_ok=True)
                unrelated.write_text('Not the selected experiment.\n',encoding='utf-8')
                self.assertEqual(validate(),[])
                unrelated.unlink()
                unrelated = root/'evidence/POC-011/profiles/local-v1/v1/unrelated.txt'
                unrelated.parent.mkdir(parents=True,exist_ok=True)
                unrelated.write_text('Not a canonical experiment.\n',encoding='utf-8')
                self.assertTrue(any('current validation context' in e for e in validate()))
                unrelated.unlink()
                original_code = code.read_text(encoding='utf-8')
                code.write_text('Changed behavior, still old matching execution/configuration.\n',encoding='utf-8')
                self.assertTrue(any('current validation context' in e for e in validate()))
                def commit(*paths):
                    subprocess.run(['git','-C',str(root),'add','--',*paths],check=True)
                    subprocess.run(['git','-C',str(root),'-c','user.name=POC Fixture','-c','user.email=poc-fixture@guize.invalid','commit','-q','-m','synthetic fixture change'],check=True)
                commit('fixture-tested-source.txt')
                self.assertTrue(any('current validation context' in e for e in validate()))
                code.write_text(original_code,encoding='utf-8');commit('fixture-tested-source.txt')
                own_slot = str(index.parent.relative_to(root)).replace('\\','/')
                commit(own_slot)
                self.assertEqual(validate(),[])
            finally:
                temp.cleanup()


    def test_127_sibling_slots_can_coexist_in_both_full_milestones(self):
        temp,root = self.temp_repo()
        try:
            for profile in ('local-v1','production'):
                for task in sorted(CHECK.TASKS): self.make_profile_slot(root,task,profile)
            self.assertEqual(CHECK.validate_repository(root,'local-v1',True,'GZ-018'),[])
            self.assertEqual(CHECK.validate_repository(root,'production',True,'GZ-020'),[])
        finally: temp.cleanup()

    def test_128_qualified_execution_and_approval_times_cannot_be_future(self):
        future = '2099-09-04T00:02:00Z'
        for profile in ('local-v1','production'):
            temp,root = self.temp_repo()
            try:
                index = self.make_profile_slot(root,'POC-006',profile)
                validate = lambda: CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'})
                result_path = root/load_yaml(index)['resultRef'];result=load_yaml(result_path)
                execution_path = root/result['executionRef'];execution=load_yaml(execution_path)
                data = load_yaml(execution_path)
                data['environmentCaptured']['executionWindow'] = dict(startedAt='2099-09-03T00:00:00Z',finishedAt='2099-09-04T00:00:00Z')
                write_yaml(execution_path,data)
                self.assertTrue(any('validation time' in e for e in validate()))
                write_yaml(execution_path,execution)
                result['approvedAt']=future;write_yaml(result_path,result)
                self.assertTrue(any('validation time' in e for e in validate()))
                result['approvedAt']='2026-09-04T00:02:00Z';write_yaml(result_path,result)
                refs = [execution['environmentCaptured']['acceptanceProfileConfigurationRef'],execution['resources'][0]['configurationRef']]
                for ref in refs:
                    path=root/ref;original=path.read_bytes();data=load_yaml(path)
                    data['approvedAt']=future;write_yaml(path,data)
                    self.assertTrue(any('validation time' in e for e in validate()))
                    path.write_bytes(original)
                path=root/execution['resources'][0]['configurationRef'];data=load_yaml(path)
                data['validUntil']=future;write_yaml(path,data)
                self.assertEqual(validate(),[])
            finally: temp.cleanup()

    def test_129_api_performance_has_local_and_production_runtime_owners(self):
        nfr = load_yaml(self.repo/'specs/requirements/v1/nfr.yaml')
        item = next(item for item in nfr['items'] if item['id']=='NFR-V1-PERF-001')
        self.assertEqual(item['measurement']['verificationOwners'],['GZ-011','GZ-018','GZ-020'])
        self.assertEqual(item['applicableProfiles'],['local-v1','production'])
        self.assertEqual(item['measurement']['state'],'MEASUREMENT_REQUIRED')
        self.assertIsNone(item['measurement']['value'])

    def test_130_scale_pass_requires_exercised_population_and_change_work(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-005',profile)
                result_path=root/load_yaml(index)['resultRef'];result=load_yaml(result_path)
                path=root/result['executionRef'];original=path.read_bytes()
                for mid in ('file_count','directory_count','enumeration_rate','source_change_frequency','incremental_scan_cost'):
                    data=load_yaml(path);next(m for m in data['measurements'] if m['id']==mid)['actual']=0
                    write_yaml(path,data)
                    errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-05'})
                    self.assertTrue(any('positive exercised workload' in e and mid in e for e in errors),errors)
                    path.write_bytes(original)
                data=load_yaml(path)
                for measurement in data['measurements']:
                    if type(measurement['actual']) in (int,float): measurement['actual']=0
                write_yaml(path,data);result.update(status='fail',decision='fail');write_yaml(result_path,result)
                self.assertEqual(CHECK.validate_repository(root,profile,False,selected_pocs={'POC-05'}),[])
            finally: temp.cleanup()

    def test_131_separator_secret_keys_cannot_enter_qualified_configuration(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-006',profile)
                result=load_yaml(root/load_yaml(index)['resultRef']);execution=load_yaml(root/result['executionRef'])
                path=root/execution['resources'][0]['configurationRef'];original=path.read_bytes()
                for key in ('auth.token','api.key','auth/token','auth:token','private key','clientAuthTokenValue'):
                    data=load_yaml(path);data['configuration'][key]='opaque-fixture-value'
                    write_yaml(path,data)
                    errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'})
                    self.assertTrue(any('secret-like key forbidden' in e for e in errors),errors)
                    path.write_bytes(original)
                data=load_yaml(path);data['configuration']['credentials.stored.in.repository']=False;write_yaml(path,data)
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'}),[])
            finally: temp.cleanup()

    def test_132_raw_artifacts_require_dedicated_typed_actual_bytes(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-009',profile)
                result_ref=load_yaml(index)['resultRef'];result=load_yaml(root/result_ref)
                path=root/result['executionRef'];original=path.read_bytes();execution=load_yaml(path)
                configuration=load_yaml(root/execution['environmentCaptured']['acceptanceProfileConfigurationRef'])
                protected=[index.relative_to(root).as_posix(),result_ref,result['executionRef'],execution['environmentCaptured']['acceptanceProfileConfigurationRef']]
                protected += [r[key] for r in execution['resources'] for key in ('configurationRef','bookingRef') if r.get(key)]
                protected += [s['approvalRef'] for s in execution['samples']]+[r['reviewRef'] for r in execution['complianceReviews']]
                for ref in configuration['numericDomainReviewRefs'].values():
                    protected += [ref,load_yaml(root/ref)['definitionRef']]
                def artifacts(ref):
                    data=(root/ref).read_bytes()
                    return [dict(ref=ref,artifactType='command_output',byteCount=len(data),sha256='sha256:'+hashlib.sha256(data).hexdigest())]
                for ref in protected:
                    data=load_yaml(path);data['rawOutputRefs']=[ref]
                    for command in data['commands']: command['outputRef']=ref
                    data['environmentCaptured']['rawExecutionArtifacts']=artifacts(ref)
                    write_yaml(path,data)
                    errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-09'})
                    self.assertTrue(any('raw outputs must be disjoint' in e for e in errors),errors)
                    path.write_bytes(original)
                for field,value in (('artifactType','resource_configuration'),('artifactType','measurement_output'),('byteCount',-1),('sha256','sha256:'+'0'*64)):
                    data=load_yaml(path);data['environmentCaptured']['rawExecutionArtifacts'][0][field]=value;write_yaml(path,data)
                    errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-09'})
                    self.assertTrue(any('qualified raw artifacts' in e for e in errors),errors)
                    path.write_bytes(original)
                raw_ref=execution['rawOutputRefs'][0];raw_path=root/raw_ref;raw_path.unlink()
                os.link(root/execution['environmentCaptured']['acceptanceProfileConfigurationRef'],raw_path)
                data=load_yaml(path);data['environmentCaptured']['rawExecutionArtifacts']=artifacts(raw_ref);write_yaml(path,data)
                errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-09'})
                self.assertTrue(any('raw outputs must be disjoint' in e for e in errors),errors)
            finally: temp.cleanup()


    def test_133_permission_isolation_requires_both_runtime_milestone_owners(self):
        nfr = load_yaml(self.repo/'specs/requirements/v1/nfr.yaml')
        item = next(item for item in nfr['items'] if item['id']=='NFR-V1-SEC-001')
        self.assertEqual(item['measurement']['verificationOwners'],['GZ-011','GZ-018','GZ-020'])
        self.assertEqual(item['applicableProfiles'],['local-v1','production'])

    def test_134_encode_output_provenance_binds_actual_media_bytes(self):
        for profile in ('local-v1','production'):
            temp,root = self.temp_repo()
            try:
                index = self.make_profile_slot(root,'POC-002',profile)
                result = load_yaml(root/load_yaml(index)['resultRef'])
                path = root/result['executionRef']; original = path.read_bytes()
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'}),[])
                for field,value in (('producedMediaArtifactRef',None),('producedMediaArtifactRef',load_yaml(path)['rawOutputRefs'][0])):
                    data=load_yaml(path); data['environmentCaptured'][field]=value; write_yaml(path,data)
                    self.assertTrue(any('designated nonempty produced_media' in e for e in CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'})))
                    path.write_bytes(original)
                data=load_yaml(path); data['provenance']['output_sha256']='sha256:'+'0'*64; write_yaml(path,data)
                self.assertTrue(any('output_sha256 must match produced media bytes' in e for e in CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'})))
            finally: temp.cleanup()

    def test_135_encode_worker_identity_and_parallel_intervals_are_required(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-002',profile)
                result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
                mutations = [
                    lambda env: env.update(worker_node_inventory='captured-workers'),
                    lambda env: env.update(worker_node_inventory=env['worker_node_inventory'][:1]),
                    lambda env: env['worker_node_inventory'][1].update(platform='windows'),
                    lambda env: env.update(encoder_capability_matrix='captured-capability'),
                    lambda env: env.update(physical_host_scope='captured-host-scope'),
                    lambda env: env.update(workerEncodeExecutions=[]),
                    lambda env: env['workerEncodeExecutions'][0].update(nodeId='unqualified-node'),
                    lambda env: env['worker_node_inventory'][0].update(compatibilityGroupId='other-group'),
                    lambda env: env['workerEncodeExecutions'][0].update(compatibilityGroupId='other-group'),
                    lambda env: env['workerEncodeExecutions'][0].update(inputSha256={}),
                    lambda env: env['workerEncodeExecutions'][0].update(outputSha256='sha256:'+'0'*64),
                    lambda env: env['workerEncodeExecutions'][0].update(rawOutputRef=env['workerEncodeExecutions'][1]['rawOutputRef']),
                    lambda env: env['workerEncodeExecutions'][1].update(startedAt='2026-09-03T00:01:00Z',finishedAt='2026-09-03T00:02:00Z'),
                ]
                for mutate in mutations:
                    data=load_yaml(path);mutate(data['environmentCaptured']);write_yaml(path,data)
                    errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'})
                    self.assertTrue(any('qualified encode workers' in e for e in errors),errors)
                    path.write_bytes(original)
            finally: temp.cleanup()

    def test_136_encode_pass_requires_positive_throughput_and_soak(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-002',profile)
                result_path=root/load_yaml(index)['resultRef'];result=load_yaml(result_path)
                path=root/result['executionRef'];original=path.read_bytes()
                for mid in ('encode_throughput','sustained_encode_duration'):
                    data=load_yaml(path);next(m for m in data['measurements'] if m['id']==mid)['actual']=0;write_yaml(path,data)
                    errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'})
                    self.assertTrue(any('positive exercised workload' in e and mid in e for e in errors),errors)
                    result.update(status='fail',decision='fail');write_yaml(result_path,result)
                    self.assertEqual(CHECK.validate_repository(root,profile,False,selected_pocs={'POC-02'}),[])
                    result.update(status='pass',decision='pass');write_yaml(result_path,result);path.write_bytes(original)
            finally: temp.cleanup()

    def test_137_ignored_untracked_referenced_evidence_cannot_pass(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                (root/'.gitignore').write_text('*.log\n',encoding='utf8')
                index=self.make_profile_slot(root,'POC-006',profile)
                result=load_yaml(root/load_yaml(index)['resultRef']);execution=load_yaml(root/result['executionRef'])
                errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'})
                self.assertTrue(any('referenced qualified evidence must not be ignored and untracked' in e for e in errors),errors)
                for ref in execution['rawOutputRefs']:
                    subprocess.run(['git','-C',str(root),'add','-f','--',ref],check=True)
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'}),[])
                if os.name != 'nt':
                    # A tracked symlink cannot preserve an ignored, untracked target.
                    execution_path=root/result['executionRef']; data=load_yaml(execution_path)
                    prefix=str(index.parent.relative_to(root)).replace('\\','/')
                    target_ref=prefix+'/raw/ignored-target.log';alias_ref=prefix+'/raw/tracked-alias.txt'
                    target=root/target_ref;target.write_text('Synthetic alias target.\n',encoding='utf8')
                    os.symlink(target.name,root/alias_ref)
                    subprocess.run(['git','-C',str(root),'add','--',alias_ref],check=True)
                    # Retain exercised fault observations while replacing only command output.
                    observations=[r for r in data['environmentCaptured']['rawExecutionArtifacts'] if r['artifactType']=='scope_observation']
                    data['rawOutputRefs']=[alias_ref,*[r['ref'] for r in observations]]
                    for command in data['commands']: command['outputRef']=alias_ref
                    data['environmentCaptured']['rawExecutionArtifacts']=[dict(ref=alias_ref,artifactType='command_output',byteCount=target.stat().st_size,sha256='sha256:'+hashlib.sha256(target.read_bytes()).hexdigest())]
                    data['environmentCaptured']['rawExecutionArtifacts'].extend(observations)
                    write_yaml(execution_path,data)
                    errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'})
                    self.assertTrue(any('referenced qualified evidence must not be ignored and untracked' in e and target_ref in e for e in errors),errors)
                    subprocess.run(['git','-C',str(root),'add','-f','--',target_ref],check=True)
                    self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'}),[])
                    index_bytes=index.read_bytes();index.unlink()
                    index_target=index.parent/'index-data.log';index_target.write_bytes(index_bytes)
                    os.symlink(index_target.name,index)
                    subprocess.run(['git','-C',str(root),'add','--',index.relative_to(root).as_posix()],check=True)
                    errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'})
                    self.assertTrue(any('referenced qualified evidence must not be ignored and untracked' in e and 'index-data.log' in e for e in errors),errors)
                    subprocess.run(['git','-C',str(root),'add','-f','--',index_target.relative_to(root).as_posix()],check=True)
                    self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'}),[])
            finally: temp.cleanup()


    def test_138_vm_and_device_output_hashes_bind_typed_media_bytes(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-001',profile)
                result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-01'}),[])
                key='vm_validation_scope' if profile=='local-v1' else 'android_validation_scope'
                for mode in ('hash','type','node'):
                    data=load_yaml(path);scope=data['environmentCaptured'][key]
                    if mode=='hash': scope['outputSha256']='sha256:'+'f'*64
                    else:
                        artifact=next(a for a in data['environmentCaptured']['rawExecutionArtifacts'] if a['ref']==scope['rawOutputRef'])
                        artifact.update(artifactType='command_output') if mode=='type' else artifact.update(nodeId='other-node')
                    write_yaml(path,data)
                    errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-01'})
                    self.assertTrue(any('qualified Android output' in e for e in errors),errors)
                    path.write_bytes(original)
            finally: temp.cleanup()

    def test_139_qualified_text_credentials_and_decode_failures_are_rejected(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-006',profile)
                result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];execution=load_yaml(path)
                raw_ref=execution['rawOutputRefs'][0];raw=root/raw_ref
                def capture(data):
                    raw.write_bytes(data)
                    execution['environmentCaptured']['rawExecutionArtifacts'][0].update(byteCount=len(data),sha256='sha256:'+hashlib.sha256(data).hexdigest())
                    write_yaml(path,execution)
                for data in (b'password=fixture-secret\n',b'{"api.key":"opaque-fixture-secret"}\n',b'{"scope":"fixture","password":"opaque-fixture-secret"}\n',b'Authorization: Bearer opaque-fixture-secret\n',b'{"Authorization":"Bearer opaque-fixture-secret"}\n',b'x'*(CHECK.ARTIFACT_CHUNK_BYTES-5)+b'\npassword=fixture-secret\n'):
                    capture(data)
                    errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'})
                    self.assertTrue(any('credentials forbidden in raw textual artifacts' in e for e in errors),errors)
                capture(b'\xff\xfe')
                self.assertTrue(any('must decode as UTF-8' in e for e in CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'})))
                for safe in ('已完成；credentials.stored.in.repository=false\n','{"credentialsStoredInRepository":false,"scope":"fixture"}\n'):
                    capture(safe.encode('utf8'))
                    self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'}),[])
                original_open=Path.open
                def deny(selected,*args,**kwargs):
                    if selected==raw and (args[0] if args else kwargs.get('mode','r'))=='rb': raise OSError('synthetic unreadable raw artifact')
                    return original_open(selected,*args,**kwargs)
                with mock.patch.object(Path,'open',deny):
                    self.assertTrue(any('cannot read raw artifact' in e for e in CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'})))
            finally: temp.cleanup()

    def test_140_media_hashing_is_bounded_and_reused_per_validation(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-002',profile)
                result=load_yaml(root/load_yaml(index)['resultRef']);execution=load_yaml(root/result['executionRef'])
                media={root/a['ref'] for a in execution['environmentCaptured']['rawExecutionArtifacts'] if a['artifactType']=='produced_media'}
                counts={path:0 for path in media};original_open=Path.open
                test=self
                class BoundedReader:
                    def __init__(self,handle): self.handle=handle
                    def __enter__(self): self.handle.__enter__();return self
                    def __exit__(self,*args): return self.handle.__exit__(*args)
                    def read(self,size):
                        test.assertGreater(size,0);test.assertLessEqual(size,CHECK.ARTIFACT_CHUNK_BYTES)
                        return self.handle.read(size)
                def spy(path,*args,**kwargs):
                    handle=original_open(path,*args,**kwargs)
                    if path in media and (args[0] if args else kwargs.get('mode','r'))=='rb':
                        counts[path]+=1;return BoundedReader(handle)
                    return handle
                with mock.patch.object(Path,'read_bytes',side_effect=AssertionError('whole artifact reads forbidden')),mock.patch.object(Path,'open',spy):
                    self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'}),[])
                self.assertTrue(all(count==1 for count in counts.values()),counts)
                # Binary media is hashed without attempting textual credential decoding.
                path=next(iter(media));data=b'\xff\x00password=synthetic-binary-metadata'
                path.write_bytes(data)
                info=CHECK.inspect_artifact(path,{},textual=False)
                self.assertEqual(info['sha256'],'sha256:'+hashlib.sha256(data).hexdigest())
                self.assertFalse(info['invalidUtf8']);self.assertFalse(info['credential'])
            finally: temp.cleanup()


    def test_141_production_android_observations_require_distinct_node_bound_artifact(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-001','production')
            result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
            validate=lambda: CHECK.validate_repository(root,'production',True,selected_pocs={'POC-01'})
            self.assertEqual(validate(),[])
            for mode in ('media','generic','type','node','alias'):
                path.write_bytes(original);data=load_yaml(path);env=data['environmentCaptured']
                scope=env['android_validation_scope'];observation=env['android_thermal_background_observation']
                artifact=next(a for a in env['rawExecutionArtifacts'] if a['ref']==observation['rawOutputRef'])
                if mode=='media': observation['rawOutputRef']=scope['rawOutputRef']
                elif mode=='generic': observation['rawOutputRef']=data['commands'][0]['outputRef']
                elif mode=='type': artifact['artifactType']='command_output'
                elif mode=='node': artifact['nodeId']='other-node'
                else:
                    output=root/observation['rawOutputRef'];output.unlink();os.symlink(root/scope['rawOutputRef'],output)
                    artifact.update(byteCount=output.stat().st_size,sha256='sha256:'+hashlib.sha256(output.read_bytes()).hexdigest())
                configuration=load_yaml(root/env['acceptanceProfileConfigurationRef'])
                route=CHECK.execution_route(load_yaml(root/'specs/poc/plans/POC-001.yaml'),'production')
                for ref in configuration['numericDomainReviewRefs'].values():
                    review=load_yaml(root/ref);review['environmentCaptured']={k:env[k] for k in route['captureBeforeExecution']};write_yaml(root/ref,review)
                write_yaml(path,data)
                errors=validate()
                self.assertTrue(any('qualified Android output' in e and ('scope_observation' in e or 'distinct from encoded media' in e) for e in errors),errors)
        finally: temp.cleanup()

    def test_142_production_capacity_preserves_frozen_floor_and_local_route(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-004',profile)
                result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
                validate=lambda: CHECK.validate_repository(root,profile,True,selected_pocs={'POC-04'})
                self.assertEqual(validate(),[])
                if profile=='local-v1': continue
                for value in (0,499,499.99,500,501):
                    data=load_yaml(path)
                    next(m for m in data['measurements'] if m['id']=='minimum_free_space_gib')['actual']=value
                    write_yaml(path,data);errors=validate()
                    if value < 500:self.assertTrue(any('qualified production capacity' in e for e in errors),errors)
                    else:self.assertEqual(errors,[])
                data=load_yaml(path)
                next(m for m in data['measurements'] if m['id']=='minimum_free_space_gib')['actual']=0
                plan=load_yaml(root/'specs/poc/plans/POC-004.yaml');errors=[]
                CHECK.validate_qualified_production_capacity(plan,data,'fail',errors)
                self.assertEqual(errors,[])
            finally: temp.cleanup()


    def sync_capture_reviews(self,root,execution):
        env=execution['environmentCaptured'];configuration=load_yaml(root/env['acceptanceProfileConfigurationRef'])
        poc=execution['pocId'];profile=env['acceptanceProfile']['id']
        plan=load_yaml(root/f"specs/poc/plans/POC-{int(poc.split('-')[1]):03d}.yaml")
        route=CHECK.execution_route(plan,profile)
        for ref in configuration['numericDomainReviewRefs'].values():
            review=load_yaml(root/ref);review['environmentCaptured']={k:env[k] for k in route['captureBeforeExecution']};write_yaml(root/ref,review)

    def test_143_qualified_input_bytes_bind_approved_sample_hashes(self):
        for profile in ('local-v1','production'):
            for task in ('POC-001','POC-002'):
                temp,root=self.temp_repo()
                try:
                    index=self.make_profile_slot(root,task,profile)
                    result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
                    validate=lambda: CHECK.validate_repository(root,profile,True,selected_pocs={result['pocId']})
                    self.assertEqual(validate(),[])
                    execution=load_yaml(path);sample=execution['samples'][0];approval_path=root/sample['approvalRef'];approval_bytes=approval_path.read_bytes()
                    input_path=root/execution['environmentCaptured']['inputSampleArtifacts'][0]['inputArtifactRef'];input_bytes=input_path.read_bytes()
                    for mode in ('fabricated','bytes','alias','result','index'):
                        path.write_bytes(original);approval_path.write_bytes(approval_bytes);input_path.write_bytes(input_bytes)
                        data=load_yaml(path);env=data['environmentCaptured'];sample=data['samples'][0];artifact=env['inputSampleArtifacts'][0]
                        if mode=='bytes':input_path.write_bytes(input_bytes+b'changed bytes')
                        else:
                            digest='sha256:'+'f'*64
                            if mode=='alias':
                                output=next(r for r in env['rawExecutionArtifacts'] if r['artifactType']=='produced_media')
                                artifact.update(inputArtifactRef=output['ref'],byteCount=output['byteCount']);digest=output['sha256']
                            elif mode in ('result','index'):
                                structured_path=root/load_yaml(index)['resultRef'] if mode=='result' else index
                                structured_bytes=structured_path.read_bytes()
                                digest='sha256:'+hashlib.sha256(structured_bytes).hexdigest()
                                artifact.update(inputArtifactRef=structured_path.relative_to(root).as_posix(),byteCount=len(structured_bytes))
                            sample['checksum']=artifact['sha256']=digest
                            approval=load_yaml(approval_path);approval['checksum']=digest;write_yaml(approval_path,approval)
                            if task=='POC-001':env['android_validation_scope' if profile=='production' else 'vm_validation_scope']['inputSha256']=digest
                            else:
                                data['provenance']['input_sha256']=digest
                                for run in env['workerEncodeExecutions']:run['inputSha256']=digest
                        write_yaml(path,data);self.sync_capture_reviews(root,data)
                        errors=validate()
                        self.assertTrue(any('qualified input samples' in e for e in errors),errors)
                finally:temp.cleanup()

    def test_144_profile_configuration_requires_independent_pre_execution_approval(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-004',profile)
                result=load_yaml(root/load_yaml(index)['resultRef']);execution=load_yaml(root/result['executionRef'])
                path=root/execution['environmentCaptured']['acceptanceProfileConfigurationRef'];original=path.read_bytes()
                validate=lambda: CHECK.validate_repository(root,profile,True,selected_pocs={'POC-04'})
                self.assertEqual(validate(),[])
                for mode in ('no_time','no_reviewer','implementer','late','wrong_profile','wrong_task','rejected'):
                    path.write_bytes(original);data=load_yaml(path)
                    if mode=='no_time':data.pop('approvedAt')
                    elif mode=='no_reviewer':data.pop('approvedBy')
                    elif mode=='implementer':data['approvedBy']=execution['executor']
                    elif mode=='late':data['approvedAt']='2026-09-03T00:00:01Z'
                    elif mode=='wrong_profile':data['acceptanceProfile']=CHECK.profile_identity('production' if profile=='local-v1' else 'local-v1')
                    elif mode=='wrong_task':data['taskId']='POC-999'
                    else:data['decision']='rejected'
                    write_yaml(path,data);errors=validate()
                    self.assertTrue(any('profile configuration' in e for e in errors),errors)
            finally:temp.cleanup()

    def test_145_production_phone_pass_requires_positive_soak_duration(self):
        for profile,status in (('local-v1','pass'),('production','pass'),('production','fail')):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-001',profile,status=status)
                result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef']
                validate=lambda: CHECK.validate_repository(root,profile,status=='pass',selected_pocs={'POC-01'})
                self.assertEqual(validate(),[])
                if profile=='local-v1':continue
                data=load_yaml(path);next(m for m in data['measurements'] if m['id']=='multi_day_stability_duration')['actual']=0;write_yaml(path,data)
                errors=validate()
                if status=='pass':self.assertTrue(any('positive multi_day_stability_duration' in e for e in errors),errors)
                else:self.assertEqual(errors,[])
            finally:temp.cleanup()

    def test_146_local_captures_require_reproducible_structured_settings(self):
        for task in ('POC-002','POC-005','POC-006','POC-007'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,task,'local-v1')
                result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
                execution=load_yaml(path);config_path=root/execution['environmentCaptured']['acceptanceProfileConfigurationRef'];config_original=config_path.read_bytes()
                validate=lambda: CHECK.validate_repository(root,'local-v1',True,selected_pocs={result['pocId']})
                self.assertEqual(validate(),[])
                for field in CHECK.LOCAL_STRUCTURED_CAPTURES[result['pocId']]:
                    for mode in ('boolean','empty','foreign_scope',*(['foreign_ref'] if field=='injected_failure_matrix' else [])):
                        path.write_bytes(original);config_path.write_bytes(config_original);data=load_yaml(path);env=data['environmentCaptured'];config=load_yaml(config_path)
                        value=True if mode=='boolean' else {} if mode=='empty' else env[field]
                        if mode=='foreign_scope':value['scope']='PRODUCTION_RELEASE'
                        elif mode=='foreign_ref':value['cases'][0]['rawOutputRef']=value['cases'][0]['rawOutputRef'].replace('local-v1','production')
                        env[field]=config['capturedSettings'][field]=value
                        write_yaml(path,data);write_yaml(config_path,config);self.sync_capture_reviews(root,data)
                        errors=validate()
                        self.assertTrue(any('qualified local capture' in e and field in e for e in errors),errors)
            finally:temp.cleanup()


    def test_147_every_qualified_sample_binds_actual_input_bytes(self):
        for profile in ('local-v1','production'):
            for task in sorted(CHECK.TASKS):
                with self.subTest(profile=profile,task=task):
                    temp,root=self.temp_repo()
                    try:
                        index=self.make_profile_slot(root,task,profile)
                        result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
                        validate=lambda:CHECK.validate_repository(root,profile,True,selected_pocs={result['pocId']})
                        self.assertEqual(validate(),[])
                        execution=load_yaml(path);sample=execution['samples'][0]
                        approval_path=root/sample['approvalRef'];approval_bytes=approval_path.read_bytes()
                        input_path=root/execution['environmentCaptured']['inputSampleArtifacts'][0]['inputArtifactRef'];input_bytes=input_path.read_bytes()
                        for mode in ('missing','fabricated','bytes'):
                            path.write_bytes(original);approval_path.write_bytes(approval_bytes);input_path.write_bytes(input_bytes)
                            data=load_yaml(path);env=data['environmentCaptured']
                            if mode=='missing':env.pop('inputSampleArtifacts')
                            elif mode=='bytes':input_path.write_bytes(input_bytes+b'changed bytes')
                            else:
                                digest='sha256:'+'f'*64
                                data['samples'][0]['checksum']=env['inputSampleArtifacts'][0]['sha256']=digest
                                approval=load_yaml(approval_path);approval['checksum']=digest;write_yaml(approval_path,approval)
                            write_yaml(path,data)
                            errors=validate()
                            self.assertTrue(any('qualified input samples' in error for error in errors),errors)
                    finally:temp.cleanup()


    def test_148_parallel_media_spans_and_assembled_decode_bind_actual_outputs(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-002',profile)
                result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
                execution=load_yaml(path);report_path=root/execution['environmentCaptured']['parallelMediaAssembly']['validationRef'];report_bytes=report_path.read_bytes()
                validate=lambda:CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'})
                self.assertEqual(validate(),[])
                for mode in ('duplicate','gap','incomplete','boolean_frame','reordered','missing_report','decoded_count','decode_error','timeline_error','report_hash','part_as_assembly'):
                    path.write_bytes(original);report_path.write_bytes(report_bytes)
                    data=load_yaml(path);env=data['environmentCaptured'];assembly=env['parallelMediaAssembly'];runs=env['workerEncodeExecutions'];report=load_yaml(report_path)
                    if mode in ('duplicate','gap','incomplete','boolean_frame'):
                        if mode=='duplicate':runs[1].update(sourceStartFrame=0,sourceEndFrame=120)
                        elif mode=='gap':runs[1]['sourceStartFrame']=61
                        elif mode=='incomplete':runs[1]['sourceEndFrame']=119
                        else:runs[0]['sourceStartFrame']=False
                        assembly['parts']=[{key:run[key] for key in ('nodeId','outputArtifactRef','outputSha256','sourceStartFrame','sourceEndFrame')} for run in runs]
                        report['parts']=assembly['parts']
                    elif mode=='reordered':assembly['parts'].reverse();report['parts']=assembly['parts']
                    elif mode=='missing_report':assembly['validationRef']=runs[0]['rawOutputRef']
                    elif mode=='decoded_count':report['decodedFrameCount']=119
                    elif mode=='decode_error':report['decodeErrorCount']=1
                    elif mode=='timeline_error':report['timelineDiscontinuityCount']=1
                    elif mode=='report_hash':report['outputSha256']='sha256:'+'f'*64
                    else:assembly['outputArtifactRef']=runs[0]['outputArtifactRef']
                    write_yaml(report_path,report)
                    record=next(item for item in env['rawExecutionArtifacts'] if item['ref']==report_path.relative_to(root).as_posix())
                    record.update(byteCount=report_path.stat().st_size,sha256='sha256:'+hashlib.sha256(report_path.read_bytes()).hexdigest())
                    write_yaml(path,data)
                    errors=validate()
                    self.assertTrue(any('qualified media assembly' in error for error in errors),errors)
            finally:temp.cleanup()


    def test_149_authenticated_lifecycle_closure_preserves_tested_source(self):
        spec=importlib.util.spec_from_file_location('poc_lifecycle_unit_fixture',self.repo/'tests/governance/test_program_plan_history.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        fixture=module.TestProgramPlanHistory()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            def git(*args,input=None):
                return subprocess.run(['git',*args],cwd=root,text=True,encoding='utf8',input=input,capture_output=True,check=True).stdout.strip()
            fixture.create_regular_completion(str(root))
            old_closure=git('rev-parse','HEAD');source=git('rev-parse','HEAD^1')
            ledger=CHECK.yaml.safe_load(git('show',old_closure+':specs/coordination/task-completions.yaml'))
            record=ledger['records'][0];reservation=record['reservationCommit']
            terminal_spec=git('show',old_closure+':specs/tasks/GZ-004.md')+'\n'
            terminal_plan=CHECK.yaml.safe_load(git('show',old_closure+':specs/coordination/program-plan.yaml'))
            terminal_active=CHECK.yaml.safe_load(git('show',old_closure+':specs/coordination/active-work.yaml'))
            tree=git('rev-parse',source+'^{tree}')
            merged=git('commit-tree',tree,'-p',reservation,'-p',source,input='GZ-004 implementation (#31)\n')
            git('reset','--hard',merged)
            record['mergeCommit']=merged
            write_yaml(root/'specs/coordination/program-plan.yaml',terminal_plan)
            write_yaml(root/'specs/coordination/active-work.yaml',terminal_active)
            write_yaml(root/'specs/coordination/task-completions.yaml',ledger)
            (root/'specs/tasks/GZ-004.md').write_text(terminal_spec.replace(source,merged),encoding='utf8')
            for name in ('summary.md','handoff.md','commands.txt','test-results/README.md'):
                path=root/'evidence/GZ-004'/name;path.parent.mkdir(parents=True,exist_ok=True)
                path.write_text(f'GZ-004 synthetic lifecycle unit fixture; never actual execution acceptance\nImplementation: {merged}\nStatus: COMPLETED\nCommand: python fixture-check.py\nExit Code: 0\nResult: PASS\n',encoding='utf8')
            archive=root/'evidence/GZ-004/test-results/accepted-fixture';archive.mkdir()
            raw=b'Synthetic history archive; never actual accepted test execution.\n'
            part=base64.b64encode(zlib.compress(raw))+b'\n';(archive/'raw.part.txt').write_bytes(part)
            (archive/'raw-results.bundle.json').write_text(json.dumps(dict(source=source,actualMain=merged,tree=tree,entries=[dict(size=len(raw),sha256=hashlib.sha256(raw).hexdigest(),encoding='concatenated-zlib-base64-parts',parts=[dict(path='raw.part.txt',sha256=hashlib.sha256(part).hexdigest())])]))+'\n',encoding='utf8')
            canonical=root/'evidence/GZ-004/test-results/canonical-fixture';canonical.mkdir()
            (canonical/'history.txt').write_bytes(raw)
            (canonical/'manifest.json').write_text(json.dumps(dict(actualSource=source,tree=tree,files=[dict(path='history.txt',canonicalBytes=len(raw),canonicalLfSha256=hashlib.sha256(raw).hexdigest())]))+'\n',encoding='utf8')
            git('add','.');git('commit','-qm','GZ-004 completion metadata (#32)');good=git('rev-parse','HEAD')
            identity=dict(commit=source,tree=tree)
            execution=dict(environmentCaptured=dict(testedSource=identity,acceptanceProfile=CHECK.profile_identity('local-v1')))
            definitions=load_yaml(self.repo/'specs/poc/program.schema.yaml')['$defs']
            def validate():
                errors=[]
                CHECK.validate_qualified_source(root,dict(pocId='POC-06',taskId='POC-006'),execution,dict(testedSource=identity),definitions,'evidence/POC-006/profiles/local-v1',errors)
                return errors
            self.assertEqual(validate(),[])
            for title in ('当前 Review（以上实施/预留阶段描述为历史记录）','当前 Completion（实施阶段为历史记录）'):
                git('reset','--hard',good);git('reset','--soft',merged)
                path=root/'specs/tasks/GZ-004.md'
                phase=path.read_text(encoding='utf8')+'\n## '+title+'\n\nOnly authenticated phase metadata; original scope and runtime remain unchanged.\n'
                path.write_text(phase,encoding='utf8')
                git('add','.');git('commit','-qm','GZ-004 phase handoff fixture (#32)')
                self.assertEqual(validate(),[],title)
                git('reset','--soft',merged)
                path.write_text(phase.replace('docs/test/**','backend/**'),encoding='utf8')
                git('add','.');git('commit','-qm','GZ-004 invalid phase authority fixture (#32)')
                self.assertTrue(any('qualified tested source' in error for error in validate()),title)
            for mode in ('fake_identity','scope','policy','duplicate_row','arbitrary_evidence','archive_digest','canonical_digest','wrong_actor','wrong_base'):
                git('reset','--hard',good);git('reset','--soft',merged)
                if mode=='fake_identity':
                    path=root/'specs/coordination/task-completions.yaml';data=load_yaml(path);data['records'][0]['reservationCommit']='f'*40;write_yaml(path,data)
                elif mode=='scope':
                    path=root/'specs/tasks/GZ-004.md';path.write_text(path.read_text(encoding='utf8').replace('docs/test/**','backend/**'),encoding='utf8')
                elif mode=='policy':
                    path=root/'specs/coordination/program-plan.yaml';data=load_yaml(path);data['fabricatedPolicy']='weakened';write_yaml(path,data)
                elif mode=='duplicate_row':
                    path=root/'specs/coordination/program-plan.yaml';data=load_yaml(path);data['tasks'].append(dict(data['tasks'][0]));write_yaml(path,data)
                elif mode=='arbitrary_evidence':(root/'evidence/GZ-004/unlisted.txt').write_text('Unlisted mutation.\n',encoding='utf8')
                elif mode=='archive_digest':(archive/'raw.part.txt').write_bytes(part+b'changed')
                elif mode=='canonical_digest':(canonical/'history.txt').write_bytes(raw+b'changed')
                else:
                    path=root/'specs/tasks/GZ-004.md';text=path.read_text(encoding='utf8')
                    text=text.replace('reviewer: reviewer','reviewer: implementer') if mode=='wrong_actor' else text.replace('baseSha: '+merged,'baseSha: '+'f'*40)
                    path.write_text(text,encoding='utf8')
                git('add','.');git('commit','-qm','GZ-004 invalid completion fixture (#32)')
                self.assertTrue(any('qualified tested source' in error for error in validate()),mode)
            git('reset','--hard',merged)
            original=(root/'seed.txt').read_bytes()
            (root/'seed.txt').write_bytes(b'Runtime drift.\n');git('add','.');git('commit','-qm','GZ-004 runtime drift fixture')
            (root/'seed.txt').write_bytes(original);git('add','.');git('commit','-qm','GZ-004 restored runtime fixture')
            self.assertEqual(validate(),[])
            policy_path=root/'specs/coordination/program-plan.yaml';original_policy=policy_path.read_bytes()
            policy=load_yaml(policy_path);policy['fabricatedPolicy']='weakened';write_yaml(policy_path,policy)
            git('add','.');git('commit','-qm','GZ-004 policy drift fixture')
            policy_path.write_bytes(original_policy);git('add','.');git('commit','-qm','GZ-004 restored policy fixture')
            self.assertTrue(any('qualified tested source' in error for error in validate()))


    def test_150_local_hierarchy_pass_matches_exact_approved_workload(self):
        for profile,status in (('local-v1','pass'),('local-v1','fail'),('production','pass')):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-005',profile,status=status)
                result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
                validate=lambda:CHECK.validate_repository(root,profile,status=='pass',selected_pocs={'POC-05'})
                self.assertEqual(validate(),[])
                if profile=='production':continue
                for metric in ('file_count','directory_count','directory_depth_max'):
                    path.write_bytes(original);data=load_yaml(path)
                    next(item for item in data['measurements'] if item['id']==metric)['actual']=11
                    write_yaml(path,data);errors=validate()
                    if status=='pass':self.assertTrue(any('qualified local capture' in error and metric in error for error in errors),errors)
                    else:self.assertEqual(errors,[])
                if status=='pass':
                    path.write_bytes(original);data=load_yaml(path)
                    data['environmentCaptured']['synthetic_hierarchy_manifest']['generator']=True
                    write_yaml(path,data)
                    self.assertTrue(any('qualified local capture' in error for error in validate()))
            finally:temp.cleanup()

    def test_151_local_tls_origins_validate_semantic_host_and_port(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-007','local-v1')
            result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
            configuration_path=root/load_yaml(path)['environmentCaptured']['acceptanceProfileConfigurationRef'];configuration_bytes=configuration_path.read_bytes()
            validate=lambda:CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-07'})
            self.assertEqual(validate(),[])
            for field in ('entryOrigin','openlistOrigin'):
                for host,accepted in (('guize.local:1',True),('guize.local:443',True),('127.0.0.1:65535',True),('[::1]:443',True),('guize.local:99999',False),('guize.local:00000',False),('bad..local:443',False),('-bad.local:443',False),('999.1.1.1:443',False),('[:::1]:443',False)):
                    path.write_bytes(original);configuration_path.write_bytes(configuration_bytes)
                    data=load_yaml(path);configuration=load_yaml(configuration_path)
                    value='https://'+host
                    data['environmentCaptured']['local_tls_path_configuration'][field]=value
                    configuration['capturedSettings']['local_tls_path_configuration'][field]=value
                    write_yaml(path,data);write_yaml(configuration_path,configuration);self.sync_capture_reviews(root,data)
                    errors=validate()
                    if accepted:self.assertEqual(errors,[],value)
                    else:self.assertTrue(any('qualified local capture' in error and field in error for error in errors),errors)
        finally:temp.cleanup()


    def test_152_canonical_secret_reference_preserves_plaintext_guards(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-006',profile)
                execution=load_yaml(root/load_yaml(root/index)['resultRef'])
                execution=load_yaml(root/execution['executionRef'])
                path=root/execution['resources'][0]['configurationRef']
                record=load_yaml(path);record['configuration']['credentialReference']='secretref_example01'
                write_yaml(path,record)
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'}),[])
                record['configuration']['credentialReference']='plaintext-not-reference'
                write_yaml(path,record)
                self.assertTrue(any('Secret reference' in e for e in CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'})))
            finally:temp.cleanup()
        for invalid in ('secretref_','secretref_'+'x'*65,'secretref_valid\n','https://vault/token',True,None,{'password':'plaintext'}):
            errors=[];CHECK.secret_scan({'credentialReference':invalid},'fixture',errors)
            self.assertTrue(errors,invalid)
        for key in ('credential_reference','credential-reference','password','accessToken','secretReference'):
            errors=[];CHECK.secret_scan({key:'secretref_example01'},'fixture',errors)
            self.assertTrue(errors,key)

    def test_153_encode_metrics_bound_measured_continuous_intervals(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-002',profile)
                result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
                validate=lambda:CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'})
                self.assertEqual(validate(),[])
                for metric,actual in (('encode_throughput',3),('encode_throughput',1000000),('sustained_encode_duration',2),('sustained_encode_duration',1000000)):
                    path.write_bytes(original);record=load_yaml(path)
                    next(m for m in record['measurements'] if m['id']==metric)['actual']=actual
                    write_yaml(path,record)
                    self.assertTrue(any('captured continuous worker interval capacity' in e for e in validate()),metric)
            finally:temp.cleanup()
        instant=lambda seconds:CHECK.utc('2026-09-03T00:'+f'{seconds//60:02d}:'+f'{seconds%60:02d}'+'Z')
        cases=[
            ([('a',0,60),('b',0,60)],(2,1)),
            ([('a',0,60),('a',0,60)],(1,1)),
            ([('a',0,60),('b',60,120)],(1,2)),
            ([('a',0,60),('b',120,180)],(1,1)),
            ([('a',0,60),('b',30,90)],(2,1.5)),
        ]
        for runs,expected in cases:
            self.assertEqual(CHECK.encode_interval_capacity([(node,instant(start),instant(end)) for node,start,end in runs]),expected)


    def test_154_production_soak_binds_approved_days_and_observed_hours(self):
        for profile,status in (('production','pass'),('production','fail'),('local-v1','pass')):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-001',profile,status=status)
                result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
                validate=lambda:CHECK.validate_repository(root,profile,status=='pass',selected_pocs={'POC-01'})
                self.assertEqual(validate(),[])
                if profile!='production':
                    self.assertNotIn('productionPassthroughSoak',load_yaml(path)['environmentCaptured'])
                    continue
                if status!='pass':
                    record=load_yaml(path);next(m for m in record['measurements'] if m['id']=='multi_day_stability_duration')['actual']=0.001
                    write_yaml(path,record);self.assertEqual(validate(),[])
                    continue
                baseline=load_yaml(path);floor_path=root/baseline['environmentCaptured']['productionPassthroughSoak']['configurationRef'];floor_bytes=floor_path.read_bytes()
                for mode in ('nominal','overclaim','short_observed','below_approved','wrong_ref','wrong_raw','wrong_floor','invalid_days','late_approval'):
                    path.write_bytes(original);floor_path.write_bytes(floor_bytes);record=load_yaml(path);capture=record['environmentCaptured']['productionPassthroughSoak']
                    metric=next(m for m in record['measurements'] if m['id']=='multi_day_stability_duration')
                    if mode=='nominal':metric['actual']=0.001
                    elif mode=='overclaim':metric['actual']=49
                    elif mode=='short_observed':capture['observedFinishedAt']='2026-09-03T00:01:00Z';metric['actual']=1/60
                    elif mode=='below_approved':
                        capture['minimumContinuousDays']=3;floor=load_yaml(floor_path);floor['configuration']['productionPassthroughSoak']['minimumContinuousDays']=3;write_yaml(floor_path,floor)
                    elif mode=='wrong_ref':capture['configurationRef']=record['environmentCaptured']['acceptanceProfileConfigurationRef']
                    elif mode=='wrong_raw':capture['rawOutputRef']=record['rawOutputRefs'][0]
                    elif mode=='wrong_floor':capture['minimumContinuousDays']=3
                    elif mode=='invalid_days':
                        capture['minimumContinuousDays']=True;floor=load_yaml(floor_path);floor['configuration']['productionPassthroughSoak']['minimumContinuousDays']=True;write_yaml(floor_path,floor)
                    else:
                        floor=load_yaml(floor_path);floor['approvedAt']='2026-09-03T00:00:01Z';write_yaml(floor_path,floor)
                    write_yaml(path,record)
                    self.assertTrue(any('qualified production soak' in e or 'approval must precede' in e for e in validate()),mode)
            finally:temp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
