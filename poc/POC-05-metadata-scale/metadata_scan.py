"""Bounded synthetic source and transactional POC index. No platform asset writes."""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
from pathlib import Path

MAX_LINE_BYTES = 65536
MAX_PAGE_RECORDS = 1000
MAX_PAGE_BYTES = 4 * 1024 * 1024
FIELDS = {"objectId", "parentId", "name", "path", "isDirectory", "sizeBytes", "versionId"}


class ScanError(ValueError):
    """Invalid or inconsistent POC input; the checkpoint must not advance."""


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def natural(value, label, maximum=None):
    if type(value) is not int or value < 0 or (maximum is not None and value > maximum):
        raise ScanError("INVALID_" + label)
    return value


def text(value, label, limit=256, empty=False):
    if not isinstance(value, str) or (not empty and not value) or "\x00" in value:
        raise ScanError("INVALID_" + label)
    try:
        length = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise ScanError("INVALID_" + label) from exc
    if length > limit:
        raise ScanError("OVERSIZED_" + label)
    return value


def validate_record(record):
    if not isinstance(record, dict) or set(record) != FIELDS:
        raise ScanError("INVALID_RECORD_FIELDS")
    text(record["objectId"], "OBJECT_ID")
    text(record["versionId"], "VERSION_ID")
    text(record["name"], "NAME", 4096, empty=True)
    text(record["path"], "PATH", 16384)
    if record["parentId"] is not None:
        text(record["parentId"], "PARENT_ID")
    if type(record["isDirectory"]) is not bool:
        raise ScanError("INVALID_DIRECTORY_FLAG")
    natural(record["sizeBytes"], "SIZE", 2**63 - 1)
    if record["isDirectory"] and record["sizeBytes"] != 0:
        raise ScanError("DIRECTORY_HAS_SIZE")
    if any(c in record["name"] for c in ("/", "\\")) or record["name"] in (".", ".."):
        raise ScanError("INVALID_NAME")
    if record["parentId"] is None:
        if not record["isDirectory"] or record["name"] != "" or record["path"] != "/":
            raise ScanError("INVALID_ROOT")
    elif not record["name"]:
        raise ScanError("EMPTY_CHILD_NAME")


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_fixture(path, *, file_count, directory_count, maximum_depth, seed=20261015):
    """Prepare immutable JSONL; returned counts are not scan measurements."""
    natural(file_count, "FILE_COUNT", 1000000)
    natural(directory_count, "DIRECTORY_COUNT", 1000000)
    natural(maximum_depth, "DEPTH", 64)
    natural(seed, "SEED", 2**31 - 1)
    if directory_count < maximum_depth + 1 or (maximum_depth == 0 and directory_count != 1):
        raise ScanError("UNACHIEVABLE_DIRECTORY_DEPTH")
    directories = []
    eligible = []
    with Path(path).open("xb") as handle:
        def emit(record):
            validate_record(record)
            row = (canonical(record) + "\n").encode("utf-8")
            if len(row) > MAX_LINE_BYTES:
                raise ScanError("OVERSIZED_LINE")
            handle.write(row)
        for number in range(directory_count):
            object_id = f"d-{number:09d}"
            if number == 0:
                parent, depth, name, locator = None, 0, "", "/"
            else:
                parent = directories[number - 1] if number <= maximum_depth else eligible[
                    (number * 48271 + seed) % len(eligible)]
                depth, name = parent["depth"] + 1, f"目录-{number:09d}"
                locator = parent["path"].rstrip("/") + "/" + name
            record = {"objectId": object_id, "parentId": parent["objectId"] if parent else None,
                      "name": name, "path": locator, "isDirectory": True,
                      "sizeBytes": 0, "versionId": object_id + "-v1"}
            emit(record)
            item = {**record, "depth": depth}
            directories.append(item)
            if depth < maximum_depth:
                eligible.append(item)
        for number in range(file_count):
            parent = directories[(number * 48271 + seed) % len(directories)]
            names = (f"clip-{number}.mp4", f"视频-{number}.mkv", f"mix混合-{number}.webm",
                     f"with space {number}.mov", "long-" + "x" * 180 + f"-{number}.mp4",
                     f".hidden-{number}", f"noextension-{number}", f"archive-{number}.tar.gz")
            object_id, name = f"f-{number:09d}", names[number % len(names)]
            emit({"objectId": object_id, "parentId": parent["objectId"], "name": name,
                  "path": parent["path"].rstrip("/") + "/" + name, "isDirectory": False,
                  "sizeBytes": (number * 104729 + seed) % 1048576 + 1,
                  "versionId": object_id + "-v1"})
    return {"fixtureSha256": file_sha256(path), "bytes": Path(path).stat().st_size,
            "fileCount": file_count, "directoryCount": directory_count,
            "maximumDepth": maximum_depth, "seed": seed,
            "declaredSizesOnly": True, "productionRepresentative": False}


