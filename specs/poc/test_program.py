#!/usr/bin/env python3
"""Positive and negative tests for POC-PROTOCOL-V1."""

from __future__ import annotations

import importlib.util
import copy
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
            phone = dict(nodeId='fixture-android-node', deviceId='fixture-phone', physicalHostId='fixture-physical-phone', encoderBuild='fixture-av1-encoder', platform='android', isEmulator=False, isVirtualMachine=False)
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
                    sandbox_resource=next(r for r in execution['resources'] if r['id']=='RES-METADATA-SCALE')
                    env['syntheticHierarchySandbox']=dict(schemaVersion=1,configurationRef=sandbox_resource['configurationRef'],boundary=dict(schemaVersion=1,scope='LOCAL_FULL_V1',resourceId='RES-METADATA-SCALE',sandboxId='fixture-disposable-sandbox',mountId='fixture-controlled-mount',physicalHostId='fixture-scanner-host',controlled=True,disposable=True,rootPath='fixture-hierarchy'))
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
                probe_ref=new_prefix+'/raw/android-media-probe.yaml'
                write_yaml(root/probe_ref,dict(schemaVersion=1,kind='android_media_probe',nodeId=scope['nodeId'],encoderBuild=scope['encoderBuild'],inputSha256=scope['inputSha256'],outputArtifactRef=media_ref,outputSha256=scope['outputSha256'],decoderBuild='synthetic-fixture-decoder; never actual media validation',codec='av1',decodable=True,decodedFrameCount=120,durationSeconds=4,decodeErrorCount=0))
                env['androidMediaProbeRef']=probe_ref
                artifact_nodes[probe_ref]=scope['nodeId']
                execution['rawOutputRefs'].append(probe_ref)
                if production:
                    observation_ref=new_prefix+'/raw/android-scope-observation.log'
                    write_yaml(root/observation_ref,dict(schemaVersion=1,kind='physical_phone_observation',**{key:scope[key] for key in ('nodeId','deviceId','physicalHostId','encoderBuild')},temperaturePeakCelsius=38,powerPeakWatts=3,testDurationSeconds=60,backgroundSurvivedSeconds=60,observedStartedAt='2026-09-03T00:00:00Z',observedFinishedAt='2026-09-03T00:01:00Z'))
                    env['android_thermal_background_observation']['rawOutputRef']=observation_ref
                    artifact_nodes[observation_ref]=scope['nodeId']
                    execution['rawOutputRefs'].append(observation_ref)
                    if status=='pass':
                        a380_identity=dict(schemaVersion=1,resourceId='RES-A380-ESXI67',nodeId='fixture-a380-node',physicalHostId='fixture-esxi-host',guestId='fixture-a380-guest',platform='linux',hypervisorVendor='VMware',hypervisorProduct='ESXi',hypervisorVersion='6.7',hypervisorBuild='synthetic-esxi-build',gpuVendor='Intel',gpuModel='Arc A380',gpuDeviceId='fixture-a380-device',driverBuild='synthetic-driver-build',runtimeBuild='synthetic-worker-build',encoderBuild='synthetic-av1-build')
                        a380_resource=next(r for r in execution['resources'] if r['id']=='RES-A380-ESXI67')
                        env['productionPassthroughIdentity']=dict(schemaVersion=1,configurationRef=a380_resource['configurationRef'],identity=a380_identity)
                        env['worker_node_inventory'].append({key:value for key,value in a380_identity.items() if key not in ('schemaVersion','resourceId')})
                        soak_ref=new_prefix+'/raw/passthrough-soak-observation.log'
                        write_yaml(root/soak_ref,dict(schemaVersion=1,kind='passthrough_soak_observation',configurationRef=a380_resource['configurationRef'],identity=a380_identity,observedStartedAt='2026-09-03T00:00:00Z',observedFinishedAt='2026-09-05T00:00:00Z',continuous=True))
                        artifact_nodes[soak_ref]=a380_identity['nodeId']
                        execution['rawOutputRefs'].append(soak_ref)
                        env['productionPassthroughSoak']=dict(schemaVersion=1,configurationRef=a380_resource['configurationRef'],minimumContinuousDays=2,observedStartedAt='2026-09-03T00:00:00Z',observedFinishedAt='2026-09-05T00:00:00Z',rawOutputRef=soak_ref)
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
            if task_id=='POC-009' and status=='pass':
                env=execution['environmentCaptured']
                inference_ref=new_prefix+'/raw/inference-observation.yaml'
                env['inferenceObservationRef']=inference_ref
                write_yaml(root/inference_ref,dict(schemaVersion=1,kind='inference_observation',subjectVersion=CHECK.compliance_subject_version(plan,execution),inputSamples=[{key:s[key] for key in ('id','immutableId','checksum')} for s in execution['samples']],completedItemCount=60,observedStartedAt='2026-09-03T00:00:00Z',observedFinishedAt='2026-09-03T00:01:00Z'))
                execution['rawOutputRefs'].append(inference_ref)
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
            if task_id=='POC-009' and status=='pass':
                next(record for record in execution['environmentCaptured']['rawExecutionArtifacts'] if record['ref']==inference_ref)['artifactType']='measurement_output'
            if task_id=='POC-002':
                next(record for record in execution['environmentCaptured']['rawExecutionArtifacts'] if record['ref']==validation_ref)['artifactType']='measurement_output'
            if task_id=='POC-001':
                next(record for record in execution['environmentCaptured']['rawExecutionArtifacts'] if record['ref']==probe_ref)['artifactType']='measurement_output'
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
                floor_record['configuration']['productionPassthroughIdentity']=env['productionPassthroughIdentity']['identity']
                write_yaml(floor_path,floor_record)
            if task_id=='POC-005' and not production:
                sandbox_path=root/env['syntheticHierarchySandbox']['configurationRef']
                sandbox_record=load_yaml(sandbox_path)
                sandbox_record['configuration']['syntheticHierarchySandbox']=env['syntheticHierarchySandbox']['boundary']
                write_yaml(sandbox_path,sandbox_record)
            if task_id=='POC-001' and production and status=='pass':self.prepare_qualified_firmware_fixture(root,execution,new_prefix)
            if task_id=='POC-001' and production and status=='pass':self.prepare_qualified_passthrough_transitions_fixture(root,execution,new_prefix)
            if task_id=='POC-001' and status=='pass':self.prepare_qualified_worker_safety_fixture(root,execution,new_prefix)
            if task_id=='POC-001' and status=='pass':self.prepare_qualified_worker_capabilities_fixture(root,execution,new_prefix)
            if task_id=='POC-006' and not production and status=='pass':self.prepare_qualified_source_fault_fixture(root,execution,new_prefix)
            if task_id=='POC-010' and status=='pass':self.prepare_qualified_recovery_fixture(root,execution,new_prefix)
            if task_id=='POC-002' and production and status=='pass':self.prepare_qualified_a380_fixture(root,execution,new_prefix)
            if task_id=='POC-002' and status=='pass':self.prepare_qualified_quality_timing_fixture(root,execution,new_prefix)
            if task_id=='POC-002' and status=='pass':self.prepare_qualified_media_negative_fixture(root,execution,new_prefix)
            if task_id=='POC-002' and status=='pass':self.prepare_qualified_h264_fallback_fixture(root,execution,new_prefix)
            if task_id=='POC-002' and status=='pass':self.prepare_qualified_media_soak_fixture(root,execution,new_prefix)
            if task_id=='POC-002' and status=='pass':self.prepare_qualified_hls_ready_fixture(root,execution,new_prefix)
            if task_id=='POC-002' and status=='pass':self.prepare_qualified_media_scheduling_fixture(root,execution,new_prefix)
            if task_id=='POC-005' and status=='pass':self.prepare_qualified_metadata_scan_fixture(root,execution,new_prefix)
            if task_id=='POC-007' and status=='pass':self.prepare_qualified_access_fixture(root,execution,new_prefix)
            if task_id=='POC-007' and production and status=='pass':self.prepare_qualified_public_network_fixture(root,execution,new_prefix)
            if task_id=='POC-003' and status=='pass':self.prepare_qualified_range_fixture(root,execution,new_prefix)
            if task_id=='POC-008' and status=='pass':self.prepare_qualified_frontend_fixture(root,execution,new_prefix)
            if task_id=='POC-004' and not production and status=='pass':self.prepare_qualified_local_storage_fixture(root,execution,new_prefix)
            if task_id=='POC-009' and status=='pass':self.prepare_qualified_ai_results_fixture(root,execution,new_prefix)
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
        # A qualified record may use staged Own Evidence, but never an untracked reference.
        # Directory staging intentionally preserves ignored raw logs for test137's controls.
        subprocess.run(['git','-C',str(root),'add','--',str(Path(ref).parent)],check=True,capture_output=True)
        return root/ref

    def prepare_qualified_recovery_fixture(self,root,execution,prefix):
        """Synthetic recovery reports with real local signing/fixture decoding, not OpenBao restore."""
        env=execution['environmentCaptured'];artifact_records=env['rawExecutionArtifacts']
        def retain(name,data,kind='recovery_output'):
            ref=prefix+'/raw/'+name;path=root/ref
            if isinstance(data,dict):write_yaml(path,data)
            else:path.write_bytes(data)
            raw=path.read_bytes();digest='sha256:'+hashlib.sha256(raw).hexdigest()
            execution['rawOutputRefs'].append(ref);artifact_records.append(dict(ref=ref,artifactType=kind,byteCount=len(raw),sha256=digest))
            return ref,digest,len(raw)
        hash_value='sha256:'+'a'*64
        state=dict(database=dict(schemaSha256=hash_value,dataSha256=hash_value),permissions=[dict(userId='fixture-user',roleIds=['fixture-role'],permissionIds=['asset:read'])],assets=[dict(assetId='fixture-asset',version='fixture-v1',metadataSha256=hash_value)],sourceMappings=[dict(sourceId='fixture-source',assetId='fixture-asset',connectorId='fixture-connector',checkpoint='fixture-checkpoint')],replicas=[dict(replicaId='fixture-primary',assetId='fixture-asset',storageRef='fixture-storage',sha256=hash_value,state='verified',primary=True)],retention=[dict(assetId='fixture-asset',policyId='fixture-policy',lifecycleState='retained',scheduledAt='2026-09-06T00:00:00Z')],delivery=[dict(eventId='fixture-event',dedupId='fixture-dedup',aggregateId='fixture-asset',status='pending',publicationCount=0,inboxProcessedCount=0)],tasks=[dict(taskId='fixture-task',assetId='fixture-asset',status='running',attemptCount=1,ownerId='fixture-user')],openbao=dict(mountIds=['fixture-mount'],policyIds=['fixture-policy'],referenceIds=['secretref_fixture']),unreadableFixture=dict(fixtureId='fixture-corrupt-backup',backupSha256=hash_value,expectedErrorCode='DECRYPTION_MISMATCH'),revisions=[dict(revisionId='fixture-revision',assetId='fixture-asset',authorUserId='fixture-user',revisionNumber=1,provenanceSha256=hash_value)],indexEntries=[dict(entryId='fixture-index',assetId='fixture-asset',metadataSha256=hash_value)])
        state['permissions'][0]['scopedGrants']=[dict(grantId='fixture-read-grant',assetId='fixture-asset',permissionId='asset:read',disposition='allow',grantVersion=1,aclVersion=1)]
        state['assets'][0].update(visibility='PRIVATE',anonymousAccess=False,aclVersion=1)
        audit=dict(entryId='fixture-audit',sequence=0,entityId='fixture-asset',previousSha256='sha256:'+'0'*64)
        audit['event']=dict(actorId='fixture-user',occurredAt='2026-09-02T23:59:57Z',source='fixture-local-control',action='asset.read',reason='Approved recovery fixture',beforeSha256=hash_value,afterSha256=hash_value,result='succeeded',traceId='fixture-trace',approvalId=None,taskId='fixture-task')
        audit['sha256']='sha256:'+hashlib.sha256(json.dumps(audit,sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest();state['audit']=[audit]
        common=dict(schemaVersion=1,resourceId='RES-RECOVERY-SANDBOX',acceptanceProfile=env['acceptanceProfile'],subjectVersion=CHECK.compliance_subject_version({'pocId':'POC-10'},execution),inputSamples=[{key:s[key] for key in ('id','immutableId','checksum')} for s in execution['samples']])
        image_bytes=b'Synthetic deployment image; not an actual image.\n'
        verifier_build=subprocess.run(['openssl','version'],check=True,capture_output=True,text=True).stdout.strip()
        with tempfile.TemporaryDirectory(prefix='guize-signature-unit-fixture-') as signing:
            private=Path(signing)/'ephemeral.pem';image=Path(signing)/'image.bin';image.write_bytes(image_bytes)
            subprocess.run(['openssl','genpkey','-algorithm','ED25519','-out',str(private)],check=True,capture_output=True)
            public_bytes=subprocess.run(['openssl','pkey','-in',str(private),'-pubout'],check=True,capture_output=True).stdout
            signature_bytes=subprocess.run(['openssl','pkeyutl','-sign','-inkey',str(private),'-rawin','-in',str(image)],check=True,capture_output=True).stdout
        public_ref,public_sha,_=retain('approved-ed25519-public.pem',public_bytes)
        signer=dict(signerIdentity='fixture-approved-signer',algorithm='ed25519',publicKeyRef=public_ref,publicKeySha256=public_sha,verifierBuild=verifier_build)
        unreadable_observations=[]
        manifests=[]
        for phase in ('baseline','restored'):
            states=json.loads(json.dumps(state))
            context=dict(referenceId='secretref_fixture',method='hmac-sha256',comparisonContextId='fixture-approved-comparison-context')
            ref,digest,_=retain(phase+'-one-way-comparison.yaml',dict(schemaVersion=1,kind='one_way_value_comparison',**context,comparisonDigest=hash_value),'measurement_output')
            states['valueComparisons']=[dict(**context,artifactRef=ref,sha256=digest)]
            ref,digest,size=retain(phase+'-restored-file.bin',b'Synthetic file restore fixture; never an actual backup.\n')
            states['files']=[dict(logicalPath='fixture/restored-file.bin',artifactRef=ref,byteCount=size,sha256=digest)]
            ref,digest,size=retain(phase+'-playback-range.bin',b'Synthetic Range fixture only.\n')
            states['playback']=[dict(assetId='fixture-asset',authorizedUserId='fixture-user',statusCode=206,rangeStart=0,rangeEnd=size-1,artifactRef=ref,sha256=digest)]
            ref,digest,size=retain(phase+'-replica-readback.bin',b'Synthetic actual replica readback bytes.\n')
            states['replicas'][0].update(artifactRef=ref,sha256=digest,byteCount=size)
            bao=dict(schemaVersion=1,kind='openbao_nonsecret_configuration',subjectVersion=common['subjectVersion'],acceptanceProfile=common['acceptanceProfile'],mounts=[dict(mountId='fixture-mount',engineType='kv',engineVersion='2',options=dict(version='2',casRequired=True))],policies=[dict(policyId='fixture-policy',rules='path "fixture/*" { capabilities = ["read"] }')],authMethods=[dict(authId='fixture-userpass',methodType='userpass',configuration=dict(defaultLeaseSeconds=60))])
            ref,digest,_=retain(phase+'-openbao-config.yaml',bao,'measurement_output');states['openbao'].update(configurationRef=ref,configurationSha256=digest)
            encoded=json.dumps(bao,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf8');encoder=zlib.compressobj(wbits=31);control=encoder.compress(encoded)+encoder.flush()
            offset=len(control)-8;corrupt=control[:offset]+bytes([control[offset]^1])+control[offset+1:]
            self.assertEqual(json.loads(zlib.decompress(control,31)),bao)
            with self.assertRaises(zlib.error):zlib.decompress(corrupt,31)
            control_ref,control_sha,_=retain(phase+'-control-config-backup.gz',control)
            bad_ref,bad_sha,bad_size=retain(phase+'-corrupted-config-backup.gz',corrupt)
            states['unreadableFixture']=dict(fixtureId='fixture-corrupt-backup',backupSha256=bad_sha,expectedErrorCode='BACKUP_DECODE_FAILED',artifactRef=bad_ref,byteCount=bad_size,controlBackupRef=control_ref,controlBackupSha256=control_sha,codec='synthetic-openbao-config-gzip-json-v1',corruptionOffset=offset,corruptionXor=1)
            observation=dict(schemaVersion=1,kind='backup_decode_observation',fixtureId='fixture-corrupt-backup',codec='synthetic-openbao-config-gzip-json-v1',decoderBuild='python-stdlib-zlib-gzip-json-v1',controlBackupSha256=control_sha,backupSha256=bad_sha,controlDecodedSha256='sha256:'+hashlib.sha256(encoded).hexdigest(),controlOutcome='succeeded',restoreOutcome='failed',readbackOutcome='failed',errorCode='BACKUP_DECODE_FAILED',successfulReadCount=0)
            ref,_,_=retain(phase+'-backup-decode-observation.yaml',observation,'measurement_output');unreadable_observations.append(ref)
            image_ref,image_sha,_=retain(phase+'-image.bin',image_bytes)
            sig_ref,sig_sha,_=retain(phase+'-image-signature.bin',signature_bytes)
            verification_ref,_,_=retain(phase+'-signature-verification.yaml',dict(schemaVersion=1,kind='signature_verification',imageSha256=image_sha,signatureSha256=sig_sha,signerIdentity=signer['signerIdentity'],algorithm='ed25519',verified=True,publicKeySha256=public_sha,verifierBuild=verifier_build),'measurement_output')
            states['deployment']=[dict(imageId='fixture-image',imageArtifactRef=image_ref,imageSha256=image_sha,signatureArtifactRef=sig_ref,signatureSha256=sig_sha,signerIdentity='fixture-approved-signer',verificationRef=verification_ref)]
            report=dict(**common,kind='recovery_'+phase,observedStartedAt='2026-09-02T23:59:57Z' if phase=='baseline' else '2026-09-03T00:00:01Z',observedFinishedAt='2026-09-02T23:59:59Z' if phase=='baseline' else '2026-09-03T00:01:00Z',states=states)
            ref,sha,_=retain('recovery-'+phase+'.yaml',report,'measurement_output');manifests.append((ref,sha,report))
        baseline_ref,baseline_sha,baseline=manifests[0];restored_ref,restored_sha,restored=manifests[1]
        rows=[dict(gate=gate,before={d:CHECK.recovery_domain_digest(baseline['states'][d]) for d in domains},after={d:CHECK.recovery_domain_digest(restored['states'][d]) for d in domains}) for gate,domains in CHECK.RECOVERY_GATE_DOMAINS.items()]
        comparison=dict(**common,kind='recovery_comparison',baselineRef=baseline_ref,baselineSha256=baseline_sha,restoredRef=restored_ref,restoredSha256=restored_sha,observedStartedAt='2026-09-03T00:01:00Z',observedFinishedAt='2026-09-03T00:02:00Z',rows=rows,replayedEventIds=['fixture-event'],postReplayDelivery=[{**item,'status':'processed','publicationCount':1,'inboxProcessedCount':1} for item in state['delivery']],unreadableWitness=dict(fixtureId='fixture-corrupt-backup',backupSha256=baseline['states']['unreadableFixture']['backupSha256'],errorCode='BACKUP_DECODE_FAILED',restoreOutcome='failed',readbackOutcome='failed',successfulReadCount=0,observationRef=unreadable_observations[-1]))
        comparison_ref,_,_=retain('recovery-comparison.yaml',comparison,'measurement_output')
        resource=next(r for r in execution['resources'] if r['id']=='RES-RECOVERY-SANDBOX');config_path=root/resource['configurationRef'];config=load_yaml(config_path)
        config['configuration']['recoveryBaseline']=dict(baselineRef=baseline_ref,baselineSha256=baseline_sha,approvedReplayEventIds=['fixture-event'],approvedComparisonContexts=[{key:item[key] for key in ('referenceId','method','comparisonContextId')} for item in baseline['states']['valueComparisons']],approvedSigners=[signer],approvedUnreadableFixture={key:baseline['states']['unreadableFixture'][key] for key in ('fixtureId','backupSha256','controlBackupSha256','codec','corruptionOffset','corruptionXor')});write_yaml(config_path,config)
        env['recoveryEvidence']=dict(configurationRef=resource['configurationRef'],baselineRef=baseline_ref,restoredRef=restored_ref,comparisonRef=comparison_ref)
        subjects=dict(recoveryRunId='fixture-recovery-run',physicalHostId='fixture-recovery-host',serviceSetId='fixture-services',vmSetId='fixture-vm-set',authorizedUserId='fixture-user',assetId='fixture-asset',backupCheckpointAt='2026-09-02T23:59:59Z')
        config['approvedAt']='2026-09-03T00:00:00Z';config['configuration']['recoveryTimingSubjects']=subjects;write_yaml(config_path,config)
        events=[]
        for event in ('backup_checkpoint','recoverable_data_boundary','recovery_started','services_ready','vm_set_ready','authenticated_browsing_succeeded','authorized_playback_succeeded','recovery_completed'):
            at=subjects['backupCheckpointAt'] if event=='backup_checkpoint' else '2026-09-03T00:00:00Z' if event in ('recoverable_data_boundary','recovery_started') else '2026-09-03T00:00:01Z'
            ref,_,_=retain('recovery-event-'+event+'.yaml',dict(**common,kind='recovery_business_event',subjects=subjects,event=event,observedAt=at,outcome='succeeded'),'measurement_output')
            events.append(dict(event=event,observedAt=at,witnessRef=ref))
        timing_ref,_,_=retain('recovery-timing.yaml',dict(**common,kind='recovery_timing_report',subjects=subjects,**{key:env['recoveryEvidence'][key] for key in ('configurationRef','baselineRef','restoredRef','comparisonRef')},events=events),'measurement_output')
        env['recoveryTimingRef']=timing_ref


    def prepare_qualified_a380_fixture(self,root,execution,prefix):
        """Synthetic A380 identity and observations for schema tests, never hardware evidence."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-A380-ENCODE');node=env['worker_node_inventory'][0];run=env['workerEncodeExecutions'][0]
        identity=dict(schemaVersion=1,resourceId='RES-A380-ENCODE',**{k:node[k] for k in ('nodeId','platform','physicalHostId','encoderBuild')},gpuVendor='Intel',gpuModel='Arc A380',gpuDeviceId='synthetic-a380-device',driverBuild='synthetic-driver',runtimeBuild='synthetic-runtime',encoderBackend='hardware')
        node.update({k:v for k,v in identity.items() if k not in ('schemaVersion','resourceId')});run.update({k:identity[k] for k in ('gpuDeviceId','driverBuild','runtimeBuild','encoderBackend')})
        phases=[dict(phase=name,startedAt=f'2026-09-03T00:00:{start:02d}Z',finishedAt=f'2026-09-03T00:00:{end:02d}Z' if end<60 else '2026-09-03T00:01:00Z') for name,start,end in (('warmup',0,20),('concurrency',20,40),('soak',40,60))]
        sampling=dict(toolBuild='synthetic-telemetry-tool-v1',intervalSeconds=10,scope='device',phases=phases)
        config_path=root/resource['configurationRef'];config=load_yaml(config_path);config['configuration']['productionA380Encode']=dict(identity=identity,telemetrySampling=sampling,outputServingPath='/synthetic/a380-output');write_yaml(config_path,config)
        def retain(name,data,kind='measurement_output'):
            ref=prefix+'/raw/'+name;path=root/ref
            if isinstance(data,bytes):path.write_bytes(data)
            else:write_yaml(path,data)
            raw=path.read_bytes();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,nodeId=identity['nodeId'],byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));execution['rawOutputRefs'].append(ref);return ref
        common=dict(schemaVersion=1,identity=identity,configurationRef=resource['configurationRef'],**{k:run[k] for k in ('inputSampleId','inputSha256','outputArtifactRef','outputSha256')})
        samples=[dict(observedAt=f'2026-09-03T00:00:{second:02d}Z' if second<60 else '2026-09-03T00:01:00Z',phase='warmup' if second<20 else 'concurrency' if second<40 else 'soak',powerWatts=1,temperatureCelsius=1) for second in range(0,61,10)]
        telemetry_ref=retain('a380-telemetry.yaml',dict(**common,kind='a380_telemetry_observation',sampling=sampling,samples=samples))
        body=(root/run['outputArtifactRef']).read_bytes()[:8];body_ref=retain('a380-range-body.bin',body,'produced_media')
        range_ref=retain('a380-range.yaml',dict(**common,kind='a380_range_observation',mediaPath='/synthetic/a380-output',requestRange='bytes=0-7',rangeStart=0,rangeEnd=7,statusCode=206,contentRange=f'bytes 0-7/{(root/run["outputArtifactRef"]).stat().st_size}',requestStartedAt='2026-09-03T00:01:00Z',firstByteAt='2026-09-03T00:01:00.001Z',responseBodyRef=body_ref,responseSha256='sha256:'+hashlib.sha256(body).hexdigest()))
        env['productionA380Encode']=dict(schemaVersion=1,identity=identity,configurationRef=resource['configurationRef'],outputArtifactRef=run['outputArtifactRef'],telemetryRef=telemetry_ref,rangeRef=range_ref)


    def prepare_qualified_access_fixture(self,root,execution,prefix):
        """Retained synthetic request/response cases, never actual ACL or network execution."""
        env=execution['environmentCaptured'];local=env['acceptanceProfile']['id']=='local-v1';resource_id='RES-LOCAL-ACCESS-PATH' if local else 'RES-PUBLIC-NETWORK';resource=next(r for r in execution['resources'] if r['id']==resource_id)
        tls=env.get('local_tls_path_configuration') or {};entry=tls.get('entryOrigin','https://synthetic-public.invalid');origin=tls.get('openlistOrigin','https://synthetic-source.invalid')
        policy=dict(assetId='synthetic-protected-asset',sourceVersion='synthetic-source-version',aclVersion='synthetic-current-acl',authorizedUserId='synthetic-allowed-user',deniedUserId='synthetic-denied-user',authorizedGrantId='synthetic-current-grant',deniedGrantId='synthetic-denied-subject-grant',expiredGrantId='synthetic-expired-grant',grantValidFrom='2026-09-03T00:00:00Z',grantValidUntil='2026-09-04T00:00:00Z',expiredAt='2026-09-02T00:00:00Z',protectedCacheKey='synthetic-cache-asset-version',maximumBufferedBytes=4096,rateLimit=dict(maximumRequests=2,windowSeconds=10),paths=dict(range=entry+'/protected/range',stream=entry+'/protected/stream',source=origin+'/protected/source',admin=origin+'/api/admin',worker='http://127.0.0.1:17000/protected/worker'))
        config_path=root/resource['configurationRef'];config=load_yaml(config_path);config['configuration']['accessPolicy']=policy;write_yaml(config_path,config)
        sample=execution['samples'][0];source=root/env['inputSampleArtifacts'][0]['inputArtifactRef'];data=source.read_bytes();etag='"'+sample['checksum'].removeprefix('sha256:')+'"'
        def retain(name,data,kind):
            ref=prefix+'/raw/'+name;path=root/ref
            if isinstance(data,bytes):path.write_bytes(data)
            else:write_yaml(path,data)
            raw=path.read_bytes();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));execution['rawOutputRefs'].append(ref);return ref
        common=dict(configurationRef=resource['configurationRef'],pathConfigurationRef=env['acceptanceProfileConfigurationRef'],resourceId=resource_id,acceptanceProfile=env['acceptanceProfile'],subjectVersion=CHECK.compliance_subject_version(load_yaml(self.plan_path(root,'POC-007')),execution),inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']],assetId=policy['assetId'],sourceVersion=policy['sourceVersion'],aclVersion=policy['aclVersion'],inputSampleId=sample['id'])
        cases=[]
        names=['authorized_range','authorized_if_range','authorized_stream','unauthorized','expired','cross_user','rate_limit']+(['direct_source','direct_admin','direct_worker'] if local else [])
        for case in names:
            authorized=case.startswith('authorized_');stream=case=='authorized_stream';body=data if stream else data[:8] if authorized else b'';body_ref=retain('access-'+case+'-body.bin',body,'produced_media')
            role='stream' if stream else case.removeprefix('direct_') if case.startswith('direct_') else 'range'
            user=policy['authorizedUserId'] if authorized or case in ('expired','rate_limit') else policy['deniedUserId'] if case=='cross_user' else 'anonymous'
            grant=policy['authorizedGrantId'] if authorized or case=='rate_limit' else policy['expiredGrantId'] if case=='expired' else policy['deniedGrantId'] if case=='cross_user' else None
            at='2026-09-03T00:00:03Z' if case=='rate_limit' else '2026-09-03T00:00:02Z' if case=='cross_user' else '2026-09-03T00:00:01Z'
            witness=dict(schemaVersion=1,kind='access_request_outcome',**common,case=case,observedAt=at,userId=user,grantId=grant,requestURL=policy['paths'][role],rangeStart=0,rangeEnd=len(data)-1 if stream else 7,requestRange='' if stream else 'bytes=0-7',ifRange=etag if case=='authorized_if_range' else '',statusCode=200 if stream else 206 if authorized else 429 if case=='rate_limit' else 403,etag=etag if authorized else '',contentRange='' if stream or not authorized else f'bytes 0-7/{len(data)}',cacheKey=policy['protectedCacheKey'],responseBodyRef=body_ref,responseSha256='sha256:'+hashlib.sha256(body).hexdigest(),responseByteCount=len(body),maximumBufferedBytes=min(4096,len(body)),requestCount=3 if case=='rate_limit' else 1,originRequestCount=2 if case=='rate_limit' else 1 if authorized else 0,rateWindowSeconds=10,rateAttempts=[dict(sequence=i,observedAt=f'2026-09-03T00:00:0{i}Z',statusCode=206 if i<=2 else 429,originContacted=i<=2) for i in range(1,4)] if case=='rate_limit' else [])
            for attempt in witness['rateAttempts']:
                returned=data[:8] if attempt['sequence']<=2 else body
                returned_ref=retain('access-rate-attempt-'+str(attempt['sequence'])+'-body.bin',returned,'produced_media') if attempt['sequence']<=2 else body_ref
                attempt.update(responseBodyRef=returned_ref,responseSha256='sha256:'+hashlib.sha256(returned).hexdigest(),responseByteCount=len(returned))
            ref=retain('access-'+case+'.yaml',witness,'measurement_output');cases.append(dict(case=case,witnessRef=ref))
        env['accessOutcomeRef']=retain('access-outcomes.yaml',dict(schemaVersion=1,kind='access_outcome_report',**common,cases=cases),'measurement_output')


    def prepare_qualified_frontend_fixture(self,root,execution,prefix):
        """Synthetic frontend observations; never actual prototypes or build/UI execution."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-FRONTEND-COMPARE');sample=execution['samples'][0];input_record=next(r for r in env['inputSampleArtifacts'] if r['sampleId']==sample['id'])
        scenarios=[dict(scenarioId=scenario,fixtureId='synthetic-'+scenario,arguments=dict(rowCount=1000000,viewportRows=30,overscanRows=5) if scenario=='million_row_virtual_list_equivalent' else dict(controlledFixture='synthetic-'+scenario),expectedResults={action:dict(fixture='synthetic-'+scenario,interaction=action,normalizedOutcome='synthetic-expected-state') for action in actions}) for scenario,actions in CHECK.FRONTEND_SCENARIO_ACTIONS.items()]
        path=root/input_record['inputArtifactRef'];write_yaml(path,dict(schemaVersion=1,kind='frontend_fixed_scenario_fixture',scenarios=scenarios));raw=path.read_bytes();digest='sha256:'+hashlib.sha256(raw).hexdigest();sample['checksum']=digest;input_record.update(byteCount=len(raw),sha256=digest);approval=load_yaml(root/sample['approvalRef']);approval['checksum']=digest;write_yaml(root/sample['approvalRef'],approval)
        def retain(name,data,kind):
            ref=prefix+'/raw/'+name;path=root/ref
            if isinstance(data,bytes):path.write_bytes(data)
            else:write_yaml(path,data)
            raw=path.read_bytes();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));execution['rawOutputRefs'].append(ref);return ref,'sha256:'+hashlib.sha256(raw).hexdigest(),len(raw)
        identities=[];rows=[]
        for candidate in ('vue','react'):
            lock_ref,lock_sha,_=retain(candidate+'-dependency-lock.json',json.dumps(dict(synthetic=True,candidate=candidate,version='synthetic-locked-'+candidate)).encode(),'command_output');identity=dict(candidateId=candidate,frameworkVersion='synthetic-locked-'+candidate,sourceRevision='synthetic-'+candidate+'-source-snapshot',compilerBuild='synthetic-pinned-compiler',lockRef=lock_ref,lockSha256=lock_sha,commandArgs=['synthetic-build',candidate]);identities.append(identity);build_id='synthetic-'+candidate+'-build'
            bundle_ref,bundle_sha,bundle_size=retain(candidate+'-bundle.js',('/* Synthetic '+candidate+' bundle; never an actual build. */').encode(),'command_output');build_ref,_,_=retain(candidate+'-build.yaml',dict(schemaVersion=1,kind='frontend_build_observation',identity=identity,buildId=build_id,startedAt='2026-09-03T00:00:00Z',finishedAt='2026-09-03T00:00:01Z',exitCode=0,bundles=[dict(ref=bundle_ref,sha256=bundle_sha,byteCount=bundle_size)]),'measurement_output')
            case_rows=[]
            for scenario in scenarios:
                actions=[dict(actionId=action,startedAt='2026-09-03T00:00:02Z',finishedAt='2026-09-03T00:00:02Z',result=value) for action,value in scenario['expectedResults'].items()];ref,_,_=retain(candidate+'-'+scenario['scenarioId']+'.yaml',dict(schemaVersion=1,kind='frontend_scenario_observation',candidateId=candidate,buildId=build_id,scenarioId=scenario['scenarioId'],fixtureId=scenario['fixtureId'],inputSha256=sample['checksum'],scenarioDriverBuild='synthetic-pinned-ui-driver',startedAt='2026-09-03T00:00:02Z',finishedAt='2026-09-03T00:00:03Z',status='completed',actions=actions,measurements=[dict(measurementId='interaction_duration',unit='ms',value=1000)]+([dict(measurementId='measured_input_rows',unit='rows',value=1000000),dict(measurementId='rendered_dom_rows_peak',unit='rows',value=30 if candidate=='vue' else 40)] if scenario['scenarioId']=='million_row_virtual_list_equivalent' else [])),'measurement_output');case_rows.append(dict(scenarioId=scenario['scenarioId'],observationRef=ref))
            score_rows=[]
            for criterion in ('ecosystem_team_fit','component_reuse','long_term_maintenance'):
                ref,_,_=retain(candidate+'-'+criterion+'.yaml',dict(schemaVersion=1,kind='frontend_rubric_observation',candidateId=candidate,buildId=build_id,rubricId='synthetic-fixed-rubric',rubricVersion='synthetic-rubric-version',criterionId=criterion,assessorId='synthetic-approved-assessor',observedAt='2026-09-03T00:00:04Z',grade=1,basis='Synthetic rubric justification; never an actual team assessment.',scenarioRefs=[r['observationRef'] for r in case_rows]),'measurement_output');score_rows.append(dict(criterionId=criterion,observationRef=ref))
            rows.append(dict(candidateId=candidate,buildRef=build_ref,scenarios=case_rows,scores=score_rows))
            if candidate=='vue':baseline_bytes=bundle_size
        policy=dict(inputSampleId=sample['id'],scenarioDriverBuild='synthetic-pinned-ui-driver',candidates=identities,bundleCandidate='vue',scoreCandidate='vue',rubricId='synthetic-fixed-rubric',rubricVersion='synthetic-rubric-version',assessorId='synthetic-approved-assessor',criteria=[dict(criterionId=criterion,weight=1) for criterion in ('ecosystem_team_fit','component_reuse','long_term_maintenance')],gradeValues=[1,2,3,4,5]);config_path=root/resource['configurationRef'];config=load_yaml(config_path);config['configuration']['frontendComparisonPolicy']=policy;write_yaml(config_path,config)
        report=dict(schemaVersion=1,kind='frontend_comparison_report',configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=CHECK.compliance_subject_version(load_yaml(self.plan_path(root,'POC-008')),execution),inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']],inputFixtureRef=input_record['inputArtifactRef'],inputFixtureSha256=sample['checksum'],candidates=rows);ref,_,_=retain('frontend-comparison.yaml',report,'measurement_output');env['frontendComparisonRef']=ref
        for measurement in execution['measurements']:
            if measurement['id']=='prototype_coverage':measurement['actual']=100
            elif measurement['id']=='bundle_baseline':measurement['actual']=baseline_bytes/1024


    def prepare_qualified_metadata_scan_fixture(self,root,execution,prefix):
        """Synthetic metadata/control records, never a scanner workload measurement."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-METADATA-SCALE');sample=execution['samples'][0];input_record=next(r for r in env['inputSampleArtifacts'] if r['sampleId']==sample['id'])
        objects=[dict(objectId='synthetic-directory-1',kind='directory',versionId='version-1',depth=1,fileSizeBytes=0),dict(objectId='synthetic-file-1',kind='file',versionId='version-1',depth=1,fileSizeBytes=1)]
        baseline_bytes=b''.join((json.dumps(record,separators=(',',':'))+'\n').encode() for record in objects);(root/input_record['inputArtifactRef']).write_bytes(baseline_bytes);digest='sha256:'+hashlib.sha256(baseline_bytes).hexdigest();sample['checksum']=digest;input_record.update(byteCount=len(baseline_bytes),sha256=digest);approval=load_yaml(root/sample['approvalRef']);approval['checksum']=digest;write_yaml(root/sample['approvalRef'],approval)
        def retain(name,records):
            raw=b''.join((json.dumps(record,separators=(',',':'))+'\n').encode() for record in records);ref=prefix+'/raw/'+name;(root/ref).write_bytes(raw);digest='sha256:'+hashlib.sha256(raw).hexdigest();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType='command_output',byteCount=len(raw),sha256=digest));execution['rawOutputRefs'].append(ref);return dict(ref=ref,sha256=digest,count=len(records))
        changes=[dict(eventId='synthetic-change-'+str(i),sequence=i,objectId=object_id,operation=operation,beforeVersion=before,afterVersion=after) for i,object_id,operation,before,after in ((1,'synthetic-file-1','update','version-1','version-2'),(2,'synthetic-file-2','create','absent','version-1'),(3,'synthetic-file-1','delete','version-2','absent'))]
        policy=dict(manifestId=sample['immutableId'],baselineInputSampleId=sample['id'],scannerBuild=CHECK.compliance_subject_version(load_yaml(self.plan_path(root,'POC-005')),execution),scanId='synthetic-baseline-scan',changeSetId='synthetic-controlled-changes',hierarchyGenerator=copy.deepcopy(env.get('synthetic_hierarchy_manifest',{}).get('generator')) if isinstance(env.get('synthetic_hierarchy_manifest'),dict) else None,baseline=dict(ref=input_record['inputArtifactRef'],sha256=digest,count=len(objects)),expectedChanges=retain('approved-metadata-changes.jsonl',changes))
        if policy['hierarchyGenerator'] is None:policy.pop('hierarchyGenerator')
        config_path=root/resource['configurationRef'];config=load_yaml(config_path);config['configuration']['metadataScanPolicy']=policy;write_yaml(config_path,config)
        report=dict(schemaVersion=1,kind='metadata_scan_observation',configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=policy['scannerBuild'],inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']],manifestId=policy['manifestId'],scannerBuild=policy['scannerBuild'],enumeration=dict(scanId=policy['scanId'],startedAt='2026-09-03T00:00:00Z',finishedAt='2026-09-03T00:00:02Z',objects=retain('enumerated-metadata.jsonl',objects)),changeStream=dict(changeSetId=policy['changeSetId'],startedAt='2026-09-03T00:00:05Z',finishedAt='2026-09-03T00:00:15Z',events=retain('observed-metadata-changes.jsonl',[dict(**event,observedAt=f'2026-09-03T00:00:0{event["sequence"]+5}Z') for event in changes])),incremental=dict(changeSetId=policy['changeSetId'],startedAt='2026-09-03T00:00:16Z',finishedAt='2026-09-03T00:00:20Z',appliedEvents=retain('applied-metadata-changes.jsonl',[dict(eventId=event['eventId']) for event in changes]),traversedObjects=retain('incremental-metadata-visits.jsonl',[dict(objectId=record['objectId']) for record in objects]+[dict(objectId='synthetic-file-2')])))
        ref=prefix+'/raw/metadata-scan.yaml';path=root/ref;write_yaml(path,report);raw=path.read_bytes();env['metadataScanRef']=ref;env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType='measurement_output',byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));execution['rawOutputRefs'].append(ref)
        for measurement in execution['measurements']:
            if measurement['id']=='source_change_frequency':measurement['actual']=1080
            elif measurement['id']=='incremental_scan_cost':measurement['actual']=4
        self.prepare_qualified_metadata_resource_fixture(root,execution,prefix,policy)
        self.prepare_qualified_metadata_profiling_fixture(root,execution,prefix,policy)



    def prepare_qualified_media_scheduling_fixture(self,root,execution,prefix,total_capacity=2,per_node_capacity=1):
        """Synthetic queue/media observations only; never actual FFmpeg admission or preemption."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-HETEROGENEOUS-WORKERS');config_path=root/resource['configurationRef'];config=load_yaml(config_path);security=config['configuration']['mediaNegativePolicy'];nodes=env['worker_node_inventory'];sample=execution['samples'][0]
        context={k:security[k] for k in ('assetId','assetVersion','authorizedUserId','deniedUserId','currentGrantId','expiredGrantId','revokedGrantId','aclVersion','grantValidFrom','grantValidUntil','revokedAt')}
        assert (total_capacity,per_node_capacity) in ((2,1),(3,2))
        generated=lambda ref:ref.startswith(prefix+'/raw/scheduler-') or ref==prefix+'/raw/media-scheduling.yaml'
        env['rawExecutionArtifacts']=[a for a in env['rawExecutionArtifacts'] if not generated(a['ref'])];execution['rawOutputRefs']=[ref for ref in execution['rawOutputRefs'] if not generated(ref)]
        specs=[];rows=[];times={}
        clock=lambda s:('2026-09-03T00:'+str(int(s)//60).zfill(2)+':'+format(s%60,'06.3f')+'Z')
        def retain(name,value,kind,node):
            ref=prefix+'/raw/'+name
            if isinstance(value,bytes):(root/ref).write_bytes(value)
            else:write_yaml(root/ref,value)
            raw=(root/ref).read_bytes();digest='sha256:'+hashlib.sha256(raw).hexdigest();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,nodeId=node,byteCount=len(raw),sha256=digest));execution['rawOutputRefs'].append(ref);return ref,digest
        schedule=[('background','background',0,0,0,20,20.5,0,'current'),('aging','background',0,22,22,24,24.5,0,'current'),('playback','playback',1,2,2,4,4.5,1,'current'),('prewarm','prewarm',1,20,20,22,22.5,0,'current'),('denied','playback',1,None,None,None,None,1,'denied'),('expired','playback',1,None,None,None,None,1,'expired'),('revoked','playback',61,None,None,None,None,1,'revoked')]
        if total_capacity==3:schedule.insert(1,('background-extra','background',0,0,0,20,20.5,0,'current'))
        for job,purpose,q,a,s,f,ready,node_index,permission in schedule:
            node=nodes[node_index];user=context['deniedUserId'] if permission=='denied' else context['authorizedUserId'];grant=context['expiredGrantId'] if permission=='expired' else context['revokedGrantId'] if permission=='revoked' else context['currentGrantId']
            spec=dict(jobId='synthetic-scheduling-'+job,purpose=purpose,nodeId=node['nodeId'],encoderBuild=node['encoderBuild'],userId=user,grantId=grant,aclVersion=context['aclVersion'],demandEpoch=1,sourceStartFrame=0,sourceEndFrame=40);specs.append(spec);times[spec['jobId']]=(q,a,s,f,ready)
            row=dict(**spec,queuedAt=clock(q),admittedAt=clock(a) if a is not None else None,startedAt=clock(s) if s is not None else None,finishedAt=clock(f) if f is not None else None,readyAt=clock(ready) if ready is not None else None,outputArtifactRef=None,outputSha256=None,decodeRef=None,denialBodyRef=None,denialBodySha256=None)
            if a is None:row['denialBodyRef'],row['denialBodySha256']=retain('scheduler-'+job+'-denied.bin',b'','produced_media',node['nodeId'])
            else:
                row['outputArtifactRef'],row['outputSha256']=retain('scheduler-'+job+'-av1.bin',('Synthetic '+job+' scheduling AV1 bytes; never actual encoded media.').encode(),'produced_media',node['nodeId'])
                row['decodeRef'],_=retain('scheduler-'+job+'-decode.yaml',dict(schemaVersion=1,kind='media_scheduling_decode',jobId=spec['jobId'],demandEpoch=1,nodeId=node['nodeId'],encoderBuild=node['encoderBuild'],decoderBuild='synthetic-scheduling-decoder',inputSampleId=sample['id'],inputSha256=sample['checksum'],sourceStartFrame=spec['sourceStartFrame'],sourceEndFrame=spec['sourceEndFrame'],outputArtifactRef=row['outputArtifactRef'],outputSha256=row['outputSha256'],observedAt=clock(ready),codec='av1',decodedFrameCount=40,decodeErrorCount=0,decodable=True),'measurement_output',node['nodeId'])
            rows.append(row)
        policy=dict(schedulerBuild='synthetic-cooperative-scheduler',decoderBuild='synthetic-scheduling-decoder',demandEpoch=1,inputSampleId=sample['id'],inputSha256=sample['checksum'],sourceFrameCount=120,context=context,totalCapacity=total_capacity,perNodeCapacity=per_node_capacity,reservedPlaybackSlots=1,agingStepSeconds=5,agingFloorPriority=1,maximumAdmissionSeconds=2,maximumFirstReadySeconds=5,playbackJobId='synthetic-scheduling-playback',prewarmJobId='synthetic-scheduling-prewarm',agingJobId='synthetic-scheduling-aging',saturationJobIds=['synthetic-scheduling-background']+(['synthetic-scheduling-background-extra'] if total_capacity==3 else []),jobs=specs)
        config['configuration']['mediaSchedulingPolicy']=policy;write_yaml(config_path,config);snapshots=[]
        for at in (0,1,2,4,4.5,20,22,24.5,61,62):
            states=[]
            for spec in specs:
                q,a,s,f,ready=times[spec['jobId']];state='not_queued' if at<q else 'denied' if a is None else 'queued' if at<a else 'admitted' if at<s else 'running' if at<f else 'completed' if at<ready else 'ready';base={'playback':0,'prewarm':3,'background':6}[spec['purpose']];aged_at=min(at,a) if a is not None else at;effective=0 if base==0 else max(1,base-int(max(0,aged_at-q)//5));states.append(dict(jobId=spec['jobId'],state=state,basePriority=base,effectivePriority=effective))
            snapshots.append(dict(observedAt=clock(at),jobs=states))
        h264=load_yaml(root/env['h264FallbackRef']);fallback=dict(jobId=policy['playbackJobId'],observedAt=clock(3),userId=context['authorizedUserId'],grantId=context['currentGrantId'],aclVersion=context['aclVersion'],assetId=context['assetId'],assetVersion=context['assetVersion'],demandEpoch=1,outputArtifactRef=h264['outputArtifactRef'],outputSha256=h264['outputSha256'],decodeRef=h264['decodeRef'])
        report=dict(schemaVersion=1,kind='media_scheduling_observation',configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=CHECK.compliance_subject_version(load_yaml(self.plan_path(root,'POC-002')),execution),inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']],context=context,schedulerBuild=policy['schedulerBuild'],demandEpoch=1,jobs=rows,snapshots=snapshots,admissionLatencySeconds=1,firstReadyLatencySeconds=3.5,preemptedRunningProcessIds=[],fallback=fallback)
        env['mediaSchedulingRef'],_=retain('media-scheduling.yaml',report,'measurement_output',nodes[0]['nodeId'])
        # Seal this synthetic scheduling fixture after its retained artifacts are complete.
        subprocess.run(['git','-C',str(root),'add','--',prefix],check=True,capture_output=True)

    def prepare_qualified_hls_ready_fixture(self,root,execution,prefix):
        """Synthetic HLS sequence only, never runtime encode or playback evidence."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-HETEROGENEOUS-WORKERS');sample=execution['samples'][0];segments=[];rows=[]
        def retain(name,value,kind,node):
            ref=prefix+'/raw/'+name
            if isinstance(value,bytes):(root/ref).write_bytes(value)
            else:write_yaml(root/ref,value)
            raw=(root/ref).read_bytes();sha='sha256:'+hashlib.sha256(raw).hexdigest();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,nodeId=node,byteCount=len(raw),sha256=sha));execution['rawOutputRefs'].append(ref);return ref,sha,len(raw)
        job='synthetic-hls-job';decoder='synthetic-hls-decoder'
        init,init_sha,_=retain('hls-init.mp4',b'Synthetic fMP4 initialization; never actual media.','produced_media',env['worker_node_inventory'][0]['nodeId'])
        for n in range(3):
            node=env['worker_node_inventory'][n%2];segment=dict(segmentId='synthetic-hls-'+str(n),index=n,**{k:node[k] for k in ('nodeId','physicalHostId','encoderBuild','compatibilityGroupId')},sourceStartFrame=n*40,sourceEndFrame=(n+1)*40,uri='segment-'+str(n)+'.m4s');segments.append(segment)
            start=0 if n<2 else 20;finish=(20,10,30)[n];at=lambda seconds:f'2026-09-03T00:00:{seconds:02d}Z'
            media,sha,size=retain('hls-segment-'+str(n)+'.bin',('Synthetic HLS segment '+str(n)+'; never actual AV1.').encode(),'produced_media',node['nodeId'])
            probe,_,_=retain('hls-segment-'+str(n)+'-decode.yaml',dict(schemaVersion=1,kind='hls_segment_decode',jobId=job,attemptEpoch=1,segmentId=segment['segmentId'],nodeId=node['nodeId'],encoderBuild=node['encoderBuild'],decoderBuild=decoder,inputSha256=sample['checksum'],outputArtifactRef=media,outputSha256=sha,initArtifactRef=init,initSha256=init_sha,observedAt=at(finish),codec='av1',decodable=True,decodedFrameCount=40,decodeErrorCount=0),'measurement_output',node['nodeId'])
            rows.append(dict(**segment,startedAt=at(start),finishedAt=at(finish),readyAt=at(finish),exitCode=0,encodedFrameCount=40,outputArtifactRef=media,outputSha256=sha,outputByteCount=size,decodeRef=probe))
        policy=dict(jobId=job,attemptEpoch=1,inputSampleId=sample['id'],inputSha256=sample['checksum'],sourceFrameCount=120,framesPerSecond=30,decoderBuild=decoder,segments=segments,initNodeId=env['worker_node_inventory'][0]['nodeId'],initUri='init.mp4')
        config_path=root/resource['configurationRef'];config=load_yaml(config_path);config['configuration']['hlsReadyPolicy']=policy;write_yaml(config_path,config)
        snapshots=[]
        for seconds,ready_ids,prefix_count in ((11,{1},0),(21,{0,1},2),(31,{0,1,2},3)):
            lines=['#EXTM3U','#EXT-X-VERSION:7','#EXT-X-TARGETDURATION:2','#EXT-X-MEDIA-SEQUENCE:0','#EXT-X-MAP:URI="init.mp4"']
            for segment in segments[:prefix_count]:lines.extend(['#EXTINF:1.333333,',segment['uri']])
            if prefix_count==3:lines.append('#EXT-X-ENDLIST')
            ref,sha,_=retain('hls-playlist-'+str(seconds)+'.m3u8',('\n'.join(lines)+'\n').encode(),'command_output',env['worker_node_inventory'][0]['nodeId'])
            snapshots.append(dict(observedAt=f'2026-09-03T00:00:{seconds:02d}Z',segmentStates=[dict(segmentId=s['segmentId'],state='ready' if s['index'] in ready_ids else 'queued' if seconds<int(rows[s['index']]['startedAt'][17:19]) else 'encoding') for s in segments],playlistRef=ref,playlistSha256=sha))
        report=dict(schemaVersion=1,kind='hls_ready_observation',configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=CHECK.compliance_subject_version(load_yaml(self.plan_path(root,'POC-002')),execution),inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']],initArtifactRef=init,initSha256=init_sha,initReadyAt='2026-09-03T00:00:00Z',**{k:policy[k] for k in ('jobId','attemptEpoch','inputSampleId','inputSha256','initNodeId','initUri')},segments=rows,snapshots=snapshots)
        ref,_,_=retain('hls-ready.yaml',report,'measurement_output',env['worker_node_inventory'][0]['nodeId']);env['hlsReadyRef']=ref


    def prepare_qualified_media_soak_fixture(self,root,execution,prefix):
        """Synthetic continuous codec counters; never a real soak or encoder workload."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-HETEROGENEOUS-WORKERS');sample=execution['samples'][0];cases=[];rows=[]
        def retain(name,value,kind,node):
            ref=prefix+'/raw/'+name
            if isinstance(value,bytes):(root/ref).write_bytes(value)
            else:write_yaml(root/ref,value)
            raw=(root/ref).read_bytes();sha='sha256:'+hashlib.sha256(raw).hexdigest();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,nodeId=node,byteCount=len(raw),sha256=sha));execution['rawOutputRefs'].append(ref);return ref,sha,len(raw)
        for node,codec in [(n,'av1') for n in env['worker_node_inventory']]+[(env['worker_node_inventory'][0],'h264')]:
            case_id='synthetic-soak-'+node['nodeId']+'-'+codec
            case=dict(caseId=case_id,runId=case_id+'-run',nodeId=node['nodeId'],physicalHostId=node['physicalHostId'],encoderBuild=node['encoderBuild'],compatibilityGroupId=node['compatibilityGroupId'],decoderBuild='synthetic-soak-decoder',inputSampleId=sample['id'],inputSha256=sample['checksum'],sourceStartFrame=0,sourceEndFrame=120,codec=codec,encoderParameters=dict(codec=codec,preset='synthetic-soak'),commandArgs=['synthetic-soak',node['nodeId'],codec]);cases.append(case)
            start='2026-09-03T00:00:00Z' if codec=='av1' else '2026-09-03T00:01:00Z';end='2026-09-03T00:01:00Z' if codec=='av1' else '2026-09-03T00:02:00Z';decoded='2026-09-03T00:01:00.001Z' if codec=='av1' else '2026-09-03T00:02:00.001Z'
            media,sha,size=retain(case_id+'.bin',('Synthetic '+codec+' soak output; never actual encoded media.').encode(),'produced_media',node['nodeId'])
            identity={k:case[k] for k in ('runId','caseId','nodeId','physicalHostId','encoderBuild','compatibilityGroupId','decoderBuild','inputSampleId','inputSha256','sourceStartFrame','sourceEndFrame','codec')}
            probe,_,_=retain(case_id+'-decode.yaml',dict(schemaVersion=1,kind='media_soak_decode',**identity,outputArtifactRef=media,outputSha256=sha,observedAt=decoded,decodable=True,decodedFrameCount=120,durationSeconds=4,decodeErrorCount=0),'measurement_output',node['nodeId'])
            progress=[dict(observedAt=at,completedIterations=iterations,completedFrames=iterations*120,residentBytes=1048576,temporaryBytes=0,cpuSeconds=seconds) for at,iterations,seconds in ((start,0,0),(end,2,30))]
            rows.append(dict(**case,startedAt=start,finishedAt=end,processExitCode=0,terminalStatus='completed',processTerminationReason='approved_window_completed',outputArtifactRef=media,outputSha256=sha,outputByteCount=size,decodeRef=probe,progress=progress,failureEvents=[]))
        policy=dict(minimumDurationMinutes=1,maximumProgressGapSeconds=60,maximumRecoverySeconds=5,maximumResidentBytes=2097152,maximumResidentGrowthBytes=1048576,maximumTemporaryBytes=1048576,maximumCpuSeconds=60,cases=cases)
        config_path=root/resource['configurationRef'];config=load_yaml(config_path);config['configuration']['mediaSoakPolicy']=policy;write_yaml(config_path,config)
        report=dict(schemaVersion=1,kind='media_soak_observation',configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=CHECK.compliance_subject_version(load_yaml(self.plan_path(root,'POC-002')),execution),inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']],cases=rows)
        ref,_,_=retain('media-soak.yaml',report,'measurement_output',env['worker_node_inventory'][0]['nodeId']);env['mediaSoakRef']=ref

    def prepare_qualified_h264_fallback_fixture(self,root,execution,prefix):
        """Synthetic H264 run/probe fixtures; never actual encoded or decoded media."""
        env=execution['environmentCaptured'];node=env['worker_node_inventory'][0];sample=execution['samples'][0]
        resource=next(r for r in execution['resources'] if r['id']=='RES-HETEROGENEOUS-WORKERS')
        policy=dict(runId='synthetic-h264-fallback-run',nodeId=node['nodeId'],physicalHostId=node['physicalHostId'],encoderBuild=node['encoderBuild'],compatibilityGroupId=node['compatibilityGroupId'],decoderBuild='synthetic-h264-decoder',inputSampleId=sample['id'],inputSha256=sample['checksum'],sourceStartFrame=0,sourceEndFrame=120,codec='h264',encoderParameters=dict(codec='h264',preset='synthetic-pinned-preset'),commandArgs=['synthetic-encode','h264',sample['immutableId']])
        path=root/resource['configurationRef'];config=load_yaml(path);config['configuration']['mediaFallbackPolicy']=policy;write_yaml(path,config)
        def retain(name,value,kind):
            ref=prefix+'/raw/'+name
            if isinstance(value,bytes):(root/ref).write_bytes(value)
            else:write_yaml(root/ref,value)
            raw=(root/ref).read_bytes();digest='sha256:'+hashlib.sha256(raw).hexdigest();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,byteCount=len(raw),sha256=digest,nodeId=node['nodeId']));execution['rawOutputRefs'].append(ref)
            return ref,digest,len(raw)
        media,sha,size=retain('h264-fallback.bin',b'Synthetic H264-only fallback fixture; never actual encoded media.\n','produced_media')
        identity={k:policy[k] for k in ('runId','nodeId','physicalHostId','encoderBuild','compatibilityGroupId','decoderBuild','inputSampleId','inputSha256','sourceStartFrame','sourceEndFrame','codec')}
        probe,_,_=retain('h264-fallback-decode.yaml',dict(schemaVersion=1,kind='h264_fallback_decode',**identity,outputArtifactRef=media,outputSha256=sha,observedAt='2026-09-03T00:00:02Z',decodable=True,decodedFrameCount=120,durationSeconds=4,decodeErrorCount=0),'measurement_output')
        report=dict(schemaVersion=1,kind='h264_fallback_encode',configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=CHECK.compliance_subject_version(load_yaml(self.plan_path(root,'POC-002')),execution),inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']],**policy,startedAt='2026-09-03T00:00:00Z',finishedAt='2026-09-03T00:00:01Z',exitCode=0,encodedFrameCount=120,outputArtifactRef=media,outputSha256=sha,outputByteCount=size,decodeRef=probe)
        ref,_,_=retain('h264-fallback-encode.yaml',report,'measurement_output');env['h264FallbackRef']=ref

    def prepare_qualified_metadata_resource_fixture(self,root,execution,prefix,scan_policy):
        """Synthetic quota/process counters, never actual adapter or scanner measurements."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-METADATA-SCALE')
        source=dict(adapterId='synthetic-metadata-adapter',adapterBuild=scan_policy['scannerBuild'],sourceId='synthetic-metadata-source',sourceVersion=scan_policy['manifestId'])
        quota_ref=prefix+'/raw/approved-source-quota.yaml'
        write_yaml(root/quota_ref,dict(schemaVersion=1,kind='documented_source_quota',sourceIdentity=source,requestLimit=1,periodSeconds=60,resetSemantics='Synthetic fixed window reset; never provider documentation.',backoffStrategy='Synthetic capped exponential backoff.',maximumBackoffSeconds=1,documentationRevision='synthetic-quota-revision'))
        quota_sha='sha256:'+hashlib.sha256((root/quota_ref).read_bytes()).hexdigest()
        policy=dict(scannerBuild=scan_policy['scannerBuild'],scanId=scan_policy['scanId'],manifestId=scan_policy['manifestId'],processId='synthetic-scan-process',collectorBuild='synthetic-os-peak-counter',sourceIdentity=source,quotaDocumentRef=quota_ref,quotaDocumentSha256=quota_sha)
        config_path=root/resource['configurationRef'];config=load_yaml(config_path);config['configuration']['metadataResourcePolicy']=policy;write_yaml(config_path,config)
        report=dict(schemaVersion=1,kind='metadata_resource_observation',configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=CHECK.compliance_subject_version(load_yaml(self.plan_path(root,'POC-005')),execution),inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']],method='os_process_peak_resident_counter',**policy,memorySamples=[dict(observedAt=at,processId=policy['processId'],scanId=policy['scanId'],scannerBuild=policy['scannerBuild'],peakResidentBytes=value) for at,value in (('2026-09-03T00:00:00Z',524288),('2026-09-03T00:00:20Z',1048576))])
        ref=prefix+'/raw/metadata-resources.yaml';write_yaml(root/ref,report);raw=(root/ref).read_bytes();env['metadataResourceRef']=ref;env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType='measurement_output',byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));execution['rawOutputRefs'].append(ref)


    def prepare_qualified_metadata_profiling_fixture(self,root,execution,prefix,scan_policy):
        """Synthetic complete name/page/Range/version observations; never actual provider execution."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-METADATA-SCALE');config_path=root/resource['configurationRef'];config=load_yaml(config_path);source=config['configuration']['metadataResourcePolicy']['sourceIdentity'];stem=prefix+'/raw/metadata-profile-'
        env['rawExecutionArtifacts']=[a for a in env['rawExecutionArtifacts'] if not a['ref'].startswith(stem)];execution['rawOutputRefs']=[r for r in execution['rawOutputRefs'] if not r.startswith(stem)]
        def retain(name,value,kind):
            ref=stem+name
            if isinstance(value,bytes):(root/ref).write_bytes(value)
            else:write_yaml(root/ref,value)
            raw=(root/ref).read_bytes();digest='sha256:'+hashlib.sha256(raw).hexdigest();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,byteCount=len(raw),sha256=digest));execution['rawOutputRefs'].append(ref);return dict(ref=ref,sha256=digest)
        def stream(name,records):
            descriptor=retain(name,b''.join((json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n').encode() for r in records),'command_output');descriptor['count']=len(records);return descriptor
        objects=[json.loads(line) for line in (root/scan_policy['baseline']['ref']).read_bytes().splitlines()];named=[]
        for row in objects:
            name='目录-'+row['objectId'] if row['kind']=='directory' else row['objectId']+'.txt';named.append(dict(**row,name=name,path='/'.join(['synthetic-parent']*(row['depth']-1)+[name]),modifiedAt='2026-09-01T00:00:00Z'))
        approved=stream('approved-names.jsonl',named);observed=stream('observed-names.jsonl',named);probe_size=next(row['fileSizeBytes'] for row in objects if row['objectId']=='synthetic-file-1');before=retain('baseline-object.bin',b'A'*probe_size,'produced_media');after=retain('updated-object.bin',b'B'*probe_size,'produced_media')
        policy=dict(manifestId=scan_policy['manifestId'],scannerBuild=scan_policy['scannerBuild'],sourceIdentity=source,endpointURL='https://synthetic-metadata.invalid/list',filenameInput=approved,extensionCategories=['txt','mp4'],minimumListingRuns=2,probeObjectId='synthetic-file-1',baselineVersion='version-1',updatedVersion='version-2',baselinePayload=before,updatedPayload=after,rangeDisposition='supported',validatorKind='etag');config['configuration']['metadataProfilingPolicy']=policy;write_yaml(config_path,config)
        distributions={k:{} for k in ('nameLength','characterSet','extension','pathDepth')}
        for row in named:
            values=dict(nameLength=str(len(row['name'])),characterSet='ascii' if row['name'].isascii() else 'non_ascii',pathDepth=str(row['depth']))
            if row['kind']=='file':values['extension']='txt'
            for k,v in values.items():distributions[k][v]=distributions[k].get(v,0)+1
        pages=[]
        for run in range(2):
            for index,row in enumerate(named):
                at=f'2026-09-03T00:00:0{run+1}.{index:03d}Z';pages.append(dict(runId='synthetic-provider-list-'+str(run),requestId=f'synthetic-provider-list-{run}-{index}',sourceIdentity=source,endpointURL=policy['endpointURL'],requestedAt=at,finishedAt=at,requestCursor=None if index==0 else 'synthetic-cursor-'+str(index),nextCursor=None if index+1==len(named) else 'synthetic-cursor-'+str(index+1),statusCode=200,providerTimestamp=at,objects=stream(f'page-{run}-{index}.jsonl',[row])))
        probes=[]
        for index,case in enumerate(('unchanged_first','unchanged_second','bounded','unsatisfiable','changed')):
            changed=case=='changed';descriptor=after if changed else before;content=(root/descriptor['ref']).read_bytes();version='version-2' if changed else 'version-1';body=content[:2] if case=='bounded' else b'' if case=='unsatisfiable' else content;response=retain('response-'+case+'.bin',body,'produced_media')
            probes.append(dict(case=case,requestId='synthetic-metadata-probe-'+case,objectId=policy['probeObjectId'],objectVersion=version,observedAt=f'2026-09-03T00:00:0{7 if changed else 3}.{index:03d}Z',requestRange='bytes=0-1' if case=='bounded' else f'bytes={len(content)}-' if case=='unsatisfiable' else '',statusCode=206 if case=='bounded' else 416 if case=='unsatisfiable' else 200,contentRange=f'bytes 0-{min(1,len(content)-1)}/{len(content)}' if case=='bounded' else f'bytes */{len(content)}' if case=='unsatisfiable' else '',etag='"synthetic-'+version+'"',versionValidator='',responseRef=response['ref'],responseSha256=response['sha256'],responseByteCount=len(body)))
        report=dict(schemaVersion=1,kind='metadata_profiling_observations',configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=scan_policy['scannerBuild'],inputSamples=[{k:v[k] for k in ('id','immutableId','checksum')} for v in execution['samples']],manifestId=scan_policy['manifestId'],scannerBuild=scan_policy['scannerBuild'],sourceIdentity=source,filenameObjects=observed,filenameDistributions=distributions,providerPages=stream('provider-pages.jsonl',pages),rangeDisposition=policy['rangeDisposition'],validatorKind='etag',validatorStableOnUnchanged=True,validatorChangedOnUpdate=True,probes=probes);env['metadataProfilingRef']=retain('report.yaml',report,'measurement_output')['ref']
        # Seal only artifacts retained by this synthetic profiling fixture.
        subprocess.run(['git','-C',str(root),'add','--',*[a['ref'] for a in env['rawExecutionArtifacts'] if a['ref'].startswith(stem)]],check=True,capture_output=True)


    def prepare_qualified_public_network_fixture(self,root,execution,prefix):
        """Explicitly synthetic external DNS/TLS/routing cases, never public network measurements."""
        env=execution['environmentCaptured'];access=load_yaml(root/env['accessOutcomeRef']);path=root/access['configurationRef'];config=load_yaml(path);access_policy=config['configuration']['accessPolicy'];entry='https://synthetic-public.invalid:8443'
        for key in ('range','stream'):access_policy['paths'][key]=entry+'/protected/'+key
        for case in access['cases']:
            witness_path=root/case['witnessRef'];witness=load_yaml(witness_path);witness['requestURL']=access_policy['paths']['stream' if case['case']=='authorized_stream' else 'range'];write_yaml(witness_path,witness)
        policy=dict(endpointURL=access_policy['paths']['range'],testPointIds=['synthetic-external-point'],newAddress='2001:db8::2',oldAddress='2001:db8::1',ddnsName='synthetic-public.invalid',ddnsUpdatedAt='2026-09-03T00:00:00.100Z',maximumPropagationSeconds=1,resolverBuild='synthetic-resolver-build',trustStoreBuild='synthetic-trust-store-build',certificateSha256='sha256:'+'a'*64,trustAnchorSha256='sha256:'+'b'*64,approvedProtocols=['TLSv1.3'],approvedCiphers=['TLS_AES_128_GCM_SHA256'],routeId='synthetic-approved-proxy-route',proxyBuild='synthetic-proxy-build',originHost='synthetic-source.invalid',originPort=443,originAddress='2001:db8::3',unintendedURL='https://synthetic-public.invalid:8444/protected/range',bypassURL=access_policy['paths']['source'])
        config['configuration']['publicNetworkPolicy']=policy;write_yaml(path,config)
        def retain(name,data,kind):
            ref=prefix+'/raw/'+name;path=root/ref
            if isinstance(data,bytes):path.write_bytes(data)
            else:write_yaml(path,data)
            raw=path.read_bytes();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));execution['rawOutputRefs'].append(ref);return ref
        witness_ref=next(r['witnessRef'] for r in access['cases'] if r['case']=='authorized_range');witness=load_yaml(root/witness_ref)
        baseline_ref=witness_ref;body=(root/witness['responseBodyRef']).read_bytes();witness['responseBodyRef']=retain('public-current-response.bin',body,'produced_media');witness.update(kind='public_access_request_outcome',requestId='synthetic-current-public-request',testPointId=policy['testPointIds'][0],baselineAccessWitnessRef=baseline_ref)
        witness_ref=retain('public-current-request.yaml',witness,'measurement_output')
        dns=lambda address,at,serial:dict(name=policy['ddnsName'],recordType='AAAA',addresses=[address],observedAt=at,resolverBuild=policy['resolverBuild'],recordSerial=serial)
        tls=dict(startedAt='2026-09-03T00:00:00.650Z',finishedAt='2026-09-03T00:00:00.700Z',sni=policy['ddnsName'],protocol='TLSv1.3',cipher=policy['approvedCiphers'][0],trustStoreBuild=policy['trustStoreBuild'],certificateSha256=policy['certificateSha256'],chainFingerprints=[policy['certificateSha256'],policy['trustAnchorSha256']],chainValidated=True,hostnameValidated=True)
        control=dict(testPointId=policy['testPointIds'][0],testPointScope='external',requestId='synthetic-current-public-request',requestURL=policy['endpointURL'],accessWitnessRef=witness_ref,connectedAt='2026-09-03T00:00:00.600Z',requestStartedAt='2026-09-03T00:00:00.800Z',requestFinishedAt=witness['observedAt'],addressFamily='IPv6',connectedAddress=policy['newAddress'],remotePort=8443,tls=tls,routeId=policy['routeId'],proxyBuild=policy['proxyBuild'],originHost=policy['originHost'],originPort=policy['originPort'],**{k:witness[k] for k in ('responseBodyRef','responseSha256','responseByteCount')})
        denials=[]
        for case in ('unintended_listener','direct_bypass','stale_address'):
            body=retain('public-'+case+'-body.bin',b'','produced_media');denials.append(dict(case=case,testPointId=policy['testPointIds'][0],testPointScope='external',requestId='synthetic-denied-public-'+case,requestURL=policy['unintendedURL'] if case=='unintended_listener' else policy['bypassURL'] if case=='direct_bypass' else policy['endpointURL'],connectedAddress=policy['originAddress'] if case=='direct_bypass' else policy['oldAddress'] if case=='stale_address' else policy['newAddress'],remotePort=8444 if case=='unintended_listener' else 443 if case=='direct_bypass' else 8443,observedAt='2026-09-03T00:00:02Z',statusCode=0,outcome='connection_refused',routeId=None,originRequestCount=0,responseBodyRef=body,responseSha256='sha256:'+hashlib.sha256(b'').hexdigest(),responseByteCount=0))
        report=dict(schemaVersion=1,kind='public_network_observations',configurationRef=access['configurationRef'],accessOutcomeRef=env['accessOutcomeRef'],**{k:access[k] for k in ('acceptanceProfile','subjectVersion','inputSamples')},dnsBefore=dns(policy['oldAddress'],'2026-09-03T00:00:00Z','synthetic-old-record'),dnsAfter=dns(policy['newAddress'],'2026-09-03T00:00:00.500Z','synthetic-new-record'),controls=[control],denials=denials)
        env['publicNetworkRef']=retain('public-network.yaml',report,'measurement_output');self.refresh_qualified_observation_fixture(root,execution)


    def prepare_qualified_range_fixture(self,root,execution,prefix):
        """Synthetic retained Range/cache cases; never actual ATS or network execution."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-ATS-SANDBOX');sample=execution['samples'][0];source=root/env['inputSampleArtifacts'][0]['inputArtifactRef'];data=source.read_bytes();changed=data.replace(b'Synthetic',b'Updated!!',1)
        def retain(name,value,kind='produced_media'):
            ref=prefix+'/raw/'+name;path=root/ref
            if isinstance(value,bytes):path.write_bytes(value)
            else:write_yaml(path,value)
            raw=path.read_bytes();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));execution['rawOutputRefs'].append(ref);return ref
        changed_ref=retain('range-updated-source.bin',changed);changed_sha='sha256:'+hashlib.sha256(changed).hexdigest()
        policy=dict(assetId='synthetic-range-asset',aclVersion='synthetic-current-acl',baseVersion='synthetic-v1',updatedVersion='synthetic-v2',updatedInputRef=changed_ref,updatedInputSha256=changed_sha,entryURL='https://synthetic-range.invalid/asset',authorizedUsers=['synthetic-user-a','synthetic-user-b'],deniedUser='synthetic-user-denied',sliceBytes=16,maximumBufferedBytes=4096,maximumRetries=2,slowOriginDelayMs=1,slowOriginBandwidthBytesPerSecond=1024,concurrentUsers=2,latencySampleCount=2,percentileMethod='mean')
        policy.update(baseETag='"'+sample['checksum'].removeprefix('sha256:')+'"',updatedETag='"'+changed_sha.removeprefix('sha256:')+'"')
        config_path=root/resource['configurationRef'];config=load_yaml(config_path);config['configuration']['rangeMatrixPolicy']=policy;write_yaml(config_path,config)
        common=dict(configurationRef=resource['configurationRef'],inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']],inputSampleId=sample['id'],subjectVersion=CHECK.compliance_subject_version(load_yaml(self.plan_path(root,'POC-003')),execution),acceptanceProfile=env['acceptanceProfile'],assetId=policy['assetId'],aclVersion=policy['aclVersion'])
        update_ref=retain('range-source-update.yaml',dict(schemaVersion=1,kind='range_source_update',**common,observedAt='2026-09-03T00:00:20Z',baseVersion=policy['baseVersion'],updatedVersion=policy['updatedVersion'],baseSha256=sample['checksum'],updatedSha256=changed_sha),'measurement_output')
        cases=[]
        for name in sorted(CHECK.RANGE_MATRIX_CASES):
            version=policy['updatedVersion'] if name=='updated' else policy['baseVersion'];content=changed if name=='updated' else data;size=len(content);sha='sha256:'+hashlib.sha256(content).hexdigest();etag='"'+sha.removeprefix('sha256:')+'"';requests=[]
            for number in range(2 if name.startswith('latency_') else 1):
                full=name in ('stream','if_stale');start,end=(0,size-1) if full else (8,15) if name=='range_middle' else (size-8,size-1) if name in ('range_end','suffix') else (0,7)
                header='' if name=='stream' else 'bytes=8-15' if name=='range_middle' else f'bytes={size-8}-{size-1}' if name=='range_end' else 'bytes=-8' if name=='suffix' else f'bytes={size}-{size+7}' if name=='unsatisfiable' else 'bytes=0-7'
                body=b'' if name in ('unsatisfiable','denied_user','partial_read') else content[start:start+3] if name=='interrupted' else content[start:end+1];body_ref=retain('range-'+name+'-'+str(number)+'-body.bin',body)
                second=21 if name=='updated' else 3 if name=='interrupted' else 4 if name=='partial_read' else 5 if name=='recovered' else 1 if name=='latency_multi' else 1+number
                user=policy['deniedUser'] if name=='denied_user' else policy['authorizedUsers'][1] if name=='other_user' or name=='latency_multi' and number else policy['authorizedUsers'][0]
                status_code=403 if name=='denied_user' else 503 if name=='partial_read' else 416 if name=='unsatisfiable' else 200 if full else 206
                cache_status={'miss':'MISS','fill':'FILL','hit':'HIT','updated':'INVALIDATED','interrupted':'PARTIAL','partial_read':'PARTIAL','recovered':'FILL','latency_hot':'HIT','latency_cold':'MISS','latency_slow':'MISS','latency_multi':'HIT'}.get(name,'BYPASS')
                requests.append(dict(startedAt=f'2026-09-03T00:00:{second:02d}Z',firstByteAt=f'2026-09-03T00:00:{second:02d}.001Z',finishedAt=f'2026-09-03T00:00:{second:02d}.002Z',sourceVersion=version,sourceSha256=sha,requestURL=policy['entryURL'],aclVersion=policy['aclVersion'],userId=user,cacheKey='synthetic-cache-'+user,requestRange=header,ifRange=etag if name=='if_match' else '"stale-version"' if name=='if_stale' else '',statusCode=status_code,etag=etag if name not in ('denied_user','partial_read') else '',contentRange=f'bytes */{size}' if name=='unsatisfiable' else '' if full or name in ('denied_user','partial_read') else f'bytes {start}-{end}/{size}',responseBodyRef=body_ref,responseSha256='sha256:'+hashlib.sha256(body).hexdigest(),responseByteCount=len(body),cacheComplete=name not in ('interrupted','partial_read','denied_user'),cacheVisible=name not in ('interrupted','partial_read','denied_user'),transferCompleted=name not in ('interrupted','partial_read'),maximumBufferedBytes=len(body),retryCount=1 if name=='recovered' else 0,cacheStatus=cache_status,cachePurged=name=='latency_cold',originDelayMs=policy['slowOriginDelayMs'] if name=='latency_slow' else 0,originBandwidthBytesPerSecond=policy['slowOriginBandwidthBytesPerSecond'],concurrentUsers=2 if name=='latency_multi' else 1))
            ref=retain('range-'+name+'.yaml',dict(schemaVersion=1,kind='range_request_observation',**common,case=name,requests=requests),'measurement_output');cases.append(dict(case=name,witnessRef=ref))
        slices=[]
        for start in range(0,len(data),policy['sliceBytes']):
            body=data[start:start+policy['sliceBytes']];ref=retain('range-slice-'+str(start)+'.bin',body);slices.append(dict(start=start,end=start+len(body)-1,artifactRef=ref,sha256='sha256:'+hashlib.sha256(body).hexdigest()))
        stages=[]
        for stage,second,content,version in (('before',0,b'',policy['baseVersion']),('filled',2,data,policy['baseVersion']),('interrupted',3,data[:3],policy['baseVersion']),('recovered',5,data,policy['baseVersion']),('updated',21,changed,policy['updatedVersion']),('cleanup',22,b'',policy['updatedVersion'])):
            objects=[]
            if content:
                ref=retain('range-cache-'+stage+'.bin',content);objects=[dict(sourceVersion=version,artifactRef=ref,sha256='sha256:'+hashlib.sha256(content).hexdigest(),byteCount=len(content),complete=stage!='interrupted',visible=stage!='interrupted')]
            stages.append(dict(stage=stage,observedAt=f'2026-09-03T00:00:{second:02d}Z',allocatedBytes=len(content),objects=objects))
        lifecycle_ref=retain('range-cache-lifecycle.yaml',dict(schemaVersion=1,kind='range_cache_lifecycle',**common,stages=stages),'measurement_output')
        env['rangeMatrixRef']=retain('range-matrix.yaml',dict(schemaVersion=1,kind='range_matrix_report',**common,sourceUpdateRef=update_ref,cacheLifecycleRef=lifecycle_ref,cases=cases,slices=slices),'measurement_output')


    def prepare_qualified_passthrough_transitions_fixture(self,root,execution,prefix):
        """Synthetic reboot/reset witnesses; never actual hardware validation."""
        env=execution['environmentCaptured'];capture=env['productionPassthroughIdentity'];identity=capture['identity'];device=identity['gpuDeviceId'];config=capture['configurationRef'];rows=[]
        def retain(name,data,kind):
            ref=prefix+'/raw/'+name;path=root/ref
            if isinstance(data,bytes):path.write_bytes(data)
            else:write_yaml(path,data)
            raw=path.read_bytes();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,nodeId=identity['nodeId'],byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));execution['rawOutputRefs'].append(ref);return ref
        def state(index,host,guest,generation):
            start=f'2026-09-03T00:04:{index*10:02d}Z';finish=f'2026-09-03T00:04:{index*10+1:02d}Z';at=f'2026-09-03T00:04:{index*10+2:02d}Z';payload=b'Synthetic passthrough probe output, never actual encoded media.'+str(index).encode();output=retain('passthrough-probe-'+str(index)+'.bin',payload,'produced_media')
            probe=dict(schemaVersion=1,kind='passthrough_runtime_probe',configurationRef=config,identity=identity,hostBootId=host,guestBootId=guest,deviceGenerationId=generation,startedAt=start,finishedAt=finish,inputSha256=execution['samples'][0]['checksum'],outputRef=output,outputSha256='sha256:'+hashlib.sha256(payload).hexdigest(),codec='av1',decodedFrameCount=1,decodeErrorCount=0,runtimeReady=True);ref=retain('passthrough-probe-'+str(index)+'.yaml',probe,'measurement_output')
            return dict(observedAt=at,hostBootId=host,guestBootId=guest,deviceGenerationId=generation,enumeratedDeviceIds=[device],assignedDeviceIds=[device],runtimeReady=True,probeRef=ref)
        states=[state(0,'synthetic-captured-host-boot','synthetic-guest-boot-0','synthetic-device-generation-0'),state(1,'synthetic-captured-host-boot','synthetic-guest-boot-1','synthetic-device-generation-1'),state(2,'synthetic-host-boot-1','synthetic-guest-boot-2','synthetic-device-generation-2'),state(3,'synthetic-host-boot-1','synthetic-guest-boot-2','synthetic-device-generation-3')]
        for i,case in enumerate(('guest_reboot','host_reboot','device_reset')):
            rows.append(dict(case=case,startedAt=f'2026-09-03T00:04:{i*10+3:02d}Z',finishedAt=f'2026-09-03T00:04:{i*10+4:02d}Z',manualRebuildCount=0,before=states[i],after=states[i+1]))
        env['passthroughTransitionRef']=retain('passthrough-transitions.yaml',dict(schemaVersion=1,kind='production_passthrough_transitions',configurationRef=config,identity=identity,cases=rows),'measurement_output')



    def prepare_qualified_worker_capabilities_fixture(self,root,execution,prefix):
        """Synthetic node codec records; never actual device or VM capabilities."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-HETEROGENEOUS-WORKERS');sample=execution['samples'][0];claims=[];rows=[]
        def retain(name,value,kind,node):
            ref=prefix+'/raw/'+name
            if isinstance(value,bytes):(root/ref).write_bytes(value)
            else:write_yaml(root/ref,value)
            raw=(root/ref).read_bytes();sha='sha256:'+hashlib.sha256(raw).hexdigest();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,nodeId=node,byteCount=len(raw),sha256=sha));execution['rawOutputRefs'].append(ref);return ref,sha,len(raw)
        for node in env['worker_node_inventory']:
            node.update(osBuild='synthetic-'+node['platform']+'-os-build',architecture='synthetic-x86_64' if node.get('isEmulator') or node['platform']!='android' else 'synthetic-arm64',nodeConfiguration=dict(schemaVersion=1,mode='synthetic-only'))
            node.setdefault('compatibilityGroupId','synthetic-capability-group')
            for codec in ('av1','h264','hevc'):
                case_id='synthetic-capability-'+node['nodeId']+'-'+codec
                claim=dict(caseId=case_id,runId=case_id+'-run',**{k:node[k] for k in ('nodeId','physicalHostId','encoderBuild','compatibilityGroupId','platform','osBuild','architecture','nodeConfiguration')},decoderBuild='synthetic-capability-decoder',inputSampleId=sample['id'],inputSha256=sample['checksum'],sourceStartFrame=0,sourceEndFrame=120,codec=codec,encoderParameters=dict(codec=codec,preset='synthetic-pinned-config'),commandArgs=['synthetic-capability-probe',node['nodeId'],codec],status='unsupported' if codec=='hevc' else 'supported');claims.append(claim)
                if codec=='hevc':
                    raw,sha,_=retain(case_id+'-diagnostic.txt',b'Synthetic absent codec diagnostic; never actual hardware proof.','command_output',node['nodeId'])
                    diagnostic,_,_=retain(case_id+'-diagnostic.yaml',dict(schemaVersion=1,kind='worker_capability_diagnostic',**claim,observedAt='2026-09-03T00:00:02Z',probeToolBuild='synthetic-capability-tool',reason='Synthetic unsupported extra codec.',rawProbeRef=raw,rawProbeSha256=sha),'measurement_output',node['nodeId']);rows.append(dict(**claim,diagnosticRef=diagnostic));continue
                media,sha,size=retain(case_id+'.bin',('Synthetic '+node['nodeId']+' '+codec+'; never encoded media.').encode(),'produced_media',node['nodeId'])
                identity={k:claim[k] for k in ('runId','caseId','nodeId','physicalHostId','encoderBuild','compatibilityGroupId','decoderBuild','inputSampleId','inputSha256','sourceStartFrame','sourceEndFrame','codec')}
                probe,_,_=retain(case_id+'-decode.yaml',dict(schemaVersion=1,kind='worker_capability_decode',**identity,outputArtifactRef=media,outputSha256=sha,observedAt='2026-09-03T00:00:02Z',decodable=True,decodedFrameCount=120,durationSeconds=4,decodeErrorCount=0),'measurement_output',node['nodeId'])
                rows.append(dict(**claim,startedAt='2026-09-03T00:00:00Z',finishedAt='2026-09-03T00:00:01Z',exitCode=0,encodedFrameCount=120,outputArtifactRef=media,outputSha256=sha,outputByteCount=size,decodeRef=probe))
        hosts=sorted({n['physicalHostId'] for n in env['worker_node_inventory']});env['physical_host_scope']=dict(physicalHostIds=hosts,physicalMultiHostValidated=len(hosts)>1)
        policy=dict(sourceFrameCount=120,framesPerSecond=30,claims=claims);env['encoder_capability_matrix']=copy.deepcopy(claims);config_path=root/resource['configurationRef'];config=load_yaml(config_path);config['configuration']['workerCapabilityPolicy']=policy;write_yaml(config_path,config)
        report=dict(schemaVersion=1,kind='worker_capability_observation',configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=CHECK.compliance_subject_version(load_yaml(self.plan_path(root,'POC-001')),execution),inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']],claims=rows)
        ref,_,_=retain('worker-capabilities.yaml',report,'measurement_output',env['worker_node_inventory'][0]['nodeId']);env['workerCapabilitiesRef']=ref


    def prepare_qualified_worker_safety_fixture(self,root,execution,prefix):
        """Synthetic per-node safety observations; never actual worker execution evidence."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-HETEROGENEOUS-WORKERS');subject=CHECK.compliance_subject_version(load_yaml(self.plan_path(root,'POC-001')),execution)
        nodes=[{k:n[k] for k in ('nodeId','physicalHostId','encoderBuild')} for n in env['worker_node_inventory']]
        limits=dict(cpuSeconds=5,memoryBytes=100,elapsedSeconds=5,temporaryBytes=100,outputBytes=100)
        policy=dict(subjectVersion=subject,nodes=nodes,limits=limits,maximumRecoverySeconds=10,taskId='synthetic-worker-safety-task',allowedTarget='https://synthetic-task.invalid/approved-input',privateTarget='http://127.0.0.1/private',unsupportedTarget='file:///synthetic-input',administrativeTarget='https://synthetic-storage.invalid/api/admin',grantId='synthetic-task-grant',expiredGrantId='synthetic-expired-task-grant',grantValidFrom='2026-09-03T00:00:00Z',grantValidUntil='2026-09-03T01:00:00Z',expiredAt='2026-09-02T00:00:00Z')
        path=root/resource['configurationRef'];config=load_yaml(path);config['configuration']['workerSafetyPolicy']=policy;write_yaml(path,config)
        rows=[]
        for node in nodes:
            identity=node['nodeId'];cases=[]
            for kind,ceiling in limits.items():
                observed={k:1 for k in limits};observed[kind]=ceiling+1
                cases.append(dict(case=kind,requestId=identity+'-limit-'+kind,startedAt='2026-09-03T00:01:00Z',finishedAt='2026-09-03T00:01:06Z' if kind=='elapsedSeconds' else '2026-09-03T00:01:01Z',observed=observed,terminationReason=kind,processExited=True,remainingTemporaryBytes=0,remainingOutputBytes=0,publishedArtifactIds=[]))
            restart=dict(taskId=policy['taskId'],oldLeaseId=identity+'-old-lease',newLeaseId=identity+'-new-lease',oldRegistrationId=identity+'-old-registration',newRegistrationId=identity+'-new-registration',oldLeaseIssuedAt='2026-09-03T00:02:00Z',disconnectedAt='2026-09-03T00:02:01Z',oldLeaseExpiresAt='2026-09-03T00:02:02Z',expiredLeaseObservedAt='2026-09-03T00:02:03Z',reRegisteredAt='2026-09-03T00:02:04Z',newLeaseIssuedAt='2026-09-03T00:02:04Z',recoveredAt='2026-09-03T00:02:05Z',newLeaseExpiresAt='2026-09-03T00:02:10Z',completedTaskId=policy['taskId'],completionLeaseId=identity+'-new-lease',completionRegistrationId=identity+'-new-registration',taskCompletionCount=1,staleLeasePublicationCount=0)
            network=[]
            for kind,key in dict(authorized='allowedTarget',private_target='privateTarget',unsupported_target='unsupportedTarget',administrative_target='administrativeTarget',expired_grant='allowedTarget').items():
                data=b'Synthetic task-scoped outbound control; never actual network traffic.' if kind=='authorized' else b'';ref=prefix+'/raw/worker-'+identity+'-'+kind+'.bin';(root/ref).write_bytes(data);digest='sha256:'+hashlib.sha256(data).hexdigest()
                env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType='produced_media',nodeId=identity,byteCount=len(data),sha256=digest));execution['rawOutputRefs'].append(ref)
                network.append(dict(case=kind,requestId=identity+'-network-'+kind,taskId=policy['taskId'],grantId=policy['expiredGrantId'] if kind=='expired_grant' else policy['grantId'],requestURL=policy[key],observedAt='2026-09-03T00:03:00Z',decision='allowed' if kind=='authorized' else 'denied',outboundRef=ref,outboundSha256=digest,outboundByteCount=len(data)))
            rows.append(dict(identity=node,limitCases=cases,restart=restart,networkCases=network))
        report=dict(schemaVersion=1,kind='worker_safety_outcomes',configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=subject,inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']],nodes=rows)
        ref=prefix+'/raw/worker-safety.yaml';path=root/ref;write_yaml(path,report);raw=path.read_bytes();env['workerSafetyRef']=ref;env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType='measurement_output',byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));execution['rawOutputRefs'].append(ref)


    def prepare_qualified_source_fault_fixture(self,root,execution,prefix):
        """Synthetic request/state observations; never actual OpenList execution."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-OPENLIST-LOCAL');plan=load_yaml(self.plan_path(root,'POC-006'))
        policy=dict(scope='GENERIC_OPENLIST_SANDBOX',sandboxId='fixture-local-source-sandbox',sourceId='fixture-source-id',objectId='fixture-stable-object-id',objectVersion='fixture-source-object-v1',assetId='fixture-stable-asset-id',assetVersion='fixture-asset-version-v1',subjectVersion=CHECK.compliance_subject_version(plan,execution),idempotencyKey='fixture-stable-source-sync-key',maxAttempts=3,maxBackoffSeconds=2)
        config_path=root/resource['configurationRef'];config=load_yaml(config_path);config['configuration']['localSourceFaultPolicy']=policy;write_yaml(config_path,config)
        full=dict(assets=[dict(assetId=policy['assetId'],versionId=policy['assetVersion'])],sourceObjects=[dict(sourceId=policy['sourceId'],objectId=policy['objectId'],versionId=policy['objectVersion'],availability='available')],links=[dict(sourceId=policy['sourceId'],objectId=policy['objectId'],assetId=policy['assetId'])])
        rows=[];configured={case['fault']:case['caseId'] for case in env['injected_failure_matrix']['cases']}
        for index,case in enumerate(('http_429','http_5xx','network_disconnect','auth_expired','interrupted_sync','duplicate_replay','source_delete')):
            attempts=[];count=1 if case in ('auth_expired','source_delete') else 2
            for number in range(1,count+1):
                classification=case if number==1 and case!='duplicate_replay' else 'success';base=1+index*10+(number-1)*2
                code=429 if classification=='http_429' else 503 if classification=='http_5xx' else 401 if classification=='auth_expired' else 204 if classification=='source_delete' else None if classification in ('network_disconnect','interrupted_sync') else 200
                checkpoint='fixture-retained-partial-checkpoint' if case=='interrupted_sync' else None
                attempts.append(dict(attemptNo=number,requestId=f'fixture-{case}-request-{number}',idempotencyKey=policy['idempotencyKey'],requestedAt=f'2026-09-03T00:{base//60:02d}:{base%60:02d}Z',finishedAt=f'2026-09-03T00:{(base+1)//60:02d}:{(base+1)%60:02d}Z',transport='network_disconnect' if classification=='network_disconnect' else 'interrupted' if classification=='interrupted_sync' else 'http_response',httpStatus=code,classification=classification,authorization='expired' if case=='auth_expired' else 'valid',retryAfterSeconds=1 if classification=='http_429' else 0,backoffAfterSeconds=1 if number<count else 0,checkpointBefore=checkpoint if number>1 else None,checkpointAfter=checkpoint,completedObjectIds=[policy['objectId']] if classification=='success' else [],returnedAssetIds=[policy['assetId']] if classification=='success' else [],createdAssetIds=[]))
            after=copy.deepcopy(full)
            if case=='source_delete':after['sourceObjects'][0]['availability']='source_unavailable'
            rows.append(dict(case=case,caseId=configured.get(case,'fixture-'+case),recoveryMode='none' if count==1 else 'resume',outcome='explicit_failure' if case=='auth_expired' else 'source_unavailable' if case=='source_delete' else 'recovered',before=copy.deepcopy(full),after=after,attempts=attempts))
        report=dict(schemaVersion=1,kind='local_source_fault_outcomes',configurationRef=resource['configurationRef'],subjectVersion=policy['subjectVersion'],inputSamples=[{k:sample[k] for k in ('id','immutableId','checksum')} for sample in execution['samples']],acceptanceProfile=env['acceptanceProfile'],scope=policy['scope'],sandboxId=policy['sandboxId'],cases=rows)
        ref=prefix+'/raw/source-fault-outcomes.yaml';path=root/ref;write_yaml(path,report);raw=path.read_bytes();env['sourceFaultOutcomeRef']=ref;env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType='scope_observation',byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));execution['rawOutputRefs'].append(ref)
        for case in env['injected_failure_matrix']['cases']:case['rawOutputRef']=ref
        self.prepare_qualified_source_listing_fixture(root,execution,prefix)
        self.prepare_qualified_local_source_authentication_fixture(root,execution,prefix)


    def prepare_qualified_local_source_authentication_fixture(self,root,execution,prefix):
        """Synthetic authentication contract, never actual OpenList credentials or requests."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-OPENLIST-LOCAL');config_path=root/resource['configurationRef'];config=load_yaml(config_path);fault=config['configuration']['localSourceFaultPolicy'];sample=execution['samples'][0]
        policy={k:fault[k] for k in ('sourceId','sandboxId','subjectVersion','objectId','objectVersion')}
        policy.update(authMethod='basic',principalId='synthetic-local-source-reader',authorizedAuthRef='secretref_synthetic_source_reader',invalidAuthRef='secretref_synthetic_source_invalid',endpointURL='http://127.0.0.1:15525/d/synthetic-source-object',sampleId=sample['id'],immutableId=sample['immutableId'],payloadSha256=sample['checksum'])
        config['configuration']['localSourceAuthenticationPolicy']=policy;write_yaml(config_path,config)
        source=next(r for r in env['inputSampleArtifacts'] if r['sampleId']==sample['id']);payload=(root/source['inputArtifactRef']).read_bytes();rows=[]
        for index,case in enumerate(('authenticated','anonymous_denied','invalid_auth_denied')):
            success=case=='authenticated';anonymous=case=='anonymous_denied';body=payload if success else b'';ref=prefix+'/raw/source-auth-'+case+'.bin';(root/ref).write_bytes(body);digest='sha256:'+hashlib.sha256(body).hexdigest()
            env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType='produced_media',byteCount=len(body),sha256=digest));execution['rawOutputRefs'].append(ref)
            rows.append(dict(case=case,requestId='synthetic-auth-request-'+str(index),httpMethod='GET',endpointURL=policy['endpointURL'],authMethod='none' if anonymous else policy['authMethod'],authRef=None if anonymous else policy['authorizedAuthRef'] if success else policy['invalidAuthRef'],requestPrincipalId=None if anonymous else policy['principalId'],authenticatedPrincipalId=policy['principalId'] if success else None,requestedAt=f'2026-09-03T00:04:0{index}Z',finishedAt=f'2026-09-03T00:04:0{index}.100Z',statusCode=200 if success else 401,responseBodyRef=ref,responseByteCount=len(body),responseSha256=digest,returnedObjectId=policy['objectId'] if success else None,returnedObjectVersion=policy['objectVersion'] if success else None))
        report=dict(schemaVersion=1,kind='local_source_authentication_observation',configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=policy['subjectVersion'],inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']],scope='GENERIC_OPENLIST_SANDBOX',**{k:policy[k] for k in ('sourceId','sandboxId','endpointURL','objectId','objectVersion','authMethod','principalId')},requests=rows)
        ref=prefix+'/raw/source-authentication.yaml';write_yaml(root/ref,report);raw=(root/ref).read_bytes();env['sourceAuthenticationRef']=ref;env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType='measurement_output',byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));execution['rawOutputRefs'].append(ref)


    def prepare_qualified_source_listing_fixture(self,root,execution,prefix):
        """Synthetic listing/assessment records; never actual OpenList execution."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-OPENLIST-LOCAL');config_path=root/resource['configurationRef'];config=load_yaml(config_path);fault=config['configuration']['localSourceFaultPolicy']
        def retain(name,value):
            ref=prefix+'/raw/'+name;write_yaml(root/ref,value);raw=(root/ref).read_bytes();digest='sha256:'+hashlib.sha256(raw).hexdigest();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType='measurement_output',byteCount=len(raw),sha256=digest));execution['rawOutputRefs'].append(ref);return ref,digest
        objects=[dict(objectId=fault['objectId'],versionId=fault['objectVersion'],name='Synthetic source file',kind='file'),dict(objectId='synthetic-listing-directory',versionId='synthetic-directory-version',name='目录',kind='directory')]
        criteria=[dict(criterionId=c,weight=1) for c in ('api','sdk','versioning','support')];policy=dict(sourceId=fault['sourceId'],sandboxId=fault['sandboxId'],subjectVersion=fault['subjectVersion'],endpointURL='http://127.0.0.1:15525/api/fs/list',objects=objects,minimumListingRuns=2,criteria=criteria,gradeValues=dict(available=1,limited=0.5,unavailable=0));config['configuration']['localSourceListingPolicy']=policy;write_yaml(config_path,config)
        runs=[]
        for run in range(2):
            pages=[]
            for index,obj in enumerate(objects):
                second=run*10+index+1;pages.append(dict(requestId=f'synthetic-list-{run}-{index}',requestedAt=f'2026-09-03T00:03:{second:02d}Z',finishedAt=f'2026-09-03T00:03:{second:02d}.500Z',requestCursor=None if index==0 else 'synthetic-next',nextCursor='synthetic-next' if index==0 else None,statusCode=200,objects=[obj]))
            runs.append(dict(runId='synthetic-listing-'+str(run),pages=pages))
        assessment=[]
        for criterion in criteria:
            c=criterion['criterionId'];basis=dict(schemaVersion=1,kind='source_maintainability_basis',criterionId=c,subjectVersion=fault['subjectVersion'],observedAt='2026-09-03T00:03:20Z',toolBuild='synthetic-assessment-build',reference='synthetic-'+c+'-documentation-reference',details='Synthetic assessed '+c+' evidence; never actual provider assessment.');ref,sha=retain('source-assessment-'+c+'.yaml',basis)
            assessment.append(dict(criterionId=c,status='available',basisRef=ref,basisSha256=sha,observedAt='2026-09-03T00:03:21Z',rationale='Synthetic reviewed '+c+' availability.'))
        report=dict(schemaVersion=1,kind='local_source_listing_observations',configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=fault['subjectVersion'],inputSamples=[{k:v[k] for k in ('id','immutableId','checksum')} for v in execution['samples']],sourceId=policy['sourceId'],sandboxId=policy['sandboxId'],endpointURL=policy['endpointURL'],runs=runs,assessment=assessment);env['sourceListingRef']=retain('source-listing.yaml',report)[0]
        next(m for m in execution['measurements'] if m['id']=='maintainability')['actual']=1


    def prepare_qualified_local_storage_fixture(self,root,execution,prefix):
        """Synthetic storage observations; never actual OpenList or backup execution."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-OPENLIST-LOCAL');subject=CHECK.compliance_subject_version(load_yaml(self.plan_path(root,'POC-004')),execution);common=dict(configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=subject,inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']])
        def retain(name,data,kind='produced_media'):
            ref=prefix+'/raw/'+name;path=root/ref
            if isinstance(data,bytes):path.write_bytes(data)
            else:write_yaml(path,data)
            raw=path.read_bytes();digest='sha256:'+hashlib.sha256(raw).hexdigest();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,byteCount=len(raw),sha256=digest));execution['rawOutputRefs'].append(ref);return ref,digest
        objects=[];baseline=dict(assets=[],sourceMappings=[],retention=[],replicas=[],caches=[]);payloads={}
        for index,sample in enumerate(execution['samples']):
            source=next(r for r in env['inputSampleArtifacts'] if r['sampleId']==sample['id']);payload=(root/source['inputArtifactRef']).read_bytes();payloads[sample['id']]=payload;asset='synthetic-storage-asset-'+str(index);version=sample['immutableId'];replica='synthetic-old-replica-'+str(index);cache_id='synthetic-cache-'+str(index);old_ref,old_sha=retain(replica+'.bin',payload);cache_ref,cache_sha=retain(cache_id+'.bin',payload)
            objects.append(dict(sampleId=sample['id'],assetId=asset,versionId=version,sourceId='synthetic-source',objectId='synthetic-object-'+str(index),oldReplicaId=replica,newReplicaId='synthetic-new-replica-'+str(index),objectURL='http://127.0.0.1:15525/d/synthetic-'+str(index)));baseline['assets'].append(dict(assetId=asset,versionId=version,metadata=dict(title='Synthetic retained object '+str(index),mediaType='synthetic/test')));baseline['sourceMappings'].append(dict(sourceId='synthetic-source',objectId='synthetic-object-'+str(index),assetId=asset,versionId=version));baseline['retention'].append(dict(assetId=asset,policyId='synthetic-retention-policy',state='retained'));baseline['replicas'].append(dict(replicaId=replica,assetId=asset,versionId=version,state='VERIFIED',payloadRef=old_ref,sha256=old_sha));baseline['caches'].append(dict(cacheId=cache_id,assetId=asset,versionId=version,state='COMPLETE',payloadRef=cache_ref,sha256=cache_sha))
        policy=dict(subjectVersion=subject,sandboxRoot=env['sandbox_root_boundary'],openlistBuild=env['openlist_version'],authorizedAuthRef='secretref_synthetic_storage_authorized',invalidAuthRef='secretref_synthetic_storage_invalid',maximumRetries=2,objects=objects,baselineState=baseline);config_path=root/resource['configurationRef'];config=load_yaml(config_path);config['configuration']['localStoragePolicy']=policy;write_yaml(config_path,config)
        def snapshot(name,value,at='2026-09-03T00:00:00Z'):return retain(name,dict(schemaVersion=1,kind='local_storage_state',observedAt=at,**common,**value),'measurement_output')[0]
        baseline_ref=snapshot('storage-baseline-state.yaml',baseline);rows=[];complete_bytes=0
        for index,obj in enumerate(objects):
            payload=payloads[obj['sampleId']];total=len(payload);requests=[];complete_bytes+=total
            for kind in ('full','bounded','suffix','unsatisfiable','missing_auth','invalid_auth','concurrent_a','concurrent_b'):
                authorized=kind not in ('missing_auth','invalid_auth');partial=kind in ('bounded','suffix');data=payload[:8] if kind=='bounded' else payload[-4:] if kind=='suffix' else payload if authorized and kind!='unsatisfiable' else b'';ref,sha=retain('storage-'+str(index)+'-'+kind+'.bin',data);start='2026-09-03T00:01:00Z' if not kind.startswith('concurrent_') else '2026-09-03T00:02:00Z';finish='2026-09-03T00:01:01Z' if not kind.startswith('concurrent_') else '2026-09-03T00:02:01Z';requests.append(dict(case=kind,requestId='storage-'+str(index)+'-'+kind,objectURL=obj['objectURL'],assetId=obj['assetId'],versionId=obj['versionId'],authRef=policy['authorizedAuthRef'] if authorized else policy['invalidAuthRef'] if kind=='invalid_auth' else None,requestRange='bytes=0-7' if kind=='bounded' else 'bytes=-4' if kind=='suffix' else f'bytes={total}-' if kind=='unsatisfiable' else None,statusCode=206 if partial else 416 if kind=='unsatisfiable' else 200 if authorized else 403,contentRange=f'bytes 0-7/{total}' if kind=='bounded' else f'bytes {total-4}-{total-1}/{total}' if kind=='suffix' else f'bytes */{total}' if kind=='unsatisfiable' else None,responseRef=ref,responseSha256=sha,originByteCount=len(data),startedAt=start,finishedAt=finish))
            copies=[]
            for case in ('incomplete','hash_mismatch'):
                bad=payload[:len(payload)//2] if case=='incomplete' else bytes([payload[0]^1])+payload[1:];ref,sha=retain('storage-'+str(index)+'-'+case+'.bin',bad);copies.append(dict(case=case,assetId=obj['assetId'],versionId=obj['versionId'],payloadRef=ref,sha256=sha,expectedSha256='sha256:'+hashlib.sha256(payload).hexdigest(),promotionDecision='rejected',afterStateRef=snapshot('storage-'+str(index)+'-'+case+'-state.yaml',baseline,'2026-09-03T00:03:01Z'),startedAt='2026-09-03T00:03:00Z',finishedAt='2026-09-03T00:03:01Z'))
            attempts=[]
            for attempt,data in ((1,payload[:min(8,total-1)]),(2,payload)):
                ref,sha=retain('storage-'+str(index)+'-recovery-'+str(attempt)+'.bin',data);attempts.append(dict(attemptNo=attempt,startedAt=f'2026-09-03T00:04:0{attempt*2}Z',finishedAt=f'2026-09-03T00:04:0{attempt*2+1}Z',transport='disconnected' if attempt==1 else 'success',responseRef=ref,responseSha256=sha,partialPromotedCount=0))
            disconnect=dict(attempts=attempts,serviceRestartedAt='2026-09-03T00:04:03Z',afterStateRef=snapshot('storage-'+str(index)+'-recovered-state.yaml',baseline,'2026-09-03T00:04:05Z'));backup_ref,backup_sha=retain('storage-'+str(index)+'-backup.bin',payload);restored_ref,restored_sha=retain('storage-'+str(index)+'-restored.bin',payload);backup_state=copy.deepcopy(baseline);restored_state=copy.deepcopy(baseline);next(r for r in backup_state['replicas'] if r['replicaId']==obj['oldReplicaId'])['payloadRef']=backup_ref;next(r for r in restored_state['replicas'] if r['replicaId']==obj['oldReplicaId'])['payloadRef']=restored_ref;backup=dict(backupDataRef=backup_ref,backupSha256=backup_sha,restoredDataRef=restored_ref,restoredSha256=restored_sha,backupStateRef=snapshot('storage-'+str(index)+'-backup-state.yaml',backup_state,'2026-09-03T00:05:00Z'),restoredStateRef=snapshot('storage-'+str(index)+'-restored-state.yaml',restored_state,'2026-09-03T00:05:01Z'),startedAt='2026-09-03T00:05:00Z',finishedAt='2026-09-03T00:05:01Z');evicted=copy.deepcopy(baseline);evicted['caches']=[r for r in evicted['caches'] if r['assetId']!=obj['assetId']]
            pending_ref,pending_sha=retain('storage-'+str(index)+'-migration-pending.bin',payload[:min(8,total-1)]);new_ref,new_sha=retain('storage-'+str(index)+'-migration-verified.bin',payload);copying=copy.deepcopy(baseline);copying['replicas'].append(dict(replicaId=obj['newReplicaId'],assetId=obj['assetId'],versionId=obj['versionId'],state='COPYING',payloadRef=pending_ref,sha256=pending_sha));verified=copy.deepcopy(baseline);verified['replicas'].append(dict(replicaId=obj['newReplicaId'],assetId=obj['assetId'],versionId=obj['versionId'],state='VERIFIED',payloadRef=new_ref,sha256=new_sha));migration=dict(newReplicaId=obj['newReplicaId'],copyingStateRef=snapshot('storage-'+str(index)+'-migration-copying-state.yaml',copying,'2026-09-03T00:06:00Z'),verifiedStateRef=snapshot('storage-'+str(index)+'-migration-verified-state.yaml',verified,'2026-09-03T00:06:01Z'),startedAt='2026-09-03T00:06:00Z',verifiedAt='2026-09-03T00:06:01Z');rows.append(dict(sampleId=obj['sampleId'],requests=requests,copyRejections=copies,disconnect=disconnect,backupRestore=backup,evictionAfterStateRef=snapshot('storage-'+str(index)+'-evicted-state.yaml',evicted,'2026-09-03T00:05:30Z'),evictedAt='2026-09-03T00:05:30Z',migration=migration))
        observations=[dict(phase=phase,observedAt=f'2026-09-03T00:07:0{index}Z',freeBytes=free,reservedBytes=reserved,admission=admission) for index,(phase,free,reserved,admission) in enumerate((('baseline',400,50,'admitted'),('fill',200,50,'paused'),('pause',180,50,'paused'),('evict',400,0,'paused'),('resume',400,0,'admitted')))];report=dict(schemaVersion=1,kind='local_storage_outcomes',**common,baselineStateRef=baseline_ref,objects=rows,capacityObservations=observations);env['localStorageRef'],_=retain('local-storage-outcomes.yaml',report,'measurement_output')
        values=dict(local_minimum_free_bytes=180,local_maximum_reserved_bytes=50,sequential_throughput=complete_bytes/len(objects)/1000000,io_latency=1000)
        for measurement in execution['measurements']:
            if measurement['id'] in values:measurement['actual']=values[measurement['id']]


    def prepare_qualified_media_negative_fixture(self,root,execution,prefix):
        """Synthetic failure observations; never actual worker, FFmpeg or HLS execution."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-HETEROGENEOUS-WORKERS');quality=load_yaml(root/env['mediaQualityTimingRef']);assembly=env['parallelMediaAssembly'];nodes=[{k:n[k] for k in ('nodeId','physicalHostId','encoderBuild')} for n in env['worker_node_inventory']]
        def retain(name,data,node=None,kind='produced_media'):
            ref=prefix+'/raw/'+name;path=root/ref
            if isinstance(data,bytes):path.write_bytes(data)
            else:write_yaml(path,data)
            raw=path.read_bytes();digest='sha256:'+hashlib.sha256(raw).hexdigest();record=dict(ref=ref,artifactType=kind,byteCount=len(raw),sha256=digest)
            if node is not None:record['nodeId']=node
            env['rawExecutionArtifacts'].append(record);execution['rawOutputRefs'].append(ref);return ref,digest
        outputs=[]
        for surface in ('manifest','init'):
            ref,sha=retain('synthetic-protected-'+surface+'.bin',b'Synthetic protected '+surface.encode()+b'; never actual HLS bytes.');outputs.append(dict(surface=surface,ref=ref,sha256=sha))
        outputs.extend(dict(surface=surface,ref=quality['firstSegment']['segmentRef'],sha256=quality['firstSegment']['segmentSha256']) for surface in ('segment','cache_hit'))
        policy=dict(subjectVersion=quality['subjectVersion'],jobId=quality['jobId'],retryDecoderBuild=assembly['decoderBuild'],cancelJobId='synthetic-independent-cancel-job',assetId='synthetic-media-asset',assetVersion=next(r['immutableId'] for r in execution['samples'] if r['id']==assembly['inputSampleId']),nodes=nodes,limits=dict(cpuSeconds=5,memoryBytes=100,elapsedSeconds=5,temporaryBytes=100,outputBytes=100),deniedTargets=[dict(case=case,target=target) for case,target in (('protocol','file:///synthetic-denied-input'),('path','/synthetic/../denied-input'),('proxy','http://127.0.0.1/synthetic-private'))],authorizedUserId='synthetic-owner',deniedUserId='synthetic-other-user',currentGrantId='synthetic-current-grant',expiredGrantId='synthetic-expired-grant',revokedGrantId='synthetic-revoked-grant',aclVersion='synthetic-acl-v1',grantValidFrom='2026-09-03T00:00:00Z',grantValidUntil='2026-09-04T00:00:00Z',expiredAt='2026-09-02T00:00:00Z',revokedAt='2026-09-03T00:01:00Z',protectedOutputs=outputs)
        config_path=root/resource['configurationRef'];config=load_yaml(config_path);config['configuration']['mediaNegativePolicy']=policy;write_yaml(config_path,config);rows=[]
        for identity in nodes:
            node=identity['nodeId'];denials=[];checks=[]
            for target in policy['deniedTargets']:
                ref,sha=retain(node+'-denied-'+target['case']+'.bin',b'',node);denials.append(dict(**target,requestId=node+'-denied-'+target['case'],observedAt='2026-09-03T00:02:00Z',status='denied',inputBytesRead=0,outputBytesWritten=0,publicationCount=0,outboundRef=ref,outboundSha256=sha))
            for kind,ceiling in policy['limits'].items():
                observed={k:1 for k in policy['limits']};observed[kind]=ceiling+1;checks.append(dict(case=kind,requestId=node+'-limit-'+kind,startedAt='2026-09-03T00:03:00Z',finishedAt='2026-09-03T00:03:06Z' if kind=='elapsedSeconds' else '2026-09-03T00:03:01Z',observed=observed,terminationReason=kind,processStatus='terminated',remainingTemporaryBytes=0,remainingOutputBytes=0,publicationCount=0))
            partial_ref,partial_sha=retain(node+'-interrupted-partial.bin',b'Synthetic interrupted partial; never actual AV1.',node);run=next(r for r in env['workerEncodeExecutions'] if r['nodeId']==node)
            retry_ref,retry_sha=retain(node+'-fresh-retry-output.bin',b'Synthetic retry output; never actual AV1.',node)
            retry_probe_ref,_=retain(node+'-retry-av1-probe.yaml',dict(schemaVersion=1,kind='media_retry_decode_observation',jobId=policy['jobId'],attemptEpoch=2,nodeId=node,encoderBuild=identity['encoderBuild'],inputSha256=assembly['inputSha256'],outputArtifactRef=retry_ref,outputSha256=retry_sha,decoderBuild=policy['retryDecoderBuild'],codec='av1',decodable=True,sourceStartFrame=run['sourceStartFrame'],sourceEndFrame=run['sourceEndFrame'],decodedFrameCount=run['sourceEndFrame']-run['sourceStartFrame'],durationSeconds=2,decodeErrorCount=0,startedAt='2026-09-03T00:04:04Z',finishedAt='2026-09-03T00:04:04.001Z'),node,kind='measurement_output')
            cancel_ref,cancel_sha=retain(node+'-cancel-partial.bin',b'Synthetic active cancelled partial; never actual AV1.',node)
            life=dict(retryProbeRef=retry_probe_ref,cancelJobId=policy['cancelJobId'],cancelledAttemptEpoch=3,cancelledStartedAt='2026-09-03T00:04:04Z',cancelledPartialCreatedAt='2026-09-03T00:04:04Z',cancelledPartialRef=cancel_ref,cancelledPartialSha256=cancel_sha,cancelledProcessStatusBefore='running',cancelledProcessStatusAfter='terminated',partialRef=partial_ref,partialSha256=partial_sha,partialCreatedAt='2026-09-03T00:04:00Z',interruptedAt='2026-09-03T00:04:01Z',oldAttemptExpiresAt='2026-09-03T00:04:02Z',retriedAt='2026-09-03T00:04:03Z',retryFinishedAt='2026-09-03T00:04:04.002Z',cancelledAt='2026-09-03T00:04:05Z',cleanupFinishedAt='2026-09-03T00:04:06Z',oldAttemptEpoch=1,currentAttemptEpoch=2,retryJobId=policy['jobId'],terminalResultCount=1,remainingTemporaryBytes=0,remainingOutputBytes=0,activeProcessCount=0,cancelledAttemptPublicationCount=0,cancelledPartialDisposition='removed',cancelledPartialPublishable=False,publishedRef=retry_ref,publishedSha256=retry_sha,retryEncoderBuild=identity['encoderBuild'],retryInputSha256=assembly['inputSha256'],retrySourceStartFrame=run['sourceStartFrame'],retrySourceEndFrame=run['sourceEndFrame'],retryDecodedFrameCount=run['sourceEndFrame']-run['sourceStartFrame'],retryDecodeErrorCount=0,submissions=[dict(case=case,observedAt='2026-09-03T00:04:04.002Z' if case=='current' else '2026-09-03T00:04:07Z',attemptEpoch=1 if case=='late' else 3 if case=='cancelled' else 2,jobId=policy['cancelJobId'] if case=='cancelled' else policy['jobId'],decision='published' if case=='current' else 'rejected',publicationDelta=1 if case=='current' else 0,terminalResultDelta=1 if case=='current' else 0) for case in ('current','duplicate','late','cancelled')]);seek=[]
            for case in ('current','stale_seek','revoked'):
                ref,sha=retain(node+'-seek-'+case+'.bin',b'Synthetic authorized demand bytes' if case=='current' else b'',node);seek.append(dict(case=case,observedAt='2026-09-03T00:05:00Z',previousSeekEpoch=1,currentSeekEpoch=2,requestedSeekEpoch=1 if case=='stale_seek' else 2,grantId=policy['revokedGrantId'] if case=='revoked' else policy['currentGrantId'],decision='admitted' if case=='current' else 'denied',newReservedSlots=1 if case=='current' else 0,responseRef=ref,responseSha256=sha))
            rows.append(dict(identity=identity,deniedTargets=denials,limitCases=checks,lifecycle=life,seekCases=seek))
        access=[]
        for surface in outputs:
            for case in ('authorized','cross_user','expired','revoked','direct_origin'):
                ref,sha=retain('hls-'+surface['surface']+'-'+case+'.bin',(root/surface['ref']).read_bytes() if case=='authorized' else b'');access.append(dict(surface=surface['surface'],case=case,requestId='hls-'+surface['surface']+'-'+case,observedAt='2026-09-03T00:06:00Z',assetId=policy['assetId'],assetVersion=policy['assetVersion'],aclVersion=policy['aclVersion'],userId=policy['deniedUserId'] if case=='cross_user' else policy['authorizedUserId'],grantId=policy['expiredGrantId'] if case=='expired' else policy['revokedGrantId'] if case=='revoked' else policy['currentGrantId'],route='origin' if case=='direct_origin' else 'entry',decision='allowed' if case=='authorized' else 'denied',originContactCount=1 if case=='authorized' and surface['surface']!='cache_hit' else 0,statusCode=200 if case=='authorized' else 403,responseRef=ref,responseSha256=sha))
        report=dict(schemaVersion=1,kind='media_negative_outcomes',configurationRef=resource['configurationRef'],acceptanceProfile=env['acceptanceProfile'],subjectVersion=quality['subjectVersion'],inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']],jobId=policy['jobId'],assetId=policy['assetId'],assetVersion=policy['assetVersion'],inputSampleId=assembly['inputSampleId'],inputSha256=assembly['inputSha256'],nodes=rows,accessCases=access);env['mediaNegativeRef'],_=retain('media-negative-outcomes.yaml',report,kind='measurement_output')


    def prepare_qualified_quality_timing_fixture(self,root,execution,prefix):
        """Synthetic retained quality/timing observations, not AV1 or VMAF execution."""
        env=execution['environmentCaptured'];assembly=env['parallelMediaAssembly'];run=env['workerEncodeExecutions'][0];resource=next(r for r in execution['resources'] if r['id']=='RES-HETEROGENEOUS-WORKERS')
        def retain(name,value,kind='measurement_output'):
            ref=prefix+'/raw/'+name;path=root/ref
            if isinstance(value,bytes):path.write_bytes(value)
            else:write_yaml(path,value)
            raw=path.read_bytes();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,nodeId=run['nodeId'],byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));execution['rawOutputRefs'].append(ref);return ref,'sha256:'+hashlib.sha256(raw).hexdigest()
        plan=load_yaml(self.plan_path(root,'POC-002'));policy=dict(jobId='synthetic-approved-media-job',evaluatorBuild='synthetic-vmaf-evaluator-build',modelId='synthetic-approved-vmaf-model',modelSha256='sha256:'+'a'*64,encoderBuild=run['encoderBuild'],encoderParameters=copy.deepcopy(execution['provenance']['encoder_parameters']),inputSamples=[{k:sample[k] for k in ('id','immutableId','checksum')} for sample in execution['samples']])
        config_path=root/resource['configurationRef'];config=load_yaml(config_path);config['configuration']['mediaEvaluationPolicy']=policy;write_yaml(config_path,config)
        common=dict(configurationRef=resource['configurationRef'],subjectVersion=CHECK.compliance_subject_version(plan,execution),acceptanceProfile=env['acceptanceProfile'],jobId=policy['jobId'],inputSampleId=assembly['inputSampleId'],inputSha256=assembly['inputSha256'],outputArtifactRef=assembly['outputArtifactRef'],outputSha256=assembly['outputSha256'],encoderBuild=run['encoderBuild'],encoderParameters=policy['encoderParameters'])
        job_event={k:common[k] for k in ('configurationRef','subjectVersion','acceptanceProfile','jobId','inputSampleId','inputSha256','encoderBuild','encoderParameters')}
        job_event_ref,_=retain('media-job-start.yaml',dict(schemaVersion=1,kind='media_job_start_observation',**job_event,encodeRunRef=run['rawOutputRef'],nodeId=run['nodeId'],jobStartedAt=run['startedAt'],workerStartedAt=run['startedAt']))
        command,_=retain('vmaf-command.txt',b'Synthetic evaluator invocation fixture, never actual VMAF.\n','command_output')
        quality_ref,_=retain('vmaf-evaluator-output.yaml',dict(schemaVersion=1,kind='vmaf_evaluator_output',**common,evaluatorBuild=policy['evaluatorBuild'],modelId=policy['modelId'],modelSha256=policy['modelSha256'],evaluatedAt='2026-09-03T00:01:01Z',evaluatedFrameCount=assembly['sourceFrameCount'],vmafMean=1,evaluatorCommandRef=command))
        segment_ref,segment_sha=retain('first-playable-segment.bin',b'Synthetic first segment, never actual encoded AV1.','produced_media')
        probe_ref,_=retain('first-playable-segment-probe.yaml',dict(schemaVersion=1,kind='first_playable_segment_probe',jobId=policy['jobId'],nodeId=run['nodeId'],segmentRef=segment_ref,segmentSha256=segment_sha,inputSha256=assembly['inputSha256'],sourceStartFrame=0,sourceEndFrame=1,decodedFrameCount=1,decodeErrorCount=0,decoderBuild=assembly['decoderBuild'],codec='av1',decodable=True,observedAt='2026-09-03T00:00:00.001Z'))
        segment=dict(encodeRunRef=run['rawOutputRef'],nodeId=run['nodeId'],jobStartedAt=run['startedAt'],segmentProducedAt='2026-09-03T00:00:00.001Z',firstPlayableAt='2026-09-03T00:00:00.001Z',segmentRef=segment_ref,segmentSha256=segment_sha,sourceStartFrame=0,sourceEndFrame=1,decodeRef=probe_ref)
        env['mediaQualityTimingRef'],_=retain('media-quality-timing.yaml',dict(schemaVersion=1,kind='media_quality_timing_report',**common,jobEventRef=job_event_ref,qualityRef=quality_ref,firstSegment=segment))


    def prepare_qualified_firmware_fixture(self,root,execution,prefix):
        """Explicitly synthetic firmware/group witness, never a hardware experiment."""
        env=execution['environmentCaptured'];capture=env['productionPassthroughIdentity'];identity=capture['identity'];device=identity['gpuDeviceId'];audio=device+'-audio-function'
        policy=dict(firmwareBuild='synthetic-firmware-build',biosConfigurationId='synthetic-approved-bios-config',iommuGroupId='synthetic-approved-iommu-group',approvedGroupDeviceIds=[device,audio])
        path=root/capture['configurationRef'];config=load_yaml(path);config['configuration']['passthroughFirmwarePolicy']=policy;write_yaml(path,config)
        report=dict(schemaVersion=1,kind='production_passthrough_firmware',configurationRef=capture['configurationRef'],identity=copy.deepcopy(identity),firmwareBuild=policy['firmwareBuild'],biosConfigurationId=policy['biosConfigurationId'],hostBootId='synthetic-captured-host-boot',settingsCapturedAt='2026-09-03T00:00:00Z',guestEnumeratedAt='2026-09-03T00:00:01Z',runtimeInitializedAt='2026-09-03T00:00:02Z',iommuEnabled=True,iommuGroupId=policy['iommuGroupId'],iommuMembers=[dict(deviceId=value,requiredHostDevice=False,assignedToGuest=True) for value in policy['approvedGroupDeviceIds']],above4gEnabled=True,resizableBarEnabled=True,allocatedDeviceId=device,addressSpaceAllocatedBytes=4096,allocationSucceeded=True,enumeratedDeviceIds=[device,audio],runtimeReady=True)
        ref=prefix+'/raw/passthrough-firmware.yaml';path=root/ref;write_yaml(path,report);raw=path.read_bytes();env['productionFirmwareRef']=ref;env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType='measurement_output',nodeId=identity['nodeId'],byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));execution['rawOutputRefs'].append(ref)


    def prepare_qualified_ai_results_fixture(self,root,execution,prefix):
        """Synthetic outputs, scores, usage and dispatch traces; no provider API execution."""
        env=execution['environmentCaptured'];resource=next(r for r in execution['resources'] if r['id']=='RES-AI-BENCH');sample=execution['samples'][0];plan=load_yaml(self.plan_path(root,'POC-009'));subject=CHECK.compliance_subject_version(plan,execution)
        def retain(name,value,kind='measurement_output'):
            ref=prefix+'/raw/'+name;path=root/ref
            if isinstance(value,bytes):path.write_bytes(value)
            else:write_yaml(path,value)
            raw=path.read_bytes();env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));execution['rawOutputRefs'].append(ref);return ref,'sha256:'+hashlib.sha256(raw).hexdigest()
        methods=[dict(metricId=metric,mode='f1' if metric=='tag_f1' else 'tool_score' if metric in ('translation_comet','translation_bleu') else 'human_score' if metric=='quality_score' else 'count_ratio',methodId='synthetic-'+metric,evaluatorBuild='synthetic-independent-evaluator',rubricVersion='synthetic-approved-rubric') for metric in sorted(CHECK.AI_EVALUATED_METRICS)]
        policy=dict(subjectVersion=subject,benchmarkId='synthetic-immutable-benchmark',querySetId='synthetic-fixed-query-set',corpusId='synthetic-immutable-corpus',items=[dict(itemId='synthetic-item-'+str(i),sampleId=sample['id'],stratumId='synthetic-stratum') for i in range(60)],strata=[dict(stratumId='synthetic-stratum',language='synthetic-language',mediaQuality='synthetic-quality',durationBand='synthetic-duration',scenario='synthetic-scenario',minimumSamples=1)],evaluationMethods=methods,queries=[dict(queryId='synthetic-query',relevance=[dict(itemId='synthetic-document',grade=1)])],corpusItemIds=['synthetic-document'],retrievalCutoff=1,warmupCount=1,percentileMethod='mean',pricing=dict(version='synthetic-approved-pricing',currency='synthetic-currency',inputUnitPrice=.001,outputUnitPrice=0),gatePolicy=dict(authorizedCallerId='synthetic-authorized-caller',unauthorizedCallerId='synthetic-unauthorized-caller',assetId='synthetic-current-asset',currentAclVersion='synthetic-current-acl',revokedAclVersion='synthetic-revoked-acl',budgetPeriodId='synthetic-budget-period',budgetLimit=1,requestRateLimit=1,concurrencyLimit=1,plannedInputTokens=1,plannedOutputTokens=0))
        config_path=root/resource['configurationRef'];config=load_yaml(config_path);config['configuration']['aiEvaluationPolicy']=policy;write_yaml(config_path,config)
        common=dict(configurationRef=resource['configurationRef'],subjectVersion=subject,inputSamples=[{k:s[k] for k in ('id','immutableId','checksum')} for s in execution['samples']],acceptanceProfile=env['acceptanceProfile'],benchmarkId=policy['benchmarkId'],querySetId=policy['querySetId'],corpusId=policy['corpusId'])
        usage=[]
        for item in policy['items']:
            ref,sha=retain(item['itemId']+'-output.txt',b'Synthetic retained result; never provider/model output. '+item['itemId'].encode(),'produced_media')
            usage.append(dict(**item,inputSha256=sample['checksum'],inputTokens=1,outputTokens=0,outputRef=ref,outputSha256=sha,startedAt='2026-09-03T00:00:00Z',finishedAt='2026-09-03T00:01:00Z'))
        usage_ref,_=retain('ai-usage.yaml',dict(schemaVersion=1,kind='ai_usage_observation',**common,pricingVersion=policy['pricing']['version'],currency=policy['pricing']['currency'],items=usage))
        first=usage[0];evaluations=[]
        for method in methods:
            evaluations.append(dict(metricId=method['metricId'],itemId=first['itemId'],sampleId=first['sampleId'],stratumId=first['stratumId'],outputRef=first['outputRef'],outputSha256=first['outputSha256'],methodId=method['methodId'],evaluatorBuild=method['evaluatorBuild'],rubricVersion=method['rubricVersion'],observedAt='2026-09-03T00:01:01Z',numerator=1,denominator=1,truePositive=1,falsePositive=0,falseNegative=0,score=1))
        queries=[];warmup=[]
        for phase,started,finished in (('warmup','2026-09-03T00:01:30Z','2026-09-03T00:01:30.001Z'),('measured','2026-09-03T00:02:00Z','2026-09-03T00:02:00.001Z')):
            ref,sha=retain('ai-query-'+phase+'.yaml',dict(schemaVersion=1,kind='ai_retrieval_output',**common,queryId='synthetic-query',retrievedIds=['synthetic-document']),'produced_media')
            row=dict(queryId='synthetic-query',querySetId=policy['querySetId'],corpusId=policy['corpusId'],retrievedIds=['synthetic-document'],startedAt=started,finishedAt=finished,outputRef=ref,outputSha256=sha);(warmup if phase=='warmup' else queries).append(row)
        evaluation_ref,_=retain('ai-evaluation.yaml',dict(schemaVersion=1,kind='ai_evaluation_results',**common,evaluations=evaluations,queries=queries,warmupQueries=warmup,percentileMethod=policy['percentileMethod']))
        outcomes=[];gates=policy['gatePolicy']
        for case in ['authorized']+sorted(CHECK.AI_POLICY_GATES):
            caller=gates['unauthorizedCallerId'] if case=='permission_denied' else gates['authorizedCallerId'];acl=gates['revokedAclVersion'] if case=='acl_revoked' else gates['currentAclVersion'];at='2026-09-03T00:03:00Z';request_ids=['synthetic-authorized-provider-request'] if case=='authorized' else []
            value=dict(schemaVersion=1,kind='ai_provider_dispatch',**common,requestIds=request_ids,callerId=caller,assetId=gates['assetId'],aclVersion=acl,observedAt=at) if case=='authorized' else b''
            ref,sha=retain('ai-dispatch-'+case+'.yaml' if case=='authorized' else 'ai-dispatch-'+case+'.bin',value,'produced_media')
            outcomes.append(dict(case=case,observedAt=at,callerId=caller,assetId=gates['assetId'],aclVersion=acl,callerAllowed=case!='permission_denied',assetAllowed=case!='acl_revoked',budgetPeriodId=gates['budgetPeriodId'],budgetRemaining=0 if case=='budget_exhausted' else 1,estimatedCost=.001,requestCount=2 if case=='request_rate_exceeded' else 0,concurrentCalls=2 if case=='concurrency_exceeded' else 0,requestWindowSeconds=60,decision='dispatched' if case=='authorized' else case,providerRequestIds=request_ids,outboundRef=ref,outboundSha256=sha))
        dispatch_ref,_=retain('ai-policy-outcomes.yaml',dict(schemaVersion=1,kind='ai_dispatch_outcomes',**common,outcomes=outcomes));reviews={r['type']:r['reviewRef'] for r in execution['complianceReviews']}
        env['aiResultsRef'],_=retain('ai-results.yaml',dict(schemaVersion=1,kind='ai_results_report',**common,evaluationRef=evaluation_ref,usageRef=usage_ref,dispatchRef=dispatch_ref,privacyReviewRef=reviews['privacy'],licenseReviewRef=reviews['license']))
        data_policy=dict(policyId='synthetic-reviewed-data-policy',policyVersion='synthetic-data-policy-v1',subjectVersion=subject,assetId=gates['assetId'],classificationId='synthetic-approved-input-classification',allowedPurpose='synthetic-approved-purpose',deniedPurpose='synthetic-disallowed-purpose',privacyReviewRef=reviews['privacy'])
        data_policy.update(providerMode='commercial_external',assetVersion=env['input_sample_version'],inputSamples=copy.deepcopy(common['inputSamples']),allowedPayloadScope=[sample['immutableId'] for sample in execution['samples']])
        config['configuration']['aiDataPolicy']=data_policy;write_yaml(config_path,config)
        authorized=next(row for row in outcomes if row['case']=='authorized')
        denial_ref,denial_sha=retain('ai-data-policy-denied.bin',b'','produced_media')
        data_rows=[]
        for allowed in (True,False):
            data_rows.append(dict(case='authorized' if allowed else 'data_policy_denied',policyId=data_policy['policyId'],policyVersion=data_policy['policyVersion'],classificationId=data_policy['classificationId'],purpose=data_policy['allowedPurpose'] if allowed else data_policy['deniedPurpose'],callerId=gates['authorizedCallerId'],assetId=gates['assetId'],aclVersion=gates['currentAclVersion'],evaluatedAt='2026-09-03T00:02:59Z',dispatchedAt=authorized['observedAt'] if allowed else None,decision='allowed' if allowed else 'denied',providerRequestIds=authorized['providerRequestIds'] if allowed else [],outboundRef=authorized['outboundRef'] if allowed else denial_ref,outboundSha256=authorized['outboundSha256'] if allowed else denial_sha))
        env['aiDataPolicyRef'],_=retain('ai-data-policy-outcomes.yaml',dict(schemaVersion=1,kind='ai_data_policy_outcomes',**common,providerMode=data_policy['providerMode'],assetVersion=data_policy['assetVersion'],dispatchRef=dispatch_ref,privacyReviewRef=reviews['privacy'],outcomes=data_rows))


    def refresh_qualified_observation_fixture(self,root,record,approve_captures=False):
        """Refresh explicitly synthetic retained bytes; never actual experiment evidence."""
        env=record['environmentCaptured']
        for artifact in env['rawExecutionArtifacts']:
            path=root/artifact['ref']
            if path.exists():
                raw=path.read_bytes();artifact['byteCount']=len(raw);artifact['sha256']='sha256:'+hashlib.sha256(raw).hexdigest()
        if approve_captures:
            plan=load_yaml(self.plan_path(root,'POC-'+record['pocId'][-2:].zfill(3)))
            route=CHECK.execution_route(plan,'local-v1')
            config_path=root/env['acceptanceProfileConfigurationRef'];config=load_yaml(config_path)
            config['capturedSettings']={key:env[key] for key in CHECK.LOCAL_STRUCTURED_CAPTURES.get(plan['pocId'],{})}
            write_yaml(config_path,config)
            for ref in config.get('numericDomainReviewRefs',{}).values():
                path=root/ref;domain=load_yaml(path);domain['environmentCaptured']={key:env[key] for key in route['captureBeforeExecution']};write_yaml(path,domain)

    def test_160_physical_phone_report_and_non_vm_marker_bind_actual_scope(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-001','production')
            path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=path.read_bytes();baseline=load_yaml(path)
            ref=baseline['environmentCaptured']['android_thermal_background_observation']['rawOutputRef'];raw_path=root/ref;raw=raw_path.read_bytes()
            validate=lambda:CHECK.validate_repository(root,'production',True,selected_pocs={'POC-01'})
            self.assertEqual(validate(),[])
            for mode in ('arbitrary','empty','malformed','oversize','node','device','host','build','temperature','power','duration','background','start','end','zero_interval','vm_scope','vm_inventory','missing_scope_marker','missing_inventory_marker','numeric_scope_marker','numeric_inventory_marker'):
                path.write_bytes(original);raw_path.write_bytes(raw);record=load_yaml(path);env=record['environmentCaptured'];report=load_yaml(raw_path)
                if mode in ('arbitrary','empty','malformed','oversize'):
                    raw_path.write_text({'arbitrary':'Unrelated UTF8 report without observations','empty':'','malformed':'[unterminated','oversize':'x'*262145}[mode],encoding='utf8')
                elif mode.startswith('vm_') or 'marker' in mode:
                    target=env['android_validation_scope'] if mode.endswith('scope') or 'scope_marker' in mode else next(n for n in env['worker_node_inventory'] if n['platform']=='android')
                    if mode.startswith('missing'):target.pop('isVirtualMachine')
                    else:target['isVirtualMachine']=0 if mode.startswith('numeric') else True
                else:
                    key={'node':'nodeId','device':'deviceId','host':'physicalHostId','build':'encoderBuild','temperature':'temperaturePeakCelsius','power':'powerPeakWatts','duration':'testDurationSeconds','background':'backgroundSurvivedSeconds','start':'observedStartedAt','end':'observedFinishedAt','zero_interval':'observedFinishedAt'}[mode]
                    report[key]=99 if mode in ('temperature','power','duration','background') else '2026-09-02T00:00:00Z' if mode=='start' else '2026-09-06T00:00:00Z' if mode=='end' else report['observedStartedAt'] if mode=='zero_interval' else 'wrong-observation-identity'
                    write_yaml(raw_path,report)
                self.refresh_qualified_observation_fixture(root,record);write_yaml(path,record)
                self.assertTrue(any('physical phone observation' in e or 'tested physical Android' in e for e in validate()),mode)
        finally:temp.cleanup()
        for profile,status in (('local-v1','pass'),('production','fail')):
            temp,root=self.temp_repo()
            try:
                self.make_profile_slot(root,'POC-001',profile,status)
                self.assertEqual(CHECK.validate_repository(root,profile,status=='pass',selected_pocs={'POC-01'}),[])
            finally:temp.cleanup()

    def test_161_inference_rate_is_derived_from_retained_count_time_and_subject(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-009',profile)
                path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=path.read_bytes();baseline=load_yaml(path)
                raw_path=root/baseline['environmentCaptured']['inferenceObservationRef'];raw=raw_path.read_bytes()
                validate=lambda:CHECK.validate_repository(root,profile,True,selected_pocs={'POC-09'})
                self.assertEqual(validate(),[])
                for mode in ('overclaim','missing','wrong_type','arbitrary','empty','malformed','oversize','count_zero','count_bool','subject','input','zero_interval','before_window','after_window'):
                    path.write_bytes(original);raw_path.write_bytes(raw);record=load_yaml(path);env=record['environmentCaptured'];report=load_yaml(raw_path)
                    if mode=='overclaim':next(m for m in record['measurements'] if m['id']=='throughput')['actual']=1e9
                    elif mode=='missing':env.pop('inferenceObservationRef')
                    elif mode=='wrong_type':next(a for a in env['rawExecutionArtifacts'] if a['ref']==env['inferenceObservationRef'])['artifactType']='command_output'
                    elif mode in ('arbitrary','empty','malformed','oversize'):raw_path.write_text({'arbitrary':'Unrelated throughput assertion','empty':'','malformed':'[unterminated','oversize':'x'*262145}[mode],encoding='utf8')
                    else:
                        if mode in ('count_zero','count_bool'):report['completedItemCount']=0 if mode=='count_zero' else True
                        elif mode=='subject':report['subjectVersion']='wrong-model-prompt-parameters-runtime-tools'
                        elif mode=='input':report['inputSamples'][0]['checksum']='sha256:'+'a'*64
                        elif mode=='zero_interval':report['observedFinishedAt']=report['observedStartedAt']
                        elif mode=='before_window':report['observedStartedAt']='2026-09-02T00:00:00Z'
                        else:report['observedFinishedAt']='2026-09-05T00:00:00Z'
                        write_yaml(raw_path,report)
                    self.refresh_qualified_observation_fixture(root,record);write_yaml(path,record)
                    self.assertTrue(any('qualified inference observation' in e for e in validate()),(profile,mode))
            finally:temp.cleanup()
            for status in ('fail','inconclusive'):
                temp,root=self.temp_repo()
                try:
                    index=self.make_profile_slot(root,'POC-009',profile,status)
                    path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];record=load_yaml(path)
                    next(m for m in record['measurements'] if m['id']=='throughput')['actual']=0;write_yaml(path,record)
                    self.assertEqual(CHECK.validate_repository(root,profile,False,selected_pocs={'POC-09'}),[])
                finally:temp.cleanup()

    def test_162_three_streams_on_two_nodes_honor_trace_identity_and_caps(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-002','local-v1')
            path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];record=load_yaml(path);env=record['environmentCaptured'];runs=env['workerEncodeExecutions']
            added=copy.deepcopy(runs[0]);prefix=str(path.parent.relative_to(root)).replace('\\','/')
            for key,kind in (('rawOutputRef','command_output'),('outputArtifactRef','produced_media')):
                ref=prefix+'/raw/third-stream-'+key+'.bin';(root/ref).write_bytes(b'Synthetic third stream fixture; never an encode. '+key.encode());added[key]=ref
                env['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,nodeId=added['nodeId'],byteCount=0,sha256='sha256:'+'0'*64));record['rawOutputRefs'].append(ref)
            added['outputSha256']='sha256:'+hashlib.sha256((root/added['outputArtifactRef']).read_bytes()).hexdigest();runs.append(added)
            for i,run in enumerate(runs):run['sourceStartFrame']=i*40;run['sourceEndFrame']=(i+1)*40
            assembly=env['parallelMediaAssembly'];assembly['parts']=[{key:r[key] for key in ('nodeId','outputArtifactRef','outputSha256','sourceStartFrame','sourceEndFrame')} for r in runs]
            report_path=root/assembly['validationRef'];report=load_yaml(report_path);report['parts']=assembly['parts'];write_yaml(report_path,report)
            env['scheduler_configuration'].update(perNodeConcurrency=2,maxConcurrentSegments=3)
            next(m for m in record['measurements'] if m['id']=='encode_throughput')['actual']=3
            negative_path=root/env['mediaNegativeRef'];negative=load_yaml(negative_path)
            for row in negative['nodes']:
                selected=next(r for r in runs if r['nodeId']==row['identity']['nodeId']);life=row['lifecycle']
                life.update(retrySourceStartFrame=selected['sourceStartFrame'],retrySourceEndFrame=selected['sourceEndFrame'],retryDecodedFrameCount=selected['sourceEndFrame']-selected['sourceStartFrame'])
                probe_path=root/life['retryProbeRef'];probe=load_yaml(probe_path)
                probe.update(sourceStartFrame=life['retrySourceStartFrame'],sourceEndFrame=life['retrySourceEndFrame'],decodedFrameCount=life['retryDecodedFrameCount']);write_yaml(probe_path,probe)
            write_yaml(negative_path,negative)
            self.prepare_qualified_media_scheduling_fixture(root,record,prefix,total_capacity=3,per_node_capacity=2)
            self.refresh_qualified_observation_fixture(root,record,approve_captures=True);write_yaml(path,record);baseline=path.read_bytes()
            validate=lambda:CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-02'})
            self.assertEqual(validate(),[])
            for mode in ('duplicate_trace','duplicate_output','per_node_cap','total_cap','overclaim','no_distinct_overlap'):
                path.write_bytes(baseline);record=load_yaml(path);env=record['environmentCaptured'];runs=env['workerEncodeExecutions']
                if mode=='duplicate_trace':runs[2]['rawOutputRef']=runs[0]['rawOutputRef']
                elif mode=='duplicate_output':runs[2]['outputArtifactRef']=runs[0]['outputArtifactRef'];runs[2]['outputSha256']=runs[0]['outputSha256']
                elif mode=='per_node_cap':env['scheduler_configuration']['perNodeConcurrency']=1
                elif mode=='total_cap':env['scheduler_configuration']['maxConcurrentSegments']=2
                elif mode=='overclaim':next(m for m in record['measurements'] if m['id']=='encode_throughput')['actual']=4
                else:runs[1].update(startedAt='2026-09-03T00:01:00Z',finishedAt='2026-09-03T00:02:00Z')
                self.refresh_qualified_observation_fixture(root,record,approve_captures=True);write_yaml(path,record)
                self.assertTrue(any('qualified encode workers' in e for e in validate()),mode)
        finally:temp.cleanup()

    def test_163_recovery_pass_requires_approved_parsed_states_and_real_comparisons(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-010',profile)
                path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=path.read_bytes();record=load_yaml(path);capture=record['environmentCaptured']['recoveryEvidence']
                saved={root/a['ref']:(root/a['ref']).read_bytes() for a in record['environmentCaptured']['rawExecutionArtifacts']}
                config_path=root/capture['configurationRef'];config_bytes=config_path.read_bytes()
                validate=lambda:CHECK.validate_repository(root,profile,True,selected_pocs={'POC-10'})
                self.assertEqual(validate(),[])
                for mode in ('missing','wrong_config','missing_approval','wrong_baseline_hash','alias_reports','unrelated','empty','malformed','oversize','wrong_inputs','wrong_tool','wrong_profile','baseline_after_start','restored_outside','comparison_before_restore','state_mismatch','matching_bad_relationships','audit_link','delivery_duplicate','replay_duplicate','no_replay','value_mismatch','plaintext','unreadable_success','unreadable_count','unreadable_identity','file_bytes','file_alias','signature_mismatch','missing_gate','fake_rows','unapproved_context','wrong_artifact_type'):
                    path.write_bytes(original);config_path.write_bytes(config_bytes)
                    for artifact,raw in saved.items():artifact.write_bytes(raw)
                    record=load_yaml(path);env=record['environmentCaptured'];capture=env['recoveryEvidence'];config=load_yaml(config_path)
                    base_path=root/capture['baselineRef'];restored_path=root/capture['restoredRef'];comparison_path=root/capture['comparisonRef']
                    base=load_yaml(base_path);restored=load_yaml(restored_path);comparison=load_yaml(comparison_path)
                    if mode=='missing':env.pop('recoveryEvidence')
                    elif mode=='wrong_config':capture['configurationRef']=env['acceptanceProfileConfigurationRef']
                    elif mode=='missing_approval':config['configuration'].pop('recoveryBaseline')
                    elif mode=='wrong_baseline_hash':config['configuration']['recoveryBaseline']['baselineSha256']='sha256:'+'0'*64
                    elif mode=='alias_reports':capture['restoredRef']=capture['baselineRef']
                    elif mode in ('unrelated','empty','malformed','oversize'):
                        restored_path.write_text({'unrelated':'Unrelated UTF8 restore success claims','empty':'','malformed':'[unterminated','oversize':'x'*262145}[mode],encoding='utf8')
                    elif mode=='wrong_inputs':restored['inputSamples'][0]['checksum']='sha256:'+'0'*64
                    elif mode=='wrong_tool':restored['subjectVersion']='wrong-tool-build'
                    elif mode=='wrong_profile':restored['acceptanceProfile']={'id':'wrong'}
                    elif mode=='baseline_after_start':base['observedFinishedAt']='2026-09-03T00:00:01Z'
                    elif mode=='restored_outside':restored['observedFinishedAt']='2026-09-05T00:00:00Z'
                    elif mode=='comparison_before_restore':comparison['observedStartedAt']='2026-09-03T00:00:00Z'
                    elif mode=='state_mismatch':restored['states']['assets'][0]['version']='wrong-restored-version'
                    elif mode=='matching_bad_relationships':base['states']['sourceMappings'][0]['assetId']=restored['states']['sourceMappings'][0]['assetId']='nonexistent-asset'
                    elif mode=='audit_link':restored['states']['audit'][0]['previousSha256']='sha256:'+'1'*64
                    elif mode=='delivery_duplicate':comparison['postReplayDelivery'].append(dict(comparison['postReplayDelivery'][0]))
                    elif mode=='replay_duplicate':comparison['postReplayDelivery'][0]['publicationCount']=2
                    elif mode=='no_replay':comparison['postReplayDelivery']=json.loads(json.dumps(restored['states']['delivery']))
                    elif mode in ('value_mismatch','plaintext'):
                        item=restored['states']['valueComparisons'][0];artifact=root/item['artifactRef'];value=load_yaml(artifact)
                        if mode=='plaintext':value['password']='forbidden-plaintext-fixture'
                        else:value['comparisonDigest']='sha256:'+'b'*64
                        write_yaml(artifact,value);item['sha256']='sha256:'+hashlib.sha256(artifact.read_bytes()).hexdigest()
                    elif mode=='unreadable_success':comparison['unreadableWitness']['readbackOutcome']='succeeded'
                    elif mode=='unreadable_count':comparison['unreadableWitness']['successfulReadCount']=1
                    elif mode=='unreadable_identity':comparison['unreadableWitness']['fixtureId']='unrelated-backup'
                    elif mode=='file_bytes':(root/restored['states']['files'][0]['artifactRef']).write_bytes(b'Wrong restored file bytes.\n')
                    elif mode=='file_alias':restored['states']['files'][0]['artifactRef']=base['states']['files'][0]['artifactRef']
                    elif mode=='signature_mismatch':
                        artifact=root/restored['states']['deployment'][0]['verificationRef'];verification=load_yaml(artifact);verification['imageSha256']='sha256:'+'b'*64;write_yaml(artifact,verification)
                    elif mode=='missing_gate':comparison['rows'].pop()
                    elif mode=='fake_rows':comparison['rows'][0]['before']['database']='sha256:'+'0'*64
                    elif mode=='unapproved_context':config['configuration']['recoveryBaseline']['approvedComparisonContexts']=[]
                    else:next(a for a in env['rawExecutionArtifacts'] if a['ref']==capture['comparisonRef'])['artifactType']='command_output'
                    if mode not in ('unrelated','empty','malformed','oversize'):write_yaml(restored_path,restored)
                    write_yaml(base_path,base)
                    if mode in ('state_mismatch','matching_bad_relationships','audit_link','value_mismatch','plaintext','file_alias'):
                        for row in comparison['rows']:
                            domains=CHECK.RECOVERY_GATE_DOMAINS[row['gate']];row['before']={d:CHECK.recovery_domain_digest(base['states'][d]) for d in domains};row['after']={d:CHECK.recovery_domain_digest(restored['states'][d]) for d in domains}
                    if mode=='matching_bad_relationships':config['configuration']['recoveryBaseline']['baselineSha256']='sha256:'+hashlib.sha256(base_path.read_bytes()).hexdigest()
                    comparison['baselineSha256']='sha256:'+hashlib.sha256(base_path.read_bytes()).hexdigest();comparison['restoredSha256']='sha256:'+hashlib.sha256(restored_path.read_bytes()).hexdigest()
                    write_yaml(comparison_path,comparison);write_yaml(config_path,config)
                    self.refresh_qualified_observation_fixture(root,record);write_yaml(path,record)
                    self.assertTrue(any('qualified recovery observation' in e for e in validate()),(profile,mode))
            finally:temp.cleanup()
            for status in ('fail','inconclusive'):
                temp,root=self.temp_repo()
                try:
                    self.make_profile_slot(root,'POC-010',profile,status)
                    self.assertEqual(CHECK.validate_repository(root,profile,False,selected_pocs={'POC-10'}),[])
                finally:temp.cleanup()

    def test_164_binary_recovery_credentials_and_approved_single_event_replay(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'retained.bin'
            with mock.patch.object(CHECK,'ARTIFACT_CHUNK_BYTES',7):
                for raw in (b'\xffpassword=fixture-forbidden-value\n',b'\xff'+b'x'*40+b'\nAuthorization: Bearer fixture-forbidden-value\n',b'\xff'+b'x'*40+b'\n{"api_key":"fixture-forbidden-value"}\n'):
                    path.write_bytes(raw);result=CHECK.inspect_artifact(path,{},textual=True)
                    self.assertTrue(result['invalidUtf8']);self.assertTrue(result['credential'])
                path.write_bytes(b'\xff\x00harmless binary recovery payload');result=CHECK.inspect_artifact(path,{},textual=True)
                self.assertTrue(result['invalidUtf8']);self.assertFalse(result['credential'])
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-010','local-v1');path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];record=load_yaml(path);capture=record['environmentCaptured']['recoveryEvidence']
            base_path=root/capture['baselineRef'];restored_path=root/capture['restoredRef'];comparison_path=root/capture['comparisonRef'];config_path=root/capture['configurationRef']
            base=load_yaml(base_path);restored=load_yaml(restored_path);comparison=load_yaml(comparison_path);config=load_yaml(config_path)
            unselected=dict(eventId='fixture-unselected-event',dedupId='fixture-unselected-dedup',aggregateId='fixture-asset',status='pending',publicationCount=0,inboxProcessedCount=0)
            for report in (base,restored):report['states']['delivery'].append(dict(unselected))
            comparison['postReplayDelivery'].append(dict(unselected))
            for row in comparison['rows']:
                domains=CHECK.RECOVERY_GATE_DOMAINS[row['gate']];row['before']={d:CHECK.recovery_domain_digest(base['states'][d]) for d in domains};row['after']={d:CHECK.recovery_domain_digest(restored['states'][d]) for d in domains}
            write_yaml(base_path,base);write_yaml(restored_path,restored)
            comparison['baselineSha256']=config['configuration']['recoveryBaseline']['baselineSha256']='sha256:'+hashlib.sha256(base_path.read_bytes()).hexdigest();comparison['restoredSha256']='sha256:'+hashlib.sha256(restored_path.read_bytes()).hexdigest()
            write_yaml(comparison_path,comparison);write_yaml(config_path,config);self.refresh_qualified_observation_fixture(root,record);write_yaml(path,record)
            validate=lambda:CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-10'})
            self.assertEqual(validate(),[])
            raw=comparison_path.read_bytes();original=path.read_bytes()
            for mode in ('unapproved_replay','changed_unselected'):
                comparison_path.write_bytes(raw);path.write_bytes(original);comparison=load_yaml(comparison_path);record=load_yaml(path)
                if mode=='unapproved_replay':comparison['replayedEventIds'].append('fixture-unselected-event')
                else:comparison['postReplayDelivery'][1].update(status='processed',publicationCount=1,inboxProcessedCount=1)
                write_yaml(comparison_path,comparison);self.refresh_qualified_observation_fixture(root,record);write_yaml(path,record)
                self.assertTrue(any('qualified recovery observation' in e for e in validate()),mode)
        finally:temp.cleanup()

    def test_165_invalid_scheduler_shapes_are_rejected_without_exceptions(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-002','local-v1');path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=path.read_bytes()
            baseline=load_yaml(path);config_path=root/baseline['environmentCaptured']['acceptanceProfileConfigurationRef'];config_raw=config_path.read_bytes()
            validate=lambda:CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-02'})
            self.assertEqual(validate(),[])
            for value in (True,False,None,'not-a-config',[1],17,{}):
                path.write_bytes(original);config_path.write_bytes(config_raw);record=load_yaml(path);config=load_yaml(config_path)
                record['environmentCaptured']['scheduler_configuration']=config['capturedSettings']['scheduler_configuration']=value
                write_yaml(path,record);write_yaml(config_path,config);self.sync_capture_reviews(root,record)
                self.assertTrue(any('qualified local capture' in e or 'positive integer local concurrency caps' in e for e in validate()),repr(value))
        finally:temp.cleanup()

    def test_166_retention_schedule_requires_parseable_utc_before_state_comparison(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-010',profile);path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=path.read_bytes();record=load_yaml(path);capture=record['environmentCaptured']['recoveryEvidence']
                base_path=root/capture['baselineRef'];restored_path=root/capture['restoredRef'];comparison_path=root/capture['comparisonRef'];config_path=root/capture['configurationRef']
                saved={p:p.read_bytes() for p in (base_path,restored_path,comparison_path,config_path)}
                validate=lambda:CHECK.validate_repository(root,profile,True,selected_pocs={'POC-10'})
                self.assertEqual(validate(),[])
                for value in ('not-a-date','2026-09-06T00:00:00','2026-02-30T00:00:00Z',''):
                    path.write_bytes(original)
                    for p,raw in saved.items():p.write_bytes(raw)
                    record=load_yaml(path);base=load_yaml(base_path);restored=load_yaml(restored_path);comparison=load_yaml(comparison_path);config=load_yaml(config_path)
                    for report in (base,restored):report['states']['retention'][0]['scheduledAt']=value
                    for row in comparison['rows']:
                        domains=CHECK.RECOVERY_GATE_DOMAINS[row['gate']];row['before']={d:CHECK.recovery_domain_digest(base['states'][d]) for d in domains};row['after']={d:CHECK.recovery_domain_digest(restored['states'][d]) for d in domains}
                    write_yaml(base_path,base);write_yaml(restored_path,restored)
                    comparison['baselineSha256']=config['configuration']['recoveryBaseline']['baselineSha256']='sha256:'+hashlib.sha256(base_path.read_bytes()).hexdigest();comparison['restoredSha256']='sha256:'+hashlib.sha256(restored_path.read_bytes()).hexdigest()
                    write_yaml(comparison_path,comparison);write_yaml(config_path,config);self.refresh_qualified_observation_fixture(root,record);write_yaml(path,record)
                    self.assertTrue(any('retention scheduledAt' in e or 'qualified recovery observation' in e and 'schema' in e for e in validate()),(profile,value))
            finally:temp.cleanup()

    def test_167_six_recovery_times_bind_business_events_and_allow_zero_rpo(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-010',profile);path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=path.read_bytes();record=load_yaml(path);env=record['environmentCaptured']
                timing_path=root/env['recoveryTimingRef'];config_path=root/env['recoveryEvidence']['configurationRef'];timing=load_yaml(timing_path)
                saved={root/a['ref']:(root/a['ref']).read_bytes() for a in env['rawExecutionArtifacts']};saved[config_path]=config_path.read_bytes()
                validate=lambda:CHECK.validate_repository(root,profile,True,selected_pocs={'POC-10'})
                self.assertEqual(validate(),[])
                for mode in ('rpo_observed','rto_observed','service_recovery_time','vm_recovery_time','core_browsing_recovery_time','playback_recovery_time','missing_report','wrong_config','wrong_subject','wrong_input','wrong_tool','missing_event','duplicate_event','arbitrary_event','wrong_event_time','wrong_event_subject','outside_window','reverse_recovery','checkpoint_after_baseline','missing_witness','alias_witness','malformed','oversize'):
                    path.write_bytes(original)
                    for artifact,raw in saved.items():artifact.write_bytes(raw)
                    record=load_yaml(path);env=record['environmentCaptured'];report=load_yaml(timing_path)
                    if mode in CHECK.RECOVERY_TIME_ENDPOINTS:next(m for m in record['measurements'] if m['id']==mode)['actual']=0
                    elif mode=='missing_report':env.pop('recoveryTimingRef')
                    elif mode=='wrong_config':report['configurationRef']=env['acceptanceProfileConfigurationRef']
                    elif mode=='wrong_subject':report['subjects']['physicalHostId']='unapproved-host'
                    elif mode=='wrong_input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                    elif mode=='wrong_tool':report['subjectVersion']='wrong-tool-version'
                    elif mode=='missing_event':report['events'].pop()
                    elif mode=='duplicate_event':report['events'][-1]=dict(report['events'][0])
                    elif mode in ('arbitrary_event','wrong_event_time','wrong_event_subject'):
                        event_path=root/report['events'][3]['witnessRef'];witness=load_yaml(event_path)
                        if mode=='arbitrary_event':event_path.write_text('Unrelated recovery time assertions\n',encoding='utf8')
                        else:
                            if mode=='wrong_event_time':witness['observedAt']='2026-09-03T00:00:02Z'
                            else:witness['subjects']['vmSetId']='another-vm-set'
                            write_yaml(event_path,witness)
                    elif mode in ('outside_window','reverse_recovery','checkpoint_after_baseline'):
                        event=report['events'][3] if mode=='outside_window' else report['events'][2] if mode=='reverse_recovery' else report['events'][0]
                        event['observedAt']='2026-09-05T00:00:00Z' if mode=='outside_window' else '2026-09-03T00:00:02Z'
                        witness_path=root/event['witnessRef'];witness=load_yaml(witness_path);witness['observedAt']=event['observedAt'];write_yaml(witness_path,witness)
                    elif mode=='missing_witness':report['events'][3]['witnessRef']=str(timing_path.relative_to(root)).replace('\\','/')+'-missing'
                    elif mode=='alias_witness':report['events'][3]['witnessRef']=report['events'][4]['witnessRef']
                    elif mode=='malformed':timing_path.write_text('[unterminated',encoding='utf8')
                    else:timing_path.write_text('x'*262145,encoding='utf8')
                    if mode not in ('malformed','oversize'):write_yaml(timing_path,report)
                    self.refresh_qualified_observation_fixture(root,record);write_yaml(path,record)
                    self.assertTrue(any('qualified recovery timing' in e for e in validate()),(profile,mode))
                # Independent endpoints may differ; readiness is not report capture duration.
                path.write_bytes(original)
                for artifact,raw in saved.items():artifact.write_bytes(raw)
                record=load_yaml(path);report=load_yaml(timing_path)
                offsets={'services_ready':1,'vm_set_ready':2,'authenticated_browsing_succeeded':3,'authorized_playback_succeeded':4,'recovery_completed':4}
                for event in report['events']:
                    if event['event'] in offsets:
                        event['observedAt']='2026-09-03T00:00:0'+str(offsets[event['event']])+'Z';witness_path=root/event['witnessRef'];witness=load_yaml(witness_path);witness['observedAt']=event['observedAt'];write_yaml(witness_path,witness)
                for metric,(_,last) in CHECK.RECOVERY_TIME_ENDPOINTS.items():
                    if metric!='rpo_observed':next(m for m in record['measurements'] if m['id']==metric)['actual']=offsets[last]
                write_yaml(timing_path,report);self.refresh_qualified_observation_fixture(root,record);write_yaml(path,record);self.assertEqual(validate(),[])
                # Zero RPO is valid when the approved recoverable checkpoint equals the boundary.
                base_path=root/record['environmentCaptured']['recoveryEvidence']['baselineRef'];comparison_path=root/record['environmentCaptured']['recoveryEvidence']['comparisonRef'];base=load_yaml(base_path);comparison=load_yaml(comparison_path);config=load_yaml(config_path)
                base['observedFinishedAt']='2026-09-03T00:00:00Z';report['subjects']['backupCheckpointAt']=config['configuration']['recoveryTimingSubjects']['backupCheckpointAt']='2026-09-03T00:00:00Z'
                for event in report['events']:
                    if event['event']=='backup_checkpoint':event['observedAt']='2026-09-03T00:00:00Z'
                    witness_path=root/event['witnessRef'];witness=load_yaml(witness_path);witness['subjects']=report['subjects'];witness['observedAt']=event['observedAt'];write_yaml(witness_path,witness)
                write_yaml(base_path,base);comparison['baselineSha256']=config['configuration']['recoveryBaseline']['baselineSha256']='sha256:'+hashlib.sha256(base_path.read_bytes()).hexdigest()
                write_yaml(comparison_path,comparison);write_yaml(config_path,config);write_yaml(timing_path,report);next(m for m in record['measurements'] if m['id']=='rpo_observed')['actual']=0
                self.refresh_qualified_observation_fixture(root,record);write_yaml(path,record);self.assertEqual(validate(),[])
            finally:temp.cleanup()
            for status in ('fail','inconclusive'):
                temp,root=self.temp_repo()
                try:
                    self.make_profile_slot(root,'POC-010',profile,status);self.assertEqual(CHECK.validate_repository(root,profile,False,selected_pocs={'POC-10'}),[])
                finally:temp.cleanup()

    def test_168_recovery_timing_never_reloads_unbounded_state_reports(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-010','local-v1');result=load_yaml(root/load_yaml(index)['resultRef']);record=load_yaml(root/result['executionRef']);env=record['environmentCaptured']
            capture=env['recoveryEvidence'];prefix=Path(result['executionRef']).parent.as_posix()
            defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];plan=load_yaml(self.plan_path(root,'POC-010'))
            window=tuple(CHECK.utc(env['executionWindow'][key]) for key in ('startedAt','finishedAt'))
            reports=[root/capture[key] for key in ('baselineRef','restoredRef','comparisonRef')];original={p:p.read_bytes() for p in reports};ordinary_load=CHECK.load
            def guarded_load(path):
                self.assertNotIn(Path(path),reports,'State reports must use the bounded typed reader')
                return ordinary_load(path)
            for selected in reports:
                for invalid in ('x'*262145,'[unterminated','states: true\n'):
                    for path,raw in original.items():path.write_bytes(raw)
                    selected.write_text(invalid,encoding='utf8');errors=[]
                    with mock.patch.object(CHECK,'load',side_effect=guarded_load):
                        CHECK.validate_qualified_recovery_timing(root,plan,record,prefix,'pass',window,defs,errors,{})
                    self.assertTrue(errors,(selected.name,invalid[:20]))
        finally:temp.cleanup()

    def test_169_production_a380_metrics_bind_device_telemetry_and_range_bytes(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-002','production');result=load_yaml(root/load_yaml(index)['resultRef']);record=load_yaml(root/result['executionRef']);env=record['environmentCaptured'];capture=env['productionA380Encode'];prefix=Path(result['executionRef']).parent.as_posix()
            plan=load_yaml(self.plan_path(root,'POC-002'));defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];window=tuple(CHECK.utc(env['executionWindow'][key]) for key in ('startedAt','finishedAt'))
            telemetry_path=root/capture['telemetryRef'];request_path=root/capture['rangeRef'];config_path=root/capture['configurationRef'];request=load_yaml(request_path);body_path=root/request['responseBodyRef']
            originals={p:p.read_bytes() for p in (telemetry_path,request_path,config_path,body_path)};original=copy.deepcopy(record)
            def validate(data):
                errors=[];CHECK.validate_qualified_a380_encode(root,plan,data,prefix,'pass',window,defs,errors,{});return errors
            self.assertEqual(CHECK.validate_repository(root,'production',True,selected_pocs={'POC-02'}),[]);self.assertEqual(validate(record),[])
            for mode in ('missing','bad_capture','cpu_only','non_intel','other_gpu','software','wrong_device','wrong_host','wrong_driver','wrong_runtime','unapproved_config','bad_inventory','bad_runs','wrong_node','wrong_run_device','wrong_run_backend','wrong_output','bad_run_time','wrong_report_identity','wrong_input','wrong_report_output','missing_telemetry','arbitrary_telemetry','oversize_telemetry','bad_sample_type','nan_sample','bad_sample_time','out_of_phase','missing_phase','wrong_interval','repeated_sample','sampling_tool','peak_power','peak_temperature','range_latency','wrong_path','wrong_status','wrong_range_header','wrong_body','wrong_body_hash','wrong_body_node','request_before_encode','invalid_first_byte'):
                for p,raw in originals.items():p.write_bytes(raw)
                data=copy.deepcopy(original);env=data['environmentCaptured'];capture=env['productionA380Encode'];telemetry=load_yaml(telemetry_path);request=load_yaml(request_path);config=load_yaml(config_path)
                if mode=='missing':env.pop('productionA380Encode')
                elif mode=='bad_capture':env['productionA380Encode']=True
                elif mode=='cpu_only':config['configuration']={'cpu_only':True}
                elif mode in ('non_intel','other_gpu','software','wrong_device','wrong_host','wrong_driver','wrong_runtime'):
                    key,value={'non_intel':('gpuVendor','Other'),'other_gpu':('gpuModel','Another GPU'),'software':('encoderBackend','software'),'wrong_device':('gpuDeviceId','another-device'),'wrong_host':('physicalHostId','another-host'),'wrong_driver':('driverBuild','another-driver'),'wrong_runtime':('runtimeBuild','another-runtime')}[mode];capture['identity'][key]=value
                elif mode=='unapproved_config':capture['configurationRef']=env['acceptanceProfileConfigurationRef']
                elif mode=='bad_inventory':env['worker_node_inventory']=True
                elif mode=='bad_runs':env['workerEncodeExecutions']=True
                elif mode=='wrong_node':env['worker_node_inventory'][0]['gpuDeviceId']='another-device'
                elif mode=='wrong_run_device':env['workerEncodeExecutions'][0]['gpuDeviceId']='another-device'
                elif mode=='wrong_run_backend':env['workerEncodeExecutions'][0]['encoderBackend']='software'
                elif mode=='wrong_output':capture['outputArtifactRef']=env['workerEncodeExecutions'][1]['outputArtifactRef']
                elif mode=='bad_run_time':env['workerEncodeExecutions'][0]['startedAt']='not-a-date'
                elif mode=='wrong_report_identity':telemetry['identity']['physicalHostId']='another-host'
                elif mode=='wrong_input':telemetry['inputSha256']='sha256:'+'0'*64
                elif mode=='wrong_report_output':request['outputArtifactRef']=env['producedMediaArtifactRef']
                elif mode=='missing_telemetry':capture['telemetryRef']+='-missing'
                elif mode=='arbitrary_telemetry':telemetry_path.write_text('Claimed peaks without retained telemetry\n',encoding='utf8')
                elif mode=='oversize_telemetry':telemetry_path.write_text('x'*262145,encoding='utf8')
                elif mode=='bad_sample_type':telemetry['samples'][0]['powerWatts']=True
                elif mode=='nan_sample':telemetry['samples'][0]['temperatureCelsius']=float('nan')
                elif mode=='bad_sample_time':telemetry['samples'][0]['observedAt']='not-a-date'
                elif mode=='out_of_phase':telemetry['samples'][0]['phase']='soak'
                elif mode=='missing_phase':telemetry['samples']=[s for s in telemetry['samples'] if s['phase']!='concurrency']
                elif mode=='wrong_interval':telemetry['samples'][1]['observedAt']='2026-09-03T00:00:11Z'
                elif mode=='repeated_sample':telemetry['samples'].insert(1,copy.deepcopy(telemetry['samples'][0]))
                elif mode=='sampling_tool':telemetry['sampling']['toolBuild']='another-tool'
                elif mode in ('peak_power','peak_temperature','range_latency'):
                    mid={'peak_power':'encoder_power_peak_watts','peak_temperature':'encoder_temperature_peak_celsius','range_latency':'a380_range_first_byte_latency'}[mode];next(m for m in data['measurements'] if m['id']==mid)['actual']=2
                elif mode=='wrong_path':request['mediaPath']='/unapproved/path'
                elif mode=='wrong_status':request['statusCode']=200
                elif mode=='wrong_range_header':request['contentRange']='bytes 0-8/99'
                elif mode=='wrong_body':
                    body_path.write_bytes(b'Corrupt!');request['responseSha256']='sha256:'+hashlib.sha256(body_path.read_bytes()).hexdigest()
                elif mode=='wrong_body_hash':request['responseSha256']='sha256:'+'0'*64
                elif mode=='wrong_body_node':next(a for a in env['rawExecutionArtifacts'] if a['ref']==request['responseBodyRef'])['nodeId']='other-node'
                elif mode=='request_before_encode':request['requestStartedAt']=request['firstByteAt']='2026-09-03T00:00:30Z'
                else:request['firstByteAt']='invalid-utc'
                if mode not in ('arbitrary_telemetry','oversize_telemetry'):write_yaml(telemetry_path,telemetry)
                write_yaml(request_path,request);write_yaml(config_path,config);self.assertTrue(validate(data),mode)
            # Values come from measured rows, including legitimate subzero temperatures.
            for p,raw in originals.items():p.write_bytes(raw)
            record=copy.deepcopy(original);telemetry=load_yaml(telemetry_path);request=load_yaml(request_path)
            for row in telemetry['samples']:row['powerWatts']=2;row['temperatureCelsius']=-10
            request['firstByteAt']='2026-09-03T00:01:00.002Z'
            for mid,value in (('encoder_power_peak_watts',2),('encoder_temperature_peak_celsius',-10),('a380_range_first_byte_latency',2)):next(m for m in record['measurements'] if m['id']==mid)['actual']=value
            write_yaml(telemetry_path,telemetry);write_yaml(request_path,request);self.assertEqual(validate(record),[])
            # Partial responses still bind exact bytes even with self-consistent returned-body hashes.
            source_bytes=(root/original['environmentCaptured']['productionA380Encode']['outputArtifactRef']).read_bytes()
            self.assertGreater(len(source_bytes),2)
            for first,last in ((0,len(source_bytes)-2),(1,len(source_bytes)-1)):
                for p,raw in originals.items():p.write_bytes(raw)
                data=copy.deepcopy(original);request=load_yaml(request_path);body=source_bytes[first:last+1]
                request.update(rangeStart=first,rangeEnd=last,requestRange=f'bytes={first}-{last}',contentRange=f'bytes {first}-{last}/{len(source_bytes)}')
                body_path.write_bytes(body);request['responseSha256']='sha256:'+hashlib.sha256(body).hexdigest()
                write_yaml(request_path,request);self.refresh_qualified_observation_fixture(root,data)
                self.assertEqual(validate(data),[])
                corrupt=bytes([body[0]^1])+body[1:]
                body_path.write_bytes(corrupt);request['responseSha256']='sha256:'+hashlib.sha256(corrupt).hexdigest()
                write_yaml(request_path,request);self.refresh_qualified_observation_fixture(root,data)
                errors=validate(data)
                self.assertTrue(any('actual Range response must equal' in error for error in errors),errors)
        finally:temp.cleanup()
        for profile,status in (('local-v1','pass'),('production','fail'),('production','inconclusive')):
            temp,root=self.temp_repo()
            try:
                self.make_profile_slot(root,'POC-002',profile,status);self.assertEqual(CHECK.validate_repository(root,profile,status=='pass',selected_pocs={'POC-02'}),[])
            finally:temp.cleanup()

    def test_170_access_gates_bind_requests_acl_cache_and_actual_returned_bytes(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-007',profile);result=load_yaml(root/load_yaml(index)['resultRef']);record=load_yaml(root/result['executionRef']);env=record['environmentCaptured'];report_path=root/env['accessOutcomeRef'];report=load_yaml(report_path);config_path=root/report['configurationRef'];prefix=Path(result['executionRef']).parent.as_posix();plan=load_yaml(self.plan_path(root,'POC-007'));defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];window=tuple(CHECK.utc(env['executionWindow'][key]) for key in ('startedAt','finishedAt'))
                originals={root/a['ref']:(root/a['ref']).read_bytes() for a in env['rawExecutionArtifacts']};originals[config_path]=config_path.read_bytes();original=copy.deepcopy(record)
                def validate(data):
                    errors=[];CHECK.validate_qualified_access_outcomes(root,plan,data,prefix,'pass',window,defs,errors,{});return errors
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-07'}),[]);self.assertEqual(validate(record),[])
                modes=['missing_report','arbitrary_report','oversize_report','bad_policy','wrong_config','wrong_profile','wrong_acl','wrong_input','missing_case','duplicate_case','wrong_witness_type','bad_source','authorized_corrupt','if_range','stream_buffer','deny_payload','deny_duplicate_error','deny_status','deny_other_range','expired_current_grant','unexpired_grant','cross_user_subject','cross_user_grant','cache_key','cache_order','rate_below_limit','rate_no_attempts','rate_bad_sequence','rate_wrong_status','rate_origin_bypass','rate_window','rate_warmup_corrupt','rate_attempt_hash','rate_attempt_payload','wrong_path','bad_time','body_hash','body_count','aliased_body','claimed_gate']+(['missing_direct_source','missing_direct_admin','missing_direct_worker'] if profile=='local-v1' else [])
                for mode in modes:
                    for p,raw in originals.items():p.write_bytes(raw)
                    data=copy.deepcopy(original);env=data['environmentCaptured'];report=load_yaml(report_path);config=load_yaml(config_path);policy=config['configuration']['accessPolicy']
                    case='expired' if mode in ('expired_current_grant','unexpired_grant') else 'cross_user' if mode in ('cross_user_subject','cross_user_grant','cache_key','cache_order') else 'rate_limit' if mode.startswith('rate_') else 'authorized_range' if mode in ('authorized_corrupt','wrong_path','body_hash','body_count','aliased_body','bad_time') else 'authorized_if_range' if mode=='if_range' else 'authorized_stream' if mode=='stream_buffer' else 'unauthorized'
                    row=next(r for r in report['cases'] if r['case']==case);witness_path=root/row['witnessRef'];witness=load_yaml(witness_path);body_path=root/witness['responseBodyRef']
                    if mode=='missing_report':env.pop('accessOutcomeRef')
                    elif mode=='arbitrary_report':report_path.write_text('Unrelated ACL claims\n',encoding='utf8')
                    elif mode=='oversize_report':report_path.write_text('x'*262145,encoding='utf8')
                    elif mode=='bad_policy':config['configuration']['accessPolicy']=True
                    elif mode=='wrong_config':report['configurationRef']=env['acceptanceProfileConfigurationRef']
                    elif mode=='wrong_profile':report['acceptanceProfile']['id']='production' if profile=='local-v1' else 'local-v1'
                    elif mode=='wrong_acl':witness['aclVersion']='stale-acl'
                    elif mode=='wrong_input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                    elif mode=='missing_case':report['cases'].pop()
                    elif mode=='duplicate_case':report['cases'][-1]=copy.deepcopy(report['cases'][0])
                    elif mode=='wrong_witness_type':next(a for a in env['rawExecutionArtifacts'] if a['ref']==row['witnessRef'])['artifactType']='command_output'
                    elif mode=='bad_source':env['inputSampleArtifacts']=True
                    elif mode in ('authorized_corrupt','deny_payload','deny_duplicate_error'):
                        body_path.write_bytes(b'Corrupt!' if mode=='authorized_corrupt' else b'{"error":"protected bytes","error":"access_denied"}' if mode=='deny_duplicate_error' else b'Synthetic protected payload leaked')
                        witness['responseByteCount']=body_path.stat().st_size;witness['responseSha256']='sha256:'+hashlib.sha256(body_path.read_bytes()).hexdigest()
                    elif mode=='if_range':witness['ifRange']='stale-version'
                    elif mode=='stream_buffer':witness['maximumBufferedBytes']=policy['maximumBufferedBytes']+1
                    elif mode=='deny_status':witness['statusCode']=206
                    elif mode=='deny_other_range':witness['rangeStart']=1;witness['rangeEnd']=8;witness['requestRange']='bytes=1-8'
                    elif mode=='expired_current_grant':witness['grantId']=policy['authorizedGrantId']
                    elif mode=='unexpired_grant':policy['expiredAt']='2026-09-04T00:00:00Z'
                    elif mode=='cross_user_subject':witness['userId']=policy['authorizedUserId']
                    elif mode=='cross_user_grant':witness['grantId']=policy['authorizedGrantId']
                    elif mode=='cache_key':witness['cacheKey']='other-cache'
                    elif mode=='cache_order':witness['observedAt']='2026-09-03T00:00:00Z'
                    elif mode=='rate_below_limit':witness['requestCount']=2
                    elif mode=='rate_no_attempts':witness['rateAttempts']=[]
                    elif mode=='rate_bad_sequence':witness['rateAttempts'][1]['sequence']=3
                    elif mode=='rate_wrong_status':witness['rateAttempts'][-1]['statusCode']=206
                    elif mode=='rate_origin_bypass':witness['rateAttempts'][-1]['originContacted']=True;witness['originRequestCount']=3
                    elif mode=='rate_window':witness['rateWindowSeconds']=1
                    elif mode in ('rate_warmup_corrupt','rate_attempt_hash','rate_attempt_payload'):
                        attempt=witness['rateAttempts'][0 if mode!='rate_attempt_payload' else -1]
                        if mode=='rate_attempt_hash':attempt['responseSha256']='sha256:'+'0'*64
                        else:
                            returned=root/attempt['responseBodyRef'];returned.write_bytes(b'Corrupt!' if mode=='rate_warmup_corrupt' else b'Protected payload');attempt['responseSha256']='sha256:'+hashlib.sha256(returned.read_bytes()).hexdigest();attempt['responseByteCount']=returned.stat().st_size
                    elif mode=='wrong_path':witness['requestURL']='https://other.invalid/protected'
                    elif mode=='bad_time':witness['observedAt']='not-a-date'
                    elif mode=='body_hash':witness['responseSha256']='sha256:'+'0'*64
                    elif mode=='body_count':witness['responseByteCount']+=1
                    elif mode=='aliased_body':witness['responseBodyRef']=row['witnessRef']
                    elif mode=='claimed_gate':next(m for m in data['measurements'] if m['id']=='unauthorized_identity_denied')['actual']=False
                    else:report['cases']=[r for r in report['cases'] if r['case']!=mode.removeprefix('missing_')]
                    if mode not in ('arbitrary_report','oversize_report'):write_yaml(report_path,report)
                    write_yaml(config_path,config);write_yaml(witness_path,witness);self.assertTrue(validate(data),(profile,mode))
                # Denial may retain an exact public error document with no arbitrary protected payload.
                for p,raw in originals.items():p.write_bytes(raw)
                record=copy.deepcopy(original);report=load_yaml(report_path)
                for row in report['cases']:
                    if row['case'].startswith('authorized_'):continue
                    path=root/row['witnessRef'];witness=load_yaml(path);body=root/witness['responseBodyRef'];body.write_text(json.dumps({'error':'rate_limited' if row['case']=='rate_limit' else 'access_denied'}),encoding='utf8');witness['responseByteCount']=body.stat().st_size;witness['responseSha256']='sha256:'+hashlib.sha256(body.read_bytes()).hexdigest()
                    if row['case']=='rate_limit':witness['rateAttempts'][-1].update(responseSha256=witness['responseSha256'],responseByteCount=witness['responseByteCount'])
                    write_yaml(path,witness)
                self.assertEqual(validate(record),[])
            finally:temp.cleanup()
            for status in ('fail','inconclusive'):
                temp,root=self.temp_repo()
                try:
                    self.make_profile_slot(root,'POC-007',profile,status);self.assertEqual(CHECK.validate_repository(root,profile,False,selected_pocs={'POC-07'}),[])
                finally:temp.cleanup()

    def test_171_range_matrix_binds_response_slices_versions_cache_recovery_and_latency(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-003',profile);result=load_yaml(root/load_yaml(index)['resultRef']);record=load_yaml(root/result['executionRef']);env=record['environmentCaptured'];report_path=root/env['rangeMatrixRef'];report=load_yaml(report_path);config_path=root/report['configurationRef'];prefix=Path(result['executionRef']).parent.as_posix();plan=load_yaml(self.plan_path(root,'POC-003'));defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];window=tuple(CHECK.utc(env['executionWindow'][key]) for key in ('startedAt','finishedAt'))
                originals={root/a['ref']:(root/a['ref']).read_bytes() for a in env['rawExecutionArtifacts']};originals[config_path]=config_path.read_bytes();original=copy.deepcopy(record)
                def validate(data):
                    errors=[];CHECK.validate_qualified_range_matrix(root,plan,data,prefix,'pass',window,defs,errors,{});return errors
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-03'}),[]);self.assertEqual(validate(record),[])
                for mode in ('missing_report','arbitrary_report','oversize_report','bad_policy','wrong_config','wrong_input','missing_case','duplicate_case','wrong_witness_type','wrong_status','corrupt_bytes','wrong_range','wrong_etag','if_match_validator','if_stale_partial','updated_stale_bytes','update_hash','updated_before_change','partial_complete','partial_read_payload','recovery_order','retry_excess','buffer_excess','cache_hit_miss','cold_without_purge','slow_profile','multi_serial','multi_same_user','cache_shared_key','transient_shared_key','other_user_identity','denied_payload','slice_gap','slice_corrupt','slice_size','cache_object_corrupt','cache_allocation','cache_duplicate','cache_alias','cache_partial_visible','cache_updated_stale','cache_cleanup_objects','hot_latency','cold_latency','slow_latency','multi_latency','correctness','bad_time','wrong_path'):
                    for p,raw in originals.items():p.write_bytes(raw)
                    data=copy.deepcopy(original);env=data['environmentCaptured'];report=load_yaml(report_path);config=load_yaml(config_path);policy=config['configuration']['rangeMatrixPolicy']
                    case='if_match' if mode=='if_match_validator' else 'if_stale' if mode=='if_stale_partial' else 'updated' if mode in ('updated_stale_bytes','updated_before_change') else 'interrupted' if mode=='partial_complete' else 'partial_read' if mode=='partial_read_payload' else 'recovered' if mode in ('recovery_order','retry_excess') else 'hit' if mode=='cache_hit_miss' else 'latency_cold' if mode=='cold_without_purge' else 'latency_slow' if mode=='slow_profile' else 'latency_multi' if mode in ('multi_serial','multi_same_user') else 'denied_user' if mode=='denied_payload' else 'range_start'
                    row=next(r for r in report['cases'] if r['case']==case);witness_path=root/row['witnessRef'];witness=load_yaml(witness_path);request=witness['requests'][0];body=root/request['responseBodyRef'];update_path=root/report['sourceUpdateRef'];update=load_yaml(update_path);lifecycle_path=root/report['cacheLifecycleRef'];lifecycle=load_yaml(lifecycle_path)
                    if mode in ('transient_shared_key','other_user_identity'):
                        row=next(r for r in report['cases'] if r['case']=='other_user');witness_path=root/row['witnessRef'];witness=load_yaml(witness_path);request=witness['requests'][0]
                    if mode=='missing_report':env.pop('rangeMatrixRef')
                    elif mode=='arbitrary_report':report_path.write_text('All Range cases allegedly pass\n',encoding='utf8')
                    elif mode=='oversize_report':report_path.write_text('x'*262145,encoding='utf8')
                    elif mode=='bad_policy':config['configuration']['rangeMatrixPolicy']=True
                    elif mode=='wrong_config':report['configurationRef']=env['acceptanceProfileConfigurationRef']
                    elif mode=='wrong_input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                    elif mode=='missing_case':report['cases'].pop()
                    elif mode=='duplicate_case':report['cases'][-1]=copy.deepcopy(report['cases'][0])
                    elif mode=='wrong_witness_type':next(a for a in env['rawExecutionArtifacts'] if a['ref']==row['witnessRef'])['artifactType']='command_output'
                    elif mode=='wrong_status':request['statusCode']=200
                    elif mode in ('corrupt_bytes','denied_payload','partial_read_payload','updated_stale_bytes'):
                        if mode=='updated_stale_bytes':body.write_bytes((root/env['inputSampleArtifacts'][0]['inputArtifactRef']).read_bytes()[:8])
                        else:body.write_bytes(b'Corrupt!')
                        request['responseByteCount']=body.stat().st_size;request['responseSha256']='sha256:'+hashlib.sha256(body.read_bytes()).hexdigest()
                    elif mode=='wrong_range':request['requestRange']='bytes=1-8'
                    elif mode=='wrong_etag':request['etag']='"stale-version"'
                    elif mode=='if_match_validator':request['ifRange']='"stale-version"'
                    elif mode=='if_stale_partial':request['statusCode']=206
                    elif mode=='update_hash':update['updatedSha256']=update['baseSha256']
                    elif mode=='updated_before_change':request['startedAt']=request['firstByteAt']=request['finishedAt']='2026-09-03T00:00:19Z'
                    elif mode=='partial_complete':request['cacheComplete']=request['cacheVisible']=True
                    elif mode=='recovery_order':request['startedAt']=request['firstByteAt']=request['finishedAt']='2026-09-03T00:00:02Z'
                    elif mode=='retry_excess':request['retryCount']=policy['maximumRetries']+1
                    elif mode=='buffer_excess':request['maximumBufferedBytes']=policy['maximumBufferedBytes']+1
                    elif mode=='cache_hit_miss':request['cacheStatus']='MISS'
                    elif mode=='cold_without_purge':request['cachePurged']=False
                    elif mode=='slow_profile':request['originDelayMs']=policy['slowOriginDelayMs']+1
                    elif mode=='multi_serial':
                        later=witness['requests'][1];later['startedAt']='2026-09-03T00:00:02Z';later['firstByteAt']='2026-09-03T00:00:02.001Z';later['finishedAt']='2026-09-03T00:00:02.002Z'
                    elif mode=='multi_same_user':witness['requests'][1]['userId']=request['userId']
                    elif mode=='transient_shared_key':request['cacheKey']='synthetic-cache-'+policy['authorizedUsers'][0]
                    elif mode=='other_user_identity':request['userId']=policy['authorizedUsers'][0];request['cacheKey']='synthetic-cache-'+policy['authorizedUsers'][0]
                    elif mode=='cache_shared_key':
                        for entry in report['cases']:
                            path=root/entry['witnessRef'];captured=load_yaml(path)
                            for r in captured['requests']:r['cacheKey']='shared-protected-key'
                            write_yaml(path,captured)
                        for r in witness['requests']:r['cacheKey']='shared-protected-key'
                    elif mode=='slice_gap':report['slices'][1]['start']+=1
                    elif mode=='slice_size':policy['sliceBytes']=8
                    elif mode=='slice_corrupt':
                        segment=report['slices'][0];path=root/segment['artifactRef'];path.write_bytes(b'x'*16);segment['sha256']='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
                    elif mode=='cache_object_corrupt':
                        item=lifecycle['stages'][1]['objects'][0];path=root/item['artifactRef'];path.write_bytes(b'x'*item['byteCount']);item['sha256']='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
                    elif mode=='cache_allocation':lifecycle['stages'][1]['allocatedBytes']+=1
                    elif mode in ('cache_duplicate','cache_alias'):
                        stage=lifecycle['stages'][1];duplicate=copy.deepcopy(stage['objects'][0])
                        if mode=='cache_alias':
                            alias=root/prefix/'raw/cache-physical-alias.bin';os.link(root/duplicate['artifactRef'],alias);duplicate['artifactRef']=alias.relative_to(root).as_posix();data['rawOutputRefs'].append(duplicate['artifactRef']);env['rawExecutionArtifacts'].append(dict(ref=duplicate['artifactRef'],artifactType='produced_media',byteCount=duplicate['byteCount'],sha256=duplicate['sha256']))
                        stage['objects'].append(duplicate);stage['allocatedBytes']*=2
                    elif mode=='cache_partial_visible':lifecycle['stages'][2]['objects'][0]['visible']=True
                    elif mode=='cache_updated_stale':lifecycle['stages'][4]['objects'][0]['sourceVersion']=policy['baseVersion']
                    elif mode=='cache_cleanup_objects':lifecycle['stages'][-1]['objects']=copy.deepcopy(lifecycle['stages'][1]['objects'])
                    elif mode in ('hot_latency','cold_latency','slow_latency','multi_latency'):
                        mid={'hot_latency':'range_hot_cache_latency','cold_latency':'range_cold_cache_latency','slow_latency':'range_slow_origin_latency','multi_latency':'range_multi_user_latency'}[mode];next(m for m in data['measurements'] if m['id']==mid)['actual']=2
                    elif mode=='correctness':next(m for m in data['measurements'] if m['id']=='range_correctness')['actual']=99
                    elif mode=='bad_time':request['firstByteAt']='not-a-date'
                    else:request['requestURL']='https://other.invalid/asset'
                    if mode not in ('arbitrary_report','oversize_report'):write_yaml(report_path,report)
                    write_yaml(config_path,config);write_yaml(witness_path,witness);write_yaml(update_path,update);write_yaml(lifecycle_path,lifecycle);self.assertTrue(validate(data),(profile,mode))
                for p,raw in originals.items():p.write_bytes(raw)
                data=copy.deepcopy(original);config=load_yaml(config_path);config['configuration']['rangeMatrixPolicy']['percentileMethod']='nearest-rank-p95';write_yaml(config_path,config);self.assertEqual(validate(data),[])
                # Stable opaque ETags are permitted; they need not encode the content hash.
                config['configuration']['rangeMatrixPolicy'].update(baseETag='"opaque-old"',updatedETag='"opaque-new"');write_yaml(config_path,config)
                for row in load_yaml(report_path)['cases']:
                    path=root/row['witnessRef'];witness=load_yaml(path)
                    for request in witness['requests']:
                        if request['etag']:request['etag']='"opaque-new"' if row['case']=='updated' else '"opaque-old"'
                        if row['case']=='if_match':request['ifRange']='"opaque-old"'
                    write_yaml(path,witness)
                self.assertEqual(validate(data),[])
                # Different source versions may reuse a key; immutable cache objects may be observed at later stages.
                current=load_yaml(report_path);row=next(r for r in current['cases'] if r['case']=='updated');path=root/row['witnessRef'];witness=load_yaml(path)
                for request in witness['requests']:request['cacheKey']='synthetic-cache-'+config['configuration']['rangeMatrixPolicy']['authorizedUsers'][1]
                write_yaml(path,witness);lifecycle_path=root/current['cacheLifecycleRef'];lifecycle=load_yaml(lifecycle_path);lifecycle['stages'][3]['objects']=copy.deepcopy(lifecycle['stages'][1]['objects']);write_yaml(lifecycle_path,lifecycle);self.assertEqual(validate(data),[])
            finally:temp.cleanup()
            for status in ('fail','inconclusive'):
                temp,root=self.temp_repo()
                try:
                    self.make_profile_slot(root,'POC-003',profile,status);self.assertEqual(CHECK.validate_repository(root,profile,False,selected_pocs={'POC-03'}),[])
                finally:temp.cleanup()

    def test_172_ai_results_bind_quality_retrieval_usage_and_policy_dispatch(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-009',profile);result=load_yaml(root/load_yaml(index)['resultRef']);record=load_yaml(root/result['executionRef']);env=record['environmentCaptured'];report_path=root/env['aiResultsRef'];report=load_yaml(report_path);config_path=root/report['configurationRef'];evaluation_path=root/report['evaluationRef'];usage_path=root/report['usageRef'];dispatch_path=root/report['dispatchRef'];prefix=Path(result['executionRef']).parent.as_posix();plan=load_yaml(self.plan_path(root,'POC-009'));defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];window=tuple(CHECK.utc(env['executionWindow'][key]) for key in ('startedAt','finishedAt'))
                originals={root/a['ref']:(root/a['ref']).read_bytes() for a in env['rawExecutionArtifacts']};originals[config_path]=config_path.read_bytes();original=copy.deepcopy(record)
                def validate(data):
                    errors=[];CHECK.validate_qualified_ai_results(root,plan,data,prefix,'pass',window,defs,errors,{});return errors
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-09'}),[]);self.assertEqual(validate(record),[])
                numeric=CHECK.AI_EVALUATED_METRICS|{'retrieval_recall','retrieval_mrr','retrieval_ndcg','query_latency','cost_estimate','provider_budget_limit','provider_request_rate_limit','provider_concurrency_limit'}
                for metric in sorted(numeric):
                    data=copy.deepcopy(original);next(m for m in data['measurements'] if m['id']==metric)['actual']+=.125;self.assertTrue(validate(data),(profile,metric))
                for mode in ('missing','arbitrary','oversize','bad_policy','wrong_config','wrong_subject','wrong_input','wrong_benchmark','missing_metric','duplicate_evaluation','wrong_output','wrong_rubric','wrong_method','wrong_method_mode','missing_stratum','coverage_count','score_nan','denominator_zero','duplicate_usage','missing_usage','output_alias','output_hash','token_usage','pricing_version','currency','wrong_query','unknown_rank','duplicate_rank','ranked_output','query_latency_time','query_set','corpus','no_warmup','late_warmup','missing_policy_case','duplicate_policy_case','permission_caller','acl_version','budget_not_exceeded','rate_not_exceeded','concurrency_not_exceeded','denied_dispatch_ids','denied_outbound_bytes','authorized_arbitrary_outbound','budget_period','review_binding','claimed_gate'):
                    for p,raw in originals.items():p.write_bytes(raw)
                    data=copy.deepcopy(original);env=data['environmentCaptured'];report=load_yaml(report_path);config=load_yaml(config_path);policy=config['configuration']['aiEvaluationPolicy'];evaluation=load_yaml(evaluation_path);usage=load_yaml(usage_path);dispatch=load_yaml(dispatch_path)
                    selected_case='acl_revoked' if mode=='acl_version' else 'budget_exhausted' if mode=='budget_not_exceeded' else 'request_rate_exceeded' if mode=='rate_not_exceeded' else 'concurrency_exceeded' if mode=='concurrency_not_exceeded' else 'authorized' if mode=='authorized_arbitrary_outbound' else 'permission_denied';outcome=next(o for o in dispatch['outcomes'] if o['case']==selected_case)
                    if mode=='missing':env.pop('aiResultsRef')
                    elif mode=='arbitrary':report_path.write_text('Unrelated assertions of quality and quota success\n',encoding='utf8')
                    elif mode=='oversize':report_path.write_text('x'*262145,encoding='utf8')
                    elif mode=='bad_policy':config['configuration']['aiEvaluationPolicy']=True
                    elif mode=='wrong_config':report['configurationRef']=env['acceptanceProfileConfigurationRef']
                    elif mode=='wrong_subject':report['subjectVersion']='another-model-prompt-parameter-runtime'
                    elif mode=='wrong_input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                    elif mode=='wrong_benchmark':report['benchmarkId']='another-benchmark'
                    elif mode=='missing_metric':evaluation['evaluations'].pop()
                    elif mode=='duplicate_evaluation':evaluation['evaluations'][-1]=copy.deepcopy(evaluation['evaluations'][0])
                    elif mode=='wrong_output':evaluation['evaluations'][0]['outputRef']=usage['items'][1]['outputRef']
                    elif mode=='wrong_rubric':evaluation['evaluations'][0]['rubricVersion']='unapproved-rubric'
                    elif mode=='wrong_method':evaluation['evaluations'][0]['evaluatorBuild']='other-evaluator'
                    elif mode=='wrong_method_mode':policy['evaluationMethods'][0]['mode']='tool_score'
                    elif mode=='missing_stratum':evaluation['evaluations'][0]['stratumId']='unapproved-stratum'
                    elif mode=='coverage_count':policy['strata'][0]['minimumSamples']=2
                    elif mode=='score_nan':next(r for r in evaluation['evaluations'] if r['metricId']=='quality_score')['score']=float('nan')
                    elif mode=='denominator_zero':next(r for r in evaluation['evaluations'] if r['metricId']=='asr_wer')['denominator']=0
                    elif mode=='duplicate_usage':usage['items'][-1]=copy.deepcopy(usage['items'][0])
                    elif mode=='missing_usage':usage['items'].pop()
                    elif mode=='output_alias':usage['items'][1].update(outputRef=usage['items'][0]['outputRef'],outputSha256=usage['items'][0]['outputSha256'])
                    elif mode=='output_hash':usage['items'][0]['outputSha256']='sha256:'+'0'*64
                    elif mode=='token_usage':usage['items'][0]['inputTokens']=2
                    elif mode=='pricing_version':usage['pricingVersion']='other-price-version'
                    elif mode=='currency':usage['currency']='other-currency'
                    elif mode=='wrong_query':evaluation['queries'][0]['queryId']='unapproved-query'
                    elif mode=='unknown_rank':evaluation['queries'][0]['retrievedIds']=['unapproved-document']
                    elif mode=='duplicate_rank':evaluation['queries'][0]['retrievedIds']*=2
                    elif mode=='ranked_output':
                        row=evaluation['queries'][0];path=root/row['outputRef'];captured=load_yaml(path);captured['retrievedIds']=[];write_yaml(path,captured);row['outputSha256']='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
                    elif mode=='query_latency_time':evaluation['queries'][0]['finishedAt']='2026-09-03T00:02:00.002Z'
                    elif mode=='query_set':evaluation['queries'][0]['querySetId']='other-query-set'
                    elif mode=='corpus':evaluation['queries'][0]['corpusId']='other-corpus'
                    elif mode=='no_warmup':evaluation['warmupQueries']=[]
                    elif mode=='late_warmup':evaluation['warmupQueries'][0]['finishedAt']='2026-09-03T00:04:00Z'
                    elif mode=='missing_policy_case':dispatch['outcomes'].pop()
                    elif mode=='duplicate_policy_case':dispatch['outcomes'][-1]=copy.deepcopy(dispatch['outcomes'][0])
                    elif mode=='permission_caller':outcome['callerId']=policy['gatePolicy']['authorizedCallerId']
                    elif mode=='acl_version':outcome['aclVersion']=policy['gatePolicy']['currentAclVersion']
                    elif mode=='budget_not_exceeded':outcome['budgetRemaining']=1
                    elif mode=='rate_not_exceeded':outcome['requestCount']=1
                    elif mode=='concurrency_not_exceeded':outcome['concurrentCalls']=1
                    elif mode=='denied_dispatch_ids':outcome['providerRequestIds']=['leaked-provider-request']
                    elif mode in ('denied_outbound_bytes','authorized_arbitrary_outbound'):
                        path=root/outcome['outboundRef'];path.write_text('Unexpected provider request bytes\n',encoding='utf8');outcome['outboundSha256']='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
                    elif mode=='budget_period':outcome['budgetPeriodId']='other-budget-period'
                    elif mode=='review_binding':report['privacyReviewRef']=report['licenseReviewRef']
                    else:next(m for m in data['measurements'] if m['id']=='hard_budget_gate')['actual']=False
                    if mode not in ('arbitrary','oversize'):write_yaml(report_path,report)
                    write_yaml(config_path,config);write_yaml(evaluation_path,evaluation);write_yaml(usage_path,usage);write_yaml(dispatch_path,dispatch);self.assertTrue(validate(data),(profile,mode))
                # Error rates may exceed one and COMET may be negative when the retained evaluator actually observed them.
                for p,raw in originals.items():p.write_bytes(raw)
                data=copy.deepcopy(original);evaluation=load_yaml(evaluation_path)
                for metric,value,numerator,denominator in (('asr_wer',2,2,1),('asr_cer',2,2,1),('speaker_der',1.2,12,10),('translation_comet',-.3,1,1)):
                    row=next(r for r in evaluation['evaluations'] if r['metricId']==metric);row.update(numerator=numerator,denominator=denominator,score=value);next(m for m in data['measurements'] if m['id']==metric)['actual']=value
                write_yaml(evaluation_path,evaluation);self.refresh_qualified_observation_fixture(root,data);path=root/result['executionRef'];write_yaml(path,data);self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-09'}),[])
            finally:temp.cleanup()
            for status in ('fail','inconclusive'):
                temp,root=self.temp_repo()
                try:
                    self.make_profile_slot(root,'POC-009',profile,status);self.assertEqual(CHECK.validate_repository(root,profile,False,selected_pocs={'POC-09'}),[])
                finally:temp.cleanup()

    def test_173_recovery_resource_non_objects_return_contract_errors(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-010',profile)
                path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef']
                original=load_yaml(path)
                validate=lambda:CHECK.validate_repository(root,profile,True,selected_pocs={'POC-10'})
                self.assertEqual(validate(),[])
                for value in (None,True,42,'invalid-resource',[]):
                    data=copy.deepcopy(original);data['resources'].append(value);write_yaml(path,data)
                    errors=validate()
                    self.assertTrue(errors,(profile,value))
                    self.assertTrue(any('schema' in error for error in errors),(profile,value,errors))
            finally:temp.cleanup()

    def test_174_ai_data_policy_requires_prior_allow_and_zero_dispatch_denial(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-009',profile)
                path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path)
                report_path=root/original['environmentCaptured']['aiDataPolicyRef'];report_original=load_yaml(report_path)
                config_path=root/report_original['configurationRef'];config_original=load_yaml(config_path)
                denied_path=root/report_original['outcomes'][1]['outboundRef'];saved_denial=denied_path.read_bytes()
                def validate(data):
                    self.refresh_qualified_observation_fixture(root,data);write_yaml(path,data)
                    return CHECK.validate_repository(root,profile,True,selected_pocs={'POC-09'})
                self.assertEqual(validate(copy.deepcopy(original)),[])
                for mode in ('missing','arbitrary','bad_policy','policy_version','wrong_subject','wrong_privacy','wrong_input','missing_case','duplicate_case','allowed_purpose_for_denial','unapproved_payload','wrong_asset_version','wrong_provider_mode','policy_input_mismatch','late_allow','invalid_time','denied_dispatch','denied_bytes','allow_wrong_dispatch'):
                    data=copy.deepcopy(original);report=copy.deepcopy(report_original);config=copy.deepcopy(config_original);denied_path.write_bytes(saved_denial)
                    allow,deny=report['outcomes']
                    if mode=='missing':data['environmentCaptured'].pop('aiDataPolicyRef')
                    elif mode=='arbitrary':report=None
                    elif mode=='bad_policy':config['configuration']['aiDataPolicy']=True
                    elif mode=='policy_version':deny['policyVersion']='unapproved-policy-version'
                    elif mode=='wrong_subject':config['configuration']['aiDataPolicy']['subjectVersion']='other-provider-model'
                    elif mode=='wrong_privacy':report['privacyReviewRef']='unapproved-privacy-review'
                    elif mode=='wrong_input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                    elif mode=='missing_case':report['outcomes'].pop()
                    elif mode=='duplicate_case':report['outcomes'][1]=copy.deepcopy(allow)
                    elif mode=='allowed_purpose_for_denial':deny['purpose']=config['configuration']['aiDataPolicy']['allowedPurpose']
                    elif mode=='unapproved_payload':config['configuration']['aiDataPolicy']['allowedPayloadScope']=['another-input-version']
                    elif mode=='wrong_asset_version':report['assetVersion']='other-asset-version'
                    elif mode=='wrong_provider_mode':report['providerMode']='private_local'
                    elif mode=='policy_input_mismatch':config['configuration']['aiDataPolicy']['inputSamples'][0]['checksum']='sha256:'+'0'*64
                    elif mode=='late_allow':allow['evaluatedAt']='2026-09-03T00:03:01Z'
                    elif mode=='invalid_time':deny['evaluatedAt']='not-a-date'
                    elif mode=='denied_dispatch':deny.update(dispatchedAt=allow['dispatchedAt'],providerRequestIds=['unexpected-provider-request'])
                    elif mode=='denied_bytes':
                        denied_path.write_bytes(b'Protected bytes dispatched despite data denial');deny['outboundSha256']='sha256:'+hashlib.sha256(denied_path.read_bytes()).hexdigest()
                    else:allow.update(outboundRef=deny['outboundRef'],outboundSha256=deny['outboundSha256'])
                    if report is None:report_path.write_text('Unrelated data-policy assertions\n',encoding='utf8')
                    else:write_yaml(report_path,report)
                    write_yaml(config_path,config)
                    self.assertTrue(any('qualified AI data policy' in error for error in validate(data)),(profile,mode))
            finally:temp.cleanup()

    def test_175_production_firmware_binds_approved_group_settings_and_runtime(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-001','production')
            path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path)
            report_path=root/original['environmentCaptured']['productionFirmwareRef'];report_original=load_yaml(report_path)
            config_path=root/report_original['configurationRef'];config_original=load_yaml(config_path)
            def validate(data):
                self.refresh_qualified_observation_fixture(root,data);write_yaml(path,data)
                return CHECK.validate_repository(root,'production',True,selected_pocs={'POC-01'})
            # The approved GPU and audio functions may legitimately share a group.
            self.assertEqual(len(report_original['iommuMembers']),2)
            self.assertEqual(validate(copy.deepcopy(original)),[])
            modes=('missing','arbitrary','bad_policy','wrong_config','wrong_identity','wrong_firmware','wrong_bios','wrong_group','iommu_off','above4g_off','bar_off','required_host_device','unassigned_member','foreign_member','duplicate_member','missing_gpu','wrong_allocation','no_allocation','zero_address_space','guest_missing_gpu','runtime_failed','invalid_time','settings_after_guest','outside_window','claimed_gate')
            for mode in modes:
                data=copy.deepcopy(original);report=copy.deepcopy(report_original);config=copy.deepcopy(config_original)
                if mode=='missing':data['environmentCaptured'].pop('productionFirmwareRef')
                elif mode=='arbitrary':report=None
                elif mode=='bad_policy':config['configuration']['passthroughFirmwarePolicy']=True
                elif mode=='wrong_config':report['configurationRef']=data['environmentCaptured']['acceptanceProfileConfigurationRef']
                elif mode=='wrong_identity':report['identity']['gpuDeviceId']='another-device'
                elif mode=='wrong_firmware':report['firmwareBuild']='unapproved-firmware'
                elif mode=='wrong_bios':report['biosConfigurationId']='unapproved-bios-config'
                elif mode=='wrong_group':report['iommuGroupId']='other-iommu-group'
                elif mode=='iommu_off':report['iommuEnabled']=False
                elif mode=='above4g_off':report['above4gEnabled']=False
                elif mode=='bar_off':report['resizableBarEnabled']=False
                elif mode=='required_host_device':report['iommuMembers'][1]['requiredHostDevice']=True
                elif mode=='unassigned_member':report['iommuMembers'][1]['assignedToGuest']=False
                elif mode=='foreign_member':report['iommuMembers'].append(dict(deviceId='unrelated-host-controller',requiredHostDevice=False,assignedToGuest=True))
                elif mode=='duplicate_member':report['iommuMembers'].append(copy.deepcopy(report['iommuMembers'][0]))
                elif mode=='missing_gpu':report['iommuMembers'].pop(0)
                elif mode=='wrong_allocation':report['allocatedDeviceId']='another-device'
                elif mode=='no_allocation':report['allocationSucceeded']=False
                elif mode=='zero_address_space':report['addressSpaceAllocatedBytes']=0
                elif mode=='guest_missing_gpu':report['enumeratedDeviceIds']=report['enumeratedDeviceIds'][1:]
                elif mode=='runtime_failed':report['runtimeReady']=False
                elif mode=='invalid_time':report['settingsCapturedAt']='not-a-date'
                elif mode=='settings_after_guest':report['settingsCapturedAt']='2026-09-03T00:00:03Z'
                elif mode=='outside_window':report['runtimeInitializedAt']='2026-09-06T00:00:00Z'
                else:next(m for m in data['measurements'] if m['id']=='iommu_group_isolation_verified')['actual']=False
                if report is None:report_path.write_text('Unrelated firmware assertions\n',encoding='utf8')
                else:write_yaml(report_path,report)
                write_yaml(config_path,config)
                self.assertTrue(any('qualified production passthrough firmware' in error for error in validate(data)),mode)
        finally:temp.cleanup()
        for profile,status in (('local-v1','pass'),('production','fail'),('production','inconclusive')):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-001',profile,status=status)
                record=load_yaml(root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'])
                self.assertNotIn('productionFirmwareRef',record['environmentCaptured'])
                self.assertEqual(CHECK.validate_repository(root,profile,status=='pass',selected_pocs={'POC-01'}),[])
            finally:temp.cleanup()

    def test_176_media_quality_and_first_playable_latency_bind_retained_observations(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-002',profile);path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path)
                report_path=root/original['environmentCaptured']['mediaQualityTimingRef'];report_original=load_yaml(report_path)
                quality_path=root/report_original['qualityRef'];quality_original=load_yaml(quality_path)
                job_path=root/report_original['jobEventRef'];job_original=load_yaml(job_path)
                probe_path=root/report_original['firstSegment']['decodeRef'];probe_original=load_yaml(probe_path)
                config_path=root/report_original['configurationRef'];config_original=load_yaml(config_path)
                def validate(data):
                    self.refresh_qualified_observation_fixture(root,data);write_yaml(path,data)
                    return CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'})
                self.assertEqual(validate(copy.deepcopy(original)),[])
                modes=('missing','arbitrary','bad_policy','wrong_config','input_sha','output_sha','parameters','build','model','model_sha','evaluator_build','frames','score_claim','score_nan','latency_claim','quality_before_encode','quality_outside','missing_command','command_type','job_id','run_ref','node_id','job_start','produced_after_ready','invalid_time','segment_hash','probe_hash','probe_frames','probe_errors','not_decodable','probe_input','decoder_build','nonzero_start','unbounded_span','bad_run_end','missing_job_event','job_event_identity','job_event_input','job_event_time','late_job_event')
                for mode in modes:
                    data=copy.deepcopy(original);report=copy.deepcopy(report_original);quality=copy.deepcopy(quality_original);probe=copy.deepcopy(probe_original);config=copy.deepcopy(config_original);job=copy.deepcopy(job_original);segment=report['firstSegment']
                    if mode=='missing':data['environmentCaptured'].pop('mediaQualityTimingRef')
                    elif mode=='arbitrary':quality=None
                    elif mode=='bad_policy':config['configuration']['mediaEvaluationPolicy']=True
                    elif mode=='wrong_config':report['configurationRef']=data['environmentCaptured']['acceptanceProfileConfigurationRef']
                    elif mode=='input_sha':quality['inputSha256']='sha256:'+'0'*64
                    elif mode=='output_sha':quality['outputSha256']='sha256:'+'0'*64
                    elif mode=='parameters':quality['encoderParameters']={'unapproved':'parameters'}
                    elif mode=='build':quality['encoderBuild']='other-encoder'
                    elif mode=='model':quality['modelId']='other-model'
                    elif mode=='model_sha':quality['modelSha256']='sha256:'+'0'*64
                    elif mode=='evaluator_build':quality['evaluatorBuild']='unapproved-evaluator'
                    elif mode=='frames':quality['evaluatedFrameCount']-=1
                    elif mode=='score_claim':next(m for m in data['measurements'] if m['id']=='av1_quality')['actual']+=.2
                    elif mode=='score_nan':quality['vmafMean']=float('nan')
                    elif mode=='latency_claim':next(m for m in data['measurements'] if m['id']=='first_segment_latency')['actual']+=1
                    elif mode=='quality_before_encode':quality['evaluatedAt']='2026-09-03T00:00:00Z'
                    elif mode=='quality_outside':quality['evaluatedAt']='2026-09-06T00:00:00Z'
                    elif mode=='missing_command':quality['evaluatorCommandRef']='missing-command-ref'
                    elif mode=='command_type':next(a for a in data['environmentCaptured']['rawExecutionArtifacts'] if a['ref']==quality['evaluatorCommandRef'])['artifactType']='measurement_output'
                    elif mode=='job_id':probe['jobId']='other-job'
                    elif mode=='run_ref':segment['encodeRunRef']='another-run-ref'
                    elif mode=='node_id':segment['nodeId']='another-node'
                    elif mode=='job_start':segment['jobStartedAt']='2026-09-03T00:00:00.0001Z'
                    elif mode=='produced_after_ready':segment['segmentProducedAt']='2026-09-03T00:00:01Z'
                    elif mode=='invalid_time':segment['firstPlayableAt']='not-a-date'
                    elif mode=='segment_hash':segment['segmentSha256']='sha256:'+'0'*64
                    elif mode=='probe_hash':probe['segmentSha256']='sha256:'+'0'*64
                    elif mode=='probe_frames':probe['decodedFrameCount']+=1
                    elif mode=='probe_errors':probe['decodeErrorCount']=1
                    elif mode=='not_decodable':probe['decodable']=False
                    elif mode=='probe_input':probe['inputSha256']='sha256:'+'0'*64
                    elif mode=='decoder_build':probe['decoderBuild']='other-decoder'
                    elif mode=='nonzero_start':segment['sourceStartFrame']=1
                    elif mode=='unbounded_span':segment['sourceEndFrame']=121
                    elif mode=='bad_run_end':data['environmentCaptured']['workerEncodeExecutions'][0]['sourceEndFrame']='invalid-span-end'
                    elif mode=='missing_job_event':report['jobEventRef']='missing-job-event'
                    elif mode=='job_event_identity':job['jobId']='another-job'
                    elif mode=='job_event_input':job['inputSha256']='sha256:'+'0'*64
                    elif mode=='job_event_time':job['jobStartedAt']='2026-09-03T00:00:00.0001Z'
                    else:job['jobStartedAt']=segment['jobStartedAt']='2026-09-03T00:00:00.002Z'
                    if quality is None:quality_path.write_text('Unrelated quality assertions\n',encoding='utf8')
                    else:write_yaml(quality_path,quality)
                    write_yaml(report_path,report);write_yaml(probe_path,probe);write_yaml(config_path,config);write_yaml(job_path,job)
                    self.assertTrue(any('qualified media quality/timing' in error for error in validate(data)),(profile,mode))
                # The platform job starts 50 ms before its selected worker: all 51 ms count.
                data=copy.deepcopy(original);report=copy.deepcopy(report_original);probe=copy.deepcopy(probe_original);job=copy.deepcopy(job_original)
                job_start='2026-09-02T23:59:59.950Z';worker_start='2026-09-03T00:00:00Z';ready='2026-09-03T00:00:00.001Z'
                data['environmentCaptured']['executionWindow']['startedAt']=job_start
                job['jobStartedAt']=report['firstSegment']['jobStartedAt']=job_start
                sample_approval_path=root/data['samples'][0]['approvalRef'];sample_approval_raw=sample_approval_path.read_bytes()
                sample_approval=load_yaml(sample_approval_path);sample_approval['approvedAt']='2026-09-02T23:59:59.949Z';write_yaml(sample_approval_path,sample_approval)
                data['environmentCaptured']['workerEncodeExecutions'][0]['startedAt']=worker_start
                job['workerStartedAt']=worker_start;report['firstSegment'].update(segmentProducedAt=ready,firstPlayableAt=ready);probe['observedAt']=ready
                next(m for m in data['measurements'] if m['id']=='first_segment_latency')['actual']=51
                write_yaml(config_path,config_original);write_yaml(quality_path,quality_original);write_yaml(report_path,report);write_yaml(probe_path,probe);write_yaml(job_path,job)
                self.assertEqual(validate(data),[],profile)
                next(m for m in data['measurements'] if m['id']=='first_segment_latency')['actual']=1
                self.assertTrue(any('first_segment_latency must derive' in error for error in validate(data)),profile)
                sample_approval_path.write_bytes(sample_approval_raw)
            finally:temp.cleanup()
        for status in ('fail','inconclusive'):
            temp,root=self.temp_repo()
            try:
                self.make_profile_slot(root,'POC-002','local-v1',status)
                self.assertEqual(CHECK.validate_repository(root,'local-v1',False,selected_pocs={'POC-02'}),[])
            finally:temp.cleanup()

    def test_177_local_source_faults_bind_retry_checkpoint_and_logical_state(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-006','local-v1');path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path)
            report_path=root/original['environmentCaptured']['sourceFaultOutcomeRef'];report_original=load_yaml(report_path)
            config_path=root/report_original['configurationRef'];config_original=load_yaml(config_path)
            def validate(data):
                self.refresh_qualified_observation_fixture(root,data);write_yaml(path,data)
                return CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-06'})
            self.assertEqual(validate(copy.deepcopy(original)),[])
            modes=('missing','arbitrary','bad_policy','wrong_config','wrong_versions','wrong_input','wrong_sandbox','foreign_scope','missing_case','duplicate_case','wrong_case_id','wrong_matrix_ref','response_class','auth_isolation','retry_guidance','backoff_timing','backoff_limit','attempt_budget','duplicate_request','wrong_key','checkpoint_mismatch','no_checkpoint','foreign_object','duplicate_asset','duplicate_create','expired_result','expired_mutation','deleted_asset','deletion_not_observed','asset_version','claimed_gate')
            for mode in modes:
                data=copy.deepcopy(original);report=copy.deepcopy(report_original);config=copy.deepcopy(config_original)
                rows={row['case']:row for row in report['cases']};rate=rows['http_429'];interrupted=rows['interrupted_sync'];expired=rows['auth_expired'];deleted=rows['source_delete']
                if mode=='missing':data['environmentCaptured'].pop('sourceFaultOutcomeRef')
                elif mode=='arbitrary':report=None
                elif mode=='bad_policy':config['configuration']['localSourceFaultPolicy']=True
                elif mode=='wrong_config':report['configurationRef']=data['environmentCaptured']['acceptanceProfileConfigurationRef']
                elif mode=='wrong_versions':report['subjectVersion']='another-service-api-version'
                elif mode=='wrong_input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                elif mode=='wrong_sandbox':report['sandboxId']='unapproved-sandbox'
                elif mode=='foreign_scope':report['scope']='BAIDU_PRODUCTION'
                elif mode=='missing_case':report['cases'].pop()
                elif mode=='duplicate_case':report['cases'][-1]=copy.deepcopy(report['cases'][0])
                elif mode=='wrong_case_id':rate['caseId']='another-exercised-case'
                elif mode=='wrong_matrix_ref':data['environmentCaptured']['injected_failure_matrix']['cases'][0]['rawOutputRef']=data['rawOutputRefs'][0]
                elif mode=='response_class':rate['attempts'][0]['httpStatus']=200
                elif mode=='auth_isolation':rate['attempts'][0]['authorization']='expired'
                elif mode=='retry_guidance':rate['attempts'][0]['retryAfterSeconds']=2
                elif mode=='backoff_timing':rate['attempts'][0]['backoffAfterSeconds']=.5
                elif mode=='backoff_limit':config['configuration']['localSourceFaultPolicy']['maxBackoffSeconds']=.5
                elif mode=='attempt_budget':config['configuration']['localSourceFaultPolicy']['maxAttempts']=1
                elif mode=='duplicate_request':rate['attempts'][1]['requestId']=rate['attempts'][0]['requestId']
                elif mode=='wrong_key':rate['attempts'][1]['idempotencyKey']='another-sync-key'
                elif mode=='checkpoint_mismatch':interrupted['attempts'][1]['checkpointBefore']='other-checkpoint'
                elif mode=='no_checkpoint':
                    interrupted['attempts'][0]['checkpointAfter']=None;interrupted['attempts'][1]['checkpointBefore']=None
                elif mode=='foreign_object':rate['after']['sourceObjects'][0]['objectId']='another-source-object'
                elif mode=='duplicate_asset':rate['after']['assets'].append(copy.deepcopy(rate['after']['assets'][0]))
                elif mode=='duplicate_create':rate['attempts'][1]['createdAssetIds']=[config['configuration']['localSourceFaultPolicy']['assetId']]*2
                elif mode=='expired_result':expired['attempts'][0]['returnedAssetIds']=[config['configuration']['localSourceFaultPolicy']['assetId']]
                elif mode=='expired_mutation':expired['after']['assets']=[]
                elif mode=='deleted_asset':deleted['after']['assets']=[]
                elif mode=='deletion_not_observed':deleted['after']['sourceObjects'][0]['availability']='available'
                elif mode=='asset_version':rate['after']['assets'][0]['versionId']='another-logical-version'
                else:next(m for m in data['measurements'] if m['id']=='duplicate_objects_prevented')['actual']=False
                if report is None:report_path.write_text('Unrelated fault success assertions\n',encoding='utf8')
                else:write_yaml(report_path,report)
                write_yaml(config_path,config)
                self.assertTrue(any('qualified local source faults' in error for error in validate(data)),mode)
            # Network loss may terminate safely, immediately or after bounded retries.
            def explicit_network_failure(count,empty=False):
                report=copy.deepcopy(report_original);row=next(r for r in report['cases'] if r['case']=='network_disconnect')
                row['outcome']='explicit_failure';row['recoveryMode']='none';row['attempts']=row['attempts'][:count]
                if empty:row['before']=dict(assets=[],sourceObjects=[],links=[]);row['after']=copy.deepcopy(row['before'])
                for i,attempt in enumerate(row['attempts']):
                    attempt.update(classification='network_disconnect',transport='network_disconnect',httpStatus=None,returnedAssetIds=[],createdAssetIds=[],completedObjectIds=[],checkpointBefore='retained-network-cursor',checkpointAfter='retained-network-cursor',backoffAfterSeconds=1 if i+1<count else 0)
                return report
            for count,empty in ((1,False),(2,False),(1,True)):
                write_yaml(report_path,explicit_network_failure(count,empty));write_yaml(config_path,config_original)
                self.assertEqual(validate(copy.deepcopy(original)),[])
            for mode in ('result','create','progress','logical_mutation','promotion','checkpoint_change','checkpoint_gap','classification','timing','backoff','budget','idempotency'):
                report=explicit_network_failure(2);row=next(r for r in report['cases'] if r['case']=='network_disconnect');attempt=row['attempts'][-1];config=copy.deepcopy(config_original);policy=config['configuration']['localSourceFaultPolicy']
                if mode=='result':attempt['returnedAssetIds']=[policy['assetId']]
                elif mode=='create':attempt['createdAssetIds']=[policy['assetId']]
                elif mode=='progress':attempt['completedObjectIds']=[policy['objectId']]
                elif mode=='logical_mutation':row['after']['assets']=[]
                elif mode=='promotion':row['before']=dict(assets=[],sourceObjects=[],links=[])
                elif mode=='checkpoint_change':attempt['checkpointAfter']='corrupt-cursor'
                elif mode=='checkpoint_gap':attempt.update(checkpointBefore='lost-cursor',checkpointAfter='lost-cursor')
                elif mode=='classification':attempt.update(classification='success',transport='http_response',httpStatus=200)
                elif mode=='timing':attempt['requestedAt']=row['attempts'][0]['requestedAt']
                elif mode=='backoff':policy['maxBackoffSeconds']=.5
                elif mode=='budget':policy['maxAttempts']=1
                else:attempt['idempotencyKey']='unapproved-key'
                write_yaml(report_path,report);write_yaml(config_path,config)
                self.assertTrue(any('qualified local source faults' in error for error in validate(copy.deepcopy(original))),mode)
            # Both checkpoint resume and an explicitly reset idempotent rerun are legal.
            report=copy.deepcopy(report_original);row=next(row for row in report['cases'] if row['case']=='interrupted_sync');row['recoveryMode']='idempotent_rerun';row['attempts'][1]['checkpointBefore']=None
            write_yaml(report_path,report);write_yaml(config_path,config_original);self.assertEqual(validate(copy.deepcopy(original)),[])
            # First synchronization may create one asset; repeated recovery may not create two.
            report=copy.deepcopy(report_original);row=next(row for row in report['cases'] if row['case']=='http_429');row['before']=dict(assets=[],sourceObjects=[],links=[]);row['attempts'][1]['createdAssetIds']=[config_original['configuration']['localSourceFaultPolicy']['assetId']]
            write_yaml(report_path,report);self.assertEqual(validate(copy.deepcopy(original)),[])
        finally:temp.cleanup()
        for profile,status in (('local-v1','fail'),('local-v1','inconclusive'),('production','pass')):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-006',profile,status=status);record=load_yaml(root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'])
                self.assertNotIn('sourceFaultOutcomeRef',record['environmentCaptured'])
                errors=CHECK.validate_repository(root,profile,status=='pass',selected_pocs={'POC-06'})
                if profile=='production':self.assertEqual(errors,['deferred production qualification POC-06: production outcome validation is not implemented; PASS unavailable'])
                else:self.assertEqual(errors,[])
            finally:temp.cleanup()

    def test_178_worker_safety_requires_per_node_limits_restart_and_network_outcomes(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-001',profile);path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path);report_path=root/original['environmentCaptured']['workerSafetyRef'];report_original=load_yaml(report_path);config_path=root/report_original['configurationRef'];config_original=load_yaml(config_path)
                def validate(data):
                    self.refresh_qualified_observation_fixture(root,data);write_yaml(path,data)
                    return CHECK.validate_repository(root,profile,True,selected_pocs={'POC-01'})
                self.assertEqual(validate(copy.deepcopy(original)),[])
                # Active leases may have been issued before the experiment begins.
                report=copy.deepcopy(report_original)
                for row in report['nodes']:row['restart']['oldLeaseIssuedAt']='2026-09-02T23:59:59Z'
                write_yaml(report_path,report);self.assertEqual(validate(copy.deepcopy(original)),[])
                for mode,value in (('invalid_issue','invalid-utc'),('future_issue','2026-09-03T00:02:02Z'),('after_expiry_issue','2026-09-03T00:02:03Z')):
                    report=copy.deepcopy(report_original);report['nodes'][0]['restart']['oldLeaseIssuedAt']=value
                    write_yaml(report_path,report);self.assertTrue(any('qualified worker safety' in e for e in validate(copy.deepcopy(original))),(profile,mode))
                for mode in ('missing','arbitrary','policy','profile','input','subject','config','missing_node','duplicate_node','host','limit_case','not_exceeded','multiple_exceeded','termination','cleanup','publication','limit_clock','lease_expiry','registration','same_lease','stale_completion','duplicate_completion','stale_publication','recovery_bound','missing_denial','target','grant','decision','network_bytes','network_hash','network_node','expired_time','request_id','gate'):
                    data=copy.deepcopy(original);report=copy.deepcopy(report_original);config=copy.deepcopy(config_original);row=report['nodes'][0];limit=row['limitCases'][0];restart=row['restart'];network=row['networkCases'][1];policy=config['configuration']['workerSafetyPolicy']
                    if mode=='missing':data['environmentCaptured'].pop('workerSafetyRef')
                    elif mode=='arbitrary':report=None
                    elif mode=='policy':config['configuration']['workerSafetyPolicy']=True
                    elif mode=='profile':report['acceptanceProfile']=CHECK.profile_identity('production' if profile=='local-v1' else 'local-v1')
                    elif mode=='input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                    elif mode=='subject':report['subjectVersion']='foreign-worker-build'
                    elif mode=='config':report['configurationRef']=data['environmentCaptured']['acceptanceProfileConfigurationRef']
                    elif mode=='missing_node':report['nodes']=[]
                    elif mode=='duplicate_node':report['nodes'].append(copy.deepcopy(row))
                    elif mode=='host':row['identity']['physicalHostId']='other-host'
                    elif mode=='limit_case':row['limitCases'].pop()
                    elif mode=='not_exceeded':limit['observed'][limit['case']]=policy['limits'][limit['case']]
                    elif mode=='multiple_exceeded':limit['observed']['memoryBytes']=101
                    elif mode=='termination':limit['terminationReason']='success'
                    elif mode=='cleanup':limit['remainingTemporaryBytes']=1
                    elif mode=='publication':limit['publishedArtifactIds']=['unsafe-artifact']
                    elif mode=='limit_clock':limit['finishedAt']=limit['startedAt']
                    elif mode=='lease_expiry':restart['expiredLeaseObservedAt']=restart['disconnectedAt']
                    elif mode=='registration':restart['newRegistrationId']=restart['oldRegistrationId']
                    elif mode=='same_lease':restart['newLeaseId']=restart['oldLeaseId']
                    elif mode=='stale_completion':restart['completionLeaseId']=restart['oldLeaseId']
                    elif mode=='duplicate_completion':restart['taskCompletionCount']=2
                    elif mode=='stale_publication':restart['staleLeasePublicationCount']=1
                    elif mode=='recovery_bound':policy['maximumRecoverySeconds']=1
                    elif mode=='missing_denial':row['networkCases'].pop()
                    elif mode=='target':network['requestURL']=policy['allowedTarget']
                    elif mode=='grant':network['grantId']='unapproved-grant'
                    elif mode=='decision':network['decision']='allowed'
                    elif mode=='network_bytes':network.update(outboundRef=row['networkCases'][0]['outboundRef'],outboundSha256=row['networkCases'][0]['outboundSha256'],outboundByteCount=row['networkCases'][0]['outboundByteCount'])
                    elif mode=='network_hash':network['outboundSha256']='sha256:'+'0'*64
                    elif mode=='network_node':next(a for a in data['environmentCaptured']['rawExecutionArtifacts'] if a['ref']==network['outboundRef'])['nodeId']='another-node'
                    elif mode=='expired_time':policy['expiredAt']='2026-09-03T00:04:00Z'
                    elif mode=='request_id':network['requestId']=limit['requestId']
                    else:next(m for m in data['measurements'] if m['id']=='worker_network_boundary_enforced')['actual']=False
                    if report is None:report_path.write_text('Unrelated worker safety success assertions\n',encoding='utf8')
                    else:write_yaml(report_path,report)
                    write_yaml(config_path,config)
                    self.assertTrue(any('qualified worker safety' in e for e in validate(data)),(profile,mode))
            finally:temp.cleanup()
        for profile in ('local-v1','production'):
            for status in ('fail','inconclusive'):
                temp,root=self.temp_repo()
                try:
                    index=self.make_profile_slot(root,'POC-001',profile,status=status);record=load_yaml(root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef']);self.assertNotIn('workerSafetyRef',record['environmentCaptured']);self.assertEqual(CHECK.validate_repository(root,profile,False,selected_pocs={'POC-01'}),[])
                finally:temp.cleanup()

    def test_179_worker_safety_returns_errors_for_unhashable_inventory_node_ids(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-001',profile);path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path)
                # Preserve a successful valid-node control alongside malformed cases.
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-01'}),[])
                for value in (['invalid-node-id'],{'invalid':'node-id'}):
                    data=copy.deepcopy(original);data['environmentCaptured']['worker_node_inventory'][0]['nodeId']=value;write_yaml(path,data)
                    errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-01'})
                    self.assertTrue(any('qualified worker safety' in error for error in errors),(profile,value))
            finally:temp.cleanup()

    def test_180_passthrough_recovery_requires_changed_boots_and_recovered_runtime(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-001','production');path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path);report_path=root/original['environmentCaptured']['passthroughTransitionRef'];report_original=load_yaml(report_path);probe_path=root/report_original['cases'][0]['after']['probeRef'];probe_original=load_yaml(probe_path)
            def validate(data):
                self.refresh_qualified_observation_fixture(root,data);write_yaml(path,data)
                return CHECK.validate_repository(root,'production',True,selected_pocs={'POC-01'})
            self.assertEqual(validate(copy.deepcopy(original)),[])
            for mode in ('missing','arbitrary','identity','config','duplicate_case','unchanged_guest','unchanged_host','unchanged_reset','lost_enumeration','lost_assignment','runtime','manual_rebuild','clock','probe_reused','probe_input','probe_identity','probe_boot','probe_clock','probe_errors','probe_output','probe_hash','probe_frames','chain','initial_host','gate'):
                data=copy.deepcopy(original);report=copy.deepcopy(report_original);probe=copy.deepcopy(probe_original);row=report['cases'][0]
                if mode=='missing':data['environmentCaptured'].pop('passthroughTransitionRef')
                elif mode=='arbitrary':report=None
                elif mode=='identity':report['identity']['driverBuild']='foreign-driver'
                elif mode=='config':report['configurationRef']=data['environmentCaptured']['acceptanceProfileConfigurationRef']
                elif mode=='duplicate_case':report['cases'][-1]['case']=row['case']
                elif mode=='unchanged_guest':row['after']['guestBootId']=row['before']['guestBootId']
                elif mode=='unchanged_host':report['cases'][1]['after']['hostBootId']=report['cases'][1]['before']['hostBootId']
                elif mode=='unchanged_reset':report['cases'][2]['after']['deviceGenerationId']=report['cases'][2]['before']['deviceGenerationId']
                elif mode=='lost_enumeration':row['after']['enumeratedDeviceIds']=['foreign-gpu']
                elif mode=='lost_assignment':row['after']['assignedDeviceIds']=['foreign-gpu']
                elif mode=='runtime':row['after']['runtimeReady']=False
                elif mode=='manual_rebuild':row['manualRebuildCount']=1
                elif mode=='clock':row['finishedAt']=row['startedAt']
                elif mode=='probe_reused':row['after']['probeRef']=row['before']['probeRef']
                elif mode=='probe_input':probe['inputSha256']='sha256:'+'0'*64
                elif mode=='probe_identity':probe['identity']['encoderBuild']='foreign-encoder'
                elif mode=='probe_boot':probe['guestBootId']='foreign-boot'
                elif mode=='probe_clock':probe['startedAt']=row['startedAt']
                elif mode=='probe_errors':probe['decodeErrorCount']=1
                elif mode=='probe_output':probe['outputRef']=original['environmentCaptured']['inputSampleArtifacts'][0]['inputArtifactRef']
                elif mode=='probe_hash':probe['outputSha256']='sha256:'+'0'*64
                elif mode=='probe_frames':probe['decodedFrameCount']=0
                elif mode=='chain':report['cases'][1]['before']['deviceGenerationId']='foreign-chain'
                elif mode=='initial_host':row['before']['hostBootId']='foreign-host-boot'
                else:next(m for m in data['measurements'] if m['id']=='vm_reboot_recovery')['actual']=False
                if report is None:report_path.write_text('Unrelated recovery success assertions\n',encoding='utf8')
                else:write_yaml(report_path,report)
                write_yaml(probe_path,probe);self.assertTrue(any('qualified passthrough transitions' in e for e in validate(data)),mode)
        finally:temp.cleanup()
        for profile,status in (('local-v1','pass'),('production','fail'),('production','inconclusive')):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-001',profile,status=status);record=load_yaml(root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef']);self.assertNotIn('passthroughTransitionRef',record['environmentCaptured']);self.assertEqual(CHECK.validate_repository(root,profile,status=='pass',selected_pocs={'POC-01'}),[])
            finally:temp.cleanup()

    def test_181_public_network_gates_require_bound_dns_tls_ipv6_and_route_outcomes(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-007','production');path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path);report_path=root/original['environmentCaptured']['publicNetworkRef'];report_original=load_yaml(report_path);config_path=root/report_original['configurationRef'];config_original=load_yaml(config_path)
            def validate(data):
                self.refresh_qualified_observation_fixture(root,data);write_yaml(path,data)
                return CHECK.validate_repository(root,'production',True,selected_pocs={'POC-07'})
            self.assertEqual(validate(copy.deepcopy(original)),[])
            # Coarse observation clocks and unavailable/stable serial metadata are legitimate.
            for mode in ('same_clock','same_serial','no_serial'):
                report=copy.deepcopy(report_original);control=report['controls'][0]
                if mode=='same_clock':
                    control['connectedAt']=control['tls']['startedAt']=control['tls']['finishedAt']=control['requestStartedAt']=control['requestFinishedAt']
                elif mode=='same_serial':report['dnsAfter']['recordSerial']=report['dnsBefore']['recordSerial']
                else:report['dnsBefore']['recordSerial']=report['dnsAfter']['recordSerial']=None
                write_yaml(report_path,report);self.assertEqual(validate(copy.deepcopy(original)),[])
            for mode in ('tls_reversed','request_reversed'):
                report=copy.deepcopy(report_original);control=report['controls'][0]
                if mode=='tls_reversed':control['tls']['finishedAt']='2026-09-03T00:00:00.640Z'
                else:control['requestStartedAt']='2026-09-03T00:00:01.001Z'
                write_yaml(report_path,report);self.assertTrue(any('qualified public network' in e for e in validate(copy.deepcopy(original))),mode)
            def add_point(report,data):
                point='synthetic-second-external-point';control=copy.deepcopy(report['controls'][0]);control.update(testPointId=point,requestId='synthetic-second-public-request');source=load_yaml(root/control['accessWitnessRef']);body_path=root/control['responseBodyRef']
                created_refs=[]
                def retain(name,payload,kind):
                    ref=report_path.parent.as_posix().removeprefix(root.as_posix()+'/')+'/'+name;path=root/ref
                    if isinstance(payload,bytes):path.write_bytes(payload)
                    else:write_yaml(path,payload)
                    raw=path.read_bytes();data['environmentCaptured']['rawExecutionArtifacts'].append(dict(ref=ref,artifactType=kind,byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));data['rawOutputRefs'].append(ref);created_refs.append(ref);return ref
                control['responseBodyRef']=retain('second-point-response.bin',body_path.read_bytes(),'produced_media');source.update(testPointId=point,requestId=control['requestId'],responseBodyRef=control['responseBodyRef']);control['accessWitnessRef']=retain('second-point-request.yaml',source,'measurement_output');report['controls'].append(control)
                for old in list(report['denials']):
                    row=copy.deepcopy(old);row.update(testPointId=point,requestId='second-point-'+row['case'],responseBodyRef=retain('second-point-'+row['case']+'.bin',(root/row['responseBodyRef']).read_bytes(),'produced_media'));report['denials'].append(row)
                subprocess.run(['git','-C',str(root),'add','--',*created_refs],check=True,capture_output=True)
                return point
            report=copy.deepcopy(report_original);data=copy.deepcopy(original);config=copy.deepcopy(config_original);point=add_point(report,data);config['configuration']['publicNetworkPolicy']['testPointIds'].append(point);write_yaml(config_path,config);write_yaml(report_path,report);self.assertEqual(validate(copy.deepcopy(data)),[])
            second_request_original=load_yaml(root/report['controls'][1]['accessWitnessRef'])
            for mode in ('reused_request','reused_body','wrong_point_request'):
                write_yaml(root/report['controls'][1]['accessWitnessRef'],second_request_original)
                damaged=copy.deepcopy(report);second=damaged['controls'][1]
                if mode=='reused_request':second['accessWitnessRef']=damaged['controls'][0]['accessWitnessRef']
                elif mode=='reused_body':
                    second['responseBodyRef']=damaged['controls'][0]['responseBodyRef'];witness=load_yaml(root/second['accessWitnessRef']);witness['responseBodyRef']=second['responseBodyRef'];write_yaml(root/second['accessWitnessRef'],witness)
                else:
                    witness=load_yaml(root/second['accessWitnessRef']);witness['requestId']='unrelated-recorded-request';write_yaml(root/second['accessWitnessRef'],witness)
                write_yaml(report_path,damaged);self.assertTrue(any('qualified public network' in e for e in validate(copy.deepcopy(data))),mode)
            write_yaml(config_path,config_original)
            for mode in ('missing','arbitrary','policy','config','profile','input','access_ref','ddns_name','same_mapping','old_dns','stale_dns','resolver','propagation','point','missing_control','address_family','address','port','route','proxy','origin','tls_chain','tls_hostname','tls_sni','tls_cipher','tls_protocol','tls_store','tls_leaf','tls_anchor','tls_clock','request_clock','witness_ref','response_hash','missing_denial','stale_time','bypass_origin','denial_target','denial_address','denial_bytes','duplicate_request','gate'):
                data=copy.deepcopy(original);report=copy.deepcopy(report_original);config=copy.deepcopy(config_original);policy=config['configuration']['publicNetworkPolicy'];control=report['controls'][0];tls=control['tls'];denial=report['denials'][-1]
                if mode=='missing':data['environmentCaptured'].pop('publicNetworkRef')
                elif mode=='arbitrary':report=None
                elif mode=='policy':config['configuration']['publicNetworkPolicy']=True
                elif mode=='config':report['configurationRef']=data['environmentCaptured']['acceptanceProfileConfigurationRef']
                elif mode=='profile':report['acceptanceProfile']=CHECK.profile_identity('local-v1')
                elif mode=='input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                elif mode=='access_ref':report['accessOutcomeRef']=data['rawOutputRefs'][0]
                elif mode=='ddns_name':report['dnsAfter']['name']='foreign-endpoint.invalid'
                elif mode=='same_mapping':policy['oldAddress']=policy['newAddress']
                elif mode=='old_dns':report['dnsBefore']['addresses']=[policy['newAddress']]
                elif mode=='stale_dns':report['dnsAfter']['addresses'].append(policy['oldAddress'])
                elif mode=='resolver':report['dnsAfter']['resolverBuild']='foreign-resolver'
                elif mode=='propagation':policy['maximumPropagationSeconds']=.1
                elif mode=='point':control['testPointId']='unapproved-test-point'
                elif mode=='missing_control':report['controls']=[]
                elif mode=='address_family':control['addressFamily']='IPv4'
                elif mode=='address':control['connectedAddress']=policy['oldAddress']
                elif mode=='port':control['remotePort']=443
                elif mode=='route':control['routeId']='bypass-route'
                elif mode=='proxy':control['proxyBuild']='foreign-proxy'
                elif mode=='origin':control['originPort']=8444
                elif mode=='tls_chain':tls['chainValidated']=False
                elif mode=='tls_hostname':tls['hostnameValidated']=False
                elif mode=='tls_sni':tls['sni']='foreign-host.invalid'
                elif mode=='tls_cipher':tls['cipher']='unapproved-cipher'
                elif mode=='tls_protocol':tls['protocol']='unapproved-protocol'
                elif mode=='tls_store':tls['trustStoreBuild']='foreign-trust-store'
                elif mode=='tls_leaf':tls['certificateSha256']='sha256:'+'0'*64
                elif mode=='tls_anchor':tls['chainFingerprints'][-1]='sha256:'+'0'*64
                elif mode=='tls_clock':tls['finishedAt']='2026-09-03T00:00:00.640Z'
                elif mode=='request_clock':control['requestFinishedAt']='2026-09-03T00:00:01.001Z'
                elif mode=='witness_ref':control['accessWitnessRef']=next(r['witnessRef'] for r in load_yaml(root/report['accessOutcomeRef'])['cases'] if r['case']=='unauthorized')
                elif mode=='response_hash':control['responseSha256']='sha256:'+'0'*64
                elif mode=='missing_denial':report['denials'].pop()
                elif mode=='stale_time':denial['observedAt']='2026-09-03T00:00:01Z'
                elif mode=='bypass_origin':denial['originRequestCount']=1
                elif mode=='denial_target':denial['requestURL']=policy['bypassURL']
                elif mode=='denial_address':denial['connectedAddress']=policy['newAddress']
                elif mode=='denial_bytes':denial.update(**{k:control[k] for k in ('responseBodyRef','responseSha256','responseByteCount')})
                elif mode=='duplicate_request':denial['requestId']=control['requestId']
                else:next(m for m in data['measurements'] if m['id']=='tls_valid')['actual']=False
                if report is None:report_path.write_text('Unrelated public network success assertions\n',encoding='utf8')
                else:write_yaml(report_path,report)
                write_yaml(config_path,config);self.assertTrue(any('qualified public network' in e for e in validate(data)),mode)
        finally:temp.cleanup()
        for profile,status in (('local-v1','pass'),('production','fail'),('production','inconclusive')):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-007',profile,status=status);record=load_yaml(root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef']);self.assertNotIn('publicNetworkRef',record['environmentCaptured']);self.assertEqual(CHECK.validate_repository(root,profile,status=='pass',selected_pocs={'POC-07'}),[])
            finally:temp.cleanup()

    def test_182_metadata_rates_and_costs_derive_complete_streamed_observations(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-005',profile);path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path);report_path=root/original['environmentCaptured']['metadataScanRef'];report_original=load_yaml(report_path);config_path=root/report_original['configurationRef'];config_original=load_yaml(config_path);files={root/a['ref']:(root/a['ref']).read_bytes() for a in original['environmentCaptured']['rawExecutionArtifacts']}
                def validate(data):
                    self.refresh_qualified_observation_fixture(root,data);write_yaml(path,data)
                    return CHECK.validate_repository(root,profile,True,selected_pocs={'POC-05'})
                self.assertEqual(validate(copy.deepcopy(original)),[])
                # Equal-granularity event times retain the approved deterministic sequence.
                report=copy.deepcopy(report_original);file=root/report['changeStream']['events']['ref'];records=[json.loads(line) for line in file.read_bytes().splitlines()]
                for record in records:record['observedAt']='2026-09-03T00:00:06Z'
                raw=b''.join((json.dumps(record,separators=(',',':'))+'\n').encode() for record in records);file.write_bytes(raw);report['changeStream']['events']['sha256']='sha256:'+hashlib.sha256(raw).hexdigest();write_yaml(report_path,report);self.assertEqual(validate(copy.deepcopy(original)),[])
                for mode in ('missing','arbitrary','policy','config','profile','input','build','baseline_sample','scan_id','changes_id','enumeration_count','event_count','enumeration_clock','event_clock','traversal_clock','phase_order','rate','frequency','cost','objects_incomplete','object_duplicate','object_version','event_duplicate','event_sequence','event_version','event_timestamp','event_reordered','event_missing','applied_missing','applied_duplicate','traversed_foreign','generator','row_type','error_echo','duplicate_field','stream_hash'):
                    for file,raw in files.items():file.write_bytes(raw)
                    data=copy.deepcopy(original);report=copy.deepcopy(report_original);config=copy.deepcopy(config_original);policy=config['configuration']['metadataScanPolicy'];enum=report['enumeration'];events=report['changeStream'];incremental=report['incremental']
                    def rewrite(descriptor,mutate):
                        file=root/descriptor['ref'];records=[json.loads(line) for line in file.read_bytes().splitlines()];mutate(records);raw=b''.join((json.dumps(record,separators=(',',':'))+'\n').encode() for record in records);file.write_bytes(raw);descriptor.update(count=len(records),sha256='sha256:'+hashlib.sha256(raw).hexdigest())
                    if mode=='missing':data['environmentCaptured'].pop('metadataScanRef')
                    elif mode=='arbitrary':report=None
                    elif mode=='policy':config['configuration']['metadataScanPolicy']=True
                    elif mode=='config':report['configurationRef']=data['environmentCaptured']['acceptanceProfileConfigurationRef']
                    elif mode=='profile':report['acceptanceProfile']=CHECK.profile_identity('production' if profile=='local-v1' else 'local-v1')
                    elif mode=='input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                    elif mode=='build':report['scannerBuild']='foreign-scanner'
                    elif mode=='baseline_sample':policy['baselineInputSampleId']='other-sample'
                    elif mode=='scan_id':enum['scanId']='other-scan'
                    elif mode=='changes_id':events['changeSetId']='other-changes'
                    elif mode=='enumeration_count':enum['objects']['count']+=1
                    elif mode=='event_count':events['events']['count']+=1
                    elif mode=='enumeration_clock':enum['finishedAt']=enum['startedAt']
                    elif mode=='event_clock':events['finishedAt']=events['startedAt']
                    elif mode=='traversal_clock':incremental['finishedAt']=incremental['startedAt']
                    elif mode=='phase_order':incremental['startedAt']='2026-09-03T00:00:10Z'
                    elif mode in ('rate','frequency','cost'):
                        metric={'rate':'enumeration_rate','frequency':'source_change_frequency','cost':'incremental_scan_cost'}[mode];next(m for m in data['measurements'] if m['id']==metric)['actual']+=1
                    elif mode=='objects_incomplete':rewrite(enum['objects'],lambda records:records.pop())
                    elif mode=='object_duplicate':rewrite(enum['objects'],lambda records:records.append(copy.deepcopy(records[0])))
                    elif mode=='object_version':rewrite(enum['objects'],lambda records:records[0].update(versionId='foreign-version'))
                    elif mode=='event_duplicate':rewrite(events['events'],lambda records:records.append(copy.deepcopy(records[0])))
                    elif mode=='event_sequence':rewrite(events['events'],lambda records:records[0].update(sequence=9))
                    elif mode=='event_version':rewrite(events['events'],lambda records:records[0].update(beforeVersion='foreign-version'))
                    elif mode=='event_timestamp':rewrite(events['events'],lambda records:records[0].update(observedAt='2026-09-03T00:00:19Z'))
                    elif mode=='event_reordered':
                        def reorder(records):
                            records[:]=[records[2],records[0],records[1]]
                            for offset,record in enumerate(records):record['observedAt']=f'2026-09-03T00:00:0{offset+6}Z'
                        rewrite(events['events'],reorder)
                    elif mode=='event_missing':rewrite(events['events'],lambda records:records.pop())
                    elif mode=='applied_missing':rewrite(incremental['appliedEvents'],lambda records:records.pop())
                    elif mode=='applied_duplicate':rewrite(incremental['appliedEvents'],lambda records:records.append(copy.deepcopy(records[0])))
                    elif mode=='traversed_foreign':rewrite(incremental['traversedObjects'],lambda records:records[0].update(objectId='foreign-object'))
                    elif mode=='generator':policy['hierarchyGenerator']={'invalid':'generator'}
                    elif mode=='row_type':rewrite(enum['objects'],lambda records:records.__setitem__(0,True))
                    elif mode=='error_echo':rewrite(enum['objects'],lambda records:records[0].update(objectId={'marker':'INPUT_VALUE_MUST_NOT_APPEAR_IN_ERRORS'}))
                    elif mode=='duplicate_field':
                        file=root/enum['objects']['ref'];raw=file.read_bytes().replace(b'{',b'{"objectId":"duplicate",',1);file.write_bytes(raw);enum['objects']['sha256']='sha256:'+hashlib.sha256(raw).hexdigest()
                    else:enum['objects']['sha256']='sha256:'+'0'*64
                    if report is None:report_path.write_text('Unrelated scan success assertions\n',encoding='utf8')
                    else:write_yaml(report_path,report)
                    write_yaml(config_path,config);errors=validate(data);self.assertTrue(any('qualified metadata scan' in e for e in errors),(profile,mode))
                    if mode=='error_echo':self.assertNotIn('INPUT_VALUE_MUST_NOT_APPEAR_IN_ERRORS','\n'.join(errors))
            finally:temp.cleanup()
        for profile in ('local-v1','production'):
            for status in ('fail','inconclusive'):
                temp,root=self.temp_repo()
                try:
                    index=self.make_profile_slot(root,'POC-005',profile,status=status);record=load_yaml(root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef']);self.assertNotIn('metadataScanRef',record['environmentCaptured']);self.assertEqual(CHECK.validate_repository(root,profile,False,selected_pocs={'POC-05'}),[])
                finally:temp.cleanup()

    def test_187_average_file_size_derives_the_complete_file_population(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-005',profile)
                path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef']
                original=load_yaml(path)
                def validate(data):
                    self.refresh_qualified_observation_fixture(root,data)
                    write_yaml(path,data)
                    return CHECK.validate_repository(root,profile,True,selected_pocs={'POC-05'})
                self.assertEqual(validate(copy.deepcopy(original)),[])
                for value in (0,2,1000000):
                    data=copy.deepcopy(original)
                    next(m for m in data['measurements'] if m['id']=='average_file_size')['actual']=value
                    self.assertTrue(any('average_file_size' in e for e in validate(data)),(profile,value))
                data=copy.deepcopy(original)
                report_path=root/data['environmentCaptured']['metadataScanRef']
                report=load_yaml(report_path)
                config_path=root/report['configurationRef'];config=load_yaml(config_path)
                policy=config['configuration']['metadataScanPolicy']
                records=[json.loads(line) for line in (root/policy['baseline']['ref']).read_bytes().splitlines()]
                # Large directory size is excluded; two distinct files contribute.
                records[0]['fileSizeBytes']=1000
                records[1]['fileSizeBytes']=3
                records.append(dict(objectId='synthetic-file-3',kind='file',versionId='version-1',depth=1,fileSizeBytes=7))
                raw=b''.join((json.dumps(record,separators=(',',':'))+'\n').encode() for record in records)
                digest='sha256:'+hashlib.sha256(raw).hexdigest()
                for descriptor in (policy['baseline'],report['enumeration']['objects']):
                    (root/descriptor['ref']).write_bytes(raw);descriptor.update(sha256=digest,count=3)
                sample=data['samples'][0];sample['checksum']=digest
                input_record=next(r for r in data['environmentCaptured']['inputSampleArtifacts'] if r['sampleId']==sample['id'])
                input_record.update(byteCount=len(raw),sha256=digest)
                approval=load_yaml(root/sample['approvalRef']);approval['checksum']=digest;write_yaml(root/sample['approvalRef'],approval)
                report['inputSamples'][0]['checksum']=digest
                resource_report_path=root/data['environmentCaptured']['metadataResourceRef']
                resource_report=load_yaml(resource_report_path);resource_report['inputSamples'][0]['checksum']=digest;write_yaml(resource_report_path,resource_report)
                if profile=='local-v1':
                    data['environmentCaptured']['synthetic_hierarchy_manifest']['generator']['fileCount']=2
                    policy['hierarchyGenerator']['fileCount']=2
                    profile_path=root/data['environmentCaptured']['acceptanceProfileConfigurationRef']
                    profile_configuration=load_yaml(profile_path)
                    profile_configuration['capturedSettings']['synthetic_hierarchy_manifest']=copy.deepcopy(data['environmentCaptured']['synthetic_hierarchy_manifest'])
                    write_yaml(profile_path,profile_configuration)
                for metric,value in (('file_count',2),('enumeration_rate',1.5),('average_file_size',5)):
                    next(m for m in data['measurements'] if m['id']==metric)['actual']=value
                write_yaml(config_path,config);write_yaml(report_path,report)
                prefix=str(index.parent.relative_to(root)).replace("\\","/");self.prepare_qualified_metadata_profiling_fixture(root,data,prefix,policy)
                self.assertEqual(validate(data),[])
            finally:temp.cleanup()

    def test_188_metadata_quota_and_peak_memory_bind_approved_source_and_scan(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-005',profile)
                path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path)
                report_path=root/original['environmentCaptured']['metadataResourceRef'];report_original=load_yaml(report_path)
                config_path=root/report_original['configurationRef'];config_original=load_yaml(config_path)
                quota_path=root/report_original['quotaDocumentRef'];quota_original=load_yaml(quota_path)
                def validate(data):
                    self.refresh_qualified_observation_fixture(root,data);write_yaml(path,data)
                    return CHECK.validate_repository(root,profile,True,selected_pocs={'POC-05'})
                self.assertEqual(validate(copy.deepcopy(original)),[])
                for mode in ('missing','unrelated','policy_type','profile','input','source','build','process','collector','quota_hash','quota_source','quota_reset','quota_period','quota_ref','quota_oversize','quota_malformed','quota_big_integer','quota_overflow','quota_tiny_period','quota_claim','memory_claim','memory_type','memory_clock','memory_coverage','memory_reset','memory_big_integer','sample_process','sample_scan'):
                    data=copy.deepcopy(original);report=copy.deepcopy(report_original);config=copy.deepcopy(config_original);quota=copy.deepcopy(quota_original);policy=config['configuration']['metadataResourcePolicy']
                    if mode=='missing':data['environmentCaptured'].pop('metadataResourceRef')
                    elif mode=='unrelated':report=True
                    elif mode=='policy_type':config['configuration']['metadataResourcePolicy']=[]
                    elif mode=='profile':report['acceptanceProfile']=CHECK.profile_identity('production' if profile=='local-v1' else 'local-v1')
                    elif mode=='input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                    elif mode=='source':report['sourceIdentity']['sourceVersion']='foreign-source'
                    elif mode=='build':report['scannerBuild']='foreign-build'
                    elif mode=='process':report['processId']='foreign-process'
                    elif mode=='collector':report['collectorBuild']='foreign-collector'
                    elif mode=='quota_hash':policy['quotaDocumentSha256']=report['quotaDocumentSha256']='sha256:'+'0'*64
                    elif mode=='quota_source':quota['sourceIdentity']['adapterBuild']='foreign-adapter'
                    elif mode=='quota_reset':quota['resetSemantics']=''
                    elif mode=='quota_period':quota['periodSeconds']=0
                    elif mode=='quota_ref':policy['quotaDocumentRef']=report['quotaDocumentRef']=report['configurationRef']
                    elif mode=='quota_big_integer':quota['requestLimit']=10**400
                    elif mode=='quota_overflow':quota.update(requestLimit=10**307,periodSeconds=1)
                    elif mode=='quota_tiny_period':quota['periodSeconds']=1e-320
                    elif mode in ('quota_claim','memory_claim'):
                        metric='source_api_quota' if mode=='quota_claim' else 'memory_peak';next(m for m in data['measurements'] if m['id']==metric)['actual']=2
                    elif mode=='memory_type':report['memorySamples'][1]['peakResidentBytes']=True
                    elif mode=='memory_clock':report['memorySamples'][0]['observedAt']='2026-09-02T00:00:00Z'
                    elif mode=='memory_coverage':report['memorySamples'][1]['observedAt']='2026-09-03T00:00:19Z'
                    elif mode=='memory_reset':report['memorySamples'][1]['peakResidentBytes']=1
                    elif mode=='memory_big_integer':report['memorySamples'][1]['peakResidentBytes']=10**400
                    elif mode=='sample_process':report['memorySamples'][1]['processId']='foreign-process'
                    elif mode=='sample_scan':report['memorySamples'][1]['scanId']='foreign-scan'
                    write_yaml(quota_path,quota)
                    if mode=='quota_oversize':quota_path.write_bytes(b' '*262145)
                    elif mode=='quota_malformed':quota_path.write_text('{broken: [',encoding='utf8')
                    if mode in ('quota_source','quota_reset','quota_period','quota_oversize','quota_malformed','quota_big_integer','quota_overflow','quota_tiny_period'):
                        digest='sha256:'+hashlib.sha256(quota_path.read_bytes()).hexdigest();policy['quotaDocumentSha256']=report['quotaDocumentSha256']=digest
                    write_yaml(config_path,config);write_yaml(report_path,report)
                    self.assertTrue(any('qualified metadata scan resources' in e for e in validate(data)),(profile,mode))
                data=copy.deepcopy(original);report=copy.deepcopy(report_original);config=copy.deepcopy(config_original);quota=copy.deepcopy(quota_original)
                quota.update(requestLimit=75,periodSeconds=120);write_yaml(quota_path,quota)
                digest='sha256:'+hashlib.sha256(quota_path.read_bytes()).hexdigest();config['configuration']['metadataResourcePolicy']['quotaDocumentSha256']=report['quotaDocumentSha256']=digest
                report['memorySamples'][1]['peakResidentBytes']=1572864
                for metric,value in (('source_api_quota',37.5),('memory_peak',1.5)):next(m for m in data['measurements'] if m['id']==metric)['actual']=value
                write_yaml(config_path,config);write_yaml(report_path,report);self.assertEqual(validate(data),[])
            finally:temp.cleanup()

    def deferred_production_errors(self,profile,poc):
        return [f'deferred production qualification {poc}: production outcome validation is not implemented; PASS unavailable'] if profile=='production' and poc in ('POC-04','POC-06') else []

    def test_189_deferred_production_storage_and_baidu_fail_closed_without_losing_diagnostics(self):
        for task in ('POC-004','POC-006'):
            poc='POC-'+task[-2:]
            for profile in ('local-v1','production'):
                for status in ('pass','fail','inconclusive'):
                    temp,root=self.temp_repo()
                    try:
                        self.make_profile_slot(root,task,profile,status=status)
                        errors=CHECK.validate_repository(root,profile,status=='pass',selected_pocs={poc})
                        self.assertEqual(errors,self.deferred_production_errors(profile,poc) if status=='pass' else [])
                    finally:temp.cleanup()

    def test_190_h264_fallback_requires_a_distinct_approved_run_and_decoder_result(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-002',profile);result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=load_yaml(path)
                env=original['environmentCaptured'];report_path=root/env['h264FallbackRef'];report_original=load_yaml(report_path);probe_path=root/report_original['decodeRef'];probe_original=load_yaml(probe_path);config_path=root/report_original['configurationRef'];config_original=load_yaml(config_path);media_path=root/report_original['outputArtifactRef'];media_bytes=media_path.read_bytes()
                prefix=str(index.parent.relative_to(root)).replace('\\','/');plan=load_yaml(self.plan_path(root,'POC-002'));defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];window=tuple(CHECK.utc(env['executionWindow'][key]) for key in ('startedAt','finishedAt'))
                def validate(data):
                    self.refresh_qualified_observation_fixture(root,data);errors=[]
                    CHECK.validate_qualified_h264_fallback(root,plan,data,prefix,'pass',window,defs,errors,{})
                    return errors
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'}),[])
                self.assertEqual(validate(copy.deepcopy(original)),[])
                modes=('missing','unrelated','policy_type','profile','input','node','host','build','codec','parameters','args','span','assembly_type','clock','exit','encoded_count','decode_missing','decode_codec','decode_clock','decode_false','decode_errors','decode_count','decode_duration','decode_hash','output_hash','output_bytes','empty','output_owner','output_kind','alias_av1','alias_input')
                for mode in modes:
                    data=copy.deepcopy(original);report=copy.deepcopy(report_original);probe=copy.deepcopy(probe_original);config=copy.deepcopy(config_original);media_path.write_bytes(media_bytes);linked=False
                    if mode=='missing':data['environmentCaptured'].pop('h264FallbackRef')
                    elif mode=='unrelated':report=True
                    elif mode=='policy_type':config['configuration']['mediaFallbackPolicy']=True
                    elif mode=='profile':report['acceptanceProfile']=CHECK.profile_identity('production' if profile=='local-v1' else 'local-v1')
                    elif mode=='input':report['inputSha256']='sha256:'+'0'*64
                    elif mode=='node':report['nodeId']='foreign-node'
                    elif mode=='host':report['physicalHostId']='foreign-host'
                    elif mode=='build':report['encoderBuild']='foreign-build'
                    elif mode=='codec':report['codec']='av1'
                    elif mode=='parameters':report['encoderParameters']['preset']='foreign-preset'
                    elif mode=='args':report['commandArgs'].append('unapproved-argument')
                    elif mode=='span':report['sourceEndFrame']=119
                    elif mode=='assembly_type':data['environmentCaptured']['parallelMediaAssembly']=True
                    elif mode=='clock':report['finishedAt']=report['startedAt']
                    elif mode=='exit':report['exitCode']=1
                    elif mode=='encoded_count':report['encodedFrameCount']=119
                    elif mode=='decode_missing':report['decodeRef']=data['environmentCaptured']['h264FallbackRef']
                    elif mode=='decode_codec':probe['codec']='av1'
                    elif mode=='decode_clock':probe['observedAt']='2026-09-03T00:00:00Z'
                    elif mode=='decode_false':probe['decodable']=False
                    elif mode=='decode_errors':probe['decodeErrorCount']=1
                    elif mode=='decode_count':probe['decodedFrameCount']=119
                    elif mode=='decode_duration':probe['durationSeconds']=0
                    elif mode=='decode_hash':probe['outputSha256']='sha256:'+'0'*64
                    elif mode=='output_hash':report['outputSha256']=probe['outputSha256']='sha256:'+'0'*64
                    elif mode=='output_bytes':report['outputByteCount']+=1
                    elif mode=='empty':media_path.write_bytes(b'')
                    elif mode in ('output_owner','output_kind'):
                        artifact=next(a for a in data['environmentCaptured']['rawExecutionArtifacts'] if a['ref']==report['outputArtifactRef'])
                        if mode=='output_owner':artifact['nodeId']='foreign-node'
                        else:artifact['artifactType']='command_output'
                    elif mode in ('alias_av1','alias_input'):
                        target=root/(data['environmentCaptured']['workerEncodeExecutions'][0]['outputArtifactRef'] if mode=='alias_av1' else data['environmentCaptured']['inputSampleArtifacts'][0]['inputArtifactRef'])
                        media_path.unlink();os.link(target,media_path);linked=True;raw=media_path.read_bytes();report['outputByteCount']=len(raw);report['outputSha256']=probe['outputSha256']='sha256:'+hashlib.sha256(raw).hexdigest()
                    write_yaml(config_path,config);write_yaml(report_path,report);write_yaml(probe_path,probe)
                    try:self.assertTrue(any('qualified H264 fallback' in e for e in validate(data)),(profile,mode))
                    finally:
                        if linked:media_path.unlink();media_path.write_bytes(media_bytes)
                # Removing fallback must also fail the ordinary repository entry point.
                data=copy.deepcopy(original);data['environmentCaptured'].pop('h264FallbackRef');write_yaml(path,data)
                self.assertTrue(any('qualified H264 fallback' in e for e in CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'})))
            finally:temp.cleanup()

    def test_191_sustained_minutes_equal_the_retained_continuous_worker_interval(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-002',profile);result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=load_yaml(path)
                prefix=str(index.parent.relative_to(root)).replace('\\','/');plan=load_yaml(self.plan_path(root,'POC-002'));defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];window=tuple(CHECK.utc(original['environmentCaptured']['executionWindow'][key]) for key in ('startedAt','finishedAt'))
                def validate(value):
                    data=copy.deepcopy(original);next(m for m in data['measurements'] if m['id']=='sustained_encode_duration')['actual']=value;errors=[]
                    CHECK.validate_qualified_encode_workers(root,plan,data,prefix,'pass',window,errors,{},defs)
                    return errors
                self.assertEqual(validate(1),[])
                self.assertEqual(validate(1+1e-10),[])
                for value in (0,0.5,1-1e-8,1+1e-8,2,True,None,float('inf'),10**400):
                    self.assertTrue(any('sustained_encode_duration must equal' in e for e in validate(value)),type(value).__name__)
                data=copy.deepcopy(original);next(m for m in data['measurements'] if m['id']=='sustained_encode_duration')['actual']=0.5;write_yaml(path,data)
                self.assertTrue(any('sustained_encode_duration must equal' in e for e in CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'})))
            finally:temp.cleanup()

    def test_192_media_soak_requires_approved_window_continuous_progress_and_stable_outputs(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-002',profile);result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=load_yaml(path)
                env=original['environmentCaptured'];report_path=root/env['mediaSoakRef'];report_original=load_yaml(report_path);config_path=root/report_original['configurationRef'];config_original=load_yaml(config_path);probe_path=root/report_original['cases'][0]['decodeRef'];probe_original=load_yaml(probe_path)
                prefix=str(index.parent.relative_to(root)).replace('\\','/');plan=load_yaml(self.plan_path(root,'POC-002'));defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];window=tuple(CHECK.utc(env['executionWindow'][key]) for key in ('startedAt','finishedAt'))
                def validate(data,status='pass'):
                    self.refresh_qualified_observation_fixture(root,data);errors=[]
                    CHECK.validate_qualified_media_soak(root,plan,data,prefix,status,window,defs,errors,{})
                    return errors
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'}),[])
                self.assertEqual(validate(copy.deepcopy(original)),[])
                modes=('missing','unrelated','policy_type','minimum','minimum_type','profile','input','missing_case','no_h264','duplicate_case','node','build','parameters','short_window','outside','final_exit','final_exit_type','final_exit_missing','final_status','final_reason','progress_gap','progress_missing_end','no_progress','frames','memory_peak','memory_growth','temporary','temporary_cleanup','cpu','nonfinite_cpu','gpu_hang','corrupt_segment','unrecovered','late_recovery','decode_error','decode_codec','decode_count','decode_clock','decode_hash','output_owner','output_size','gate')
                for mode in modes:
                    data=copy.deepcopy(original);report=copy.deepcopy(report_original);config=copy.deepcopy(config_original);probe=copy.deepcopy(probe_original);policy=config['configuration']['mediaSoakPolicy'];row=report['cases'][0]
                    if mode=='missing':data['environmentCaptured'].pop('mediaSoakRef')
                    elif mode=='unrelated':report=True
                    elif mode=='policy_type':config['configuration']['mediaSoakPolicy']=True
                    elif mode=='minimum':policy['minimumDurationMinutes']=2
                    elif mode=='minimum_type':policy['minimumDurationMinutes']=True
                    elif mode=='profile':report['acceptanceProfile']=CHECK.profile_identity('production' if profile=='local-v1' else 'local-v1')
                    elif mode=='input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                    elif mode=='missing_case':report['cases'].pop()
                    elif mode=='no_h264':policy['cases'].pop();report['cases'].pop()
                    elif mode=='duplicate_case':policy['cases'][1]=copy.deepcopy(policy['cases'][0])
                    elif mode=='node':row['nodeId']='foreign-node'
                    elif mode=='build':row['encoderBuild']='foreign-build'
                    elif mode=='parameters':row['encoderParameters']['preset']='unapproved-preset'
                    elif mode=='short_window':row['finishedAt']=row['progress'][-1]['observedAt']='2026-09-03T00:00:30Z'
                    elif mode=='outside':row['startedAt']='2026-09-02T00:00:00Z'
                    elif mode=='final_exit':row['processExitCode']=1
                    elif mode=='final_exit_type':row['processExitCode']=False
                    elif mode=='final_exit_missing':row.pop('processExitCode')
                    elif mode=='final_status':row['terminalStatus']='failed'
                    elif mode=='final_reason':row['processTerminationReason']='unrecovered_failure'
                    elif mode=='progress_gap':policy['maximumProgressGapSeconds']=59
                    elif mode=='progress_missing_end':row['progress'][-1]['observedAt']='2026-09-03T00:00:59Z'
                    elif mode=='no_progress':row['progress'][-1].update(completedIterations=0,completedFrames=0)
                    elif mode=='frames':row['progress'][-1]['completedFrames']=121
                    elif mode=='memory_peak':row['progress'][-1]['residentBytes']=policy['maximumResidentBytes']+1
                    elif mode=='memory_growth':policy['maximumResidentGrowthBytes']=0;row['progress'][-1]['residentBytes']+=1
                    elif mode=='temporary':row['progress'][0]['temporaryBytes']=policy['maximumTemporaryBytes']+1
                    elif mode=='temporary_cleanup':row['progress'][-1]['temporaryBytes']=1
                    elif mode=='cpu':row['progress'][-1]['cpuSeconds']=policy['maximumCpuSeconds']+1
                    elif mode=='nonfinite_cpu':row['progress'][-1]['cpuSeconds']=float('inf')
                    elif mode in ('gpu_hang','corrupt_segment','unrecovered','late_recovery'):
                        row['failureEvents']=[dict(eventId='synthetic-failure',kind=mode if mode in ('gpu_hang','corrupt_segment') else 'encoder',occurredAt='2026-09-03T00:00:00Z',recoveredAt=None if mode=='unrecovered' else '2026-09-03T00:00:06Z' if mode=='late_recovery' else '2026-09-03T00:00:01Z')]
                    elif mode=='decode_error':probe['decodeErrorCount']=1
                    elif mode=='decode_codec':probe['codec']='h264'
                    elif mode=='decode_count':probe['decodedFrameCount']=119
                    elif mode=='decode_clock':probe['observedAt']='2026-09-03T00:00:59Z'
                    elif mode=='decode_hash':probe['outputSha256']='sha256:'+'0'*64
                    elif mode=='output_owner':next(a for a in data['environmentCaptured']['rawExecutionArtifacts'] if a['ref']==row['outputArtifactRef'])['nodeId']='foreign-node'
                    elif mode=='output_size':row['outputByteCount']+=1
                    elif mode=='gate':next(m for m in data['measurements'] if m['id']=='sustained_encode_stability')['actual']=False
                    write_yaml(config_path,config);write_yaml(report_path,report);write_yaml(probe_path,probe)
                    self.assertTrue(any('qualified media soak' in e for e in validate(data)),(profile,mode))
                data=copy.deepcopy(original);report=copy.deepcopy(report_original);row=report['cases'][0]
                row['failureEvents']=[dict(eventId='synthetic-recovered-failure',kind='encoder',occurredAt='2026-09-03T00:00:01Z',recoveredAt='2026-09-03T00:00:03Z')]
                row['progress'].insert(1,dict(observedAt='2026-09-03T00:00:02Z',completedIterations=0,completedFrames=0,residentBytes=1048576,temporaryBytes=1,cpuSeconds=1))
                write_yaml(config_path,config_original);write_yaml(report_path,report);write_yaml(probe_path,probe_original);self.assertEqual(validate(data),[])
                for status in ('fail','inconclusive'):
                    data=copy.deepcopy(original);data['environmentCaptured'].pop('mediaSoakRef');self.assertEqual(validate(data,status),[])
                data=copy.deepcopy(original);data['environmentCaptured'].pop('mediaSoakRef');write_yaml(path,data)
                self.assertTrue(any('qualified media soak' in e for e in CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'})))
            finally:temp.cleanup()


    def test_193_hls_ready_requires_out_of_order_intermediate_manifest_prefixes(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-002',profile);path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path);env=original['environmentCaptured'];report_path=root/env['hlsReadyRef'];original_report=load_yaml(report_path);config_path=root/original_report['configurationRef'];original_config=load_yaml(config_path);probe_path=root/original_report['segments'][0]['decodeRef'];original_probe=load_yaml(probe_path)
                playlist_path=root/original_report['snapshots'][0]['playlistRef'];original_playlist=playlist_path.read_bytes();prefix=str(index.parent.relative_to(root)).replace('\\','/');plan=load_yaml(self.plan_path(root,'POC-002'));defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];window=tuple(CHECK.utc(env['executionWindow'][k]) for k in ('startedAt','finishedAt'))
                def validate(data,status='pass'):
                    self.refresh_qualified_observation_fixture(root,data);errors=[];CHECK.validate_qualified_hls_ready(root,plan,data,prefix,status,window,defs,errors,{});return errors
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'}),[])
                self.assertEqual(validate(copy.deepcopy(original)),[])
                for mode in ('missing','shape','policy','profile','job','epoch','input','coverage','duplicate','node','clock','exit','exit_bool','frames','owner','size','decode_hash','decode_error','decode_frames','decode_clock','state','snapshot_clock','hole','early_endlist','final_only','missing_intermediate','init_hash','init_owner','init_clock','init_decode','init_map','init_alias','before_start_state','caps_shape','assembly_shape','inventory_shape','fps_huge','fps_tiny','gate'):
                    if mode=='caps_shape' and profile=='production':continue
                    data=copy.deepcopy(original);report=copy.deepcopy(original_report);config=copy.deepcopy(original_config);probe=copy.deepcopy(original_probe);policy=config['configuration']['hlsReadyPolicy'];row=report['segments'][0];body=original_playlist
                    if mode=='missing':data['environmentCaptured'].pop('hlsReadyRef')
                    elif mode=='shape':report=True
                    elif mode=='policy':config['configuration']['hlsReadyPolicy']=True
                    elif mode=='profile':report['acceptanceProfile']=CHECK.profile_identity('production' if profile=='local-v1' else 'local-v1')
                    elif mode=='job':report['jobId']='foreign'
                    elif mode=='epoch':report['attemptEpoch']=2
                    elif mode=='input':report['inputSha256']='sha256:'+'0'*64
                    elif mode=='coverage':policy['segments'][0]['sourceStartFrame']=1
                    elif mode=='duplicate':policy['segments'][1]['segmentId']=policy['segments'][0]['segmentId']
                    elif mode=='node':row['nodeId']='foreign'
                    elif mode=='clock':row['readyAt']='2026-09-03T00:00:19Z'
                    elif mode=='exit':row['exitCode']=1
                    elif mode=='exit_bool':row['exitCode']=False
                    elif mode=='frames':row['encodedFrameCount']=39
                    elif mode=='owner':next(a for a in data['environmentCaptured']['rawExecutionArtifacts'] if a['ref']==row['outputArtifactRef'])['nodeId']='foreign'
                    elif mode=='size':row['outputByteCount']+=1
                    elif mode=='decode_hash':probe['outputSha256']='sha256:'+'0'*64
                    elif mode=='decode_error':probe['decodeErrorCount']=1
                    elif mode=='decode_frames':probe['decodedFrameCount']=39
                    elif mode=='decode_clock':probe['observedAt']='2026-09-03T00:00:21Z'
                    elif mode=='init_hash':report['initSha256']='sha256:'+'0'*64
                    elif mode=='init_owner':next(a for a in data['environmentCaptured']['rawExecutionArtifacts'] if a['ref']==report['initArtifactRef'])['nodeId']='foreign'
                    elif mode=='init_clock':report['initReadyAt']='2026-09-03T00:00:11Z'
                    elif mode=='init_decode':probe['initSha256']='sha256:'+'0'*64
                    elif mode=='init_map':body=body.replace(b'#EXT-X-MAP:URI="init.mp4"\n',b'')
                    elif mode=='init_alias':report['initArtifactRef']=row['outputArtifactRef'];report['initSha256']=row['outputSha256']
                    elif mode=='before_start_state':report['snapshots'][0]['segmentStates'][2]['state']='encoding'
                    elif mode=='caps_shape':data['environmentCaptured']['scheduler_configuration']=True
                    elif mode=='assembly_shape':data['environmentCaptured']['parallelMediaAssembly']=True
                    elif mode=='inventory_shape':data['environmentCaptured']['worker_node_inventory']=True
                    elif mode=='fps_huge':policy['framesPerSecond']=10**401
                    elif mode=='fps_tiny':policy['framesPerSecond']=1e-308
                    elif mode=='state':report['snapshots'][0]['segmentStates'][0]['state']='ready'
                    elif mode=='snapshot_clock':report['snapshots'][0]['observedAt']='2026-09-02T00:00:00Z'
                    elif mode=='hole':body+=b'#EXTINF:1.333333,\nsegment-1.m4s\n'
                    elif mode=='early_endlist':body+=b'#EXT-X-ENDLIST\n'
                    elif mode=='final_only':report['snapshots']=[report['snapshots'][-1]]*3
                    elif mode=='missing_intermediate':report['snapshots'][1]=copy.deepcopy(report['snapshots'][0]);report['snapshots'][1]['observedAt']='2026-09-03T00:00:12Z'
                    else:next(m for m in data['measurements'] if m['id']=='hls_ready_only_contiguous')['actual']=False
                    playlist_path.write_bytes(body)
                    if isinstance(report,dict):report['snapshots'][0]['playlistSha256']='sha256:'+hashlib.sha256(body).hexdigest()
                    write_yaml(config_path,config);write_yaml(report_path,report);write_yaml(probe_path,probe)
                    self.assertTrue(any('qualified HLS READY' in e for e in validate(data)),(profile,mode))
                write_yaml(config_path,original_config);write_yaml(report_path,original_report);write_yaml(probe_path,original_probe);playlist_path.write_bytes(original_playlist)
                report=copy.deepcopy(original_report);report['initReadyAt']='2026-09-03T00:00:01Z';write_yaml(report_path,report);self.assertEqual(validate(copy.deepcopy(original)),[])
                report=copy.deepcopy(original_report);report['snapshots'][0]['observedAt']='2026-09-03T00:00:00Z';report['initReadyAt']='2026-09-03T00:00:01Z';write_yaml(report_path,report);self.assertTrue(any('after initialization' in e for e in validate(copy.deepcopy(original))))
                write_yaml(report_path,original_report)
                for status in ('fail','inconclusive'):
                    data=copy.deepcopy(original);data['environmentCaptured'].pop('hlsReadyRef');self.assertEqual(validate(data,status),[])
                data=copy.deepcopy(original);data['environmentCaptured'].pop('hlsReadyRef');write_yaml(path,data);self.assertTrue(any('qualified HLS READY' in e for e in CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'})))
            finally:temp.cleanup()



    def test_194_playback_priority_reservation_aging_and_fallback_bind_real_state_observations(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-002',profile);path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path);env=original['environmentCaptured'];ref=root/env['mediaSchedulingRef'];baseline=load_yaml(ref);config_path=root/baseline['configurationRef'];config=load_yaml(config_path);prefix=str(index.parent.relative_to(root)).replace('\\','/');plan=load_yaml(self.plan_path(root,'POC-002'));defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];window=tuple(CHECK.utc(env['executionWindow'][k]) for k in ('startedAt','finishedAt'))
                def validate(data,status='pass'):
                    self.refresh_qualified_observation_fixture(root,data);errors=[];CHECK.validate_qualified_media_scheduling(root,plan,data,prefix,status,window,defs,errors,{});return errors
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'}),[])
                self.assertEqual(validate(copy.deepcopy(original)),[])

                def rebuild_states(report,policy):
                    base_priorities={'playback':0,'prewarm':3,'background':6}
                    for snapshot in report['snapshots']:
                        at=CHECK.utc(snapshot['observedAt']);states=[]
                        for job in report['jobs']:
                            q=CHECK.utc(job['queuedAt']);a=CHECK.utc(job['admittedAt']) if job['admittedAt'] else None;s=CHECK.utc(job['startedAt']) if job['startedAt'] else None;f=CHECK.utc(job['finishedAt']) if job['finishedAt'] else None;ready=CHECK.utc(job['readyAt']) if job['readyAt'] else None
                            state='not_queued' if at<q else 'denied' if a is None else 'queued' if at<a else 'admitted' if at<s else 'running' if at<f else 'completed' if at<ready else 'ready';base=base_priorities[job['purpose']];aged=min(at,a) if a is not None else at;effective=0 if base==0 else max(policy['agingFloorPriority'],base-int(max(0,(aged-q).total_seconds())//policy['agingStepSeconds']));states.append(dict(jobId=job['jobId'],state=state,basePriority=base,effectivePriority=effective))
                        snapshot['jobs']=states
                for simultaneous_case in ('same_node_nonplayback','total_capacity'):
                    data=copy.deepcopy(original);report=copy.deepcopy(baseline);cfg=copy.deepcopy(config);policy=cfg['configuration']['mediaSchedulingPolicy'];aged=next(j for j in report['jobs'] if j['jobId']==policy['agingJobId']);aged.update(admittedAt='2026-09-03T00:00:20Z',startedAt='2026-09-03T00:00:20Z',finishedAt='2026-09-03T00:00:22Z')
                    # Deliberately omit the oversubscribed20..22 interval from snapshots;
                    # both jobs are admitted in the same clock batch and finish at22.
                    report['snapshots']=[s for s in report['snapshots'] if s['observedAt']!='2026-09-03T00:00:20.000Z']
                    if simultaneous_case=='total_capacity':
                        playback=next(j for j in report['jobs'] if j['jobId']==policy['playbackJobId']);added=copy.deepcopy(playback);added.update(jobId='synthetic-extra-simultaneous-playback',queuedAt='2026-09-03T00:00:19Z',admittedAt='2026-09-03T00:00:20Z',startedAt='2026-09-03T00:00:20Z',finishedAt='2026-09-03T00:00:22Z',readyAt='2026-09-03T00:00:24.500Z')
                        media_ref=prefix+'/raw/simultaneous-playback-output.bin';payload=b'Synthetic separate simultaneous playback output; never actual encode.';(root/media_ref).write_bytes(payload);added['outputArtifactRef']=media_ref;added['outputSha256']='sha256:'+hashlib.sha256(payload).hexdigest();data['environmentCaptured']['rawExecutionArtifacts'].append(dict(ref=media_ref,artifactType='produced_media',nodeId=added['nodeId'],byteCount=len(payload),sha256=added['outputSha256']));data['rawOutputRefs'].append(media_ref)
                        probe=load_yaml(root/playback['decodeRef']);probe.update(jobId=added['jobId'],outputArtifactRef=media_ref,outputSha256=added['outputSha256'],observedAt=added['readyAt']);added['decodeRef']=prefix+'/raw/simultaneous-playback-decode.yaml';write_yaml(root/added['decodeRef'],probe);raw=(root/added['decodeRef']).read_bytes();data['environmentCaptured']['rawExecutionArtifacts'].append(dict(ref=added['decodeRef'],artifactType='measurement_output',nodeId=added['nodeId'],byteCount=len(raw),sha256='sha256:'+hashlib.sha256(raw).hexdigest()));data['rawOutputRefs'].append(added['decodeRef']);report['jobs'].append(added);policy['jobs'].append({k:added[k] for k in policy['jobs'][0]})
                    rebuild_states(report,policy);write_yaml(config_path,cfg);write_yaml(ref,report)
                    self.assertTrue(any('admission intervals exceed' in e for e in validate(data)),(profile,simultaneous_case))
                write_yaml(config_path,config);write_yaml(ref,baseline)

                for mode in ('missing','shape','policy','profile','context','build','node','grant','epoch','clock','priority','state','reserve','caps','aging','preemption','saturation','admission_latency','ready_latency','decode','output_hash','empty','fallback_grant','fallback_hash','fallback_clock','fallback_before_decode','aging_tiny','denial_bytes','local_caps_shape','inventory_shape','assembly_shape','gate'):
                    if mode=='local_caps_shape' and profile=='production':continue
                    data=copy.deepcopy(original);report=copy.deepcopy(baseline);cfg=copy.deepcopy(config);policy=cfg['configuration']['mediaSchedulingPolicy'];playback=next(j for j in report['jobs'] if j['jobId']==policy['playbackJobId'])
                    if mode=='missing':data['environmentCaptured'].pop('mediaSchedulingRef')
                    elif mode=='shape':report=True
                    elif mode=='policy':cfg['configuration']['mediaSchedulingPolicy']=True
                    elif mode=='profile':report['acceptanceProfile']=CHECK.profile_identity('production' if profile=='local-v1' else 'local-v1')
                    elif mode=='context':report['context']['assetVersion']='foreign'
                    elif mode=='build':report['schedulerBuild']='foreign'
                    elif mode=='node':playback['nodeId']='foreign'
                    elif mode=='grant':playback['grantId']=policy['context']['expiredGrantId']
                    elif mode=='epoch':playback['demandEpoch']=2
                    elif mode=='clock':playback['admittedAt']='2026-09-03T00:00:00Z'
                    elif mode=='priority':report['snapshots'][2]['jobs'][0]['effectivePriority']=0
                    elif mode=='state':report['snapshots'][2]['jobs'][0]['state']='queued'
                    elif mode=='reserve':policy['reservedPlaybackSlots']=2
                    elif mode=='caps':policy['perNodeCapacity']=0
                    elif mode=='aging':report['snapshots'][5]['jobs'][1]['effectivePriority']=6
                    elif mode=='preemption':report['preemptedRunningProcessIds']=['synthetic-background-process']
                    elif mode=='saturation':policy['saturationJobIds']=[policy['prewarmJobId']]
                    elif mode=='admission_latency':report['admissionLatencySeconds']=0
                    elif mode=='ready_latency':report['firstReadyLatencySeconds']=0
                    elif mode=='decode':playback['decodeRef']=env['h264FallbackRef']
                    elif mode=='output_hash':playback['outputSha256']='sha256:'+'0'*64
                    elif mode=='empty':playback['outputArtifactRef']=next(j['denialBodyRef'] for j in report['jobs'] if j['denialBodyRef'] is not None)
                    elif mode=='fallback_grant':report['fallback']['grantId']=policy['context']['revokedGrantId']
                    elif mode=='fallback_hash':report['fallback']['outputSha256']='sha256:'+'0'*64
                    elif mode=='fallback_clock':report['fallback']['observedAt']='2026-09-03T00:00:05Z'
                    elif mode=='fallback_before_decode':report['fallback']['observedAt']='2026-09-03T00:00:01.500Z'
                    elif mode=='aging_tiny':policy['agingStepSeconds']=1e-320
                    elif mode=='denial_bytes':next(j for j in report['jobs'] if j['denialBodyRef'] is not None)['denialBodyRef']=playback['outputArtifactRef']
                    elif mode=='local_caps_shape':data['environmentCaptured']['scheduler_configuration']=True
                    elif mode=='inventory_shape':data['environmentCaptured']['worker_node_inventory']=True
                    elif mode=='assembly_shape':data['environmentCaptured']['parallelMediaAssembly']=True
                    else:next(m for m in data['measurements'] if m['id']=='playback_priority_reserved_capacity')['actual']=False
                    write_yaml(config_path,cfg);write_yaml(ref,report)
                    self.assertTrue(any('qualified playback scheduling' in e for e in validate(data)),(profile,mode))
                write_yaml(config_path,config);write_yaml(ref,baseline)
                for status in ('fail','inconclusive'):
                    data=copy.deepcopy(original);data['environmentCaptured'].pop('mediaSchedulingRef');self.assertEqual(validate(data,status),[])
                data=copy.deepcopy(original);data['environmentCaptured'].pop('mediaSchedulingRef');write_yaml(path,data);self.assertTrue(any('qualified playback scheduling' in e for e in CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'})))
            finally:temp.cleanup()


    def test_195_worker_capability_claims_require_every_node_codec_and_exact_decoder_outputs(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-001',profile);path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path);env=original['environmentCaptured'];report_path=root/env['workerCapabilitiesRef'];original_report=load_yaml(report_path);config_path=root/original_report['configurationRef'];original_config=load_yaml(config_path);probe_path=root/original_report['claims'][0]['decodeRef'];original_probe=load_yaml(probe_path);diagnostic_path=root/original_report['claims'][2]['diagnosticRef'];original_diagnostic=load_yaml(diagnostic_path)
                prefix=str(index.parent.relative_to(root)).replace('\\','/');plan=load_yaml(self.plan_path(root,'POC-001'));defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];window=tuple(CHECK.utc(env['executionWindow'][k]) for k in ('startedAt','finishedAt'))
                def validate(data,status='pass'):
                    self.refresh_qualified_observation_fixture(root,data);errors=[];CHECK.validate_qualified_worker_capabilities(root,plan,data,prefix,status,window,defs,errors,{});return errors
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-01'}),[]);self.assertEqual(validate(copy.deepcopy(original)),[])
                for mode in ('missing','shape','policy','matrix_shape','matrix_missing','node_missing','claim_missing','duplicate','profile','input','os','architecture','configuration','parameters','codec','clock','exit','exit_bool','frames','owner','bytes','decode_codec','decode_node','decode_build','decode_hash','decode_clock','decode_frames','decode_error','decode_duration','diagnostic_status','diagnostic_node','diagnostic_hash','diagnostic_reason','untested_required','fps_huge','fps_tiny','gate'):
                    data=copy.deepcopy(original);report=copy.deepcopy(original_report);config=copy.deepcopy(original_config);probe=copy.deepcopy(original_probe);diagnostic=copy.deepcopy(original_diagnostic);policy=config['configuration']['workerCapabilityPolicy'];row=report['claims'][0]
                    if mode=='missing':data['environmentCaptured'].pop('workerCapabilitiesRef')
                    elif mode=='shape':report=True
                    elif mode=='policy':config['configuration']['workerCapabilityPolicy']=True
                    elif mode=='matrix_shape':data['environmentCaptured']['encoder_capability_matrix']=True
                    elif mode=='matrix_missing':data['environmentCaptured']['encoder_capability_matrix'].pop()
                    elif mode=='node_missing':data['environmentCaptured']['worker_node_inventory'].append(dict(nodeId='foreign-node'))
                    elif mode=='claim_missing':report['claims'].pop()
                    elif mode=='duplicate':policy['claims'][1]['caseId']=policy['claims'][0]['caseId'];data['environmentCaptured']['encoder_capability_matrix']=copy.deepcopy(policy['claims'])
                    elif mode=='profile':report['acceptanceProfile']=CHECK.profile_identity('production' if profile=='local-v1' else 'local-v1')
                    elif mode=='input':row['inputSha256']='sha256:'+'0'*64
                    elif mode=='os':data['environmentCaptured']['worker_node_inventory'][0]['osBuild']='foreign'
                    elif mode=='architecture':data['environmentCaptured']['worker_node_inventory'][0]['architecture']='foreign'
                    elif mode=='configuration':row['nodeConfiguration']['mode']='foreign'
                    elif mode=='parameters':row['encoderParameters']['preset']='foreign'
                    elif mode=='codec':row['codec']='h264'
                    elif mode=='clock':row['finishedAt']='2026-09-02T00:00:00Z'
                    elif mode=='exit':row['exitCode']=1
                    elif mode=='exit_bool':row['exitCode']=False
                    elif mode=='frames':row['encodedFrameCount']=119
                    elif mode=='owner':next(a for a in data['environmentCaptured']['rawExecutionArtifacts'] if a['ref']==row['outputArtifactRef'])['nodeId']='foreign'
                    elif mode=='bytes':row['outputByteCount']+=1
                    elif mode=='decode_codec':probe['codec']='h264'
                    elif mode=='decode_node':probe['nodeId']='foreign'
                    elif mode=='decode_build':probe['encoderBuild']='foreign'
                    elif mode=='decode_hash':probe['outputSha256']='sha256:'+'0'*64
                    elif mode=='decode_clock':probe['observedAt']='2026-09-03T00:00:00Z'
                    elif mode=='decode_frames':probe['decodedFrameCount']=119
                    elif mode=='decode_error':probe['decodeErrorCount']=1
                    elif mode=='decode_duration':probe['durationSeconds']=3
                    elif mode=='diagnostic_status':diagnostic['status']='untested'
                    elif mode=='diagnostic_node':diagnostic['nodeId']='foreign'
                    elif mode=='diagnostic_hash':diagnostic['rawProbeSha256']='sha256:'+'0'*64
                    elif mode=='diagnostic_reason':diagnostic['reason']=''
                    elif mode=='untested_required':policy['claims'][0]['status']='untested';data['environmentCaptured']['encoder_capability_matrix']=copy.deepcopy(policy['claims'])
                    elif mode=='fps_huge':policy['framesPerSecond']=10**401
                    elif mode=='fps_tiny':policy['framesPerSecond']=1e-308
                    else:next(m for m in data['measurements'] if m['id']=='worker_capabilities_reproducible')['actual']=False
                    write_yaml(config_path,config);write_yaml(report_path,report);write_yaml(probe_path,probe);write_yaml(diagnostic_path,diagnostic)
                    self.assertTrue(any('qualified worker capabilities' in e for e in validate(data)),(profile,mode))
                # An unclaimed optional codec may remain explicitly untested; never assert support.
                data=copy.deepcopy(original);report=copy.deepcopy(original_report);config=copy.deepcopy(original_config);diagnostic=copy.deepcopy(original_diagnostic);config['configuration']['workerCapabilityPolicy']['claims'][2]['status']='untested';data['environmentCaptured']['encoder_capability_matrix']=copy.deepcopy(config['configuration']['workerCapabilityPolicy']['claims']);report['claims'][2]['status']=diagnostic['status']='untested'
                write_yaml(config_path,config);write_yaml(report_path,report);write_yaml(probe_path,original_probe);write_yaml(diagnostic_path,diagnostic);self.assertEqual(validate(data),[])
                write_yaml(config_path,original_config);write_yaml(report_path,original_report);write_yaml(diagnostic_path,original_diagnostic)
                for status in ('fail','inconclusive'):
                    data=copy.deepcopy(original);data['environmentCaptured'].pop('workerCapabilitiesRef');self.assertEqual(validate(data,status),[])
                data=copy.deepcopy(original);data['environmentCaptured'].pop('workerCapabilitiesRef');write_yaml(path,data);self.assertTrue(any('qualified worker capabilities' in e for e in CHECK.validate_repository(root,profile,True,selected_pocs={'POC-01'})))
            finally:temp.cleanup()


    def test_196_worker_physical_scope_requires_exact_node_host_coverage(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-001',profile);path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path)
                prefix=str(index.parent.relative_to(root)).replace('\\','/');plan=load_yaml(self.plan_path(root,'POC-001'));defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];window=tuple(CHECK.utc(original['environmentCaptured']['executionWindow'][k]) for k in ('startedAt','finishedAt'))
                def validate(data,status='pass'):
                    errors=[];CHECK.validate_qualified_worker_capabilities(root,plan,data,prefix,status,window,defs,errors,{});return errors
                self.assertEqual(validate(original),[])
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-01'}),[])
                for mode in ('missing','string','boolean','empty','host_type','duplicate','foreign','missing_host','multihost','gate'):
                    data=copy.deepcopy(original);env=data['environmentCaptured'];scope=env['physical_host_scope']
                    if mode=='missing':env.pop('physical_host_scope')
                    elif mode=='string':env['physical_host_scope']='same-host unknown'
                    elif mode=='boolean':env['physical_host_scope']=True
                    elif mode=='empty':scope['physicalHostIds']=[]
                    elif mode=='host_type':scope['physicalHostIds']=[True]
                    elif mode=='duplicate':scope['physicalHostIds'].append(scope['physicalHostIds'][0])
                    elif mode=='foreign':scope['physicalHostIds'].append('foreign-host')
                    elif mode=='missing_host':scope['physicalHostIds'].pop()
                    elif mode=='multihost':scope['physicalMultiHostValidated']=not scope['physicalMultiHostValidated']
                    else:next(m for m in data['measurements'] if m['id']=='worker_physical_scope_recorded')['actual']=False
                    self.assertTrue(any('physical' in e for e in validate(data)),(profile,mode))
                for status in ('fail','inconclusive'):
                    data=copy.deepcopy(original);data['environmentCaptured'].pop('physical_host_scope');self.assertEqual(validate(data,status),[])
                data=copy.deepcopy(original);data['environmentCaptured']['physical_host_scope']='not a node-host mapping';write_yaml(path,data)
                self.assertTrue(any('physical' in e for e in CHECK.validate_repository(root,profile,True,selected_pocs={'POC-01'})))
            finally:temp.cleanup()


    def test_197_local_source_listing_and_assessment_require_bound_repeated_observations(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-006','local-v1');path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path);env=original['environmentCaptured'];report_path=root/env['sourceListingRef'];original_report=load_yaml(report_path);config_path=root/original_report['configurationRef'];original_config=load_yaml(config_path);basis_path=root/original_report['assessment'][0]['basisRef'];original_basis=load_yaml(basis_path)
            prefix=str(index.parent.relative_to(root)).replace('\\','/');plan=load_yaml(self.plan_path(root,'POC-006'));defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];window=tuple(CHECK.utc(env['executionWindow'][k]) for k in ('startedAt','finishedAt'))
            def validate(data,status='pass'):
                self.refresh_qualified_observation_fixture(root,data);errors=[];CHECK.validate_qualified_local_source_listing(root,plan,data,prefix,status,window,defs,errors,{});return errors
            self.assertEqual(CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-06'}),[]);self.assertEqual(validate(copy.deepcopy(original)),[])
            for mode in ('missing','shape','policy','source','sandbox','version','endpoint','input','single_run','duplicate_run','cursor','last_cursor','status','clock','duplicate_request','missing_object','version_changed','name_changed','duplicate_object','duplicate_policy','criterion','basis_missing','basis_version','basis_hash','basis_clock','basis_reason','rubric','score','gate'):
                data=copy.deepcopy(original);report=copy.deepcopy(original_report);config=copy.deepcopy(original_config);basis=copy.deepcopy(original_basis);policy=config['configuration']['localSourceListingPolicy'];page=report['runs'][1]['pages'][0]
                if mode=='missing':data['environmentCaptured'].pop('sourceListingRef')
                elif mode=='shape':report=True
                elif mode=='policy':config['configuration']['localSourceListingPolicy']=True
                elif mode in ('source','sandbox','version','endpoint'):report[dict(source='sourceId',sandbox='sandboxId',version='subjectVersion',endpoint='endpointURL')[mode]]='foreign'
                elif mode=='input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                elif mode=='single_run':report['runs'].pop()
                elif mode=='duplicate_run':report['runs'][1]['runId']=report['runs'][0]['runId']
                elif mode=='cursor':page['requestCursor']='wrong'
                elif mode=='last_cursor':report['runs'][1]['pages'][-1]['nextCursor']='unfinished'
                elif mode=='status':page['statusCode']=500
                elif mode=='clock':page['requestedAt']='2026-09-02T00:00:00Z'
                elif mode=='duplicate_request':page['requestId']=report['runs'][0]['pages'][0]['requestId']
                elif mode=='missing_object':page['objects']=[]
                elif mode=='version_changed':page['objects'][0]['versionId']='foreign'
                elif mode=='name_changed':page['objects'][0]['name']='changed unexpectedly'
                elif mode=='duplicate_object':page['objects'].append(copy.deepcopy(page['objects'][0]))
                elif mode=='duplicate_policy':policy['objects'].append(copy.deepcopy(policy['objects'][0]))
                elif mode=='criterion':report['assessment'][1]['criterionId']='api'
                elif mode=='basis_missing':report['assessment'][0]['basisRef']=prefix+'/raw/missing.yaml'
                elif mode=='basis_version':basis['subjectVersion']='foreign'
                elif mode=='basis_hash':report['assessment'][0]['basisSha256']='sha256:'+'0'*64
                elif mode=='basis_clock':basis['observedAt']='2026-09-03T00:03:22Z'
                elif mode=='basis_reason':basis['details']=''
                elif mode=='rubric':policy['criteria'][0]['weight']=True
                elif mode=='score':next(m for m in data['measurements'] if m['id']=='maintainability')['actual']=0.9
                else:next(m for m in data['measurements'] if m['id']=='listing_stability')['actual']=False
                write_yaml(report_path,report);write_yaml(config_path,config);write_yaml(basis_path,basis);self.assertTrue(any('qualified local source listing' in e for e in validate(data)),mode)
            write_yaml(config_path,original_config);write_yaml(basis_path,original_basis);report=copy.deepcopy(original_report);report['assessment'][0]['status']='limited';write_yaml(report_path,report);data=copy.deepcopy(original);next(m for m in data['measurements'] if m['id']=='maintainability')['actual']=0.875;self.assertEqual(validate(data),[])
            write_yaml(report_path,original_report)
            for status in ('fail','inconclusive'):
                data=copy.deepcopy(original);data['environmentCaptured'].pop('sourceListingRef');self.assertEqual(validate(data,status),[])
            data=copy.deepcopy(original);data['environmentCaptured'].pop('sourceListingRef');write_yaml(path,data);self.assertTrue(any('qualified local source listing' in e for e in CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-06'})))
            data['environmentCaptured']['acceptanceProfile']=CHECK.profile_identity('production');self.assertEqual(validate(data),[])
        finally:temp.cleanup()


    def test_198_metadata_profiling_requires_complete_names_pages_and_actual_range_validators(self):
        import sqlite3
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-005',profile);path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path);env=original['environmentCaptured'];report_path=root/env['metadataProfilingRef'];original_report=load_yaml(report_path);config_path=root/original_report['configurationRef'];original_config=load_yaml(config_path);files={root/a['ref']:(root/a['ref']).read_bytes() for a in env['rawExecutionArtifacts']}
                prefix=str(index.parent.relative_to(root)).replace('\\','/');plan=load_yaml(self.plan_path(root,'POC-005'));defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];window=tuple(CHECK.utc(env['executionWindow'][k]) for k in ('startedAt','finishedAt'));resource=next(r for r in original['resources'] if r['id']=='RES-METADATA-SCALE')
                def validate(data):
                    self.refresh_qualified_observation_fixture(root,data);errors=[];config=load_yaml(config_path);scan=config['configuration']['metadataScanPolicy'];connection=sqlite3.connect(':memory:')
                    connection.executescript('CREATE TABLE baseline(objectId TEXT PRIMARY KEY,kind TEXT,versionId TEXT,depth INTEGER,fileSizeBytes INTEGER);CREATE TABLE expected(eventId TEXT PRIMARY KEY,sequence INTEGER,objectId TEXT,operation TEXT,beforeVersion TEXT,afterVersion TEXT);')
                    for row in [json.loads(line) for line in (root/scan['baseline']['ref']).read_bytes().splitlines()]:connection.execute('INSERT INTO baseline VALUES (?,?,?,?,?)',tuple(row[k] for k in ('objectId','kind','versionId','depth','fileSizeBytes')))
                    for row in [json.loads(line) for line in (root/scan['expectedChanges']['ref']).read_bytes().splitlines()]:connection.execute('INSERT INTO expected VALUES (?,?,?,?,?,?)',tuple(row[k] for k in ('eventId','sequence','objectId','operation','beforeVersion','afterVersion')))
                    try:CHECK.validate_qualified_metadata_profiles(root,plan,data,prefix,window,defs,errors,{},resource,scan,connection)
                    except (ValueError,sqlite3.Error):errors.append('qualified metadata profiling: invalid retained stream or derived result')
                    finally:connection.close()
                    return errors
                def rewrite(descriptor,change):
                    p=root/descriptor['ref'];rows=[json.loads(line) for line in p.read_bytes().splitlines()];change(rows);raw=b''.join((json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n').encode() for r in rows);p.write_bytes(raw);descriptor.update(sha256='sha256:'+hashlib.sha256(raw).hexdigest(),count=len(rows))
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-05'}),[]);self.assertEqual(validate(copy.deepcopy(original)),[])
                for mode in ('missing','shape','policy','profile','input','source','build','manifest','filename_hash','filename_count','filename_missing','filename_duplicate','filename_changed','filename_depth','distribution','extensions','pages_missing','pages_hash','single_run','page_status','page_source','page_cursor','page_clock','page_identity','probe_missing','probe_duplicate','probe_version','probe_object','probe_clock','probe_hash','payload_size','probe_bytes','probe_status','probe_range','probe_header','validator_kind','validator_stable','validator_changed','gate'):
                    for file,raw in files.items():file.write_bytes(raw)
                    data=copy.deepcopy(original);report=copy.deepcopy(original_report);config=copy.deepcopy(original_config);policy=config['configuration']['metadataProfilingPolicy'];probe=report['probes'][2]
                    if mode=='missing':data['environmentCaptured'].pop('metadataProfilingRef')
                    elif mode=='shape':report=True
                    elif mode=='policy':config['configuration']['metadataProfilingPolicy']=True
                    elif mode=='profile':report['acceptanceProfile']=CHECK.profile_identity('production' if profile=='local-v1' else 'local-v1')
                    elif mode=='input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                    elif mode=='source':report['sourceIdentity']['sourceId']='foreign'
                    elif mode=='build':report['scannerBuild']='foreign'
                    elif mode=='manifest':report['manifestId']='foreign'
                    elif mode=='filename_hash':report['filenameObjects']['sha256']='sha256:'+'0'*64
                    elif mode=='filename_count':report['filenameObjects']['count']+=1
                    elif mode=='filename_missing':rewrite(report['filenameObjects'],lambda rows:rows.pop())
                    elif mode=='filename_duplicate':rewrite(report['filenameObjects'],lambda rows:rows.append(copy.deepcopy(rows[0])))
                    elif mode=='filename_changed':rewrite(report['filenameObjects'],lambda rows:rows[0].update(name='foreign'))
                    elif mode=='filename_depth':rewrite(report['filenameObjects'],lambda rows:rows[0].update(path='wrong/depth'))
                    elif mode=='distribution':report['filenameDistributions']['characterSet']['ascii']+=1
                    elif mode=='extensions':policy['extensionCategories'].append('txt')
                    elif mode=='pages_missing':report.pop('providerPages')
                    elif mode=='pages_hash':report['providerPages']['sha256']='sha256:'+'0'*64
                    elif mode=='single_run':rewrite(report['providerPages'],lambda rows:rows.__setitem__(slice(None),[r for r in rows if r['runId']=='synthetic-provider-list-0']))
                    elif mode=='page_status':rewrite(report['providerPages'],lambda rows:rows[0].update(statusCode=500))
                    elif mode=='page_source':rewrite(report['providerPages'],lambda rows:rows[0]['sourceIdentity'].update(sourceId='foreign'))
                    elif mode=='page_cursor':rewrite(report['providerPages'],lambda rows:rows[0].update(requestCursor='unexpected'))
                    elif mode=='page_clock':rewrite(report['providerPages'],lambda rows:rows[0].update(requestedAt='2026-09-02T00:00:00Z'))
                    elif mode=='page_identity':rewrite(report['providerPages'],lambda rows:rows[0]['objects'].update(count=100))
                    elif mode=='probe_missing':report['probes'].pop()
                    elif mode=='probe_duplicate':report['probes'][1]['requestId']=report['probes'][0]['requestId']
                    elif mode=='probe_version':probe['objectVersion']='foreign'
                    elif mode=='probe_object':probe['objectId']='foreign'
                    elif mode=='probe_clock':probe['observedAt']='2026-09-02T00:00:00Z'
                    elif mode=='probe_hash':probe['responseSha256']='sha256:'+'0'*64
                    elif mode=='payload_size':
                        payload=policy['baselinePayload'];file=root/payload['ref'];raw=file.read_bytes()+b'X';file.write_bytes(raw);payload['sha256']='sha256:'+hashlib.sha256(raw).hexdigest()
                    elif mode=='probe_bytes':probe['responseByteCount']+=1
                    elif mode=='probe_status':probe['statusCode']=200
                    elif mode=='probe_range':probe['requestRange']='bytes=3-4'
                    elif mode=='probe_header':probe['contentRange']='bytes 3-4/100'
                    elif mode=='validator_kind':probe['versionValidator']='unexpected'
                    elif mode=='validator_stable':report['validatorStableOnUnchanged']=False
                    elif mode=='validator_changed':report['validatorChangedOnUpdate']=False
                    else:next(m for m in data['measurements'] if m['id']=='provider_characteristics_profiled')['actual']=False
                    write_yaml(config_path,config);write_yaml(report_path,report);self.assertTrue(validate(data),(profile,mode))
                # Unsupported Range and equivalent version tokens remain truthful valid profiles.
                for file,raw in files.items():file.write_bytes(raw)
                report=copy.deepcopy(original_report);config=copy.deepcopy(original_config);policy=config['configuration']['metadataProfilingPolicy'];policy['rangeDisposition']=report['rangeDisposition']='unsupported';policy['validatorKind']=report['validatorKind']='version_token'
                for probe in report['probes']:
                    probe['etag']='';probe['versionValidator']=probe['objectVersion']
                    if probe['case'] in ('bounded','unsatisfiable'):
                        (root/probe['responseRef']).write_bytes(b'');probe.update(statusCode=405,contentRange='',responseSha256='sha256:'+hashlib.sha256(b'').hexdigest(),responseByteCount=0)
                write_yaml(config_path,config);write_yaml(report_path,report);self.assertEqual(validate(copy.deepcopy(original)),[])
                for file,raw in files.items():file.write_bytes(raw)
                write_yaml(config_path,original_config);write_yaml(report_path,original_report);data=copy.deepcopy(original);data['environmentCaptured'].pop('metadataProfilingRef');write_yaml(path,data);self.assertTrue(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-05'}))
            finally:temp.cleanup()


    def test_183_streamed_metadata_representation_reads_one_million_records_bounded(self):
        # Actual million-record parser coverage; no scanner throughput/POC claim.
        with tempfile.TemporaryDirectory(prefix='guize-million-records-') as folder:
            path=Path(folder)/'metadata.jsonl';digest=hashlib.sha256();total=1000000
            with path.open('wb') as output:
                for index in range(total):
                    line=(json.dumps(dict(objectId='synthetic-object-'+str(index),kind='file',versionId='version-1',depth=1,fileSizeBytes=1),separators=(',',':'))+'\n').encode();output.write(line);digest.update(line)
            schema=load_yaml(self.repo/'specs/poc/program.schema.yaml')['$defs']['metadataObjectRecord'];original_open=Path.open
            class BoundedReader:
                def __init__(self,handle):self.handle=handle
                def __enter__(self):self.handle.__enter__();return self
                def __exit__(self,*args):return self.handle.__exit__(*args)
                def readline(self,size):
                    self.assert_size=size
                    if not 0<size<=CHECK.ARTIFACT_CHUNK_BYTES+1:raise AssertionError('unbounded metadata line read')
                    return self.handle.readline(size)
                def read(self,*args):raise AssertionError('manifest materialization forbidden')
            def opening(file,*args,**kwargs):
                handle=original_open(file,*args,**kwargs)
                return BoundedReader(handle) if file==path and args and args[0]=='rb' else handle
            with mock.patch.object(Path,'open',opening):
                iterator=CHECK.streamed_metadata_records(path,schema);count=0
                while True:
                    try:next(iterator);count+=1
                    except StopIteration as terminal:observed_count,sha=terminal.value;break
            self.assertEqual((count,observed_count,sha),(total,total,'sha256:'+digest.hexdigest()))

    def test_184_frontend_comparison_binds_both_builds_fixed_scenarios_and_rubric(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-008',profile);path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path);report_path=root/original['environmentCaptured']['frontendComparisonRef'];report_original=load_yaml(report_path);config_path=root/report_original['configurationRef'];config_original=load_yaml(config_path);files={root/a['ref']:(root/a['ref']).read_bytes() for a in original['environmentCaptured']['rawExecutionArtifacts']}
                def validate(data):
                    self.refresh_qualified_observation_fixture(root,data);write_yaml(path,data)
                    return CHECK.validate_repository(root,profile,True,selected_pocs={'POC-08'})
                self.assertEqual(validate(copy.deepcopy(original)),[])
                for mode in ('missing','arbitrary','policy','config','profile','input','fixture_ref','missing_candidate','duplicate_candidate','version','lock_hash','build_status','build_time','bundle_count','bundle_hash','missing_scenario','duplicate_scenario','scenario_build','scenario_fixture','scenario_input','scenario_driver','scenario_status','missing_action','action_result','action_time','scenario_measurement','missing_score','duplicate_score','rubric','assessor','score_build','grade','grade_nan','basis','score_time','score_refs','weight','criterion','coverage','bundle','maintainability','gate'):
                    for file,raw in files.items():file.write_bytes(raw)
                    data=copy.deepcopy(original);report=copy.deepcopy(report_original);config=copy.deepcopy(config_original);policy=config['configuration']['frontendComparisonPolicy'];row=report['candidates'][0];build_path=root/row['buildRef'];build=load_yaml(build_path);trace_path=root/row['scenarios'][0]['observationRef'];trace=load_yaml(trace_path);score_path=root/row['scores'][0]['observationRef'];score=load_yaml(score_path)
                    if mode=='missing':data['environmentCaptured'].pop('frontendComparisonRef')
                    elif mode=='arbitrary':report=None
                    elif mode=='policy':config['configuration']['frontendComparisonPolicy']=True
                    elif mode=='config':report['configurationRef']=data['environmentCaptured']['acceptanceProfileConfigurationRef']
                    elif mode=='profile':report['acceptanceProfile']=CHECK.profile_identity('production' if profile=='local-v1' else 'local-v1')
                    elif mode=='input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                    elif mode=='fixture_ref':report['inputFixtureRef']=data['rawOutputRefs'][0]
                    elif mode=='missing_candidate':report['candidates'].pop()
                    elif mode=='duplicate_candidate':report['candidates'][-1]['candidateId']='vue'
                    elif mode=='version':build['identity']['frameworkVersion']='foreign-framework'
                    elif mode=='lock_hash':policy['candidates'][0]['lockSha256']='sha256:'+'0'*64
                    elif mode=='build_status':build['exitCode']=1
                    elif mode=='build_time':build['finishedAt']='2026-09-03T00:00:05Z'
                    elif mode=='bundle_count':build['bundles'][0]['byteCount']+=1
                    elif mode=='bundle_hash':build['bundles'][0]['sha256']='sha256:'+'0'*64
                    elif mode=='missing_scenario':row['scenarios'].pop()
                    elif mode=='duplicate_scenario':row['scenarios'][-1]['scenarioId']=row['scenarios'][0]['scenarioId']
                    elif mode=='scenario_build':trace['buildId']='foreign-build'
                    elif mode=='scenario_fixture':trace['fixtureId']='foreign-fixture'
                    elif mode=='scenario_input':trace['inputSha256']='sha256:'+'0'*64
                    elif mode=='scenario_driver':trace['scenarioDriverBuild']='foreign-driver'
                    elif mode=='scenario_status':trace['status']='failed'
                    elif mode=='missing_action':trace['actions'].pop()
                    elif mode=='action_result':trace['actions'][0]['result']={'unrelated':'success'}
                    elif mode=='action_time':trace['actions'][0]['finishedAt']='2026-09-03T00:00:01Z'
                    elif mode=='scenario_measurement':trace['measurements'][0]['value']+=1
                    elif mode=='missing_score':row['scores'].pop()
                    elif mode=='duplicate_score':row['scores'][-1]['criterionId']=row['scores'][0]['criterionId']
                    elif mode=='rubric':score['rubricVersion']='foreign-rubric'
                    elif mode=='assessor':score['assessorId']='unapproved-assessor'
                    elif mode=='score_build':score['buildId']='foreign-build'
                    elif mode=='grade':score['grade']=9
                    elif mode=='grade_nan':score['grade']=float('nan')
                    elif mode=='basis':score['basis']='UNKNOWN'
                    elif mode=='score_time':score['observedAt']='2026-09-03T00:00:02Z'
                    elif mode=='score_refs':score['scenarioRefs'][0]=data['rawOutputRefs'][0]
                    elif mode=='weight':policy['criteria'][0]['weight']=float('nan')
                    elif mode=='criterion':policy['criteria'][0]['criterionId']='unapproved-criterion'
                    elif mode in ('coverage','bundle','maintainability'):
                        metric={'coverage':'prototype_coverage','bundle':'bundle_baseline','maintainability':'maintainability_score'}[mode];next(m for m in data['measurements'] if m['id']==metric)['actual']+=1
                    else:next(m for m in data['measurements'] if m['id']=='million_row_virtual_list_equivalent')['actual']=False
                    if report is None:report_path.write_text('Unrelated frontend success assertions\n',encoding='utf8')
                    else:write_yaml(report_path,report)
                    write_yaml(config_path,config);write_yaml(build_path,build);write_yaml(trace_path,trace);write_yaml(score_path,score);self.assertTrue(any('qualified frontend comparison' in e for e in validate(data)),(profile,mode))
                # Identical functional results can have different valid DOM window sizes.
                input_path=root/report_original['inputFixtureRef'];input_original=load_yaml(input_path)
                for mode in ('valid_window','missing_counts','short_input','full_dom','wrong_unit','fractional_input','fractional_dom','zero_dom','bool_dom','invalid_viewport','invalid_overscan','unbounded_window','missing_window'):
                    for file,raw in files.items():file.write_bytes(raw)
                    data=copy.deepcopy(original);fixture=copy.deepcopy(input_original);million=next(s for s in fixture['scenarios'] if s['scenarioId']=='million_row_virtual_list_equivalent');trace_path=root/report_original['candidates'][0]['scenarios'][0]['observationRef'];trace=load_yaml(trace_path)
                    if mode=='valid_window':trace['measurements'][2]['value']=35
                    elif mode=='missing_counts':trace['measurements']=trace['measurements'][:1]
                    elif mode=='short_input':trace['measurements'][1]['value']=999999
                    elif mode=='full_dom':trace['measurements'][2]['value']=1000000
                    elif mode=='wrong_unit':trace['measurements'][1]['unit']='ms'
                    elif mode=='fractional_input':trace['measurements'][1]['value']=1000000.0
                    elif mode=='fractional_dom':trace['measurements'][2]['value']=30.5
                    elif mode=='zero_dom':trace['measurements'][2]['value']=0
                    elif mode=='bool_dom':trace['measurements'][2]['value']=True
                    else:
                        if mode=='invalid_viewport':million['arguments']['viewportRows']=0
                        elif mode=='invalid_overscan':million['arguments']['overscanRows']=-1
                        elif mode=='unbounded_window':million['arguments']['viewportRows']=1000000
                        else:million['arguments'].pop('overscanRows')
                        write_yaml(input_path,fixture);digest='sha256:'+hashlib.sha256(input_path.read_bytes()).hexdigest();sample=data['samples'][0];sample['checksum']=digest;approval=load_yaml(root/sample['approvalRef']);approval['checksum']=digest;write_yaml(root/sample['approvalRef'],approval);record=next(r for r in data['environmentCaptured']['inputSampleArtifacts'] if r['sampleId']==sample['id']);record.update(byteCount=len(input_path.read_bytes()),sha256=digest);report=copy.deepcopy(report_original);report['inputFixtureSha256']=digest;report['inputSamples'][0]['checksum']=digest;write_yaml(report_path,report)
                        for row in report['candidates']:
                            for case in row['scenarios']:
                                location=root/case['observationRef'];other=load_yaml(location);other['inputSha256']=digest;write_yaml(location,other)
                        trace=load_yaml(trace_path)
                    write_yaml(trace_path,trace);errors=validate(data)
                    if mode=='valid_window':self.assertEqual(errors,[],(profile,mode))
                    else:self.assertTrue(any('qualified frontend comparison' in e for e in errors),(profile,mode))

            finally:temp.cleanup()
        for profile in ('local-v1','production'):
            for status in ('fail','inconclusive'):
                temp,root=self.temp_repo()
                try:
                    index=self.make_profile_slot(root,'POC-008',profile,status=status);record=load_yaml(root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef']);self.assertNotIn('frontendComparisonRef',record['environmentCaptured']);self.assertEqual(CHECK.validate_repository(root,profile,False,selected_pocs={'POC-08'}),[])
                finally:temp.cleanup()

    def test_185_media_negative_matrix_binds_actual_failures_cleanup_fencing_and_acl(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-002',profile);path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path);report_path=root/original['environmentCaptured']['mediaNegativeRef'];report_original=load_yaml(report_path);config_path=root/report_original['configurationRef'];config_original=load_yaml(config_path);files={root/a['ref']:(root/a['ref']).read_bytes() for a in original['environmentCaptured']['rawExecutionArtifacts']}
                def validate(data):
                    self.refresh_qualified_observation_fixture(root,data);write_yaml(path,data);return CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'})
                self.assertEqual(validate(copy.deepcopy(original)),[])
                for mode in ('missing','arbitrary','policy','profile','input','job','version','node','missing_target','target','input_read','denied_outbound','missing_limit','not_exceeded','multiple_exceeded','termination','limit_cleanup','limit_publish','elapsed_clock','partial_empty','retry_job','old_epoch','lifecycle_clock','duplicate_terminal','cancel_process','cancel_before','cancel_partial_empty','cancel_job','cancel_cleanup','cancel_publish','cancel_partial','published_hash','missing_probe','probe_output','probe_input','probe_node','probe_build','probe_decoder','probe_codec','probe_frames','probe_errors','probe_epoch','probe_clock','missing_fencing','late_publish','duplicate_result','completion_epoch','missing_seek','stale_slots','revoked_bytes','seek_epoch','seek_grant','missing_hls','cross_user','expired_grant','revoked_decision','origin_read','cache_hash','hls_version','hls_acl','hls_time','gate'):
                    for file,raw in files.items():file.write_bytes(raw)
                    data=copy.deepcopy(original);report=copy.deepcopy(report_original);config=copy.deepcopy(config_original);policy=config['configuration']['mediaNegativePolicy'];row=report['nodes'][0];target=row['deniedTargets'][0];limit=row['limitCases'][0];life=row['lifecycle'];seek=row['seekCases'][1];access=report['accessCases'][1]
                    if mode=='missing':data['environmentCaptured'].pop('mediaNegativeRef')
                    elif mode=='arbitrary':report=None
                    elif mode=='policy':config['configuration']['mediaNegativePolicy']=True
                    elif mode=='profile':report['acceptanceProfile']=CHECK.profile_identity('production' if profile=='local-v1' else 'local-v1')
                    elif mode=='input':report['inputSha256']='sha256:'+'0'*64
                    elif mode=='job':report['jobId']='foreign-job'
                    elif mode=='version':report['assetVersion']='foreign-version'
                    elif mode=='node':row['identity']['encoderBuild']='foreign-build'
                    elif mode=='missing_target':row['deniedTargets'].pop()
                    elif mode=='target':target['target']='https://unapproved.invalid/input'
                    elif mode=='input_read':target['inputBytesRead']=1
                    elif mode=='denied_outbound':(root/target['outboundRef']).write_bytes(b'Unexpected outbound bytes')
                    elif mode=='missing_limit':row['limitCases'].pop()
                    elif mode=='not_exceeded':limit['observed']['cpuSeconds']=policy['limits']['cpuSeconds']
                    elif mode=='multiple_exceeded':limit['observed']['memoryBytes']=policy['limits']['memoryBytes']+1
                    elif mode=='termination':limit['processStatus']='running'
                    elif mode=='limit_cleanup':limit['remainingTemporaryBytes']=1
                    elif mode=='limit_publish':limit['publicationCount']=1
                    elif mode=='elapsed_clock':row['limitCases'][2]['observed']['elapsedSeconds']=7
                    elif mode=='partial_empty':(root/life['partialRef']).write_bytes(b'')
                    elif mode=='retry_job':life['retryJobId']='foreign-job'
                    elif mode=='old_epoch':life['currentAttemptEpoch']=life['oldAttemptEpoch']
                    elif mode=='lifecycle_clock':life['retriedAt']='2026-09-03T00:04:01Z'
                    elif mode=='duplicate_terminal':life['terminalResultCount']=2
                    elif mode=='cancel_process':life['activeProcessCount']=1
                    elif mode=='cancel_before':life['cancelledProcessStatusBefore']='terminated'
                    elif mode=='cancel_partial_empty':(root/life['cancelledPartialRef']).write_bytes(b'')
                    elif mode=='cancel_job':life['cancelJobId']=policy['jobId']
                    elif mode=='cancel_cleanup':life['remainingOutputBytes']=1
                    elif mode=='cancel_publish':life['cancelledAttemptPublicationCount']=1
                    elif mode=='cancel_partial':life['cancelledPartialPublishable']=True
                    elif mode=='published_hash':life['publishedSha256']='sha256:'+'0'*64
                    elif mode=='missing_probe':life['retryProbeRef']=data['rawOutputRefs'][0]
                    elif mode.startswith('probe_'):
                        probe_path=root/life['retryProbeRef'];probe=load_yaml(probe_path);field={'probe_output':'outputSha256','probe_input':'inputSha256','probe_node':'nodeId','probe_build':'encoderBuild','probe_decoder':'decoderBuild','probe_codec':'codec','probe_frames':'decodedFrameCount','probe_errors':'decodeErrorCount','probe_epoch':'attemptEpoch','probe_clock':'finishedAt'}[mode]
                        probe[field]='sha256:'+'0'*64 if mode in ('probe_output','probe_input') else 1 if mode=='probe_errors' else 3 if mode=='probe_epoch' else 999 if mode=='probe_frames' else '2026-09-03T00:04:07Z' if mode=='probe_clock' else 'foreign-probe-value';write_yaml(probe_path,probe)

                    elif mode=='missing_fencing':life['submissions'].pop()
                    elif mode=='late_publish':life['submissions'][2]['publicationDelta']=1
                    elif mode=='duplicate_result':life['submissions'][1]['terminalResultDelta']=1
                    elif mode=='completion_epoch':life['submissions'][0]['attemptEpoch']=1
                    elif mode=='missing_seek':row['seekCases'].pop()
                    elif mode=='stale_slots':seek['newReservedSlots']=1
                    elif mode=='revoked_bytes':(root/row['seekCases'][2]['responseRef']).write_bytes(b'Protected bytes')
                    elif mode=='seek_epoch':seek['requestedSeekEpoch']=seek['currentSeekEpoch']
                    elif mode=='seek_grant':seek['grantId']='foreign-grant'
                    elif mode=='missing_hls':report['accessCases'].pop()
                    elif mode=='cross_user':access['userId']=policy['authorizedUserId']
                    elif mode=='expired_grant':report['accessCases'][2]['grantId']=policy['currentGrantId']
                    elif mode=='revoked_decision':report['accessCases'][3]['decision']='allowed'
                    elif mode=='origin_read':report['accessCases'][4]['originContactCount']=1
                    elif mode=='cache_hash':report['accessCases'][15]['responseSha256']='sha256:'+'0'*64
                    elif mode=='hls_version':access['assetVersion']='foreign-version'
                    elif mode=='hls_acl':access['aclVersion']='foreign-acl'
                    elif mode=='hls_time':report['accessCases'][0]['observedAt']=policy['grantValidUntil']
                    else:next(m for m in data['measurements'] if m['id']=='hls_acl_and_revocation')['actual']=False
                    if report is None:report_path.write_text('Unrelated media success assertions\n',encoding='utf8')
                    else:write_yaml(report_path,report)
                    write_yaml(config_path,config);self.assertTrue(any('qualified media negative matrix' in e for e in validate(data)),(profile,mode))
            finally:temp.cleanup()
        for profile in ('local-v1','production'):
            for mode in ('partial_alias','original_alias','cancel_alias','distinct_same_bytes'):
                temp,root=self.temp_repo()
                try:
                    index=self.make_profile_slot(root,'POC-002',profile);path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];data=load_yaml(path);report_path=root/data['environmentCaptured']['mediaNegativeRef'];report=load_yaml(report_path);life=report['nodes'][0]['lifecycle'];probe_path=root/life['retryProbeRef'];probe=load_yaml(probe_path)
                    if mode in ('original_alias','distinct_same_bytes'):
                        original_run=data['environmentCaptured']['workerEncodeExecutions'][0];link=root/life['publishedRef'];link.unlink()
                        if mode=='original_alias':link.hardlink_to(root/original_run['outputArtifactRef'])
                        else:link.write_bytes((root/original_run['outputArtifactRef']).read_bytes())
                        life['publishedSha256']=original_run['outputSha256'];probe['outputSha256']=life['publishedSha256'];write_yaml(probe_path,probe)
                    else:
                        field='partialRef' if mode=='partial_alias' else 'cancelledPartialRef';digest='partialSha256' if mode=='partial_alias' else 'cancelledPartialSha256';link=root/life[field];link.unlink();link.hardlink_to(root/life['publishedRef']);life[digest]=life['publishedSha256']
                    write_yaml(report_path,report);self.refresh_qualified_observation_fixture(root,data);write_yaml(path,data);errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-02'})
                    if mode=='distinct_same_bytes':self.assertEqual(errors,[],(profile,mode))
                    else:self.assertTrue(any('physically distinct' in e for e in errors),(profile,mode))
                finally:temp.cleanup()
        for profile in ('local-v1','production'):
            for status in ('fail','inconclusive'):
                temp,root=self.temp_repo()
                try:
                    index=self.make_profile_slot(root,'POC-002',profile,status=status);record=load_yaml(root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef']);self.assertNotIn('mediaNegativeRef',record['environmentCaptured']);self.assertEqual(CHECK.validate_repository(root,profile,False,selected_pocs={'POC-02'}),[])
                finally:temp.cleanup()

    def test_186_local_storage_binds_reads_integrity_state_and_safe_lifecycle(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-004','local-v1');path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path);report_path=root/original['environmentCaptured']['localStorageRef'];report_original=load_yaml(report_path);config_path=root/report_original['configurationRef'];config_original=load_yaml(config_path);files={root/a['ref']:(root/a['ref']).read_bytes() for a in original['environmentCaptured']['rawExecutionArtifacts']}
            def validate(data):
                self.refresh_qualified_observation_fixture(root,data);write_yaml(path,data);return CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-04'})
            self.assertEqual(validate(copy.deepcopy(original)),[])
            for mode in ('missing','arbitrary','policy','root','build','profile','input','missing_object','version','missing_request','path','credential','unauthorized_bytes','full_hash','bounded_bytes','suffix_header','unsatisfiable','concurrency','duplicate_request','baseline_metadata','baseline_invalid','copy_missing','incomplete_promoted','hash_copy_valid','copy_state','copy_old_snapshot','disconnect_attempts','disconnect_full_hash','disconnect_promoted','disconnect_restart','recovery_old_snapshot','backup_hash','restore_hash','restore_metadata','restore_state_bytes','backup_time','eviction_asset','eviction_replica','eviction_retention','eviction_cache','eviction_time','migration_old_missing','migration_unverified','migration_pending_verified','migration_pending_asset','migration_pending_version','migration_hash','migration_version','migration_state_time','capacity_phase','capacity_order','capacity_admission','capacity_floor','capacity_count','throughput','latency','gate'):
                for file,raw in files.items():file.write_bytes(raw)
                data=copy.deepcopy(original);report=copy.deepcopy(report_original);config=copy.deepcopy(config_original);policy=config['configuration']['localStoragePolicy'];row=report['objects'][0];request=row['requests'][0];copy_case=row['copyRejections'][0];backup=row['backupRestore'];migration=row['migration']
                def change_state(ref,change):
                    location=root/ref;state=load_yaml(location);change(state);write_yaml(location,state)
                def change_body(record,payload,field='responseRef',digest='responseSha256'):
                    (root/record[field]).write_bytes(payload);record[digest]='sha256:'+hashlib.sha256(payload).hexdigest()
                if mode=='missing':data['environmentCaptured'].pop('localStorageRef')
                elif mode=='arbitrary':report=None
                elif mode=='policy':config['configuration']['localStoragePolicy']=True
                elif mode=='root':policy['sandboxRoot']='foreign-storage-root'
                elif mode=='build':policy['openlistBuild']='foreign-openlist-build'
                elif mode=='profile':report['acceptanceProfile']=CHECK.profile_identity('production')
                elif mode=='input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                elif mode=='missing_object':report['objects'].pop()
                elif mode=='version':policy['objects'][0]['versionId']='foreign-version'
                elif mode=='missing_request':row['requests'].pop()
                elif mode=='path':request['objectURL']='http://127.0.0.1/foreign-object'
                elif mode=='credential':request['authRef']=policy['invalidAuthRef']
                elif mode=='unauthorized_bytes':change_body(row['requests'][4],b'Protected source bytes')
                elif mode=='full_hash':change_body(request,b'Unrelated full source response')
                elif mode=='bounded_bytes':change_body(row['requests'][1],b'BADBYTES')
                elif mode=='suffix_header':row['requests'][2]['contentRange']='bytes 0-3/99'
                elif mode=='unsatisfiable':row['requests'][3]['statusCode']=200
                elif mode=='concurrency':row['requests'][7]['startedAt']='2026-09-03T00:02:02Z';row['requests'][7]['finishedAt']='2026-09-03T00:02:03Z'
                elif mode=='duplicate_request':row['requests'][1]['requestId']=request['requestId']
                elif mode=='baseline_metadata':change_state(report['baselineStateRef'],lambda s:s['assets'][0]['metadata'].update(title='Changed metadata'))
                elif mode=='baseline_invalid':write_yaml(root/report['baselineStateRef'],True)
                elif mode=='copy_missing':row['copyRejections'].pop()
                elif mode=='incomplete_promoted':copy_case['promotionDecision']='verified'
                elif mode=='hash_copy_valid':
                    source=data['environmentCaptured']['inputSampleArtifacts'][0]['inputArtifactRef'];change_body(row['copyRejections'][1],(root/source).read_bytes(),'payloadRef','sha256')
                elif mode=='copy_state':change_state(copy_case['afterStateRef'],lambda s:s['replicas'].append({**s['replicas'][0],'replicaId':'unsafe-promoted-replica'}))
                elif mode=='copy_old_snapshot':copy_case['afterStateRef']=report['baselineStateRef']
                elif mode=='disconnect_attempts':row['disconnect']['attempts']=row['disconnect']['attempts'][-1:]
                elif mode=='disconnect_full_hash':change_body(row['disconnect']['attempts'][-1],b'Corrupt recovered data')
                elif mode=='disconnect_promoted':row['disconnect']['attempts'][0]['partialPromotedCount']=1
                elif mode=='disconnect_restart':row['disconnect']['serviceRestartedAt']='2026-09-03T00:04:06Z'
                elif mode=='recovery_old_snapshot':row['disconnect']['afterStateRef']=report['baselineStateRef']
                elif mode=='backup_hash':change_body(backup,b'Corrupt backup','backupDataRef','backupSha256')
                elif mode=='restore_hash':change_body(backup,b'Corrupt restored object','restoredDataRef','restoredSha256')
                elif mode=='restore_metadata':change_state(backup['restoredStateRef'],lambda s:s['assets'][0]['metadata'].update(title='Wrong restored metadata'))
                elif mode=='restore_state_bytes':change_state(backup['restoredStateRef'],lambda s:s['replicas'][0].update(payloadRef=policy['baselineState']['replicas'][0]['payloadRef']))
                elif mode=='backup_time':change_state(backup['backupStateRef'],lambda s:s.update(observedAt='2026-09-03T00:04:00Z'))
                elif mode=='eviction_asset':change_state(row['evictionAfterStateRef'],lambda s:s['assets'][0]['metadata'].update(title='Eviction changed asset'))
                elif mode=='eviction_replica':change_state(row['evictionAfterStateRef'],lambda s:s['replicas'].clear())
                elif mode=='eviction_retention':change_state(row['evictionAfterStateRef'],lambda s:s['retention'][0].update(state='released'))
                elif mode=='eviction_cache':change_state(row['evictionAfterStateRef'],lambda s:s['caches'].extend(copy.deepcopy(policy['baselineState']['caches'])))
                elif mode=='eviction_time':row['evictedAt']='2026-09-03T00:05:31Z'
                elif mode=='migration_old_missing':change_state(migration['copyingStateRef'],lambda s:s['replicas'].pop(0))
                elif mode=='migration_unverified':change_state(migration['verifiedStateRef'],lambda s:s['replicas'][-1].update(state='COPYING'))
                elif mode=='migration_pending_verified':change_state(migration['copyingStateRef'],lambda s:s['replicas'][-1].update(state='VERIFIED'))
                elif mode=='migration_pending_asset':change_state(migration['copyingStateRef'],lambda s:s['replicas'][-1].update(assetId='foreign-asset'))
                elif mode=='migration_pending_version':change_state(migration['copyingStateRef'],lambda s:s['replicas'][-1].update(versionId='foreign-version'))
                elif mode=='migration_hash':
                    location=root/migration['verifiedStateRef'];state=load_yaml(location);replica=state['replicas'][-1];change_body(replica,b'Corrupt migrated replica','payloadRef','sha256');write_yaml(location,state)
                elif mode=='migration_version':change_state(migration['verifiedStateRef'],lambda s:s['replicas'][-1].update(versionId='foreign-version'))
                elif mode=='migration_state_time':change_state(migration['verifiedStateRef'],lambda s:s.update(observedAt='2026-09-03T00:05:59Z'))
                elif mode=='capacity_phase':report['capacityObservations'][2]['phase']='fill'
                elif mode=='capacity_order':
                    observations=report['capacityObservations'];report['capacityObservations']=[observations[0],observations[4],observations[1],observations[2],observations[3]]
                    for i,item in enumerate(report['capacityObservations']):item['observedAt']=f'2026-09-03T00:07:0{i}Z'
                elif mode=='capacity_admission':report['capacityObservations'][2]['admission']='admitted'
                elif mode=='capacity_floor':report['capacityObservations'][2]['freeBytes']=120
                elif mode in ('capacity_count','throughput','latency'):
                    metric={'capacity_count':'local_minimum_free_bytes','throughput':'sequential_throughput','latency':'io_latency'}[mode];next(m for m in data['measurements'] if m['id']==metric)['actual']+=1
                else:next(m for m in data['measurements'] if m['id']=='local_backup_restore_verified')['actual']=False
                if report is None:report_path.write_text('Unrelated storage success assertions\n',encoding='utf8')
                else:write_yaml(report_path,report)
                write_yaml(config_path,config);self.assertTrue(any('qualified local storage' in e for e in validate(data)),mode)
        finally:temp.cleanup()
        # Exact eight-byte data can exercise bounded, suffix and unsatisfiable Range controls.
        from unittest.mock import patch
        native_fixture=self.prepare_qualified_local_storage_fixture
        def eight_byte_fixture(root,execution,prefix):
            for sample in execution['samples']:
                record=next(r for r in execution['environmentCaptured']['inputSampleArtifacts'] if r['sampleId']==sample['id']);payload=b'01234567';(root/record['inputArtifactRef']).write_bytes(payload);digest='sha256:'+hashlib.sha256(payload).hexdigest();sample['checksum']=digest;record.update(byteCount=8,sha256=digest);approval=load_yaml(root/sample['approvalRef']);approval['checksum']=digest;write_yaml(root/sample['approvalRef'],approval)
            native_fixture(root,execution,prefix)
        temp,root=self.temp_repo()
        try:
            with patch.object(self,'prepare_qualified_local_storage_fixture',new=eight_byte_fixture):self.make_profile_slot(root,'POC-004','local-v1')
            self.assertEqual(CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-04'}),[])
        finally:temp.cleanup()
        # Same-clock and repeated legitimate observations preserve the ordered lifecycle.
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-004','local-v1');path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];data=load_yaml(path);report_path=root/data['environmentCaptured']['localStorageRef'];report=load_yaml(report_path);observations=report['capacityObservations'];report['capacityObservations']=[observations[0],observations[1],copy.deepcopy(observations[1]),observations[2],observations[3],observations[4]]
            for item in report['capacityObservations']:item['observedAt']='2026-09-03T00:07:00Z'
            write_yaml(report_path,report);self.refresh_qualified_observation_fixture(root,data);write_yaml(path,data);self.assertEqual(CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-04'}),[])
        finally:temp.cleanup()
        for profile,status in (('local-v1','fail'),('local-v1','inconclusive'),('production','pass')):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-004',profile,status=status);record=load_yaml(root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef']);self.assertNotIn('localStorageRef',record['environmentCaptured']);errors=CHECK.validate_repository(root,profile,status=='pass',selected_pocs={'POC-04'})
                if profile=='production':self.assertEqual(errors,['deferred production qualification POC-04: production outcome validation is not implemented; PASS unavailable'])
                else:self.assertEqual(errors,[])
            finally:temp.cleanup()

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
            self.make_profile_slot(root,profile='production',status='inconclusive')
            for ref,content in old_files.items(): self.assertEqual((root/ref).read_bytes(),content)
            self.assertEqual(CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-06'}),[])
            self.assertEqual(CHECK.validate_repository(root,'production',False,selected_pocs={'POC-06'}),[])
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
            self.assertEqual(CHECK.validate_repository(root,'production',True,selected_pocs={'POC-06'}),self.deferred_production_errors('production','POC-06'))
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
                    self.assertEqual(CHECK.validate_repository(root, profile, True, selected_pocs={'POC-06'}), self.deferred_production_errors(profile,'POC-06'))
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
                        self.assertEqual(CHECK.validate_repository(root, profile, True, selected_pocs={'POC-06'}), self.deferred_production_errors(profile,'POC-06'))
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
                    plan=load_yaml(self.plan_path(root,'POC-009'));route=CHECK.execution_route(plan,'local-v1');env=data['environmentCaptured'];configuration=load_yaml(root/env['acceptanceProfileConfigurationRef']);defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];prefix=Path(result['executionRef']).parent.as_posix();window=tuple(CHECK.utc(env['executionWindow'][key]) for key in ('startedAt','finishedAt'))
                    unit=next(m['unit'] for m in route['protocol']['measurements'] if m['id']==mid);errors=[]
                    if not CHECK.good_actual(unit,value,mid):errors.append('invalid numeric unit domain')
                    CHECK.validate_qualified_domains(root,plan,data,route,configuration,defs,prefix,result['reviewer'],window,errors)
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
            # Keep this domain-focused positive consistent with its retained evaluator output.
            report=load_yaml(root/execution['environmentCaptured']['mediaQualityTimingRef']);quality_path=root/report['qualityRef'];quality=load_yaml(quality_path);quality['vmafMean']=110;write_yaml(quality_path,quality)
            self.refresh_qualified_observation_fixture(root,execution);write_yaml(path,execution)
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
                self.assertEqual(validate(),self.deferred_production_errors(profile,'POC-06'))
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
                self.assertEqual(validate(),self.deferred_production_errors(profile,'POC-06'))
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
                self.assertEqual(validate(),self.deferred_production_errors(profile,'POC-06'))
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
                    subprocess.run(['git','-C',str(root),'-c','user.name=POC Fixture','-c','user.email=poc-fixture@guize.invalid','commit','--only','-q','-m','synthetic fixture change','--',*paths],check=True)
                commit('fixture-tested-source.txt')
                self.assertTrue(any('current validation context' in e for e in validate()))
                code.write_text(original_code,encoding='utf-8');commit('fixture-tested-source.txt')
                own_slot = str(index.parent.relative_to(root)).replace('\\','/')
                commit(own_slot)
                self.assertEqual(validate(),self.deferred_production_errors(profile,'POC-06'))
            finally:
                temp.cleanup()


    def test_127_sibling_slots_can_coexist_in_both_full_milestones(self):
        temp,root = self.temp_repo()
        try:
            for profile in ('local-v1','production'):
                for task in sorted(CHECK.TASKS): self.make_profile_slot(root,task,profile,status='inconclusive' if profile=='production' and task in ('POC-004','POC-006') else 'pass')
            self.assertEqual(CHECK.validate_repository(root,'local-v1',True,'GZ-018'),[])
            self.assertEqual(CHECK.validate_repository(root,'production',True,'GZ-020'),[f'profile evidence {task}/production: selected profile requires independently approved PASS' for task in ('POC-004','POC-006')])
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
                self.assertEqual(validate(),self.deferred_production_errors(profile,'POC-06'))
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
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'}),self.deferred_production_errors(profile,'POC-06'))
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
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'}),self.deferred_production_errors(profile,'POC-06'))
                if os.name != 'nt':
                    # A tracked symlink cannot preserve an ignored, untracked target.
                    execution_path=root/result['executionRef']; data=load_yaml(execution_path)
                    prefix=str(index.parent.relative_to(root)).replace('\\','/')
                    target_ref=prefix+'/raw/ignored-target.log';alias_ref=prefix+'/raw/tracked-alias.txt'
                    target=root/target_ref;target.write_text('Synthetic alias target.\n',encoding='utf8')
                    os.symlink(target.name,root/alias_ref)
                    subprocess.run(['git','-C',str(root),'add','--',alias_ref],check=True)
                    # Retain all typed observations while replacing only command output.
                    observations=[r for r in data['environmentCaptured']['rawExecutionArtifacts'] if r['artifactType']!='command_output']
                    data['rawOutputRefs']=[alias_ref,*[r['ref'] for r in observations]]
                    for command in data['commands']: command['outputRef']=alias_ref
                    data['environmentCaptured']['rawExecutionArtifacts']=[dict(ref=alias_ref,artifactType='command_output',byteCount=target.stat().st_size,sha256='sha256:'+hashlib.sha256(target.read_bytes()).hexdigest())]
                    data['environmentCaptured']['rawExecutionArtifacts'].extend(observations)
                    write_yaml(execution_path,data)
                    errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'})
                    self.assertTrue(any('referenced qualified evidence must not be ignored and untracked' in e and target_ref in e for e in errors),errors)
                    subprocess.run(['git','-C',str(root),'add','-f','--',target_ref],check=True)
                    self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'}),self.deferred_production_errors(profile,'POC-06'))
                    index_bytes=index.read_bytes();index.unlink()
                    index_target=index.parent/'index-data.log';index_target.write_bytes(index_bytes)
                    os.symlink(index_target.name,index)
                    subprocess.run(['git','-C',str(root),'add','--',index.relative_to(root).as_posix()],check=True)
                    errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'})
                    self.assertTrue(any('referenced qualified evidence must not be ignored and untracked' in e and 'index-data.log' in e for e in errors),errors)
                    subprocess.run(['git','-C',str(root),'add','-f','--',index_target.relative_to(root).as_posix()],check=True)
                    self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'}),self.deferred_production_errors(profile,'POC-06'))
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
                    self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'}),self.deferred_production_errors(profile,'POC-06'))
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
                self.assertEqual(validate(),self.deferred_production_errors(profile,'POC-04'))
                if profile=='local-v1': continue
                for value in (0,499,499.99,500,501):
                    data=load_yaml(path)
                    next(m for m in data['measurements'] if m['id']=='minimum_free_space_gib')['actual']=value
                    write_yaml(path,data);errors=validate()
                    if value < 500:self.assertTrue(any('qualified production capacity' in e for e in errors),errors)
                    else:self.assertEqual(errors,self.deferred_production_errors(profile,'POC-04'))
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
        tls=env.get('local_tls_path_configuration')
        if poc=='POC-07' and profile=='local-v1' and env.get('accessOutcomeRef') and isinstance(tls,dict) and all(isinstance(tls.get(key),str) for key in ('entryOrigin','openlistOrigin')):
            report=load_yaml(root/env['accessOutcomeRef']);resource_path=root/report['configurationRef'];resource=load_yaml(resource_path);policy=resource['configuration']['accessPolicy']
            for key,origin,path in (('range',tls['entryOrigin'],'/protected/range'),('stream',tls['entryOrigin'],'/protected/stream'),('source',tls['openlistOrigin'],'/protected/source'),('admin',tls['openlistOrigin'],'/api/admin')):policy['paths'][key]=origin+path
            write_yaml(resource_path,resource)
            for case in report['cases']:
                path=root/case['witnessRef'];witness=load_yaml(path);role='stream' if case['case']=='authorized_stream' else case['case'].removeprefix('direct_') if case['case'].startswith('direct_') else 'range';witness['requestURL']=policy['paths'][role];write_yaml(path,witness)
            self.refresh_qualified_observation_fixture(root,execution)
            index=CHECK.profile_index_ref('POC-'+str(int(poc.split('-')[1])).zfill(3),profile);result=load_yaml(root/load_yaml(root/index)['resultRef']);write_yaml(root/result['executionRef'],execution)
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
                self.assertEqual(validate(),self.deferred_production_errors(profile,'POC-04'))
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
                        self.assertEqual(validate(),self.deferred_production_errors(profile,result['pocId']))
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
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'}),self.deferred_production_errors(profile,'POC-06'))
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


    def test_155_inference_pass_requires_positive_measured_throughput(self):
        for profile in ('local-v1','production'):
            for status in ('pass','fail','inconclusive'):
                temp,root=self.temp_repo()
                try:
                    index=self.make_profile_slot(root,'POC-009',profile,status=status)
                    result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
                    validate=lambda:CHECK.validate_repository(root,profile,status=='pass',selected_pocs={'POC-09'})
                    self.assertEqual(validate(),[])
                    for value in ((0,-1,True,float('nan')) if status=='pass' else (0,)):
                        path.write_bytes(original);record=load_yaml(path)
                        next(m for m in record['measurements'] if m['id']=='throughput')['actual']=value
                        write_yaml(path,record)
                        if status=='pass':
                            self.assertTrue(any('positive measured inference throughput' in e for e in validate()),(profile,status,value))
                        else:
                            self.assertEqual(validate(),[],(profile,status,value))
                finally:temp.cleanup()


    def test_156_android_media_requires_bound_av1_decoder_report(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-001',profile)
                result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
                baseline=load_yaml(path);env=baseline['environmentCaptured']
                scope=env['vm_validation_scope'] if profile=='local-v1' else env['android_validation_scope']
                probe_ref=env['androidMediaProbeRef'];probe_path=root/probe_ref;probe_bytes=probe_path.read_bytes()
                media_path=root/scope['rawOutputRef'];media_bytes=media_path.read_bytes()
                validate=lambda:CHECK.validate_repository(root,profile,True,selected_pocs={'POC-01'})
                self.assertEqual(validate(),[])
                for mode in ('missing','hash','output','input','node','encoder','decoder','codec','frames','duration','errors','decodable','boolean_frames','empty','malformed','oversize','alias_ref','hardlink','artifact_node','arbitrary_media','metadata_alias'):
                    path.write_bytes(original);probe_path.unlink();probe_path.write_bytes(probe_bytes);media_path.write_bytes(media_bytes)
                    record=load_yaml(path);env=record['environmentCaptured'];scope=env['vm_validation_scope'] if profile=='local-v1' else env['android_validation_scope'];report=load_yaml(probe_path)
                    if mode=='missing':env.pop('androidMediaProbeRef')
                    elif mode=='hash':report['outputSha256']='sha256:'+'f'*64
                    elif mode=='output':report['outputArtifactRef']=record['rawOutputRefs'][0]
                    elif mode=='input':report['inputSha256']='sha256:'+'f'*64
                    elif mode=='node':report['nodeId']='other-node'
                    elif mode=='encoder':report['encoderBuild']='other-build'
                    elif mode=='decoder':report['decoderBuild']=''
                    elif mode=='codec':report['codec']='h264'
                    elif mode=='frames':report['decodedFrameCount']=0
                    elif mode=='duration':report['durationSeconds']=0
                    elif mode=='errors':report['decodeErrorCount']=1
                    elif mode=='decodable':report['decodable']=False
                    elif mode=='boolean_frames':report['decodedFrameCount']=True
                    elif mode=='alias_ref':env['androidMediaProbeRef']=scope['rawOutputRef']
                    elif mode=='artifact_node':next(a for a in env['rawExecutionArtifacts'] if a['ref']==probe_ref)['nodeId']='other-node'
                    elif mode=='arbitrary_media':
                        media_path.write_bytes(b'NOT A VIDEO; synthetic malformed media counterexample.\n')
                        scope['outputSha256']='sha256:'+hashlib.sha256(media_path.read_bytes()).hexdigest()
                        artifact=next(a for a in env['rawExecutionArtifacts'] if a['ref']==scope['rawOutputRef'])
                        artifact.update(byteCount=media_path.stat().st_size,sha256=scope['outputSha256'])
                    elif mode=='metadata_alias':
                        cfg_ref=env['acceptanceProfileConfigurationRef'];cfg_path=root/cfg_ref
                        env['androidMediaProbeRef']=cfg_ref;record['rawOutputRefs'].append(cfg_ref)
                        env['rawExecutionArtifacts'].append(dict(ref=cfg_ref,artifactType='measurement_output',nodeId=scope['nodeId'],byteCount=cfg_path.stat().st_size,sha256='sha256:'+hashlib.sha256(cfg_path.read_bytes()).hexdigest()))
                    if mode=='empty':probe_path.write_bytes(b'')
                    elif mode=='malformed':probe_path.write_text('[unterminated',encoding='utf8')
                    elif mode=='oversize':probe_path.write_bytes(b'x'*262145)
                    elif mode=='hardlink':probe_path.unlink();os.link(media_path,probe_path)
                    else:write_yaml(probe_path,report)
                    artifact=next(a for a in env['rawExecutionArtifacts'] if a['ref']==probe_ref)
                    artifact.update(byteCount=probe_path.stat().st_size,sha256='sha256:'+hashlib.sha256(probe_path.read_bytes()).hexdigest())
                    write_yaml(path,record)
                    self.assertTrue(any('qualified Android media probe' in e for e in validate()),(profile,mode))
            finally:temp.cleanup()
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-001','local-v1',status='fail')
            result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];record=load_yaml(path)
            record['environmentCaptured'].pop('androidMediaProbeRef');write_yaml(path,record)
            self.assertEqual(CHECK.validate_repository(root,'local-v1',False,selected_pocs={'POC-01'}),[])
        finally:temp.cleanup()


    def test_157_production_passthrough_matches_frozen_approved_inventory(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-001','production')
            result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
            baseline=load_yaml(path);config_path=root/baseline['environmentCaptured']['productionPassthroughIdentity']['configurationRef'];config_bytes=config_path.read_bytes()
            validate=lambda:CHECK.validate_repository(root,'production',True,selected_pocs={'POC-01'})
            self.assertEqual(validate(),[])
            mutations=(('hypervisorVendor','OTHER_VENDOR'),('hypervisorProduct','OTHER_PRODUCT'),('hypervisorVersion','8.0'),('gpuVendor','OTHER_VENDOR'),('gpuModel','OTHER_GPU'),('platform','android'),('gpuDeviceId',''),('physicalHostId',''),('guestId',''),('runtimeBuild',''),('driverBuild',''),('encoderBuild',''))
            for mode in [key for key,value in mutations]+['missing','generic_configuration','wrong_ref','approved_mismatch','missing_inventory','inventory_mismatch','duplicate_inventory']:
                path.write_bytes(original);config_path.write_bytes(config_bytes);record=load_yaml(path);env=record['environmentCaptured'];capture=env['productionPassthroughIdentity'];config=load_yaml(config_path)
                identity=capture['identity'];node=next(n for n in env['worker_node_inventory'] if n['nodeId']==identity['nodeId'])
                if mode in dict(mutations):
                    value=dict(mutations)[mode];identity[mode]=value;node[mode]=value;config['configuration']['productionPassthroughIdentity'][mode]=value
                elif mode=='missing':env.pop('productionPassthroughIdentity')
                elif mode=='generic_configuration':config['configuration'].pop('productionPassthroughIdentity')
                elif mode=='wrong_ref':capture['configurationRef']=env['acceptanceProfileConfigurationRef']
                elif mode=='approved_mismatch':config['configuration']['productionPassthroughIdentity']['physicalHostId']='other-approved-host'
                elif mode=='missing_inventory':env['worker_node_inventory'].remove(node)
                elif mode=='inventory_mismatch':node['gpuDeviceId']='other-device'
                else:env['worker_node_inventory'].append(dict(node))
                write_yaml(config_path,config);write_yaml(path,record)
                self.assertTrue(any('qualified production passthrough identity' in e for e in validate()),mode)
        finally:temp.cleanup()
        for profile,status in (('local-v1','pass'),('production','fail'),('production','inconclusive')):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-001',profile,status=status)
                result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];record=load_yaml(path)
                self.assertNotIn('productionPassthroughIdentity',record['environmentCaptured'])
                if status!='pass':
                    record['environmentCaptured']['productionPassthroughIdentity']=dict(identity=dict(hypervisorVendor='OTHER_VENDOR',hypervisorVersion='8.0',gpuModel='OTHER_GPU'))
                    write_yaml(path,record)
                self.assertEqual(CHECK.validate_repository(root,profile,status=='pass',selected_pocs={'POC-01'}),[])
            finally:temp.cleanup()

    def test_158_production_soak_requires_dedicated_bound_observation(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-001','production')
            result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
            env=load_yaml(path)['environmentCaptured'];raw_ref=env['productionPassthroughSoak']['rawOutputRef'];raw_path=root/raw_ref;raw_bytes=raw_path.read_bytes()
            validate=lambda:CHECK.validate_repository(root,'production',True,selected_pocs={'POC-01'})
            self.assertEqual(validate(),[])
            for mode in ('phone_alias','media_alias','probe_alias','phone_hardlink','wrong_node','wrong_host','wrong_resource','wrong_configuration','wrong_start','short_finish','not_continuous','empty','malformed','oversize','artifact_node','metadata_alias'):
                path.write_bytes(original);raw_path.unlink();raw_path.write_bytes(raw_bytes)
                record=load_yaml(path);env=record['environmentCaptured'];capture=env['productionPassthroughSoak'];report=load_yaml(raw_path)
                if mode=='phone_alias':capture['rawOutputRef']=env['android_thermal_background_observation']['rawOutputRef']
                elif mode=='media_alias':capture['rawOutputRef']=env['android_validation_scope']['rawOutputRef']
                elif mode=='probe_alias':capture['rawOutputRef']=env['androidMediaProbeRef']
                elif mode=='wrong_node':report['identity']['nodeId']='other-node'
                elif mode=='wrong_host':report['identity']['physicalHostId']='other-host'
                elif mode=='wrong_resource':report['identity']['resourceId']='RES-A380-ENCODE'
                elif mode=='wrong_configuration':report['configurationRef']=env['acceptanceProfileConfigurationRef']
                elif mode=='wrong_start':report['observedStartedAt']='2026-09-03T00:00:01Z'
                elif mode=='short_finish':report['observedFinishedAt']='2026-09-03T00:01:00Z'
                elif mode=='not_continuous':report['continuous']=False
                elif mode=='artifact_node':next(a for a in env['rawExecutionArtifacts'] if a['ref']==raw_ref)['nodeId']='other-node'
                elif mode=='metadata_alias':
                    cfg_ref=env['acceptanceProfileConfigurationRef'];cfg_path=root/cfg_ref;capture['rawOutputRef']=cfg_ref;record['rawOutputRefs'].append(cfg_ref)
                    env['rawExecutionArtifacts'].append(dict(ref=cfg_ref,artifactType='scope_observation',nodeId=report['identity']['nodeId'],byteCount=cfg_path.stat().st_size,sha256='sha256:'+hashlib.sha256(cfg_path.read_bytes()).hexdigest()))
                if mode=='empty':raw_path.write_bytes(b'')
                elif mode=='malformed':raw_path.write_text('[unterminated',encoding='utf8')
                elif mode=='oversize':raw_path.write_bytes(b'x'*262145)
                elif mode=='phone_hardlink':raw_path.unlink();os.link(root/env['android_thermal_background_observation']['rawOutputRef'],raw_path)
                else:write_yaml(raw_path,report)
                artifact=next(a for a in env['rawExecutionArtifacts'] if a['ref']==raw_ref)
                artifact.update(byteCount=raw_path.stat().st_size,sha256='sha256:'+hashlib.sha256(raw_path.read_bytes()).hexdigest())
                write_yaml(path,record)
                self.assertTrue(any('qualified production soak' in e for e in validate()),mode)
        finally:temp.cleanup()


    def test_159_local_hierarchy_root_binds_safe_controlled_sandbox(self):
        unsafe=['/etc','../../outside','C:/Windows','C:'+chr(92)+'Windows',chr(92)*2+'server'+chr(92)+'share','//server/share','fixture/../outside','fixture/./inside','fixture//inside','fixture/','fixture/.','fixture/..','fixture/con.txt','fixture/LPT1','fixture/name.','fixture/name ','fixture:stream',' fixture','fixture'+chr(0),'fixture'+chr(10),'fixture?name']
        for value in unsafe:self.assertFalse(CHECK.safe_generator_relative_path(value),value)
        for value in ('fixture-hierarchy','fixture-hierarchy/subfolder','归泽/fixtures','fixtures/space inside'):
            self.assertTrue(CHECK.safe_generator_relative_path(value),value)
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-005','local-v1')
            result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];original=path.read_bytes()
            baseline=load_yaml(path);env=baseline['environmentCaptured']
            cfg_path=root/env['acceptanceProfileConfigurationRef'];cfg_bytes=cfg_path.read_bytes()
            resource_path=root/env['syntheticHierarchySandbox']['configurationRef'];resource_bytes=resource_path.read_bytes()
            validate=lambda:CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-05'})
            self.assertEqual(validate(),[])
            def synchronize(record,resource):
                env=record['environmentCaptured'];cfg=load_yaml(cfg_path)
                cfg['capturedSettings']['synthetic_hierarchy_manifest']=env['synthetic_hierarchy_manifest']
                resource['configuration']['metadataScanPolicy']['hierarchyGenerator']=copy.deepcopy(env['synthetic_hierarchy_manifest']['generator'])
                for ref in cfg['numericDomainReviewRefs'].values():
                    review_path=root/ref;review=load_yaml(review_path)
                    review['environmentCaptured']['synthetic_hierarchy_manifest']=env['synthetic_hierarchy_manifest'];write_yaml(review_path,review)
                write_yaml(cfg_path,cfg);write_yaml(resource_path,resource);write_yaml(path,record)
            for value in ['fixture-hierarchy/subfolder']+unsafe:
                path.write_bytes(original);cfg_path.write_bytes(cfg_bytes);resource_path.write_bytes(resource_bytes)
                record=load_yaml(path);resource=load_yaml(resource_path)
                record['environmentCaptured']['synthetic_hierarchy_manifest']['generator']['rootPath']=value
                record['environmentCaptured']['syntheticHierarchySandbox']['boundary']['rootPath']=value
                resource['configuration']['syntheticHierarchySandbox']['rootPath']=value
                synchronize(record,resource)
                if value=='fixture-hierarchy/subfolder':self.assertEqual(validate(),[])
                else:self.assertTrue(any('qualified local hierarchy sandbox' in e for e in validate()),value)
            for mode in ('missing','missing_configuration','wrong_ref','wrong_bound_root','wrong_host','empty_mount','unsafe_mount','uncontrolled','not_disposable','wrong_scope','wrong_resource'):
                path.write_bytes(original);cfg_path.write_bytes(cfg_bytes);resource_path.write_bytes(resource_bytes)
                record=load_yaml(path);env=record['environmentCaptured'];resource=load_yaml(resource_path)
                boundary=env['syntheticHierarchySandbox']['boundary'];approved=resource['configuration']['syntheticHierarchySandbox']
                if mode=='missing':env.pop('syntheticHierarchySandbox')
                elif mode=='missing_configuration':resource['configuration'].pop('syntheticHierarchySandbox')
                elif mode=='wrong_ref':env['syntheticHierarchySandbox']['configurationRef']=env['acceptanceProfileConfigurationRef']
                elif mode=='wrong_bound_root':boundary['rootPath']='other-root'
                elif mode=='wrong_host':approved['physicalHostId']='other-host'
                elif mode=='empty_mount':boundary['mountId']=approved['mountId']=''
                elif mode=='unsafe_mount':boundary['mountId']=approved['mountId']='../../outside'
                elif mode=='uncontrolled':boundary['controlled']=approved['controlled']=False
                elif mode=='not_disposable':boundary['disposable']=approved['disposable']=False
                elif mode=='wrong_scope':boundary['scope']=approved['scope']='PRODUCTION_RELEASE'
                else:boundary['resourceId']=approved['resourceId']='RES-OPENLIST-LOCAL'
                synchronize(record,resource)
                self.assertTrue(any('qualified local hierarchy sandbox' in e for e in validate()),mode)
        finally:temp.cleanup()
        for profile,status in (('production','pass'),('local-v1','fail')):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-005',profile,status=status)
                result=load_yaml(root/load_yaml(index)['resultRef']);path=root/result['executionRef'];record=load_yaml(path)
                if profile=='production':self.assertNotIn('syntheticHierarchySandbox',record['environmentCaptured'])
                else:
                    record['environmentCaptured'].pop('syntheticHierarchySandbox');write_yaml(path,record)
                self.assertEqual(CHECK.validate_repository(root,profile,status=='pass',selected_pocs={'POC-05'}),[])
            finally:temp.cleanup()


    def test_199_referenced_unignored_profile_evidence_must_be_tracked(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-006',profile)
                result=load_yaml(root/load_yaml(index)['resultRef'])
                record=load_yaml(root/result['executionRef'])
                refs=[index.relative_to(root).as_posix(),record['environmentCaptured']['acceptanceProfileConfigurationRef']]
                expected=self.deferred_production_errors(profile,'POC-06')
                self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'}),expected)
                for ref in refs:
                    subprocess.run(['git','-C',str(root),'rm','--cached','--',ref],check=True,capture_output=True)
                    ignored=subprocess.run(['git','-C',str(root),'check-ignore','--',ref],capture_output=True)
                    self.assertEqual(ignored.returncode,1)
                    errors=CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'})
                    self.assertTrue(any('referenced qualified evidence must be tracked' in e and ref in e for e in errors),(profile,ref,errors))
                    subprocess.run(['git','-C',str(root),'add','--',ref],check=True,capture_output=True)
                    self.assertEqual(CHECK.validate_repository(root,profile,True,selected_pocs={'POC-06'}),expected)
            finally:temp.cleanup()

    def test_200_invalid_firmware_reports_return_validation_errors(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-001','production')
            path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef']
            record=load_yaml(path);env=record['environmentCaptured']
            report_path=root/env['productionFirmwareRef'];original=load_yaml(report_path)
            defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs']
            plan=load_yaml(self.plan_path(root,'POC-001'));prefix=Path(str(path.relative_to(root))).parent.as_posix()
            window=tuple(CHECK.utc(env['executionWindow'][key]) for key in ('startedAt','finishedAt'))
            for missing in ('hostBootId','runtimeInitializedAt'):
                report=copy.deepcopy(original);report.pop(missing);write_yaml(report_path,report)
                self.refresh_qualified_observation_fixture(root,record)
                errors=[]
                CHECK.validate_qualified_passthrough_transitions(root,plan,record,prefix,'pass',window,defs,errors,{})
                self.assertTrue(any(missing in e and 'required' in e for e in errors),(missing,errors))
        finally:temp.cleanup()

    def test_201_denied_access_requires_zero_origin_requests(self):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-007',profile)
                path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef']
                record=load_yaml(path);env=record['environmentCaptured'];report=load_yaml(root/env['accessOutcomeRef'])
                defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs']
                plan=load_yaml(self.plan_path(root,'POC-007'));prefix=path.parent.relative_to(root).as_posix()
                window=tuple(CHECK.utc(env['executionWindow'][key]) for key in ('startedAt','finishedAt'))
                def validate():
                    self.refresh_qualified_observation_fixture(root,record)
                    errors=[];CHECK.validate_qualified_access_outcomes(root,plan,record,prefix,'pass',window,defs,errors,{})
                    return errors
                self.assertEqual(validate(),[])
                for row in report['cases']:
                    if row['case'].startswith('authorized_') or row['case']=='rate_limit':continue
                    witness_path=root/row['witnessRef'];witness=load_yaml(witness_path)
                    self.assertEqual(witness['originRequestCount'],0)
                    witness['originRequestCount']=1;write_yaml(witness_path,witness)
                    self.assertTrue(any('denied requests must not contact the origin' in e for e in validate()),(profile,row['case']))
                    witness['originRequestCount']=0;write_yaml(witness_path,witness)
                    self.assertEqual(validate(),[])
            finally:temp.cleanup()


    def exercise_recovery_integrity_regressions(self,cases,mutate):
        for profile in ('local-v1','production'):
            temp,root=self.temp_repo()
            try:
                index=self.make_profile_slot(root,'POC-010',profile)
                path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];record=load_yaml(path);capture=record['environmentCaptured']['recoveryEvidence']
                paths=[root/capture[k] for k in ('baselineRef','restoredRef','comparisonRef','configurationRef')]
                saved={root/a['ref']:(root/a['ref']).read_bytes() for a in record['environmentCaptured']['rawExecutionArtifacts']};saved[path]=path.read_bytes();saved[paths[3]]=paths[3].read_bytes()
                validate=lambda:CHECK.validate_repository(root,profile,True,selected_pocs={'POC-10'})
                self.assertEqual(validate(),[])
                for case in cases:
                    for artifact,raw in saved.items():artifact.write_bytes(raw)
                    record=load_yaml(path);base,restored,comparison,config=[load_yaml(p) for p in paths]
                    mutate(case,root,base,restored,comparison,config)
                    for row in comparison['rows']:
                        domains=CHECK.RECOVERY_GATE_DOMAINS[row['gate']];row['before']={d:CHECK.recovery_domain_digest(base['states'][d]) for d in domains};row['after']={d:CHECK.recovery_domain_digest(restored['states'][d]) for d in domains}
                    write_yaml(paths[0],base);write_yaml(paths[1],restored)
                    comparison['baselineSha256']=config['configuration']['recoveryBaseline']['baselineSha256']='sha256:'+hashlib.sha256(paths[0].read_bytes()).hexdigest();comparison['restoredSha256']='sha256:'+hashlib.sha256(paths[1].read_bytes()).hexdigest()
                    write_yaml(paths[2],comparison);write_yaml(paths[3],config)
                    self.refresh_qualified_observation_fixture(root,record);write_yaml(path,record)
                    errors=validate();self.assertTrue(any('qualified recovery observation' in e for e in errors),(profile,case,errors))
            finally:temp.cleanup()

    def test_202_recovery_preserves_scoped_acl_and_publication(self):
        def mutate(case,root,base,restored,comparison,config):
            if case=='changed_disposition':restored['states']['permissions'][0]['scopedGrants'][0]['disposition']='deny'
            elif case=='changed_publication':restored['states']['assets'][0].update(visibility='PUBLIC',anonymousAccess=True)
            else:
                for report in (base,restored):
                    permission=report['states']['permissions'][0]
                    if case=='missing':permission.pop('scopedGrants')
                    elif case=='orphan':permission['scopedGrants'][0]['assetId']='missing-asset'
                    else:permission['scopedGrants'][0]['aclVersion']=2
        self.exercise_recovery_integrity_regressions(('missing','orphan','acl_version','changed_disposition','changed_publication'),mutate)

    def test_203_recovery_verified_replicas_require_actual_readback(self):
        def mutate(case,root,base,restored,comparison,config):
            for report in (base,restored):
                row=report['states']['replicas'][0]
                if case=='missing':row.pop('artifactRef')
                elif case=='invented_hash':row['sha256']='sha256:'+'a'*64
                elif case=='size':row['byteCount']+=1
                else:(root/row['artifactRef']).write_bytes(b'Corrupted actual replica bytes.\n')
        self.exercise_recovery_integrity_regressions(('missing','invented_hash','size','corrupt'),mutate)

    def test_204_recovery_openbao_compares_nonsecret_configuration(self):
        def mutate(case,root,base,restored,comparison,config):
            if case in ('missing','hash'):
                for report in (base,restored):
                    if case=='missing':report['states']['openbao'].pop('configurationRef')
                    else:report['states']['openbao']['configurationSha256']='sha256:'+'a'*64
            else:
                store=restored['states']['openbao'];artifact=root/store['configurationRef'];snapshot=load_yaml(artifact)
                if case=='policy':snapshot['policies'][0]['rules']='path "fixture/*" { capabilities = ["deny"] }'
                elif case=='mount':snapshot['mounts'][0]['options']['version']='1'
                else:snapshot['authMethods'][0]['configuration']['defaultLeaseSeconds']=600
                write_yaml(artifact,snapshot);store['configurationSha256']='sha256:'+hashlib.sha256(artifact.read_bytes()).hexdigest()
        self.exercise_recovery_integrity_regressions(('missing','hash','policy','mount','auth'),mutate)

    def test_205_recovery_audit_hash_chain_covers_event_contents(self):
        def mutate(case,root,base,restored,comparison,config):
            if case in ('action','trace'):
                row=restored['states']['audit'][0];row['event']['action' if case=='action' else 'traceId']='changed-audit-content'
                row['sha256']='sha256:'+hashlib.sha256(json.dumps({k:v for k,v in row.items() if k!='sha256'},sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest()
            else:
                for report in (base,restored):
                    row=report['states']['audit'][0]
                    if case=='missing':row.pop('event')
                    elif case=='actor':row['event']['actorId']='missing-user'
                    else:row['event']['reason']='Altered contents behind the original chain hash'
        self.exercise_recovery_integrity_regressions(('missing','actor','action','trace','unchanged_hash'),mutate)

    def test_206_recovery_signatures_require_actual_approved_key_verification(self):
        def mutate(case,root,base,restored,comparison,config):
            policy=config['configuration']['recoveryBaseline']
            if case=='missing_trust':policy.pop('approvedSigners')
            elif case=='key_hash':policy['approvedSigners'][0]['publicKeySha256']='sha256:'+'a'*64
            else:
                for report in (base,restored):
                    row=report['states']['deployment'][0];artifact=root/row['verificationRef'];verification=load_yaml(artifact)
                    if case=='signer':row['signerIdentity']=verification['signerIdentity']='unapproved-signer'
                    else:
                        field,hash_field=('signatureArtifactRef','signatureSha256') if case=='random_signature' else ('imageArtifactRef','imageSha256')
                        payload=root/row[field];payload.write_bytes(b'x'*64 if case=='random_signature' else b'Changed image retaining the original signature.\n')
                        row[hash_field]=verification[hash_field]='sha256:'+hashlib.sha256(payload.read_bytes()).hexdigest()
                    write_yaml(artifact,verification)
        self.exercise_recovery_integrity_regressions(('missing_trust','key_hash','random_signature','changed_image','signer'),mutate)

    def test_207_recovery_unreadable_backup_uses_readable_control_and_actual_decoder(self):
        def mutate(case,root,base,restored,comparison,config):
            if case=='approved_control':config['configuration']['recoveryBaseline']['approvedUnreadableFixture']['controlBackupSha256']='sha256:'+'a'*64;return
            if case=='observation':
                artifact=root/comparison['unreadableWitness']['observationRef'];observation=load_yaml(artifact);observation['controlDecodedSha256']='sha256:'+'a'*64;write_yaml(artifact,observation);return
            for report in (base,restored):
                fixture=report['states']['unreadableFixture']
                if case=='missing_control':fixture.pop('controlBackupRef');continue
                control=root/fixture['controlBackupRef'];bad=root/fixture['artifactRef']
                if case=='invalid_control':
                    data=b'An arbitrary invalid gzip cannot qualify as a readable control.';control.write_bytes(data);fixture['corruptionOffset']=0;fixture['controlBackupSha256']='sha256:'+hashlib.sha256(data).hexdigest();bad.write_bytes(bytes([data[0]^1])+data[1:])
                elif case=='unchanged_backup':bad.write_bytes(control.read_bytes())
                else:bad.write_bytes(b'Unrelated corrupt bytes are not an approved control mutation.')
                fixture['backupSha256']='sha256:'+hashlib.sha256(bad.read_bytes()).hexdigest();fixture['byteCount']=bad.stat().st_size
            if case!='missing_control':
                fixture=base['states']['unreadableFixture'];comparison['unreadableWitness']['backupSha256']=fixture['backupSha256'];config['configuration']['recoveryBaseline']['approvedUnreadableFixture']={k:fixture[k] for k in ('fixtureId','backupSha256','controlBackupSha256','codec','corruptionOffset','corruptionXor')}
        self.exercise_recovery_integrity_regressions(('missing_control','invalid_control','unchanged_backup','unrelated_corrupt','observation','approved_control'),mutate)


    def test_208_local_source_authentication_requires_bound_method_bytes_and_denials(self):
        temp,root=self.temp_repo()
        try:
            index=self.make_profile_slot(root,'POC-006','local-v1');path=root/load_yaml(root/load_yaml(index)['resultRef'])['executionRef'];original=load_yaml(path);env=original['environmentCaptured'];report_path=root/env['sourceAuthenticationRef'];original_report=load_yaml(report_path);config_path=root/original_report['configurationRef'];original_config=load_yaml(config_path)
            prefix=str(index.parent.relative_to(root)).replace('\\','/');plan=load_yaml(self.plan_path(root,'POC-006'));defs=load_yaml(root/'specs/poc/program.schema.yaml')['$defs'];window=tuple(CHECK.utc(env['executionWindow'][k]) for k in ('startedAt','finishedAt'))
            original_bodies={row['responseBodyRef']:(root/row['responseBodyRef']).read_bytes() for row in original_report['requests']}
            def validate(data,status='pass'):
                self.refresh_qualified_observation_fixture(root,data);errors=[];CHECK.validate_qualified_local_source_authentication(root,plan,data,prefix,status,window,defs,errors,{});return errors
            self.assertEqual(validate(copy.deepcopy(original)),[])
            self.assertEqual(CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-06'}),[])
            for mode in ('missing','shape','policy_shape','method','principal','source','sandbox','version','endpoint','input','sample','payload','duplicate_auth_ref','invalid_ref','request_method','request_endpoint','observed_method','observed_ref','observed_principal','authenticated_principal','clock','future_clock','success_status','body_hash','body_count','body_bytes','empty_success','object','object_version','anonymous_success','anonymous_ref','anonymous_identity','anonymous_bytes','invalid_success','invalid_result','duplicate_case','duplicate_request','missing_case','alias','outside_slot','raw_type','gate'):
                with self.subTest(mode=mode):
                    data=copy.deepcopy(original);report=copy.deepcopy(original_report);config=copy.deepcopy(original_config);policy=config['configuration']['localSourceAuthenticationPolicy'];success,anonymous,invalid=report['requests']
                    for ref,body in original_bodies.items():(root/ref).write_bytes(body)
                    if mode=='missing':data['environmentCaptured'].pop('sourceAuthenticationRef')
                    elif mode=='shape':report=True
                    elif mode=='policy_shape':config['configuration']['localSourceAuthenticationPolicy']=True
                    elif mode in ('method','principal','source','sandbox','version','endpoint'):report[dict(method='authMethod',principal='principalId',source='sourceId',sandbox='sandboxId',version='subjectVersion',endpoint='endpointURL')[mode]]='foreign'
                    elif mode=='input':report['inputSamples'][0]['checksum']='sha256:'+'0'*64
                    elif mode=='sample':policy['sampleId']='foreign'
                    elif mode=='payload':policy['payloadSha256']='sha256:'+'0'*64
                    elif mode=='duplicate_auth_ref':policy['invalidAuthRef']=policy['authorizedAuthRef']
                    elif mode=='invalid_ref':policy['authorizedAuthRef']='plaintext-not-a-reference'
                    elif mode=='request_method':success['httpMethod']='POST'
                    elif mode=='request_endpoint':success['endpointURL']='http://127.0.0.1:15525/other'
                    elif mode=='observed_method':success['authMethod']='bearer'
                    elif mode=='observed_ref':success['authRef']=policy['invalidAuthRef']
                    elif mode=='observed_principal':success['requestPrincipalId']='foreign'
                    elif mode=='authenticated_principal':success['authenticatedPrincipalId']=None
                    elif mode=='clock':success['finishedAt']='2026-09-03T00:03:00Z'
                    elif mode=='future_clock':success['finishedAt']='2099-09-03T00:04:01Z'
                    elif mode=='success_status':success['statusCode']=401
                    elif mode=='body_hash':success['responseSha256']='sha256:'+'0'*64
                    elif mode=='body_count':success['responseByteCount']+=1
                    elif mode in ('body_bytes','empty_success'):
                        body=b'Forged protected response' if mode=='body_bytes' else b'';(root/success['responseBodyRef']).write_bytes(body);success['responseSha256']='sha256:'+hashlib.sha256(body).hexdigest();success['responseByteCount']=len(body)
                    elif mode=='object':success['returnedObjectId']='foreign'
                    elif mode=='object_version':success['returnedObjectVersion']='foreign'
                    elif mode=='anonymous_success':anonymous['statusCode']=200
                    elif mode=='anonymous_ref':anonymous['authRef']=policy['authorizedAuthRef']
                    elif mode=='anonymous_identity':anonymous['authenticatedPrincipalId']=policy['principalId']
                    elif mode=='anonymous_bytes':
                        body=original_bodies[success['responseBodyRef']];(root/anonymous['responseBodyRef']).write_bytes(body);anonymous['responseSha256']='sha256:'+hashlib.sha256(body).hexdigest();anonymous['responseByteCount']=len(body)
                    elif mode=='invalid_success':invalid['statusCode']=200
                    elif mode=='invalid_result':invalid['returnedObjectId']=policy['objectId']
                    elif mode=='duplicate_case':invalid['case']='anonymous_denied'
                    elif mode=='duplicate_request':invalid['requestId']=success['requestId']
                    elif mode=='missing_case':report['requests'].pop()
                    elif mode=='alias':anonymous['responseBodyRef']=invalid['responseBodyRef']
                    elif mode=='outside_slot':success['responseBodyRef']='evidence/POC-006/foreign.bin'
                    elif mode=='raw_type':next(a for a in data['environmentCaptured']['rawExecutionArtifacts'] if a['ref']==success['responseBodyRef'])['artifactType']='command_output'
                    else:next(m for m in data['measurements'] if m['id']=='auth_flow_supported')['actual']=False
                    write_yaml(report_path,report);write_yaml(config_path,config);self.assertTrue(validate(data),mode)
            for ref,body in original_bodies.items():(root/ref).write_bytes(body)
            write_yaml(config_path,original_config);write_yaml(report_path,original_report)
            # Basic and Bearer both retain real protected payload and anonymous/invalid controls.
            for method in ('basic','bearer'):
                config=copy.deepcopy(original_config);report=copy.deepcopy(original_report);config['configuration']['localSourceAuthenticationPolicy']['authMethod']=method;report['authMethod']=method
                for row in report['requests']:
                    if row['case']!='anonymous_denied':row['authMethod']=method
                write_yaml(config_path,config);write_yaml(report_path,report);self.assertEqual(validate(copy.deepcopy(original)),[])
            for status in ('fail','inconclusive'):
                data=copy.deepcopy(original);data['environmentCaptured'].pop('sourceAuthenticationRef');self.assertEqual(validate(data,status),[])
            data=copy.deepcopy(original);data['environmentCaptured']['acceptanceProfile']=CHECK.profile_identity('production');data['environmentCaptured'].pop('sourceAuthenticationRef');self.assertEqual(validate(data),[])
            write_yaml(config_path,original_config);write_yaml(report_path,original_report);data=copy.deepcopy(original);data['environmentCaptured'].pop('sourceAuthenticationRef');write_yaml(path,data)
            self.assertTrue(any('qualified local source authentication' in e for e in CHECK.validate_repository(root,'local-v1',True,selected_pocs={'POC-06'})))
        finally:temp.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=2)
