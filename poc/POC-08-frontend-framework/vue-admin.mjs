import { h, ref } from "vue";
import {
  editNode, graphEdges, initialRules, loadGraph, monitoring, ruleError, saveGraph,
} from "./scenario-models.mjs";

const Graph = {
  setup() {
    const nodes = ref(loadGraph());
    const selected = ref(nodes.value[0].id);
    const update = (changes) => {
      nodes.value = editNode(nodes.value, selected.value, changes);
      saveGraph(nodes.value);
    };

    return () => {
      const current = nodes.value.find(({ id }) => id === selected.value);
      return h("section", { "aria-labelledby": "graph-heading" }, [
        h("h2", { id: "graph-heading" }, "Workflow graph"),
        h("div", { class: "graph" }, nodes.value.map((node) => h("button", {
          key: node.id, type: "button", "aria-pressed": node.id === selected.value,
          style: { gridColumn: node.x + 1, gridRow: node.y + 1 },
          onClick: () => { selected.value = node.id; },
        }, node.label))),
        h("ul", { "aria-label": "Connections" }, graphEdges.map(([from, to]) =>
          h("li", { key: from }, `${from} to ${to}`),
        )),
        h("label", {}, ["Node label", h("input", {
          value: current.label, onInput: (event) => update({ label: event.currentTarget.value }),
        })]),
        h("button", {
          type: "button", onClick: () => update({ y: 1 - current.y }),
        }, "Move selected node"),
        h("p", { role: "status" }, `Row ${current.y + 1}, column ${current.x + 1}`),
      ]);
    };
  },
};

const DecisionTable = {
  setup() {
    const rules = ref(initialRules);
    const result = ref({ error: "", status: "" });
    const update = (next) => {
      rules.value = next;
      result.value = { error: "", status: "" };
    };
    const change = (index, changes) => update(rules.value.map((rule, offset) =>
      index === offset ? { ...rule, ...changes } : rule,
    ));
    const save = (event) => {
      event.preventDefault();
      const error = ruleError(rules.value);
      result.value = { error, status: error ? "" : `${rules.value.length} rules saved.` };
    };

    return () => h("section", { "aria-labelledby": "rules-heading" }, [
      h("h2", { id: "rules-heading" }, "Decision table"),
      h("form", { onSubmit: save }, [
        h("table", {}, [
          h("thead", {}, [h("tr", {}, [h("th", {}, "Condition"), h("th", {}, "Allow")])]),
          h("tbody", {}, rules.value.map((rule, index) => h("tr", { key: index }, [
            h("td", {}, [h("input", {
              "aria-label": `Rule ${index + 1} condition`, value: rule.status,
              onInput: (event) => change(index, { status: event.currentTarget.value }),
            })]),
            h("td", {}, [h("input", {
              type: "checkbox", "aria-label": `Rule ${index + 1} allow`, checked: rule.allow,
              onChange: (event) => change(index, { allow: event.currentTarget.checked }),
            })]),
          ]))),
        ]),
        h("button", {
          type: "button", onClick: () => update([...rules.value, { status: "", allow: false }]),
        }, "Add rule"),
        h("button", { type: "submit" }, "Save rules"),
      ]),
      h("p", { role: "alert" }, result.value.error),
      h("p", { role: "status" }, result.value.status),
    ]);
  },
};

const Monitoring = {
  setup() {
    const series = ref("active");
    const error = ref("");
    return () => h("section", { "aria-labelledby": "monitor-heading" }, [
      h("h2", { id: "monitor-heading" }, "Monitoring"),
      h("div", { class: "field" }, [
        h("label", { for: "monitor-series" }, "Series"),
        h("select", {
          id: "monitor-series",
          value: series.value,
          onChange: (event) => { series.value = event.currentTarget.value; },
        }, [h("option", { value: "active" }, "Active"), h("option", { value: "failed" }, "Failed")]),
      ]),
      h("ul", { "aria-label": "Metric samples" }, monitoring.samples.map((sample) =>
        h("li", { key: sample.time }, `${sample.time}s · ${sample[series.value]}`),
      )),
      h("button", {
        type: "button", onClick: () => { error.value = monitoring.refreshError; },
      }, "Refresh metrics"),
      h("p", { role: "alert" }, error.value ? `Refresh failed (${error.value}).` : ""),
    ]);
  },
};

export { Graph, DecisionTable, Monitoring };
