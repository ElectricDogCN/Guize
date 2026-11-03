"""Verify the retrievable small evidence archive without extracting or executing it."""
from pathlib import Path,PurePosixPath
import hashlib,json,zipfile
root=Path(__file__).resolve().parent
index=json.loads((root/'accepted-code-main-evidence-index.json').read_bytes())
archive=root/index['archive'];raw=archive.read_bytes()
assert len(raw)==index['archiveBytes'] and hashlib.sha256(raw).hexdigest()==index['archiveSha256']
with zipfile.ZipFile(archive) as z:
 rows=index['entries'];assert len(rows)==len(z.namelist())==len(set(z.namelist()))
 assert set(z.namelist())=={x['path'] for x in rows}
 for row in rows:
  name=PurePosixPath(row['path']);assert not name.is_absolute() and '..' not in name.parts
  data=z.read(row['path']);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
print('Verified',len(rows),'retrievable evidence entries; no payload executed or extracted.')
