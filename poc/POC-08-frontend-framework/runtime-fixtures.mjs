import fixture from "./scenarios.json";

const { scenarios } = fixture;

const input = (id) => scenarios.find((scenario) => scenario.scenarioId === id).arguments;
export const player = input("player_integration_equivalent");
export const permissions = input("permission_model_equivalent");
export const theme = input("design_token_equivalent");

export function attachFixtureStream(update) {
  const connection = new EventSource("/fixture-events");
  const events = [];
  let reconnects = 0;
  connection.onmessage = (message) => {
    const item = JSON.parse(message.data);
    if (events.some(({ sequence }) => sequence === item.sequence)) return;
    events.push(item);
    update({ events: [...events], reconnects });
    if (item.status === "ready") connection.close();
  };
  connection.onerror = () => {
    reconnects += 1;
    update({ events: [...events], reconnects });
  };
  return () => connection.close();
}

export function attachFixtureSocket(update) {
  const events = [];
  let socket;
  let reconnects = 0;
  let finished = false;
  const connect = () => {
    const url = new URL("/fixture-events/ws", location.href);
    url.protocol = location.protocol === "https:" ? "wss:" : "ws:";
    url.searchParams.set("since", String(events.at(-1)?.sequence ?? 0));
    socket = new WebSocket(url);
    socket.onmessage = (message) => {
      const item = JSON.parse(message.data);
      if (events.some(({ sequence }) => sequence === item.sequence)) return;
      events.push(item);
      update({ events: [...events], reconnects });
    };
    socket.onclose = (event) => {
      if (finished || event.code !== 1012) return;
      reconnects += 1;
      update({ events: [...events], reconnects });
      connect();
    };
  };
  connect();
  return () => {
    finished = true;
    socket?.close();
  };
}

export async function fixtureAuthorization(subject) {
  const query = new URLSearchParams({ subject, action: "edit" });
  const response = await fetch("/fixture-authorization?" + query);
  return response.status;
}

export function defineFixturePlayer() {
  if (customElements.get(player.component)) return;
  class FixturePlayer extends HTMLElement {
    connectedCallback() {
      if (this.shadowRoot) return;
      const root = this.attachShadow({ mode: "open" });
      const label = document.createElement("p");
      label.textContent = this.getAttribute("asset-id");
      root.append(label);
      for (const [index, name] of ["Signal ready", "Pause playback", "Signal unavailable"].entries()) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = name;
        button.addEventListener("click", () => {
          this.dispatchEvent(new CustomEvent("fixture-player-status", {
            detail: { status: player.events[index] },
          }));
        });
        root.append(button);
      }
    }
  }
  customElements.define(player.component, FixturePlayer);
}

export function themeTokens(name) {
  const { surface, text } = theme.themes[name];
  return { "--sample-surface": surface, "--sample-text": text, "--sample-space": `${theme.spacing}px` };
}
