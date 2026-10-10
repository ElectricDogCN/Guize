"""Acceptance and meaningful failure cases for the contract, not runtime claims."""
import copy
import json

import pytest
import yaml

from check_contract import (CONTRACT, ENTRY, ContractError, UniqueLoader,
                            compatible, read_yaml, resolve, validate_instance,
                            verify, verify_http_samples)
from check_contract import operations, verify_proposed_approval
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
    ('retainAsset','x-resource-binding','trust the arbitrary supplied version'),
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
    with pytest.raises(ContractError,match='must not self-approve'):verify(changed,catalog)


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