class JsonlSource:
    """Read at most one bounded page; cursors belong to exact approved bytes."""
    def __init__(self, path, *, source_id, snapshot_version, fixture_sha256, page_size=200):
        text(source_id, "SOURCE_ID")
        text(snapshot_version, "SNAPSHOT_VERSION")
        if (not isinstance(fixture_sha256, str) or len(fixture_sha256) != 64
                or any(c not in "0123456789abcdef" for c in fixture_sha256)):
            raise ScanError("INVALID_FIXTURE_SHA256")
        natural(page_size, "PAGE_SIZE", MAX_PAGE_RECORDS)
        if page_size == 0:
            raise ScanError("EMPTY_PAGE_SIZE")
        self.path, self.source_id, self.version = Path(path), source_id, snapshot_version
        self.sha, self.page_size = fixture_sha256, page_size
        before = self.signature()
        if file_sha256(self.path) != self.sha or before != self.signature():
            raise ScanError("FIXTURE_DIGEST_MISMATCH")
        self.identity = before

    def signature(self):
        value = self.path.stat()
        return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns

    def page(self, cursor):
        if (not isinstance(cursor, str) or len(cursor) > 24 or not cursor.isascii()
                or not cursor.isdecimal() or str(int(cursor)) != cursor):
            raise ScanError("INVALID_CURSOR")
        offset = int(cursor)
        if self.signature() != self.identity or offset > self.identity[2]:
            raise ScanError("FIXTURE_CHANGED_OR_CURSOR_OUTSIDE")
        records, consumed = [], 0
        with self.path.open("rb") as handle:
            if offset:
                handle.seek(offset - 1)
                if handle.read(1) != b"\n":
                    raise ScanError("CURSOR_NOT_LINE_BOUNDARY")
            handle.seek(offset)
            while len(records) < self.page_size:
                line = handle.readline(MAX_LINE_BYTES + 1)
                if not line:
                    break
                if len(line) > MAX_LINE_BYTES or not line.endswith(b"\n"):
                    raise ScanError("OVERSIZED_OR_UNTERMINATED_LINE")
                if consumed + len(line) > MAX_PAGE_BYTES - 1024:
                    handle.seek(-len(line), 1)
                    break
                try:
                    record = json.loads(line)
                except (ValueError, UnicodeError) as exc:
                    raise ScanError("INVALID_JSONL") from exc
                validate_record(record)
                records.append(record)
                consumed += len(line)
            position = handle.tell()
        if self.signature() != self.identity:
            raise ScanError("FIXTURE_CHANGED")
        return {"sourceId": self.source_id, "snapshotVersion": self.version,
                "fixtureSha256": self.sha, "cursor": cursor,
                "nextCursor": str(position) if position < self.identity[2] else None,
                "records": records}


SCHEMA = """
CREATE TABLE state (
 id INTEGER PRIMARY KEY CHECK(id=1), source_id TEXT NOT NULL, fixture_sha TEXT NOT NULL,
 initial_version TEXT NOT NULL, current_version TEXT NOT NULL, cursor TEXT NOT NULL,
 complete INTEGER NOT NULL DEFAULT 0, sequence INTEGER NOT NULL DEFAULT 0);
CREATE TABLE objects (
 object_id TEXT PRIMARY KEY, parent_id TEXT, name TEXT NOT NULL, path TEXT NOT NULL,
 is_directory INTEGER NOT NULL, size_bytes INTEGER NOT NULL, version_id TEXT NOT NULL,
 depth INTEGER NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
CREATE UNIQUE INDEX live_path ON objects(path) WHERE deleted=0;
CREATE INDEX children ON objects(parent_id, deleted);
CREATE TABLE cursors (cursor TEXT PRIMARY KEY);
CREATE TABLE events (sequence INTEGER PRIMARY KEY, digest TEXT NOT NULL);
PRAGMA user_version=1;
"""


