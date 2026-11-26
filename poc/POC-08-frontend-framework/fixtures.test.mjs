import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { assetRow, assetWindow, rowCount } from "./fixtures.mjs";

const scenarios = JSON.parse(readFileSync(new URL("./scenarios.json", import.meta.url)));

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
  assert.equal(new Set(scenarios.map((scenario) => scenario.id)).size, 10);
  for (const scenario of scenarios) {
    assert.match(scenario.id, /_equivalent$/);
    assert.ok(Object.keys(scenario.inputs).length > 0);
    assert.ok(scenario.steps.length > 0);
  }
  const list = scenarios.find(({ id }) => id === "million_row_virtual_list_equivalent");
  assert.equal(list.inputs.rowCount, rowCount);
  for (const offset of list.inputs.offsets) {
    assert.equal(assetWindow(offset, list.inputs.visibleRows).length, list.inputs.visibleRows);
  }
});
