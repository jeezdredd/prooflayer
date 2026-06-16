import { defineConfig } from "vite";
import { crx } from "@crxjs/vite-plugin";
import manifest from "./manifest.json";

export default defineConfig(({ mode }) => ({
  plugins: [crx({ manifest })],
  build: {
    outDir: mode === "firefox" ? "dist-firefox" : "dist-chrome",
    emptyOutDir: true,
  },
}));
