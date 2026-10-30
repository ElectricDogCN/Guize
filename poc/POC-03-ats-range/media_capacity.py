"""Derive a conservative bound from closed records under the reviewed fixed source.

This does not approve a source, method, experiment or POC. The source callgraph,
native allocation domain, immutable initialization and isolation conditions still
need their independent approval and actual execution bindings.
"""
from datetime import datetime, timezone
import hashlib
from pathlib import Path

from durable_peak_probe import parse_durable_peaks, LIMIT as JOURNAL_LIMIT
from lab import unique_json

ORIGIN_BYTES = 73729
GATEWAY_BYTES = 409610
COLLECTOR_BYTES = 532492
PHASE_BYTES = 1048577
HASH_OWNER_BYTES = 4096


def _integer(value, name, minimum=0):
    if type(value) is not int or not minimum <= value <= 2**64-1:
        raise ValueError('invalid ' + name)
    return value


def _utc(value):
    if not isinstance(value, str) or not value.endswith('Z'):
        raise ValueError('actual UTC endpoint required')
    result = datetime.fromisoformat(value[:-1] + '+00:00')
    if result.tzinfo != timezone.utc:
        raise ValueError('actual UTC endpoint required')
    return result


def _read(path, limit=1048576):
    path = Path(path)
    with path.open('rb') as stream:
        raw = stream.read(limit + 1)
    if not raw or len(raw) > limit:
        raise ValueError('record byte quota')
    return unique_json(raw), raw


def closed_request_peaks(controller, collection):
    """Use retained cumulative peaks, never an idle snapshot's active count."""
    if (controller.get('kind') != 'CLOSED_CONTROLLER_REQUEST_WINDOW_NOT_AGGREGATE_MEMORY'
            or controller.get('closed') is not True):
        raise ValueError('closed controller window required')
    start, end = _utc(controller['startedAt']), _utc(controller['closedAt'])
    if start >= end:
        raise ValueError('nonempty controller window required')
    windows = controller['httpRequestWindows']
    if (not isinstance(windows, list) or len(windows) != 2
            or {row['listenerPort'] for row in windows} != {18231, 18233}):
        raise ValueError('both owned HTTP listener windows required')
    for row in windows:
        admitted = _integer(row['admitted'], 'HTTP admitted')
        if (row.get('closed') is not True or _integer(row.get('active'), 'HTTP active') != 0
                or _integer(row['finished'], 'HTTP finished') != admitted
                or _integer(row['peak'], 'HTTP peak') > admitted
                or not start <= _utc(row['startedAt']) <= _utc(row['closedAt']) <= end):
            raise ValueError('unfinished owned HTTP request interval')
    peaks = controller['requestConcurrency']
    if (peaks.get('kind') != 'SYNCHRONOUS_REQUEST_INTERVAL_HIGH_WATER_NOT_MEMORY_SAMPLING'
            or _integer(peaks.get('activeOrigin'), 'Origin active') != 0
            or _integer(peaks.get('activeGateway'), 'Gateway active') != 0):
        raise ValueError('closed synchronous controller peaks required')
    origin = _integer(peaks['peakOrigin'], 'Origin peak')
    gateway = _integer(peaks['peakGateway'], 'Gateway peak')
    by_port = {row['listenerPort']:row for row in windows}
    if origin > by_port[18231]['peak'] or gateway > by_port[18233]['peak']:
        raise ValueError('media peak exceeds owned HTTP admission peak')
    client = collection['requestConcurrency']
    if (client.get('kind') != 'SYNCHRONOUS_REQUEST_INTERVAL_HIGH_WATER_NOT_MEMORY_SAMPLING'
            or client.get('admissionClosed') is not True or _integer(client.get('active'), 'Collector active') != 0
            or not start <= _utc(client['closedAt']) <= end):
        raise ValueError('closed Collector admission required')
    peak = _integer(client['peak'], 'Collector peak', 1)
    rows = collection['rows']
    if not isinstance(rows, list) or not rows or peak > len(rows):
        raise ValueError('complete nonempty Collector intervals required')
    for row in rows:
        if not start <= _utc(row['startedAt']) <= _utc(row['finishedAt']) <= _utc(client['closedAt']):
            raise ValueError('Collector interval outside closed window')
    return dict(origin=origin, gateway=gateway, collector=peak)


