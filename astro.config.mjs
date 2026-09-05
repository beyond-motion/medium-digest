import { defineConfig } from "astro/config";

export default defineConfig({
  base: "/medium-digest/",
  output: "static",
  site: process.env.SITE_URL || "https://beyond-motion.github.io/medium-digest/",
});
