"""Retain the local access witnesses from the observed fixture replay."""

from hashlib import file_digest
import json
from os import fstat
from pathlib import Path

from replay_fixture import retained_access_http_response


PLAYBACK_CASES = {
    "range": "authorized_range", "if-range": "authorized_if_range", "full": "authorized_stream",
    "anonymous": "unauthorized", "expired": "expired", "other-identity": "cross_user",
}


def retain(path: Path, record: dict) -> str:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(record, stream, indent=2)
        stream.write("\n")
    return path.as_posix()


def request_binding(directory: Path, row: dict) -> dict:
    native = row["nativeTransport"]
    argv = native["requestCommand"]
    response = directory / row["rawResponse"]
    if Path(argv[-1]) != response:
        raise ValueError("Request transport command does not bind the retained HTTP response")
    with Path(argv[2]).open("rb") as script:
        observer = "sha256:" + file_digest(script, "sha256").hexdigest()
    return {
        "requestId": row["requestId"], "traceId": row["traceId"], "observerBuild": observer,
        "commandArgs": argv, "pid": native["requestProcessId"], "exitCode": native["requestExitCode"],
        "responseRef": argv[-1], "responseBodyRef": (directory / row["responseBody"]).as_posix(),
        "responseSha256": row["rawResponseSha256"],
    }


def tls_execution(directory: Path, case: str, context: dict, native: dict, binding: dict) -> dict:
    if "tlsCommand" not in native:
        return {}
    stdout = native["tlsCommand"][-1]
    if Path(stdout) != directory / native["tlsResult"]:
        raise ValueError("TLS transport command does not bind the retained client stdout")
    record = {
        "schemaVersion": 1, "kind": "local_access_tls_execution", "context": context,
        "observerBuild": binding["observerBuild"], "commandArgs": native["tlsCommand"],
        "connectionId": binding["traceId"], "processId": native["tlsProcessId"],
        "startedAt": native["tlsStartedAt"], "finishedAt": native["tlsFinishedAt"],
        "exitCode": native["tlsExitCode"], "stdoutRef": stdout, "stdoutSha256": native["tlsResultSha256"],
        "stderrRef": (directory / native["tlsStderr"]).as_posix(), "stderrSha256": native["tlsStderrSha256"],
    }
    return {
        "tlsExecutionRef": retain(directory / f"{case}.tls-execution.json", record),
        "tlsConnectionId": record["connectionId"], "tlsClientProcessId": record["processId"],
    }


def request_scope(row: dict, binding: dict) -> dict:
    target = binding["commandArgs"][-3]
    return {
        "userId": row.get("userId", "anonymous"), "grantId": row.get("grantId"), "requestURL": target,
        "requestRange": row["requestRange"] or "", "ifRange": row.get("ifRange") or "",
        "cacheKey": row.get("cacheKey") or f"uncached:{target}",
    }


def source_events(row: dict, binding: dict, scope: dict, context: dict, source_url: str) -> list[dict]:
    if not row.get("sourceRequestedAt"):
        return []
    request = dict(binding, originRequestId=f"{binding['traceId']}:openlist")
    events = [{"type": "origin_request", "observedAt": row["sourceRequestedAt"], **request,
               "requestURL": source_url, "requestRange": scope["requestRange"]}]
    for index, read in enumerate(row["sourceReads"], 1):
        events.append({"type": "object_read", "observedAt": read["observed_at"], **request,
                       "readId": f"{request['originRequestId']}:{index}", "assetId": context["assetId"],
                       "sourceVersion": context["sourceVersion"], "offset": read["offset"],
                       "byteCount": read["byte_count"], "sha256": read["sha256"]})
    return events


def outcome(context: dict, case: str, row: dict, scope: dict, binding: dict, window: float) -> dict:
    status, headers, count, digest = retained_access_http_response(Path(binding["responseRef"]))
    if scope["requestRange"]:
        first, last = map(int, scope["requestRange"].removeprefix("bytes=").split("-"))
    else:
        first, last = 0, count - 1
    buffered = max(row["clientPeakReceiveBytes"], row.get("sourceReadPeakBytes", 0),
                   count if status == 206 else 0)
    return {
        "schemaVersion": 1, "kind": "access_request_outcome", **context, "case": case, **scope,
        "observedAt": row["clientFinishedAt"], "rangeStart": first, "rangeEnd": last, "statusCode": status,
        "etag": headers.get("etag", ""), "contentRange": headers.get("content-range", ""),
        "responseBodyRef": binding["responseBodyRef"], "responseSha256": digest, "responseByteCount": count,
        "requestCount": 1, "originRequestCount": row.get("completedSourceTransfers", 0),
        "maximumBufferedBytes": buffered, "rateWindowSeconds": window, "rateAttempts": [],
    }


