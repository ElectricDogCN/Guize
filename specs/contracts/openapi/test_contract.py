"""Acceptance and meaningful failure cases for the contract, not runtime claims."""
import copy
import json

import pytest
import yaml

from check_contract import (CONTRACT, ENTRY, ContractError, UniqueLoader,
                            compatible, read_yaml, resolve, validate_instance,
                            verify, verify_http_samples)
from check_contract import operations, verify_proposed_approval
from check_contract import parse_http
from intent_hash import (IntentError, canonical_json, intent_digest, normalize_path,
                         normalize_query, request_fingerprint)


@pytest.fixture(scope='session')
def baseline():
    return resolve(read_yaml(ENTRY))


@pytest.fixture(scope='session')
def catalog():
    return read_yaml(CONTRACT/'common/errors.yaml')


@pytest.fixture(scope='session')
def samples():
    return json.loads((CONTRACT/'common/http-samples.json').read_text(encoding='utf-8'))


def test_full_standard_and_semantics(baseline,catalog):
    result=verify(baseline,catalog)
    assert result['examples']>=result['operations']
    assert len(result['requirements'])==8



def op_by_id(spec, oid):
    return next(op for _,_,op in operations(spec) if op['operationId']==oid)


@pytest.mark.parametrize('oid',['loginPassword','verifyPasskey'])
def test_authenticated_session_is_issued_with_browser_security(baseline,catalog,samples,oid):
    op=op_by_id(baseline,oid)
    header=op['responses']['200']['headers']['Set-Cookie']
    assert header['required']
    sample=next(s for s in samples if s['operationId']==oid)
    _,headers,_=parse_http(sample['response'])
    validate_instance(headers['set-cookie'],header['schema'])
    changed=copy.deepcopy(baseline)
    op_by_id(changed,oid)['responses']['200']['headers'].pop('Set-Cookie')
    with pytest.raises(ContractError,match='issue'):verify(changed,catalog)


@pytest.mark.parametrize('suffix',[
    '; Path=/; HttpOnly; SameSite=Strict',
    '; Path=/; Secure; SameSite=Strict',
    '; Path=/; Secure; HttpOnly; SameSite=None',
    '; Path=/; Secure; HttpOnly; SameSite=Strict; Domain=example.com',
])
def test_issued_session_cannot_drop_browser_security(baseline,suffix):
    with pytest.raises(ContractError):
        validate_instance('guize_session='+'x'*32+suffix,baseline['components']['schemas']['SessionCookieIssuance'])


@pytest.mark.parametrize('mutation',['missing','short','ambiguous','malformed-cookie'])
def test_cookie_writes_require_explicit_csrf_and_one_identity(baseline,samples,mutation):
    changed=copy.deepcopy(samples)
    sample=next(s for s in changed if s.get('scenario')=='cookie-csrf')
    if mutation=='missing':
        sample['request']=sample['request'].replace('X-CSRF-Token: EXAMPLE_ONLY_INVALID_CSRF_TOKEN_0001\r\n','')
    elif mutation=='short':
        sample['request']=sample['request'].replace('EXAMPLE_ONLY_INVALID_CSRF_TOKEN_0001','short')
    elif mutation=='ambiguous':
        sample['request']=sample['request'].replace('Host:','Authorization: Bearer EXAMPLE_ONLY_INVALID_TOKEN\r\nHost:')
    else:
        sample['request']=sample['request'].replace('guize_session=EXAMPLE_ONLY_INVALID_SESSION_00001','guize_session=short')
    with pytest.raises(ContractError):verify_http_samples(baseline,changed)


def test_http_scenarios_cover_bearer_and_cookie_for_every_authenticated_write(baseline,samples):
    cases={(s['operationId'],s['scenario']) for s in samples}
    for _,method,op in operations(baseline):
        if method not in {'get','head','options'} and op['x-authorization']['mode']=='AUTHENTICATED':
            assert (op['operationId'],'baseline') in cases
            assert (op['operationId'],'cookie-csrf') in cases


def test_duplicate_http_scenario_is_rejected(baseline,samples):
    changed=copy.deepcopy(samples)
    changed.append(copy.deepcopy(changed[0]))
    with pytest.raises(ContractError,match='duplicate'):verify_http_samples(baseline,changed)


@pytest.mark.parametrize('name',['credentialReference','providerToken','secret'])
@pytest.mark.parametrize('oid',['getDataSource','listDataSources'])
def test_ordinary_source_response_cannot_carry_private_fields(baseline,name,oid):
    media=op_by_id(baseline,oid)['responses']['200']['content']['application/json']
    value=copy.deepcopy(media['examples']['illustrative']['value'])
    data=value['data']['items'][0] if oid=='listDataSources' else value['data']
    data[name]='PRIVATE_EXAMPLE_MUST_BE_REJECTED'
    with pytest.raises(ContractError):validate_instance(value,media['schema'])


@pytest.mark.parametrize('oid,field',[
    ('getSourceCredentialReference','credentialValue'),
    ('getSourceCredentialReference','providerToken'),
    ('getSourceCredentialReference','nestedSecret'),
    ('getPublicAsset','sourcePath'),('getPublicAsset','credentials'),
    ('getPublicAsset','acl'),
])
def test_dedicated_safe_response_rejects_private_extensions(baseline,oid,field):
    media=op_by_id(baseline,oid)['responses']['200']['content']['application/json']
    value=copy.deepcopy(media['examples']['illustrative']['value'])
    value['data'][field]={'secret':'PRIVATE_EXAMPLE_MUST_BE_REJECTED'}
    with pytest.raises(ContractError):validate_instance(value,media['schema'])


@pytest.mark.parametrize('oid',['createRole','replaceRole'])
@pytest.mark.parametrize('scenario',['baseline','cookie-csrf'])
def test_role_wire_response_cannot_expand_requested_capabilities(baseline,samples,oid,scenario):
    changed=copy.deepcopy(samples)
    sample=next(s for s in changed if s['operationId']==oid and s['scenario']==scenario)
    head,body=sample['response'].split('\r\n\r\n',1)
    value=json.loads(body)
    value['data']['capabilities'].append('asset.play')
    wire=json.dumps(value,ensure_ascii=False,separators=(',',':'))
    import re
    head=re.sub(r'Content-Length: [0-9]+','Content-Length: '+str(len(wire.encode('utf-8'))),head)
    sample['response']=head+'\r\n\r\n'+wire
    with pytest.raises(ContractError,match='exactly match'):verify_http_samples(baseline,changed)


