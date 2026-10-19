import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const backend = env.VITE_API_PROXY_TARGET || "http://127.0.0.1:8000";
  return {
    plugins: [react()],
    server: {
      port: 5173,
      // Same-origin calls in dev; routes that MSW does not mock fall through to the backend.
      proxy: {
        "/api": backend,
        "/health": backend,
      },
    },
  };
});
