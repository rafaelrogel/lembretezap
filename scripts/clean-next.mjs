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

rm(path.join(root, ".next"));
rm(path.join(root, "node_modules", ".cache"));