def retain_request(directory: Path, context: dict, case: str, row: dict, window: float, source_url: str) -> str:
    binding = request_binding(directory, row)
    scope = request_scope(row, binding)
    summary = outcome(context, case, row, scope, binding, window)
    ids = {key: binding[key] for key in ("requestId", "traceId")}
    authorization = {key: context[key] for key in ("assetId", "sourceVersion", "aclVersion")}
    # The direct OpenList denial is observed when its response starts arriving at the client.
    auth_at = row.get("gatewayObservedAt", row["firstResponseAt"])
    decision = "allowed" if row.get("gatewayDecision") == "allowed" else "denied"
    if (summary["statusCode"] in (200, 206)) != (decision == "allowed"):
        raise ValueError("Observed HTTP result and access decision disagree")
    events = [
        {"type": "request", "observedAt": row["clientRequestStartedAt"], **ids, **scope, "httpMethod": "GET"},
        {"type": "authorization", "observedAt": auth_at, **ids, **authorization, "decision": decision,
         "userId": scope["userId"], "grantId": scope["grantId"]},
        *source_events(row, ids, scope, context, source_url),
        {"type": "exit", "observedAt": row["clientFinishedAt"], **ids, "exitCode": binding["exitCode"]},
    ]
    transport = {
        "schemaVersion": 1, "kind": "local_access_request_transport", "context": context, "case": case, **binding,
        "startedAt": row["clientStartedAt"], "finishedAt": row["clientFinishedAt"], "peerAddress": row["peerAddress"],
        "peerPort": row["peerPort"], "connectionOutcome": "connected", "maximumBufferedBytes": summary["maximumBufferedBytes"],
        "events": events, **tls_execution(directory, case, context, row["nativeTransport"], binding),
    }
    reference = retain(directory / f"{case}.request.json", transport)
    return retain(directory / f"{case}.outcome.json", {**summary, **ids, "transportRef": reference})


def retain_rate(directory: Path, context: dict, playback: dict) -> str:
    traces = playback["rateTransport"]
    rows = playback["caseResults"][-len(traces):]
    final = rows[-1]
    binding = request_binding(directory, final)
    summary = outcome(context, "rate_limit", final, request_scope(final, binding), binding, playback["windowSeconds"])
    attempts = [
        {"sequence": sequence, "requestId": row["requestId"], "traceId": row["traceId"],
         "transportRef": (directory / trace).as_posix(), "observedAt": row["clientFinishedAt"], "statusCode": row["status"],
         "originContacted": bool(row["completedSourceTransfers"]), "responseBodyRef": (directory / row["responseBody"]).as_posix(),
         "responseSha256": row["bodySha256"], "responseByteCount": row["bodyByteCount"]}
        for sequence, (row, trace) in enumerate(zip(rows, traces, strict=True), 1)
    ]
    summary.update(requestCount=len(attempts), originRequestCount=sum(a["originContacted"] for a in attempts), rateAttempts=attempts)
    return retain(directory / "rate_limit.outcome.json", summary)


def retain_access_report(root: Path, playback: dict, resources: dict) -> str:
    context = playback["transportContext"]
    window = playback["windowSeconds"]
    origin = playback["originDenial"]
    source_url = origin["nativeTransport"]["requestCommand"][-3]
    playback_dir = root / "playback"
    cases = []
    for row in playback["caseResults"]:
        case = PLAYBACK_CASES.get(row["case"])
        if case:
            ref = retain_request(playback_dir, context, case, row, window, source_url)
            cases.append({"case": case, "witnessRef": ref})
    origin_ref = retain_request(playback_dir, context, "direct_source", origin, window, source_url)
    cases.append({"case": "direct_source", "witnessRef": origin_ref})
    for case, row in resources["retainedDenials"].items():
        observed = row | {"clientStartedAt": row["started_at"], "clientRequestStartedAt": row["request_started_at"],
                          "clientFinishedAt": row["finished_at"], "firstResponseAt": row["first_response_at"],
                          "gatewayObservedAt": row["authorizationObservedAt"], "peerAddress": row["peer_address"],
                          "peerPort": row["peer_port"], "clientPeakReceiveBytes": row["peak_receive_bytes"],
                          "rawResponseSha256": row["raw_sha256"]}
        ref = retain_request(root / "resources", context, case, observed, window, source_url)
        cases.append({"case": case, "witnessRef": ref})
    cases.append({"case": "rate_limit", "witnessRef": retain_rate(playback_dir, context, playback)})
    return retain(root / "access-outcome.json", {"schemaVersion": 1, "kind": "access_outcome_report", **context, "cases": cases})


def retain_access_artifacts(path: Path, report_ref: str, command_output: Path, trust_store: Path) -> None:
    """Inventory the exact files referenced by the access and command records."""
    artifacts: dict[str, str] = {}

    def select(ref: str, kind: str) -> None:
        if artifacts.setdefault(ref, kind) != kind:
            raise ValueError("An access evidence reference has conflicting artifact types")

    def select_record(ref: str, kind: str) -> dict:
        select(ref, kind)
        return json.loads(Path(ref).read_bytes())

    report = select_record(report_ref, "measurement_output")
    select(command_output.as_posix(), "command_output")
    select(trust_store.as_posix(), "command_output")
    for case in report["cases"]:
        witness = select_record(case["witnessRef"], "measurement_output")
        select(witness["responseBodyRef"], "produced_media")
        for attempt in witness["rateAttempts"]:
            trace = select_record(attempt["transportRef"], "command_output")
            select(trace["responseRef"], "produced_media")
            select(trace["responseBodyRef"], "produced_media")
        if "transportRef" in witness:
            trace = select_record(witness["transportRef"], "command_output")
            select(trace["responseRef"], "produced_media")
            if "tlsExecutionRef" in trace:
                tls = select_record(trace["tlsExecutionRef"], "command_output")
                select(tls["stdoutRef"], "command_output")
                select(tls["stderrRef"], "command_output")

    inventory = []
    for ref, kind in sorted(artifacts.items()):
        with Path(ref).open("rb") as stream:
            digest = file_digest(stream, "sha256").hexdigest()
            count = fstat(stream.fileno()).st_size
        inventory.append({
            "ref": ref, "artifactType": kind, "byteCount": count, "sha256": "sha256:" + digest,
        })
    retain(path, {"rawOutputRefs": [record["ref"] for record in inventory], "rawExecutionArtifacts": inventory})
