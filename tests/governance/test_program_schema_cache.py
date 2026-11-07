"""Exact Program structure reuse never replaces fresh format or authority checks."""
import copy
from datetime import datetime,timedelta,timezone
import importlib.util
import itertools
import sys
from pathlib import Path

import pytest
import yaml

ROOT=Path(__file__).resolve().parents[2]
SERIAL=itertools.count()


def load(path,prefix):
    spec=importlib.util.spec_from_file_location(prefix+str(next(SERIAL)),path)
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module
    spec.loader.exec_module(module)
    return module


SNAPSHOTS=load(ROOT/'tests/governance/test_historical_task_snapshot.py','program_structure_fixtures_')
make_history=SNAPSHOTS.make_history


@pytest.fixture
def sample():
    h=load(ROOT/'scripts/check-program-plan-history.py','program_structure_')
    text=(ROOT/h.PROGRAM_SCHEMA).read_text(encoding='utf-8')
    schema=yaml.safe_load(text)
    program=h.load_current(str(ROOT),h.PLAN)
    assert program['status']=='active' and program['recovery']['frozenAt']
    def validator(checker=None,definition=None):
        return h.jsonschema.Draft202012Validator(
            copy.deepcopy(schema if definition is None else definition),
            format_checker=checker if checker is not None else h.jsonschema.FormatChecker())
    return h,text,program,validator


def messages(errors):
    return [error.message for error in errors]


def test_real_nonempty_recovery_reuses_structure_and_checks_format_each_hit(sample):
    h,text,program,make=sample
    checker=h.jsonschema.FormatChecker();actual=h.jsonschema.FormatChecker();formats=[]
    @checker.checks('date-time')
    def observe(value):
        formats.append(value)
        return actual.conforms(value,'date-time')
    validator=make(checker);full=[];previous=sys.getprofile()
    def observe_root(frame,event,arg):
        if (event=='call' and frame.f_code is h._PROGRAM_ITER_ERRORS.__code__
                and frame.f_locals.get('self') is validator
                and frame.f_locals.get('instance') is program):
            full.append(True)
    sys.setprofile(observe_root)
    try:
        assert h.program_schema_failures(validator,text,program)==[]
        assert h.program_schema_failures(validator,text,program)==[]
    finally:sys.setprofile(previous)
    assert len(full)==1
    assert formats==[program['recovery']['frozenAt']]*2
    assert len(h._PROGRAM_STRUCTURE_SUCCESSES)==1


def test_changed_format_result_preserves_current_error_and_is_not_cached(sample):
    h,text,program,make=sample
    checker=h.jsonschema.FormatChecker();validator=make(checker)
    assert not h.program_schema_failures(validator,text,program)
    calls=[]
    @checker.checks('date-time')
    def deny(value):calls.append(value);return False
    expected=messages(validator.iter_errors(program));calls.clear()
    for label in ['first current label','second current label']:
        failures=h.program_schema_failures(validator,text,program)
        assert messages(failures)==expected
        assert [f'{label} Program schema violation: {e.message}' for e in failures]==[
            f'{label} Program schema violation: {message}' for message in expected]
    assert calls==[program['recovery']['frozenAt']]*2
    assert not h._PROGRAM_STRUCTURE_SUCCESSES


@pytest.mark.parametrize('kind',['missing','null','empty','bad-date','wrong-type'])
def test_recovery_shape_and_format_mutations_get_original_errors(sample,kind):
    h,text,program,make=sample
    assert not h.program_schema_failures(make(),text,program)
    changed=copy.deepcopy(program)
    if kind=='missing':changed.pop('recovery')
    elif kind=='null':changed['recovery']=None
    elif kind=='empty':changed['recovery']={}
    elif kind=='bad-date':changed['recovery']['frozenAt']='not-a-date'
    else:changed['recovery']['frozenAt']=23
    checker=h.jsonschema.FormatChecker()
    if kind=='bad-date':
        # Optional format packages differ by environment; exercise a real
        # current checker with a deterministic rejection, without adding one.
        @checker.checks('date-time')
        def current_format(value):return value!='not-a-date'
    validator=make(checker);expected=messages(validator.iter_errors(changed))
    assert messages(h.program_schema_failures(validator,text,changed))==expected
    if kind!='missing':assert expected


