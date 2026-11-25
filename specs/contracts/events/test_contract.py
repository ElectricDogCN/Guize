"""Contract and compatibility regression tests; not runtime acceptance."""
from datetime import timedelta
from pathlib import Path
import copy,json,tempfile,unittest,shutil
from check_contract import (
    BASE, CORE, EXECUTION_EVENTS, ROOT, ContractViolation, EventContracts,
    compare_versions, parse_event_time, read,
)

class EventContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contracts=EventContracts()
        cls.samples={name:json.loads((ROOT/'specs/contracts/events/examples'/f'{name}-v1.json').read_text()) for name,version in cls.contracts.entries}
    def example(self,name):return copy.deepcopy(self.samples[name])
    def rejected(self,event,code=None):
        with self.assertRaises(ContractViolation) as caught:self.contracts.validate(event)
        if code:self.assertEqual(caught.exception.code,code)
    def test_all_ten_examples(self):
        self.assertEqual(len(CORE), 10)
        for name in CORE:
            self.contracts.validate(self.samples[name])
    def test_required_envelope_fields(self):
        for name in ['eventId','aggregateId','occurredAt','producer','traceId','payload']:
            with self.subTest(name=name):
                event=self.example('asset.created');del event[name];self.rejected(event,'EVENT_SCHEMA_INVALID')
    def test_required_payload_fields(self):
        for (name,version),schema in self.contracts.schemas.items():
            for field in schema['allOf'][1]['properties']['payload']['required']:
                with self.subTest(event=name,field=field):
                    event=self.example(name);del event['payload'][field];self.rejected(event,'EVENT_SCHEMA_INVALID')
    def test_unknown_payload_does_not_silently_extend_version(self):
        event=self.example('asset.created');event['payload']['newMeaning']='unknown';self.rejected(event)
    def test_unknown_envelope(self):
        event=self.example('asset.created');event['credential']='opaque-invalid-field';self.rejected(event)
    def test_unknown_type_and_version_are_unsupported(self):
        for field,value in [('eventType','asset.unrecognized'),('eventVersion',2)]:
            event=self.example('asset.created');event[field]=value;self.rejected(event,'EVENT_UNSUPPORTED_VERSION')
    def test_boolean_version_is_not_integer_version(self):
        event=self.example('asset.created');event['eventVersion']=True;self.rejected(event,'EVENT_INVALID_IDENTITY')
    def test_numeric_sse_cursor_is_not_domain_event_id(self):
        event=self.example('task.status.changed');event['eventId']='123';self.rejected(event)
    def test_aggregate_identity_binds_each_payload(self):
        for name in self.samples:
            event=self.example(name);event['aggregateId']='other_wrong';self.rejected(event,'EVENT_AGGREGATE_MISMATCH')
    def test_aggregate_type_and_producer(self):
        for field,value in [('aggregateType','Wrong'),('producer','untrusted-worker')]:
            event=self.example('replica.verified');event[field]=value;self.rejected(event)
    def test_revision_positive_non_boolean(self):
        for value in [0,-1,True,'1']:
            event=self.example('asset.created');event['payload']['revision']=value;self.rejected(event)
    def test_timestamps_checked(self):
        for value in ['not-a-time','2026-10-14']:
            event=self.example('asset.created');event['occurredAt']=value;self.rejected(event)
    def test_fact_does_not_follow_occurrence(self):
        event=self.example('asset.created');event['payload']['createdAt']='2026-10-15T00:00:00Z';self.rejected(event,'EVENT_FACT_AFTER_OCCURRENCE')
    def test_rfc3339_lowercase_occurrence(self):
        event=self.example('asset.created');event['occurredAt']='2026-10-14t00:00:00z';self.contracts.validate(event)
    def test_rfc3339_equivalent_offset_occurrence(self):
        event=self.example('asset.created');event['occurredAt']='2026-10-14T01:00:00+01:00';self.contracts.validate(event)
    def test_etag_not_treated_as_full_hash(self):
        event=self.example('source.object.observed');event['payload']['etag']='weak-provider-validator';self.contracts.validate(event)
    def test_unavailable_observation_remains_observation(self):
        event=self.example('source.object.observed');event['payload']['availability']='UNAVAILABLE';self.contracts.validate(event)
    def test_source_confirmation_required(self):
        event=self.example('source.object.deleted');event['payload']['confirmation']='TIMED_OUT';self.rejected(event)
    def test_source_deletion_cannot_encode_asset_deletion(self):
        event=self.example('source.object.deleted');event['payload']['deleteAsset']=True;self.rejected(event)
    def test_unknown_and_sample_hashes_are_version_metadata(self):
        for value in ['UNKNOWN','SAMPLE','FULL_VERIFIED']:
            event=self.example('asset.version.created');event['payload']['hashStatus']=value;self.contracts.validate(event)
    def test_cache_is_complete_file_not_slice(self):
        event=self.example('cache.complete.verified');event['payload']['state']='PARTIAL_SLICE';self.rejected(event)
    def test_pinned_cache_class_matches_state(self):
        event=self.example('cache.complete.verified');event['payload']['cacheClass']='PINNED_FILE';self.rejected(event)
        event['payload']['state']='PINNED_CACHE';self.contracts.validate(event)
    def test_upload_is_not_verified_replica(self):
        event=self.example('replica.verified');event['payload']['status']='UPLOADED_UNVERIFIED';self.rejected(event)
    def test_hash_mismatch_both_verified_events(self):
        for name in ['cache.complete.verified','replica.verified']:
            event=self.example(name);event['payload']['verification']['actualHash']='b'*64;self.rejected(event,'EVENT_FULL_HASH_MISMATCH')
    def test_full_hash_not_sample_or_malformed(self):
        for name in ['cache.complete.verified','replica.verified']:
            for field,value in [('algorithm','SAMPLE_V1'),('expectedHash','abc'),('actualHash','a'*64+'\n')]:
                event=self.example(name);event['payload']['verification'][field]=value;self.rejected(event)
    def test_verification_time_bound(self):
        event=self.example('replica.verified');event['payload']['verification']['verifiedAt']='2026-10-15T00:00:00Z';self.rejected(event,'EVENT_FACT_AFTER_OCCURRENCE')
    def test_rendition_quality_and_publication(self):
        for field,value in [('qualityStatus','FAIL'),('publicationStatus','DRAFT')]:
            event=self.example('rendition.published');event['payload'][field]=value;self.rejected(event)
    def test_rendition_provenance_required(self):
        for field in ['assetVersionId','inputHash','outputHash','toolVersion','profileVersionId']:
            event=self.example('rendition.published');del event['payload'][field];self.rejected(event)
    def test_artifact_uncertainty_is_preserved(self):
        event=self.example('artifact.published');self.assertTrue(event['payload']['uncertainty']);self.contracts.validate(event)
    def test_artifact_confidence_bounds(self):
        for value in [-0.1,1.1,'certain',True]:
            event=self.example('artifact.published');event['payload']['confidence']=value;self.rejected(event)
    def test_nonfinite_numeric_fields(self):
        for name,field in [('artifact.published','confidence'),('task.status.changed','progress')]:
            event=self.example(name);event['payload'][field]=float('nan');self.rejected(event,'EVENT_NONFINITE_NUMBER')
            for value in [float('inf'),float('-inf')]:
                event['payload'][field]=value;self.rejected(event)
    def test_nonstandard_json_numbers_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'nonstandard.json'
            for value in ['NaN','Infinity','-Infinity']:
                path.write_text('{"number":'+value+'}')
                with self.assertRaisesRegex(ContractViolation,'CONTRACT_NONFINITE_JSON_NUMBER'):read(path)
    def test_thumbnail_generation_truth(self):
        event=self.example('artifact.published');event['payload']['artifactType']='THUMBNAIL_REAL';event['payload']['generated']=True;self.rejected(event)
        event['payload']['generated']=False;self.contracts.validate(event)
        event['payload']['artifactType']='THUMBNAIL_GENERATED';self.rejected(event)
        event['payload']['generated']=True;self.contracts.validate(event)
    def test_task_progress_does_not_change_status(self):
        event=self.example('task.status.changed');event['payload']['progress']=100;self.contracts.validate(event);self.assertEqual(event['payload']['status'],'RUNNING')
    def test_task_same_status_not_a_transition(self):
        event=self.example('task.status.changed');event['payload']['previousStatus']='RUNNING';self.rejected(event,'EVENT_STATUS_UNCHANGED')
    def test_task_priority_and_progress_bounds(self):
        for field,value in [('priority',9),('priority',-1),('progress',101),('progress',-1)]:
            event=self.example('task.status.changed');event['payload'][field]=value;self.rejected(event)
    def test_policy_draft_not_publication(self):
        event=self.example('policy.published');event['payload']['state']='DRAFT';self.rejected(event)
    def test_policy_does_not_embed_executable_definition(self):
        event=self.example('policy.published');event['payload']['definition']='THEN(arbitrary)';self.rejected(event)
    def test_versions_unchanged_compatible(self):compare_versions(self.contracts,self.contracts)
    def test_common_envelope_mutation_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);shutil.copytree(ROOT/'contracts',root/'contracts')
            path=root/'contracts/events/event-envelope.schema.json';envelope=read(path);envelope['required'].remove('traceId');path.write_text(json.dumps(envelope))
            changed=EventContracts(root);event=self.example('asset.created');del event['traceId']
            self.rejected(event,'EVENT_SCHEMA_INVALID');changed.validate(event)
            with self.assertRaisesRegex(ContractViolation,'EVENT_ENVELOPE_MUTATED'):compare_versions(self.contracts,changed)
    def test_old_version_removed_rejected(self):
        changed=copy.copy(self.contracts);changed.entries=dict(self.contracts.entries);del changed.entries[('asset.created',1)]
        with self.assertRaisesRegex(ContractViolation,'EVENT_VERSION_REMOVED'):compare_versions(self.contracts,changed)
    def test_existing_schema_mutation_rejected(self):
        changed=copy.copy(self.contracts);changed.schemas=copy.deepcopy(self.contracts.schemas);changed.schemas[('asset.created',1)]['title']='changed'
        with self.assertRaisesRegex(ContractViolation,'EVENT_VERSION_MUTATED'):compare_versions(self.contracts,changed)
    def test_existing_semantic_mutation_rejected(self):
        changed=copy.copy(self.contracts);changed.entries=copy.deepcopy(self.contracts.entries);changed.entries[('source.object.deleted',1)]['semantics']='deletes logical asset'
        with self.assertRaisesRegex(ContractViolation,'EVENT_VERSION_SEMANTICS_MUTATED'):compare_versions(self.contracts,changed)
    def test_new_version_can_coexist_without_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);shutil.copytree(ROOT/'contracts',root/'contracts')
            catalog=json.loads((root/'contracts/events/catalog.json').read_text());entry=copy.deepcopy(catalog['events'][2]);self.assertEqual(entry['eventType'],'asset.created')
            entry['eventVersion']=2;entry['schema']=entry['schema'].replace('-v1.','-v2.');catalog['events'].append(entry)
            schema=copy.deepcopy(self.contracts.schemas[('asset.created',1)]);schema['$id']=BASE+entry['schema'];schema['allOf'][1]['properties']['eventVersion']['const']=2
            schema['allOf'][1]['properties']['payload']['properties']['description']={'type':'string'}
            (root/'contracts/events'/entry['schema']).write_text(json.dumps(schema));(root/'contracts/events/catalog.json').write_text(json.dumps(catalog))
            upgraded=EventContracts(root);compare_versions(self.contracts,upgraded)
            event=self.example('asset.created');event['eventVersion']=2;event['payload']['description']='v2 optional data';upgraded.validate(event)
            self.rejected(event,'EVENT_UNSUPPORTED_VERSION');event['eventVersion']=1;self.rejected(event,'EVENT_SCHEMA_INVALID')
    def test_all_execution_examples(self):
        self.assertEqual(len(EXECUTION_EVENTS), 9)
        for name in sorted(EXECUTION_EVENTS):
            with self.subTest(event=name):
                entry = self.contracts.validate(self.example(name))
                self.assertEqual(entry['producerModule'], 'MOD-TASK')
                self.assertEqual(set(entry['consumers']), {'MOD-AUDIT', 'MOD-OBS'})

    def test_fencing_and_versions_are_positive_exact_integers(self):
        for field in ('fencing', 'planVersion', 'stepVersion', 'revision'):
            for value in (0, True, '1', 9007199254740992):
                with self.subTest(field=field, value=value):
                    event = self.example('task.attempt.result.accepted')
                    event['payload'][field] = value
                    self.rejected(event, 'EVENT_SCHEMA_INVALID')

    def test_lease_and_reservation_expiry_after_occurrence(self):
        for name in ('task.attempt.leased', 'task.resource.reserved'):
            event = self.example(name)
            event['payload']['expiresAt'] = event['occurredAt']
            with self.subTest(event=name):
                self.rejected(event, 'EVENT_EXPIRES_BEFORE_OR_AT_OCCURRENCE')

    def test_execution_result_time_matches_committed_fact(self):
        event = self.example('task.attempt.result.accepted')
        event['payload']['acceptedAt'] = (parse_event_time(event['occurredAt']) + timedelta(seconds=1)).isoformat()
        self.rejected(event, 'EVENT_FACT_AFTER_OCCURRENCE')

    def test_historical_core_versions_remain_valid(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / 'contracts/events', root / 'contracts/events')
            path = root / 'contracts/events/catalog.json'
            catalog = read(path)
            catalog['events'] = [
                entry for entry in catalog['events'] if entry['eventType'] in CORE
            ]
            path.write_text(json.dumps(catalog), encoding='utf-8')
            historical = EventContracts(root, historical=True)
            compare_versions(historical, self.contracts)
            with self.assertRaisesRegex(ContractViolation, 'CATALOG_INCOMPLETE'):
                EventContracts(root)

    def test_effective_schema_dependency_must_be_version_owned(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / 'contracts/events', root / 'contracts/events')
            path = root / 'contracts/events/task/task.plan.accepted-v1.schema.json'
            schema = read(path)
            schema['allOf'][1]['properties']['payload']['properties']['taskId'] = {
                '$ref': BASE + 'task/task.step.ready-v1.schema.json'
            }
            path.write_text(json.dumps(schema), encoding='utf-8')
            with self.assertRaisesRegex(ContractViolation, 'CATALOG_UNREGISTERED_SCHEMA_REFERENCE'):
                EventContracts(root)

    def test_execution_catalog_does_not_expand_consumers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / 'contracts/events', root / 'contracts/events')
            path = root / 'contracts/events/catalog.json'
            catalog = read(path)
            entry = next(row for row in catalog['events'] if row['eventType'] == 'task.resource.reserved')
            entry['consumers'].append('MOD-WORKER')
            path.write_text(json.dumps(catalog), encoding='utf-8')
            with self.assertRaisesRegex(ContractViolation, 'CATALOG_INVALID_EXECUTION_OWNERSHIP'):
                EventContracts(root)


    def test_compatibility_preserves_boolean_schema_constants(self):
        changed = copy.copy(self.contracts)
        changed.schemas = copy.deepcopy(self.contracts.schemas)
        payload = changed.schemas[('artifact.published', 1)]['allOf'][1]['properties']['payload']
        generated_schema = payload['allOf'][1]['then']['properties']['generated']
        self.assertIs(generated_schema['const'], True)
        generated_schema['const'] = 1
        with self.assertRaisesRegex(ContractViolation, 'EVENT_VERSION_MUTATED'):
            compare_versions(self.contracts, changed)

    def test_catalog_version_constant_keeps_json_type(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            shutil.copytree(ROOT / 'contracts/events', root / 'contracts/events')
            path = root / 'contracts/events/task/task.plan.accepted-v1.schema.json'
            schema = read(path)
            schema['allOf'][1]['properties']['eventVersion']['const'] = True
            path.write_text(json.dumps(schema), encoding='utf-8')
            with self.assertRaisesRegex(ContractViolation, 'CATALOG_SCHEMA_IDENTITY_MISMATCH'):
                EventContracts(root)

    def test_cancellation_and_later_success_examples_have_distinct_attempts(self):
        cancellation = self.example('task.attempt.cancelled')
        lease = self.example('task.attempt.leased')
        result = self.example('task.attempt.result.accepted')
        self.assertEqual(cancellation['aggregateId'], lease['aggregateId'])
        self.assertGreater(cancellation['payload']['revision'], lease['payload']['revision'])
        self.assertNotEqual(result['aggregateId'], cancellation['aggregateId'])
        self.assertEqual(result['payload']['stepId'], lease['payload']['stepId'])
        self.assertGreater(result['payload']['fencing'], cancellation['payload']['fencing'])

if __name__=='__main__':unittest.main(verbosity=2)
