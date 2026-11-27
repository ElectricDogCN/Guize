"""Collect optional local plugin readiness and reuse GZ-008 release assessment."""

from argparse import ArgumentParser
from http.client import HTTPConnection, HTTPException
import json
from pathlib import Path
from queue import Empty, Queue
import sys
from threading import Thread
from time import monotonic, sleep
from urllib.parse import urlsplit


def observe(port, endpoint, timeout):
    """Read one health response. None indicates a temporary failure."""
    if type(port) is not int or not 1 <= port <= 65535 or not isinstance(endpoint, str):
        return []
    connection = HTTPConnection("127.0.0.1", port, timeout=timeout)
    try:
        parsed = urlsplit(endpoint)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or not endpoint.startswith("/"):
            return []
        connection.request("GET", endpoint)
        response = connection.getresponse()
        if response.status == 503:
            return None
        if response.status != 200:
            return []
        content = response.read(4097)
        if len(content) > 4096:
            return []
        observation = json.loads(content)
        if isinstance(observation, dict) and observation.get("status") == "READY":
            capabilities = observation.get("capabilities")
            if isinstance(capabilities, list) and capabilities:
                return capabilities
    except OSError:
        return None
    except (HTTPException, ValueError, OverflowError):
        return []
    finally:
        connection.close()
    return []


def assess_plugins(repository, directory, timeout):
    sys.path.insert(0, str(repository / "specs/contracts/runtime"))
    from check_plugin_contract import assess, asset_file, read_json

    lock = read_json(directory / "release-lock.json")
    inventory = read_json(directory / "inventory.json")
    ports = read_json(directory / "probes.json")
    if not isinstance(inventory["plugins"], dict) or not isinstance(ports, dict):
        raise ValueError("Expected the release inventory and a plugin-to-loopback-port map")
    for entry in inventory["plugins"].values():
        if isinstance(entry, dict):
            entry["health"] = "UNAVAILABLE"
            entry["observedCapabilities"] = []

    eligibility = assess(lock, inventory, directory)["plugins"]
    pending = {}
    for plugin, result in eligibility.items():
        if result["state"] != "UNAVAILABLE" or plugin not in ports:
            continue
        try:
            entry = inventory["plugins"][plugin]
            manifest = read_json(asset_file(directory, entry["manifestFile"]))
            runtime = manifest["spec"]["runtime"]
            network = manifest["spec"].get("permissions", {}).get("network", [])
            if runtime["mode"] == "EXTERNAL_SERVICE" and "LOOPBACK" in network:
                pending[plugin] = (ports[plugin], runtime.get("healthEndpoint", "/health"))
        except (OSError, ValueError, KeyError, TypeError):
            continue

    results = Queue()
    deadline = monotonic() + timeout

    def probe(plugin, params):
        remaining = deadline - monotonic()
        while remaining > 0:
            capabilities = observe(*params, remaining)
            observed_at = monotonic()
            if capabilities is not None:
                results.put((observed_at, plugin, capabilities))
                return
            sleep(min(0.05, max(0, deadline - observed_at)))
            remaining = deadline - monotonic()
        results.put((monotonic(), plugin, []))

    for plugin, params in pending.items():
        Thread(target=probe, args=(plugin, params), daemon=True).start()
    for _ in pending:
        remaining = deadline - monotonic()
        try:
            observed_at, plugin, capabilities = results.get(timeout=max(0, remaining))
        except Empty:
            break
        if observed_at <= deadline and capabilities:
            inventory["plugins"][plugin].update(health="READY", observedCapabilities=capabilities)
    return assess(lock, inventory, directory)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    parser.add_argument("directory", type=Path)
    parser.add_argument("timeout_millis", type=int)
    args = parser.parse_args()
    if args.timeout_millis <= 0:
        parser.error("The plugin deadline must be positive")
    try:
        result = assess_plugins(args.repository.resolve(strict=True), args.directory.resolve(strict=True),
                                args.timeout_millis / 1000)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(1, f"Invalid optional plugin configuration: {error}\n")
    print(json.dumps(result, separators=(",", ":")))


if __name__ == "__main__":
    main()
