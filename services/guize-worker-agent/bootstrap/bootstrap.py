"""Start a Worker only after its fixed SDK passes protocol conformance."""

from argparse import ArgumentParser
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZipFile


# PLUGIN-CONTRACT-V1 release-conformance-v1.json binds these Worker SDK inputs.
SDK_SHA256 = "debb66b4a493abd8ba21fdaa5725372aba04e108fe2028d843fa8ffff66f8f04"
SCHEMA_SHA256 = "45cac8900d332fa4aebed0c300d8aba19df7551046ef042d4a00cabd7867ad65"
VECTORS_SHA256 = "2bfe772731446f04719ad2b490443741ee0266a28970755a8c404d41cf06ac8b"
SDK_BYTES = 37_742
SDK_VERSION = "1.0.0"
PROTOCOL_VERSION = "worker-v1"
VERIFIED_CASES = 40
VECTORS_NAME = "worker-conformance-v1.json"


def verify_worker_sdk(sdk_path: Path) -> dict:
    with sdk_path.open("rb") as source:
        payload = source.read(SDK_BYTES + 1)
    if len(payload) != SDK_BYTES or sha256(payload).hexdigest() != SDK_SHA256:
        raise ValueError("Worker SDK SHA-256 does not match the approved package")

    with ZipFile(BytesIO(payload)) as archive, TemporaryDirectory(prefix="guize-worker-sdk-") as temporary:
        schema = archive.read("protocol.schema.yaml")
        vectors = archive.read(VECTORS_NAME)
        if sha256(schema).hexdigest() != SCHEMA_SHA256 or sha256(vectors).hexdigest() != VECTORS_SHA256:
            raise ValueError("Worker protocol schema or conformance vectors do not match the approved SDK")
        directory = Path(temporary)
        for name in ("check_worker_contract.py", "validation.py", "protocol.schema.yaml", VECTORS_NAME):
            (directory / name).write_bytes(archive.read(name))
        run = subprocess.run(
            [sys.executable, "-B", "check_worker_contract.py", "conformance", VECTORS_NAME],
            cwd=directory, capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
        if run.returncode != 0:
            raise ValueError("The approved Worker SDK failed protocol conformance: " + run.stderr.strip())
        report = json.loads(run.stdout)

    if (report.get("protocolVersion") != PROTOCOL_VERSION or report.get("verifiedCases") != VERIFIED_CASES
            or report.get("fixtureSha256") != VECTORS_SHA256):
        raise ValueError("Worker SDK returned an unexpected conformance result")
    return {"status": "ready", "protocolVersion": PROTOCOL_VERSION, "sdkVersion": SDK_VERSION,
            "sdkSha256": SDK_SHA256, "verifiedCases": report["verifiedCases"]}


def main() -> None:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--sdk", type=Path, required=True, help="Approved Worker SDK zip")
    args = parser.parse_args()
    try:
        result = verify_worker_sdk(args.sdk)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
