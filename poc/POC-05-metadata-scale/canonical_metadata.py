"""Canonical frozen POC record streams around the isolated transactional scanner."""
from __future__ import annotations

import hashlib
import gzip
import json
import os
import re
import zlib
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path

from metadata_scan import (
    MAX_LINE_BYTES, MAX_PAGE_BYTES, MAX_PAGE_RECORDS, ScanError, Scanner,
    canonical, file_sha256, natural, text,
)

BASIC = {"objectId", "kind", "versionId", "depth", "fileSizeBytes"}
PROFILE = BASIC | {"name", "path", "modifiedAt"}
EVENT = {"eventId", "sequence", "objectId", "operation", "beforeVersion", "afterVersion"}
ANCHOR = "__poc005_virtual_anchor__"
ABSENT = "absent"
MAX_DECODED_BYTES = 2 * 1024 * 1024 * 1024
MAX_RECORDS = 2_000_000
STREAM_CHUNK_BYTES = 65536


def validate_profile(row):
    if not isinstance(row, dict) or set(row) != PROFILE:
        raise ScanError("INVALID_CANONICAL_PROFILE_FIELDS")
    text(row["objectId"], "OBJECT_ID")
    text(row["versionId"], "VERSION_ID")
    if row["objectId"] == ANCHOR or row["versionId"] == ABSENT:
        raise ScanError("RESERVED_CANONICAL_IDENTIFIER")
    if row["kind"] not in ("file", "directory"):
        raise ScanError("INVALID_CANONICAL_KIND")
    natural(row["depth"], "DEPTH", 64)
    natural(row["fileSizeBytes"], "SIZE", 2**63 - 1)
    if row["kind"] == "directory" and row["fileSizeBytes"]:
        raise ScanError("DIRECTORY_HAS_SIZE")
    text(row["name"], "NAME", 4096)
    text(row["path"], "PATH", 16384)
    if len(row["name"]) > 1024 or len(row["path"]) > 8192:
        raise ScanError("OVERSIZED_CANONICAL_PATH")
    parts = row["path"].split("/")
    if (any(not p or p in (".", "..") or "\\" in p or
            any(ord(c) < 32 or ord(c) == 127 for c in p) for p in parts)
            or parts[-1] != row["name"] or len(parts) != row["depth"]):
        raise ScanError("CANONICAL_PATH_DEPTH_MISMATCH")
    text(row["modifiedAt"], "MODIFIED_AT", 128)
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?(?:Z|[+-][0-9]{2}:[0-9]{2})", row["modifiedAt"]) is None:
        raise ScanError("INVALID_MODIFIED_AT")
    try:
        value = datetime.fromisoformat(row["modifiedAt"].replace("Z", "+00:00"))
        if value.tzinfo is None:
            raise ValueError()
    except ValueError:
        raise ScanError("INVALID_MODIFIED_AT") from None


def basic_record(profile):
    return {key: profile[key] for key in sorted(BASIC)}


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ScanError("DUPLICATE_JSON_FIELD")
        result[key] = value
    return result


def _line(handle):
    raw = handle.readline(MAX_LINE_BYTES + 1)
    if not raw:
        return None, b""
    if len(raw) > MAX_LINE_BYTES or not raw.endswith(b"\n"):
        raise ScanError("INVALID_CANONICAL_LINE")
    try:
        return json.loads(raw, object_pairs_hook=_unique), raw
    except (ValueError, UnicodeError) as error:
        if isinstance(error, ScanError):
            raise
        raise ScanError("INVALID_CANONICAL_JSON") from None


def _sha(value):
    if not isinstance(value, str) or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ScanError("INVALID_FIXTURE_SHA256")
    return value


def _signature(stat):
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns


