"""Bounded, read-only OpenList v4.2.6 numeric-page listing observations."""
from __future__ import annotations

import hashlib
import http.client
import json
import math
import re
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from openlist_source import MAX_BODY_BYTES, RESPONSE_HEADERS, SourceError, _NoRedirect, _segments

MAX_OBJECTS = 1_100_000
MAX_PAGE = 1000
CAPABILITY_FIELDS = {"sign", "thumb", "token", "password", "raw_url"}


def _positive(value, maximum, code):
    if type(value) is not int or not 1 <= value <= maximum:
        raise SourceError(code)


def _unique(pairs):
    row = {}
    for key, value in pairs:
        if key in row:
            raise SourceError("DUPLICATE_LISTING_JSON_FIELD")
        row[key] = value
    return row


def _decode(raw):
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except (UnicodeError, ValueError, RecursionError):
        raise SourceError("INVALID_LISTING_JSON") from None


def _sensitive(value, token):
    if isinstance(value, dict):
        return any((token is not None and token in key)
                   or (key.lower() in CAPABILITY_FIELDS and bool(item)) or _sensitive(item, token)
                   for key, item in value.items())
    if isinstance(value, list):
        return any(_sensitive(item, token) for item in value)
    return isinstance(value, str) and token is not None and token in value


def _cursor(directory, page):
    return json.dumps({"directory": directory, "page": page}, ensure_ascii=True,
                      sort_keys=True, separators=(",", ":"))


def _modified_at(value):
    if not isinstance(value, str) or len(value) > 128:
        raise SourceError("INVALID_LISTING_TIMESTAMP")
    match = re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.([0-9]+))?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])", value)
    if match is None:
        raise SourceError("INVALID_LISTING_TIMESTAMP")
    try:
        observed = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise SourceError("INVALID_LISTING_TIMESTAMP") from None
    # Convert only whole seconds with datetime; retain all observed fractional digits.
    fraction = (match.group(1) or "").rstrip("0")
    return (f"{observed.year:04}-{observed.month:02}-{observed.day:02}T"
            f"{observed.hour:02}:{observed.minute:02}:{observed.second:02}"
            + ("."+fraction if fraction else "") + "Z")


