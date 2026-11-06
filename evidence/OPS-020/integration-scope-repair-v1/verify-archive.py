from pathlib import Path,PurePosixPath
import hashlib,json,zipfile
p=Path(__file__).resolve().parent;i=json.loads((p/'index.json').read_bytes());a=p/i['archive']
assert a.stat().st_size==i['archiveBytes'] and hashlib.sha256(a.read_bytes()).hexdigest()==i['archiveSha256']
with zipfile.ZipFile(a) as z:
 rows=i['entries'];assert len(rows)==len(z.namelist())==len(set(z.namelist())) and set(z.namelist())=={r['path'] for r in rows}
 for row in rows:
  name=PurePosixPath(row['path']);assert not name.is_absolute() and '..' not in name.parts
  data=z.read(row['path']);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
print('Verified',len(rows),'members without extracting or executing archive payloads.')
