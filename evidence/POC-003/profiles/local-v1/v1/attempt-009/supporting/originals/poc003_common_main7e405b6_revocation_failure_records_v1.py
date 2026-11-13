"""Read existing matrix outcome records without executing or accepting a run.

The future qualified supervisor must incorporate this reviewed behavior explicitly;
this diagnostic helper grants no source, runtime, measurement or retry authority.
"""
import json
from pathlib import Path


class MatrixOutcomeError(RuntimeError):
    pass


def retain_revocation_outcomes(result, writable):
    """Retain readable evidence first, then distinguish runtime and artifact failure.

    The caller supplies its actual attach/engine observations. Missing or malformed
    records never stand in for an owner/target wait. This does not validate scenario
    outcomes or relax the supervisor's original 26-epoch success assertions.
    """
    writable=Path(writable)
    missing=[]; unreadable=[]; closures=[]
    # Repeated inspection must not leave a stale successful owner record behind.
    for name in ('clientReport','actualOwnerWait','actualTargetClosures'):
        result.pop(name,None)

    def read(relative):
        path=writable/relative
        try:
            value=json.loads(path.read_bytes())
            if not isinstance(value,dict):raise ValueError('record must be a JSON object')
            return value
        except FileNotFoundError:
            missing.append(relative)
        except (OSError,ValueError) as error:
            unreadable.append(dict(path=relative,errorType=type(error).__name__,error=str(error)[:512]))
        return None

    client=read('warm-cache-revocation-client.json')
    owner=read('work/execution-owner-wait.json')
    if client is not None:result['clientReport']=client
    if owner is not None:result['actualOwnerWait']=owner
    for index in range(2):
        closure=read('work/process-epochs/epoch-'+str(index)+'/closure.json')
        if closure is not None:closures.append(closure)
    result.update(actualTargetClosures=closures,missingOutcomeArtifacts=missing,
                  unreadableOutcomeArtifacts=unreadable,readableClosureCount=len(closures),
                  requiredOutcomeArtifactsPresent=not missing and not unreadable)
    attach=result.get('attachedCliExitCode'); engine=result.get('engineExitCode')
    runtime_failure=bool(result.get('runtimeError') or result.get('externalCleanup')
                         or type(attach) is not int or type(engine) is not int
                         or attach!=0 or engine!=0)
    result['runtimeOutcomeFailed']=runtime_failure
    if runtime_failure:
        result['primaryOutcomeFailure']=dict(kind='runtime',attachedCliExitCode=attach,
            engineExitCode=engine,runtimeError=result.get('runtimeError'),
            externalCleanup=list(result.get('externalCleanup',[])))
        raise MatrixOutcomeError('Owned runtime failed: attach='+str(attach)+', engine='+str(engine))
    if missing or unreadable:
        result['primaryOutcomeFailure']=dict(kind='incomplete_outcome_artifacts',
                                            missing=missing,unreadable=unreadable)
        raise MatrixOutcomeError('Required owner/target outcome artifacts are incomplete')
    result['primaryOutcomeFailure']=None
    return result