class Scanner:
    def __init__(self, database, *, source_id, fixture_sha256, snapshot_version):
        text(source_id, "SOURCE_ID")
        text(snapshot_version, "SNAPSHOT_VERSION")
        if (not isinstance(fixture_sha256, str) or len(fixture_sha256) != 64
                or any(c not in "0123456789abcdef" for c in fixture_sha256)):
            raise ScanError("INVALID_FIXTURE_SHA256")
        self.binding = source_id, fixture_sha256, snapshot_version
        path = Path(database)
        created = False
        try:
            with path.open("xb"):
                created = True
        except FileExistsError:
            pass
        self.db = sqlite3.connect(str(path), isolation_level=None)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.execute("PRAGMA cache_size=-2048")
            if created:
                self.db.executescript(SCHEMA)
                self.db.execute("INSERT INTO state VALUES (1,?,?,?,?, '0',0,0)",
                                (source_id, fixture_sha256, snapshot_version, snapshot_version))
            if self.db.execute("PRAGMA user_version").fetchone()[0] != 1:
                raise ScanError("UNSUPPORTED_INDEX_VERSION")
            state = self.state()
            if (state["source_id"], state["fixture_sha"], state["initial_version"]) != self.binding:
                raise ScanError("CHECKPOINT_BINDING_MISMATCH")
        except BaseException:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def state(self):
        return dict(self.db.execute("SELECT * FROM state WHERE id=1").fetchone())

    def _shape(self, record):
        validate_record(record)
        if record["parentId"] is None:
            other = self.db.execute(
                "SELECT object_id FROM objects WHERE parent_id IS NULL AND deleted=0 "
                "AND object_id<>?", (record["objectId"],)).fetchone()
            if other:
                raise ScanError("MULTIPLE_ROOTS")
            return 0
        parent = self.db.execute(
            "SELECT * FROM objects WHERE object_id=? AND deleted=0",
            (record["parentId"],)).fetchone()
        if not parent or not parent["is_directory"] or record["parentId"] == record["objectId"]:
            raise ScanError("MISSING_OR_INVALID_PARENT")
        expected = parent["path"].rstrip("/") + "/" + record["name"]
        if record["path"] != expected:
            raise ScanError("PATH_PARENT_MISMATCH")
        return parent["depth"] + 1

    def _store(self, record, update=False):
        depth = self._shape(record)
        values = (record["parentId"], record["name"], record["path"],
                  int(record["isDirectory"]), record["sizeBytes"], record["versionId"],
                  depth, record["objectId"])
        if update:
            self.db.execute("UPDATE objects SET parent_id=?,name=?,path=?,is_directory=?,"
                            "size_bytes=?,version_id=?,depth=?,deleted=0 WHERE object_id=?", values)
        else:
            self.db.execute("INSERT INTO objects(parent_id,name,path,is_directory,size_bytes,"
                            "version_id,depth,object_id) VALUES (?,?,?,?,?,?,?,?)", values)

    def apply_page(self, page):
        fields = {"sourceId", "snapshotVersion", "fixtureSha256", "cursor", "nextCursor", "records"}
        if not isinstance(page, dict) or set(page) != fields:
            raise ScanError("INVALID_PAGE_FIELDS")
        if (page["sourceId"], page["fixtureSha256"], page["snapshotVersion"]) != self.binding:
            raise ScanError("PAGE_BINDING_MISMATCH")
        rows = page["records"]
        if not isinstance(rows, list) or len(rows) > MAX_PAGE_RECORDS:
            raise ScanError("OVERSIZED_PAGE")
        if len(canonical(page).encode("utf-8")) > MAX_PAGE_BYTES:
            raise ScanError("OVERSIZED_PAGE")
        for cursor in (page["cursor"], page["nextCursor"]):
            if cursor is not None:
                text(cursor, "CURSOR", 256)
        if page["cursor"] is None or (not rows and page["nextCursor"] is not None):
            raise ScanError("EMPTY_NONFINAL_PAGE")
        self.db.execute("SAVEPOINT page_apply")
        try:
            state = self.state()
            if state["complete"] or state["cursor"] != page["cursor"]:
                raise ScanError("STALE_OR_COMPLETED_PAGE")
            self.db.execute("INSERT INTO cursors VALUES (?)", (page["cursor"],))
            next_cursor = page["nextCursor"]
            if next_cursor is not None and self.db.execute(
                    "SELECT 1 FROM cursors WHERE cursor=?", (next_cursor,)).fetchone():
                raise ScanError("CURSOR_LOOP")
            for record in rows:
                self._store(record)
            if next_cursor is None and not self.db.execute(
                    "SELECT 1 FROM objects WHERE parent_id IS NULL AND deleted=0").fetchone():
                raise ScanError("MISSING_ROOT")
            self.db.execute("UPDATE state SET cursor=?,complete=? WHERE id=1",
                            (next_cursor or page["cursor"], int(next_cursor is None)))
            self.db.execute("RELEASE page_apply")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK TO page_apply")
                self.db.execute("RELEASE page_apply")
            raise

    def apply_changes(self, batch):
        if (not isinstance(batch, dict) or set(batch) != {"sourceId", "fixtureSha256", "events"}
                or (batch["sourceId"], batch["fixtureSha256"]) != self.binding[:2]):
            raise ScanError("CHANGE_BINDING_MISMATCH")
        events = batch["events"]
        if not isinstance(events, list) or not events or len(events) > MAX_PAGE_RECORDS:
            raise ScanError("INVALID_CHANGE_BATCH")
        if len(canonical(events).encode("utf-8")) > MAX_PAGE_BYTES:
            raise ScanError("OVERSIZED_CHANGE_BATCH")
        self.db.execute("SAVEPOINT changes_apply")
        try:
            if not self.state()["complete"]:
                raise ScanError("INCOMPLETE_INITIAL_SCAN")
            for event in events:
                self._event(event)
            self.db.execute("RELEASE changes_apply")
        except BaseException:
            if self.db.in_transaction:
                self.db.execute("ROLLBACK TO changes_apply")
                self.db.execute("RELEASE changes_apply")
            raise

    def _event(self, event):
        if not isinstance(event, dict):
            raise ScanError("INVALID_EVENT")
        sequence = natural(event.get("sequence"), "SEQUENCE", 2**63 - 1)
        operation = event.get("operation")
        required = {"sequence", "operation", "fromVersion", "toVersion",
                    "objectId" if operation == "delete" else "record"}
        if set(event) != required or operation not in ("create", "update", "delete"):
            raise ScanError("INVALID_EVENT_FIELDS")
        text(event["fromVersion"], "FROM_VERSION")
        text(event["toVersion"], "TO_VERSION")
        if event["fromVersion"] == event["toVersion"]:
            raise ScanError("UNCHANGED_EVENT_VERSION")
        digest = hashlib.sha256(canonical(event).encode("utf-8")).hexdigest()
        previous = self.db.execute("SELECT digest FROM events WHERE sequence=?", (sequence,)).fetchone()
        if previous:
            if previous["digest"] != digest:
                raise ScanError("CONFLICTING_EVENT_REPLAY")
            return
        state = self.state()
        if sequence != state["sequence"] + 1 or event["fromVersion"] != state["current_version"]:
            raise ScanError("EVENT_GAP_OR_VERSION_MISMATCH")
        if operation != "delete":
            validate_record(event["record"])
            object_id = event["record"]["objectId"]
        else:
            object_id = text(event["objectId"], "OBJECT_ID")
        old = self.db.execute("SELECT * FROM objects WHERE object_id=?", (object_id,)).fetchone()
        if operation == "create":
            if old:
                raise ScanError("CREATE_EXISTING_ID")
            self._store(event["record"])
        else:
            if not old or old["deleted"]:
                raise ScanError("CHANGE_MISSING_OBJECT")
            children = self.db.execute(
                "SELECT 1 FROM objects WHERE parent_id=? AND deleted=0 LIMIT 1", (object_id,)).fetchone()
            if operation == "delete":
                if children or old["parent_id"] is None:
                    raise ScanError("DELETE_NONEMPTY_OR_ROOT")
                self.db.execute("UPDATE objects SET deleted=1 WHERE object_id=?", (object_id,))
            else:
                record = event["record"]
                if old["version_id"] == record["versionId"]:
                    raise ScanError("UPDATE_REQUIRES_NEW_OBJECT_VERSION")
                if children and (old["path"] != record["path"] or not record["isDirectory"]):
                    raise ScanError("NONEMPTY_DIRECTORY_MOVE_OR_TYPE_CHANGE")
                if (old["parent_id"] is None) != (record["parentId"] is None):
                    raise ScanError("ROOT_IDENTITY_CHANGE")
                self._store(record, update=True)
        self.db.execute("INSERT INTO events VALUES (?,?)", (sequence, digest))
        self.db.execute("UPDATE state SET sequence=?,current_version=? WHERE id=1",
                        (sequence, event["toVersion"]))

    def profile(self):
        """Compute from persisted accepted rows, never generator declarations."""
        result = dict(self.db.execute(
            "SELECT count(*) object_count, "
            "coalesce(sum(is_directory=0),0) file_count, "
            "coalesce(sum(is_directory=1),0) directory_count, "
            "coalesce(max(CASE WHEN is_directory=1 THEN depth END),0) directory_depth_max, "
            "coalesce(sum(CASE WHEN is_directory=0 THEN size_bytes END),0) declared_file_bytes "
            "FROM objects WHERE deleted=0").fetchone())
        result["average_file_size"] = result["declared_file_bytes"] / result["file_count"] if result["file_count"] else 0
        names = {"ascii": 0, "nonAscii": 0, "spaces": 0, "hidden": 0, "noExtension": 0,
                 "maximumNameCharacters": 0, "maximumNameUtf8Bytes": 0}
        for row in self.db.execute("SELECT name FROM objects WHERE deleted=0 AND parent_id IS NOT NULL"):
            name = row[0]
            names["ascii" if name.isascii() else "nonAscii"] += 1
            names["spaces"] += int(" " in name)
            names["hidden"] += int(name.startswith("."))
            names["noExtension"] += int("." not in name.lstrip("."))
            names["maximumNameCharacters"] = max(names["maximumNameCharacters"], len(name))
            names["maximumNameUtf8Bytes"] = max(names["maximumNameUtf8Bytes"], len(name.encode("utf-8")))
        return {**result, "names": names, "state": self.state(), "declaredSizesOnly": True}