def complete_serial_native_epochs(run, owner_wait, component_pins, *, expected_count):
    """Reparse every real finished native journal, including all helper epochs.

    The reviewed singleton owner forbids another launch before actual closure of
    the previous target. No artificial process-end timestamps are synthesized.
    """
    run = Path(run)
    count = _integer(expected_count, 'expected native epoch count', 1)
    if count > 128 or not isinstance(component_pins, dict) or not component_pins:
        raise ValueError('finite approved component/epoch set required')
    summary = owner_wait['targetClosureSummary']
    if (owner_wait.get('actualOwnerWaitCompleted') is not True
            or type(owner_wait.get('ownerExitCode')) is not int or owner_wait['ownerExitCode'] != 0
            or summary.get('allAccepted') is not True or summary.get('closureRoot') != 'process-epochs'
            or any(type(summary.get(k)) is not int or summary[k] != count
                   for k in ('epochCount', 'closedEpochCount', 'acceptedCount'))):
        raise ValueError('nonempty complete actual owner wait/summary required')
    root = run / 'process-epochs'
    if {p.name for p in root.iterdir()} != {'epoch-' + str(i) for i in range(count)}:
        raise ValueError('missing or extra native epoch')
    peaks = []
    previous_tick = -1
    identities = set()
    roles = []
    for number in range(count):
        folder = root / ('epoch-' + str(number))
        launch, _ = _read(folder / 'launch/launch.json')
        closure, _ = _read(folder / 'closure.json')
        if (launch.get('state') != 'completed' or launch.get('fixedSingleExecRequested') is not True
                or launch.get('targetExecAttestedByNativeJournal') is not True
                or launch.get('completeTrackedProcessEpoch') is not True
                or launch.get('waitCompleted') is not True or type(launch.get('exitCode')) is not int
                or launch['exitCode'] != 0 or launch.get('execErrorPipeClosedWithoutMessage') is not True
                or launch.get('componentsAfterExit') != launch.get('componentsBeforeExec')):
            raise ValueError('native launch/exit/component qualification incomplete')
        actual_components = launch['componentsBeforeExec']
        if not isinstance(actual_components, dict) or set(actual_components) != set(component_pins):
            raise ValueError('exact approved native component set required')
        for name, expected in component_pins.items():
            actual = actual_components[name]
            if (not isinstance(expected, str) or len(expected) != 64
                    or any(c not in '0123456789abcdef' for c in expected)
                    or not isinstance(actual, dict) or actual.get('sha256') != expected):
                raise ValueError('approved native component digest mismatch')
            _integer(actual.get('bytes'), 'component size', 1)
            _integer(actual.get('device'), 'component device')
            _integer(actual.get('inode'), 'component inode', 1)
        handoff = launch['singleExecHandoff']
        if any(handoff.get(k) is not True for k in ('grantAttempted','continueSent','listenerClosed')):
            raise ValueError('single owned initial exec handoff required')
        birth = launch['launchIdentity']
        _integer(birth['pid'], 'native PID', 1)
        _integer(birth['startTicks'], 'native birth ticks', 1)
        identity = (birth['pid'], birth['startTicks'])
        if identity in identities or launch['pid'] != birth['pid']:
            raise ValueError('duplicate or changed native process identity')
        identities.add(identity)
        tick = _integer(launch['goMonotonicNs'], 'GO monotonic endpoint', 1)
        if tick <= previous_tick:
            raise ValueError('native epoch launch order mismatch')
        if (closure.get('accepted') is not True or closure.get('error') is not None
                or closure.get('actualWaitCompleted') is not True
                or type(closure.get('exitCode')) is not int or closure['exitCode'] != 0
                or closure['pid'] != birth['pid'] or closure['epochRef'] != 'process-epochs/epoch-' + str(number)):
            raise ValueError('actual successful per-epoch closure required')
        with (folder / 'finished/durable-peaks.raw').open('rb') as stream:
            raw = stream.read(JOURNAL_LIMIT + 1)
        if len(raw) > JOURNAL_LIMIT:
            raise ValueError('durable journal quota')
        result = parse_durable_peaks(raw, birth, finished=True, exit_code=closure['exitCode'])
        retained = closure['trackedEpoch']
        if (retained.get('completeTrackedProcessEpoch') is not True or retained.get('waitCompleted') is not True
                or type(retained.get('exitCode')) is not int or retained['exitCode'] != 0
                or result['first']['beforeMonotonicNs'] < tick
                or any(retained.get(k) != result[k] for k in
                       ('rawSha256','recordCount','first','last','maximumObservedTrackedCapacityBytes'))
                or launch['journalSha256'] != result['rawSha256']):
            raise ValueError('complete native raw/capture/launch binding mismatch')
        previous_tick = result['last']['beforeMonotonicNs']
        command = launch['targetCommand']
        if command[-2:] == ['-n','2']:
            roles.append('start')
        elif command[-2:] in (['-C','verify_config'], ['-C','clear_cache']):
            roles.append(command[-1])
        else:
            raise ValueError('unexpected native target role')
        peaks.append(dict(token=str(number),pid=birth['pid'],startTicks=birth['startTicks'],
            rawSha256=result['rawSha256'],peakBytes=result['maximumObservedTrackedCapacityBytes']))
    expected_roles = ['verify_config','start'] + ['clear_cache','start'] * ((count-2)//2)
    if count < 2 or count % 2 or roles != expected_roles:
        raise ValueError('complete verify/start/clear native sequence required')
    if not any(row['peakBytes'] > 0 for row in peaks):
        raise ValueError('no actual native allocation peak retained')
    return dict(epochCount=count, epochs=peaks,
        maximumTrackedCapacityBytes=max(row['peakBytes'] for row in peaks),
        aggregation='max of complete actual serialized target epochs, conditional on the pinned singleton owner source')


def conservative_total(peaks, native_bytes, *, external_revocation_readers=0):
    """All independent maxima add; only the reviewed phase owners share a max."""
    o = _integer(peaks['origin'], 'Origin peak')
    g = _integer(peaks['gateway'], 'Gateway peak')
    c = _integer(peaks['collector'], 'Collector peak')
    extra = _integer(external_revocation_readers, 'separate fresh revocation reader count')
    if extra > 1:
        raise ValueError('only the reviewed single bounded revocation reader is supported')
    native = _integer(native_bytes, 'complete native peak')
    terms = dict(native=native, origin=o*ORIGIN_BYTES, gateway=g*GATEWAY_BYTES,
        collector=(c+extra)*COLLECTOR_BYTES, synchronousPhase=PHASE_BYTES,
        hash=(o+g+c+extra+1)*HASH_OWNER_BYTES)
    return dict(terms=terms, maximumBufferedBytes=sum(terms.values()),
        sourcePayloadOwnerPeaks=dict(origin=o,gateway=g,collector=c,externalRevocation=extra),
        sourceAndWindowConditionsRequired=True, independentAggregateAccepted=False,
        formalPocAccepted=False)