@pytest.mark.parametrize('name,mutation',[
    ('Replica','remove-model'),('Replica','remove-field'),('Replica','remove-enum'),
    ('RetentionHold','remove-model'),('RetentionHold','remove-field'),
])
def test_exported_models_remain_compatible_without_operations(baseline,catalog,name,mutation):
    changed=copy.deepcopy(baseline)
    model=changed['components']['schemas'][name]
    if mutation=='remove-model':
        del changed['components']['schemas'][name]
    elif mutation=='remove-field':
        model['properties'].pop(model['required'][0])
    else:
        enum=next(v['enum'] for v in model['properties'].values() if 'enum' in v)
        enum.pop()
    with pytest.raises(ContractError):compatible(baseline,changed,catalog,catalog)


def test_image_search_works_without_text_and_text_modes_require_query(baseline):
    schema=baseline['components']['schemas']['SearchQuery']
    image={'mode':'IMAGE','imageArtifactId':'art_example01','limit':25}
    validate_instance(image,schema)
    image.pop('imageArtifactId')
    with pytest.raises(ContractError):validate_instance(image,schema)
    for mode in ('KEYWORD','SEMANTIC','HYBRID'):
        with pytest.raises(ContractError):validate_instance({'mode':mode,'limit':25},schema)
        validate_instance({'mode':mode,'query':'example','limit':25},schema)


@pytest.mark.parametrize('oid',['rollbackPolicy','rollbackConfiguration'])
def test_rollback_approval_binds_current_and_target_revision(baseline,oid):
    operation=op_by_id(baseline,oid)
    media=operation['requestBody']['content']['application/json']
    payload=copy.deepcopy(media['examples']['illustrative']['value'])
    resource='pol_example01' if oid=='rollbackPolicy' else 'cfg_example01'
    path='/api/v1/'+('policies/' if oid=='rollbackPolicy' else 'configurations/')+resource+':rollback'
    body={key:value for key,value in payload.items() if key!='approvalId'}
    proposal={'action':oid,'resourceId':resource,'revision':body['expectedRevision'],
              'payloadHash':intent_digest(oid,resource,body['expectedRevision'],'POST',path,{},body,approval_carrier=True),
              'requestIntent':{'method':'POST','path':path,'query':{},'body':body},'reason':'Exact rollback target review'}
    verify_proposed_approval(baseline,proposal)
    altered=copy.deepcopy(proposal);altered['requestIntent']['body']['targetRevision']=2
    with pytest.raises(ContractError,match='digest mismatch'):verify_proposed_approval(baseline,altered)
    payload.pop('targetRevision')
    with pytest.raises(ContractError):validate_instance(payload,media['schema'])


@pytest.mark.parametrize('oid',['registerWorker','heartbeatWorker'])
@pytest.mark.parametrize('field',['workerId','leaseId','expiresAt'])
def test_worker_wire_credential_cannot_bind_a_different_lease(baseline,samples,oid,field):
    changed=copy.deepcopy(samples);sample=next(s for s in changed if s['operationId']==oid and s['scenario']=='baseline')
    head,body=sample['response'].split('\r\n\r\n',1);value=json.loads(body)
    value['data']['credential'][field]='2026-10-09T12:02:00Z' if field=='expiresAt' else 'wrk_foreign01' if field=='workerId' else 'lse_foreign01'
    wire=json.dumps(value,ensure_ascii=False,separators=(',',':'))
    import re
    head=re.sub(r'Content-Length: [0-9]+','Content-Length: '+str(len(wire.encode('utf-8'))),head)
    sample['response']=head+'\r\n\r\n'+wire
    with pytest.raises(ContractError,match='exact authenticated worker lease'):verify_http_samples(baseline,changed)


@pytest.mark.parametrize('permission',['worker.bootstrap','asset.publish','admin.all'])
def test_worker_credential_cannot_grant_user_or_bootstrap_permission(baseline,permission):
    media=op_by_id(baseline,'registerWorker')['responses']['200']['content']['application/json']
    value=copy.deepcopy(media['examples']['illustrative']['value']);value['data']['credential']['permissions']=[permission]
    with pytest.raises(ContractError):validate_instance(value,media['schema'])


@pytest.mark.parametrize('oid,field',[
    ('setSourceVisibility','platformAcl'),('setSourceVisibility','approvalId'),
    ('releaseAssetQuarantine','assetVersionId'),('releaseAssetQuarantine','reviewFindingId'),
    ('releaseAssetQuarantine','approvalId'),
])
def test_admin_transitions_cannot_omit_target_or_approval(baseline,oid,field):
    media=op_by_id(baseline,oid)['requestBody']['content']['application/json']
    value=copy.deepcopy(media['examples']['illustrative']['value']);value.pop(field)
    with pytest.raises(ContractError):validate_instance(value,media['schema'])


def test_source_owner_can_share_and_retract_without_admin_public_authority(baseline):
    operation=op_by_id(baseline,'setSourceVisibility')
    assert operation['x-authorization']['permission']=='source.owner'
    guard=operation['x-source-visibility-authorization']
    assert guard['ownerTransitions']==['PRIVATE','SHARED']
    assert guard['administratorIdentityRequired'] is True
    assert guard['additionalCapability']=='source.publish'
    assert guard['administratorTrigger']=='target visibility=ADMIN_PUBLIC OR current visibility=ADMIN_PUBLIC'
    media=operation['requestBody']['content']['application/json'];value=copy.deepcopy(media['examples']['illustrative']['value'])
    value['visibility']='SHARED';validate_instance(value,media['schema'])
    value['visibility']='PRIVATE';value.pop('platformAcl');validate_instance(value,media['schema'])
    value['platformAcl']=[]
    with pytest.raises(ContractError):validate_instance(value,media['schema'])


