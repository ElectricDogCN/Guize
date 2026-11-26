import { h, onMounted, onUnmounted, ref } from "vue";
import {
  attachFixtureSocket, attachFixtureStream, defineFixturePlayer, fixtureAuthorization, permissions, player, theme, themeTokens,
} from "./runtime-fixtures.mjs";

defineFixturePlayer();

const StreamPanel = {
  props: ["heading", "headingId", "connect"],
  setup(props) {
    const state = ref({ events: [], reconnects: 0 });
    let disconnect;
    onMounted(() => { disconnect = props.connect((next) => { state.value = next; }); });
    onUnmounted(() => { disconnect?.(); });
    return () => h("section", { "aria-labelledby": props.headingId }, [
      h("h2", { id: props.headingId }, props.heading),
      h("p", { role: "status" }, `Reconnects: ${state.value.reconnects}`),
      h("ol", {}, state.value.events.map(({ sequence, status }) =>
        h("li", { key: sequence }, `${sequence} · ${status}`),
      )),
    ]);
  },
};

const Stream = {
  render: () => h("div", {}, [
    h(StreamPanel, { heading: "SSE stream", headingId: "sse-heading", connect: attachFixtureStream }),
    h(StreamPanel, { heading: "WebSocket stream", headingId: "ws-heading", connect: attachFixtureSocket }),
  ]),
};

const Player = {
  setup() {
    const widget = ref(null);
    const status = ref("mounted");
    const update = (event) => { status.value = event.detail.status; };
    let element;
    onMounted(() => {
      element = widget.value;
      element.addEventListener("fixture-player-status", update);
    });
    onUnmounted(() => element?.removeEventListener("fixture-player-status", update));
    return () => h("section", { "aria-labelledby": "player-heading" }, [
      h("h2", { id: "player-heading" }, "Playback component"),
      h(player.component, { ref: widget, "asset-id": player.assetId }),
      h("p", { role: "status" }, `Playback: ${status.value}`),
    ]);
  },
};

const Responsive = {
  setup() {
    const detail = ref(false);
    return () => h("section", { "aria-labelledby": "mobile-heading" }, [
      h("h2", { id: "mobile-heading" }, "Responsive actions"),
      h("div", { class: "responsive-actions" }, [
        h("button", {
          type: "button", onClick: () => { detail.value = true; }, disabled: detail.value,
        }, "Open sample"),
        h("button", {
          type: "button", onClick: () => { detail.value = false; }, disabled: !detail.value,
        }, "Back to samples"),
      ]),
      h("p", { role: "status" }, detail.value ? "Sample details" : "Sample list"),
    ]);
  },
};

const Permissions = {
  setup() {
    const id = ref(permissions.subjects[0].id);
    const action = ref("read");
    const serverStatus = ref(null);
    return () => {
      const subject = permissions.subjects.find((item) => item.id === id.value);
      return h("section", { "aria-labelledby": "permission-heading" }, [
        h("h2", { id: "permission-heading" }, "Subject visibility"),
        h("div", { class: "field" }, [
          h("label", { for: "fixture-subject" }, "Sample subject"),
          h("select", { id: "fixture-subject", value: id.value, onChange: (event) => {
            id.value = event.currentTarget.value;
            action.value = "read";
            serverStatus.value = null;
          } }, permissions.subjects.map((item) => h("option", { key: item.id, value: item.id }, item.id))),
        ]),
        ...permissions.actions.filter((item) => subject.actions.includes(item)).map((item) =>
          h("button", {
            type: "button", key: item, onClick: () => { action.value = item; },
          }, item),
        ),
        action.value === "edit" ? h("label", {}, ["Sample title", h("input", { value: "Asset" })]) : null,
        h("button", {
          type: "button", onClick: async () => { serverStatus.value = await fixtureAuthorization(id.value); },
        }, "Check sample edit capability"),
        h("p", {}, serverStatus.value ? "Server edit status " + serverStatus.value : ""),
        h("p", { role: "status" }, `Current view: ${action.value}`),
      ]);
    };
  },
};

const Theme = {
  setup() {
    const name = ref("light");
    return () => h("section", { "aria-labelledby": "theme-heading" }, [
      h("h2", { id: "theme-heading" }, "Theme preview"),
      ...Object.keys(theme.themes).map((item) =>
        h("button", {
          key: item, type: "button", "aria-pressed": item === name.value,
          onClick: () => { name.value = item; },
        }, item),
      ),
      h("p", { class: "sample-surface", style: themeTokens(name.value) }, "Sample surface"),
    ]);
  },
};

export { Stream, Player, Responsive, Permissions, Theme };
