"""A separate Windows-only synthetic source; no listing/probe/scan experiment."""
import argparse,hashlib,json,os,secrets,shutil,socket,sqlite3,subprocess,sys,time,urllib.request,zipfile
from datetime import datetime,timezone
from pathlib import Path

t=Path(__file__).resolve().parent;workspace=t.parent
w=t/'poc005-attempt011-runtime-15dcd6c'
parser=argparse.ArgumentParser(description='Prepare only a new isolated attempt011 Windows OpenList after complete fixed-source acceptance; never approve an experiment.')
parser.add_argument('--source-review',type=Path,required=True)
args=parser.parse_args()
if os.name!='nt': raise SystemExit('Windows-only method; preparation not started')
review_path=args.source_review.resolve(strict=True)
if review_path.parent!=t.resolve(): raise ValueError('Use the exact independently issued public source review in this task tools directory')
review_raw=review_path.read_bytes()
assert hashlib.sha256(review_raw).hexdigest()=='4bda4cbbdd3a611cc4f40c79b1da2b8fd85e5159eb81fabb6fb85193d1abb0b1'
review=json.loads(review_raw)
accepted_source_commit=review.get('source')
assert accepted_source_commit=='15dcd6cd22a576821cdbe0f936002ad9a1be69e3'
if not (isinstance(accepted_source_commit,str) and len(accepted_source_commit)==40
        and review.get('fullSourceAccepted') is True and review.get('latestSourceCiAccepted') is True
        and review.get('unapprovedTemplatePreparationMayProceed') is True and review.get('mustFix')==[]):
    raise ValueError('Full fixed-source acceptance and explicit unapproved-template preparation review required; resource preparation not started')
assert subprocess.check_output(['git','-c','core.longpaths=true','-C',str(w),'rev-parse','HEAD'],text=True).strip()==accepted_source_commit
assert not subprocess.check_output(['git','-c','core.longpaths=true','-C',str(w),'status','--porcelain','--','poc/POC-05-metadata-scale','specs/tasks/POC-005.md'],text=True)
code=w/'poc/POC-05-metadata-scale'
sys.path.insert(0,str(code))
from native_scan_protocol import read_json,write_json
from windows_native import identity,owner_sid,PTR
from windows_source_files import read_private
from openlist_source import _NoRedirect
fixture=json.loads((t/'poc005-attempt011-windows-native-fixture-preparation.json').read_bytes())
assert fixture['actualFilesystemCounts']=={'file':1000000,'directory':500} and fixture['allPayloadsReread']
assert fixture['source']==accepted_source_commit and fixture['allMtimesReread'] and fixture['exactFullPathInventoryRevalidated']
assert Path(fixture['storageRoot']).resolve()==(Path.home()/'.codex/local-lab/poc005-native-windows-v8-1m-attempt011').resolve()
assert Path(fixture['filesystemRoot']).resolve()==(Path(fixture['storageRoot'])/'fixture').resolve()
lab=workspace/'local-lab/openlist'
archive=lab/'openlist-windows-amd64.zip'
assert archive.stat().st_size==50246230 and hashlib.sha256(archive.read_bytes()).hexdigest()=='10d24913f86843e347eefac219c61224628bbd5d3c7443b2ee119c168a8cb3b9'
with zipfile.ZipFile(archive) as package:
    members=[name for name in package.namelist() if name.endswith('openlist.exe')]
    assert len(members)==1
    expected_executable=hashlib.sha256(package.read(members[0])).hexdigest()
