import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import { fixtureEvents } from "./fixture-events.mjs";

export default defineConfig(({ mode }) => {
  const candidate = ["react", "vue"].includes(mode) ? mode : null;
  return {
    base: "./",
    plugins: [fixtureEvents],
    build: {
      manifest: true,
      outDir: candidate ? "dist/" + candidate : "dist",
      rollupOptions: {
        input: candidate ? fileURLToPath(new URL(candidate + ".html", import.meta.url)) : undefined,
      },
    },
  };
});