def _stream_facts(handle, compressed):
    """Hash original bytes and validate a finite, single-member JSONL envelope."""
    digest = hashlib.sha256()
    decoder = zlib.decompressobj(31) if compressed else None
    size, records, line_bytes = 0, 0, 0

    def consume(chunk):
        nonlocal size, records, line_bytes
        size += len(chunk)
        if size > MAX_DECODED_BYTES:
            raise ScanError("CANONICAL_DECODED_BYTE_LIMIT")
        parts = chunk.split(b"\n")
        for index, part in enumerate(parts):
            line_bytes += len(part)
            if line_bytes + (index < len(parts) - 1) > MAX_LINE_BYTES:
                raise ScanError("INVALID_CANONICAL_LINE")
            if index < len(parts) - 1:
                records += 1
                line_bytes = 0
                if records > MAX_RECORDS:
                    raise ScanError("CANONICAL_RECORD_LIMIT")

    try:
        for physical in iter(lambda: handle.read(STREAM_CHUNK_BYTES), b""):
            digest.update(physical)
            if decoder is None:
                consume(physical)
                continue
            pending = physical
            while pending:
                decoded = decoder.decompress(pending, STREAM_CHUNK_BYTES)
                pending = decoder.unconsumed_tail
                if decoder.unused_data:
                    raise ScanError("CANONICAL_GZIP_TRAILING_DATA")
                consume(decoded)
        if decoder is not None and not decoder.eof:
            raise ScanError("CANONICAL_GZIP_INCOMPLETE")
    except zlib.error:
        raise ScanError("CANONICAL_GZIP_INVALID") from None
    if line_bytes:
        raise ScanError("INVALID_CANONICAL_LINE")
    return digest.hexdigest(), size


