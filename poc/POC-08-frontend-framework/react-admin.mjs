import { createElement as h, useState } from "react";
import {
  editNode, graphEdges, initialRules, loadGraph, monitoring, ruleError, saveGraph,
} from "./scenario-models.mjs";

function Graph() {
  const [nodes, setNodes] = useState(loadGraph);
  const [selected, setSelected] = useState(nodes[0].id);
  const current = nodes.find(({ id }) => id === selected);
  const update = (changes) => {
    const next = editNode(nodes, selected, changes);
    setNodes(next);
    saveGraph(next);
  };

  return h("section", { "aria-labelledby": "graph-heading" },
    h("h2", { id: "graph-heading" }, "Workflow graph"),
    h("div", { className: "graph" }, nodes.map((node) => h("button", {
      key: node.id, type: "button", "aria-pressed": node.id === selected,
      style: { gridColumn: node.x + 1, gridRow: node.y + 1 },
      onClick: () => setSelected(node.id),
    }, node.label))),
    h("ul", { "aria-label": "Connections" }, graphEdges.map(([from, to]) =>
      h("li", { key: from }, `${from} to ${to}`),
    )),
    h("label", {}, "Node label", h("input", {
      value: current.label, onChange: (event) => update({ label: event.currentTarget.value }),
    })),
    h("button", { type: "button", onClick: () => update({ y: 1 - current.y }) }, "Move selected node"),
    h("p", { role: "status" }, `Row ${current.y + 1}, column ${current.x + 1}`),
  );
}

function DecisionTable() {
  const [rules, setRules] = useState(initialRules);
  const [result, setResult] = useState({ error: "", status: "" });
  const update = (next) => {
    setRules(next);
    setResult({ error: "", status: "" });
  };
  const change = (index, changes) => update(rules.map((rule, offset) =>
    index === offset ? { ...rule, ...changes } : rule,
  ));
  const save = (event) => {
    event.preventDefault();
    const error = ruleError(rules);
    setResult({ error, status: error ? "" : `${rules.length} rules saved.` });
  };

  return h("section", { "aria-labelledby": "rules-heading" },
    h("h2", { id: "rules-heading" }, "Decision table"),
    h("form", { onSubmit: save },
      h("table", {}, h("thead", {}, h("tr", {}, h("th", {}, "Condition"), h("th", {}, "Allow"))),
        h("tbody", {}, rules.map((rule, index) => h("tr", { key: index },
          h("td", {}, h("input", {
            "aria-label": `Rule ${index + 1} condition`,
            value: rule.status,
            onChange: (event) => change(index, { status: event.currentTarget.value }),
          })),
          h("td", {}, h("input", {
            type: "checkbox", "aria-label": `Rule ${index + 1} allow`,
            checked: rule.allow,
            onChange: (event) => change(index, { allow: event.currentTarget.checked }),
          })),
        ))),
      ),
      h("button", {
        type: "button", onClick: () => update([...rules, { status: "", allow: false }]),
      }, "Add rule"),
      h("button", { type: "submit" }, "Save rules"),
    ),
    h("p", { role: "alert" }, result.error),
    h("p", { role: "status" }, result.status),
  );
}

function Monitoring() {
  const [series, setSeries] = useState("active");
  const [error, setError] = useState("");
  return h("section", { "aria-labelledby": "monitor-heading" },
    h("h2", { id: "monitor-heading" }, "Monitoring"),
    h("div", { className: "field" },
      h("label", { htmlFor: "monitor-series" }, "Series"),
      h("select", {
        id: "monitor-series", value: series, onChange: (event) => setSeries(event.currentTarget.value),
      }, h("option", { value: "active" }, "Active"), h("option", { value: "failed" }, "Failed")),
    ),
    h("ul", { "aria-label": "Metric samples" }, monitoring.samples.map((sample) =>
      h("li", { key: sample.time }, `${sample.time}s · ${sample[series]}`),
    )),
    h("button", { type: "button", onClick: () => setError(monitoring.refreshError) }, "Refresh metrics"),
    h("p", { role: "alert" }, error ? `Refresh failed (${error}).` : ""),
  );
}

export { Graph, DecisionTable, Monitoring };
