import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import { fixtureEvents } from "./fixture-events.mjs";

const titles = { react: "React", vue: "Vue" };
const sample = fileURLToPath(new URL("./scenarios.json", import.meta.url)).replaceAll("\\", "/");

export default defineConfig(({ mode }) => {
  const candidate = Object.hasOwn(titles, mode) ? mode : null;
  const entry = candidate ?? "react";
  return {
    base: "./",
    plugins: [
      fixtureEvents,
      {
        name: "guize-comparison-entry",
        enforce: "pre",
        transform(source, id) {
          if (id !== sample) return;
          const { scenarios } = JSON.parse(source);
          return JSON.stringify({
            scenarios: scenarios.map(({ scenarioId, arguments: { steps, ...inputs } }) =>
              ({ scenarioId, arguments: inputs }),
            ),
          });
        },
        transformIndexHtml: {
          order: "pre",
          handler(html) {
            return html.replace("{{framework}}", titles[entry]).replace("{{entry}}", entry);
          },
        },
      },
    ],
    build: {
      manifest: true,
      outDir: candidate ? "dist/" + candidate : "dist",
    },
  };
});
