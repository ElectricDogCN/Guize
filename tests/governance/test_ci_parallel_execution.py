"""Exercise the configured full-suite command and its failure/reporting behavior."""
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import xml.etree.ElementTree as ET

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[2]
PARALLEL_OPTIONS = ['-n', '2', '--dist', 'loadfile', '--max-worker-restart=0']


def workflow_command():
    workflow = yaml.safe_load((ROOT / '.github/workflows/governance-gate.yml').read_text(encoding='utf-8'))
    job = workflow['jobs']['governance-check']
    step = next(item for item in job['steps'] if item.get('id') == 'governance-tests')
    lines = [line.strip() for line in step['run'].splitlines() if line.strip()]
    command = [line for line in lines if line.startswith('python -m pytest ')]
    assert len(command) == 1
    return workflow, job, step, shlex.split(command[0])


def test_workflow_preserves_full_selection_and_explicit_file_workers():
    workflow, job, step, command = workflow_command()
    assert command == [
        'python', '-m', 'pytest', 'tests/governance/', '-v', '-ra',
        '--junitxml=/tmp/test-results/governance-junit.xml',
        '-n', '2', '--dist', 'loadfile', '--max-worker-restart=0',
    ]
    assert step['run'].splitlines()[0].strip() == 'set -euo pipefail'
    install = next(item for item in job['steps'] if item.get('id') == 'install-deps')
    assert 'pip install -r requirements-governance.txt pytest-xdist==3.8.0' in install['run'].splitlines()
    for scope in (workflow, job, step):
        assert 'PYTEST_ADDOPTS' not in scope.get('env', {})
    assert 'PYTEST_ADDOPTS' not in step['run']
    assert job['runs-on'] == 'ubuntu-latest' and job['timeout-minutes'] == 30


def execution_mode(request):
    plugin_available = importlib.util.find_spec('xdist') is not None
    outer_worker = getattr(request.config, 'workerinput', None) is not None
    if os.environ.get('GITHUB_ACTIONS', '').lower() == 'true' or outer_worker:
        assert plugin_available, 'CI and outer workers require the declared xdist dependency'
    return 'parallel' if plugin_available else 'serial'


def write_suite(directory, outcome, mode):
    suite = directory / 'tests/governance'
    suite.mkdir(parents=True)
    (directory / 'observed').mkdir()
    nested = directory / 'nested'
    nested.mkdir()
    (nested / 'test_leaf.py').write_text(
        'def test_serial_child(request):\n'
        '    assert not hasattr(request.config, "workerinput")\n', encoding='utf-8')
    common = '''import json, os, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
def record(name, request):
    worker_input = getattr(request.config, 'workerinput', None)
    value = dict(mode='parallel' if worker_input is not None else 'serial',
                 worker=worker_input['workerid'] if worker_input is not None else 'serial',
                 pid=os.getpid(), file=Path(__file__).name)
    (ROOT / 'observed' / (name + '.json')).write_text(json.dumps(value), encoding='utf-8')
'''
    action = {
        'success': 'assert True',
        'assertion_failure': 'assert False, "intentional child assertion failure"',
        'process_crash': 'os._exit(91)',
    }[outcome]
    if outcome == 'process_crash' and mode == 'serial':
        action = "\n    ".join([
            "process = subprocess.Popen([sys.executable, '-c', 'import os; os._exit(91)'])",
            'code = process.wait()',
            "(ROOT / 'crash-receipt.json').write_text(json.dumps(dict(pid=process.pid, actual_wait=True, exit_code=code)), encoding='utf-8')",
            'assert code == 91',
            "assert code == 0, 'owned child crashed with exit 91'",
        ])
    first = common + f'''
def test_a_first(request):
    record('a_first', request)
    {action}
def test_a_second(request):
    record('a_second', request)
    child = subprocess.run([sys.executable, '-m', 'pytest', 'nested/test_leaf.py', '-q'], cwd=ROOT, capture_output=True, text=True)
    assert child.returncode == 0, child.stdout + child.stderr
'''
    second = common + '''
def test_b_first(request):
    record('b_first', request)
def test_b_second(request):
    record('b_second', request)
'''
    (suite / 'test_group_a.py').write_text(first, encoding='utf-8')
    (suite / 'test_group_b.py').write_text(second, encoding='utf-8')


