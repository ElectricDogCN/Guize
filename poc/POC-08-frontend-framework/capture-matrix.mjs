import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { mkdir, readFile } from "node:fs/promises";
import { posix } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";

const names = ["policy", "fixture", "output"];
const options = Object.fromEntries(names.map((name) => [name, { type: "string" }]));
const { values } = parseArgs({ options });
for (const name of names) {
  const path = values[name];
  assert.ok(path && path.split("/").every((part) => part && part !== "." && part !== "..") &&
    !path.includes("\\") && !path.includes(":"), "Expected a repository-relative --" + name);
}

const policy = JSON.parse(await readFile(values.policy));
const fixture = JSON.parse(await readFile(values.fixture));
const candidates = policy.candidates.map(({ candidateId }) => candidateId);
assert.deepEqual(candidates.slice().sort(), ["react", "vue"], "Expected one React and one Vue candidate");
const scenarios = fixture.scenarios.map(({ scenarioId }) => scenarioId);
assert.equal(scenarios.length, 10, "Expected the complete ten-scenario fixture");
assert.equal(new Set(scenarios).size, scenarios.length, "Repeated scenario");
assert.ok(scenarios.every((id) => /^[a-z][a-z0-9_]*$/.test(id)), "Invalid scenario ID");

const capture = fileURLToPath(new URL("./capture-scenario.mjs", import.meta.url));
await mkdir(posix.dirname(values.output), { recursive: true });
await mkdir(values.output);
for (const candidate of candidates) {
  const directory = posix.join(values.output, candidate);
  await mkdir(directory);
  for (const scenario of scenarios) {
    const output = posix.join(directory, scenario);
    const child = spawn(process.execPath, [capture, "--policy", values.policy, "--fixture", values.fixture,
      "--candidate", candidate, "--scenario", scenario, "--output", output], { stdio: "inherit" });
    const status = await new Promise((resolve, reject) => {
      child.once("error", reject);
      child.once("close", (code, signal) => resolve({ code, signal }));
    });
    assert.equal(status.code, 0, candidate + "/" + scenario + " capture failed. See " + output +
      (status.signal ? " (" + status.signal + ")" : ""));
  }
  console.log(candidate + ": " + scenarios.length + " native scenario records");
}
