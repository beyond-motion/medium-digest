import { defineConfig } from "astro/config";

export default defineConfig({
  output: "static",
  base: "/medium-digest/",
  site: process.env.SITE_URL || "https://beyond-motion.github.io/medium-digest/",
});
