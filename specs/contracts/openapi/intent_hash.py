"""Executable contract vectors, not a runtime authorization or approval service."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qsl, quote, unquote, urlsplit

import rfc8785


class IntentError(ValueError):
    pass


def canonical_json(value):
    """RFC 8785 UTF-8; unsupported numbers/Unicode/keys fail closed."""
    try:
        return rfc8785.dumps(value)
    except (rfc8785.CanonicalizationError, TypeError, ValueError) as exc:
        raise IntentError("not an RFC 8785 JSON value") from exc


def normalize_path(path):
    if not isinstance(path, str) or re.search(r"%(?![0-9A-Fa-f]{2})", path):
        raise IntentError("invalid path encoding")
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or parsed.path != path:
        raise IntentError("path must be relative and exclude query/fragment")
    if re.search(r"%2f|%5c", path, re.I):
        raise IntentError("encoded separators are ambiguous")
    try:
        decoded = unquote(path, encoding="utf-8", errors="strict")
    except UnicodeError as exc:
        raise IntentError("invalid UTF-8 path") from exc
    if not decoded.startswith("/api/v1/") or "\\" in decoded:
        raise IntentError("not the versioned gateway path")
    if any(part in {"", ".", ".."} for part in decoded.split("/")[1:]):
        raise IntentError("ambiguous path segments")
    if any(ord(c) < 32 or ord(c) == 127 for c in decoded):
        raise IntentError("control character in path")
    try:
        return quote(decoded, safe="/:@-._~", encoding="utf-8", errors="strict")
    except UnicodeError as exc:
        raise IntentError("invalid Unicode path") from exc


def normalize_query(query):
    """Decoded names map to ordered string arrays; duplicate values are retained."""
    if isinstance(query, str):
        if re.search(r"%(?![0-9A-Fa-f]{2})", query):
            raise IntentError("invalid query encoding")
        try:
            pairs = parse_qsl(query, keep_blank_values=True, encoding="utf-8", errors="strict")
        except (UnicodeError, ValueError) as exc:
            raise IntentError("invalid UTF-8 query") from exc
        result = {}
        for name, value in pairs:
            result.setdefault(name, []).append(value)
    elif isinstance(query, dict):
        result = {}
        for name, values in query.items():
            if not isinstance(name, str) or not isinstance(values, list) or not values:
                raise IntentError("query values must be nonempty string arrays")
            if any(not isinstance(value, str) for value in values):
                raise IntentError("non-string query value")
            result[name] = list(values)
    else:
        raise IntentError("query must be a string or decoded string-array map")
    canonical_json(result)
    return result


def _request(method, path, query, body):
    if not isinstance(method, str) or method.upper() not in {"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"}:
        raise IntentError("invalid HTTP method")
    if body is not None and not isinstance(body, dict):
        raise IntentError("control request body must be an object or null")
    canonical_json(body)
    return {"method": method.upper(), "path": normalize_path(path),
            "query": normalize_query(query), "body": None if body is None else dict(body)}


def _carrier(body, approval_carrier, approval_header):
    if type(approval_carrier) is not bool:
        raise IntentError("carrier policy must come from the resolved operation")
    if not approval_carrier:
        if approval_header is not None:
            raise IntentError("unexpected approval transport")
        return body, None
    body_id = body.get("approvalId") if body is not None and "approvalId" in body else None
    header_id = approval_header.strip(" \t") if isinstance(approval_header, str) else approval_header
    for value in (body_id, header_id):
        if value is not None and (not isinstance(value, str) or not re.fullmatch(r"apr_[A-Za-z0-9_-]{1,64}", value)):
            raise IntentError("invalid approval carrier")
    if body is not None and "approvalId" in body and body_id is None:
        raise IntentError("null approval carrier")
    if body_id is not None and header_id is not None and body_id != header_id:
        raise IntentError("approval header/body mismatch")
    business_body = None if body is None else {key: value for key, value in body.items() if key != "approvalId"}
    return business_body, body_id if body_id is not None else header_id


def protected_intent(action, resource_id, revision, method, path, query, body,
                     *, approval_carrier=False, approval_header=None):
    """Caller supplies server-resolved operation/resource/revision after validation.

    Only the declared top-level approvalId transport is removed. Nested business
    fields and all other request data remain. No approval ID is needed to propose
    an intent before the server creates its immutable approval snapshot.
    """
    if not isinstance(action, str) or not re.fullmatch(r"[a-z][A-Za-z0-9]+", action):
        raise IntentError("invalid resolved operation")
    if not isinstance(resource_id, str) or not re.fullmatch(r"[a-z]{2,12}_[A-Za-z0-9_-]{1,64}", resource_id):
        raise IntentError("invalid resolved resource")
    if type(revision) is not int or not 1 <= revision <= 9007199254740991:
        raise IntentError("invalid resolved revision")
    request = _request(method, path, query, body)
    request["body"], _ = _carrier(request["body"], approval_carrier, approval_header)
    result = {"purpose": "approval-intent", "action": action, "resourceId": resource_id,
              "revision": revision, "request": request}
    canonical_json(result)
    return result


def intent_digest(*args, **kwargs):
    return hashlib.sha256(canonical_json(protected_intent(*args, **kwargs))).hexdigest()


def request_fingerprint(method, path, query, body, *, approval_carrier=False, approval_header=None):
    """Full request fingerprint preserves the normalized approval carrier value.

    Header/body placements of the same declared carrier are equivalent; changing
    its value changes the digest. Subject/operation/key scope, reauthorization and
    transactional claim durability remain mandatory server responsibilities.
    """
    request = _request(method, path, query, body)
    request["body"], approval_id = _carrier(request["body"], approval_carrier, approval_header)
    if approval_carrier and approval_id is None:
        raise IntentError("execution requires an approval carrier")
    result = {"purpose": "idempotency-fingerprint", "request": request}
    if approval_carrier:
        result["approvalId"] = approval_id
    return hashlib.sha256(canonical_json(result)).hexdigest()