assert hashlib.sha256((lab/'bin/openlist.exe').read_bytes()).hexdigest()==expected_executable
private=Path.home()/'.codex/local-lab/poc005-windows-openlist-v8-1m-attempt011'
public=t/'poc005-attempt011-windows-openlist-preparation.json'
assert not private.exists() and not public.exists()
port=15535;base='http://127.0.0.1:'+str(port)
with socket.socket() as check: check.bind(('127.0.0.1',port))
private.mkdir()
sid=owner_sid(PTR(-1))
restricted=subprocess.run(['icacls.exe',str(private),'/inheritance:r','/grant:r','*'+sid+':(OI)(CI)F'],
    capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
assert restricted.returncode==0,'Private ACL setup failed; no credentials created'
binary=private/'openlist.exe';shutil.copyfile(lab/'bin/openlist.exe',binary)
assert hashlib.sha256(binary.read_bytes()).hexdigest()==expected_executable
credentials=dict(username='admin',password='guize_'+secrets.token_urlsafe(36))
write_json(private/'credentials.json',credentials)
assert json.loads(read_private(private/'credentials.json'))==credentials
data=private/'data';data.mkdir()
setup=subprocess.run([str(binary),'admin','set',credentials['password'],'--data',str(data)],
    capture_output=True,timeout=40,creationflags=subprocess.CREATE_NO_WINDOW)
(private/'bootstrap.stdout').write_bytes(setup.stdout);(private/'bootstrap.stderr').write_bytes(setup.stderr)
assert setup.returncode==0,'Private bootstrap failed; retain credential-bearing logs privately'
config_ref=data/'config.json';config=json.loads(config_ref.read_bytes())
config.update(force=True,site_url=base,tls_insecure_skip_verify=False)
config['scheme'].update(address='127.0.0.1',http_port=port,https_port=-1,force_https=False)
for key in ('s3','ftp','sftp','mcp'):
    if key in config: config[key]['enable']=False
config['log']['enable']=False
config['database']['db_file']=str(data/'data.db');config['temp_dir']=str(data/'temp');config['bleve_dir']=str(data/'bleve')
config['cors']={'allow_origins':[base],'allow_methods':['GET','POST','HEAD','OPTIONS'],'allow_headers':['Authorization','Content-Type']}
config_ref.write_text(json.dumps(config,indent=2)+'\n',encoding='utf8',newline='\n')
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),_NoRedirect())
with (private/'server.stdout').open('xb') as stdout,(private/'server.stderr').open('xb') as stderr:
    process=subprocess.Popen([str(binary),'server','--data',str(data)],cwd=private,stdin=subprocess.DEVNULL,
        stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    process_identity=identity(process.pid)
    write_json(t/'poc005-attempt011-windows-openlist-started.json',dict(identity=process_identity,base=base,privateRoot=str(private),
        state='service created; configuration not yet accepted',experimentApproved=False))
    for _ in range(60):
        assert process.poll() is None,'Private service exited; inspect private logs without printing secrets'
        try:
            with opener.open(base+'/ping',timeout=2) as response: assert response.status==200 and response.read(64).strip()==b'pong'
            break
        except (OSError,AssertionError): time.sleep(.2)
    else: raise RuntimeError('Private service readiness deadline')
def api(path,payload=None,token=None):
    assert path.startswith('/api/')
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']=token
    body=json.dumps(payload).encode() if payload is not None else None
    with opener.open(urllib.request.Request(base+path,data=body,headers=headers),timeout=5) as response: raw=response.read(2*1024*1024+1)
    assert len(raw)<=2*1024*1024
    value=json.loads(raw);assert value['code']==200,'Private sandbox configuration failed; response deliberately not printed'
    return value.get('data')
token=api('/api/auth/login',credentials)['token']
setting=api('/api/admin/setting/get?key=sign_all',token=token)
assert setting['key']=='sign_all'
api('/api/admin/setting/save',[{**setting,'value':'false'}],token)
users=api('/api/admin/user/list',token=token)['content']
guest=next(row for row in users if row['username']=='guest')
if not guest['disabled']: api('/api/admin/user/update',{**guest,'disabled':True},token)
assert api('/api/admin/storage/list',token=token)['content']==[]
mount='/poc005-windows-v8-1m-attempt011'
addition=dict(root_folder_path=fixture['storageRoot'],thumbnail=False,show_hidden=True,directory_size=False,
    recycle_bin_path=str(private/'unused-recycle-bin'))
api('/api/admin/storage/create',dict(mount_path=mount,driver='Local',order=0,cache_expiration=0,webdav_policy='native_proxy',
    addition=json.dumps(addition),enable_sign=False,disabled=False,remark='Dedicated non-sensitive synthetic POC005 Windows fixture'),token)
reader=dict(username='guize-poc005-windows-read-v8-attempt011',password=secrets.token_urlsafe(36))
reader_ref=private/'reader-credentials.json';write_json(reader_ref,reader)
assert json.loads(read_private(reader_ref))==reader
api('/api/admin/user/create',{**reader,'base_path':mount,'role':0,'permission':256,'disabled':False},token)
storage=api('/api/admin/storage/list',token=token)['content'];assert len(storage)==1
actual_reader=next(row for row in api('/api/admin/user/list',token=token)['content'] if row['username']==reader['username'])
assert actual_reader['base_path']==mount and actual_reader['role']==0 and actual_reader['permission']==256 and not actual_reader['disabled']
assert next(row for row in api('/api/admin/user/list',token=token)['content'] if row['username']=='guest')['disabled']
assert api('/api/admin/setting/get?key=sign_all',token=token)['value']=='false'
assert storage[0]['enable_sign'] is False and storage[0]['cache_expiration']==0
connection=sqlite3.connect('file:'+str(data/'data.db')+'?mode=ro',uri=True)
try: assert connection.execute('SELECT count(*) FROM x_meta').fetchone()[0]==0
finally: connection.close()
assert identity(process.pid)==process_identity
record=dict(kind='isolated_windows_openlist_preparation_only',source=accepted_source_commit,sourceReviewSha256=hashlib.sha256(review_raw).hexdigest(),preparedAt=datetime.now(timezone.utc).isoformat(),
    preparationProcessId=os.getpid(),serviceUrl=base,identity=process_identity,version='v4.2.6',
    archiveSha256=hashlib.sha256(archive.read_bytes()).hexdigest(),privateDataRoot=str(private),
    readerCredentialRef=str(reader_ref),readerUsername=reader['username'],credentialAclActuallyVerified=True,
    mountPath=mount,mountId='openlist-v426-local-v8-1m-attempt011-id'+str(storage[0]['id']),storageRoot=fixture['storageRoot'],filesystemRoot=fixture['filesystemRoot'],readerRelativeScope='fixture',readerBasePath=mount,gatewayMustEnforceFixtureScope=True,
    signAll=False,mountEnableSign=False,guestDisabled=True,readOnlyPermission=256,
    thumbnail=False,showHidden=True,cacheExpiration=0,onlyNewServiceConfigured=True,
    existingWindowsAndLinuxServicesNotRequested=True,sourceListingOrProbeExecuted=False,
    experimentApproved=False,qualificationAccepted=False)
write_json(public,record);print(json.dumps(record))
