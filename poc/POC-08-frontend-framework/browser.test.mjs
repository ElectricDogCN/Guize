import assert from "node:assert/strict";
import { after, before, test } from "node:test";
import { readFile } from "node:fs/promises";
import { chromium } from "playwright-core";
import { preview } from "vite";

const scenarios = JSON.parse(await readFile(new URL("./scenarios.json", import.meta.url)));
const listFixture = scenarios.find(({ id }) => id === "million_row_virtual_list_equivalent").inputs;
let server;
let browser;
let origin;

async function openPage(framework) {
  const page = await browser.newPage();
  page.setDefaultTimeout(7_000);
  await page.goto(`${origin}/${framework}.html`);
  return page;
}

before(async () => {
  server = await preview({ preview: { host: "127.0.0.1", port: 0 } });
  origin = `http://127.0.0.1:${server.httpServer.address().port}`;
  browser = await chromium.launch({
    executablePath: process.env.GUIZE_CHROMIUM,
    headless: true,
  });
});

after(async () => {
  await browser?.close();
  await server?.close();
});

for (const framework of ["react", "vue"]) {
  test(`${framework} renders the same bounded asset windows`, async () => {
    const page = await openPage(framework);
    try {
      await page.getByRole("heading", { name: "Asset list" }).waitFor();
      const rows = page.locator("[data-asset]");
      const list = page.getByLabel("Assets", { exact: true });
      assert.equal(await rows.count(), listFixture.visibleRows);
      for (const offset of listFixture.offsets) {
        const first = `asset-${String(offset + 1).padStart(7, "0")}`;
        await list.evaluate((region, row) => { region.scrollTop = row * 28; }, offset);
        await page.locator(`[data-asset="${first}"]`).waitFor();
        assert.equal(await rows.first().getAttribute("data-asset"), first);
        assert.equal(await rows.count(), listFixture.visibleRows);
      }
      await list.evaluate((region) => { region.scrollTop = region.scrollHeight; });
      const last = page.locator("[data-asset=asset-1000000]");
      await last.click();
      await page.getByText("Selected asset-1000000", { exact: true }).waitFor();
      assert.equal(await last.getAttribute("aria-pressed"), "true");
    } finally {
      await page.close();
    }
  });

  test(`${framework} handles the same conditional field and validation`, async () => {
    const page = await openPage(framework);
    try {
      const source = page.getByLabel("Source", { exact: true });
      const endpoint = page.getByLabel("Endpoint");
      const saveButton = page.getByRole("button", { name: "Save source" });
      await source.waitFor();
      assert.equal(await endpoint.count(), 0);
      await source.selectOption("remote");
      await endpoint.waitFor();
      await saveButton.click();
      await page.getByRole("alert").getByText("Endpoint is required.", { exact: true }).waitFor();
      await endpoint.fill("fixture-endpoint");
      await saveButton.click();
      await page.getByRole("status").getByText("Saved remote source with retry limit 3.", { exact: true }).waitFor();
      await source.selectOption("local");
      assert.equal(await endpoint.count(), 0);
    } finally {
      await page.close();
    }
  });


  test(`${framework} preserves graph edits through a reload`, async () => {
    const page = await openPage(framework);
    try {
      const graph = page.getByRole("region", { name: "Workflow graph" });
      await graph.getByRole("button", { name: "verify", exact: true }).click();
      await graph.getByRole("button", { name: "Move selected node" }).click();
      await graph.getByText("Row 2, column 2", { exact: true }).waitFor();
      await graph.getByLabel("Node label").fill("Verify input");
      await graph.getByRole("button", { name: "Verify input" }).waitFor();
      await page.reload();
      await graph.getByRole("button", { name: "Verify input" }).click();
      await graph.getByText("Row 2, column 2", { exact: true }).waitFor();
      assert.deepEqual(await graph.getByRole("listitem").allTextContents(),
        ["source to verify", "verify to publish"]);
    } finally {
      await page.close();
    }
  });

  test(`${framework} rejects duplicate rule conditions and saves the correction`, async () => {
    const page = await openPage(framework);
    try {
      const rules = page.getByRole("region", { name: "Decision table" });
      await rules.getByLabel("Rule 2 allow").check();
      await rules.getByRole("button", { name: "Add rule" }).click();
      const condition = rules.getByLabel("Rule 3 condition");
      const save = rules.getByRole("button", { name: "Save rules" });
      await condition.fill("ready");
      await save.click();
      await rules.getByText("Rule conditions must be unique.", { exact: true }).waitFor();
      await condition.fill("failed");
      await save.click();
      await rules.getByText("3 rules saved.", { exact: true }).waitFor();
      assert.equal(await rules.getByLabel("Rule 2 allow").isChecked(), true);
    } finally {
      await page.close();
    }
  });

  test(`${framework} filters fixture metrics and renders refresh failure in place`, async () => {
    const page = await openPage(framework);
    try {
      const monitor = page.getByRole("region", { name: "Monitoring" });
      const samples = monitor.getByRole("listitem");
      await samples.first().waitFor();
      assert.deepEqual(await samples.allTextContents(), ["0s · 1", "10s · 3"]);
      await monitor.getByLabel("Series").selectOption("failed");
      await monitor.getByText("10s · 1", { exact: true }).waitFor();
      assert.deepEqual(await samples.allTextContents(), ["0s · 0", "10s · 1"]);
      await monitor.getByRole("button", { name: "Refresh metrics" }).click();
      await monitor.getByRole("alert").getByText("Refresh failed (unavailable).", { exact: true }).waitFor();
      assert.deepEqual(await samples.allTextContents(), ["0s · 0", "10s · 1"]);
    } finally {
      await page.close();
    }
  });
}
