import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { assetRow, assetWindow, rowCount } from "./fixtures.mjs";

const { scenarios } = JSON.parse(readFileSync(new URL("./scenarios.json", import.meta.url)));

test("one million rows expose stable first and final windows", () => {
  assert.equal(rowCount, 1_000_000);
  assert.deepEqual(assetRow(0), { id: "asset-0000001", title: "Sample asset 0000001", status: "ready" });
  assert.deepEqual(assetWindow(999_968, 32).at(-1), assetRow(rowCount - 1));
  assert.deepEqual(assetWindow(400_000, 32), assetWindow(400_000, 32));
});

test("indexes and requested windows stay inside the shared fixture", () => {
  assert.throws(() => assetRow(rowCount), RangeError);
  assert.throws(() => assetWindow(-1, 2), RangeError);
  assert.throws(() => assetWindow(rowCount - 1, 2), RangeError);
  assert.deepEqual(assetWindow(rowCount, 0), []);
});

test("the scenario catalog uses unique inputs and steps for the ten comparison cases", () => {
  assert.equal(scenarios.length, 10);
  assert.equal(new Set(scenarios.map((scenario) => scenario.scenarioId)).size, 10);
  for (const scenario of scenarios) {
    assert.match(scenario.scenarioId, /_equivalent$/);
    assert.ok(Object.keys(scenario.arguments).length > 0);
    assert.ok(scenario.arguments.steps.length > 0);
    assert.ok(Object.keys(scenario.expectedResults).length > 0);
  }
  const list = scenarios.find(({ scenarioId }) => scenarioId === "million_row_virtual_list_equivalent");
  assert.equal(list.arguments.rowCount, rowCount);
  for (const offset of list.arguments.offsets) {
    assert.equal(assetWindow(offset, list.arguments.viewportRows).length, list.arguments.viewportRows);
  }
});
