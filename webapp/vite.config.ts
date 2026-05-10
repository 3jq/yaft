import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  // Root-relative asset paths so the same build works whether the page is
  // served at / (Telegram WebViews are happiest with bare-host URLs) or at
  // /app/ (kept for backwards compatibility).
  base: "/",
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  build: { outDir: "dist", emptyOutDir: true },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["src/test-setup.ts"],
  },
});
