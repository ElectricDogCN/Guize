"""Correct only PR111 main coordination's Actual PR branch argument; retain original five results."""
import hashlib, json, os, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/".takeover-tools"
PRIMARY=ROOT/"Guize"
NATIVE=Path("/home/sur/.cache/guize-takeover/eight-follow-up-265001d")
PYTHON="/home/sur/.cache/guize-takeover/governance-venv/bin/python"
M="9de3656325bc9b8053f99489c64db1ccbb4c5d79"
S="1c077f7eefe76c1452f9362229730ee2ccf19404"
T="16c5ccbde7e4af8972afc45dc53203d45546cf65"
B="39afaf007d800bab43d7703ac082df2bbc7e8e87"
BRANCH="chore/OPS-011-agent-edge-104-scope"
PRIOR=TOOLS/"ops011-implementation-9de3656-main-results"
OUT=TOOLS/"ops011-implementation-9de3656-main-coordination-correction"
sha=lambda b:hashlib.sha256(b).hexdigest()
utc=lambda:datetime.now(timezone.utc).isoformat()
def require(ok,message):
    if not ok: raise RuntimeError(message)
def save(name,value):
    with (OUT/name).open("x",encoding="utf-8",newline="\n") as f:
        json.dump(value,f,ensure_ascii=False,indent=2); f.write("\n"); f.flush(); os.fsync(f.fileno())
def git(repo,*args):
    prefix=["/mnt/c/Program Files/Git/cmd/git.exe","-C",str(repo).replace("/mnt/c/","C:/")] if repo==PRIMARY else ["git","-C",str(repo)]
    return subprocess.check_output([*prefix,"-c","core.fsmonitor=false","-c","core.untrackedCache=false",*args],env={**os.environ,"GIT_OPTIONAL_LOCKS":"0"}).decode("utf-8").strip()
def snapshot(reference):
    result={}
    for name,repo in (("primary",PRIMARY),("native",NATIVE)):
        remote=git(repo,"remote","get-url","origin")
        row=dict(path=str(repo),source=git(repo,"rev-parse","HEAD"),tree=git(repo,"rev-parse","HEAD^{tree}"),
            parents=git(repo,"show","-s","--format=%P","HEAD").split(),branch=git(repo,"branch","--show-current"),
            main=git(repo,"rev-parse","refs/heads/main"),trackingMain=git(repo,"rev-parse","refs/remotes/origin/main"),
            origin=remote,pushOrigin=git(repo,"remote","get-url","--push","origin"),
            liveOriginMain=git(repo,"ls-remote","--heads","origin","refs/heads/main"),files={},
            status=git(repo,"status","--porcelain=v1","--untracked-files=all"))
        require((row["source"],row["tree"],row["parents"],row["branch"],row["main"],row["status"])==(M,T,[B,S],"main",M,""),"Actual clean main identity changed: "+name)
        for path,expected in reference[name]["files"].items():
            raw=(repo/path).read_bytes()
            row["files"][path]=dict(sha256=sha(raw),canonicalLfSha256=sha(raw.replace(b"\r\n",b"\n")),byteCount=len(raw))
            require(row["files"][path]==expected,"A previously verified main file changed: "+name+"/"+path)
        result[name]=row
    require(result==reference,"Same-main snapshot differs from original six's unchanged terminal")
    return result
