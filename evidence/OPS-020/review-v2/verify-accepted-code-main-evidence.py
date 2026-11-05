from pathlib import Path,PurePosixPath
import hashlib,json,zipfile
p=Path(__file__).resolve().parent
i=json.loads((p/'accepted-code-main-evidence-index.json').read_bytes())
a=p/i['archive'];assert a.stat().st_size==i['archiveBytes'] and hashlib.sha256(a.read_bytes()).hexdigest()==i['archiveSha256']
with zipfile.ZipFile(a) as z:
    rows=i['entries'];assert len(rows)==len(z.namelist())==len(set(z.namelist()))
    assert set(z.namelist())=={r['path'] for r in rows}
    for r in rows:
        name=PurePosixPath(r['path']);assert not name.is_absolute() and '..' not in name.parts
        b=z.read(r['path']);assert len(b)==r['bytes'] and hashlib.sha256(b).hexdigest()==r['sha256']
print('Verified',len(rows),'retrievable evidence entries; no payload executed or extracted.')