@pytest.mark.parametrize('mutation',['unknown-principal','unknown-action','raw-secret'])
def test_source_sharing_uses_known_closed_identity_acl_shape(baseline,mutation):
    media=op_by_id(baseline,'setSourceVisibility')['requestBody']['content']['application/json']
    value=copy.deepcopy(media['examples']['illustrative']['value']);entry=value['platformAcl'][0]
    if mutation=='unknown-principal':entry['principalType']='ANONYMOUS'
    elif mutation=='unknown-action':entry['permissions']=['ADMINISTRATOR']
    else:entry['providerToken']='PRIVATE_EXAMPLE_MUST_BE_REJECTED'
    with pytest.raises(ContractError):validate_instance(value,media['schema'])


def test_quarantine_release_finding_is_available_on_exact_version_route(baseline):
    read=op_by_id(baseline,'listAssetSecurityFindings')
    assert read['x-authorization']['stepUp'] and read['x-authorization']['permission']=='asset.security.release'
    media=read['responses']['200']['content']['application/json']
    page=media['examples']['illustrative']['value']
    finding=page['data']['items'][0]
    release=op_by_id(baseline,'releaseAssetQuarantine')['requestBody']['content']['application/json']['examples']['illustrative']['value']
    assert release['reviewFindingId']==finding['id'] and release['assetVersionId']==finding['assetVersionId']
    leaked=copy.deepcopy(page);leaked['data']['items'][0]['sourcePath']='/private/example'
    with pytest.raises(ContractError):validate_instance(leaked,media['schema'])


@pytest.mark.parametrize('oid',['requestConfigurationAssistance','getConfigurationAssistance'])
def test_assistant_declares_real_sensitive_read_proof_transport(baseline,oid):
    operation=op_by_id(baseline,oid)
    assert operation['x-authorization']['stepUp']
    assert operation['x-authorization']['requiredCapabilities']==['config.assist','config.sensitive.read']
    assert any(p['name']=='X-Step-Up-Proof' and p['required'] for p in operation['parameters'])
    assert 'AUTH_STEP_UP_REQUIRED' in operation['responses']['403']['content']['application/json']['schema']['properties']['code']['enum']


@pytest.mark.parametrize('field',['publish','secrets','capabilities','budgetOverride'])
def test_assistant_request_cannot_execute_privileged_changes(baseline,field):
    media=op_by_id(baseline,'requestConfigurationAssistance')['requestBody']['content']['application/json']
    value=copy.deepcopy(media['examples']['illustrative']['value']);value[field]=True
    with pytest.raises(ContractError):validate_instance(value,media['schema'])


@pytest.mark.parametrize('action,field',[('GENERATE_DRAFT','draft'),('ESTIMATE_CAPACITY','capacityEstimate')])
def test_assistant_report_requires_action_specific_output(baseline,action,field):
    media=op_by_id(baseline,'getConfigurationAssistance')['responses']['200']['content']['application/json']
    value=copy.deepcopy(media['examples']['illustrative']['value']);value['data']['action']=action
    with pytest.raises(ContractError,match=field):validate_instance(value,media['schema'])


@pytest.mark.parametrize('status',['SUCCEEDED','PARTIAL_SUCCESS','FAILED','CANCELLED'])
def test_every_202_schema_rejects_terminal_acceptance(baseline,status):
    for _,_,op in operations(baseline):
        if '202' not in op['responses']:continue
        media=op['responses']['202']['content']['application/json']
        value=copy.deepcopy(media['examples']['illustrative']['value'])
        value['data']['status']=status
        with pytest.raises(ContractError):validate_instance(value,media['schema'])
    assert status in baseline['components']['schemas']['Task']['properties']['status']['enum']


@pytest.mark.parametrize('status',['APPROVED','REJECTED','EXPIRED','EXECUTED'])
def test_create_approval_response_schema_cannot_self_approve(baseline,status):
    media=op_by_id(baseline,'createApproval')['responses']['201']['content']['application/json']
    value=copy.deepcopy(media['examples']['illustrative']['value'])
    value['data']['status']=status
    with pytest.raises(ContractError):validate_instance(value,media['schema'])


def test_progress_has_one_asset_identity_and_declares_version_ownership(baseline):
    op=op_by_id(baseline,'putPlaybackProgress')
    media=op['requestBody']['content']['application/json']
    value=copy.deepcopy(media['examples']['illustrative']['value'])
    assert 'assetId' not in value
    value['assetId']='ast_foreign'
    with pytest.raises(ContractError):validate_instance(value,media['schema'])
    assert op['x-resource-binding']['primary']=='path.assetId'
    assert op['x-resource-binding']['related']==['body.versionId']


def test_artifact_content_cursor_is_consumable_by_the_next_page(baseline,samples):
    first=next(s for s in samples if s['operationId']=='getArtifactContent' and s['scenario']=='baseline')
    second=next(s for s in samples if s['operationId']=='getArtifactContent' and s['scenario']=='cursor-second-page')
    _,_,first_body=parse_http(first['response'])
    cursor=json.loads(first_body)['data']['nextCursor']
    assert cursor and 'cursor='+cursor in second['request'].split('\r\n')[0]
    _,_,second_body=parse_http(second['response'])
    assert json.loads(second_body)['data']['nextCursor'] is None


@pytest.mark.parametrize('status',['FAILED','PARTIAL_SUCCESS'])
def test_failed_task_response_requires_durable_redacted_failure(baseline,status):
    media=op_by_id(baseline,'getTask')['responses']['200']['content']['application/json']
    value=copy.deepcopy(media['examples']['illustrative']['value'])
    value['data']['status']=status
    value['data'].pop('failure',None)
    with pytest.raises(ContractError):validate_instance(value,media['schema'])
    value['data']['failure']={'code':'INTERNAL_ERROR','retryable':False,'attempts':1,'details':{}}
    validate_instance(value,media['schema'])


@pytest.mark.parametrize('mutation',[
    {'code':'PROVIDER_FREE_FORM'}, {'attempts':0}, {'attempts':101},
    {'details':{'providerResponse':'secret'}}, {'providerException':'secret'},
])
def test_task_failure_rejects_unstable_unbounded_or_private_context(baseline,mutation):
    value={'code':'INTERNAL_ERROR','retryable':False,'attempts':1,'details':{}}
    value.update(mutation)
    with pytest.raises(ContractError):validate_instance(value,baseline['components']['schemas']['TaskFailure'])


