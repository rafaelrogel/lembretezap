"""God Mode: ativado por #<senha> no chat; depois o utilizador pode rodar #status, #users, etc.

Senha em GOD_MODE_PASSWORD (env). Quem enviar #<senha_correta> ativa god-mode para esse chat.
#<senha_errada> ou #cmd sem ter ativado = sem resposta (silêncio).
Nunca retornar secrets (tokens, API keys, connection strings).
"""

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from loguru import logger

# Senha de god-mode (env). Se vazia, god-mode desativado (qualquer # = silêncio).
GOD_MODE_PASSWORD_ENV = "GOD_MODE_PASSWORD"

# chat_id -> timestamp de ativação (para TTL)
_god_mode_activated: dict[str, float] = {}
_GOD_MODE_TTL_SECONDS = 24 * 3600  # 24 horas


def get_god_mode_password() -> str:
    """Senha definida na instalação (env)."""
    return (os.environ.get(GOD_MODE_PASSWORD_ENV) or "").strip()


def activate_god_mode(chat_id: str) -> None:
    """Marca este chat como tendo god-mode ativo (por TTL)."""
    _god_mode_activated[str(chat_id)] = time.time()


def is_god_mode_activated(chat_id: str) -> bool:
    """True se este chat ativou god-mode com a senha e ainda está dentro do TTL."""
    t = _god_mode_activated.get(str(chat_id))
    if t is None:
        return False
    if time.time() - t > _GOD_MODE_TTL_SECONDS:
        del _god_mode_activated[str(chat_id)]
        return False
    return True


def deactivate_god_mode(chat_id: str) -> None:
    """Desativa god-mode para este chat (ex.: comando #quit)."""
    _god_mode_activated.pop(str(chat_id), None)


def is_god_mode_password(content_after_hash: str) -> bool:
    """True se o texto após # corresponde à senha de god-mode."""
    pwd = get_god_mode_password()
    if not pwd:
        return False
    return (content_after_hash or "").strip() == pwd


# Comandos aceites: #cmd ou #cmd <arg> (case-insensitive)
_ADMIN_CMD_RE = re.compile(r"^\s*#(\w+)(?:\s+(.*))?\s*$", re.I)
_VALID_COMMANDS = frozenset({
    "status", "users", "paid", "cron", "server", "system", "ai", "painpoints",
    "injection", "add", "remove", "mute", "quit",
})


def parse_admin_command(text: str) -> str | None:
    """
    Se a mensagem for um comando admin (#cmd ou #cmd arg), retorna o cmd em minúsculas.
    Caso contrário retorna None.
    """
    if not text or not text.strip():
        return None
    m = _ADMIN_CMD_RE.match(text.strip())
    if not m:
        return None
    cmd = m.group(1).lower()
    return cmd if cmd in _VALID_COMMANDS else None


def parse_admin_command_arg(text: str) -> tuple[str | None, str]:
    """
    Retorna (cmd, arg) para #cmd ou #cmd <arg>. arg é o resto da linha (strip).
    Se não for comando válido, retorna (None, "").
    """
    if not text or not text.strip():
        return None, ""
    m = _ADMIN_CMD_RE.match(text.strip())
    if not m:
        return None, ""
    cmd = m.group(1).lower()
    arg = (m.group(2) or "").strip()
    return (cmd, arg) if cmd in _VALID_COMMANDS else (None, "")


def log_unauthorized(from_id: str, command: str) -> None:
    """Log de tentativa não autorizada (sem PII além do identificador do comando)."""
    logger.warning(
        "admin_unauthorized from={} cmd={} ts={}",
        from_id[:8] + "***" if len(from_id) > 8 else "***",
        command,
        int(time.time()),
    )


