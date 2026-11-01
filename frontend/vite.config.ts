import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("/chart.js/") || id.includes("/react-chartjs-2/")) return "charts";
          if (id.includes("/react-router") || id.includes("/@remix-run/router/")) return "router";
          if (id.includes("/react-dom/") || id.includes("/react/")) return "react-vendor";
          if (id.includes("/react-hook-form/") || id.includes("/@hookform/") || id.includes("/zod/")) return "forms";
          return undefined;
        },
      },
    },
  },
});