@pytest.mark.parametrize('schema,field',[
    ('Rendition','profileVersionId'),('DerivedArtifact','pipelineVersionId'),
    ('DerivedArtifact','parametersHash'),
])
def test_provenance_is_required_on_the_result_schema(baseline,schema,field):
    result=baseline['components']['schemas'][schema]
    candidates=[]
    def collect(value):
        if isinstance(value,dict):
            if set(result['required']) <= set(value):candidates.append(value)
            for child in value.values():collect(child)
        elif isinstance(value,list):
            for child in value:collect(child)
    for _,_,op in operations(baseline):
        for response in op['responses'].values():
            for media in response['content'].values():
                for example in media['examples'].values():collect(example['value'])
    assert candidates
    value=copy.deepcopy(candidates[0])
    validate_instance(value,result)
    value.pop(field)
    with pytest.raises(ContractError):validate_instance(value,result)


def test_step_up_passkey_options_require_authenticated_exact_purpose_and_tuple(baseline):
    op=op_by_id(baseline,'createStepUpPasskeyChallenge')
    assert op['security']==[{'SessionCookie':[]},{'BearerAuth':[]}]
    media=op['responses']['201']['content']['application/json']
    value=copy.deepcopy(media['examples']['illustrative']['value'])
    value['data']['purpose']='LOGIN'
    with pytest.raises(ContractError):validate_instance(value,media['schema'])
    for oid in ('createStepUp','createStepUpPasskeyChallenge'):
        binding=op_by_id(baseline,oid)['x-step-up-challenge-binding']
        assert binding['tuple']==['action','resourceId','payloadHash']
        assert binding['purpose']=='STEP_UP'


@pytest.mark.parametrize('kind,endpoint',[
    ('HTTP','https://user:password@origin.example/media'),
    ('WEBDAV','https://origin.example/dav?token=secret'),
    ('S3','https://origin.example/bucket#secret'),
    ('SMB','smb://user:password@server.example/share'),
    ('NFS','https://server.example/share'),
    ('HTTP','https://user%40secret@origin.example/media'),
    ('HTTP','https://origin.example\\evil/media'),
    ('HTTP','https://origin.example/media\n'),
])
def test_source_endpoints_cannot_smuggle_inline_credentials(baseline,kind,endpoint):
    value={'name':'Example','kind':kind,'endpoint':endpoint,'root':'media','visibility':'PRIVATE'}
    with pytest.raises(ContractError):validate_instance(value,baseline['components']['schemas']['SourceDraft'])


@pytest.mark.parametrize('name',['RoleDraft','RoleReplacement'])
def test_unknown_permissions_cannot_be_granted_in_role_mutations(baseline,name):
    op=op_by_id(baseline,'createRole' if name=='RoleDraft' else 'replaceRole')
    media=op['requestBody']['content']['application/json']
    value=copy.deepcopy(media['examples']['illustrative']['value'])
    value['capabilities']=['future.root.access']
    with pytest.raises(ContractError):validate_instance(value,media['schema'])


@pytest.mark.parametrize('header',['Cache-Control','Set-Cookie'])
def test_serialized_auth_response_requires_declared_security_headers(baseline,samples,header):
    changed=copy.deepcopy(samples)
    sample=next(s for s in changed if s['operationId']=='loginPassword')
    lines=sample['response'].split('\r\n')
    sample['response']='\r\n'.join(line for line in lines if not line.startswith(header+':'))
    with pytest.raises(ContractError,match='header'):verify_http_samples(baseline,changed)


def test_no_store_is_required_in_every_control_response(baseline,catalog):
    changed=copy.deepcopy(baseline)
    op_by_id(changed,'getTask')['responses']['200']['headers']['Cache-Control'].pop('required')
    with pytest.raises(ContractError,match='no-store'):verify(changed,catalog)



def test_only_successful_logins_declare_session_issuance(baseline):
    locations={(op['operationId'],status) for _,_,op in operations(baseline)
               for status,response in op['responses'].items() if 'Set-Cookie' in response['headers']}
    assert locations=={('loginPassword','200'),('verifyPasskey','200')}


@pytest.mark.parametrize('oid',['loginPassword','verifyPasskey'])
def test_failed_login_cannot_claim_new_session(baseline,catalog,oid):
    changed=copy.deepcopy(baseline)
    op=op_by_id(changed,oid)
    op['responses']['401']['headers']['Set-Cookie']=copy.deepcopy(op['responses']['200']['headers']['Set-Cookie'])
    with pytest.raises(ContractError,match='only declared'):verify(changed,catalog)


@pytest.mark.parametrize('code',[e['code'] for e in read_yaml(CONTRACT/'common/errors.yaml')['errors']])
def test_task_failure_retryability_cannot_disagree_with_catalog(baseline,catalog,code):
    entry=next(e for e in catalog['errors'] if e['code']==code)
    value={'code':code,'retryable':entry['retryable'],'attempts':1,'details':{}}
    validate_instance(value,baseline['components']['schemas']['TaskFailure'])
    value['retryable']=not value['retryable']
    with pytest.raises(ContractError):validate_instance(value,baseline['components']['schemas']['TaskFailure'])


@pytest.mark.parametrize('kind,endpoint',[
    ('HTTP','https://origin.example/media'),('SMB','smb://server.example/share'),
    ('NFS','nfs://server.example/share'),
])
def test_network_source_accepts_typed_credential_free_endpoints(baseline,kind,endpoint):
    value={'name':'Example','kind':kind,'endpoint':endpoint,'root':'media','visibility':'PRIVATE'}
    validate_instance(value,baseline['components']['schemas']['SourceDraft'])


@pytest.mark.parametrize('oid',['createStepUp','createStepUpPasskeyChallenge'])
@pytest.mark.parametrize('key,altered',[
    ('action','deleteAsset'),('resourceId','ast_foreign'),('payloadHash','b'*64),
])
def test_step_up_wire_response_cannot_switch_requested_tuple(baseline,samples,oid,key,altered):
    changed=copy.deepcopy(samples)
    sample=next(s for s in changed if s['operationId']==oid)
    head,body=sample['response'].split('\r\n\r\n',1)
    value=json.loads(body)
    value['data'][key]=altered
    encoded=json.dumps(value,ensure_ascii=False,separators=(',',':'))
    lines=head.split('\r\n')
    head='\r\n'.join('Content-Length: '+str(len(encoded.encode('utf-8'))) if l.startswith('Content-Length: ') else l for l in lines)
    sample['response']=head+'\r\n\r\n'+encoded
    with pytest.raises(ContractError,match='tuple'):verify_http_samples(baseline,changed)




