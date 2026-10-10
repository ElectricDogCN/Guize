#!/usr/bin/env python3
"""Validate the V1 API, examples, safety declarations and compatibility.

Local refs only: this checker must never fetch an untrusted schema or follow a
reference outside contracts/openapi. Runtime enforcement is verified by later
consumer/integration tasks; this file validates the frozen contract itself.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import copy
from email.parser import Parser
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote, urlsplit, parse_qs

import yaml
from jsonschema import Draft202012Validator, FormatChecker
from openapi_spec_validator import validate
from intent_hash import IntentError, intent_digest, normalize_path, normalize_query

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / 'contracts/openapi'
ENTRY = CONTRACT / 'common/openapi.yaml'
METHODS = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace'}
FORMATS = FormatChecker()

API_IDENTITY = {
    'openapi': '3.1.1',
    'jsonSchemaDialect': 'https://json-schema.org/draft/2020-12/schema',
    'x-contract-id': 'OPENAPI-V1',
}


@FORMATS.checks('credential-free-endpoint')
def valid_credential_free_endpoint(value):
    if not isinstance(value, str):
        return True
    try:
        value.encode('utf-8', errors='strict')
        uri = urlsplit(value)
        _ = uri.port
    except (UnicodeError, ValueError):
        return False
    return (uri.scheme in {'http', 'https', 'smb', 'nfs'} and bool(uri.hostname)
            and uri.username is None and uri.password is None
            and not uri.query and not uri.fragment and '?' not in value and '#' not in value
            and '%' not in uri.netloc and not any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value)
            and '\\' not in value)


@FORMATS.checks('source-root')
def valid_source_root(value):
    if not isinstance(value, str):
        return True
    try:
        value.encode('utf-8', errors='strict')
    except UnicodeError:
        return False
    return (bool(value) and not any(c in value for c in '\\%:')
            and not any(ord(c) < 32 or ord(c) == 127 for c in value)
            and all(part not in {'', '.', '..'} for part in value.split('/')))


@FORMATS.checks('base64url')
def valid_base64url(value):
    if not isinstance(value, str):
        return True
    if not re.fullmatch(r'[A-Za-z0-9_-]+', value) or len(value) % 4 == 1:
        return False
    try:
        decoded = base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)
        return base64.urlsafe_b64encode(decoded).rstrip(b'=').decode('ascii') == value
    except (ValueError, binascii.Error):
        return False


class ContractError(ValueError):
    pass


class UniqueLoader(yaml.SafeLoader):
    """Do not let YAML silently discard duplicate paths, codes or schema keys."""


def unique_mapping(loader, node, deep=False):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if key in result:
            raise ContractError(f'duplicate YAML key: {key}')
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping)


def read_yaml(path):
    return yaml.load(Path(path).read_text(encoding='utf-8'), Loader=UniqueLoader)


def resolve(document, file=ENTRY, boundary=CONTRACT, chain=(), documents=None):
    """Resolve local refs; assertion siblings are unsupported and fail closed."""
    if documents is None:
        file, boundary = Path(file).resolve(), Path(boundary).resolve()
        documents = {}
    if isinstance(document, list):
        return [resolve(value, file, boundary, chain, documents) for value in document]
    if not isinstance(document, dict):
        return document
    if '$ref' in document:
        reference = document['$ref']
        if not isinstance(reference, str) or '://' in reference or reference.startswith(('/', '\\')):
            raise ContractError(f'nonlocal ref: {reference}')
        name, _, fragment = reference.partition('#')
        target = (file.parent / unquote(name)).resolve() if name else file
        if not target.is_relative_to(boundary):
            raise ContractError(f'ref escapes contract boundary: {reference}')
        key = (str(target), fragment)
        if key in chain:
            raise ContractError(f'recursive ref needs an explicit supported strategy: {reference}')
        if target not in documents:
            documents[target] = read_yaml(target)
        value = documents[target]
        if fragment:
            if not fragment.startswith('/'):
                raise ContractError(f'unsupported anchor: {reference}')
            try:
                for token in fragment[1:].split('/'):
                    token = unquote(token).replace('~1', '/').replace('~0', '~')
                    value = value[int(token)] if isinstance(value, list) else value[token]
            except (KeyError, IndexError, ValueError, TypeError) as exc:
                raise ContractError(f'unresolved ref: {reference}') from exc
        result = resolve(value, target, boundary, chain + (key,), documents)
        annotation_keys = {'title', 'summary', 'description', '$comment', 'x-i18n'}
        sibling_keys = set(document) - {'$ref'}
        if sibling_keys - annotation_keys:
            raise ContractError(f'unsupported ref assertion siblings: {sorted(sibling_keys - annotation_keys)}')
        for name in sibling_keys - {'x-i18n'}:
            if not isinstance(document[name], str):
                raise ContractError(f'ref annotation must be text: {name}')
        if 'x-i18n' in sibling_keys and not isinstance(document['x-i18n'], dict):
            raise ContractError('ref translations must be an annotation mapping')
        siblings = {k: resolve(v, file, boundary, chain, documents) for k, v in document.items() if k != '$ref'}
        if not isinstance(result, dict):
            if siblings:
                raise ContractError(f'non-object ref has siblings: {reference}')
            return result
        return {**result, **siblings}
    return {key: resolve(value, file, boundary, chain, documents) for key, value in document.items()}


def operations(spec):
    for path, item in spec['paths'].items():
        for method, operation in item.items():
            if method in METHODS:
                yield path, method, operation


def walk(value):
    if isinstance(value, dict):
        yield value
        for key, child in value.items():
            if key == 'x-i18n' or (key == 'value' and ('summary' in value or 'description' in value)):
                continue
            if key != 'examples' or not isinstance(child, list):
                yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def validate_instance(value, schema):
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FORMATS)
    errors = sorted(validator.iter_errors(value), key=lambda e: str(e.path))
    if errors:
        raise ContractError('; '.join(f'{list(e.path)}: {e.message}' for e in errors))


def verify_proposed_approval(spec, value):
    """Check contract examples, not server identity/ACL or approval enforcement."""
    validate_instance(value, spec['components']['schemas']['ApprovalRequest'])
    intent = value['requestIntent']
    try:
        path = normalize_path(intent['path'])
        query = normalize_query(intent['query'])
        if path != intent['path'] or query != intent['query']:
            raise ContractError('approval proposal must carry the canonical request')
        matches = []
        for template, method, operation in operations(spec):
            if method.upper() != intent['method']:
                continue
            parts = re.split(r'(\{[A-Za-z0-9]+\})', '/api/v1' + template)
            pattern = ''.join('(?P<' + part[1:-1] + '>[^/]+)' if part.startswith('{') else re.escape(part) for part in parts)
            matched = re.fullmatch(pattern, path)
            if matched:
                matches.append((operation, matched.groupdict()))
        if len(matches) != 1:
            raise ContractError('approval target does not resolve to one operation')
        operation, path_values = matches[0]
        if operation['operationId'] != value['action'] or not operation['x-authorization'].get('approval'):
            raise ContractError('approval action differs from protected target')
        for name, parameter_value in path_values.items():
            parameter = next(p for p in operation['parameters'] if p['in'] == 'path' and p['name'] == name)
            validate_instance(unquote(parameter_value), parameter['schema'])
        primary_ids = [v for k, v in path_values.items() if k.endswith('Id')]
        if primary_ids and value['resourceId'] != unquote(primary_ids[0]):
            raise ContractError('approval primary resource differs from path')
        if not primary_ids and not value['resourceId'].startswith('col_'):
            raise ContractError('collection approval needs a server-issued collection resource')
        parameters = {p['name']: p for p in operation['parameters'] if p['in'] == 'query'}
        if set(query) - set(parameters):
            raise ContractError('approval contains undeclared query parameters')
        for name, values in query.items():
            if len(values) != 1:
                raise ContractError('unsupported repeated scalar approval query')
            validate_instance(values[0], parameters[name]['schema'])
        body = intent['body']
        if 'approvalId' in body:
            raise ContractError('proposal excludes only the approvalId transport carrier')
        schema = copy.deepcopy(operation['requestBody']['content']['application/json']['schema'])
        schema.get('properties', {}).pop('approvalId', None)
        schema['required'] = [name for name in schema.get('required', []) if name != 'approvalId']
        validate_instance(body, schema)
        if 'expectedRevision' in body and body['expectedRevision'] != value['revision']:
            raise ContractError('approval primary revision differs from business request')
        actual = intent_digest(operation['operationId'], value['resourceId'], value['revision'],
                               intent['method'], path, query, body, approval_carrier=True)
        if actual != value['payloadHash']:
            raise ContractError('approval intent digest mismatch')
    except IntentError as exc:
        raise ContractError(str(exc)) from exc
    return True


def bilingual(node, label):
    for key in ('title', 'description', 'summary'):
        if not isinstance(node.get(key), str):
            continue
        translations = node.get('x-i18n', {})
        for language in ('zh-CN', 'en-US'):
            text = translations.get(language, {}).get(key)
            if not isinstance(text, str) or not text.strip():
                raise ContractError(f'{label} missing {language} {key}')
        if translations['en-US'][key] != node[key]:
            raise ContractError(f'{label} English {key} differs from primary text')


def parse_http(text):
    if '\r\n\r\n' not in text:
        raise ContractError('HTTP sample requires CRLF header separator')
    head, body = text.split('\r\n\r\n', 1)
    first, _, raw_headers = head.partition('\r\n')
    parsed = Parser().parsestr(raw_headers)
    headers = {}
    for key in parsed.keys():
        normalized = key.lower()
        if normalized in headers or len(parsed.get_all(key)) != 1:
            raise ContractError('duplicate HTTP sample header')
        headers[normalized] = parsed.get(key)
    if 'content-length' in headers and int(headers['content-length']) != len(body.encode('utf-8')):
        raise ContractError('HTTP sample Content-Length mismatch')
    return first, headers, body


def verify_http_samples(spec, samples):
    inventory = {op['operationId']:(path,method,op) for path,method,op in operations(spec)}
    seen=set()
    scenarios=set()
    for sample in samples:
        oid=sample['operationId']
        scenario=sample.get('scenario', 'baseline')
        if not isinstance(scenario,str) or not re.fullmatch(r'[a-z][a-z0-9-]{0,63}',scenario):
            raise ContractError('invalid HTTP scenario')
        if (oid,scenario) in scenarios or oid not in inventory:
            raise ContractError('duplicate/unknown HTTP sample operation scenario')
        scenarios.add((oid,scenario))
        seen.add(oid)
        path,method,op=inventory[oid]
        first,headers,body=parse_http(sample['request'])
        parts=first.split(' ')
        if len(parts)!=3 or parts[0]!=method.upper() or parts[2]!='HTTP/1.1':
            raise ContractError('HTTP sample method/version mismatch')
        uri=urlsplit(parts[1])
        if uri.scheme or uri.netloc or not uri.path.startswith('/api/v1/') or uri.fragment:
            raise ContractError('HTTP sample URI must use the versioned relative gateway')
        actual=uri.path[len('/api/v1'):]
        pattern='^'+re.sub(r'\\\{[A-Za-z0-9]+\\\}',r'([^/]+)',re.escape(path))+'$'
        matched=re.match(pattern,actual)
        if not matched:raise ContractError('HTTP sample path mismatch')
        names=re.findall(r'\{([^}]+)\}',path)
        path_values=dict(zip(names,matched.groups()))
        query=parse_qs(uri.query,keep_blank_values=True)
        declared_query={p['name'] for p in op.get('parameters',[]) if p['in']=='query'}
        if set(query)-declared_query or any(len(values)!=1 for values in query.values()):
            raise ContractError('undeclared or repeated HTTP scalar query')
        for parameter in op.get('parameters',[]):
            where,name=parameter['in'],parameter['name']
            value=headers.get(name.lower()) if where=='header' else path_values.get(name) if where=='path' else query.get(name,[None])[0]
            if value is None:
                if parameter.get('required'):raise ContractError('missing required HTTP sample parameter: '+name)
                continue
            schema=parameter['schema']
            if schema.get('type')=='integer':
                try:value=int(value)
                except ValueError as exc:raise ContractError('invalid integer HTTP parameter') from exc
            validate_instance(value,schema)
        if op['x-authorization']['mode']=='AUTHENTICATED':
            bearer=bool(re.fullmatch(r'Bearer [A-Za-z0-9_-]{16,256}',headers.get('authorization','')))
            cookie=bool(re.fullmatch(r'guize_session=[A-Za-z0-9_-]{32,256}',headers.get('cookie','')))
            if ('authorization' in headers and not bearer) or ('cookie' in headers and not cookie):
                raise ContractError('malformed HTTP sample authentication')
            if bearer == cookie:
                raise ContractError('authenticated HTTP sample requires exactly one declared bearer or cookie identity')
            scheme='BearerAuth' if bearer else 'SessionCookie'
            if {scheme:[]} not in op['security']:
                raise ContractError('HTTP identity scheme is not declared')
            if cookie and method not in {'get','head','options'}:
                csrf=next((p for p in op['parameters'] if p['in']=='header' and p['name']=='X-CSRF-Token'),None)
                if not csrf or 'x-csrf-token' not in headers:
                    raise ContractError('cookie mutation requires CSRF token')
                validate_instance(headers['x-csrf-token'],csrf['schema'])
        if op.get('requestBody'):
            if headers.get('content-type')!='application/json':raise ContractError('HTTP request media mismatch')
            validate_instance(json.loads(body),op['requestBody']['content']['application/json']['schema'])
            if oid == 'createApproval':
                verify_proposed_approval(spec, json.loads(body))
        elif body:
            raise ContractError('unexpected HTTP request body')
        response_first,response_headers,response_body=parse_http(sample['response'])
        response_parts=response_first.split(' ',2)
        if len(response_parts)!=3 or response_parts[0]!='HTTP/1.1' or response_parts[1] not in op['responses']:
            raise ContractError('HTTP sample status mismatch')
        response=op['responses'][response_parts[1]]
        for name,definition in response.get('headers',{}).items():
            header_value=response_headers.get(name.lower())
            if header_value is None:
                if definition.get('required'):
                    raise ContractError('missing required HTTP response header: '+name)
            else:
                validate_instance(header_value,definition['schema'])
        content_type=response_headers.get('content-type')
        if content_type not in response['content']:raise ContractError('HTTP sample response media mismatch')
        content=response['content'][content_type]
        value=json.loads(response_body) if content_type=='application/json' else response_body
        validate_instance(value,content['schema'])
        if oid in {'createRole','replaceRole'} and response_parts[1].startswith('2'):
            requested=json.loads(body)['capabilities']
            if set(value['data']['capabilities']) != set(requested):
                raise ContractError('role response capabilities must exactly match the requested set')
        if oid in {'registerWorker','heartbeatWorker'} and response_parts[1]=='200':
            lease=value['data'];credential=lease['credential'];request_value=json.loads(body)
            if (any(credential[key]!=lease[key] for key in ('workerId','leaseId','expiresAt'))
                    or request_value['workerId']!=lease['workerId']
                    or (oid=='heartbeatWorker' and request_value['leaseId']!=lease['leaseId'])):
                raise ContractError('worker credential must bind the exact authenticated worker lease')
        if (oid in {'createStepUp','createStepUpPasskeyChallenge'}
                and response_parts[1]=='201'):
            request_value=json.loads(body)
            if any(value['data'][key]!=request_value[key] for key in ('action','resourceId','payloadHash')):
                raise ContractError('step-up response must retain the exact requested tuple')
        if content_type=='application/json' and response_headers.get('x-trace-id')!=value['traceId']:
            raise ContractError('HTTP sample trace header/body mismatch')
        if response_headers.get('cache-control')!='no-store':raise ContractError('control HTTP sample cannot be shared-cached')
        if op['x-authorization'].get('approval') and body:
            approved=json.loads(body).get('approvalId')
            if approved and approved!=headers['x-approval-id']:raise ContractError('HTTP sample approval header/body mismatch')
    if seen!=set(inventory):raise ContractError('missing HTTP operation samples')
    for oid,(_,method,operation) in inventory.items():
        if operation['x-authorization']['mode']=='AUTHENTICATED' and method not in {'get','head','options'}:
            if not {(oid,'baseline'),(oid,'cookie-csrf')} <= scenarios:
                raise ContractError('missing bearer or cookie-CSRF HTTP mutation scenario')
    if ('getArtifactContent','cursor-second-page') not in scenarios:
        raise ContractError('missing consumable artifact cursor HTTP scenario')
    return len(scenarios)



def verify_contract_guarantees(spec, error_map):
    schemas=spec['components']['schemas']
    inventory={op['operationId']:op for _,_,op in operations(spec)}
    for name in ('SourceCredentialReference','PublicAsset'):
        if schemas[name].get('additionalProperties') is not False:
            raise ContractError('dedicated safe response must reject private extensions: '+name)
    for oid in ('rollbackPolicy','rollbackConfiguration'):
        request=inventory[oid]['requestBody']['content']['application/json']['schema']
        if not {'expectedRevision','targetRevision','approvalId'} <= set(request.get('required',[])) or not inventory[oid].get('x-rollback-binding'):
            raise ContractError('rollback must bind explicit current and target revisions')
    credential=schemas['WorkerCredential']
    if (credential.get('additionalProperties') is not False
            or not {'accessToken','workerId','leaseId','audience','expiresAt','permissions'} <= set(credential.get('required',[]))
            or credential['properties']['permissions']['items'].get('const')!='worker.self'):
        raise ContractError('worker credential must be closed and scoped to self control')
    for oid in ('registerWorker','heartbeatWorker'):
        binding=inventory[oid].get('x-worker-credential-binding',{})
        if (binding.get('maxLifetimeSeconds')!=300 or not all(binding.get(k) for k in ('subject','resource','issuance','renewal','replay'))
                or 'credential' not in inventory[oid]['responses']['200']['content']['application/json']['schema']['properties']['data']['required']):
            raise ContractError('worker lease requires a short-lived bound credential and renewal policy')
    for oid in ('setSourceVisibility','releaseAssetQuarantine'):
        operation=inventory.get(oid,{})
        auth=operation.get('x-authorization',{})
        if not auth.get('stepUp') or not auth.get('approval') or not operation.get('x-resource-binding'):
            raise ContractError('administrator safety transition requires protected resource binding')
    if not inventory.get('requestConfigurationAssistance',{}).get('x-assistant-boundary') or not inventory.get('getConfigurationAssistance',{}).get('x-resource-binding'):
        raise ContractError('configuration assistance needs bounded asynchronous request and authorized result')
    terminal={'SUCCEEDED','PARTIAL_SUCCESS','FAILED','CANCELLED'}
    accepted=set(schemas['TaskAccepted']['properties']['status'].get('enum',[]))
    if not accepted or accepted & terminal:
        raise ContractError('202 acceptance must exclude terminal task states')
    if not terminal <= set(schemas['Task']['properties']['status'].get('enum',[])):
        raise ContractError('durable Task must preserve terminal states')
    pending=inventory['createApproval']['responses']['201']['content']['application/json']['schema']['properties']['data']
    if pending['properties']['status'].get('const')!='PENDING':
        raise ContractError('creation response schema must enforce PENDING approval')
    progress=inventory['putPlaybackProgress']
    body=progress['requestBody']['content']['application/json']['schema']
    binding=progress.get('x-resource-binding',{})
    if ('assetId' in body['properties'] or binding.get('primary')!='path.assetId'
            or binding.get('related')!=['body.versionId'] or not binding.get('invariants')):
        raise ContractError('playback progress must bind the path asset to its authorized immutable version')
    artifact=inventory['getArtifactContent']
    inputs={p['name']:p for p in artifact['parameters'] if p['in']=='query'}
    if not {'cursor','limit'} <= set(inputs) or not artifact.get('x-pagination-binding',{}).get('reauthorizeEachPage'):
        raise ContractError('artifact content must accept scoped bounded pagination')
    failure=schemas['TaskFailure']
    if (failure.get('additionalProperties') is not False
            or not {'code','retryable','attempts','details'} <= set(failure.get('required',[]))
            or set(failure['properties']['code'].get('enum',[]))!=set(error_map)
            or failure['properties']['details']!=schemas['ErrorDetails']):
        raise ContractError('durable failure must use bounded redacted stable catalog data')
    for state in ('FAILED','PARTIAL_SUCCESS'):
        guards=schemas['Task'].get('allOf',[])
        if not any(state in g.get('if',{}).get('properties',{}).get('status',{}).get('enum',[])
                   and 'failure' in g.get('then',{}).get('required',[]) for g in guards):
            raise ContractError('terminal failed Task requires durable failure')
    for name,required in [('Rendition',{'profileVersionId'}),('DerivedArtifact',{'pipelineVersionId','parametersHash'})]:
        if not required <= set(schemas[name].get('required',[])):
            raise ContractError('processing provenance must identify exact immutable versions and parameters')
    permissions=set()
    for operation in inventory.values():
        auth=operation['x-authorization']
        if auth['mode']=='AUTHENTICATED':
            permissions.add(auth['permission'])
            permissions.update(auth.get('requiredCapabilities',[]))
            permissions.update(auth.get('conditionalCapabilities',[]))
    capability=schemas['CapabilityId']
    if set(capability.get('enum',[]))!=permissions:
        raise ContractError('capability catalog must exactly cover supported authenticated permissions')
    for name in ('RoleDraft','RoleReplacement'):
        if schemas[name]['properties']['capabilities']['items']!=capability:
            raise ContractError('role mutations must reject unknown capabilities')
    for oid in ('createStepUp','createStepUpPasskeyChallenge'):
        binding=inventory[oid].get('x-step-up-challenge-binding',{})
        if (binding.get('purpose')!='STEP_UP' or binding.get('tuple')!=['action','resourceId','payloadHash']
                or not binding.get('subject') or not binding.get('verification') or not binding.get('execution')):
            raise ContractError('PASSKEY step-up needs an authenticated purpose and exact tuple binding')
    challenge=inventory['createStepUpPasskeyChallenge']
    if challenge['x-authorization']['mode']!='AUTHENTICATED':
        raise ContractError('step-up options must require authentication')
    result=challenge['responses']['201']['content']['application/json']['schema']['properties']['data']
    if result['properties']['purpose'].get('const')!='STEP_UP' or not {'action','resourceId','payloadHash','purpose'} <= set(result['required']):
        raise ContractError('step-up challenge schema must enforce purpose and exact tuple')

def verify(spec=None, catalog=None, coverage=None):
    spec = resolve(read_yaml(ENTRY)) if spec is None else spec
    catalog = read_yaml(CONTRACT / 'common/errors.yaml') if catalog is None else catalog
    coverage = read_yaml(Path(__file__).with_name('coverage.yaml')) if coverage is None else coverage
    validate(spec)
    if (any(spec.get(key) != value for key, value in API_IDENTITY.items())
            or spec.get('info', {}).get('version') != '1.0.0'):
        raise ContractError('wrong API version, contract identity or JSON Schema dialect')
    errors = catalog.get('errors', [])
    codes = [item['code'] for item in errors]
    if len(codes) != len(set(codes)) or not codes:
        raise ContractError('error codes must be nonempty and unique')
    error_map = {item['code']: item for item in errors}
    if catalog.get('contractId') != 'ERROR-CATALOG-V1':
        raise ContractError('wrong error contract identity')
    for item in errors:
        if not re.fullmatch(r'[A-Z]+_[A-Z0-9_]+', item['code']):
            raise ContractError('non-English error code')
        if not 400 <= item['httpStatus'] <= 599 or not isinstance(item['retryable'], bool):
            raise ContractError('invalid error HTTP/retry semantics')
        if item.get('alarmLevel') not in {'INFO', 'WARNING', 'ERROR', 'CRITICAL'}:
            raise ContractError('missing error alarm level')
        if not item.get('documentation', '').startswith('https://'):
            raise ContractError('missing error documentation')
        if any(not item.get('action', {}).get(lang) for lang in ('zh-CN','en-US')):
            raise ContractError('missing localized error action')
        bilingual(item, item['code'])
    verify_contract_guarantees(spec, error_map)
    for node in walk(spec):
        bilingual(node, 'OpenAPI object')
    ids, requirements, example_count = set(), set(), 0
    exact_coverage = []
    for path, method, operation in operations(spec):
        oid = operation['operationId']
        if oid in ids or not re.fullmatch(r'[a-z][A-Za-z0-9]+', oid):
            raise ContractError(f'duplicate/non-English operationId: {oid}')
        ids.add(oid)
        auth = operation.get('x-authorization', {})
        if not operation.get('security') or not auth.get('permission') or not auth.get('scope'):
            raise ContractError(f'{oid}: authentication and authorization intent required')
        if auth.get('mode') not in {'AUTHENTICATED','PUBLIC_RATE_LIMITED'}:
            raise ContractError(f'{oid}: invalid authorization mode')
        public = auth['mode'] == 'PUBLIC_RATE_LIMITED'
        if public != (operation['security'] == [{}]):
            raise ContractError(f'{oid}: public/authenticated security mismatch')
        params = operation.get('parameters', [])
        parameter_map = {(p['in'], p['name']): p for p in params}
        if len(parameter_map) != len(params):
            raise ContractError(f'{oid}: duplicate parameter')
        names = set(re.findall(r'\{([^}]+)\}', path))
        declared = {p['name'] for p in params if p['in'] == 'path' and p['required']}
        if names != declared:
            raise ContractError(f'{oid}: path parameters do not match')
        if method not in {'get','head','options'}:
            key = parameter_map.get(('header','Idempotency-Key'))
            policy = operation.get('x-idempotency', {})
            if not key or not key.get('required') or policy.get('retentionSeconds') != 86400:
                raise ContractError(f'{oid}: required idempotency key/policy missing')
            if any(not policy.get(k) for k in ('scope','samePayload','differentPayload','inFlight','durability')):
                raise ContractError(f'{oid}: incomplete idempotency behavior')
        if auth.get('stepUp') and not parameter_map.get(('header','X-Step-Up-Proof'), {}).get('required'):
            raise ContractError(f'{oid}: step-up header required')
        if auth.get('approval') and not parameter_map.get(('header','X-Approval-Id'), {}).get('required'):
            raise ContractError(f'{oid}: action-bound approval header required')
        if method not in {'get','head','options'} and any(not operation['x-idempotency'].get(key) for key in ('fingerprint','reauthorization','expiredEphemeralResult')):
            raise ContractError(f'{oid}: unsafe idempotent replay boundary')
        if oid == 'createPublicPlaybackPlan':
            body = operation['requestBody']['content']['application/json']['schema']
            if body['properties']['allowTemporaryTranscode'].get('const') is not False or not operation.get('x-no-expensive-work'):
                raise ContractError('public playback cannot trigger expensive work')
        if oid == 'createPlaybackPlan' and ('202' not in operation['responses'] or not operation.get('x-playback-readiness')):
            raise ContractError('playback preparation needs asynchronous task response')
        if oid in {'getSourceCredentialReference','changeSourceCredentialReference'} and (not auth.get('stepUp') or auth.get('permission') != 'source.credential.manage'):
            raise ContractError('protected credential reference operation lacks high-risk gate')
        if oid == 'mergeAsset' and not operation.get('x-multi-resource-invariants'):
            raise ContractError('multi-resource merge lacks both-resource invariants')
        if oid == 'createPasskeyChallenge':
            allowed = {'INTERNAL_INVALID_REQUEST', 'INTERNAL_IDEMPOTENCY_CONFLICT',
                       'INTERNAL_RATE_LIMITED', 'INTERNAL_UNAVAILABLE', 'INTERNAL_ERROR'}
            if not set(operation.get('x-error-codes', [])) <= allowed:
                raise ContractError('anonymous passkey options cannot expose account-dependent errors')
            if not operation.get('x-account-enumeration-policy'):
                raise ContractError('anonymous passkey options need a uniform account privacy policy')
            for media in operation['responses']['201']['content'].values():
                options = media['schema']['properties']['data']['properties']['publicKey']
                if ('allowCredentials' not in options.get('required', [])
                        or options['properties']['allowCredentials'].get('maxItems') != 0
                        or options.get('additionalProperties') is not False):
                    raise ContractError('anonymous passkey option schema must enforce uniform discoverable login')
                for example in media['examples'].values():
                    if example['value']['data']['publicKey']['allowCredentials'] != []:
                        raise ContractError('anonymous passkey options must be discoverable and uniform')
        if operation.get('x-long-running') and '202' not in operation['responses']:
            raise ContractError(f'{oid}: asynchronous operation requires 202')
        if not set(operation.get('x-error-codes', [])) <= set(codes):
            raise ContractError(f'{oid}: unknown error code')
        observed_codes = set()
        if operation.get('requestBody'):
            for media in operation['requestBody']['content'].values():
                if not media.get('examples'):
                    raise ContractError(f'{oid}: request examples required')
                for item in media['examples'].values():
                    validate_instance(item['value'], media['schema']); example_count += 1
                    if oid == 'createApproval':
                        verify_proposed_approval(spec, item['value'])
        for status, response in operation['responses'].items():
            if not response.get('headers', {}).get('X-Trace-Id', {}).get('required'):
                raise ContractError(f'{oid}: trace response header required')
            cache=response.get('headers',{}).get('Cache-Control',{})
            if not cache.get('required') or cache.get('schema',{}).get('const')!='no-store':
                raise ContractError(f'{oid}: required no-store response header missing')
            if oid in {'loginPassword','verifyPasskey'} and status=='200':
                issued=response.get('headers',{}).get('Set-Cookie',{})
                if not issued.get('required') or issued.get('schema')!=spec['components']['schemas']['SessionCookieIssuance']:
                    raise ContractError('successful authentication must issue the secure session cookie')
            elif 'Set-Cookie' in response.get('headers',{}):
                raise ContractError('session issuance is only declared on successful authentication')
            content = response.get('content', {})
            if not content:
                raise ContractError(f'{oid}: response schema required (no untraceable 204)')
            for media_type, media in content.items():
                if not media.get('examples'):
                    raise ContractError(f'{oid}: response examples required')
                schema = media['schema']
                if media_type == 'application/json':
                    if 'traceId' not in schema.get('required', []):
                        raise ContractError(f'{oid}: required envelope traceId missing')
                    if status == '202' and 'taskId' not in schema['properties']['data'].get('required', []):
                        raise ContractError(f'{oid}: 202 data.taskId required')
                    if status.startswith(('4','5')):
                        response_codes = set(schema['properties']['code']['enum'])
                        if not response_codes or any(error_map[c]['httpStatus'] != int(status) for c in response_codes):
                            raise ContractError(f'{oid}: error HTTP code mismatch')
                        observed_codes |= response_codes
                elif media_type == 'text/event-stream':
                    if ('header','Last-Event-ID') not in parameter_map or not operation.get('x-stream-schema'):
                        raise ContractError(f'{oid}: resumable SSE schema missing')
                    if 'traceId' not in operation['x-stream-schema'].get('required', []):
                        raise ContractError(f'{oid}: SSE payload traceId required')
                else:
                    raise ContractError(f'{oid}: unreviewed response media type {media_type}')
                for item in media['examples'].values():
                    validate_instance(item['value'], schema); example_count += 1
                    if oid == 'createApproval' and status == '201':
                        if item['value']['data']['status'] != 'PENDING':
                            raise ContractError('approval proposal must not self-approve')
                    if media_type == 'text/event-stream':
                        frames = item['value'].strip().split('\n\n')
                        for frame in frames:
                            data = [line[6:] for line in frame.splitlines() if line.startswith('data: ')]
                            if len(data) != 1:
                                raise ContractError(f'{oid}: missing/bounded SSE data')
                            validate_instance(json.loads(data[0]), operation['x-stream-schema'])
        if observed_codes != set(operation['x-error-codes']):
            raise ContractError(f'{oid}: errors missing or undeclared in responses')
        if oid in {'getDataSource','listDataSources'}:
            data=operation['responses']['200']['content']['application/json']['schema']['properties']['data']
            source=data['properties']['items']['items'] if oid=='listDataSources' else data
            if 'credentialReference' in source['properties'] or source.get('additionalProperties') is not False:
                raise ContractError('ordinary source metadata must be closed and exclude protected references')
        reqs = operation.get('x-requirement-ids', [])
        if not reqs or not operation.get('x-module-id'):
            raise ContractError(f'{oid}: requirement/module trace missing')
        requirements.update(reqs)
        exact_coverage.append({'operationId':oid,'method':method.upper(),'path':path,'moduleId':operation['x-module-id'],'requirementIds':reqs})
    if exact_coverage != coverage['operations']:
        raise ContractError('coverage differs from actual operation inventory')
    required = {f'REQ-V1-{n:04}' for n in (1,2,3,4,5,7,8,9)}
    if not required <= requirements:
        raise ContractError(f'missing assigned requirements: {required-requirements}')
    return {'operations':len(ids),'schemas':len(spec['components']['schemas']),'errorCodes':len(codes),'examples':example_count,'requirements':sorted(requirements)}


def _schema_compat(old, new, direction, location):
    """Conservative gate: accept additive optional objects, reject uncertain changes.

    Requests may gain optional fields but not require new fields or narrow inputs.
    Responses may gain optional fields but cannot remove fields or loosen guarantees.
    Text/meaning/default/security changes require explicit major-version review.
    """
    if old == new:
        return
    if not isinstance(old, dict) or not isinstance(new, dict):
        raise ContractError(f'{location}: changed schema')
    old_props, new_props = old.get('properties', {}), new.get('properties', {})
    if not set(old_props) <= set(new_props):
        raise ContractError(f'{location}: removed schema field')
    old_required, new_required = set(old.get('required', [])), set(new.get('required', []))
    if direction == 'request' and not new_required <= old_required:
        raise ContractError(f'{location}: new required request field')
    if direction == 'response' and not old_required <= new_required:
        raise ContractError(f'{location}: lost required response field')
    # A new required response field is safe only when old consumers tolerate additions.
    if set(new_props)-set(old_props) and old.get('additionalProperties') is False and direction == 'response':
        raise ContractError(f'{location}: old strict response consumers reject added fields')
    for name in old_props:
        _schema_compat(old_props[name], new_props[name], direction, location+'.'+name)
    handled={'properties','required'}
    if isinstance(old.get('items'),dict) and isinstance(new.get('items'),dict):
        _schema_compat(old['items'],new['items'],direction,location+'[]');handled.add('items')
    if 'enum' in old and 'enum' in new:
        if any(value not in new['enum'] for value in old['enum']):
            raise ContractError(f'{location}: enum value removed')
        handled.add('enum')
    left={k:v for k,v in old.items() if k not in handled}
    right={k:v for k,v in new.items() if k not in handled}
    if left != right:
        raise ContractError(f'{location}: schema constraints/default/meaning changed')


def compatible(old, new, old_catalog, new_catalog):
    if old_catalog != new_catalog:
        raise ContractError('stable error catalog changed; major-version review required')
    if (old['servers'] != new['servers']
            or any(old.get(key) != new.get(key) for key in API_IDENTITY)
            or old['info']['version'] != new['info']['version']):
        raise ContractError('base/version changed')
    if old['components']['securitySchemes'] != new['components']['securitySchemes']:
        raise ContractError('authentication scheme changed')
    # Exported models are also consumed directly, including models without routes.
    for name, schema in old['components']['schemas'].items():
        replacement=new['components']['schemas'].get(name)
        if replacement is None:
            raise ContractError('removed exported component schema: '+name)
        for direction in ('request','response'):
            _schema_compat(schema,replacement,direction,'components.schemas.'+name)
    new_ops={(path,method):op for path,method,op in operations(new)}
    for path,method,left in operations(old):
        if (path,method) not in new_ops:
            raise ContractError('removed API operation')
        right=new_ops[(path,method)]
        for key in ('operationId','security','x-authorization','x-idempotency','x-long-running','x-error-codes','summary','description',
                    'x-multi-resource-invariants','x-resource-binding','x-no-expensive-work','x-playback-readiness',
                    'x-account-enumeration-policy','x-pagination-binding','x-step-up-challenge-binding',
                    'x-rollback-binding','x-worker-credential-binding','x-assistant-boundary',
                    'x-source-visibility-authorization'):
            if left.get(key) != right.get(key):
                raise ContractError(f'{path}: operation meaning/security changed: {key}')
        # Parameters and request required/media types cannot silently change.
        if left.get('parameters') != right.get('parameters'):
            raise ContractError(f'{path}: parameter contract changed')
        if bool(left.get('x-stream-schema')) != bool(right.get('x-stream-schema')):
            raise ContractError(f'{path}: stream contract presence changed')
        if left.get('x-stream-schema'):
            _schema_compat(left['x-stream-schema'],right['x-stream-schema'],'response',path+'.stream')
        old_body,new_body=left.get('requestBody'),right.get('requestBody')
        if bool(old_body)!=bool(new_body):
            raise ContractError(f'{path}: request presence changed')
        if old_body:
            if old_body.get('required')!=new_body.get('required') or set(old_body['content'])!=set(new_body['content']):
                raise ContractError(f'{path}: request requirement/media changed')
            for media,body in old_body['content'].items():
                _schema_compat(body['schema'],new_body['content'][media]['schema'],'request',path+'.request')
        if set(left['responses']) != set(right['responses']):
            raise ContractError(f'{path}: response status changed')
        for status,response in left['responses'].items():
            other=right['responses'][status]
            if response.get('headers')!=other.get('headers') or set(response['content'])!=set(other['content']):
                raise ContractError(f'{path}: response header/media changed')
            for media,body in response['content'].items():
                _schema_compat(body['schema'],other['content'][media]['schema'],'response',path+'.'+status)
    return True


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-ref', help='Actual Git integration baseline; fail if baseline API missing unless --initial-baseline.')
    parser.add_argument('--initial-baseline', action='store_true')
    parser.add_argument('--bundle', type=Path, help='Write a resolved OpenAPI artifact outside canonical source.')
    args=parser.parse_args()
    spec=resolve(read_yaml(ENTRY)); result=verify(spec)
    samples=json.loads((CONTRACT/'common/http-samples.json').read_text(encoding='utf-8'))
    result['httpSamples']=verify_http_samples(spec,samples)
    if args.base_ref:
        import tempfile
        proc=subprocess.run(['git','ls-tree','-r','--name-only',args.base_ref,'--','contracts/openapi'],cwd=ROOT,capture_output=True,text=True,check=True)
        paths=proc.stdout.splitlines()
        entry_path=ENTRY.relative_to(ROOT).as_posix()
        if entry_path not in paths:
            if not args.initial_baseline:
                raise ContractError('base has no API; initial-baseline approval is required')
            result['compatibility']='INITIAL_BASELINE (no prior published API in actual Git base)'
        else:
            with tempfile.TemporaryDirectory(prefix='guize-openapi-base-') as directory:
                temp=Path(directory)
                for name in paths:
                    target=temp/name; target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(subprocess.check_output(['git','show',args.base_ref+':'+name],cwd=ROOT))
                old_entry=temp/entry_path; boundary=temp/'contracts/openapi'
                old=resolve(read_yaml(old_entry),old_entry,boundary)
                compatible(old,spec,read_yaml(boundary/'common/errors.yaml'),read_yaml(CONTRACT/'common/errors.yaml'))
                result['compatibility']='PASS against actual Git base '+args.base_ref
    if args.bundle:
        output=args.bundle.resolve()
        if output.is_relative_to(CONTRACT):
            raise ContractError('bundle must not overwrite canonical contract source')
        output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(yaml.safe_dump(spec,allow_unicode=True,sort_keys=False),encoding='utf-8')
    print(json.dumps({'status':'PASS',**result},ensure_ascii=False))


if __name__ == '__main__':
    main()
