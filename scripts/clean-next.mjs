import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");

function rm(p) {
  try {
    fs.rmSync(p, { recursive: true, force: true });
    console.log("removed", path.relative(root, p) || p);
  } catch {
    /* ok */
  }
}

/** Pastas que o Next / bundlers usam; apagar evita chunks 404 e tela branca no dev. */
const paths = [
  path.join(root, ".next"),
  path.join(root, "node_modules", ".cache"),
  path.join(root, ".turbo"),
  path.join(root, "out"),
];

for (const p of paths) {
  rm(p);
}

console.log("Cache Next limpo. Suba o dev de novo (ex.: npm run dev).");
