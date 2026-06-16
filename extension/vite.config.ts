import { defineConfig } from "vite";
import { crx } from "@crxjs/vite-plugin";
import manifest from "./manifest.json";
import manifestFirefox from "./manifest.firefox.json";

export default defineConfig(({ mode }) => ({
  plugins: [crx({ manifest: mode === "firefox" ? manifestFirefox : manifest })],
  build: {
    outDir: mode === "firefox" ? "dist-firefox" : "dist-chrome",
    emptyOutDir: true,
  },
}));