@pytest.mark.parametrize('key,value',[
    ('version','2.0.0'),('x-contract-id','OTHER-CONTRACT'),
    ('jsonSchemaDialect','https://json-schema.org/draft/2019-09/schema'),
])
def test_api_identity_is_frozen_in_validation_and_compatibility(baseline,catalog,key,value):
    changed=copy.deepcopy(baseline)
    if key=='version':changed['info'][key]=value
    else:changed[key]=value
    with pytest.raises(ContractError):compatible(baseline,changed,catalog,catalog)
    with pytest.raises(ContractError,match='identity'):verify(changed,catalog)


def test_lifecycle_operations_require_separate_scope_admission(baseline):
    ids={op['operationId'] for _,_,op in operations(baseline)}
    assert not ids & {'listReplicas','retainAsset','restoreAsset','listRetentionHolds'}
    assert {'listCacheEntries','cacheAsset','evictCacheEntry'} <= ids
    assert {'Replica','RetentionHold'} <= set(baseline['components']['schemas'])


@pytest.mark.parametrize('details',[
    {'credential':'secret-value'},{'sourcePath':'/private/media'},
    {'deniedResourceId':'ast_private'},{'providerResponse':{'authorization':'secret'}},
    {'field':'/private/media'},{'field':'a'*257},{'retryAfterSeconds':86401},
    {'retryAfterSeconds':-1},
])
def test_error_details_reject_unreviewed_or_unbounded_context(baseline,details):
    with pytest.raises(ContractError):
        validate_instance(details,baseline['components']['schemas']['ErrorDetails'])


def test_error_details_accept_only_public_field_and_bounded_retry_hint(baseline):
    validate_instance({'field':'request','retryAfterSeconds':30},
                      baseline['components']['schemas']['ErrorDetails'])


@pytest.mark.parametrize('code',['ACCESS_NOT_FOUND','ACCESS_DENIED','AUTH_LOGIN_LOCKED',
                               'AUTH_REQUIRED','AUTH_INVALID'])
def test_anonymous_passkey_discovery_rejects_account_dependent_errors(baseline,catalog,code):
    changed=copy.deepcopy(baseline)
    op=next(op for _,_,op in operations(changed) if op['operationId']=='createPasskeyChallenge')
    op['x-error-codes'].append(code)
    with pytest.raises(ContractError,match='account-dependent'):verify(changed,catalog)


def test_anonymous_passkey_discovery_has_no_credential_or_account_branch(baseline,catalog):
    changed=copy.deepcopy(baseline)
    op=next(op for _,_,op in operations(changed) if op['operationId']=='createPasskeyChallenge')
    assert set(op['responses'])=={'201','400','409','429','500','503'}
    op['responses']['201']['content']['application/json']['examples']['illustrative']['value']['data']['publicKey']['allowCredentials']=[
        {'type':'public-key','id':'ZXhhbXBsZQ'}]
    with pytest.raises(ContractError,match='uniform'):verify(changed,catalog)


@pytest.mark.parametrize('mutation',['credential-list','missing-list','account-hint'])
def test_anonymous_options_schema_rejects_account_disclosure(baseline,mutation):
    value={'challenge':'ZXhhbXBsZQ','rpId':'guize.example','allowCredentials':[]}
    if mutation=='credential-list':value['allowCredentials']=[{'type':'public-key','id':'ZXhhbXBsZQ'}]
    elif mutation=='missing-list':value.pop('allowCredentials')
    else:value['username']='registered-account'
    with pytest.raises(ContractError):
        validate_instance(value,baseline['components']['schemas']['WebAuthnRequestOptions'])


@pytest.mark.parametrize('value',['usr_example01','ast_example01','apr_','apr_'+('a'*65),'apr_../../secret','apr_example01\n'])
def test_approval_identifier_is_consistent_across_body_header_path_and_result(baseline,value):
    schemas=baseline['components']['schemas']
    with pytest.raises(ContractError):validate_instance(value,schemas['ApprovalId'])
    for _,_,op in operations(baseline):
        for parameter in op.get('parameters',[]):
            if parameter['name'] in {'X-Approval-Id','approvalId'}:
                with pytest.raises(ContractError):validate_instance(value,parameter['schema'])
        for media in op.get('requestBody',{}).get('content',{}).values():
            if 'approvalId' in media['schema'].get('properties',{}):
                body=copy.deepcopy(media['examples']['illustrative']['value'])
                body['approvalId']=value
                with pytest.raises(ContractError):validate_instance(body,media['schema'])
    with pytest.raises(ContractError):validate_instance(value,schemas['Approval']['properties']['id'])


@pytest.mark.parametrize('root',['../../etc','/etc','C:\\Windows','..\\private','media/../private',
                                'media/./private','media//private','media/','%2e%2e/etc',
                                'media/%252e%252e/private','//server/share','media\x00file','\ud800'])
def test_local_source_root_cannot_escape_authorized_mount(baseline,root):
    body={'name':'Local','kind':'LOCAL','endpoint':'mount:media','root':root,'visibility':'PRIVATE'}
    with pytest.raises(ContractError):validate_instance(body,baseline['components']['schemas']['SourceDraft'])


@pytest.mark.parametrize('endpoint',['/etc','C:\\Windows','https://origin.example/','mount:../private','mount:media\n'])
def test_local_source_endpoint_is_an_authorized_mount_alias(baseline,endpoint):
    body={'name':'Local','kind':'LOCAL','endpoint':endpoint,'root':'media','visibility':'PRIVATE'}
    with pytest.raises(ContractError):validate_instance(body,baseline['components']['schemas']['SourceDraft'])


def test_local_source_accepts_relative_unicode_path_under_mount(baseline):
    body={'name':'Local','kind':'LOCAL','endpoint':'mount:media','root':'视频/示例.mp4','visibility':'PRIVATE'}
    validate_instance(body,baseline['components']['schemas']['SourceDraft'])


