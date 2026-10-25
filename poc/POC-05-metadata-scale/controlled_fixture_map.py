"""Explicit fixture identities bound to independently parsed provider metadata."""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from canonical_metadata import PROFILE, validate_profile
from metadata_scan import ScanError, canonical, text
from openlist_listing import MAX_OBJECTS, OpenListListing, _decode

FIELDS = ("objectId", "kind", "versionId", "depth", "fileSizeBytes", "name", "path", "modifiedAt")


class ControlledFixtureMap:
    def __init__(self, database, pair, source, *, source_identity):
        if (not isinstance(source, OpenListListing) or not isinstance(source_identity, dict)
                or set(source_identity) != {"adapterId", "adapterBuild", "sourceId", "sourceVersion"}
                or source_identity["sourceId"] != pair.binding["source_id"]):
            raise ScanError("INVALID_CONTROLLED_SOURCE_BINDING")
        for value in source_identity.values():
            text(value, "SOURCE_IDENTITY", 1024)
        self.source, self.identity = source, dict(source_identity)
        self.database = Path(database)
        with self.database.open("xb"):
            pass
        self.db = sqlite3.connect(self.database)
        self.db.row_factory = sqlite3.Row
        try:
            self.db.executescript("""
                PRAGMA temp_store=FILE;
                PRAGMA cache_size=-8192;
                CREATE TABLE context(baselineSha TEXT,profiledSha TEXT,endpoint TEXT,scope TEXT,identity TEXT);
                CREATE TABLE approved(objectId TEXT PRIMARY KEY,kind TEXT NOT NULL,versionId TEXT NOT NULL,
                    depth INTEGER NOT NULL,fileSizeBytes INTEGER NOT NULL,name TEXT NOT NULL,
                    path TEXT UNIQUE NOT NULL,modifiedAt TEXT NOT NULL);
                CREATE TABLE runs(runId TEXT PRIMARY KEY,completed INTEGER NOT NULL,nextCursor TEXT,
                    pages INTEGER NOT NULL,objects INTEGER NOT NULL,lastFinishedAt TEXT);
                CREATE TABLE observed(runId TEXT NOT NULL,objectId TEXT NOT NULL,kind TEXT NOT NULL,
                    versionId TEXT NOT NULL,depth INTEGER NOT NULL,fileSizeBytes INTEGER NOT NULL,
                    name TEXT NOT NULL,path TEXT NOT NULL,modifiedAt TEXT NOT NULL,sourceSizeBytes INTEGER NOT NULL,
                    PRIMARY KEY(runId,objectId),UNIQUE(runId,path));
            """)
            count, cursor = 0, "0"
            with self.db:
                self.db.execute("INSERT INTO context VALUES(?,?,?,?,?)", (
                    *pair.shas, source.endpoint, source.scope, canonical(self.identity)))
                while cursor is not None:
                    rows, cursor = pair.read(cursor)
                    for row in rows:
                        validate_profile(row)
                        parent = row["path"].rpartition("/")[0]
                        if parent and self.db.execute(
                                "SELECT 1 FROM approved WHERE path=? AND kind='directory'", (parent,)).fetchone() is None:
                            raise ScanError("CONTROLLED_PARENT_MISSING")
                        self.db.execute("INSERT INTO approved VALUES(?,?,?,?,?,?,?,?)", tuple(row[k] for k in FIELDS))
                        count += 1
                        if count > MAX_OBJECTS:
                            raise ScanError("CONTROLLED_POPULATION_LIMIT")
            self.count = count
        except BaseException:
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def begin_run(self, run_id):
        text(run_id, "RUN_ID", 256)
        try:
            with self.db:
                self.db.execute("INSERT INTO runs VALUES(?,0,NULL,0,0,NULL)", (run_id,))
        except sqlite3.IntegrityError:
            raise ScanError("CONTROLLED_RUN_ALREADY_EXISTS") from None

    def state(self, run_id):
        row = self.db.execute("SELECT * FROM runs WHERE runId=?", (run_id,)).fetchone()
        if row is None:
            raise ScanError("UNKNOWN_CONTROLLED_RUN")
        return dict(row)

    def _inspect(self, page):
        observation = page["observation"]
        if observation["endpointURL"] != self.source.endpoint or observation["method"] != "POST":
            raise ScanError("CONTROLLED_ENDPOINT_MISMATCH")
        for body, digest, length in (("requestBody", "requestBodySha256", None),
                                     ("body", "bodySha256", "bodyBytes")):
            raw = observation[body]
            if (not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != observation[digest]
                    or length and len(raw) != observation[length]):
                raise ScanError("CONTROLLED_RAW_HASH_MISMATCH")
        directory = observation["directory"]
        expected_request = {"path": "/" + self.source.scope + ("/" + directory if directory else ""),
                            "refresh": False, "page": observation["page"],
                            "per_page": observation["perPage"]}
        actual_request = _decode(observation["requestBody"])
        if canonical(actual_request) != canonical(expected_request):
            raise ScanError("CONTROLLED_REQUEST_MISMATCH")
        total, entries = self.source.parse_page(observation)
        if canonical(entries) != canonical(page["entries"]) or total != page["directoryTotal"]:
            raise ScanError("CONTROLLED_PARSED_PAGE_MISMATCH")
        for key in ("requestCursor", "nextCursor"):
            if page[key] is not None:
                text(page[key], "TRAVERSAL_CURSOR", 32768)
        try:
            provider_time = parsedate_to_datetime(observation["headers"]["date"])
            if provider_time.tzinfo is None:
                raise ValueError()
            provider_at = provider_time.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            first, last = (datetime.fromisoformat(observation[k].replace("Z", "+00:00"))
                           for k in ("startedAt", "endedAt"))
            if (first.tzinfo is None or last.tzinfo is None or first >= last
                    or observation["monotonicEndNs"] <= observation["monotonicStartNs"]):
                raise ValueError()
        except (KeyError, TypeError, ValueError, OverflowError):
            raise ScanError("ACTUAL_PROVIDER_DATE_AND_REQUEST_CLOCK_REQUIRED") from None
        return observation, entries, provider_at, first, last

    def bind_page(self, run_id, page):
        """Only IDs/versions come from approved rows; observed fields remain observed."""
        observation, entries, provider_at, first, last = self._inspect(page)
        state = self.state(run_id)
        if state["completed"] or state["nextCursor"] != page["requestCursor"]:
            raise ScanError("CONTROLLED_CURSOR_OR_TERMINAL_MISMATCH")
        if state["lastFinishedAt"] is not None and first < datetime.fromisoformat(state["lastFinishedAt"]):
            raise ScanError("CONTROLLED_REQUEST_ORDER_MISMATCH")
        profiles = []
        try:
            with self.db:
                for entry in entries:
                    expected = self.db.execute("SELECT * FROM approved WHERE path=?", (entry["locator"],)).fetchone()
                    if expected is None:
                        raise ScanError("UNKNOWN_CONTROLLED_FIXTURE_LOCATOR")
                    profile = dict(objectId=expected["objectId"], versionId=expected["versionId"],
                                   kind=entry["kind"], fileSizeBytes=entry["fileSizeBytes"],
                                   path=entry["locator"], name=entry["locator"].rsplit("/", 1)[-1],
                                   depth=len(entry["locator"].split("/")), modifiedAt=entry["modifiedAt"])
                    validate_profile(profile)
                    if any(type(profile[key]) is not type(expected[key]) or profile[key] != expected[key] for key in PROFILE):
                        raise ScanError("CONTROLLED_OBSERVED_METADATA_MISMATCH")
                    self.db.execute("INSERT INTO observed VALUES(?,?,?,?,?,?,?,?,?,?)", (
                        run_id, *(profile[key] for key in FIELDS), entry["sourceSizeBytes"]))
                    profiles.append(profile)
                observed_count = state["objects"] + len(profiles)
                terminal = page["nextCursor"] is None
                if terminal and (observed_count != self.count or self.db.execute(
                        "SELECT objectId FROM approved EXCEPT SELECT objectId FROM observed WHERE runId=? LIMIT 1",
                        (run_id,)).fetchone() is not None):
                    raise ScanError("INCOMPLETE_CONTROLLED_POPULATION")
                self.db.execute("UPDATE runs SET completed=?,nextCursor=?,pages=pages+1,objects=?,lastFinishedAt=? WHERE runId=?",
                                (int(terminal), page["nextCursor"], observed_count, last.isoformat(), run_id))
        except sqlite3.IntegrityError:
            raise ScanError("DUPLICATE_CONTROLLED_OBSERVATION") from None
        header = dict(runId=run_id, requestId=run_id + "/request/" + str(state["pages"] + 1),
                      sourceIdentity=dict(self.identity), endpointURL=self.source.endpoint,
                      requestedAt=observation["startedAt"], finishedAt=observation["endedAt"],
                      requestCursor=page["requestCursor"], nextCursor=page["nextCursor"],
                      statusCode=observation["status"], providerTimestamp=provider_at)
        return dict(header=header, profiles=profiles, completePopulationMapped=terminal,
                    controlledFixtureIdentity=True, stableProviderIdentityVerified=False)

    def export_observed(self, run_id, path):
        if not self.state(run_id)["completed"]:
            raise ScanError("INCOMPLETE_CONTROLLED_RUN")
        count = 0
        with Path(path).open("xb") as output:
            for row in self.db.execute("SELECT * FROM observed WHERE runId=? ORDER BY depth,objectId", (run_id,)):
                profile = {key: row[key] for key in FIELDS}
                validate_profile(profile)
                output.write((canonical(profile) + "\n").encode())
                count += 1
        if count != self.count:
            raise ScanError("CONTROLLED_OBSERVED_EXPORT_COUNT_MISMATCH")
        return dict(count=count, controlledFixtureIdentity=True, stableProviderIdentityVerified=False)
