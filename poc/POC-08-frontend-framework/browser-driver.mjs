import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { join, posix } from "node:path";
import { parseArgs } from "node:util";
import { chromium } from "playwright-core";
import { observeScenario } from "./browser-observations.mjs";
import { readBrowserContext } from "./browser-context.mjs";

const hash = (buffer) => "sha256:" + createHash("sha256").update(buffer).digest("hex");
const timestamp = () => new Date().toISOString();

async function navigate(page, url, outputDirectory) {
  const startedAt = timestamp();
  const location = new URL(url);
  const base = posix.dirname(location.pathname) + "/";
  const loaded = new Map();
  const inspect = (response) => {
    const resource = new URL(response.url());
    const type = response.request().resourceType();
    if (resource.origin !== location.origin || !["document", "script", "stylesheet"].includes(type)) return;
    if (!resource.pathname.startsWith(base)) throw new Error("Loaded asset outside candidate directory.");
    const name = decodeURIComponent(resource.pathname.slice(base.length));
    if (!loaded.has(name)) {
      loaded.set(name, response.body().then(async (data) => {
        assert.deepEqual(data, await readFile(join(outputDirectory, name)), name);
        return { ref: posix.join(outputDirectory, name), sha256: hash(data), byteCount: data.length };
      }));
    }
  };
  page.on("response", inspect);
  try {
    await page.goto(url);
    assert.equal(page.url(), url);
  } finally {
    page.off("response", inspect);
  }
  const loadedAssets = await Promise.all(loaded.values());
  const document = await loaded.get(posix.basename(location.pathname));
  assert.ok(document);
  return {
    startedAt, finishedAt: timestamp(), documentURL: page.url(), documentRef: document.ref,
    documentSha256: document.sha256, loadedAssets,
  };
}

const names = ["context", "build", "fixture", "scenario", "stdout", "url"];
const options = Object.fromEntries(names.map((name) => [name, { type: "string" }]));
const { values } = parseArgs({ options });
for (const name of names) assert.ok(values[name], "Missing --" + name);
const input = await readFile(values.fixture);
const { scenarios } = JSON.parse(input);
const scenario = scenarios.find(({ scenarioId }) => scenarioId === values.scenario);
assert.ok(scenario);
const { context, identity, buildId, compilerManifestRef } = await readBrowserContext(values.context, values.build);
const { origin, pathname, protocol, hostname } = new URL(values.url);
assert.equal(protocol, "http:");
assert.equal(hostname, "127.0.0.1");
assert.equal(pathname, "/" + identity.candidateId + "/index.html");
assert.equal(identity.outputDirectory, values.build);

const manifest = await readFile(compilerManifestRef);
const sourceFiles = await Promise.all(["browser-driver.mjs", "browser-observations.mjs", "browser-context.mjs"].map((name) =>
  readFile(new URL(name, import.meta.url)),
));
const startedAt = timestamp();
const server = await chromium.launchServer({
  executablePath: process.env.GUIZE_CHROMIUM,
  headless: true,
});
const browserProcess = server.process();
let browser;
let navigation;
let actions;
let browserBuild;
try {
  browser = await chromium.connect(server.wsEndpoint());
  browserBuild = "chromium/" + browser.version();
  const page = await browser.newPage();
  page.setDefaultTimeout(7_000);
  await page.route("**/*", (route) => {
    const resource = new URL(route.request().url());
    return resource.origin === origin ? route.continue() : route.abort();
  });
  navigation = await navigate(page, values.url, values.build);
  actions = await observeScenario({ scenario, browser, page, url: values.url });
  assert.deepEqual(actions.map((action) => action.actionId), Object.keys(scenario.expectedResults));
  assert.deepEqual(Object.fromEntries(actions.map(({ actionId, domSamples }) =>
    [actionId, domSamples.at(-1).observedValue],
  )), scenario.expectedResults);
} finally {
  try {
    await browser?.close();
  } finally {
    await server.close();
  }
}
assert.equal(browserProcess.exitCode, 0);

const result = {
  schemaVersion: 1, kind: "frontend_browser_result", context, identity, buildId,
  compilerManifestRef, compilerManifestSha256: hash(manifest), scenarioId: scenario.scenarioId,
  fixtureId: scenario.fixtureId, inputSha256: hash(input),
  scenarioDriverBuild: hash(Buffer.concat(sourceFiles)), browserBuild,
  browserProcessId: browserProcess.pid, browserExitCode: browserProcess.exitCode,
  status: "completed", startedAt, finishedAt: timestamp(), navigation, actions,
};
const json = JSON.stringify(result, null, 2) + "\n";
await writeFile(values.stdout, json, { flag: "wx" });
