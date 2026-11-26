"""Build the reproducible Worker SDK and conformance vectors."""

import argparse
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile, ZipInfo

RUNTIME = Path(__file__).resolve().parent
WORKER_CONTRACT = RUNTIME.parents[2] / "contracts" / "workers" / "v1"
SDK_VERSION = "1.0.0"


def build_sdk():
    members = {
        "check_worker_contract.py": RUNTIME / "check_worker_contract.py",
        "protocol.schema.yaml": WORKER_CONTRACT / "protocol.schema.yaml",
        "validation.py": RUNTIME / "validation.py",
        "worker-conformance-v1.json": RUNTIME / "fixtures" / "worker-conformance-v1.json",
    }
    output = BytesIO()
    with ZipFile(output, "w", compression=ZIP_STORED) as archive:
        for name, source in sorted(members.items()):
            # Zip headers and text line endings are fixed across Windows and Linux checkouts.
            entry = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, source.read_bytes().replace(b"\r\n", b"\n"))
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        content = build_sdk()
        with args.output.open("xb") as stream:
            stream.write(content)
    except OSError as error:
        parser.exit(1, f"{error}\n")
    print(json.dumps({"sdkVersion": SDK_VERSION, "sha256": sha256(content).hexdigest(), "byteCount": len(content)}))


if __name__ == "__main__":
    main()
