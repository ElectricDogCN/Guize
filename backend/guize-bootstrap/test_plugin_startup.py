"""Start the packaged core and three real synthetic plugin processes."""

from argparse import ArgumentParser
from contextlib import ExitStack, contextmanager
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
from time import monotonic, sleep


HERE = Path(__file__).resolve().parent
REPOSITORY = HERE.parents[1]


def wait_for(check, timeout, message):
    end = monotonic() + timeout
    while monotonic() < end:
        result = check()
        if result:
            return result
        sleep(0.05)
    raise AssertionError(message)


@contextmanager
def running(command, output=subprocess.DEVNULL):
    process = subprocess.Popen(command, stdout=output, stderr=subprocess.STDOUT)
    try:
        yield process
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def fixture(mode, directory):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/health":
                self.send_error(404)
                return
            if mode == "late":
                (directory / "requested").touch()
                sleep(2)
            capabilities = ["TRANSCODE"] if mode == "late" else ["MEDIA_PROBE", "THUMBNAIL"]
            body = json.dumps({"status": "READY", "capabilities": capabilities}).encode()
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except OSError:
                pass
            finally:
                if mode == "late":
                    (directory / "completed").touch()

        def log_message(self, message, *arguments):
            pass

    with HTTPServer(("127.0.0.1", 0), Handler) as server:
        marker = directory / "port.pending"
        marker.write_text(str(server.server_port), encoding="ascii")
        marker.replace(directory / "port")
        if mode == "exit":
            return 42
        server.serve_forever()
    return 0


def request_health(port, route):
    connection = HTTPConnection("127.0.0.1", port, timeout=1)
    try:
        connection.request("GET", route)
        response = connection.getresponse()
        if response.status == 200:
            return json.loads(response.read())
    except (OSError, HTTPException):
        return None
    finally:
        connection.close()
    return None


def prepare_inventory(directory, ports):
    conformance = REPOSITORY / "specs/contracts/runtime/fixtures/release-conformance-v1.json"
    data = json.loads(conformance.read_bytes())
    for name, content in data["assets"].items():
        (directory / name).write_bytes(content.encode("utf-8"))
    for name, value in (
        ("release-lock.json", data["lock"]), ("inventory.json", data["inventory"]), ("probes.json", ports),
    ):
        (directory / name).write_text(json.dumps(value), encoding="utf-8")


def test(java, jar):
    expected = {"media-analysis": {"state": "READY", "capabilities": ["MEDIA_PROBE", "THUMBNAIL"]},
                "offline-ocr": {"state": "UNAVAILABLE", "capabilities": []},
                "av1-worker": {"state": "UNAVAILABLE", "capabilities": []}}
    with TemporaryDirectory(prefix="guize-bootstrap-process-test-") as temporary, ExitStack() as resources:
        root = Path(temporary)
        provider_ports = {}
        for plugin, mode in (("media-analysis", "ready"), ("av1-worker", "late"), ("offline-ocr", "exit")):
            directory = root / mode
            directory.mkdir()
            process = resources.enter_context(running([sys.executable, "-B", __file__, "fixture", mode, str(directory)]))
            marker = directory / "port"
            port = wait_for(lambda: int(marker.read_text(encoding="ascii")) if marker.exists() else None,
                            10, f"{plugin} did not publish its local test port")
            provider_ports[plugin] = port
            if mode == "exit":
                exited_code = process.wait(timeout=5)
                assert exited_code == 42
        invent = root / "inventory"
        invent.mkdir()
        prepare_inventory(invent, provider_ports)
        log = root / "bootstrap.log"
        with log.open("wb") as output:
            command = [str(java), "-jar", str(jar), "--server.port=0",
                       "--management.endpoint.health.show-details=always",
                       f"--guize.bootstrap.repository-root={REPOSITORY}",
                       f"--guize.bootstrap.plugin-directory={invent}",
                       f"--guize.bootstrap.python={sys.executable}",
                       "--guize.bootstrap.probe-timeout-millis=800"]
            service = resources.enter_context(running(command, output))

        def find_port():
            match = re.search(r"Tomcat started on port (\d+)", log.read_text(encoding="utf-8", errors="replace"))
            if service.poll() is not None:
                raise AssertionError("The packaged control plane exited during startup")
            return int(match[1]) if match else None

        port = wait_for(find_port, 25, "The packaged control plane did not listen")
        ready = wait_for(lambda: request_health(port, "/actuator/health/readiness"), 10,
                         "The control plane did not become ready")
        assert ready["status"] == "UP"

        def states():
            health = request_health(port, "/actuator/health")
            if health is None:
                return {}
            assert health["status"] == "UP"
            return health["components"]["pluginRegistry"]["details"]["plugins"]

        observed = wait_for(states, 15, "The validated plugin inventory never appeared")
        assert observed == expected, observed
        wait_for(lambda: (root / "late" / "requested").exists(), 4, "The late plugin was never probed")
        wait_for(lambda: (root / "late" / "completed").exists(), 5, "The late plugin never attempted its response")
        assert states() == expected
        assert request_health(port, "/actuator/health/readiness")["status"] == "UP"
    print(json.dumps({"controlPlane": ready["status"], "pluginStates": observed, "exitedProviderCode": exited_code,
                      "lateProbeResponseDidNotRestoreCapability": True}))


def main():
    parser = ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("test")
    run.add_argument("--java", required=True, type=Path)
    run.add_argument("--jar", required=True, type=Path)
    worker = commands.add_parser("fixture")
    worker.add_argument("mode", choices=["ready", "exit", "late"])
    worker.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.command == "fixture":
        return fixture(args.mode, args.directory)
    test(args.java.resolve(strict=True), args.jar.resolve(strict=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