async def handle_admin_command(
    command: str,
    *,
    cron_store_path: Path | None = None,
    db_session_factory: Any = None,
    wa_channel: Any = None,
) -> str:
    """
    Executa o comando admin e retorna texto curto (1–2 telas).
    Nunca inclui secrets.
    """
    raw = (command or "").strip()
    cmd = raw.lstrip("#").strip().lower() if raw.startswith("#") else raw.lower()
    if not cmd or cmd not in _VALID_COMMANDS:
        return f"Comando desconhecido: #{command or '?'}\nComandos: #status #users #paid #cron #server #system #ai #painpoints #injection #add <nr> #remove <nr> #mute <nr> #quit"

    if cmd == "status":
        return _cmd_status()

    if cmd == "users":
        return await _cmd_users(db_session_factory)

    if cmd == "paid":
        return await _cmd_paid(db_session_factory)

    if cmd == "cron":
        return _cmd_cron(cron_store_path)

    if cmd == "server":
        return _cmd_server(cron_store_path=cron_store_path, wa_channel=wa_channel)

    if cmd == "system":
        return _cmd_system()

    if cmd == "ai":
        return _cmd_ai()

    if cmd == "painpoints":
        return _cmd_painpoints(cron_store_path)

    if cmd == "injection":
        return _cmd_injection()

    if cmd == "add":
        _, arg = parse_admin_command_arg(raw)
        if not arg:
            return "#add\nUso: #add <número de telefone>"
        from nanobot.utils.extra_allowed import add_extra_allowed
        digits = "".join(c for c in str(arg or "") if c.isdigit())
        if not digits:
            return "#add\nNúmero inválido."
        if add_extra_allowed(arg):
            return f"#add\nAdicionado: {digits}"
        return f"#add\nO número {digits} já estava na lista."

    if cmd == "remove":
        _, arg = parse_admin_command_arg(raw)
        if not arg:
            return "#remove\nUso: #remove <número de telefone>"
        from nanobot.utils.extra_allowed import remove_extra_allowed
        digits = "".join(c for c in str(arg or "") if c.isdigit())
        if not digits:
            return "#remove\nNúmero inválido."
        if remove_extra_allowed(arg):
            return f"#remove\nRemovido: {digits}"
        return f"#remove\nO número {digits} não estava na lista."

    # quit e mute são tratados no canal (WhatsApp) para enviar mensagem ao utilizador muted
    if cmd == "quit":
        return "God-mode desativado. (Use #<senha> para ativar de novo.)"
    if cmd == "mute":
        return "#mute\nUso: #mute <número de telefone> (tratado no canal)"

    return "?"


def _cmd_status() -> str:
    """Resumo rápido do sistema."""
    lines = [
        "#status",
        "God Mode ativo. Comandos: #users #paid #cron #server #system #ai #painpoints #injection",
        "#add <nr> #remove <nr> #mute <nr> #quit",
    ]
    return "\n".join(lines)


async def _cmd_users(db_session_factory: Any) -> str:
    """Total de usuários registrados."""
    if not db_session_factory:
        return "#users\nErro: DB não disponível."
    try:
        from backend.models_db import User
        db = db_session_factory()
        try:
            total = db.query(User).count()
            return f"#users\nTotal: {total} utilizadores registados."
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"admin #users failed: {e}")
        return "#users\nErro ao consultar DB."


async def _cmd_paid(db_session_factory: Any) -> str:
    """Total pagantes (critério: assinatura ativa – por definir no modelo)."""
    if not db_session_factory:
        return "#paid\nErro: DB não disponível."
    try:
        from backend.models_db import User
        db = db_session_factory()
        try:
            # Critério futuro: coluna subscription_active ou tabela payments
            total_users = db.query(User).count()
            paid = 0  # TODO: quando existir coluna/tabela de pagamento
            return f"#paid\nTotal pagantes: {paid} (critério: assinatura ativa – a definir)\nTotal users: {total_users}"
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"admin #paid failed: {e}")
        return "#paid\nErro ao consultar DB."


def _cmd_cron(cron_store_path: Path | None) -> str:
    """Quantidade de cron jobs e status (último run / next run)."""
    path = cron_store_path or (Path.home() / ".nanobot" / "cron" / "jobs.json")
    if not path.exists():
        return "#cron\n0 jobs (ficheiro não encontrado)."
    try:
        data = json.loads(path.read_text())
        jobs = data.get("jobs", [])
        total = len(jobs)
        enabled = sum(1 for j in jobs if j.get("enabled", True))
        lines = [f"#cron\nJobs: {total} (ativos: {enabled})"]
        for j in jobs[:10]:
            state = j.get("state", {})
            next_ms = state.get("nextRunAtMs")
            last_ms = state.get("lastRunAtMs")
            name = j.get("name", j.get("id", "?"))[:20]
            next_str = f"next: {_ms_to_short(next_ms)}" if next_ms else "next: -"
            last_str = f"last: {_ms_to_short(last_ms)}" if last_ms else "last: -"
            lines.append(f"  {name} | {next_str} | {last_str}")
        if total > 10:
            lines.append(f"  ... e mais {total - 10}")
        return "\n".join(lines)
    except Exception as e:
        logger.debug(f"admin #cron failed: {e}")
        return "#cron\nErro ao ler jobs."


