/**
 * Gera `zappelin-vercel-site/` (cópia só do Next.js) e `zappelin-vercel-site.zip`
 * na raiz do repo, para teste na Vercel sem backend Python.
 *
 * Uso: node scripts/pack-zappelin-website.mjs
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import process from "node:process";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(__dirname, "..");
const outDir = path.join(root, "zappelin-vercel-site");
const zipPath = path.join(root, "zappelin-vercel-site.zip");

const DIRS = ["app", "components", "public"];
const FILES = [
  "package.json",
  "package-lock.json",
  "next.config.js",
  "tsconfig.json",
  "tailwind.config.ts",
  "postcss.config.js",
];

function removeOutDir() {
  if (!fs.existsSync(outDir)) return;
  try {
    fs.rmSync(outDir, { recursive: true, force: true });
  } catch {
    if (process.platform === "win32") {
      spawnSync("cmd.exe", ["/c", "rd", "/s", "/q", outDir], { stdio: "inherit" });
    }
    if (fs.existsSync(outDir)) {
      console.error(
        "Não foi possível apagar zappelin-vercel-site (ficheiros em uso?). Fecha o IDE/terminal nessa pasta, apaga a pasta manualmente e volta a correr o script."
      );
      process.exit(1);
    }
  }
}

function main() {
  removeOutDir();
  fs.mkdirSync(outDir, { recursive: true });

  for (const d of DIRS) {
    const src = path.join(root, d);
    if (!fs.existsSync(src)) {
      console.error(`Em falta: ${src}`);
      process.exit(1);
    }
    fs.cpSync(src, path.join(outDir, d), { recursive: true });
  }

  for (const f of FILES) {
    const src = path.join(root, f);
    if (!fs.existsSync(src)) {
      console.warn(`Aviso: ficheiro opcional em falta, a saltar: ${f}`);
      continue;
    }
    fs.copyFileSync(src, path.join(outDir, f));
  }

  const tsconfigPath = path.join(outDir, "tsconfig.json");
  const ts = JSON.parse(fs.readFileSync(tsconfigPath, "utf8"));
  ts.exclude = ["node_modules", ".next"];
  fs.writeFileSync(tsconfigPath, JSON.stringify(ts, null, 2) + "\n");

  fs.writeFileSync(
    path.join(outDir, ".eslintrc.json"),
    JSON.stringify({ root: true, extends: "next/core-web-vitals" }, null, 2) + "\n"
  );

  const readme = `# Zappelin – site (Next.js)

Pacote **só do frontend** (landing) para testes na [Vercel](https://vercel.com).

## Vercel

1. Descompacta o ZIP ou usa a pasta \`zappelin-vercel-site\`.
2. **New Project** → importa esta pasta (upload ou novo repositório Git só com estes ficheiros).
3. Framework **Next.js**, Node 18+.
4. Comandos padrão: \`npm install\`, \`npm run build\`, \`npm start\` (produção).

## Local

\`\`\`bash
npm install
npm run build
npm start
\`\`\`

Não inclui backend Python nem \`bridge/\` — apenas o site Next.js.
`;
  fs.writeFileSync(path.join(outDir, "README.md"), readme);

  if (fs.existsSync(zipPath)) {
    fs.rmSync(zipPath, { force: true });
  }

  function psQuote(s) {
    return s.replace(/'/g, "''");
  }

  if (process.platform === "win32") {
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
      console.error("A pasta exportada está em:", outDir);
      process.exit(r.status ?? 1);
    }
  } else {
    const r = spawnSync("zip", ["-r", "-q", zipPath, "."], {
      cwd: outDir,
      encoding: "utf8",
      stdio: "inherit",
    });
    if (r.status !== 0) {
      console.error("Falha ao criar ZIP. Instala `zip` ou compacta manualmente:", outDir);
      process.exit(r.status ?? 1);
    }
  }

  if (!fs.existsSync(zipPath)) {
    console.error("O ZIP não foi criado.");
    process.exit(1);
  }

  console.log("Pronto:");
  console.log("  Pasta:", outDir);
  console.log("  ZIP:  ", zipPath);
}

main();
