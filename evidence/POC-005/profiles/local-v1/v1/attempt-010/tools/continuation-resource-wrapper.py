"""Reviewed interruption completion; no source listing, probe or scanner."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, importlib.util, json, os, shutil, socket, subprocess, sys, time

t = Path(__file__).resolve().parent
w = t / 'poc005-attempt010-runtime-ed8fbf3'
parser = argparse.ArgumentParser()
parser.add_argument('--review-sha256', required=True)
args = parser.parse_args()
assert os.name == 'nt' and len(args.review_sha256) == 64
review_path = t / 'poc005-attempt010-continuation-v1-independent-review.json'
review_raw = review_path.read_bytes()
assert hashlib.sha256(review_raw).hexdigest() == args.review_sha256
review = json.loads(review_raw)
assert review['decision'] == 'approved_interrupted_resource_completion_only' and review['mustFix'] == []
assert review['allowCompleteMissingFixtureFiles'] is True and review['allowNewLoopbackServiceStart'] is True
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
    'complete_poc005_attempt010_interrupted_fixture_v1_once.py', 'prepare_poc005_attempt010_windows_openlist_once.py']
for row in review['methods']:
    checked(row)
for key in ('source', 'base', 'tree', 'sourceReview', 'sourceReviewSha256', 'storageRoot',
            'servicePrivateRoot', 'inputRoot', 'port', 'executionClone', 'expectedFilesystemCounts',
            'expectedPayloadBytes', 'minimumFreeDiskBeforeBytes', 'minimumFreeMemoryBeforeBytes'):
    assert request[key] == review[key]
assert request['executionClone'] == w.name and request['port'] == 15534
assert request['preparationTimeoutSeconds'] == 7200
source_review = t / request['sourceReview']
assert source_review.name == 'poc005-compressed-output-ed8fbf3-final-source-independent-review.json'
source_raw = source_review.read_bytes()
assert hashlib.sha256(source_raw).hexdigest() == request['sourceReviewSha256'] == 'd0949b495b92d3e9715553ce1ac2154a34203eb7780273827d695407bac99648'
accepted = json.loads(source_raw)
assert all(accepted[key] is True for key in ('fullSourceAccepted', 'latestSourceCiAccepted', 'unapprovedTemplatePreparationMayProceed'))
assert accepted['mustFix'] == []
for key in ('source', 'base', 'tree'):
    assert accepted[key] == review[key]
assert accepted['source'] == 'ed8fbf32783c2600f75de7a69ef56c6f33b4824b'

def git(*argv):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    return subprocess.check_output(['git', '-c', 'core.longpaths=true', '-c', 'credential.interactive=never',
                                    '-C', str(w), *argv], timeout=45, env=env)

assert git('rev-parse', 'HEAD').decode().strip() == review['source']
assert git('rev-parse', 'HEAD^{tree}').decode().strip() == review['tree']
assert git('branch', '--show-current').decode().strip() == 'chore/POC-005-metadata-scale'
assert not git('diff', '--name-only', 'HEAD')
assert git('ls-remote', '--heads', 'https://github.com/ElectricDogCN/Guize.git', 'refs/heads/main').decode().split() == [review['base'], 'refs/heads/main']
old_untracked = git('ls-files', '--others', '--exclude-standard', '-z')
input_names={'baseline.jsonl.gz','profiled.jsonl.gz','expected-changes.jsonl','change-profiles.jsonl','updated-probe.bin','created-probe.bin','baseline-probe.bin'}
assert set(filter(None,old_untracked.decode().split('\0')))=={request['inputRoot']+'/'+name for name in input_names}
# Use the unchanged frozen validator's canonical UTC rule, before any output write.
spec = importlib.util.spec_from_file_location('attempt010_frozen_checker', w / 'specs/poc/check_program.py')
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
assert Path(request['storageRoot']).resolve() == (parent / 'poc005-native-windows-v7-1m').resolve()
assert Path(request['servicePrivateRoot']).resolve() == (parent / 'poc005-windows-openlist-v7-1m').resolve()
assert request['inputRoot'] == 'evidence/POC-005/profiles/local-v1/v1/inputs-1m-attempt010'
targets = [Path(request['storageRoot']), Path(request['servicePrivateRoot']),
           t / 'poc005-attempt010-windows-native-fixture-preparation.json',
           t / 'poc005-attempt010-windows-openlist-started.json',
           t / 'poc005-attempt010-windows-openlist-preparation.json', w / request['inputRoot']]
assert targets[0].is_dir() and targets[5].is_dir()
assert all(not path.exists() for path in targets[1:5])
assert not (targets[0]/'preparation.json').exists()
assert not (targets[0]/'payloads-continuation-v1.jsonl.gz').exists()
assert not (targets[0]/'continuation-v1-directory-mtimes-before.json').exists()
audit_ref='poc005-attempt010-interrupted-names-audit-20261027/results.json'
assert review['partialAuditRef']==request['partialAuditRef']==audit_ref
audit_raw=(t/audit_ref).read_bytes()
assert len(audit_raw)==review['partialAuditBytes']==request['partialAuditBytes']
assert hashlib.sha256(audit_raw).hexdigest()==review['partialAuditSha256']==request['partialAuditSha256']
audit=json.loads(audit_raw)
assert audit['actualExistingFileNames']==667845 and audit['actualExistingDirectoryNames']==500
with Path(audit['oldPayloadJournal']['ref']).open('rb') as stream:
    assert hashlib.file_digest(stream,'sha256').hexdigest()==audit['oldPayloadJournal']['sha256']
assert request['minimumFreeDiskBeforeBytes'] == 20 * 1024**3
assert request['minimumFreeMemoryBeforeBytes'] == 4 * 1024**3
assert shutil.disk_usage(parent).free >= request['minimumFreeDiskBeforeBytes']
with socket.socket() as port_check:
    port_check.bind(('127.0.0.1', request['port']))
out = t / 'poc005-attempt010-resource-completion-v1-run'
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
    if number == 0:
        assert targets[0].is_dir() and not (targets[0]/'payloads-continuation-v1.jsonl.gz').exists()
    else:
        assert not targets[1].exists()
        with socket.socket() as port_check:
            port_check.bind(('127.0.0.1', request['port']))
    argv = [sys.executable, '-X', 'utf8', '-B', str(t / row['file']), '--source-review', str(source_review)]
    log = out / ('fixture.raw' if number == 0 else 'openlist.raw')
    command = dict(argv=argv, startedAt=utc(), methodSha256=row['sha256'])
    with log.open('xb') as stream:
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
    command.update(exitCode=code, waitCompleted=True, completedAt=utc(), raw=log.name,
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
assert set(filter(None, git('ls-files', '--others', '--exclude-standard', '-z').split(b'\0'))) == new_inputs == set(filter(None,old_untracked.split(b'\0')))
fixture = json.loads(targets[2].read_bytes())
service = json.loads(targets[4].read_bytes())
assert fixture['actualFilesystemCounts'] == request['expectedFilesystemCounts'] == {'file': 1000000, 'directory': 500}
assert fixture['actualPayloadBytes'] == request['expectedPayloadBytes'] == 1792000000
assert service['serviceUrl'] == 'http://127.0.0.1:15534' and service['readOnlyPermission'] == 256
assert service['gatewayMustEnforceFixtureScope'] is True
assert not service['sourceListingOrProbeExecuted'] and not fixture['scannerExperimentExecuted']
record.update(preparationMethodsCompleted=True, actualFixtureFiles=1000000, actualFixtureDirectories=500,
              actualPayloadBytes=1792000000, newIdleServiceIdentity=service['identity'],
              originalUntrackedRetained=True, originalSevenInputsUnchanged=True, originalInterruptedRunNotRewritten=True,
              specificPreparationReviewStillRequired=True, completedAt=utc())
save()
print(json.dumps(dict(preparationMethodsCompleted=True, scannerStarted=False,
                      listingOrProbeExecuted=False, experimentApproved=False)), flush=True)
