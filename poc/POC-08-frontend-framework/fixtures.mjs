export const rowCount = 1_000_000;

const statuses = ["ready", "pending", "failed"];

export function assetRow(index) {
  if (!Number.isInteger(index) || index < 0 || index >= rowCount) {
    throw new RangeError("Asset index is outside the fixture.");
  }

  const id = String(index + 1).padStart(7, "0");
  return {
    id: "asset-" + id,
    title: "Sample asset " + id,
    status: statuses[index % statuses.length],
  };
}

export function assetWindow(offset, length) {
  if (
    !Number.isInteger(offset) || !Number.isInteger(length) ||
    offset < 0 || length < 0 || offset + length > rowCount
  ) {
    throw new RangeError("Asset window is outside the fixture.");
  }

  return Array.from({ length }, (_, index) => assetRow(offset + index));
}
