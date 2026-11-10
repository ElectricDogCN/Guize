"""Exact Program structure reuse never replaces fresh format or authority checks."""
import copy
from datetime import datetime,timedelta,timezone
import importlib.util
import itertools
import os
import subprocess
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


def ops023_fixture(make_history, monkeypatch, mutation=None):
    root, commit, entry = make_history("OPS-023", mutation=mutation)
    # The tiny fixture uses explicit configuration overrides when writing its
    # history. The production projection only accepts the ordinary Git view.
    monkeypatch.delenv("GIT_CONFIG_GLOBAL", raising=False)
    monkeypatch.delenv("GIT_CONFIG_NOSYSTEM", raising=False)
    history = load(ROOT / "scripts/check-program-plan-history.py", "ops023_snapshot_")
    tree = SNAPSHOTS.git(root, "rev-parse", commit + "^{tree}")
    monkeypatch.setattr(history, "_OPS023_SNAPSHOT_TREES", {commit: tree})
    monkeypatch.setattr(history, "_ops023_snapshot_validators_match", lambda: True)
    return history, root, commit, entry


def test_ops023_projection_still_runs_both_validators_and_rejects_same_tree_other_oid(make_history, monkeypatch, tmp_path):
    history, root, commit, entry = ops023_fixture(make_history, monkeypatch)
    calls = []
    original_task = history._run_historical_task_file
    original_registry = history.TASK_LINK.validate_task_registry

    def task(snapshot, task_id):
        calls.append(("task", Path(snapshot)))
        return original_task(snapshot, task_id)

    def registry(snapshot, task_id, registry_entry, errors):
        calls.append(("registry", Path(snapshot)))
        return original_registry(snapshot, task_id, registry_entry, errors)

    monkeypatch.setattr(history, "_run_historical_task_file", task)
    monkeypatch.setattr(history.TASK_LINK, "validate_task_registry", registry)
    errors = []
    history.historical_task_snapshot(str(root), commit, "OPS-023", entry, "historical fixture", errors)
    assert errors == [] and [(kind, path.name) for kind, path in calls] == [
        ("task", "pinned-snapshot"), ("registry", "pinned-snapshot")]
    SNAPSHOTS.git(root, "commit", "--allow-empty", "-m", "Different immutable commit with the same tree")
    other = SNAPSHOTS.git(root, "rev-parse", "HEAD")
    assert other != commit and SNAPSHOTS.git(root, "rev-parse", "HEAD^{tree}") == history._OPS023_SNAPSHOT_TREES[commit]
    for i, (revision, task_id) in enumerate(((other, "OPS-023"), (commit[:12], "OPS-023"), (commit, "OPS-999"))):
        temporary = tmp_path / ("unknown-" + str(i))
        temporary.mkdir()
        snapshot, result = history._checkout_task_workspace(str(root), str(temporary), revision, task_id)
        assert result.returncode == 0 and Path(snapshot).name == "snapshot"
        assert (Path(snapshot) / "payload/unrelated.bin").is_file()
        assert not (temporary / "pinned-snapshot").exists()