def test_local_root_portable_pattern_alone_rejects_traversal_and_controls(baseline):
    from jsonschema import Draft202012Validator
    schema=baseline['components']['schemas']['SourceDraft']
    body={'name':'Local','kind':'LOCAL','endpoint':'mount:media','root':'media/file0x.mp4','visibility':'PRIVATE'}
    Draft202012Validator(schema).validate(body)
    for root in ['../../etc','/etc','media/../file','media//file','media\\file','media/%2e%2e','media\n']:
        body['root']=root
        assert list(Draft202012Validator(schema).iter_errors(body))


def test_serialized_http_contracts(baseline,samples):
    assert verify_http_samples(baseline,samples)==len(samples)


@pytest.mark.parametrize('name,value',[
    ('SourceDraft',{'name':'Example','kind':'WEBDAV','endpoint':'https://origin.example/','root':'media','visibility':'PRIVATE','password':'FORBIDDEN_EXAMPLE'}),
    ('SourcePatch',{'expectedRevision':1,'credentialReference':'secretref_example01'}),
    ('SearchQuery',{'query':'Example','mode':'HYBRID','limit':25,'aclScope':['OTHER_USER']}),
    ('SearchQuery',{'query':'Example','mode':'KEYWORD','limit':101}),
    ('SearchQuery',{'query':'Example','mode':'IMAGE','limit':25}),
    ('PublicPlaybackRequest',{'assetVersionId':'ver_example01','supportedCodecs':['AV1'],'protocols':['RANGE'],'allowTemporaryTranscode':True}),
    ('PlaybackRequest',{'assetVersionId':'ver_example01','supportedCodecs':[],'protocols':['RANGE'],'allowTemporaryTranscode':False}),
    ('TaskPriority',{'expectedRevision':1,'priority':9}),
    ('MergeRequest',{'otherAssetId':'ast_example02','expectedRevision':1,'verifiedHash':'a'*64,'reason':'Example merge'}),
    ('SourceCredentialChange',{'expectedRevision':1,'credentialReference':'plaintext-not-reference','reason':'Example change'}),
    ('ArtifactContent',{'artifactId':'art_example01','revision':1,'assetVersionId':'ver_example01','contentKind':'MEDIA_REFERENCE','nextCursor':None}),
    ('PlaybackPlan',{'grantId':'grt_example01','assetVersionId':'ver_example01','renditionId':'rnd_example01','protocol':'RANGE','mediaPath':'https://origin.example/private','expiresAt':'2026-10-09T12:02:00Z','authorizationScopeVersion':1,'rangePolicy':'BOUNDED','grant':'EXAMPLE_ONLY_INVALID_GRANT'}),
    ('PlaybackProgressInput',{'assetId':'ast_example01','versionId':'ver_example01','positionMs':1,'durationMs':10,'completed':False,'lastPlayedAt':'not-a-time','deviceId':'dev_example01'}),
    ('RoleReplacement',{'name':'Example','capabilities':['asset.read']}),
    ('ReauthenticationProof',{'method':'PASSWORD'}),
    ('ReauthenticationProof',{'method':'PASSWORD','password':'EXAMPLE_ONLY','totpCode':'123456'}),
    ('PublicAsset',{'id':'ast_example01','title':'Example','assetType':'VIDEO','currentVersionId':'ver_example01','visibility':'PRIVATE','securityStatus':'SCAN_CLEAN','revision':1,'updatedAt':'2026-10-09T12:00:00Z'}),
    ('ErrorEnvelope',{'code':'ACCESS_DENIED','message':'Denied','details':{}}),
    ('DerivedArtifact',{'id':'art_example01','assetVersionId':'ver_example01','artifactType':'THUMBNAIL_GENERATED','modelVersion':'example-v1','promptVersion':'example-v1','confidence':0.5,'uncertainty':True,'generated':False,'publicationStatus':'DRAFT','revision':1}),
])
def test_reject_unsafe_or_incomplete_inputs_and_outputs(baseline,name,value):
    with pytest.raises(ContractError):validate_instance(value,baseline['components']['schemas'][name])


@pytest.mark.parametrize('mutation', ['idempotency','approval','authentication','trace','sse-trace','bilingual','replay'])
def test_reject_missing_semantic_guards(baseline,catalog,mutation):
    spec=copy.deepcopy(baseline)
    op=spec['paths']['/assets/{assetId}:publish']['post']
    if mutation=='idempotency':op['parameters']=[p for p in op['parameters'] if p['name']!='Idempotency-Key']
    elif mutation=='approval':op['parameters']=[p for p in op['parameters'] if p['name']!='X-Approval-Id']
    elif mutation=='authentication':op['security']=[{}]
    elif mutation=='trace':op['responses']['200']['content']['application/json']['schema']['required'].remove('traceId')
    elif mutation=='sse-trace':spec['paths']['/tasks/{taskId}/events']['get']['x-stream-schema']['required'].remove('traceId')
    elif mutation=='bilingual':op['x-i18n']['zh-CN'].pop('description')
    elif mutation=='replay':op['x-idempotency'].pop('reauthorization')
    with pytest.raises(ContractError):verify(spec,catalog)


def test_duplicate_error_codes_rejected(baseline,catalog):
    duplicate=copy.deepcopy(catalog);duplicate['errors'].append(copy.deepcopy(duplicate['errors'][0]))
    with pytest.raises(ContractError,match='unique'):verify(baseline,duplicate)


@pytest.mark.parametrize('reference',['https://example.invalid/schema.json','../../../../AGENTS.md','%2Ftmp/foreign.yaml'])
def test_external_and_escaping_refs_rejected(reference):
    with pytest.raises(ContractError):resolve({'$ref':reference})


def test_missing_ref_rejected():
    with pytest.raises(ContractError):resolve({'$ref':'schemas.yaml#/NoSuchSchema'})


def test_duplicate_yaml_key_rejected():
    with pytest.raises(ContractError):yaml.load('paths: {}\npaths: {}\n',Loader=UniqueLoader)


