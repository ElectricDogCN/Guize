"""Exercise the configured full-suite command and its failure/reporting behavior."""
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


def write_suite(directory, outcome):
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
def record(name):
    value = dict(worker=os.environ['PYTEST_XDIST_WORKER'], pid=os.getpid(), file=Path(__file__).name)
    (ROOT / 'observed' / (name + '.json')).write_text(json.dumps(value), encoding='utf-8')
'''
    action = {
        'success': 'assert True',
        'assertion_failure': 'assert False, "intentional child assertion failure"',
        'worker_crash': 'os._exit(91)',
    }[outcome]
    first = common + f'''
def test_a_first():
    record('a_first')
    {action}
def test_a_second():
    record('a_second')
    child = subprocess.run([sys.executable, '-m', 'pytest', 'nested/test_leaf.py', '-q'], cwd=ROOT, capture_output=True, text=True)
    assert child.returncode == 0, child.stdout + child.stderr
'''
    second = common + '''
def test_b_first():
    record('b_first')
def test_b_second():
    record('b_second')
'''
    (suite / 'test_group_a.py').write_text(first, encoding='utf-8')
    (suite / 'test_group_b.py').write_text(second, encoding='utf-8')


@pytest.mark.parametrize('outcome', ['success', 'assertion_failure', 'worker_crash'])
def test_configured_workers_propagate_results_and_preserve_auditable_junit(tmp_path, outcome):
    write_suite(tmp_path, outcome)
    _, _, _, command = workflow_command()
    junit = tmp_path / 'governance-junit.xml'
    # Keep the actual CI options; isolate this bounded fixture and its report.
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
    if outcome != 'worker_crash':
        assert len(cases) == 4 and set(records) == {'a_first', 'a_second', 'b_first', 'b_second'}, output
        assert {row['worker'] for row in records.values()} == {'gw0', 'gw1'}, output
        assert len({row['pid'] for row in records.values()}) == 2
        for names in (('a_first', 'a_second'), ('b_first', 'b_second')):
            assert records[names[0]] == records[names[1]]
    if outcome == 'success':
        assert result.returncode == 0 and not failures, output
    else:
        assert result.returncode == 1 and failures, output
    if outcome == 'assertion_failure':
        assert len(failures) == 1 and 'intentional child assertion failure' in output
    if outcome == 'worker_crash':
        assert 'crashed' in output.lower(), output
        assert 'restarting crashed worker' not in output.lower(), output
    audit = subprocess.run([
        sys.executable, str(ROOT / 'scripts/check-pytest-skips.py'), str(junit),
        str(ROOT / 'tests/governance/allowed-skips.txt'),
    ], cwd=tmp_path, capture_output=True, text=True, timeout=30)
    assert audit.returncode == 0, audit.stdout + audit.stderr