def test_program_mutation_revalidates_and_failure_never_enters_success_cache(sample):
    h,text,program,make=sample
    assert not h.program_schema_failures(make(),text,program)
    changed=copy.deepcopy(program);changed['foundationTasks'][0]['title']=42
    validator=make();expected=messages(validator.iter_errors(changed));assert expected
    original_keys=list(h._PROGRAM_STRUCTURE_SUCCESSES)
    for _ in range(2):assert messages(h.program_schema_failures(validator,text,changed))==expected
    assert list(h._PROGRAM_STRUCTURE_SUCCESSES)==original_keys


@pytest.mark.parametrize('path,value',[
    (['properties','schemaVersion'],True),
    (['properties','parallelPolicy','properties','criticalStandalone'],1),
])
def test_python_equal_bool_integer_schema_change_cannot_reuse_structure(sample,path,value):
    h,text,program,make=sample
    assert not h.program_schema_failures(make(),text,program)
    schema=yaml.safe_load(text);target=schema
    for name in path:target=target[name]
    target['const']=value
    # Python dict equality conflates bool/int; JSON Schema const does not.
    assert schema==yaml.safe_load(text)
    validator=make(definition=schema);expected=messages(validator.iter_errors(program));assert expected
    assert messages(h.program_schema_failures(validator,text,program))==expected


@pytest.mark.parametrize('kind',['text-change','schema-change','dynamic-ref','external-ref'])
def test_unknown_or_changed_schema_uses_original_complete_validator(sample,kind):
    h,text,program,make=sample
    assert not h.program_schema_failures(make(),text,program)
    definition={'type':'object','required':['new-required-field']}
    if kind=='text-change':definition=yaml.safe_load(text);changed_text=text+'\n# other actual source\n'
    elif kind=='dynamic-ref':
        definition={'$schema':'https://json-schema.org/draft/2020-12/schema',
                    '$dynamicRef':'#/$defs/required','$defs':{'required':{'required':['new-required-field']}}}
        changed_text=yaml.safe_dump(definition)
    elif kind=='external-ref':
        definition={'$ref':'urn:guize:unavailable-schema'};changed_text=yaml.safe_dump(definition)
    else:changed_text=yaml.safe_dump(definition)
    validator=make(definition=definition);keys=list(h._PROGRAM_STRUCTURE_SUCCESSES)
    if kind=='external-ref':
        with pytest.raises(Exception) as original:list(validator.iter_errors(program))
        with pytest.raises(type(original.value)):h.program_schema_failures(validator,changed_text,program)
    else:
        assert messages(h.program_schema_failures(validator,changed_text,program))==messages(validator.iter_errors(program))
    assert list(h._PROGRAM_STRUCTURE_SUCCESSES)==keys


@pytest.mark.parametrize('kind',['custom-class','keyword-dispatch','type-checker','iter-errors'])
def test_changed_validator_semantics_cannot_reuse_old_structural_success(sample,monkeypatch,kind):
    h,text,program,make=sample
    assert not h.program_schema_failures(make(),text,program)
    def reject(validator,value,instance,schema):
        yield h.jsonschema.ValidationError('fresh custom validator rejection')
    if kind=='custom-class':
        custom=h.jsonschema.validators.extend(h.jsonschema.Draft202012Validator,{'type':reject})
        validator=custom(yaml.safe_load(text),format_checker=h.jsonschema.FormatChecker())
    elif kind=='keyword-dispatch':
        monkeypatch.setitem(h.jsonschema.Draft202012Validator.VALIDATORS,'type',reject);validator=make()
    elif kind=='type-checker':
        checker=h.jsonschema.Draft202012Validator.TYPE_CHECKER.redefine('object',lambda checker,value:False)
        monkeypatch.setattr(h.jsonschema.Draft202012Validator,'TYPE_CHECKER',checker);validator=make()
    else:
        def errors(self,instance,*args,**kwargs):
            yield h.jsonschema.ValidationError('fresh replaced iter_errors')
        monkeypatch.setattr(h.jsonschema.Draft202012Validator,'iter_errors',errors);validator=make()
    expected=messages(validator.iter_errors(program));assert expected
    assert messages(h.program_schema_failures(validator,text,program))==expected


@pytest.mark.parametrize('kind',['cycle','non-json','non-string-key','nonfinite','oversized'])
def test_nonplain_or_unbounded_input_is_not_a_reuse_key(sample,kind):
    h,_,program,_=sample
    if kind=='cycle':program['self']=program
    elif kind=='non-json':program['extra']=object()
    elif kind=='non-string-key':program[1]='value'
    elif kind=='nonfinite':program['extra']=float('nan')
    else:program['extra']=['x']*20001
    assert h._program_json_key(program) is None


