import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The only place the backend URL appears for development.
// Override with VITE_DEV_API_TARGET in .env.local if your backend runs elsewhere.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_DEV_API_TARGET || "http://localhost:8000";

  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": {
          target: apiTarget,
          changeOrigin: true,
        },
      },
    },
  };
});
