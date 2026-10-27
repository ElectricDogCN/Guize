"""Validate the separate metadata activation before touching either source path."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from live_github_transport import start_bridge

t = Path(__file__).resolve().parent
c = json.loads((t / 'ops014-frozen-416-activation-v2-current-candidate.json').read_bytes())
source, base, branch = (c[k] for k in ('source', 'base', 'branch'))
assert os.geteuid() == 1000 and c['metadataActivationCommitted'] and not c['codeWritten']
bundle = t / c['bundle']
assert hashlib.sha256(bundle.read_bytes()).hexdigest() == c['bundleSha256']
w = Path('/home/sur/.cache/guize-takeover/ops014-activation-v2-' + source[:7])
assert not w.exists()
subprocess.run(['git', 'clone', '--quiet', '--branch', branch, str(bundle), str(w)], check=True)
assert not (w / '.git/objects/info/alternates').exists()
subprocess.run(['git', '-C', str(w), 'branch', 'main', 'origin/main'], check=True, capture_output=True)
subprocess.run(['git', '-C', str(w), 'remote', 'set-url', 'origin', 'https://github.com/ElectricDogCN/Guize.git'], check=True)
git = lambda *a: subprocess.check_output(['git', '-C', str(w), *a], text=True).strip()
def state():
    return dict(source=git('rev-parse', 'HEAD'), tree=git('rev-parse', 'HEAD^{tree}'), parent=git('show', '-s', '--format=%P', 'HEAD'), branch=git('branch', '--show-current'), main=git('rev-parse', 'main'), status=git('status', '--porcelain=v1', '--untracked-files=all'))
before = state()
assert before == dict(source=source, tree=c['tree'], parent=base, branch=branch, main=base, status='')
assert git('diff', '--name-only', base, source, '--').splitlines() == c['changedPaths']
for item in c['originalContractBlobs']:
    raw = (w / item['path']).read_bytes()
    assert len(raw) == item['bytes'] and hashlib.sha256(raw).hexdigest() == item['gitBlobSha256']
blocks = re.findall(r'```bash\n(.*?)\n```', (w / 'specs/tasks/OPS-014.md').read_text(), re.S)
assert len(blocks) == 2 and len(blocks[0].splitlines()) == 18 and len(blocks[1].splitlines()) == 15
commands = [shlex.split(line) for line in blocks[1].splitlines() if line != 'python specs/poc/check_program.py --repo-root .']
assert len(commands) == 14 and all('pytest' not in a and a[:2] != ['make', 'verify'] for a in commands)
commands = [[token.replace('HEAD', source) for token in argv] for argv in commands]
out = t / ('ops014-activation-v2-' + source[:7] + '-native-admission')
out.mkdir()
os.environ.update(PATH=str(Path(sys.executable).parent) + ':' + os.environ['PATH'], PYTHONDONTWRITEBYTECODE='1', GITHUB_REPOSITORY='ElectricDogCN/Guize', GITHUB_HEAD_REF=branch)
start_bridge(out)
utc = lambda: datetime.now(timezone.utc).isoformat()
result = dict(source=source, base=base, tree=c['tree'], branch=branch, before=before, startedAt=utc(), commands=[], metadataAdmissionAccepted=False, codeWritten=False)
def save():
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
save()
labels = ['diff', 'task', 'schemas', 'integrity', 'history', 'transitions', 'finalization', 'raw-lifecycle', 'lifecycle', 'coordination', 'scope', 'evidence', 'readiness', 'docs']
for label, argv in zip(labels, commands):
    row = dict(label=label, argv=argv, startedAt=utc(), raw=label + '.raw')
    with (out / row['raw']).open('x', encoding='utf-8', buffering=1) as stream:
        stream.write('Source Commit: ' + source + '\nCommand: ' + shlex.join(argv) + '\n')
        proc = subprocess.Popen(argv, cwd=w, stdout=stream, stderr=subprocess.STDOUT)
        row['pid'] = proc.pid
        result['commands'].append(row)
        save()
        code = proc.wait()
        stream.write('\nExit Code: ' + str(code) + '\n')
    raw = (out / row['raw']).read_bytes()
    row.update(exitCode=code, waitCompleted=True, endedAt=utc(), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    save()
    print(label + ': exit ' + str(code), flush=True)
    if code:
        result.update(failedGate=label, after=state())
        save()
        raise SystemExit(code)
assert state() == before
result.update(metadataAdmissionAccepted=True, codeMayBeImplementedOnlyWithinOriginalTwoPaths=True, after=state(), sourceUnchanged=True, completedAt=utc())
save()
print(json.dumps(dict(source=source, metadataAdmissionAccepted=True, commandsPassed=14, codeWritten=False)), flush=True)