class CanonicalPair:
    def __init__(self, baseline, profiled, *, baseline_sha256, profiled_sha256,
                 source_id, snapshot_version, page_size=200):
        text(source_id, "SOURCE_ID")
        text(snapshot_version, "SNAPSHOT_VERSION")
        natural(page_size, "PAGE_SIZE", MAX_PAGE_RECORDS - 1)
        if not page_size:
            raise ScanError("EMPTY_PAGE_SIZE")
        self.paths = [Path(baseline), Path(profiled)]
        if self.paths[0].samefile(self.paths[1]):
            raise ScanError("INDEPENDENT_CANONICAL_STREAMS_REQUIRED")
        self.shas = [_sha(baseline_sha256), _sha(profiled_sha256)]
        self.signatures, self.descriptor_signatures = [], []
        self.decoded_sizes = []
        self.compressed = [path.name.endswith(".jsonl.gz") for path in self.paths]
        self._streams = [None, None]
        for path, expected, compressed in zip(self.paths, self.shas, self.compressed):
            before = _signature(path.stat())
            with path.open("rb") as handle:
                descriptor_before = _signature(os.fstat(handle.fileno()))
                # Windows path.stat/fstat can expose different ctime semantics.
                # Bind identity/size/mtime across APIs, then retain each full signature.
                if before[:4] != descriptor_before[:4]:
                    raise ScanError("FIXTURE_HANDLE_IDENTITY_MISMATCH")
                digest, decoded_size = _stream_facts(handle, compressed)
                if (digest != expected or before != _signature(path.stat())
                        or descriptor_before != _signature(os.fstat(handle.fileno()))):
                    raise ScanError("FIXTURE_DIGEST_MISMATCH")
            self.signatures.append(before)
            self.descriptor_signatures.append(descriptor_before)
            self.decoded_sizes.append(decoded_size)
        version = "pair-v1:" + hashlib.sha256(canonical({
            "baseline": self.shas[0], "profiled": self.shas[1],
            "snapshotVersion": snapshot_version}).encode()).hexdigest()
        self.binding = dict(source_id=source_id, fixture_sha256=self.shas[0], snapshot_version=version)
        self.page_size = page_size

    def close(self):
        """Release gzip readers; a subsequent read can reopen at a saved cursor."""
        for index, stream in enumerate(self._streams):
            if stream is not None:
                self._streams[index] = None
                raw, decoded = stream
                try:
                    decoded.close()
                finally:
                    raw.close()

    def _reader(self, index, stack):
        if not self.compressed[index]:
            return stack.enter_context(self.paths[index].open("rb"))
        if self._streams[index] is None:
            raw = self.paths[index].open("rb")
            try:
                decoded = gzip.GzipFile(fileobj=raw, mode="rb")
            except BaseException:
                raw.close()
                raise
            self._streams[index] = raw, decoded
        return self._streams[index][1]

    def read(self, cursor):
        try:
            return self._read(cursor)
        except BaseException:
            self.close()
            raise

    def _read(self, cursor):
        if cursor == "0":
            offsets = [0, 0]
        elif isinstance(cursor, str) and re.fullmatch(r"(0|[1-9][0-9]{0,23}):(0|[1-9][0-9]{0,23})", cursor):
            offsets = [int(part) for part in cursor.split(":")]
        else:
            raise ScanError("INVALID_CANONICAL_CURSOR")
        rows, consumed = [], 0
        with ExitStack() as stack:
            handles = []
            for index, (path, expected, descriptor_expected, offset, size) in enumerate(zip(
                    self.paths, self.signatures, self.descriptor_signatures, offsets, self.decoded_sizes)):
                handle = self._reader(index, stack)
                if (_signature(path.stat()) != expected or _signature(os.fstat(handle.fileno())) != descriptor_expected
                        or offset > size):
                    raise ScanError("FIXTURE_CHANGED_OR_CURSOR_OUTSIDE")
                # A retained gzip reader already ends at the previous page's line
                # boundary. Do not rewind one byte and decompress from zero per page.
                if handle.tell() != offset:
                    if offset:
                        handle.seek(offset - 1)
                        if handle.read(1) != b"\n":
                            raise ScanError("CURSOR_NOT_LINE_BOUNDARY")
                    else:
                        handle.seek(0)
                handles.append(handle)
            while len(rows) < self.page_size:
                # Leave room for two maximum-size lines before reading. Rolling a
                # gzip reader back after overfilling a page would rescan the prefix.
                if rows and consumed + 2 * MAX_LINE_BYTES > MAX_PAGE_BYTES // 3:
                    break
                basic, basic_raw = _line(handles[0])
                full, full_raw = _line(handles[1])
                if bool(basic_raw) != bool(full_raw):
                    raise ScanError("CANONICAL_STREAM_LENGTH_MISMATCH")
                if not basic_raw:
                    break
                validate_profile(full)
                if (not isinstance(basic, dict) or set(basic) != BASIC or basic != basic_record(full)
                        or any(type(basic[key]) is not type(full[key]) for key in BASIC)):
                    raise ScanError("CANONICAL_STREAM_CONTENT_MISMATCH")
                rows.append(full)
                consumed += len(basic_raw) + len(full_raw)
            final_positions = [h.tell() for h in handles]
            ended = [position == size for position, size in zip(final_positions, self.decoded_sizes)]
            if ended[0] != ended[1]:
                raise ScanError("CANONICAL_STREAM_LENGTH_MISMATCH")
            for path, handle, expected, descriptor_expected in zip(
                    self.paths, handles, self.signatures, self.descriptor_signatures):
                if _signature(path.stat()) != expected or _signature(os.fstat(handle.fileno())) != descriptor_expected:
                    raise ScanError("FIXTURE_CHANGED")
        if not rows and cursor == "0":
            raise ScanError("EMPTY_CANONICAL_POPULATION")
        if not rows and not all(ended):
            raise ScanError("CANONICAL_PAGE_CANNOT_ADVANCE")
        next_cursor = None if all(ended) else ":".join(map(str, final_positions))
        if all(ended):
            self.close()
        return rows, next_cursor


