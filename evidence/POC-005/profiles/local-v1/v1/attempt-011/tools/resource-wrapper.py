"""One reviewed resource preparation; no source listing, probe or scanner."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, importlib.util, json, os, shutil, socket, subprocess, sys, time, yaml

t = Path(__file__).resolve().parent
w = t / 'poc005-attempt011-runtime-15dcd6c'
parser = argparse.ArgumentParser()
parser.add_argument('--review-sha256', required=True)
args = parser.parse_args()
assert os.name == 'nt' and len(args.review_sha256) == 64
review_path = t / 'poc005-attempt011-resource-preparation-independent-review.json'
review_raw = review_path.read_bytes()
assert hashlib.sha256(review_raw).hexdigest() == args.review_sha256
review = json.loads(review_raw)
assert review['decision'] == 'approved_resource_preparation_only' and review['mustFix'] == []
assert review['allowFixtureCreate'] is True and review['allowNewLoopbackServiceStart'] is True
assert review['allowedExecution'] == dict(count=1, fixtureMethodCount=1, openlistMethodCount=1,
                                         platform='Windows', preparationTimeoutSeconds=7200)

def checked(row):
    assert Path(row['file']).name == row['file']
    raw = (t / row['file']).read_bytes()
    assert len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256']
    return raw

assert review['wrapperMethod']['file'] == Path(__file__).name
checked(review['wrapperMethod'])
request_raw = checked(dict(file=review['requestRef'], bytes=review['requestBytes'], sha256=review['requestSha256']))
request = json.loads(request_raw)
assert request['wrapperMethod'] == review['wrapperMethod']
assert request['methods'] == review['methods'] and len(review['methods']) == 2
assert [row['file'] for row in review['methods']] == [
    'prepare_poc005_attempt011_windows_fixture_once.py', 'prepare_poc005_attempt011_windows_openlist_once.py']
for row in review['methods']:
    checked(row)
for key in ('source', 'base', 'tree', 'sourceReview', 'sourceReviewSha256', 'storageRoot',
            'servicePrivateRoot', 'inputRoot', 'port', 'executionClone', 'expectedFilesystemCounts',
            'expectedPayloadBytes', 'minimumFreeDiskBeforeBytes', 'minimumFreeMemoryBeforeBytes'):
    assert request[key] == review[key]
assert request['executionClone'] == w.name and request['port'] == 15535
assert request['preparationTimeoutSeconds'] == 7200
source_review = t / request['sourceReview']
assert source_review.name == 'poc005-profile-retirement-final-source-independent-review.json'
source_raw = source_review.read_bytes()
assert hashlib.sha256(source_raw).hexdigest() == request['sourceReviewSha256'] == '4bda4cbbdd3a611cc4f40c79b1da2b8fd85e5159eb81fabb6fb85193d1abb0b1'
accepted = json.loads(source_raw)
assert all(accepted[key] is True for key in ('fullSourceAccepted', 'latestSourceCiAccepted', 'unapprovedTemplatePreparationMayProceed'))
assert accepted['mustFix'] == []
for key in ('source', 'base', 'tree'):
    assert accepted[key] == review[key]
assert accepted['source'] == '15dcd6cd22a576821cdbe0f936002ad9a1be69e3'

def git(*argv):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    return subprocess.check_output(['git', '-c', 'core.longpaths=true', '-c', 'credential.interactive=never',
                                    '-C', str(w), *argv], timeout=45, env=env)

assert git('rev-parse', 'HEAD').decode().strip() == review['source']
assert git('rev-parse', 'HEAD^{tree}').decode().strip() == review['tree']
assert git('branch', '--show-current').decode().strip() == 'chore/POC-005-metadata-scale'
assert not git('status', '--porcelain', '--untracked-files=all')
assert git('ls-remote', '--heads', 'https://github.com/ElectricDogCN/Guize.git', 'refs/heads/main').decode().split() == [review['base'], 'refs/heads/main']
old_untracked = git('ls-files', '--others', '--exclude-standard', '-z')
assert not old_untracked
active=yaml.safe_load((w/'specs/coordination/active-work.yaml').read_bytes())
own=next(row for row in active['tasks'] if row['taskId']=='POC-005')
assert own['status']=='in_progress' and own['agentRole']=='implementer'
assert own['baseSha']=='746e23e582501fa08380c3f3301bdc1774902f7c'
assert own['implementer']=='/root' and own['reviewer']=='/root/gz022_planning_independent_review'
assert own['lease']=={'acquiredAt':'2026-10-22T16:08:44Z','expiresAt':'2026-10-29T16:08:44Z'}
assert review['reviewer']==own['reviewer']
assert request['parallelFileOperations']==review['parallelFileOperations']==4
assert request['maximumQueuedFileRows']==review['maximumQueuedFileRows']==32

# Use the unchanged frozen validator's canonical UTC rule, before any output write.
spec = importlib.util.spec_from_file_location('attempt011_frozen_checker', w / 'specs/poc/check_program.py')
checker = importlib.util.module_from_spec(spec)
sys.path.insert(0, str(w / 'specs/poc'))
spec.loader.exec_module(checker)
now = lambda: datetime.now(timezone.utc)
for key in ('approvedAt', 'validFrom', 'validUntil'):
    assert checker.valid_utc_timestamp(review[key])
valid_from = datetime.fromisoformat(review['validFrom'])
valid_until = datetime.fromisoformat(review['validUntil'])
assert datetime.fromisoformat(review['approvedAt']) == valid_from
assert valid_from <= now() and (valid_until - now()).total_seconds() >= 7200
assert valid_until < datetime(2026, 10, 29, 16, 8, 44, tzinfo=timezone.utc)

parent = Path.home() / '.codex/local-lab'
assert Path(request['storageRoot']).resolve() == (parent / 'poc005-native-windows-v8-1m-attempt011').resolve()
assert Path(request['servicePrivateRoot']).resolve() == (parent / 'poc005-windows-openlist-v8-1m-attempt011').resolve()
assert request['inputRoot'] == 'evidence/POC-005/profiles/local-v1/v1/inputs-1m-attempt011'
targets = [Path(request['storageRoot']), Path(request['servicePrivateRoot']),
           t / 'poc005-attempt011-windows-native-fixture-preparation.json',
           t / 'poc005-attempt011-windows-openlist-started.json',
           t / 'poc005-attempt011-windows-openlist-preparation.json', w / request['inputRoot']]
assert all(not path.exists() for path in targets)
assert request['minimumFreeDiskBeforeBytes'] == 20 * 1024**3
assert request['minimumFreeMemoryBeforeBytes'] == 4 * 1024**3
assert shutil.disk_usage(parent).free >= request['minimumFreeDiskBeforeBytes']
with socket.socket() as port_check:
    port_check.bind(('127.0.0.1', request['port']))
out = t / 'poc005-attempt011-resource-preparation-run'
out.mkdir()  # Exclusive once-only marker; failed attempts and partials are retained.
utc = lambda: now().isoformat().replace('+00:00', 'Z')
record = dict(source=review['source'], base=review['base'], sourceReview=source_review.name,
              preparationReviewSha256=args.review_sha256, requestSha256=review['requestSha256'],
              startedAt=utc(), wrapperPid=os.getpid(), commands=[], resourcePreparationAccepted=False,
              scannerStarted=False, listingOrProbeExecuted=False, experimentApproved=False, qualificationAccepted=False)

def save():
    (out / 'results.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf8', newline='\n')

deadline = time.monotonic() + 7200
save()
for number, row in enumerate(review['methods']):
    assert now() < valid_until and time.monotonic() < deadline
    checked(row)
    assert hashlib.sha256(source_review.read_bytes()).hexdigest() == request['sourceReviewSha256']
    assert git('rev-parse', 'HEAD').decode().strip() == review['source']
    assert not git('diff', '--name-only', 'HEAD')
    memory=subprocess.check_output(['powershell.exe','-NoProfile','-Command','[Console]::Write(([long](Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory)*1024)'],timeout=20,creationflags=subprocess.CREATE_NO_WINDOW)
    assert int(memory.strip())>=request['minimumFreeMemoryBeforeBytes']
    assert shutil.disk_usage(parent).free>=request['minimumFreeDiskBeforeBytes']
    if number == 0:
        assert not targets[0].exists()
    else:
        assert not targets[1].exists()
        with socket.socket() as port_check:
            port_check.bind(('127.0.0.1', request['port']))
    argv = [sys.executable, '-X', 'utf8', '-B', str(t / row['file']), '--source-review', str(source_review)]
    log = out / ('fixture.raw' if number == 0 else 'openlist.raw')
    command = dict(argv=argv, startedAt=utc(), methodSha256=row['sha256'])
    with log.open('xb') as stream:
        # Slow preflights must never turn an expired preparation budget into
        # a new child launch. The first launch still needs the full UTC window.
        launch_utc = now()
        launch_remaining = deadline - time.monotonic()
        assert launch_utc < valid_until and launch_remaining > 0
        if number == 0:
            assert (valid_until - launch_utc).total_seconds() >= 7200
        assert (valid_until - launch_utc).total_seconds() >= launch_remaining
        child = subprocess.Popen(argv, cwd=t, stdout=stream, stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        command['pid'] = child.pid
        record['commands'].append(command)
        save()
        try:
            code = child.wait(timeout=max(0.001, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            command['preparationBudgetExpired'] = True
            save()
            child.terminate()
            try:
                code = child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                code = child.wait(timeout=10)
    raw = log.read_bytes()
    command.update(exitCode=code, waitCompleted=True, actualWaitCompleted=True, completedAt=utc(), raw=log.name,
                   rawBytes=len(raw), rawSha256=hashlib.sha256(raw).hexdigest())
    save()
    print(('fixture' if number == 0 else 'new idle OpenList') + ': actual exit ' + str(code), flush=True)
    if code or command.get('preparationBudgetExpired'):
        record.update(preparationFailed=True, partialPreserved=True, completedAt=utc())
        save()
        raise SystemExit(1)
assert now() < valid_until and git('rev-parse', 'HEAD').decode().strip() == review['source']
assert not git('diff', '--name-only', 'HEAD')
new_inputs = {(Path(request['inputRoot']) / name).as_posix().encode() for name in [
    'baseline.jsonl.gz', 'profiled.jsonl.gz', 'expected-changes.jsonl', 'change-profiles.jsonl',
    'updated-probe.bin', 'created-probe.bin', 'baseline-probe.bin']}
assert set(filter(None, git('ls-files', '--others', '--exclude-standard', '-z').split(b'\0'))) == new_inputs
fixture = json.loads(targets[2].read_bytes())
service = json.loads(targets[4].read_bytes())
assert fixture['actualFilesystemCounts'] == request['expectedFilesystemCounts'] == {'file': 1000000, 'directory': 500}
assert fixture['actualPayloadBytes'] == request['expectedPayloadBytes'] == 1792000000
assert service['serviceUrl'] == 'http://127.0.0.1:15535' and service['readOnlyPermission'] == 256
assert service['gatewayMustEnforceFixtureScope'] is True
assert not service['sourceListingOrProbeExecuted'] and not fixture['scannerExperimentExecuted']
record.update(preparationMethodsCompleted=True, actualFixtureFiles=1000000, actualFixtureDirectories=500,
              actualPayloadBytes=1792000000, newIdleServiceIdentity=service['identity'],
              originalUntrackedRetained=True, onlySevenApprovedNewInputsCreated=True,
              specificPreparationReviewStillRequired=True, completedAt=utc())
save()
print(json.dumps(dict(preparationMethodsCompleted=True, scannerStarted=False,
                      listingOrProbeExecuted=False, experimentApproved=False)), flush=True)
