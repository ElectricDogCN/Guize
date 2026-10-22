"""Read-only, bounded observations of the owned loopback OpenList DAV sandbox."""
from __future__ import annotations

import base64
import hashlib
import http.client
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

MAX_BODY_BYTES = 4 * 1024 * 1024
MAX_DIRECTORY_ENTRIES = 10000
DAV = "{DAV:}"
PROPERTIES = ("resourcetype", "getcontentlength", "getetag", "getlastmodified",
              "resource-id", "sync-token")
PROPFIND_BODY = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<d:propfind xmlns:d="DAV:"><d:prop>'
    + "".join("<d:" + name + "/>" for name in PROPERTIES)
    + "</d:prop></d:propfind>"
).encode()
RESPONSE_HEADERS = (
    "Content-Type", "Content-Length", "Content-Range", "Content-Encoding",
    "ETag", "Last-Modified", "Accept-Ranges", "Retry-After",
)
REQUEST_HEADERS = {"Range", "If-Range", "If-Match", "If-None-Match"}


class SourceError(ValueError):
    def __init__(self, code, observation=None):
        self.code, self.observation = code, observation
        super().__init__(code)


def _segments(locator):
    if not isinstance(locator, str) or len(locator.encode("utf-8")) > 16384:
        raise SourceError("INVALID_LOCATOR")
    if (locator.startswith("/") or "\\" in locator or any(ord(c) < 32 or ord(c) == 127 for c in locator)):
        raise SourceError("UNSAFE_LOCATOR")
    parts = locator.rstrip("/").split("/") if locator.rstrip("/") else []
    if any(not part or part in (".", "..") for part in parts):
        raise SourceError("UNSAFE_LOCATOR")
    return parts


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class OpenListSource:
    """No mutation, proxy, remote origin, redirect, or persistent credentials."""
    def __init__(self, base_url, *, username=None, password=None, timeout=5.0):
        if (not isinstance(base_url, str) or base_url.startswith(" ")
                or any(ord(c) < 32 or ord(c) == 127 for c in base_url)):
            raise SourceError("INVALID_BASE_URL")
        try:
            parsed = urllib.parse.urlsplit(base_url)
            port = parsed.port
        except (ValueError, TypeError):
            raise SourceError("INVALID_BASE_URL") from None
        if (parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not port
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or not parsed.path.startswith("/dav/")
                or not parsed.path.endswith("/") or "%" in parsed.path):
            raise SourceError("LOOPBACK_DAV_PREFIX_REQUIRED")
        _segments(parsed.path[1:])
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 30:
            raise SourceError("INVALID_SOCKET_TIMEOUT")
        self.base = urllib.parse.urlunsplit(parsed)
        self.origin = parsed.scheme, parsed.hostname, port
        self.prefix = parsed.path
        self.timeout = float(timeout)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
        self._authorization = None
        if username is not None or password is not None:
            if (not isinstance(username, str) or not username or ":" in username
                    or not isinstance(password, str) or not password
                    or any(ord(c) < 32 for c in username + password)):
                raise SourceError("INVALID_CREDENTIAL_INPUT")
            self._authorization = "Basic " + base64.b64encode(
                (username + ":" + password).encode("utf-8")).decode("ascii")

    def _url(self, locator, directory=False):
        parts = _segments(locator)
        path = "/".join(urllib.parse.quote(part, safe="") for part in parts)
        return self.base + path + ("/" if directory and path else "")

    def observe(self, method, locator="", *, maximum_bytes, headers=None):
        if method not in ("PROPFIND", "HEAD", "GET"):
            raise SourceError("READ_ONLY_METHOD_REQUIRED")
        if type(maximum_bytes) is not int or not 0 < maximum_bytes <= MAX_BODY_BYTES:
            raise SourceError("INVALID_RESPONSE_LIMIT")
        supplied = {} if headers is None else headers
        if (not isinstance(supplied, dict) or not set(supplied).issubset(REQUEST_HEADERS)
                or (method == "PROPFIND" and supplied)):
            raise SourceError("UNSUPPORTED_REQUEST_HEADERS")
        for value in supplied.values():
            if not isinstance(value, str) or len(value) > 1024 or any(ord(c) < 32 for c in value):
                raise SourceError("INVALID_REQUEST_HEADER")
        url = self._url(locator, method == "PROPFIND")
        request_headers = {**supplied, "Accept-Encoding": "identity",
                           "User-Agent": "Guize-POC005-read-only"}
        if self._authorization is not None:
            request_headers["Authorization"] = self._authorization
        if method == "PROPFIND":
            request_headers.update(Depth="1", **{"Content-Type": "application/xml; charset=utf-8"})
        clock_info = time.get_clock_info("perf_counter")
        if not clock_info.monotonic:
            raise SourceError("MONOTONIC_CLOCK_REQUIRED")
        started = time.perf_counter_ns()
        observation = {
            "method": method, "locator": "/".join(_segments(locator)),
            "startedAt": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "monotonicStartNs": started, "clock": "time.perf_counter_ns",
            "clockImplementation": clock_info.implementation,
            "clockResolutionSeconds": clock_info.resolution, "socketTimeoutSeconds": self.timeout,
            "maximumBodyBytes": maximum_bytes, "requestHeaders": dict(supplied),
            "status": None, "headers": {}, "body": b"", "bodyComplete": False,
        }
        if method == "PROPFIND":
            observation["requestHeaders"]["Depth"] = "1"
        try:
            request = urllib.request.Request(
                url, data=PROPFIND_BODY if method == "PROPFIND" else None,
                method=method, headers=request_headers)
            try:
                response = self.opener.open(request, timeout=self.timeout)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                observation["status"] = response.status
                for name in RESPONSE_HEADERS:
                    values = response.headers.get_all(name, [])
                    if len(values) > 1:
                        raise SourceError("AMBIGUOUS_RESPONSE_HEADER")
                    if values:
                        observation["headers"][name.lower()] = values[0]
                if 300 <= response.status < 400 and response.status != 304:
                    raise SourceError("REDIRECT_REJECTED")
                encoding = observation["headers"].get("content-encoding", "identity")
                if encoding.lower() != "identity":
                    raise SourceError("ENCODED_BODY_UNSUPPORTED")
                length = observation["headers"].get("content-length")
                body_expected = method != "HEAD" and response.status not in (204, 304)
                if length is not None:
                    if not re.fullmatch(r"[0-9]+", length):
                        raise SourceError("INVALID_CONTENT_LENGTH")
                    if body_expected and int(length) > maximum_bytes:
                        raise SourceError("RESPONSE_BODY_LIMIT")
                chunks, received = [], 0
                if body_expected:
                    while True:
                        chunk = response.read1(min(65536, maximum_bytes + 1 - received))
                        if not chunk:
                            break
                        chunks.append(chunk)
                        received += len(chunk)
                        observation["body"] = b"".join(chunks)
                        if received > maximum_bytes:
                            raise SourceError("RESPONSE_BODY_LIMIT")
                    if length is not None and received != int(length):
                        raise SourceError("TRUNCATED_RESPONSE")
                observation["bodyComplete"] = True
        except SourceError as error:
            error.observation = observation
            observation["error"] = error.code
            raise
        except (OSError, urllib.error.URLError, http.client.HTTPException, ValueError):
            observation["error"] = "SOURCE_TRANSPORT_FAILURE"
            raise SourceError("SOURCE_TRANSPORT_FAILURE", observation) from None
        finally:
            observation["endedAt"] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
            observation["monotonicEndNs"] = time.perf_counter_ns()
            observation["elapsedNs"] = observation["monotonicEndNs"] - started
            observation["bodyBytes"] = len(observation["body"])
            observation["bodySha256"] = hashlib.sha256(observation["body"]).hexdigest()
        return observation

    def _href(self, href):
        if (not isinstance(href, str) or not href or href.startswith(" ")
                or any(ord(c) < 32 or ord(c) == 127 for c in href)):
            raise SourceError("INVALID_DAV_HREF")
        try:
            url = urllib.parse.urlsplit(href)
            if url.query or url.fragment or url.username is not None or url.password is not None:
                raise SourceError("UNSAFE_DAV_HREF")
            if url.scheme or url.netloc:
                if (url.scheme, url.hostname, url.port) != self.origin:
                    raise SourceError("CROSS_ORIGIN_DAV_HREF")
            if (not url.path.startswith("/") or re.search(r"%(2f|5c)", url.path, re.I)
                    or re.search(r"%(?![0-9a-fA-F]{2})", url.path)):
                raise SourceError("UNSAFE_DAV_HREF")
            path = urllib.parse.unquote(url.path, encoding="utf-8", errors="strict")
            if not path.startswith(self.prefix):
                raise SourceError("OUTSIDE_DAV_PREFIX")
            relative = path[len(self.prefix):].rstrip("/")
            return "/".join(_segments(relative))
        except SourceError:
            raise
        except (ValueError, UnicodeError):
            raise SourceError("INVALID_DAV_HREF") from None

    def directory_entries(self, observation):
        """Parse actual DAV metadata; locators are deliberately not object IDs."""
        try:
            if observation["method"] != "PROPFIND" or observation["status"] != 207 or not observation["bodyComplete"]:
                raise SourceError("DAV_MULTISTATUS_REQUIRED")
            raw = observation["body"]
            if len(raw) > MAX_BODY_BYTES:
                raise SourceError("DAV_BODY_LIMIT")
            xml = raw.decode("utf-8-sig", errors="strict")
            if "\x00" in xml or re.search(r"<!\s*(DOCTYPE|ENTITY)\b", xml, re.I):
                raise SourceError("XML_DTD_OR_ENTITY_REJECTED")
            root = ET.fromstring(xml)
            if root.tag != DAV + "multistatus":
                raise SourceError("DAV_MULTISTATUS_REQUIRED")
            responses = root.findall(DAV + "response")
            if not responses or len(responses) > MAX_DIRECTORY_ENTRIES:
                raise SourceError("DAV_ENTRY_LIMIT")
            directory, found_self, seen, entries = observation["locator"], False, set(), []
            for response in responses:
                hrefs = response.findall(DAV + "href")
                if len(hrefs) != 1:
                    raise SourceError("DAV_HREF_REQUIRED")
                locator = self._href(hrefs[0].text)
                if locator in seen:
                    raise SourceError("DUPLICATE_DAV_LOCATOR")
                seen.add(locator)
                if locator != directory and locator.rpartition("/")[0] != directory:
                    raise SourceError("NOT_IMMEDIATE_DAV_CHILD")
                properties, unavailable = {}, []
                if response.find(DAV + "status") is not None:
                    raise SourceError("DAV_RESOURCE_STATUS_FAILURE")
                for propstat in response.findall(DAV + "propstat"):
                    status = (propstat.findtext(DAV + "status") or "").split()
                    props = propstat.find(DAV + "prop")
                    if len(status) < 2 or not status[1].isdigit() or props is None:
                        raise SourceError("INVALID_DAV_PROPSTAT")
                    code = int(status[1])
                    for prop in props:
                        if prop.tag not in {DAV + name for name in PROPERTIES}:
                            continue
                        name = prop.tag[len(DAV):]
                        if name in properties or name in unavailable:
                            raise SourceError("DUPLICATE_DAV_PROPERTY")
                        if code == 200:
                            properties[name] = prop
                        elif code == 404 and name != "resourcetype":
                            unavailable.append(name)
                        else:
                            raise SourceError("DAV_REQUIRED_PROPERTY_OR_PERMISSION_FAILURE")
                if "resourcetype" not in properties:
                    raise SourceError("DAV_RESOURCE_TYPE_REQUIRED")
                directory_type = properties["resourcetype"].find(DAV + "collection") is not None
                if locator == directory:
                    if not directory_type:
                        raise SourceError("DAV_SELF_NOT_COLLECTION")
                    found_self = True
                size_element = properties.get("getcontentlength")
                size = size_element.text if size_element is not None else None
                if size is not None and (not re.fullmatch(r"[0-9]+", size) or int(size) > 2**63 - 1):
                    raise SourceError("INVALID_DAV_SIZE")
                def optional(name):
                    element = properties.get(name)
                    return element.text if element is not None else None
                entries.append({"locator": locator, "isDirectory": directory_type,
                                "sizeBytes": int(size) if size is not None else None,
                                "etag": optional("getetag"), "lastModified": optional("getlastmodified"),
                                "unavailableProperties": unavailable,
                                "omittedProperties": sorted(set(PROPERTIES) - set(properties) - set(unavailable)),
                                "providerResourceId": (properties["resource-id"].findtext(DAV + "href")
                                                       if "resource-id" in properties else None),
                                "syncToken": optional("sync-token"), "stableObjectId": None})
            if not found_self:
                raise SourceError("DAV_SELF_COLLECTION_MISSING")
            return {"entries": entries, "stableObjectIdentityValidated": False,
                    "resourceIdPropertyExposed": any(e["providerResourceId"] for e in entries),
                    "syncTokenPropertyExposed": any(e["syncToken"] for e in entries),
                    "snapshotConsistencyValidated": False, "changeJournalProbed": False,
                    "listingMode": "DAV_DEPTH_1", "paginationImplemented": False,
                    "sourcePaginationProbed": False}
        except SourceError as error:
            error.observation = observation
            raise
        except (ValueError, KeyError, UnicodeError, ET.ParseError, TypeError):
            raise SourceError("INVALID_DAV_RESPONSE", observation) from None