class CanonicalScanner:
    def __init__(self, database, pair):
        self.pair = pair
        try:
            self.core = Scanner(database, **pair.binding)
        except BaseException:
            pair.close()
            raise
        self.db = self.core.db
        try:
            exists = self.db.execute(
                "SELECT 1 FROM sqlite_master WHERE name='canonical_context' AND type='table'").fetchone()
            if not exists and self.db.execute("SELECT count(*) FROM objects").fetchone()[0]:
                raise ScanError("NON_CANONICAL_INDEX")
            self.db.execute("BEGIN IMMEDIATE")
            self.db.execute("CREATE TABLE IF NOT EXISTS canonical_context (format_version INTEGER NOT NULL)")
            if not exists:
                self.db.execute("INSERT INTO canonical_context VALUES(1)")
            if [tuple(row) for row in self.db.execute("SELECT format_version FROM canonical_context")] != [(1,)]:
                raise ScanError("UNSUPPORTED_CANONICAL_INDEX")
            self.db.execute("CREATE TABLE IF NOT EXISTS canonical_profiles "
                            "(object_id TEXT PRIMARY KEY, modified_at TEXT NOT NULL)")
            self.db.execute("CREATE TABLE IF NOT EXISTS canonical_events "
                            "(sequence INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL, digest TEXT NOT NULL)")
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            self.core.close()
            pair.close()
            raise

    def close(self):
        try:
            self.core.close()
        finally:
            self.pair.close()

    def _normalise(self, row, pending):
        validate_profile(row)
        parent_path = row["path"].rpartition("/")[0]
        if not parent_path:
            parent_id = ANCHOR
        elif parent_path in pending:
            parent_id = pending[parent_path]
        else:
            parent = self.db.execute(
                "SELECT object_id FROM objects WHERE path=? AND is_directory=1 AND deleted=0",
                ("/" + parent_path,)).fetchone()
            if parent is None:
                raise ScanError("CANONICAL_PARENT_MISSING")
            parent_id = parent[0]
        if row["kind"] == "directory":
            pending[row["path"]] = row["objectId"]
        return {"objectId": row["objectId"], "parentId": parent_id, "name": row["name"],
                "path": "/" + row["path"], "isDirectory": row["kind"] == "directory",
                "sizeBytes": row["fileSizeBytes"], "versionId": row["versionId"]}

    def apply_next(self):
        state = self.core.state()
        if state["complete"]:
            raise ScanError("SCAN_ALREADY_COMPLETE")
        cursor = state["cursor"]
        rows, next_cursor = self.pair.read(cursor)
        pending, normalised = {}, []
        if cursor == "0":
            normalised.append({"objectId": ANCHOR, "parentId": None, "name": "", "path": "/",
                               "isDirectory": True, "sizeBytes": 0, "versionId": "anchor-v1"})
        for row in rows:
            normalised.append(self._normalise(row, pending))
        page = {"sourceId": self.pair.binding["source_id"], "fixtureSha256": self.pair.shas[0],
                "snapshotVersion": self.pair.binding["snapshot_version"], "cursor": cursor,
                "nextCursor": next_cursor, "records": normalised}
        self.db.execute("BEGIN IMMEDIATE")
        try:
            self.core.apply_page(page)
            for row in rows:
                self.db.execute("INSERT INTO canonical_profiles VALUES(?,?)",
                                (row["objectId"], row["modifiedAt"]))
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise
        return rows

    def apply_events(self, batch):
        if (not isinstance(batch, dict) or set(batch) != {"sourceId", "baselineSha256", "events", "profiles"}
                or batch["sourceId"] != self.pair.binding["source_id"] or batch["baselineSha256"] != self.pair.shas[0]):
            raise ScanError("CANONICAL_CHANGE_BINDING_MISMATCH")
        events, profiles = batch["events"], batch["profiles"]
        if (not isinstance(events, list) or not 0 < len(events) <= MAX_PAGE_RECORDS
                or not isinstance(profiles, list) or len(profiles) > MAX_PAGE_RECORDS
                or len(canonical(batch).encode()) > MAX_PAGE_BYTES):
            raise ScanError("INVALID_CANONICAL_CHANGE_BATCH")
        metadata = {}
        for row in profiles:
            validate_profile(row)
            key = row["objectId"], row["versionId"]
            if key in metadata:
                raise ScanError("DUPLICATE_CHANGE_PROFILE")
            metadata[key] = row
        needed = set()
        for event in events:
            if not isinstance(event, dict) or set(event) != EVENT:
                raise ScanError("INVALID_CANONICAL_EVENT_FIELDS")
            for field in ("eventId", "objectId", "beforeVersion", "afterVersion"):
                text(event[field], field.upper())
            natural(event["sequence"], "SEQUENCE", 2**63-1)
            if event["sequence"] == 0 or event["objectId"] == ANCHOR:
                raise ScanError("INVALID_CANONICAL_EVENT")
            operation, before, after = event["operation"], event["beforeVersion"], event["afterVersion"]
            valid = (before == ABSENT and after != ABSENT if operation == "create" else
                     before != ABSENT and after == ABSENT if operation == "delete" else
                     before != ABSENT and after != ABSENT and before != after if operation == "update" else False)
            if not valid:
                raise ScanError("INVALID_CANONICAL_VERSION_TRANSITION")
            if operation != "delete":
                needed.add((event["objectId"], after))
        if needed != set(metadata):
            raise ScanError("CANONICAL_CHANGE_PROFILES_MISMATCH")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if not self.core.state()["complete"]:
                raise ScanError("INCOMPLETE_INITIAL_SCAN")
            for event in events:
                profile = metadata.get((event["objectId"], event["afterVersion"]))
                digest = hashlib.sha256(canonical({"event": event, "profile": profile}).encode()).hexdigest()
                old = self.db.execute("SELECT * FROM canonical_events WHERE sequence=?", (event["sequence"],)).fetchone()
                if old:
                    if old["event_id"] != event["eventId"] or old["digest"] != digest:
                        raise ScanError("CONFLICTING_CANONICAL_REPLAY")
                    continue
                actual = self.db.execute(
                    "SELECT version_id FROM objects WHERE object_id=? AND deleted=0", (event["objectId"],)).fetchone()
                if (actual[0] if actual else ABSENT) != event["beforeVersion"]:
                    raise ScanError("CANONICAL_BEFORE_VERSION_MISMATCH")
                internal = {"sequence": event["sequence"], "operation": event["operation"],
                            "fromVersion": self.core.state()["current_version"],
                            "toVersion": "change:" + str(event["sequence"]) + ":" + digest[:16]}
                internal.update({"record": self._normalise(profile, {})} if profile is not None
                                else {"objectId": event["objectId"]})
                self.core.apply_changes({"sourceId": batch["sourceId"], "fixtureSha256": self.pair.shas[0],
                                         "events": [internal]})
                if profile is not None:
                    self.db.execute("INSERT INTO canonical_profiles VALUES(?,?) "
                                    "ON CONFLICT(object_id) DO UPDATE SET modified_at=excluded.modified_at",
                                    (profile["objectId"], profile["modifiedAt"]))
                self.db.execute("INSERT INTO canonical_events VALUES(?,?,?)",
                                (event["sequence"], event["eventId"], digest))
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise

    def profile(self):
        result = dict(self.db.execute(
            "SELECT count(*) object_count, coalesce(sum(is_directory=0),0) file_count, "
            "coalesce(sum(is_directory=1),0) directory_count, "
            "coalesce(max(depth),0) object_depth_max, "
            "coalesce(max(CASE WHEN is_directory=1 THEN depth END),0) directory_depth_max, "
            "coalesce(sum(CASE WHEN is_directory=0 THEN size_bytes END),0) declared_file_bytes "
            "FROM objects WHERE deleted=0 AND object_id<>?", (ANCHOR,)).fetchone())
        result["average_file_size"] = result["declared_file_bytes"] / result["file_count"] if result["file_count"] else 0
        return {**result, "anchorExcluded": True, "declaredSizesOnly": True, "complete": bool(self.core.state()["complete"])}

    def export(self, basic_path, profiled_path, versions_path):
        """Read the complete accepted catalogue; no generator/expected-event shortcut."""
        if not self.core.state()["complete"]:
            raise ScanError("INCOMPLETE_INITIAL_SCAN")
        self.db.execute("BEGIN")
        count = 0
        try:
            if self.db.execute("SELECT 1 FROM objects o LEFT JOIN canonical_profiles p "
                               "ON p.object_id=o.object_id WHERE o.deleted=0 AND o.object_id<>? "
                               "AND p.object_id IS NULL LIMIT 1", (ANCHOR,)).fetchone():
                raise ScanError("MISSING_CANONICAL_PROFILE")
            with ExitStack() as stack:
                outputs = []
                for path in (basic_path, profiled_path, versions_path):
                    path = Path(path)
                    raw = stack.enter_context(path.open("xb"))
                    outputs.append(stack.enter_context(gzip.GzipFile(
                        filename="", fileobj=raw, mode="wb", compresslevel=6, mtime=0))
                        if path.name.endswith(".jsonl.gz") else raw)
                rows = self.db.execute(
                    "SELECT o.*,p.modified_at FROM objects o JOIN canonical_profiles p "
                    "ON p.object_id=o.object_id WHERE o.deleted=0 AND o.object_id<>? ORDER BY o.depth,o.object_id", (ANCHOR,))
                for row in rows:
                    profile = {"objectId": row["object_id"], "kind": "directory" if row["is_directory"] else "file",
                               "versionId": row["version_id"], "depth": row["depth"], "fileSizeBytes": row["size_bytes"],
                               "name": row["name"], "path": row["path"][1:], "modifiedAt": row["modified_at"]}
                    validate_profile(profile)
                    values = (basic_record(profile), profile, {"objectId": row["object_id"], "versionId": row["version_id"]})
                    for handle, value in zip(outputs, values):
                        handle.write((canonical(value) + "\n").encode())
                    count += 1
            self.db.execute("COMMIT")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK")
            raise
        return count


