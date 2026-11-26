import { readFileSync } from "node:fs";
import { WebSocketServer } from "ws";

const { scenarios } = JSON.parse(readFileSync(new URL("./scenarios.json", import.meta.url), "utf8"));
const fixture = scenarios.find(({ scenarioId }) => scenarioId === "sse_websocket_equivalent").arguments;
const permissionFixture = scenarios.find(({ scenarioId }) => scenarioId === "permission_model_equivalent").arguments;

function stage(reconnecting) {
  return reconnecting ? fixture.events : fixture.events.slice(0, fixture.disconnectAfter);
}

function requestFixture(request, response, next) {
  const url = new URL(request.url, "http://127.0.0.1");
  if (request.method !== "GET") return next();
  if (url.pathname === "/fixture-authorization") {
    const subject = permissionFixture.subjects.find(({ id }) => id === url.searchParams.get("subject"));
    const allowed = subject?.actions.includes(url.searchParams.get("action")) ?? false;
    response.writeHead(allowed ? 200 : 403, { "Cache-Control": "no-store" });
    response.end();
    return;
  }
  if (url.pathname !== "/fixture-events") return next();

  const reconnecting = request.headers["last-event-id"] === String(fixture.disconnectAfter);
  response.writeHead(200, { "Content-Type": "text/event-stream", "Cache-Control": "no-store" });
  response.write("retry: 50\n\n");
  for (const item of stage(reconnecting)) {
    response.write(`id: ${item.sequence}\ndata: ${JSON.stringify(item)}\n\n`);
  }
  response.end();
}

function register(server) {
  server.middlewares.use(requestFixture);
  const sockets = new WebSocketServer({ noServer: true });
  server.httpServer?.on("upgrade", (request, socket, head) => {
    const url = new URL(request.url, "http://127.0.0.1");
    if (url.pathname !== "/fixture-events/ws") return;
    const reconnecting = url.searchParams.get("since") === String(fixture.disconnectAfter);
    sockets.handleUpgrade(request, socket, head, (client) => {
      for (const item of stage(reconnecting)) client.send(JSON.stringify(item));
      client.close(reconnecting ? 1000 : 1012);
    });
  });
}

export const fixtureEvents = {
  name: "guize-frontend-comparison-events",
  configureServer: register,
  configurePreviewServer: register,
};
