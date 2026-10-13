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
            if task_id=='POC-010' and status=='pass':self.prepare_qualified_recovery_fixture(root,execution,new_prefix)
            if task_id=='POC-002' and production and status=='pass':self.prepare_qualified_a380_fixture(root,execution,new_prefix)
            if task_id=='POC-007' and status=='pass':self.prepare_qualified_access_fixture(root,execution,new_prefix)
            if task_id=='POC-003' and status=='pass':self.prepare_qualified_range_fixture(root,execution,new_prefix)
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
        return root/ref

    def prepare_qualified_recovery_fixture(self,root,execution,prefix):
        """Synthetic typed recovery reports; no backup/restore was performed."""
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
        audit=dict(entryId='fixture-audit',sequence=0,entityId='fixture-asset',previousSha256='sha256:'+'0'*64)
        audit['sha256']='sha256:'+hashlib.sha256(json.dumps(audit,sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest();state['audit']=[audit]
        common=dict(schemaVersion=1,resourceId='RES-RECOVERY-SANDBOX',acceptanceProfile=env['acceptanceProfile'],subjectVersion=CHECK.compliance_subject_version({'pocId':'POC-10'},execution),inputSamples=[{key:s[key] for key in ('id','immutableId','checksum')} for s in execution['samples']])
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
            image_ref,image_sha,_=retain(phase+'-image.bin',b'Synthetic deployment image; not an actual image.\n')
            sig_ref,sig_sha,_=retain(phase+'-image-signature.bin',b'Synthetic signature; not actual cryptographic verification.\n')
            verification_ref,_,_=retain(phase+'-signature-verification.yaml',dict(schemaVersion=1,kind='signature_verification',imageSha256=image_sha,signatureSha256=sig_sha,signerIdentity='fixture-approved-signer',algorithm='ed25519',verified=True),'measurement_output')
            states['deployment']=[dict(imageId='fixture-image',imageArtifactRef=image_ref,imageSha256=image_sha,signatureArtifactRef=sig_ref,signatureSha256=sig_sha,signerIdentity='fixture-approved-signer',verificationRef=verification_ref)]
            report=dict(**common,kind='recovery_'+phase,observedStartedAt='2026-09-02T23:59:57Z' if phase=='baseline' else '2026-09-03T00:00:01Z',observedFinishedAt='2026-09-02T23:59:59Z' if phase=='baseline' else '2026-09-03T00:01:00Z',states=states)
            ref,sha,_=retain('recovery-'+phase+'.yaml',report,'measurement_output');manifests.append((ref,sha,report))
        baseline_ref,baseline_sha,baseline=manifests[0];restored_ref,restored_sha,restored=manifests[1]
        rows=[dict(gate=gate,before={d:CHECK.recovery_domain_digest(baseline['states'][d]) for d in domains},after={d:CHECK.recovery_domain_digest(restored['states'][d]) for d in domains}) for gate,domains in CHECK.RECOVERY_GATE_DOMAINS.items()]
        comparison=dict(**common,kind='recovery_comparison',baselineRef=baseline_ref,baselineSha256=baseline_sha,restoredRef=restored_ref,restoredSha256=restored_sha,observedStartedAt='2026-09-03T00:01:00Z',observedFinishedAt='2026-09-03T00:02:00Z',rows=rows,replayedEventIds=['fixture-event'],postReplayDelivery=[{**item,'status':'processed','publicationCount':1,'inboxProcessedCount':1} for item in state['delivery']],unreadableWitness=dict(fixtureId='fixture-corrupt-backup',backupSha256=hash_value,errorCode='DECRYPTION_MISMATCH',restoreOutcome='failed',readbackOutcome='failed',successfulReadCount=0))
        comparison_ref,_,_=retain('recovery-comparison.yaml',comparison,'measurement_output')
        resource=next(r for r in execution['resources'] if r['id']=='RES-RECOVERY-SANDBOX');config_path=root/resource['configurationRef'];config=load_yaml(config_path)
        config['configuration']['recoveryBaseline']=dict(baselineRef=baseline_ref,baselineSha256=baseline_sha,approvedReplayEventIds=['fixture-event'],approvedComparisonContexts=[{key:item[key] for key in ('referenceId','method','comparisonContextId')} for item in baseline['states']['valueComparisons']]);write_yaml(config_path,config)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
