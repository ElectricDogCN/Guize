"""Derive directory fanout from the already qualified complete observed catalogue."""
import collections
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

t = Path(__file__).resolve().parent
r = t / 'poc005-feature-actor-import-v1'
read = lambda p: json.loads(p.read_text(encoding='utf-8'))
execution = read(r / 'evidence/POC-005/profiles/local-v1/v1/attempt-011/execution-candidate.json')
report = read(r / execution['environmentCaptured']['metadataProfilingRef'])
descriptor = report['filenameObjects']
source = r / descriptor['ref']
before = source.stat()
with source.open('rb') as stream:
    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
assert 'sha256:' + digest == descriptor['sha256']
children = collections.Counter()
directories = set()
count = files = 0
with gzip.open(source, 'rb') as stream:
    while True:
        raw = stream.readline(65537)
        if not raw:
            break
        assert len(raw) <= 65536
        row = json.loads(raw)
        path = row['path']
        parent = path.rpartition('/')[0]
        children[parent] += 1
        count += 1
        if row['kind'] == 'directory':
            directories.add(path)
        else:
            assert row['kind'] == 'file'
            files += 1
        assert len(children) <= 20000 and len(directories) <= 20000
after = source.stat()
assert count == descriptor['count'] == 1000500 and files == 1000000 and len(directories) == 500
assert (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
fanouts = {name: children[name] for name in sorted(directories)}
virtual = {name: children[name] for name in sorted(set(children) - directories)}
result = dict(kind='DERIVED_FROM_QUALIFIED_COMPLETE_OBSERVED_FILENAME_STREAM_NOT_NEW_EXPERIMENT',
              derivedAt=datetime.now(timezone.utc).isoformat(), sourceRuntime=execution['environmentCaptured']['testedSource'],
              input=descriptor, actualPhysicalBytes=before.st_size, actualPhysicalSha256='sha256:' + digest,
              actualRecords=count, fileRecords=files, directoryRecords=len(directories),
              fanoutDefinition='Count every observed file/directory whose exact parent path is this represented directory; zero-child directories are included. Root/virtual parent paths without a represented directory record are separate.',
              representedDirectoryFanoutHistogram={str(n): total for n, total in sorted(collections.Counter(fanouts.values()).items())},
              minimumRepresentedDirectoryFanout=min(fanouts.values()), maximumRepresentedDirectoryFanout=max(fanouts.values()),
              representedDirectoryChildCount=sum(fanouts.values()), rootOrVirtualParentChildCount=sum(virtual.values()),
              representedDirectoryFanouts=fanouts, rootOrVirtualParentChildCounts=virtual,
              sourceUnchanged=True, newExperimentExecuted=False, exitDecisionApproved=False)
assert result['representedDirectoryChildCount'] + result['rootOrVirtualParentChildCount'] == count
out = r / 'evidence/POC-005/qualified-local-1m-attempt011-v1/observed-directory-fanout.json'
with out.open('x', encoding='utf-8', newline='\n') as stream:
    stream.write(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k:result[k] for k in ('actualRecords','directoryRecords','representedDirectoryFanoutHistogram',
    'minimumRepresentedDirectoryFanout','maximumRepresentedDirectoryFanout','rootOrVirtualParentChildCount','sourceUnchanged')}))