def _ms_to_short(ms: int | None) -> str:
    if ms is None:
        return "-"
    try:
        t = ms / 1000
        if t < 60:
            return f"{int(t)}s"
        if t < 3600:
            return f"{int(t // 60)}m"
        if t < 86400:
            return f"{int(t // 3600)}h"
        return f"{int(t // 86400)}d"
    except Exception:
        return "-"


def _cmd_server(
    cron_store_path: Path | None = None,
    wa_channel: Any = None,
) -> str:
    """Snapshot atual + histórico 7 dias (RAM, CPU, disco, uptime, bridge, cron, entrega)."""
    lines = ["#server"]
    try:
        from backend.server_metrics import record_snapshot, get_historical
        from nanobot.config.loader import get_data_dir
    except ImportError:
        lines.append("Módulo server_metrics não disponível.")
        return "\n".join(lines)

    data_dir = get_data_dir()
    bridge_connected = getattr(wa_channel, "_connected", None) if wa_channel else None
    snapshot = record_snapshot(
        cron_store_path=cron_store_path,
        data_dir=data_dir,
        bridge_connected=bridge_connected,
    )

    if not snapshot:
        lines.append("Erro ao obter snapshot (psutil?).")
        return "\n".join(lines)

    def _uptime_str(secs: int) -> str:
        if secs < 60:
            return f"{secs}s"
        if secs < 3600:
            return f"{int(secs // 60)}m"
        return f"{int(secs // 3600)}h"

    # Snapshot "agora"
    lines.append("--- Snapshot ---")
    lines.append(
        f"RAM: {snapshot['ram_pct']}% usado | livre: {snapshot['ram_available_mb']:.0f}M | "
        f"swap: {snapshot['swap_used_mb']:.0f}/{snapshot['swap_total_mb']:.0f}M"
    )
    lines.append(f"CPU: {snapshot['cpu_pct']}% | load 1m: {snapshot['load_1m']}")
    lines.append(
        f"Disco: {snapshot['disk_pct']}% usado | livre: {snapshot['disk_free_mb']:.0f}M | "
        f"dados .nanobot: {snapshot['data_dir_mb']:.0f}M"
    )
    lines.append(f"Gateway uptime: {_uptime_str(snapshot['gateway_uptime_s'])}")
    bridge_st = "connected" if snapshot.get("bridge_connected") else "disconnected"
    lines.append(f"Bridge WhatsApp: {bridge_st}")
    lines.append(f"Cron: {snapshot['cron_jobs']} jobs | atrasados >60s: {snapshot['cron_delayed_60s']}")

    # Histórico 7 dias
    hist = get_historical(days=7)
    if hist:
        lines.append("")
        lines.append("--- Últimos 7 dias ---")
        prev_disk = None
        for h in hist:
            d = h.get("date", "?")
            ram = h.get("ram_max", 0)
            load = h.get("load_max", 0)
            spikes = h.get("load_spikes", 0)
            disk_mb = h.get("disk_mb", 0)
            restarts = h.get("gateway_restarts", 0)
            rec = h.get("bridge_reconnects", 0)
            skip = h.get("whatsapp_skipped", 0)
            unk = h.get("unknown_channel", 0)
            cron_del = h.get("cron_delayed_60s_max", 0)
            line = f"{d}: RAM max {ram}% | load max {load:.1f} | picos >1.5: {spikes}"
            if restarts:
                line += f" | gw restarts: {restarts}"
            if rec:
                line += f" | bridge reconn: {rec}"
            if skip or unk:
                line += f" | WA skip: {skip} | unk ch: {unk}"
            if cron_del:
                line += f" | cron atraso: {cron_del}"
            if disk_mb is not None and disk_mb > 0:
                delta = ""
                if prev_disk is not None:
                    ddelta = disk_mb - prev_disk
                    delta = f" (+{ddelta:.0f}M)" if ddelta > 0 else f" ({ddelta:.0f}M)"
                line += f" | dados {disk_mb:.0f}M{delta}"
            if disk_mb is not None and disk_mb > 0:
                prev_disk = disk_mb
            lines.append(line)

    return "\n".join(lines)