def generate_canonical(baseline, profiled, *, file_count, directory_count, maximum_depth, seed=20261015):
    """Prepare canonical inputs. Anchor is not an enumerated object; sizes are declared only."""
    natural(file_count, "FILE_COUNT", 1000000)
    natural(directory_count, "DIRECTORY_COUNT", 1000000)
    natural(maximum_depth, "DEPTH", 64)
    natural(seed, "SEED", 2**31-1)
    if not file_count or not maximum_depth or directory_count < maximum_depth:
        raise ScanError("UNACHIEVABLE_CANONICAL_POPULATION")
    directories = [{"objectId": ANCHOR, "path": "", "depth": 0}]
    eligible = list(directories)
    with Path(baseline).open("xb") as basic_out, Path(profiled).open("xb") as profile_out:
        def emit(row):
            validate_profile(row)
            basic_out.write((canonical(basic_record(row))+"\n").encode())
            profile_out.write((canonical(row)+"\n").encode())
        for number in range(1, directory_count+1):
            parent = directories[number-1] if number <= maximum_depth else eligible[(number*48271+seed)%len(eligible)]
            name = f"目录-{number:09d}"
            row = {"objectId": f"d-{number:09d}", "kind": "directory", "versionId": "v1",
                   "depth": parent["depth"]+1, "fileSizeBytes": 0, "name": name,
                   "path": parent["path"]+("/" if parent["path"] else "")+name,
                   "modifiedAt": "2026-01-01T00:00:00Z"}
            emit(row)
            directories.append(row)
            if row["depth"] < maximum_depth:
                eligible.append(row)
        for number in range(file_count):
            parent = eligible[(number*48271+seed)%len(eligible)]
            names = (f"clip-{number}.mp4", f"视频-{number}.mkv", f"mix混合-{number}.webm",
                     f"with space {number}.mov", "long-"+"x"*180+f"-{number}.mp4",
                     f".hidden-{number}", f"noextension-{number}", f"archive-{number}.tar.gz")
            name = names[number%len(names)]
            emit({"objectId": f"f-{number:09d}", "kind": "file", "versionId": "v1",
                  "depth": parent["depth"]+1, "fileSizeBytes": (0,1024,2048,4096)[number%4],
                  "name": name, "path": parent["path"]+("/" if parent["path"] else "")+name,
                  "modifiedAt": "2026-01-01T00:00:00Z"})
    return {"baselineSha256": file_sha256(baseline), "profiledSha256": file_sha256(profiled),
            "fileCount": file_count, "directoryCount": directory_count, "maximumDepth": maximum_depth,
            "anchorExcluded": True, "declaredSizesOnly": True, "productionRepresentative": False}