class TransientFailure(Exception):
    def __init__(self, status, retry_after=0.0):
        if status not in (429, 500, 502, 503, 504):
            raise ScanError("NONTRANSIENT_STATUS")
        if type(retry_after) not in (float, int) or not math.isfinite(retry_after) or retry_after < 0:
            raise ScanError("INVALID_RETRY_DELAY")
        self.status, self.retry_after = status, float(retry_after)
        super().__init__("TRANSIENT_SOURCE_FAILURE")


def fetch_with_retry(fetch, cursor, *, observations, attempts=3, maximum_delay=2.0,
                     timeout=15.0, clock=time.monotonic, sleep=time.sleep):
    natural(attempts, "ATTEMPTS", 10)
    if attempts == 0 or any(type(x) not in (int, float) or not math.isfinite(x) or x <= 0
                            for x in (maximum_delay, timeout)):
        raise ScanError("INVALID_RETRY_BUDGET")
    deadline = clock() + timeout
    for attempt in range(1, attempts + 1):
        if clock() >= deadline:
            raise ScanError("RETRY_DEADLINE")
        try:
            page = fetch(cursor)
        except TransientFailure as exc:
            delay = max(0.05 * 2 ** (attempt - 1), exc.retry_after)
            observations.append({"attempt": attempt, "status": exc.status, "delaySeconds": delay})
            if attempt == attempts:
                raise
            if delay > maximum_delay or clock() + delay >= deadline:
                raise ScanError("RETRY_BUDGET_EXCEEDED") from exc
            sleep(delay)
        else:
            if clock() >= deadline:
                raise ScanError("FETCH_EXCEEDED_DEADLINE")
            observations.append({"attempt": attempt, "status": "received"})
            return page