def _bytes_short(n: int) -> str:
    for u, s in [(1 << 30, "G"), (1 << 20, "M"), (1 << 10, "K")]:
        if n >= u:
            return f"{n / u:.1f}{s}"
    return f"{n}B"


def _cmd_system() -> str:
    """Erros últimos 60 min, latência média (estrutura; métricas a integrar)."""
    lines = ["#system"]
    # Placeholder: sem store de erros/latência ainda
    lines.append("Erros (60 min): N/A – configurar logging agregado")
    lines.append("Latência média: N/A – configurar métricas")
    return "\n".join(lines)


def _cmd_ai() -> str:
    """Uso de tokens por provedor (dia/7d, input/output, custo estimado)."""
    lines = ["#ai"]
    try:
        from backend.token_usage import get_usage_summary
        summary = get_usage_summary()
        if summary:
            lines.append(summary)
        else:
            lines.append("Nenhuma métrica de tokens registada (por dia/7d).")
    except ImportError:
        lines.append("Módulo token_usage não configurado. Tokens por provedor (DeepSeek, Mimo) a implementar.")
    except Exception as e:
        logger.debug(f"admin #ai failed: {e}")
        lines.append("Erro ao obter métricas de tokens.")
    return "\n".join(lines)


def _cmd_injection() -> str:
    """Tentativas de prompt injection por cliente: número, quantas, bloqueadas vs bem-sucedidas."""
    try:
        from backend.injection_guard import get_injection_stats
        stats = get_injection_stats()
        if not stats:
            return "#injection\nNenhuma tentativa de injection registada."
        lines = ["#injection", "Cliente | Total | Bloqueadas | Bem-sucedidas"]
        for s in stats[:20]:
            cid = s.get("chat_id", "?")
            total = s.get("total", 0)
            blocked = s.get("bloqueadas", 0)
            succeeded = s.get("bem_sucedidas", 0)
            lines.append(f"  {cid} | {total} | {blocked} | {succeeded}")
        if len(stats) > 20:
            lines.append(f"  ... e mais {len(stats) - 20} clientes")
        return "\n".join(lines)
    except Exception as e:
        logger.debug(f"admin #injection failed: {e}")
        return "#injection\nErro ao obter estatísticas."


def _cmd_painpoints(cron_store_path: Path | None) -> str:
    """Heurísticas: jobs atrasados + clientes para atendimento contactar."""
    lines = ["#painpoints"]
    path = cron_store_path or (Path.home() / ".nanobot" / "cron" / "jobs.json")
    now_ms = int(time.time() * 1000)
    atrasados = 0
    if path.exists():
        try:
            data = json.loads(path.read_text())
            for j in data.get("jobs", []):
                if not j.get("enabled", True):
                    continue
                next_run = (j.get("state") or {}).get("nextRunAtMs")
                if next_run and next_run < now_ms - 60_000:  # 1 min atraso
                    atrasados += 1
            if atrasados:
                lines.append(f"Jobs em atraso: {atrasados}")
            else:
                lines.append("Jobs em atraso: 0")
        except Exception:
            lines.append("Jobs: erro ao ler")
    else:
        lines.append("Jobs: ficheiro não encontrado")

    # Clientes para atendimento contactar (frustração/reclamação ou pedido explícito)
    try:
        from backend.painpoints_store import get_painpoints
        painpoints = get_painpoints()
        if painpoints:
            lines.append("")
            lines.append("Clientes para contactar (WhatsApp):")
            for p in painpoints[:15]:
                ph = p.get("digits") or p.get("phone_display", "?")
                reason = p.get("reason", "—")[:40]
                ts = p.get("timestamp", 0)
                from datetime import datetime
                dt = datetime.fromtimestamp(ts).strftime("%d/%m %H:%M") if ts else ""
                lines.append(f"  {ph} | {reason} | {dt}")
            if len(painpoints) > 15:
                lines.append(f"  ... e mais {len(painpoints) - 15}")
        else:
            lines.append("Clientes para contactar: 0")
    except Exception:
        lines.append("Clientes: erro ao ler")
    lines.append("Endpoints lentos: N/A – configurar APM")
    lines.append("Picos de erro: N/A – configurar agregado")
    return "\n".join(lines)
