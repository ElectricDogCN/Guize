import { createApp, h, reactive, ref } from "vue";
import { Graph, DecisionTable, Monitoring } from "./vue-admin.mjs";
import {
  condition, firstVisibleRow, formResult, initialForm, listRows, rowCount, rowHeight,
} from "./comparison.mjs";

const AssetList = {
  setup() {
    const first = ref(0);
    const selected = ref("");
    return () => h("section", { "aria-labelledby": "asset-heading" }, [
      h("h2", { id: "asset-heading" }, "Asset list"),
      h("div", {
        class: "asset-list", tabindex: 0, "aria-label": "Assets",
        onScroll: (event) => { first.value = firstVisibleRow(event.currentTarget.scrollTop); },
      }, [
        h("div", { class: "asset-spacer", style: { height: `${rowCount * rowHeight}px` } }, [
          h("div", { class: "asset-window", style: { top: `${first.value * rowHeight}px` } },
            listRows(first.value).map((row) => h("button", {
              key: row.id, type: "button", "data-asset": row.id,
              "aria-pressed": row.id === selected.value, onClick: () => { selected.value = row.id; },
            }, `${row.title} · ${row.status}`)),
          ),
        ]),
      ]),
      h("p", { "aria-live": "polite" },
        selected.value ? `Selected ${selected.value}` : "No asset selected",
      ),
    ]);
  },
};

const SourceForm = {
  setup() {
    const values = reactive({ ...initialForm });
    const result = ref({ error: "", message: "" });
    const update = (event) => {
      const { name, value } = event.currentTarget;
      values[name] = value;
      result.value = { error: "", message: "" };
    };
    return () => h("section", { "aria-labelledby": "form-heading" }, [
      h("h2", { id: "form-heading" }, "Source form"),
      h("form", {
        novalidate: true,
        onSubmit: (event) => {
          event.preventDefault();
          result.value = formResult(values);
        },
      }, [
        h("div", { class: "field" }, [
          h("label", { for: "source-type" }, "Source"),
          h("select", { id: "source-type", name: "source", value: values.source, onChange: update }, [
          h("option", { value: "local" }, "Local"),
          h("option", { value: "remote" }, "Remote"),
        ])]),
        h("label", {}, ["Retry limit", h("input", {
          name: "retryLimit", type: "number", min: 0, value: values.retryLimit, onInput: update,
        })]),
        values.source === condition.when ? h("label", {}, ["Endpoint", h("input", {
          name: condition.field, required: true, value: values[condition.field], onInput: update,
        })]) : null,
        h("button", { type: "submit" }, "Save source"),
      ]),
      h("p", { role: "alert" }, result.value.error),
      h("p", { role: "status" }, result.value.message),
    ]);
  },
};

createApp({
  render: () => h("div", {}, [
    h("h1", {}, "Vue comparison"), h(AssetList), h(SourceForm),
    h(Graph), h(DecisionTable), h(Monitoring),
  ]),
}).mount("#app");
