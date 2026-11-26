import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";

export default defineConfig({
  build: {
    rollupOptions: {
      input: ["react.html", "vue.html"].map((page) =>
        fileURLToPath(new URL(page, import.meta.url)),
      ),
    },
  },
});
