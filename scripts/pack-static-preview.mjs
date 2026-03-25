/**
 * Compacta `out/` (gerada por `npm run build:static`) em
 * `zappelin-static-preview.zip` na raiz do projeto.
 *
 * Uso: npm run pack:preview (ou build:static + este script)
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import process from "node:process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");
const outDir = path.join(root, "out");
const zipPath = path.join(root, "zappelin-static-preview.zip");

if (!fs.existsSync(path.join(outDir, "index.html"))) {
  console.error(
    "Pasta `out/` em falta ou incompleta. Corre primeiro: npm run build:static"
  );
  process.exit(1);
}

if (fs.existsSync(zipPath)) {
  fs.rmSync(zipPath, { force: true });
}

function psQuote(s) {
  return s.replace(/'/g, "''");
}

if (process.platform === "win32") {
  // Compress-Archive com '\*' em LiteralPath falha silenciosamente; .NET ZipFile é fiável.
  const ps = `
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory(
  '${psQuote(outDir)}',
  '${psQuote(zipPath)}',
  [System.IO.Compression.CompressionLevel]::Optimal,
  $false
)
`.trim();
  const r = spawnSync("powershell.exe", ["-NoProfile", "-Command", ps], {
    encoding: "utf8",
  });
  if (r.status !== 0) {
    console.error(r.stderr || r.stdout || "PowerShell falhou");
    process.exit(r.status ?? 1);
  }
} else {
  const r = spawnSync("zip", ["-r", "-q", zipPath, "."], {
    cwd: outDir,
    stdio: "inherit",
  });
  if (r.status !== 0) {
    process.exit(r.status ?? 1);
  }
}

if (!fs.existsSync(zipPath)) {
  console.error("O ZIP não foi criado. Verifica permissões e espaço em disco.");
  process.exit(1);
}

console.log("ZIP de preview estático criado:", zipPath);
console.log("Envia este ficheiro ou descompacta e serve a pasta `out/` com qualquer servidor HTTP.");
