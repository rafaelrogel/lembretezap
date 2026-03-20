/**
 * Liberta a porta pedida encerrando **node** que a escuta (evita Next noutra porta).
 * Windows: netstat + taskkill. macOS/Linux: lsof + kill (se existir).
 */
import { execSync } from "node:child_process";
import process from "node:process";

const port = process.argv[2] || "3000";

function killWin32() {
  let netstat;
  try {
    netstat = execSync(`netstat -ano | findstr ":${port}"`, {
      encoding: "utf8",
      stdio: ["pipe", "pipe", "ignore"],
    });
  } catch {
    return;
  }
  const pids = new Set();
  for (const line of netstat.split("\n")) {
    const m = line.match(/\sLISTENING\s+(\d+)\s*$/i);
    if (m) pids.add(m[1]);
  }
  for (const pid of pids) {
    try {
      const task = execSync(`tasklist /FI "PID eq ${pid}" /NH`, {
        encoding: "utf8",
        stdio: ["pipe", "pipe", "ignore"],
      });
      if (!/node\.exe/i.test(task)) continue;
      execSync(`taskkill /PID ${pid} /F`, { stdio: "inherit" });
      console.log(`Encerrado node PID ${pid} (porta ${port}).`);
    } catch {
      /* ignorar */
    }
  }
}

function killUnix() {
  try {
    const out = execSync(`lsof -ti:${port}`, {
      encoding: "utf8",
      stdio: ["pipe", "pipe", "ignore"],
    }).trim();
    if (!out) return;
    const pids = out.split(/\s+/).filter(Boolean);
    for (const pid of pids) {
      try {
        execSync(`kill -9 ${pid}`);
        console.log(`Encerrado PID ${pid} (porta ${port}).`);
      } catch {
        /* ignorar */
      }
    }
  } catch {
    /* sem lsof ou porta livre */
  }
}

function main() {
  if (process.platform === "win32") killWin32();
  else killUnix();
}

main();
