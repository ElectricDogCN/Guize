import { readFileSync } from "node:fs";
import { gzipSync } from "node:zlib";

function entryAssets(framework) {
  const output = new URL("./dist/" + framework + "/", import.meta.url);
  const manifest = JSON.parse(readFileSync(new URL(".vite/manifest.json", output), "utf8"));
  const entry = framework + ".html";
  const files = new Set();
  const pending = [entry];
  const visited = new Set();
  while (pending.length) {
    const key = pending.pop();
    if (visited.has(key)) continue;
    visited.add(key);
    const item = manifest[key];
    if (!item) throw new Error("Missing bundle manifest entry: " + key);
    files.add(item.file);
    for (const stylesheet of item.css ?? []) files.add(stylesheet);
    pending.push(...(item.imports ?? []));
  }
  return [...files].sort().map((file) => {
    const data = readFileSync(new URL(file, output));
    return { file, bytes: data.length, gzipBytes: gzipSync(data).length };
  });
}

const result = Object.fromEntries(["react", "vue"].map((framework) => {
  const files = entryAssets(framework);
  const bytes = files.reduce((sum, file) => sum + file.bytes, 0);
  const gzipBytes = files.reduce((sum, file) => sum + file.gzipBytes, 0);
  return [framework, { bytes, gzipBytes, kibibytes: bytes / 1024, files }];
}));
process.stdout.write(JSON.stringify(result, null, 2) + "\n");