class OpenListListing:
    def __init__(self, origin, scope, *, token=None, timeout=5.0):
        if (not isinstance(origin, str) or origin.startswith(" ")
                or any(ord(c) < 32 or ord(c) == 127 for c in origin)):
            raise SourceError("INVALID_LISTING_ORIGIN")
        try:
            parsed = urllib.parse.urlsplit(origin)
            port = parsed.port
        except ValueError:
            raise SourceError("INVALID_LISTING_ORIGIN") from None
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not port
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
            raise SourceError("LOOPBACK_LISTING_ORIGIN_REQUIRED")
        parts = _segments(scope)
        if not parts or parts[0].startswith("@s"):
            raise SourceError("EXPLICIT_FIXTURE_SCOPE_REQUIRED")
        self.scope = "/".join(parts)
        self.endpoint = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "/api/fs/list", "", ""))
        if type(timeout) not in (float, int) or not math.isfinite(timeout) or not 0 < timeout <= 30:
            raise SourceError("INVALID_SOCKET_TIMEOUT")
        if token is not None and (not isinstance(token, str) or not token
                                  or len(token) > 8192 or any(ord(c) < 33 or ord(c) > 126 for c in token)):
            raise SourceError("INVALID_READER_TOKEN")
        self._token, self.timeout = token, float(timeout)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())

    def observe(self, directory="", *, page=1, per_page=200, maximum_bytes=MAX_BODY_BYTES):
        parts = _segments(directory)
        _positive(page, MAX_OBJECTS + 1, "INVALID_LISTING_PAGE")
        _positive(per_page, MAX_PAGE, "INVALID_LISTING_PAGE_SIZE")
        _positive(maximum_bytes, MAX_BODY_BYTES, "INVALID_RESPONSE_LIMIT")
        request_body = json.dumps(dict(path="/" + self.scope + ("/" + "/".join(parts) if parts else ""),
                                       password="", page=page, per_page=per_page, refresh=False),
                                  ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
        headers = {"Content-Type": "application/json", "Accept": "application/json",
                   "Accept-Encoding": "identity", "User-Agent": "Guize-POC005-listing-v1"}
        if self._token is not None:
            headers["Authorization"] = self._token
        clock = time.get_clock_info("perf_counter")
        if not clock.monotonic:
            raise SourceError("MONOTONIC_CLOCK_REQUIRED")
        start = time.perf_counter_ns()
        observation = dict(endpointURL=self.endpoint, method="POST", directory="/".join(parts),
                           page=page, perPage=per_page, requestBody=request_body,
                           requestBodySha256=hashlib.sha256(request_body).hexdigest(),
                           startedAt=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'), monotonicStartNs=start,
                           clock="time.perf_counter_ns", clockImplementation=clock.implementation,
                           clockResolutionSeconds=clock.resolution, socketTimeoutSeconds=self.timeout,
                           maximumBodyBytes=maximum_bytes, status=None, headers={}, body=b"",
                           bodyComplete=False, bodyRetained=True)
        raw = bytearray()
        try:
            request = urllib.request.Request(self.endpoint, data=request_body, method="POST", headers=headers)
            try:
                response = self.opener.open(request, timeout=self.timeout)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                observation["status"] = response.status
                for name in (*RESPONSE_HEADERS, "Date"):
                    values = response.headers.get_all(name, [])
                    if len(values) > 1:
                        raise SourceError("AMBIGUOUS_RESPONSE_HEADER")
                    if values:
                        if self._token is not None and self._token in values[0]:
                            raise SourceError("SENSITIVE_RESPONSE_HEADER")
                        observation["headers"][name.lower()] = values[0]
                if 300 <= response.status < 400:
                    raise SourceError("REDIRECT_REJECTED")
                if observation["headers"].get("content-encoding", "identity").lower() != "identity":
                    raise SourceError("ENCODED_BODY_UNSUPPORTED")
                length = observation["headers"].get("content-length")
                if length is not None and re.fullmatch(r"[0-9]+", length) is None:
                    raise SourceError("INVALID_CONTENT_LENGTH")
                if length is not None and int(length) > maximum_bytes:
                    raise SourceError("RESPONSE_BODY_LIMIT")
                while True:
                    chunk = response.read1(min(65536, maximum_bytes + 1 - len(raw)))
                    if not chunk:
                        break
                    raw.extend(chunk)
                    if len(raw) > maximum_bytes:
                        raise SourceError("RESPONSE_BODY_LIMIT")
                if length is not None and len(raw) != int(length):
                    raise SourceError("TRUNCATED_RESPONSE")
                observation["bodyComplete"] = True
        except SourceError as error:
            observation["error"] = error.code
            error.observation = observation
            raise
        except (OSError, urllib.error.URLError, http.client.HTTPException, ValueError):
            observation["error"] = "SOURCE_TRANSPORT_FAILURE"
            raise SourceError("SOURCE_TRANSPORT_FAILURE", observation) from None
        finally:
            observation.update(endedAt=datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                               monotonicEndNs=time.perf_counter_ns(), bodyBytes=len(raw),
                               bodySha256=hashlib.sha256(raw).hexdigest())
            observation["elapsedNs"] = observation["monotonicEndNs"] - start
            omitted = None
            if self._token is not None and self._token.encode() in raw:
                omitted = "SENSITIVE_LISTING_CAPABILITY"
            else:
                try:
                    if _sensitive(_decode(raw), self._token):
                        omitted = "SENSITIVE_LISTING_CAPABILITY"
                except (SourceError, RecursionError):
                    omitted = "UNINSPECTABLE_LISTING_BODY"
            if omitted is not None:
                observation.update(bodyRetained=False, bodyOmittedReason=omitted)
            else:
                observation["body"] = bytes(raw)
        if not observation["bodyRetained"]:
            raise SourceError(observation["bodyOmittedReason"], observation)
        return observation

    @staticmethod
    def parse_page(observation):
        try:
            if (observation.get("error") or observation["status"] != 200
                    or not observation["bodyComplete"] or not observation["bodyRetained"]):
                raise SourceError("SUCCESSFUL_LISTING_HTTP_REQUIRED")
            if observation["headers"].get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise SourceError("LISTING_JSON_CONTENT_TYPE_REQUIRED")
            body = _decode(observation["body"])
            if not isinstance(body, dict) or type(body.get("code")) is not int:
                raise SourceError("LISTING_APPLICATION_CODE_REQUIRED")
            observation["applicationCode"] = body["code"]
            if body["code"] != 200:
                raise SourceError("LISTING_APPLICATION_FAILURE")
            data = body.get("data")
            if not isinstance(data, dict) or type(data.get("total")) is not int or not 0 <= data["total"] <= MAX_OBJECTS:
                raise SourceError("INVALID_LISTING_TOTAL")
            total = data["total"]
            rows = data.get("content")
            if rows is None and total == 0:
                rows = []
            if not isinstance(rows, list) or len(rows) > observation["perPage"]:
                raise SourceError("INVALID_LISTING_CONTENT")
            offset = (observation["page"] - 1) * observation["perPage"]
            if (offset >= total and (offset != 0 or total != 0)
                    or len(rows) != min(observation["perPage"], max(0, total - offset))):
                raise SourceError("LISTING_PAGE_CARDINALITY_MISMATCH")
            entries, names = [], set()
            for row in rows:
                if not isinstance(row, dict):
                    raise SourceError("INVALID_LISTING_OBJECT")
                name, directory, size, modified = (row.get(key) for key in ("name", "is_dir", "size", "modified"))
                if (not isinstance(name, str) or not name or len(name) > 1024 or "/" in name
                        or _segments(name) != [name] or name in names):
                    raise SourceError("INVALID_OR_DUPLICATE_LISTING_NAME")
                names.add(name)
                if type(directory) is not bool or type(size) is not int or not 0 <= size <= 2**63 - 1:
                    raise SourceError("INVALID_LISTING_OBJECT_TYPE_OR_SIZE")
                modified = _modified_at(modified)
                parent = observation["directory"]
                locator = parent + "/" + name if parent else name
                if len(locator) > 8192 or len(locator.split("/")) > 64:
                    raise SourceError("LISTING_PATH_OR_DEPTH_LIMIT")
                entries.append(dict(locator=locator, kind="directory" if directory else "file",
                                    fileSizeBytes=0 if directory else size, sourceSizeBytes=size,
                                    modifiedAt=modified, stableObjectId=None, versionId=None))
            return total, entries
        except SourceError as error:
            error.observation = observation
            raise
        except (KeyError, TypeError, ValueError):
            raise SourceError("INVALID_LISTING_OBJECT", observation) from None

    def walk(self, index_path, *, on_observation, on_page, per_page=200,
             maximum_objects=MAX_OBJECTS, maximum_bytes=MAX_BODY_BYTES):
        """Retain a new diagnostic DB even on failure; completion is explicit."""
        _positive(maximum_objects, MAX_OBJECTS, "INVALID_LISTING_POPULATION_LIMIT")
        _positive(per_page, MAX_PAGE, "INVALID_LISTING_PAGE_SIZE")
        _positive(maximum_bytes, MAX_BODY_BYTES, "INVALID_RESPONSE_LIMIT")
        path = Path(index_path)
        with path.open("xb"):
            pass
        db = sqlite3.connect(path)
        try:
            db.executescript("""
                CREATE TABLE state(completed INTEGER NOT NULL, objects INTEGER NOT NULL, pages INTEGER NOT NULL);
                INSERT INTO state VALUES(0,0,0);
                CREATE TABLE dirs(id INTEGER PRIMARY KEY,path TEXT UNIQUE NOT NULL,page INTEGER NOT NULL,
                                  total INTEGER,done INTEGER NOT NULL);
                CREATE INDEX pending_dirs ON dirs(done,id);
                INSERT INTO dirs(path,page,done) VALUES('',1,0);
                CREATE TABLE objects(locator TEXT PRIMARY KEY,kind TEXT NOT NULL,fileSizeBytes INTEGER NOT NULL,
                                     sourceSizeBytes INTEGER NOT NULL,modifiedAt TEXT NOT NULL);
            """)
            cursor, count, pages = None, 0, 0
            while True:
                pending = db.execute("SELECT id,path,page,total FROM dirs WHERE done=0 ORDER BY id LIMIT 1").fetchone()
                if pending is None:
                    break
                ident, directory, page, prior_total = pending
                try:
                    observation = self.observe(directory, page=page, per_page=per_page, maximum_bytes=maximum_bytes)
                except SourceError as error:
                    if error.observation is not None:
                        on_observation(error.observation)
                    raise
                on_observation(observation)
                total, entries = self.parse_page(observation)
                if prior_total is not None and prior_total != total:
                    raise SourceError("LISTING_TOTAL_CHANGED", observation)
                if count + len(entries) > maximum_objects:
                    raise SourceError("LISTING_POPULATION_LIMIT", observation)
                try:
                    with db:
                        for entry in entries:
                            db.execute("INSERT INTO objects VALUES(?,?,?,?,?)", tuple(entry[k] for k in
                                       ("locator", "kind", "fileSizeBytes", "sourceSizeBytes", "modifiedAt")))
                            if entry["kind"] == "directory":
                                db.execute("INSERT INTO dirs(path,page,done) VALUES(?,1,0)", (entry["locator"],))
                        if page * per_page < total:
                            db.execute("UPDATE dirs SET page=page+1,total=? WHERE id=?", (total, ident))
                        else:
                            db.execute("UPDATE dirs SET done=1,total=? WHERE id=?", (total, ident))
                        count += len(entries)
                        pages += 1
                        db.execute("UPDATE state SET objects=?,pages=?", (count, pages))
                except sqlite3.IntegrityError:
                    raise SourceError("DUPLICATE_LISTING_PATH", observation) from None
                next_row = db.execute("SELECT path,page FROM dirs WHERE done=0 ORDER BY id LIMIT 1").fetchone()
                next_cursor = _cursor(*next_row) if next_row else None
                on_page(dict(observation=observation, entries=entries, directoryTotal=total,
                             requestCursor=cursor, nextCursor=next_cursor))
                cursor = next_cursor
            with db:
                db.execute("UPDATE state SET completed=1")
            return dict(completed=True, objectCount=count, pageCount=pages,
                        stableProviderIdentityVerified=False, snapshotVerified=False)
        finally:
            db.close()
