import path from "node:path";
import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/v1": "http://127.0.0.1:5000",
      "/health": "http://127.0.0.1:5000",
    },
  },
  build: {
    outDir: path.resolve(__dirname, "../backend/build"),
    emptyOutDir: true,
    sourcemap: true,
  },
});
