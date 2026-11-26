import { createElement as element, useState } from "react";
import { Stream, Player, Responsive, Permissions, Theme } from "./react-runtime.mjs";
import { Graph, DecisionTable, Monitoring } from "./react-admin.mjs";
import { createRoot } from "react-dom/client";
import {
  condition, firstVisibleRow, formResult, initialForm, listRows, rowCount, rowHeight,
} from "./comparison.mjs";

function AssetList() {
  const [first, setFirst] = useState(0);
  const [selected, setSelected] = useState("");
  return element("section", { "aria-labelledby": "asset-heading" },
    element("h2", { id: "asset-heading" }, "Asset list"),
    element("div", {
      className: "asset-list", tabIndex: 0, "aria-label": "Assets",
      onScroll: (event) => setFirst(firstVisibleRow(event.currentTarget.scrollTop)),
    },
    element("div", { className: "asset-spacer", style: { height: rowCount * rowHeight } },
      element("div", { className: "asset-window", style: { top: first * rowHeight } },
        listRows(first).map((row) => element("button", {
          key: row.id, type: "button", "data-asset": row.id,
          "aria-pressed": row.id === selected, onClick: () => setSelected(row.id),
        }, `${row.title} · ${row.status}`)),
      ),
    )),
    element("p", { "aria-live": "polite" }, selected ? `Selected ${selected}` : "No asset selected"),
  );
}

function SourceForm() {
  const [values, setValues] = useState(initialForm);
  const [result, setResult] = useState({ error: "", message: "" });
  const update = (event) => {
    const { name, value } = event.currentTarget;
    setValues((current) => ({ ...current, [name]: value }));
    setResult({ error: "", message: "" });
  };
  return element("section", { "aria-labelledby": "form-heading" },
    element("h2", { id: "form-heading" }, "Source form"),
    element("form", {
      noValidate: true, onSubmit: (event) => {
        event.preventDefault();
        setResult(formResult(values));
      },
    },
    element("div", { className: "field" },
      element("label", { htmlFor: "source-type" }, "Source"),
      element("select", { id: "source-type", name: "source", value: values.source, onChange: update },
        element("option", { value: "local" }, "Local"),
        element("option", { value: "remote" }, "Remote"),
      ),
    ),
    element("label", {}, "Retry limit", element("input", {
      name: "retryLimit", type: "number", min: 0, value: values.retryLimit, onChange: update,
    })),
    values.source === condition.when && element("label", {}, "Endpoint", element("input", {
      name: condition.field, required: true, value: values[condition.field], onChange: update,
    })),
    element("button", { type: "submit" }, "Save source")),
    element("p", { role: "alert" }, result.error),
    element("p", { role: "status" }, result.message),
  );
}

createRoot(document.querySelector("#app")).render(element("div", {},
  element("h1", {}, "React comparison"),
  element(AssetList),
  element(SourceForm),
  element(Graph),
  element(DecisionTable),
  element(Monitoring),
  element(Stream),
  element(Player),
  element(Responsive),
  element(Permissions),
  element(Theme),
));
