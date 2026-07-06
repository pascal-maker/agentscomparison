import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(here, "..");
const configPath = resolve(projectRoot, ".vercel", "output", "config.json");
const serverEntryPath = resolve(projectRoot, ".vercel", "output", "functions", "__server.func", "index.mjs");
const chatHtmlPath = resolve(projectRoot, "public", "index.html");

let config;
try {
  config = JSON.parse(await readFile(configPath, "utf8"));
} catch (error) {
  if (error?.code === "ENOENT") {
    console.log("[patch-vercel-root] skipped: no Vercel build output");
    process.exit(0);
  }
  throw error;
}

const rootRoute = config.routes?.find((route) => route.src === "/" && route.dest === "/index");
if (!rootRoute) {
  throw new Error("[patch-vercel-root] expected generated route '/' -> '/index'");
}

rootRoute.dest = "/";
await writeFile(configPath, JSON.stringify(config, null, 2) + "\n");

const chatHtml = await readFile(chatHtmlPath, "utf8");
const serverEntry = await readFile(serverEntryPath, "utf8");
const original = "var GET__default = handleHomePageRequest;";
const replacement = `var GET__default = () => new Response(${JSON.stringify(chatHtml)}, { headers: { "cache-control": "public, max-age=0, must-revalidate", "content-type": "text/html; charset=utf-8" } });`;

if (!serverEntry.includes(original)) {
  throw new Error("[patch-vercel-root] expected generated root handler assignment");
}

await writeFile(serverEntryPath, serverEntry.replace(original, replacement));
console.log("[patch-vercel-root] rewrote '/' route to the chat page");
