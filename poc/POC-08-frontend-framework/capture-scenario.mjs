import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { closeSync, openSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { posix } from "node:path";
import { parseArgs } from "node:util";
import { readBrowserContext } from "./browser-context.mjs";

const scenarioKey = "million_row_virtual_list_equivalent";
const timestamp = () => new Date().toISOString();
const digest = (bytes) => "sha256:" + createHash("sha256").update(bytes).digest("hex");
const driver = "poc/POC-08-frontend-framework/browser-driver.mjs";
const fields = ["policy", "fixture", "candidate", "scenario", "output"];
const { values } = parseArgs({ options: Object.fromEntries(fields.map((name) => [name, { type: "string" }])) });
for (const name of fields) assert.ok(values[name], "Missing --" + name);
assert.ok(["react", "vue"].includes(values.candidate), "Unknown candidate");

function relativePath(path) {
  assert.equal(path, posix.normalize(path), path);
  assert.ok(path !== "." && path !== ".." && !posix.isAbsolute(path) && !path.startsWith("../") &&
    !path.includes("\\") && !path.includes(":"), path);
}

for (const path of [values.policy, values.fixture, values.output]) relativePath(path);
const policy = JSON.parse(await readFile(values.policy));
const { origin, hostname, protocol } = new URL(policy.browserOrigin);
assert.equal(origin, policy.browserOrigin);
assert.equal(hostname, "127.0.0.1");
assert.equal(protocol, "http:");
assert.deepEqual(policy.browserCommandArgs.slice(0, 3), ["node", driver, "--context"]);
assert.equal(policy.browserCommandArgs.length, 4);
relativePath(policy.browserCommandArgs[3]);
assert.equal(policy.browserEntryPath, "index.html");

const fixture = await readFile(values.fixture);
const scenario = JSON.parse(fixture).scenarios.find((item) => item.scenarioId === values.scenario);
const candidate = policy.candidates.find((item) => item.candidateId === values.candidate);
assert.ok(scenario && candidate);
relativePath(candidate.outputDirectory);
const context = await readBrowserContext(policy.browserCommandArgs[3], candidate.outputDirectory);
relativePath(context.compilerManifestRef);
assert.deepEqual(context.identity, candidate);

await mkdir(posix.dirname(values.output), { recursive: true });
await mkdir(values.output);
const stdoutRef = posix.join(values.output, "browser.json");
const stderrRef = posix.join(values.output, "browser.stderr.txt");
const executionRef = posix.join(values.output, "execution.json");
const argv = [...policy.browserCommandArgs, "--build", candidate.outputDirectory, "--fixture", values.fixture,
  "--scenario", scenario.scenarioId, "--stdout", stdoutRef,
  "--url", origin + "/" + candidate.candidateId + "/" + policy.browserEntryPath];

const stderr = openSync(stderrRef, "wx");
const startedAt = timestamp();
let processId;
let exitCode;
try {
  const child = spawn(process.execPath, argv.slice(1), { stdio: ["ignore", "inherit", stderr] });
  processId = child.pid;
  exitCode = await new Promise((resolve, reject) => {
    child.once("error", reject);
    child.once("close", (code, signal) => signal ? reject(new Error("Browser driver stopped by " + signal)) : resolve(code));
  });
} finally {
  closeSync(stderr);
}
const finishedAt = timestamp();
assert.equal(exitCode, 0, "Browser driver failed. See " + stderrRef);
const raw = await readFile(stdoutRef);
const result = JSON.parse(raw);
const manifest = await readFile(context.compilerManifestRef);
const identity = {
  ...context,
  compilerManifestSha256: digest(manifest),
  scenarioId: scenario.scenarioId,
  fixtureId: scenario.fixtureId,
  inputSha256: digest(fixture),
  scenarioDriverBuild: policy.scenarioDriverBuild,
  browserBuild: policy.browserBuild,
};
for (const [key, value] of Object.entries(identity)) assert.deepEqual(result[key], value, key);
assert.equal(result.status, "completed");
assert.equal(result.browserExitCode, 0);
assert.ok(startedAt <= result.startedAt && result.startedAt <= result.finishedAt && result.finishedAt <= finishedAt);
const execution = {
  schemaVersion: 1, kind: "frontend_browser_execution", ...identity, argv, processId, startedAt, finishedAt, exitCode,
  stdoutRef, stdoutSha256: digest(raw), stderrRef, stderrSha256: digest(await readFile(stderrRef)),
};
const measurements = [{
  measurementId: "interaction_duration", unit: "ms", value: Date.parse(result.finishedAt) - Date.parse(result.startedAt),
}];
if (scenario.scenarioId === scenarioKey) {
  const samples = result.actions.flatMap((action) => action.domSamples);
  const rows = [...new Set(samples.filter((sample) => sample.inputRowCount !== null).map((sample) => sample.inputRowCount))];
  const rendered = samples.filter((sample) => sample.renderedDomRows !== null).map((sample) => sample.renderedDomRows);
  assert.equal(rows.length, 1);
  assert.ok(rendered.length > 0);
  measurements.push({ measurementId: "measured_input_rows", unit: "rows", value: rows[0] },
    { measurementId: "rendered_dom_rows_peak", unit: "rows", value: Math.max(...rendered) });
}
const observation = {
  schemaVersion: 1, kind: "frontend_scenario_observation", browserExecutionRef: executionRef,
  candidateId: candidate.candidateId, buildId: result.buildId, scenarioId: result.scenarioId, fixtureId: result.fixtureId,
  inputSha256: result.inputSha256, scenarioDriverBuild: result.scenarioDriverBuild, startedAt: result.startedAt,
  finishedAt: result.finishedAt, status: result.status, measurements,
  actions: result.actions.map(({ actionId, startedAt, finishedAt, domSamples }) =>
    ({ actionId, startedAt, finishedAt, result: domSamples.at(-1).observedValue })),
};
for (const [file, value] of [[executionRef, execution], [posix.join(values.output, "observation.json"), observation]]) {
  await writeFile(file, JSON.stringify(value, null, 2) + "\n", { flag: "wx" });
}