@pytest.mark.parametrize('mutation',['operation','request-required','response-field','default','security','error','sse'])
def test_breaking_change_rejected(baseline,catalog,mutation):
    changed=copy.deepcopy(baseline); errors=copy.deepcopy(catalog)
    path='/assets/{assetId}';op=changed['paths'][path]['get']
    if mutation=='operation':changed['paths'].pop(path)
    elif mutation=='request-required':changed['paths']['/data-sources/{sourceId}']['patch']['requestBody']['content']['application/json']['schema']['required'].append('name')
    elif mutation=='response-field':op['responses']['200']['content']['application/json']['schema']['properties']['data']['properties'].pop('title')
    elif mutation=='default':changed['paths']['/assets']['get']['parameters'][-1]['schema']['default']=50
    elif mutation=='security':op['security']=[{}]
    elif mutation=='error':errors['errors'][0]['retryable']=True
    elif mutation=='sse':changed['paths']['/tasks/{taskId}/events']['get']['x-stream-schema']['properties'].pop('traceId')
    with pytest.raises(ContractError):compatible(baseline,changed,catalog,errors)


def test_additive_optional_fields_and_unknown_enums_are_compatible(baseline,catalog):
    changed=copy.deepcopy(baseline)
    request=changed['paths']['/data-sources/{sourceId}']['patch']['requestBody']['content']['application/json']['schema']
    request['properties']['displayHint']={'type':'string'}
    response=changed['paths']['/assets']['get']['responses']['200']['content']['application/json']['schema']['properties']['data']['properties']['items']['items']
    response['properties']['displayHint']={'type':'string'}
    response['properties']['assetType']['enum'].append('FUTURE_SAFE_TYPE')
    assert compatible(baseline,changed,catalog,catalog)


@pytest.mark.parametrize('mutation',['trace','length','approval','identity','missing'])
def test_http_sample_boundary_failures(baseline,samples,mutation):
    changed=copy.deepcopy(samples)
    target=next(s for s in changed if s['operationId']=='publishAsset')
    if mutation=='trace':target['response']=target['response'].replace('X-Trace-Id: trace-example-0001','X-Trace-Id: trace-different-0001',1)
    elif mutation=='length':target['request']=target['request'].replace('Content-Length: ','Content-Length: 999',1)
    elif mutation=='approval':target['request']=target['request'].replace('X-Approval-Id: apr_example01','X-Approval-Id: apr_example02',1)
    elif mutation=='identity':target['request']=target['request'].replace('Authorization: Bearer EXAMPLE_ONLY_INVALID_TOKEN\r\n','')
    elif mutation=='missing':changed.pop()
    with pytest.raises(ContractError):verify_http_samples(baseline,changed)


def test_rfc8785_number_golden_vector():
    # RFC 8785 section 3.2.2.2; expected output is independent of our serializer.
    value={'numbers':[333333333.33333329,1e30,4.50,2e-3,1e-27]}
    assert canonical_json(value)==b'{"numbers":[333333333.3333333,1e+30,4.5,0.002,1e-27]}'


def test_rfc8785_utf16_property_order_golden_vector():
    # Supplementary code points sort before U+FB33 by UTF-16, not Python order.
    value={'\ufb33':7,'😀':6,'€':5,'ö':4,'\u0080':3,'1':2,'\r':1}
    assert canonical_json(value)=='{"\\r":1,"1":2,"\u0080":3,"ö":4,"€":5,"😀":6,"\ufb33":7}'.encode('utf-8')


@pytest.mark.parametrize('value',[float('nan'),float('inf'),9007199254740992,'\ud800',{1:'non-string-key'}])
def test_invalid_jcs_values_fail_closed(value):
    with pytest.raises(IntentError):canonical_json(value)


def protected_context():
    return ['mergeAsset','ast_example01',1,'POST','/api/v1/assets/ast_example01:merge',
            {'mode':['check']},{'otherAssetId':'ast_example02','expectedRevision':1,'otherExpectedRevision':1,
                              'verifiedHash':'a'*64,'reason':'Example merge','nested':{'approvalId':'business-data'}}]


@pytest.mark.parametrize('index,value',[
    (0,'splitAsset'),(1,'ast_example03'),(2,2),(3,'PUT'),
    (4,'/api/v1/assets/ast_example03:merge'),(5,{'mode':['execute']}),
])
def test_protected_intent_binds_all_context_fields(index,value):
    original=protected_context();changed=copy.deepcopy(original);changed[index]=value
    assert intent_digest(*original,approval_carrier=True)!=intent_digest(*changed,approval_carrier=True)


@pytest.mark.parametrize('field,value',[
    ('otherAssetId','ast_example03'),('otherExpectedRevision',2),('verifiedHash','b'*64),
    ('reason','A different business reason'),('nested',{'approvalId':'different-business-data'}),
])
def test_secondary_targets_and_nested_business_fields_remain_in_intent(field,value):
    original=protected_context();changed=copy.deepcopy(original);changed[6][field]=value
    assert intent_digest(*original,approval_carrier=True)!=intent_digest(*changed,approval_carrier=True)


def test_approval_minting_is_not_circular_and_full_fingerprint_keeps_carrier():
    proposal=protected_context();a=copy.deepcopy(proposal);b=copy.deepcopy(proposal)
    a[6]['approvalId']='apr_example01';b[6]['approvalId']='apr_example02'
    expected=intent_digest(*proposal,approval_carrier=True)
    assert intent_digest(*a,approval_carrier=True)==intent_digest(*b,approval_carrier=True)==expected
    assert request_fingerprint(*a[3:],approval_carrier=True)!=request_fingerprint(*b[3:],approval_carrier=True)
    assert request_fingerprint(*proposal[3:],approval_carrier=True,approval_header='apr_example01')==request_fingerprint(*a[3:],approval_carrier=True)
    with pytest.raises(IntentError,match='mismatch'):
        intent_digest(*a,approval_carrier=True,approval_header='apr_example02')
    with pytest.raises(IntentError,match='mismatch'):
        request_fingerprint(*a[3:],approval_carrier=True,approval_header='apr_example02')
    with pytest.raises(IntentError,match='requires'):
        request_fingerprint(*proposal[3:],approval_carrier=True)


