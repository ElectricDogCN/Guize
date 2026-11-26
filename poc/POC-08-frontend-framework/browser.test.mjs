import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { readFile } from "node:fs/promises";
import { chromium } from "playwright-core";
import { preview } from "vite";
import { observeScenario } from "./browser-observations.mjs";

const { scenarios } = JSON.parse(await readFile(new URL("./scenarios.json", import.meta.url)));
let server;
let browser;
let origin;

before(async () => {
  server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
  origin = `http://127.0.0.1:${server.httpServer.address().port}`;
  browser = await chromium.launch({ executablePath: process.env.GUIZE_CHROMIUM, headless: true });
});

after(async () => {
  await browser?.close();
  await server?.close();
});

for (const name of ["react", "vue"]) {
  for (const scenario of scenarios) {
    test(name + " " + scenario.scenarioId, async () => {
      const page = await browser.newPage();
      const url = `${origin}/${name}/index.html`;
      page.setDefaultTimeout(7_000);
      try {
        await page.goto(url);
        const actions = await observeScenario({ scenario, browser, page, url });
        assert.deepEqual(actions.map(({ actionId }) => actionId), Object.keys(scenario.expectedResults));
        assert.deepEqual(Object.fromEntries(actions.map(({ actionId, domSamples }) =>
          [actionId, domSamples.at(-1).observedValue],
        )), scenario.expectedResults);
        if (scenario.arguments.rowCount) {
          const { rowCount, viewportRows, overscanRows } = scenario.arguments;
          for (const { domSamples } of actions) {
            const sample = domSamples.at(-1);
            assert.equal(sample.inputRowCount, rowCount);
            assert.ok(sample.renderedDomRows <= viewportRows + 2 * overscanRows);
          }
        }
      } finally {
        await page.close();
      }
    });
  }
}
