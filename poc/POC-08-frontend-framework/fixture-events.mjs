import { readFileSync } from "node:fs";

const cases = JSON.parse(readFileSync(new URL("./scenarios.json", import.meta.url), "utf8"));
const fixture = cases.find(({ id }) => id === "sse_websocket_equivalent").inputs;

function events(request, response, next) {
  if (request.url !== "/fixture-events" || request.method !== "GET") return next();
  const continuation = request.headers["last-event-id"] === String(fixture.disconnectAfter);
  const messages = continuation ? fixture.events : fixture.events.slice(0, fixture.disconnectAfter);
  response.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-store" });
  response.write("retry: 50\n\n");
  for (const item of messages) {
    response.write(`id: ${item.sequence}\ndata: ${JSON.stringify(item)}\n\n`);
  }
  response.end();
}

export const fixtureEvents = {
  name: "guize-frontend-comparison-events",
  configureServer(server) {
    server.middlewares.use(events);
  },
  configurePreviewServer(server) {
    server.middlewares.use(events);
  },
};
