import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/statements": "http://127.0.0.1:8000",
      "/auth": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
