import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

// The Application UI talks to the Python backend (`oh web` /
// `python -m openharness.web`) over WebSocket at /ws. In dev we proxy
// /ws (and /api, for future REST endpoints) to the backend port so the
// frontend can keep using same-origin URLs.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const backendTarget = env.VITE_OH_BACKEND_URL || "http://127.0.0.1:8765";

  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "./src"),
      },
    },
    server: {
      port: 5173,
      proxy: {
        "/ws": {
          target: backendTarget,
          ws: true,
        },
        "/api": {
          target: backendTarget,
        },
      },
    },
  };
});
