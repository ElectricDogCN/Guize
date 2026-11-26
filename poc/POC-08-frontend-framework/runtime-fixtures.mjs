import scenarios from "./scenarios.json";

const input = (id) => scenarios.find((scenario) => scenario.id === id).inputs;
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
