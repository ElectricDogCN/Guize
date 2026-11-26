import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createHash, randomUUID } from "node:crypto";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { dirname, join, posix, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { build } from "vite";

const hash = (data) => "sha256:" + createHash("sha256").update(data).digest("hex");
const now = () => new Date().toISOString();
const existsError = (path) => "Use a new output path: " + path;
const portable = (path) => path.replaceAll("\\", "/");
const packageRoot = fileURLToPath(new URL(".", import.meta.url));
const require = createRequire(import.meta.url);

function requireRelative(path) {
  assert.equal(path, posix.normalize(path));
  assert.ok(!posix.isAbsolute(path) && !path.startsWith("../") && path !== ".." &&
    path !== "." && !path.includes("\\") && !path.includes(":"), path);
}

async function emittedFiles(directory) {
  const files = [];
  async function visit(folder) {
    const entries = await readdir(join(directory, folder), { withFileTypes: true });
    for (const entry of entries) {
      const path = posix.join(folder, entry.name);
      if (entry.isDirectory()) {
        await visit(path);
      } else {
        assert.ok(entry.isFile(), "Non-regular compiler output: " + path);
        const payload = await readFile(join(directory, path));
        assert.ok(payload.length > 0, "Empty compiler output: " + path);
        files.push({ path, ref: posix.join(directory, path), sha256: hash(payload), byteCount: payload.length });
      }
    }
  }
  await visit(".");
  assert.ok(files.length > 0 && files.length <= 1024);
  return files.sort((left, right) => left.path.localeCompare(right.path, "en"));
}

const parameters = ["identity", "manifest", "report"];
const options = Object.fromEntries(parameters.map((name) => [name, { type: "string" }]));
const { values } = parseArgs({ options });
for (const name of parameters) assert.ok(values[name], "Missing --" + name);
const identity = JSON.parse(await readFile(values.identity));
const { candidateId, frameworkVersion, sourceRevision, compilerBuild, lockRef, lockSha256, outputDirectory } = identity;
assert.ok(["react", "vue"].includes(candidateId));
for (const path of [lockRef, outputDirectory, values.manifest, values.report]) requireRelative(path);
assert.notEqual(values.manifest, values.report);
for (const report of [values.manifest, values.report]) {
  assert.ok(!report.startsWith(outputDirectory + "/"), existsError(report));
  assert.ok(report !== outputDirectory);
}
assert.equal(compilerBuild, "vite@" + require("vite/package.json").version);
assert.equal(frameworkVersion, require(candidateId + "/package.json").version);
const revision = execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim();
assert.equal(sourceRevision, revision);
const repoRoot = execFileSync("git", ["rev-parse", "--show-toplevel"], { encoding: "utf8" }).trim();
assert.equal(portable(process.cwd()), repoRoot, "Run from the repository root.");
const packageScope = portable(relative(process.cwd(), packageRoot));
assert.equal(execFileSync("git", ["status", "--porcelain=v1", "--untracked-files=all", "--", packageScope],
  { encoding: "utf8" }).trim(), "", "Frontend source has working-tree changes.");
assert.deepEqual(identity.commandArgs, ["node", portable(relative(process.cwd(), process.argv[1])), ...process.argv.slice(2)]);
const lock = await readFile(lockRef);
assert.equal(hash(lock), lockSha256);
assert.deepEqual(lock, await readFile(join(packageRoot, "package-lock.json")));

await mkdir(dirname(outputDirectory), { recursive: true });
await mkdir(outputDirectory);
const buildId = randomUUID();
const startedAt = now();
await build({
  root: packageRoot, mode: candidateId,
  build: { outDir: resolve(outputDirectory), emptyOutDir: false },
});
const finishedAt = now();
const files = await emittedFiles(outputDirectory);
const manifest = {
  schemaVersion: 1, kind: "frontend_compiler_manifest", identity, buildId,
  observedAt: now(), emittedFiles: files,
};
const bytes = Buffer.from(JSON.stringify(manifest, null, 2) + "\n");
await writeFile(values.manifest, bytes, { flag: "wx" });

const details = {
  schemaVersion: 1, kind: "frontend_build_observation", identity, buildId,
  startedAt, finishedAt, exitCode: 0, compilerManifestRef: values.manifest,
  compilerManifestSha256: hash(bytes),
  bundles: files.map(({ ref, sha256, byteCount }) => ({ ref, sha256, byteCount })),
};
await writeFile(values.report, JSON.stringify(details, null, 2) + "\n", { flag: "wx" });
