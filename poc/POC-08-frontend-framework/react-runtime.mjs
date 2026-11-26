import { createElement as h, useEffect, useRef, useState } from "react";
import {
  attachFixtureStream, defineFixturePlayer, permissions, player, theme, themeTokens,
} from "./runtime-fixtures.mjs";

defineFixturePlayer();

function Stream() {
  const [state, setState] = useState({ events: [], reconnects: 0 });
  useEffect(() => attachFixtureStream(setState), []);
  return h("section", { "aria-labelledby": "stream-heading" },
    h("h2", { id: "stream-heading" }, "Event stream"),
    h("p", { role: "status" }, `Reconnects: ${state.reconnects}`),
    h("ol", {}, state.events.map(({ sequence, status }) =>
      h("li", { key: sequence }, `${sequence} · ${status}`),
    )),
  );
}

function Player() {
  const widget = useRef(null);
  const [status, setStatus] = useState("mounted");
  useEffect(() => {
    const element = widget.current;
    const update = (event) => setStatus(event.detail.status);
    element.addEventListener("fixture-player-status", update);
    return () => element.removeEventListener("fixture-player-status", update);
  }, []);
  return h("section", { "aria-labelledby": "player-heading" },
    h("h2", { id: "player-heading" }, "Playback component"),
    h(player.component, { ref: widget, "asset-id": player.assetId }),
    h("p", { role: "status" }, `Playback: ${status}`),
  );
}

function Responsive() {
  const [detail, setDetail] = useState(false);
  return h("section", { "aria-labelledby": "mobile-heading" },
    h("h2", { id: "mobile-heading" }, "Responsive actions"),
    h("div", { className: "responsive-actions" },
      h("button", {
        type: "button", onClick: () => setDetail(true), disabled: detail,
      }, "Open sample"),
      h("button", {
        type: "button", onClick: () => setDetail(false), disabled: !detail,
      }, "Back to samples"),
    ),
    h("p", { role: "status" }, detail ? "Sample details" : "Sample list"),
  );
}

function Permissions() {
  const [id, setId] = useState(permissions.subjects[0].id);
  const [action, setAction] = useState("read");
  const subject = permissions.subjects.find((item) => item.id === id);
  return h("section", { "aria-labelledby": "permission-heading" },
    h("h2", { id: "permission-heading" }, "Subject visibility"),
    h("div", { className: "field" },
      h("label", { htmlFor: "fixture-subject" }, "Sample subject"),
      h("select", { id: "fixture-subject", value: id, onChange: (event) => {
        setId(event.currentTarget.value);
        setAction("read");
      } }, permissions.subjects.map((item) => h("option", { key: item.id, value: item.id }, item.id))),
    ),
    permissions.actions.filter((item) => subject.actions.includes(item)).map((item) =>
      h("button", { type: "button", key: item, onClick: () => setAction(item) }, item),
    ),
    action === "edit" && h("label", {}, "Sample title", h("input", { defaultValue: "Asset" })),
    h("p", { role: "status" }, `Current view: ${action}`),
  );
}

function Theme() {
  const [name, selectTheme] = useState("light");
  return h("section", { "aria-labelledby": "theme-heading" },
    h("h2", { id: "theme-heading" }, "Theme preview"),
    Object.keys(theme.themes).map((item) =>
      h("button", {
        key: item, type: "button", "aria-pressed": item === name, onClick: () => selectTheme(item),
      }, item),
    ),
    h("p", { className: "sample-surface", style: themeTokens(name) }, "Sample surface"),
  );
}

export { Stream, Player, Responsive, Permissions, Theme };
