#!/usr/bin/env node
import { spawnSync } from "node:child_process";
import path from "node:path";

const preload = path.join(process.cwd(), "scripts", "localhost-resolver.cjs");
const astroBin = path.join(process.cwd(), "node_modules", ".bin", "astro");

const steps = [
  ["npm", ["run", "index"]],
  ["node", ["-r", preload, astroBin, "check"]],
  ["node", ["-r", preload, astroBin, "build"]],
  [
    "./node_modules/.bin/wrangler",
    ["pages", "deploy", "dist", "--project-name", "medium-digest", "--branch", "main", "--commit-dirty=true"],
  ],
];

for (const [command, args] of steps) {
  const result = spawnSync(command, args, {
    cwd: process.cwd(),
    env: process.env,
    stdio: "inherit",
  });

  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}