def test_shared_plain_values_have_an_immutable_expanded_key_without_mutation(sample):
    h,_,program,_=sample
    shared=['REQ-V1-0010'];document={'left':shared,'right':shared}
    assert h._program_json_key(document)==h._program_json_key({'left':list(shared),'right':list(shared)})
    assert document['left'] is document['right'] is shared
    before=h._program_json_key(document);shared.append('REQ-V1-0001')
    assert before!=h._program_json_key(document)
    assert document['left'] is document['right'] is shared


def test_real_aliased_program_reuses_values_but_rejects_changed_shared_input(sample):
    h,text,program,make=sample
    shared=program['tasks'][0]['requirementIds']
    program['tasks'][1]['requirementIds']=shared
    assert not h.program_schema_failures(make(),text,program)
    assert not h.program_schema_failures(make(),text,program)
    assert program['tasks'][0]['requirementIds'] is program['tasks'][1]['requirementIds']
    shared.append('invalid requirement id')
    validator=make();expected=messages(validator.iter_errors(program));assert expected
    assert messages(h.program_schema_failures(validator,text,program))==expected
    assert program['tasks'][0]['requirementIds'] is program['tasks'][1]['requirementIds']


def test_expansion_budget_rejects_alias_amplification_without_serializing_it(sample):
    h,_,_,_=sample
    tree=['x']
    for _ in range(16):tree=[tree,tree]
    assert h._program_json_key({'expanded':tree}) is None


def test_bounded_residency_evicts_old_successes_and_active_only(sample,monkeypatch):
    h,text,program,make=sample;monkeypatch.setattr(h,'_PROGRAM_STRUCTURE_LIMIT',2)
    old=None
    for number in range(3):
        changed=copy.deepcopy(program);changed['foundationTasks'][0]['title']=f'New valid title {number}'
        assert not h.program_schema_failures(make(),text,changed)
        if old is None:old=(text,h._program_json_key(changed))
    assert len(h._PROGRAM_STRUCTURE_SUCCESSES)==2 and old not in h._PROGRAM_STRUCTURE_SUCCESSES
    frozen=copy.deepcopy(program);frozen['status']='frozen';validator=make();keys=list(h._PROGRAM_STRUCTURE_SUCCESSES)
    assert messages(h.program_schema_failures(validator,text,frozen))==messages(validator.iter_errors(frozen))
    assert list(h._PROGRAM_STRUCTURE_SUCCESSES)==keys


def test_snapshot_factory_keeps_source_text_bound_to_one_live_read(sample,monkeypatch):
    h,_,_,_=sample;values=iter(['type: integer\n','type: string\n']);reads=[]
    def source(root,ref,path):reads.append((root,ref,path));return next(values)
    monkeypatch.setattr(h,'read_ref',source)
    first,text=h.snapshot_validator('repo','HEAD',h.PROGRAM_SCHEMA,'missing',with_source_text=True)
    assert text=='type: integer\n' and len(reads)==1 and not list(first.iter_errors(1))
    second,text=h.snapshot_validator('repo','HEAD',h.PROGRAM_SCHEMA,'missing',with_source_text=True)
    assert text=='type: string\n' and len(reads)==2 and list(second.iter_errors(1))


@pytest.mark.parametrize('mutation',['reviewer','lease','claims'])
def test_warm_structure_does_not_cache_real_historical_entry_authority(sample,make_history,monkeypatch,mutation):
    h,_,_,_=sample;root,commit,entry=make_history('OPS-023')
    registry=h.load_ref(str(root),commit,h.ACTIVE);policy=registry['policy']
    def check(value,label):
        errors=[]
        h.historical_registration_context(str(root),commit,commit,'OPS-023',value,commit,policy,label,errors)
        return errors
    initial=check(registry,'cold actual registration');assert initial==[],initial
    assert h._PROGRAM_STRUCTURE_SUCCESSES
    changed=copy.deepcopy(registry);own=changed['tasks'][0]
    if mutation=='reviewer':own['reviewer']=own['implementer']
    elif mutation=='lease':own['lease']['expiresAt']=(datetime.now(timezone.utc)-timedelta(days=1)).isoformat()
    else:own['exclusivePaths']=['backend/unregistered.py']
    errors=check(changed,'warm current registration')
    assert errors
    assert not any('Program schema violation' in error for error in errors)
    # Task/Registry validators retain their own actual labels. Compare exact
    # original-path errors instead of assuming every layer uses our label.
    monkeypatch.setattr(h,'_PROGRAM_SCHEMA_TEXT_SHA256','force-original-validation')
    assert check(changed,'warm current registration')==errors