@pytest.mark.parametrize("shape", ["filter", "mode", "missing", "replacement", "validator", "tree", "attr-command", "bytes", "config-env", "trial-hook"])
def test_ops023_unproved_inputs_use_the_original_dense_checkout(make_history, monkeypatch, tmp_path, shape):
    def mutate(root, task, entry):
        if shape == "filter":
            (root / ".gitattributes").write_text("specs/tasks/OPS-023.md filter=unproved\n", encoding="utf-8")
        elif shape == "mode":
            task.chmod(0o755)
            SNAPSHOTS.git(root, "add", "--chmod=+x", str(task.relative_to(root)))
        elif shape == "missing":
            (root / entry["handoffPath"]).unlink()

    history, root, commit, _ = ops023_fixture(make_history, monkeypatch, mutate)
    if shape == "replacement":
        (root / "payload/unrelated.bin").write_text("replacement\n", encoding="utf-8")
        SNAPSHOTS.git(root, "add", "payload/unrelated.bin")
        SNAPSHOTS.git(root, "commit", "-m", "Replacement tree")
        SNAPSHOTS.git(root, "replace", commit, "HEAD")
    elif shape == "validator":
        monkeypatch.setattr(history, "_ops023_snapshot_validators_match", lambda: False)
    elif shape == "tree":
        monkeypatch.setitem(history._OPS023_SNAPSHOT_TREES, commit, "0" * 40)
    elif shape == "config-env":
        monkeypatch.setenv("GIT_CONFIG_COUNT", "0")
    elif shape in {"attr-command", "bytes", "trial-hook"}:
        original = subprocess.run

        def execute(argv, *args, **kwargs):
            if shape == "attr-command" and argv[1] == "check-attr":
                raise subprocess.CalledProcessError(129, argv)
            result = original(argv, *args, **kwargs)
            if shape == "trial-hook" and argv[1] == "clone" and Path(argv[-1]).name == "pinned-snapshot":
                (Path(argv[-1]) / ".git/hooks/post-index-change").write_bytes(b"#!/bin/sh\nexit 0\n")
            if shape == "bytes" and argv[1] == "checkout" and Path(kwargs["cwd"]).name == "pinned-snapshot":
                path = Path(kwargs["cwd"]) / "specs/tasks/OPS-023.md"
                path.write_bytes(path.read_bytes() + b"\n")
            return result

        monkeypatch.setattr(subprocess, "run", execute)
    snapshot, result = history._checkout_task_workspace(str(root), str(tmp_path), commit, "OPS-023")
    assert result.returncode == 0 and Path(snapshot).name == "snapshot"
    assert (Path(snapshot) / "payload/unrelated.bin").is_file()