def main():
    require(sys.platform.startswith("linux") and sys.executable==PYTHON,"Use the existing native governance Python")
    require(not OUT.exists(),"Correction output already exists; do not rerun")
    raw=(PRIOR/"failed-gate-worktrees.json").read_bytes()
    require(sha(raw)=="560a8d33f03a91c6cfdba1a3a084722b27387fe05f026f473354fccc284370fe","Original failed-six proof differs")
    prior=json.loads(raw)
    require((prior["actualMain"],prior["tree"],prior["failedGate"],prior["exitCode"],prior["requiredMainSixPassed"])==(M,T,"coordination",1,False),"Unexpected original failure")
    require(prior["before"]==prior["after"],"Original six changed a main checkout")
    execraw=(PRIOR/"command-executions.json").read_bytes()
    require(sha(execraw)=="f91d931bad2f760a07b5ef1d0050c710bfd67d153a0894973aceeb2fc5a91f46","Original command executions differ")
    executions=json.loads(execraw)
    require([r["label"] for r in executions]==["identity","integrity","history","transitions","raw-lifecycle","coordination"],"Original six labels differ")
    for i,row in enumerate(executions):
        require(row["waitCompleted"] and row["exitCode"]==(1 if i==5 else 0),"Original six actual wait/exit differs")
        actual=(PRIOR/row["rawLog"]).read_bytes()
        require(sha(actual)==row["rawSha256"] and len(actual)==row["rawByteCount"],"Original raw bytes differ")
    require(executions[-1]["argv"]==["python","scripts/run-agent-coordination-gate.py","--base-ref",B,"--head-ref",M,"--task","OPS-011","--branch-name","main"],"Original wrong argument is not the observed one")
    before=snapshot(prior["after"])
    # The CLI defines --branch-name as the actual PR branch; checkout remains actual main.
    argv=[PYTHON,"scripts/run-agent-coordination-gate.py","--base-ref",B,"--head-ref",M,"--task","OPS-011","--branch-name",BRANCH]
    OUT.mkdir()
    row=dict(label="coordination",argv=argv,cwd=str(NATIVE),startedAt=utc(),rawLog="coordination.txt")
    entry=dict(kind="OPS011_MAIN_COORDINATION_ARGUMENT_CORRECTION_ONLY",actualMain=M,tree=T,base=B,source=S,
        checkoutBranch="main",actualPrNumber=111,actualPrBranch=BRANCH,pid=os.getpid(),argv=[sys.executable,*sys.argv],
        scriptSha256=sha(Path(__file__).read_bytes()),startedAt=utc(),before=before,correctedCommand=argv,
        originalFailedSix=dict(path=str(PRIOR),proofSha256=sha(raw),commandExecutionsSha256=sha(execraw)),
        priorFiveAreSameActualMainAndNotRepeated=True,localFullSuiteRepeated=False)
    save("execution-entry.json",entry)
    with (OUT/"coordination.txt").open("x",encoding="utf-8",buffering=1) as log:
        log.write("Source Commit: "+M+"\nCommand: "+" ".join(argv)+"\n"); log.flush(); os.fsync(log.fileno())
        child=subprocess.Popen(argv,cwd=NATIVE,stdout=log,stderr=subprocess.STDOUT,text=True,
            env={**os.environ,"PYTHONDONTWRITEBYTECODE":"1","GITHUB_REPOSITORY":"ElectricDogCN/Guize","GITHUB_HEAD_REF":BRANCH})
        row["pid"]=child.pid
        save("command-start.json",row)
        code=child.wait(); row.update(exitCode=code,waitCompleted=True,completedAt=utc())
        log.write("\nExit Code: "+str(code)+"\n"); log.flush(); os.fsync(log.fileno())
    lograw=(OUT/"coordination.txt").read_bytes()
    row.update(rawSha256=sha(lograw),rawByteCount=len(lograw))
    save("command-execution.json",row)
    after=snapshot(before)
    combined={r["label"]:r["exitCode"] for r in executions[:5]}
    combined["coordination"]=code
    save("verification-worktrees.json",dict(kind="OPS011_MAIN_SIX_WITH_EXPLICIT_COORDINATION_ARGUMENT_CORRECTION",
        actualMain=M,tree=T,base=B,source=S,orderedParents=[B,S],prNumber=111,before=before,after=after,
        allCleanBeforeAndAfter=True,checks=combined,correctedCoordination=row,
        originalFailedSix=entry["originalFailedSix"],originalFailureRetained=True,
        priorFiveAreSameActualMainAndNotRepeated=True,localFullSuiteRepeated=False,
        requiredMainSixPassed=code==0,actualMainAccepted=False,currentMainCiAccepted=False,
        runtimeAccepted=False,fullV1Complete=False))
    print("Corrected same-main coordination exit "+str(code)+"; original five and failure retained.",flush=True)
    return code
if __name__=="__main__": raise SystemExit(main())
