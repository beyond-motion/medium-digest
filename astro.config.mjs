import { defineConfig } from "astro/config";

export default defineConfig({
  output: "static",
  site: process.env.SITE_URL || "https://beyond-motion.github.io/medium-digest/",
});