def test_undeclared_approval_id_is_business_data_and_request_normalization_is_stable():
    original=protected_context();changed=copy.deepcopy(original)
    original[6]['approvalId']='business-one';changed[6]['approvalId']='business-two'
    assert intent_digest(*original)!=intent_digest(*changed)
    assert normalize_path('/api/v1/assets/%61st_example01:merge')=='/api/v1/assets/ast_example01:merge'
    assert normalize_query('q=hello+world&tag=b&tag=a')=={'q':['hello world'],'tag':['b','a']}
    assert normalize_query('tag=b&tag=a&q=hello%20world')==normalize_query('q=hello+world&tag=b&tag=a')
    assert normalize_query('tag=b&tag=a')!=normalize_query('tag=a&tag=b')


@pytest.mark.parametrize('path',['https://foreign.example/api/v1/assets/a','/api/v1/assets/a?secret=x',
                               '/api/v1/assets/a#fragment','/api/v1/assets/a%2Fb','/api/v1/assets/a%5Cb',
                               '/api/v1/assets//a','/api/v1/assets/../a','/api/v1/assets/%GG',
                               '/api/v1/assets/%FF','/api/v1/assets/\ud800'])
def test_ambiguous_or_invalid_target_paths_fail_closed(path):
    with pytest.raises(IntentError):normalize_path(path)


@pytest.mark.parametrize('sibling,value',[('type','string'),('properties',{}),('required',[]),
    ('enum',[0]),('minimum',0),('maximum',999),('additionalProperties',True),('$id','foreign')])
def test_reference_assertion_siblings_cannot_weaken_constraints(tmp_path,sibling,value):
    target=tmp_path/'schema.yaml';target.write_text('value:\n  type: integer\n  minimum: 1\n',encoding='utf-8')
    with pytest.raises(ContractError,match='assertion siblings'):
        resolve({'outer':{'$ref':'schema.yaml#/value',sibling:value}},file=tmp_path/'entry.yaml',boundary=tmp_path)


def test_reference_annotations_preserve_actual_constraints(tmp_path):
    target=tmp_path/'schema.yaml';target.write_text('value:\n  type: integer\n  minimum: 1\n',encoding='utf-8')
    schema=resolve({'$ref':'schema.yaml#/value','description':'Annotated integer'},file=tmp_path/'entry.yaml',boundary=tmp_path)
    validate_instance(1,schema)
    with pytest.raises(ContractError):validate_instance(0,schema)
    with pytest.raises(ContractError,match='annotation'):
        resolve({'$ref':'schema.yaml#/value','description':{'type':'string'}},file=tmp_path/'entry.yaml',boundary=tmp_path)


@pytest.mark.parametrize('oid,key,new_value',[
    ('mergeAsset','x-multi-resource-invariants',{'authorization':'only one asset needs authorization'}),
    ('cacheAsset','x-resource-binding','trust the arbitrary supplied version'),
    ('createPublicPlaybackPlan','x-no-expensive-work',False),
    ('createPlaybackPlan','x-playback-readiness','issue media grant while still preparing'),
])
@pytest.mark.parametrize('remove',[True,False])
def test_safety_extension_removal_or_meaningful_weakening_is_breaking(baseline,catalog,oid,key,new_value,remove):
    changed=copy.deepcopy(baseline)
    operation=next(op for _,_,op in operations(changed) if op['operationId']==oid)
    if remove:operation.pop(key)
    else:operation[key]=new_value
    with pytest.raises(ContractError):compatible(baseline,changed,catalog,catalog)


@pytest.mark.parametrize('mutation',['missing-intent','hash','action','resource','revision','target','body','approval-carrier'])
def test_approval_proposal_is_complete_and_bound_to_actual_operation(baseline,mutation):
    value=copy.deepcopy(baseline['paths']['/approvals']['post']['requestBody']['content']['application/json']['examples']['illustrative']['value'])
    assert verify_proposed_approval(baseline,value)
    if mutation=='missing-intent':value.pop('requestIntent')
    elif mutation=='hash':value['payloadHash']='a'*64
    elif mutation=='action':value['action']='mergeAsset'
    elif mutation=='resource':value['resourceId']='ast_example02'
    elif mutation=='revision':value['revision']=2
    elif mutation=='target':value['requestIntent']['path']='/api/v1/assets/ast_example02:publish'
    elif mutation=='body':value['requestIntent']['body']['reason']='Changed after approval'
    elif mutation=='approval-carrier':value['requestIntent']['body']['approvalId']='apr_example01'
    with pytest.raises(ContractError):verify_proposed_approval(baseline,value)


@pytest.mark.parametrize('field',['rp','user','challenge','pubKeyCredParams'])
def test_creation_options_require_browser_creation_fields(baseline,field):
    operation=baseline['paths']['/auth/passkeys/registration:options']['post']
    media=operation['responses']['201']['content']['application/json']
    value=copy.deepcopy(media['examples']['illustrative']['value']);value['data']['publicKey'].pop(field)
    with pytest.raises(ContractError):validate_instance(value,media['schema'])


def test_approval_creation_cannot_claim_approval_without_separate_decision(baseline,catalog):
    changed=copy.deepcopy(baseline)
    media=changed['paths']['/approvals']['post']['responses']['201']['content']['application/json']
    media['examples']['illustrative']['value']['data']['status']='APPROVED'
    with pytest.raises(ContractError,match='PENDING|must not self-approve'):verify(changed,catalog)


@pytest.mark.parametrize('mutation',['rp-name','user-id','user-name','displayName','empty-algorithms','wrong-type','padded-id','invalid-id','bad-challenge'])
def test_creation_options_reject_incomplete_or_invalid_wire_data(baseline,mutation):
    media=baseline['paths']['/auth/passkeys/registration:options']['post']['responses']['201']['content']['application/json']
    value=copy.deepcopy(media['examples']['illustrative']['value']);key=value['data']['publicKey']
    if mutation=='rp-name':key['rp'].pop('name')
    elif mutation=='user-id':key['user'].pop('id')
    elif mutation=='user-name':key['user'].pop('name')
    elif mutation=='displayName':key['user'].pop('displayName')
    elif mutation=='empty-algorithms':key['pubKeyCredParams']=[]
    elif mutation=='wrong-type':key['pubKeyCredParams'][0]['type']='password'
    elif mutation=='padded-id':key['user']['id']='YQ=='
    elif mutation=='invalid-id':key['user']['id']='A'
    elif mutation=='bad-challenge':key['challenge']='A'*22+'B'
    with pytest.raises(ContractError):validate_instance(value,media['schema'])
