import fixture from "./scenarios.json";
import { assetWindow } from "./fixtures.mjs";
import "./comparison.css";

const { scenarios } = fixture;

const listFixture = scenarios.find(({ scenarioId }) => scenarioId === "million_row_virtual_list_equivalent").arguments;
const formFixture = scenarios.find(({ scenarioId }) => scenarioId === "dynamic_form_equivalent").arguments;

export const rowHeight = 28;
export const { rowCount } = listFixture;
export const visibleRows = listFixture.viewportRows + 2 * listFixture.overscanRows;
export const condition = formFixture.condition;
export const initialForm = { ...formFixture.values, [condition.field]: "" };

export function firstVisibleRow(scrollTop) {
  return Math.min(Math.floor(scrollTop / rowHeight), rowCount - visibleRows);
}

export function listRows(first) {
  return assetWindow(first, visibleRows);
}

export function formResult(values) {
  if (values.source === condition.when && !values[condition.field].trim()) {
    return { error: "Endpoint is required.", message: "" };
  }
  const retries = Number(values.retryLimit);
  if (!String(values.retryLimit).trim() || !Number.isInteger(retries) || retries < 0) {
    return { error: "Retry limit must be a nonnegative integer.", message: "" };
  }
  return { error: "", message: `Saved ${values.source} source with retry limit ${retries}.` };
}
