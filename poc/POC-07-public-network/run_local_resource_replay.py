"""Validate management and Worker output separately from the playback fixture."""

import argparse
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from hmac import compare_digest
from http.client import HTTPConnection
import json
from pathlib import Path
import secrets
import sys

from resource_gateway import ProtectedResource, resource_gateway

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "POC-03-ats-range"))
from grants import Grant

MAXIMUM_BODY_BYTES = 64 * 1024


def get(port: int, path: str, authorization: str) -> tuple[int, bytes]:
    connection = HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.request("GET", path, headers={"Authorization": authorization})
        response = connection.getresponse()
        body = response.read(MAXIMUM_BODY_BYTES + 1)
        if len(body) > MAXIMUM_BODY_BYTES:
            raise ValueError("Fixture response exceeded its approved capture size")
        return response.status, body
    finally:
        connection.close()


def replay(origin_port: int, origin_auth: dict[str, str], fixture: bytes) -> dict:
    credentials = {role: "Bearer " + secrets.token_urlsafe(24) for role in ("admin", "worker", "reader")}
    now = datetime.now(timezone.utc)
    grant = Grant("local-output-fixture", "worker-fixture", now.isoformat(),
                  (now + timedelta(minutes=2)).isoformat())
    origin_reads = {"management": 0, "worker": 0}

    def read_management() -> bytes:
        origin_reads["management"] += 1
        status, result = get(origin_port, "/api/admin/storage/list", origin_auth["management"])
        document = json.loads(result)
        if status != 200 or not isinstance(document, dict) or document.get("code") != 200:
            raise ValueError("OpenList did not return the authorized management data")
        return result

    def read_output() -> bytes:
        origin_reads["worker"] += 1
        status, result = get(origin_port, "/dav/output.bin", origin_auth["worker"])
        if status != 200 or result != fixture:
            raise ValueError("OpenList did not return the expected Worker fixture")
        return result

    def management_allowed(presented: str, _: datetime) -> bool:
        return presented.isascii() and compare_digest(presented, credentials["admin"])

    def output_allowed(presented: str, observed: datetime) -> bool:
        return (presented.isascii() and compare_digest(presented, credentials["worker"])
                and grant.decision("worker-fixture", observed.isoformat()) == "allowed")

    management = ProtectedResource(management_allowed, read_management, "application/json")
    output = ProtectedResource(output_allowed, read_output, "application/octet-stream")
    with resource_gateway(management, output) as port:
        management_status, _ = get(port, "/management/storage", credentials["admin"])
        output_status, output_body = get(port, "/worker/output.bin", credentials["worker"])
        reader_management = get(port, "/management/storage", credentials["reader"])
        reader_output = get(port, "/worker/output.bin", credentials["reader"])

    if management_status != 200 or output_status != 200 or output_body != fixture:
        raise ValueError("Authorized resource requests did not reach the expected fixtures")
    if reader_management != (403, b"") or reader_output != (403, b"") or any(v != 1 for v in origin_reads.values()):
        raise ValueError("A reader outside the management and Worker scopes reached a protected origin")
    return {
        "managementOwnerStatus": management_status, "outputGrantStatus": output_status,
        "outputGrantBytes": len(output_body), "outputGrantSha256": sha256(output_body).hexdigest(),
        "readerManagementStatus": reader_management[0], "readerManagementBytes": len(reader_management[1]),
        "readerOutputStatus": reader_output[0], "readerOutputBytes": len(reader_output[1]),
        "upstreamReads": origin_reads,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origin-port", type=int, required=True)
    parser.add_argument("--output-fixture", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.origin_port <= 65535:
        parser.error("Expected the private OpenList loopback port")
    try:
        with args.output_fixture.open("rb") as sample:
            fixture = sample.read(MAXIMUM_BODY_BYTES + 1)
        if not 0 < len(fixture) <= MAXIMUM_BODY_BYTES:
            raise ValueError("Expected a bounded Worker output fixture")
        origin_auth = json.loads(sys.stdin.readline(8192))
        if not isinstance(origin_auth, dict) or origin_auth.keys() != {"management", "worker"} or any(
            not isinstance(value, str) or not value or not value.isascii() or "\r" in value or "\n" in value
            for value in origin_auth.values()
        ):
            raise ValueError("Expected two temporary OpenList identities on standard input")
        print(json.dumps(replay(args.origin_port, origin_auth, fixture), separators=(",", ":")))
    except (OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
