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

async function openPage(framework, options) {
  const page = await browser.newPage(options);
  page.setDefaultTimeout(7_000);
  await page.goto(`${origin}/${framework}/${framework}.html`);
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


  test(`${framework} resumes the stream once and deduplicates replayed events`, async () => {
    const page = await openPage(framework);
    try {
      for (const name of ["SSE stream", "WebSocket stream"]) {
        const stream = page.getByRole("region", { name });
        await stream.getByText("2 · ready", { exact: true }).waitFor();
        assert.equal(await stream.getByRole("status").textContent(), "Reconnects: 1");
        assert.deepEqual(await stream.getByRole("listitem").allTextContents(), ["1 · pending", "2 · ready"]);
      }
    } finally {
      await page.close();
    }
  });

  test(`${framework} maps events from the common playback component`, async () => {
    const page = await openPage(framework);
    try {
      const panel = page.getByRole("region", { name: "Playback component" });
      const widget = panel.locator("guize-fixture-player");
      await widget.getByText("sample-video", { exact: true }).waitFor();
      for (const [control, status] of [
        ["Signal ready", "ready"], ["Pause playback", "pause"], ["Signal unavailable", "unavailable"],
      ]) {
        await widget.getByRole("button", { name: control }).click();
        await panel.getByText(`Playback: ${status}`, { exact: true }).waitFor();
      }
      await page.getByRole("region", { name: "Monitoring" }).waitFor();
    } finally {
      await page.close();
    }
  });

  test(`${framework} exposes touch actions on both approved viewports`, async () => {
    const { viewports } = scenarios.find(({ id }) => id === "mobile_experience_equivalent").inputs;
    for (const viewport of viewports) {
      const page = await openPage(framework, { viewport, hasTouch: true, isMobile: true });
      try {
        const responsive = page.getByRole("region", { name: "Responsive actions" });
        const open = responsive.getByRole("button", { name: "Open sample" });
        const back = responsive.getByRole("button", { name: "Back to samples" });
        await open.waitFor();
        const layout = await responsive.locator(".responsive-actions").evaluate((group) => {
          const columns = getComputedStyle(group).gridTemplateColumns.split(" ").length;
          const heights = Array.from(group.querySelectorAll("button"), (button) => button.getBoundingClientRect().height);
          return { columns, heights };
        });
        assert.ok(layout.heights.every((height) => height >= 44));
        assert.equal(layout.columns, viewport.width < 600 ? 1 : 2);
        await open.tap();
        await responsive.getByText("Sample details", { exact: true }).waitFor();
        await back.tap();
        await responsive.getByText("Sample list", { exact: true }).waitFor();
      } finally {
        await page.close();
      }
    }
  });

  test(`${framework} applies the fixture subject visibility matrix`, async () => {
    const page = await openPage(framework);
    try {
      const visibility = page.getByRole("region", { name: "Subject visibility" });
      const select = visibility.getByLabel("Sample subject");
      await select.waitFor();
      const { subjects, actions } = scenarios.find(({ id }) => id === "permission_model_equivalent").inputs;
      for (const subject of subjects) {
        await select.selectOption(subject.id);
        await visibility.getByText("Current view: read", { exact: true }).waitFor();
        for (const action of actions) {
          const button = visibility.getByRole("button", { name: action, exact: true });
          assert.equal(await button.count(), Number(subject.actions.includes(action)));
        }
        const check = visibility.getByRole("button", { name: "Check sample edit capability" });
        await check.click();
        const expectedStatus = subject.actions.includes("edit") ? 200 : 403;
        await visibility.getByText("Server edit status " + expectedStatus, { exact: true }).waitFor();
      }
      await visibility.getByRole("button", { name: "edit", exact: true }).click();
      await visibility.getByLabel("Sample title").waitFor();
      await select.selectOption("reader");
      await visibility.getByLabel("Sample title").waitFor({ state: "detached" });
      await visibility.getByText("Current view: read", { exact: true }).waitFor();
    } finally {
      await page.close();
    }
  });

  test(`${framework} applies the same resolved theme tokens`, async () => {
    const page = await openPage(framework);
    try {
      const preview = page.getByRole("region", { name: "Theme preview" });
      const surface = preview.getByText("Sample surface", { exact: true });
      await surface.waitFor();
      for (const [name, background, color] of [
        ["light", "rgb(255, 255, 255)", "rgb(34, 34, 34)"],
        ["dark", "rgb(30, 30, 30)", "rgb(245, 245, 245)"],
      ]) {
        const toggle = preview.getByRole("button", { name, exact: true });
        await toggle.click();
        await preview.getByRole("button", { name, exact: true, pressed: true }).waitFor();
        const computed = await surface.evaluate((element) => {
          const style = getComputedStyle(element);
          return [style.backgroundColor, style.color, style.padding];
        });
        assert.deepEqual(computed, [background, color, "8px"]);
      }
    } finally {
      await page.close();
    }
  });
}
