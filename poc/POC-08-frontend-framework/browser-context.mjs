import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";

export async function readBrowserContext(path, outputDirectory) {
  const source = JSON.parse(await readFile(path));
  const builds = source.candidates ?? [source];
  const matches = builds.filter((build) => build.identity?.outputDirectory === outputDirectory);
  assert.equal(matches.length, 1, "Expected one context for the build directory");
  const { identity, buildId, compilerManifestRef } = matches[0];
  return { context: source.context, identity, buildId, compilerManifestRef };
}