def test_ops023_failed_sparse_trial_cannot_mask_dense_failure(make_history, monkeypatch, tmp_path):
    history, root, commit, _ = ops023_fixture(make_history, monkeypatch)
    original = subprocess.run
    monkeypatch.setenv("GIT_LFS_SKIP_SMUDGE", "caller-setting")
    dense_error = subprocess.CompletedProcess([], 19, "original stdout", "original stderr")

    def execute(argv, *args, **kwargs):
        if argv[1] == "sparse-checkout":
            original(argv, *args, **kwargs)
            raise subprocess.CalledProcessError(1, argv)
        if argv[1] == "checkout" and Path(kwargs["cwd"]).name == "snapshot":
            assert "env" not in kwargs and os.environ["GIT_LFS_SKIP_SMUDGE"] == "caller-setting"
            assert not (Path(kwargs["cwd"]) / ".git/info/sparse-checkout").exists()
            return dense_error
        return original(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", execute)
    snapshot, result = history._checkout_task_workspace(str(root), str(tmp_path), commit, "OPS-023")
    assert Path(snapshot).name == "snapshot" and result is dense_error
    assert (tmp_path / "pinned-snapshot/.git/info/sparse-checkout").exists()


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


@pytest.fixture
def historical_task_cli(tmp_path, sample, monkeypatch):
    h, _, _, _ = sample
    snapshot = tmp_path / "snapshot"
    scripts = tmp_path / "validator"
    scripts.mkdir()
    for name in ("check-task-file.py", "program-planning-revision.py"):
        (scripts / name).write_bytes((ROOT / "scripts" / name).read_bytes())
    for name in ("specs/tasks/GZ-014.md", h.PLAN, "evidence/GZ-014/handoff.md"):
        target = snapshot / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    monkeypatch.setattr(h, "__file__", str(scripts / "check-program-plan-history.py"))
    return h, snapshot, scripts


def _legacy_task_child(h, snapshot, scripts):
    return h.subprocess.run(
        [sys.executable, str(scripts / "check-task-file.py"), "--repo-root", str(snapshot), "--task", "GZ-014"],
        cwd=snapshot, capture_output=True, text=True, check=False,
    )


def test_known_task_validator_matches_cli_and_rechecks_invalid_plan(historical_task_cli, monkeypatch):
    h, snapshot, scripts = historical_task_cli
    script = str(scripts / "check-task-file.py")
    expected = _legacy_task_child(h, snapshot, scripts)
    assert expected.returncode == 0 and not expected.stderr
    assert h._known_task_file_output(script, str(snapshot), "GZ-014") == expected.stdout
    (snapshot / h.PLAN).write_text("foundationTasks: [\n", encoding="utf-8")
    rejected = _legacy_task_child(h, snapshot, scripts)
    assert rejected.returncode == 1 and "Program scope" in rejected.stdout
    assert h._known_task_file_output(script, str(snapshot), "GZ-014") is None
    monkeypatch.setattr(h, "_ordinary_task_file_context", lambda _: True)
    actual = h._run_historical_task_file(str(snapshot), "GZ-014")
    assert (actual.returncode, actual.stdout, actual.stderr) == (rejected.returncode, rejected.stdout, rejected.stderr)


def test_known_task_validator_declines_different_effective_planning_bytecode(historical_task_cli, monkeypatch):
    import os
    import py_compile

    h, snapshot, scripts = historical_task_cli
    planning = scripts / "program-planning-revision.py"
    original = planning.read_bytes()
    sibling = scripts / "different_planning.py"
    marker = b"raise RuntimeError('different loaded planning code')\n#"
    sibling.write_bytes(marker + b" " * (len(original) - len(marker)))
    stamp = planning.stat()
    os.utime(sibling, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
    bytecode = importlib.util.cache_from_source(str(planning))
    py_compile.compile(str(sibling), cfile=bytecode, dfile=str(planning), doraise=True)
    assert planning.read_bytes() == original
    expected = _legacy_task_child(h, snapshot, scripts)
    assert expected.returncode == 1 and "different loaded planning code" in expected.stdout
    assert h._known_task_file_output(str(scripts / "check-task-file.py"), str(snapshot), "GZ-014") is None
    monkeypatch.setattr(h, "_ordinary_task_file_context", lambda _: True)
    actual = h._run_historical_task_file(str(snapshot), "GZ-014")
    assert (actual.returncode, actual.stdout, actual.stderr) == (expected.returncode, expected.stdout, expected.stderr)


def test_known_task_validator_falls_back_for_changed_code_and_nondefault_context(historical_task_cli, monkeypatch):
    import shutil

    h, snapshot, scripts = historical_task_cli
    planning = scripts / "program-planning-revision.py"
    original = planning.read_bytes()
    planning.write_bytes(original + b"\n# a different source version\n")
    expected = _legacy_task_child(h, snapshot, scripts)
    assert expected.returncode == 0
    assert h._known_task_file_output(str(scripts / "check-task-file.py"), str(snapshot), "GZ-014") is None
    monkeypatch.setattr(h, "__name__", "__main__")
    monkeypatch.setattr(sys, "argv", [h.__file__])
    monkeypatch.setattr(sys, "path", [str(scripts), *sys.path[1:]])
    monkeypatch.setenv("PYTHONPATH", str(snapshot))
    def unexpected_fast_path(*_):
        pytest.fail("nondefault import context must use the original child")
    monkeypatch.setattr(h, "_known_task_file_output", unexpected_fast_path)
    actual = h._run_historical_task_file(str(snapshot), "GZ-014")
    assert (actual.returncode, actual.stdout, actual.stderr) == (expected.returncode, expected.stdout, expected.stderr)

    planning.write_bytes(original)
    unicode_snapshot = snapshot.with_name("snapshot-é")
    shutil.copytree(snapshot, unicode_snapshot)
    monkeypatch.delenv("PYTHONPATH")
    # An explicit child encoding may reject a successful report path. Keep
    # the real subprocess result rather than treating StringIO as equivalent.
    monkeypatch.setenv("PYTHONIOENCODING", "ascii:strict")
    rejected = _legacy_task_child(h, unicode_snapshot, scripts)
    assert rejected.returncode != 0 and "UnicodeEncodeError" in rejected.stderr
    actual = h._run_historical_task_file(str(unicode_snapshot), "GZ-014")
    assert (actual.returncode, actual.stdout, actual.stderr) == (rejected.returncode, rejected.stdout, rejected.stderr)
