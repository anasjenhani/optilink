import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// En développement, /api et /admin sont relayés vers Django (port 8000).
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/admin": "http://localhost:8000",
      "/static": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
  },
});