@pytest.mark.parametrize('outcome', ['success', 'assertion_failure', 'process_crash'])
def test_pytest_execution_preserves_auditable_results(tmp_path, outcome, request):
    mode = execution_mode(request)
    write_suite(tmp_path, outcome, mode)
    _, _, _, command = workflow_command()
    assert command[-5:] == PARALLEL_OPTIONS
    # The supported local setup runs serial pytest without CI-only plugins.
    # Never retry a plugin/CLI failure with fewer options.
    if mode == 'serial':
        command = command[:-5]
    junit = tmp_path / 'governance-junit.xml'
    # Keep the selected execution options; isolate the fixture and its report.
    command[0] = sys.executable
    command = [f'--junitxml={junit}' if arg.startswith('--junitxml=') else arg for arg in command]
    result = subprocess.run(command, cwd=tmp_path, env=os.environ.copy(), capture_output=True, text=True, timeout=90)
    output = result.stdout + result.stderr
    assert junit.is_file(), output
    report = ET.parse(junit).getroot()
    cases = list(report.iter('testcase'))
    failures = list(report.iter('failure')) + list(report.iter('error'))
    assert not list(report.iter('skipped')), output
    records = {path.stem: json.loads(path.read_text(encoding='utf-8')) for path in (tmp_path / 'observed').glob('*.json')}
    assert records and {row['mode'] for row in records.values()} == {mode}, output
    if mode == 'serial' or outcome != 'process_crash':
        assert len(cases) == 4 and set(records) == {'a_first', 'a_second', 'b_first', 'b_second'}, output
        if mode == 'parallel':
            assert {row['worker'] for row in records.values()} == {'gw0', 'gw1'}, output
            assert len({row['pid'] for row in records.values()}) == 2
        else:
            assert {row['worker'] for row in records.values()} == {'serial'}, output
            assert len({row['pid'] for row in records.values()}) == 1
        for names in (('a_first', 'a_second'), ('b_first', 'b_second')):
            assert records[names[0]] == records[names[1]]
    if outcome == 'success':
        assert result.returncode == 0 and not failures, output
    else:
        assert result.returncode == 1 and failures, output
    if outcome == 'assertion_failure':
        assert len(failures) == 1 and 'intentional child assertion failure' in output
    if outcome == 'process_crash':
        assert 'crashed' in output.lower(), output
        if mode == 'parallel':
            assert 'restarting crashed worker' not in output.lower(), output
            assert not (tmp_path / 'crash-receipt.json').exists()
        else:
            assert len(failures) == 1
            crash = json.loads((tmp_path / 'crash-receipt.json').read_text(encoding='utf-8'))
            assert crash['actual_wait'] is True and crash['exit_code'] == 91
            assert crash['pid'] > 0 and crash['pid'] not in {row['pid'] for row in records.values()}
    audit = subprocess.run([
        sys.executable, str(ROOT / 'scripts/check-pytest-skips.py'), str(junit),
        str(ROOT / 'tests/governance/allowed-skips.txt'),
    ], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert audit.returncode == 0, audit.stdout + audit.stderr


def test_ci_plugin_unavailability_does_not_succeed_serially(tmp_path):
    import shutil

    fixture = tmp_path / 'strict-ci'
    relative = 'tests/governance/test_ci_parallel_execution.py'
    for name in (
        relative,
        '.github/workflows/governance-gate.yml',
        'scripts/check-pytest-skips.py',
        'tests/governance/allowed-skips.txt',
    ):
        target = fixture / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
        assert target.read_bytes() == (ROOT / name).read_bytes()

    environment = os.environ.copy()
    environment.update(GITHUB_ACTIONS='true', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1')
    environment.pop('PYTEST_ADDOPTS', None)
    environment.pop('PYTEST_PLUGINS', None)
    report = fixture / 'strict-ci-junit.xml'
    result = subprocess.run([
        sys.executable, '-m', 'pytest', relative, '-q',
        '-k', 'test_pytest_execution_preserves_auditable_results',
        '--junitxml=' + str(report), '-p', 'no:cacheprovider',
    ], cwd=fixture, env=environment, capture_output=True, text=True, timeout=90)
    output = result.stdout + result.stderr
    assert result.returncode == 1 and report.is_file(), output
    root = ET.parse(report).getroot()
    cases = list(root.iter('testcase'))
    assert len(cases) == 3 and {case.get('name') for case in cases} == {
        'test_pytest_execution_preserves_auditable_results[' + outcome + ']'
        for outcome in ('success', 'assertion_failure', 'process_crash')
    }, output
    assert len(list(root.iter('failure'))) == 3, output
    assert not list(root.iter('error')) and not list(root.iter('skipped')), output
    if importlib.util.find_spec('xdist') is None:
        assert 'CI and outer workers require the declared xdist dependency' in output
    else:
        assert 'unrecognized arguments:' in output, output
        for option in ('-n 2', '--dist loadfile', '--max-worker-restart=0'):
            assert option in output, output
