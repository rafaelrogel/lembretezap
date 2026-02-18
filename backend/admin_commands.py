"""God Mode: ativado por #<senha> no chat; depois o utilizador pode rodar #status, #users, etc.

Senha em GOD_MODE_PASSWORD (env). Quem enviar #<senha_correta> ativa god-mode para esse chat.
#<senha_errada> ou #cmd sem ter ativado = sem resposta (silêncio).
Nunca retornar secrets (tokens, API keys, connection strings).

Autorização alternativa: zapista.utils.admin_security.AdminSecurity (hash + sessão 24h).
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
    try:
        from zapista.clock_drift import get_effective_time
        _now = get_effective_time()
    except Exception:
        _now = time.time()
    _god_mode_activated[str(chat_id)] = _now


def is_god_mode_activated(chat_id: str) -> bool:
    """True se este chat ativou god-mode com a senha e ainda está dentro do TTL."""
    t = _god_mode_activated.get(str(chat_id))
    if t is None:
        return False
    try:
        from zapista.clock_drift import get_effective_time
        _now = get_effective_time()
    except Exception:
        _now = time.time()
    if _now - t > _GOD_MODE_TTL_SECONDS:
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
    "injection", "blocked", "lockout", "add", "remove", "mute", "quit", "msgs", "lembretes", "tz",
    "cleanup", "history",
    "hora", "time", "ativos", "erros", "diagnostico", "diag", "help", "comandos", "clientes", "jobs",
    "redis", "whatsapp",
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
    try:
        from zapista.clock_drift import get_effective_time
        _now = get_effective_time()
    except Exception:
        _now = time.time()
    logger.warning(
        "admin_unauthorized from={} cmd={} ts={}",
        from_id[:8] + "***" if len(from_id) > 8 else "***",
        command,
        int(_now),
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
    # Fix: split by space to get cmd, not the whole line
    # parse_admin_command_arg extracts (cmd, arg) if valid
    cmd_only, _ = parse_admin_command_arg(raw)
    
    # Fallback if parse_admin_command_arg returns None (invalid command)
    # logic below expects 'cmd' to be the command string or something to check against _VALID_COMMANDS
    if not cmd_only:
        # Tenta pegar só a primeira palavra para ver se é um comando conhecido
        parts = raw.split(None, 1)
        if parts:
            possible_cmd = parts[0].lstrip("#").lower()
            if possible_cmd in _VALID_COMMANDS:
                cmd = possible_cmd
            else:
                cmd = raw.lstrip("#").strip().lower() # keep old behavior for unknowns
        else:
             cmd = ""
    else:
        cmd = cmd_only
    if not cmd or cmd not in _VALID_COMMANDS:
        return (
            f"Comando desconhecido: #{command or '?'}\n"
            "Comandos: #hora #ativos #erros #diagnostico #help #clientes #jobs #redis #whatsapp | "
            "#status #users #cron #server #system #msgs #lembretes <nr> #tz <nr> #history <nr> | "
            "#add <nr> #remove <nr> #mute <nr> #lockout #cleanup #quit"
        )

    if cmd == "status":
        return _cmd_status()

    if cmd == "users":
        return await _cmd_users(db_session_factory)

    if cmd == "paid":
        return await _cmd_paid(db_session_factory)

    if cmd == "cron":
        _, arg = parse_admin_command_arg(raw)
        return _cmd_cron(cron_store_path, arg)

    if cmd == "lembretes":
        _, arg = parse_admin_command_arg(raw)
        return _cmd_lembretes(cron_store_path, arg)

    if cmd == "tz":
        _, arg = parse_admin_command_arg(raw)
        return await _cmd_tz(db_session_factory, arg)

    if cmd == "history":
        _, arg = parse_admin_command_arg(raw)
        return await _cmd_history(db_session_factory, arg)

    if cmd == "server":
        return _cmd_server(cron_store_path=cron_store_path, wa_channel=wa_channel)

    if cmd == "msgs":
        return _cmd_msgs()

    if cmd == "system":
        return _cmd_system(wa_channel=wa_channel)

    if cmd == "ai":
        return _cmd_ai()

    if cmd == "painpoints":
        return _cmd_painpoints(cron_store_path)

    if cmd == "injection":
        return _cmd_injection()

    if cmd == "blocked":
        return _cmd_blocked()

    if cmd == "lockout":
        return _cmd_lockout()

    if cmd == "cleanup":
        return await _cmd_cleanup(db_session_factory, cron_store_path)

    if cmd == "add":
        _, arg = parse_admin_command_arg(raw)
        if not arg:
            return "#add\nUso: #add <número de telefone>"
        from zapista.utils.extra_allowed import add_extra_allowed
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
        from zapista.utils.extra_allowed import remove_extra_allowed
        digits = "".join(c for c in str(arg or "") if c.isdigit())
        if not digits:
            return "#remove\nNúmero inválido."
        if remove_extra_allowed(arg):
            return f"#remove\nRemovido: {digits}"
        return f"#remove\nO número {digits} não estava na lista."

    if cmd in ("hora", "time"):
        return _cmd_hora()

    if cmd == "ativos":
        _, arg = parse_admin_command_arg(raw)
        return await _cmd_ativos(db_session_factory, arg)

    if cmd == "erros":
        _, arg = parse_admin_command_arg(raw)
        return _cmd_erros(arg)

    if cmd in ("diagnostico", "diag"):
        return await _cmd_diagnostico(cron_store_path, db_session_factory, wa_channel)

    if cmd in ("help", "comandos"):
        return _cmd_help()

    if cmd == "clientes":
        return await _cmd_clientes(db_session_factory)

    if cmd == "jobs":
        _, arg = parse_admin_command_arg(raw)
        return _cmd_jobs(cron_store_path, arg)

    if cmd == "redis":
        return _cmd_redis()

    if cmd == "whatsapp":
        return _cmd_whatsapp(wa_channel)

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
        "God Mode ativo. Comandos: #hora #ativos #erros #diagnostico #help #clientes #jobs #redis #whatsapp",
        "#users #cron [detalhado] #lembretes <nr> #tz <nr> #history <nr> #server #msgs #system #ai #painpoints",
        "#injection #blocked #lockout #cleanup #add <nr> #remove <nr> #mute <nr> #quit",
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


def _cmd_cron(cron_store_path: Path | None, arg: str = "") -> str:
    """Quantidade de cron jobs, por utilizador, duplicatas e atrasados (>60s). arg=detalhado → mais detalhes."""
    path = cron_store_path or (Path.home() / ".zapista" / "cron" / "jobs.json")
    if not path.exists():
        return "#cron\n0 jobs (ficheiro não encontrado)."
    try:
        data = json.loads(path.read_text())
        jobs = data.get("jobs", [])
        enabled_jobs = [j for j in jobs if j.get("enabled", True)]
        disabled_jobs = [j for j in jobs if not j.get("enabled", True)]
        total = len(jobs)
        enabled = len(enabled_jobs)
        try:
            from zapista.clock_drift import get_effective_time
            now_ms = int(get_effective_time() * 1000)
        except Exception:
            now_ms = int(time.time() * 1000)
        lines = [f"#cron\nJobs: {total} (ativos: {enabled}, desativados: {len(disabled_jobs)})"]

        # Jobs por utilizador (payload.to)
        by_user: dict[str, list] = {}
        for j in enabled_jobs:
            to = (j.get("payload") or {}).get("to") or "?"
            to_digits = _digits(to)
            key = to_digits if len(to_digits) >= 8 else to
            by_user.setdefault(key, []).append(j)

        # Alertas: utilizadores com muitos jobs
        for uid, ujobs in sorted(by_user.items(), key=lambda x: -len(x[1])):
            n = len(ujobs)
            suf = ""
            if n >= 10:
                suf = " (EXCESSIVO!)"
            elif n >= 5:
                suf = " (muitos)"
            lines.append(f"  ***{uid[-6:]}: {n}{suf}")

        # Duplicatas: mesma msg + schedule para o mesmo user
        dup_groups = 0
        for uid, ujobs in by_user.items():
            seen: dict[str, int] = {}
            for j in ujobs:
                p = j.get("payload") or {}
                s = j.get("schedule") or {}
                k = f"{str(p.get('message','')).lower()}|{s.get('kind')}|{s.get('everyMs')}|{s.get('expr')}|{s.get('atMs')}"
                seen[k] = seen.get(k, 0) + 1
            dup_groups += sum(1 for c in seen.values() if c > 1)
        if dup_groups:
            lines.append(f"⚠ Duplicatas: {dup_groups} grupo(s)")

        # Atrasados (>60s)
        atrasados = [
            j for j in enabled_jobs
            if (j.get("state") or {}).get("nextRunAtMs") and (j.get("state") or {}).get("nextRunAtMs", 0) < now_ms - 60_000
        ]
        if atrasados:
            lines.append(f"⚠ Atrasados >60s: {len(atrasados)}")
            for j in atrasados[:5]:
                name = (j.get("payload") or {}).get("message", j.get("id", "?"))[:25]
                to = (j.get("payload") or {}).get("to", "?")
                lines.append(f"    - {name} (***{_digits(to)[-6:]})")
            if len(atrasados) > 5:
                lines.append(f"    ... e mais {len(atrasados) - 5}")

        # Próxima execução: mínimo entre os ativos
        next_runs = [(j.get("state") or {}).get("nextRunAtMs") for j in enabled_jobs if (j.get("state") or {}).get("nextRunAtMs")]
        if next_runs:
            next_min = min(next_runs)
            lines.append(f"Próxima execução: {_ms_to_short(next_min)}")
        # Jobs que não executaram (atrasados >60s já listados acima)
        lines.append("")
        detalhado = (arg or "").strip().lower() == "detalhado"
        n_show = len(enabled_jobs) if detalhado else min(8, len(enabled_jobs))
        for j in enabled_jobs[:n_show]:
            state = j.get("state", {})
            next_ms = state.get("nextRunAtMs")
            last_ms = state.get("lastRunAtMs")
            payload = j.get("payload") or {}
            sched = j.get("schedule") or {}
            name = (payload.get("message", j.get("id", j.get("name", "?"))))[:40 if detalhado else 20]
            to = payload.get("to", "")
            next_str = f"next: {_ms_to_short(next_ms)}" if next_ms else "next: -"
            last_str = f"last: {_ms_to_short(last_ms)}" if last_ms else "last: -"
            atraso = " (atrasado)" if next_ms and next_ms < now_ms - 60_000 else ""
            if detalhado:
                kind = sched.get("kind", "?")
                job_id = j.get("id", "?")
                tz = sched.get("tz") or "-"
                lines.append(f"  [{job_id}] {name}")
                lines.append(f"    ***{_digits(to)[-6:]} | {kind} | tz={tz} | {next_str} | {last_str}{atraso}")
            else:
                lines.append(f"  {name} | ***{_digits(to)[-6:]}{atraso} | {next_str} | {last_str}")
        if enabled > n_show and not detalhado:
            lines.append(f"  ... e mais {enabled - n_show}")
        if detalhado and disabled_jobs:
            lines.append("")
            lines.append("--- Desativados ---")
            for j in disabled_jobs[:5]:
                payload = j.get("payload") or {}
                name = (payload.get("message") or j.get("id", "?"))[:30]
                lines.append(f"  [OFF] {name}")
            if len(disabled_jobs) > 5:
                lines.append(f"  ... e mais {len(disabled_jobs) - 5}")
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


def _digits(s: str) -> str:
    """Extrai só os dígitos."""
    return "".join(c for c in str(s or "") if c.isdigit())


def _to_matches_user(to: str | None, user_arg: str) -> bool:
    """True se payload.to corresponde ao utilizador (arg = número, ex. 5511999999999)."""
    if not user_arg or not to:
        return False
    arg_digits = _digits(user_arg)
    to_digits = _digits(to)
    if not arg_digits or len(arg_digits) < 8:
        return False
    return to_digits == arg_digits or to_digits.endswith(arg_digits) or arg_digits.endswith(to_digits)


def _cmd_lembretes(cron_store_path: Path | None, user_arg: str) -> str:
    """Lista lembretes de um utilizador por número. Detecta duplicatas (mesma msg + schedule)."""
    if not user_arg or len(_digits(user_arg)) < 8:
        return "#lembretes\nUso: #lembretes <número> (ex: #lembretes 5511999999999)"
    path = cron_store_path or (Path.home() / ".zapista" / "cron" / "jobs.json")
    if not path.exists():
        return "#lembretes\n0 jobs (ficheiro não encontrado)."
    try:
        data = json.loads(path.read_text())
        jobs = data.get("jobs", [])
        user_jobs = [
            j for j in jobs
            if j.get("enabled", True)
            and _to_matches_user((j.get("payload") or {}).get("to"), user_arg)
        ]
        if not user_jobs:
            return f"#lembretes\nUtilizador {_digits(user_arg)[-8:]}***: 0 lembretes ativos."
        lines = [f"#lembretes\nUtilizador ***{_digits(user_arg)[-6:]}: {len(user_jobs)} lembretes"]
        try:
            from zapista.clock_drift import get_effective_time
            now_ms = int(get_effective_time() * 1000)
        except Exception:
            now_ms = int(time.time() * 1000)
        seen_key: dict[str, int] = {}
        for i, j in enumerate(user_jobs, 1):
            payload = j.get("payload") or {}
            msg = (payload.get("message") or "?")[:40]
            sched = j.get("schedule") or {}
            kind = sched.get("kind", "?")
            next_ms = (j.get("state") or {}).get("nextRunAtMs")
            created_ms = j.get("createdAtMs") or 0
            dup_tag = ""
            key = f"{msg.lower()}|{kind}|{sched.get('everyMs')}|{sched.get('expr')}|{sched.get('atMs')}"
            seen_key[key] = seen_key.get(key, 0) + 1
            if seen_key[key] > 1:
                dup_tag = " [DUPLICADO]"
            sched_str = ""
            if kind == "every" and sched.get("everyMs"):
                s = sched["everyMs"] // 1000
                sched_str = f"a cada {s}s" if s < 3600 else f"a cada {s // 3600}h"
            elif kind == "cron" and sched.get("expr"):
                sched_str = sched["expr"]
            elif kind == "at" and sched.get("atMs"):
                try:
                    from datetime import datetime
                    dt = datetime.fromtimestamp(sched["atMs"] / 1000)
                    sched_str = dt.strftime("%d/%m %H:%M")
                except Exception:
                    sched_str = "pontual"
            next_str = _ms_to_short(next_ms) + " (atrasado)" if next_ms and next_ms < now_ms - 60_000 else _ms_to_short(next_ms)
            created_str = ""
            if created_ms:
                try:
                    from datetime import datetime
                    created_str = datetime.fromtimestamp(created_ms / 1000).strftime("%d/%m %H:%M")
                except Exception:
                    pass
            lines.append(f"{i}. {msg}{dup_tag}")
            lines.append(f"   Schedule: {sched_str} | próximo: {next_str} | criado: {created_str}")
        dup_count = sum(1 for c in seen_key.values() if c > 1)
        if dup_count:
            lines.append(f"\n⚠ {dup_count} grupo(s) com duplicatas")
        return "\n".join(lines)
    except Exception as e:
        logger.debug(f"admin #lembretes failed: {e}")
        return "#lembretes\nErro ao ler jobs."


async def _cmd_tz(db_session_factory: Any, user_arg: str) -> str:
    """Timezone e dados do utilizador."""
    if not user_arg or len(_digits(user_arg)) < 8:
        return "#tz\nUso: #tz <número> (ex: #tz 5511999999999)"
    digits = _digits(user_arg)
    try:
        from datetime import datetime
        try:
            from zapista.clock_drift import get_effective_time
            now_sec = int(get_effective_time())
        except Exception:
            now_sec = int(time.time())
        lines = [f"#tz\nUtilizador ***{digits[-6:]}"]

        if db_session_factory:
            db = db_session_factory()
            try:
                chat_id = f"{digits}@s.whatsapp.net"
                from backend.user_store import get_user_timezone
                from backend.timezone import format_utc_timestamp_for_user
                tz_iana = get_user_timezone(db, chat_id)
                lines.append(f"Timezone: {tz_iana}")
                hora_local = format_utc_timestamp_for_user(now_sec, tz_iana)
                from zoneinfo import ZoneInfo
                try:
                    z = ZoneInfo(tz_iana)
                    from datetime import datetime
                    dt = datetime.fromtimestamp(now_sec, tz=z)
                    lines.append(f"Hora local: {dt.strftime('%H:%M')} ({dt.strftime('%d/%m')})")
                except Exception:
                    lines.append(f"Hora local: {hora_local}")
            finally:
                db.close()

        if not db_session_factory:
            from backend.timezone import phone_to_default_timezone
            tz_iana = phone_to_default_timezone(f"{digits}@s.whatsapp.net")
            lines.append(f"Timezone (inferido): {tz_iana}")
            from backend.timezone import format_utc_timestamp_for_user
            hora_local = format_utc_timestamp_for_user(now_sec, tz_iana)
            lines.append(f"Hora local: {hora_local}")

        from datetime import datetime, timezone
        from zapista.clock_drift import get_drift_status
        drift = get_drift_status()
        server_now = datetime.fromtimestamp(drift["server_ts"], tz=timezone.utc)
        effective_now = datetime.fromtimestamp(drift["effective_ts"], tz=timezone.utc)
        
        lines.append(f"Hora servidor (UTC): {server_now.strftime('%H:%M:%S')} ({server_now.strftime('%d/%m')})")
        if drift["is_corrected"]:
            lines.append(f"⚠ Clock Drift: {drift['offset_seconds']:.1f}s (Corrigido)")
            lines.append(f"Hora efetiva (UTC): {effective_now.strftime('%H:%M:%S')}")
        else:
            lines.append(f"Clock Drift: {drift['offset_seconds']:.1f}s (OK)")

        return "\n".join(lines)
    except Exception as e:
        logger.debug(f"admin #tz failed: {e}")
        return "#tz\nErro ao obter timezone."


async def _cmd_history(db_session_factory: Any, user_arg: str) -> str:
    """Histórico de interações: ReminderHistory + AuditLog do utilizador."""
    if not user_arg or len(_digits(user_arg)) < 8:
        return "#history\nUso: #history <número> (ex: #history 5511999999999)"
    if not db_session_factory:
        return "#history\nErro: DB não disponível."
    digits = _digits(user_arg)
    try:
        from datetime import datetime, timedelta, timezone
        from backend.user_store import get_or_create_user
        from backend.models_db import ReminderHistory, AuditLog

        db = db_session_factory()
        try:
            chat_id = f"{digits}@s.whatsapp.net"
            user = get_or_create_user(db, chat_id)
            since = datetime.now(timezone.utc) - timedelta(days=14)

            entries = []
            for r in db.query(ReminderHistory).filter(
                ReminderHistory.user_id == user.id,
                ReminderHistory.created_at >= since,
            ).order_by(ReminderHistory.created_at.desc()).limit(50).all():
                ts = r.created_at or r.delivered_at
                entries.append((ts, "reminder", f"{r.status or r.kind}: {(r.message or '')[:50]}"))
            for a in db.query(AuditLog).filter(
                AuditLog.user_id == user.id,
                AuditLog.created_at >= since,
            ).order_by(AuditLog.created_at.desc()).limit(50).all():
                entries.append((a.created_at, "audit", f"{a.action}: {a.resource or ''}"))

            entries.sort(key=lambda x: x[0] or datetime(1970, 1, 1), reverse=True)
            lines = [f"#history\nUtilizador ***{digits[-6:]}: últimos 14 dias ({len(entries)} entradas)"]
            for ts, typ, txt in entries[:25]:
                ts_str = ts.strftime("%d/%m %H:%M") if ts else "?"
                lines.append(f"  {ts_str} | {typ} | {txt}")
            if len(entries) > 25:
                lines.append(f"  ... e mais {len(entries) - 25}")
            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"admin #history failed: {e}")
        return "#history\nErro ao obter histórico."


def _cmd_server(
    cron_store_path: Path | None = None,
    wa_channel: Any = None,
) -> str:
    """Snapshot atual + histórico 7 dias (RAM, CPU, disco, uptime, bridge, cron, entrega)."""
    lines = ["#server"]
    try:
        from backend.server_metrics import record_snapshot, get_historical
        from zapista.config.loader import get_data_dir
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
    # Disco: total, usado, livre, percentual
    disk_total_mb = snapshot.get("disk_total_mb")
    if disk_total_mb is not None and disk_total_mb > 0:
        disk_used_mb = disk_total_mb - snapshot.get("disk_free_mb", 0)
        lines.append(
            f"Disco: {snapshot['disk_pct']}% usado | total: {disk_total_mb:.0f}M | "
            f"livre: {snapshot['disk_free_mb']:.0f}M | dados .zapista: {snapshot['data_dir_mb']:.0f}M"
        )
    else:
        lines.append(
            f"Disco: {snapshot['disk_pct']}% usado | livre: {snapshot['disk_free_mb']:.0f}M | "
            f"dados .zapista: {snapshot['data_dir_mb']:.0f}M"
        )
    lines.append(f"Gateway uptime: {_uptime_str(snapshot['gateway_uptime_s'])}")
    # Top 5 processos por memória
    try:
        import psutil
        procs = sorted(psutil.process_iter(["pid", "name", "memory_info"]), key=lambda p: (p.info.get("memory_info") or (0,)).rss, reverse=True)
        top5 = []
        for p in procs[:5]:
            try:
                mi = p.info.get("memory_info")
                rss_mb = (mi.rss / (1024 * 1024)) if mi else 0
                name = (p.info.get("name") or "?")[:20]
                top5.append(f"{name}: {rss_mb:.0f}M")
            except (psutil.NoSuchProcess, Exception):
                continue
        if top5:
            lines.append("Top 5 memória: " + " | ".join(top5))
    except Exception:
        pass
    # Temperatura CPU (Linux)
    try:
        import psutil
        if hasattr(psutil, "sensors_temperatures"):
            temps = psutil.sensors_temperatures()
            if temps:
                for name, entries in list(temps.items())[:2]:
                    for e in entries[:1]:
                        lines.append(f"Temp {name}: {e.current:.0f}°C")
                        break
    except Exception:
        pass
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


def _cmd_msgs() -> str:
    """Total de mensagens tocadas: hoje, últimos 3 dias, semana, mês, histórico total."""
    from datetime import date, datetime, timedelta

    try:
        from zapista.utils.helpers import get_sessions_path
        sessions_dir = get_sessions_path()
    except ImportError:
        sessions_dir = Path.home() / ".zapista" / "sessions"

    if not sessions_dir.exists():
        return "#msgs\n0 mensagens (pasta de sessões não existe)."

    today = date.today()
    counts = {
        "today": 0,
        "last_3_days": 0,
        "week": 0,
        "month": 0,
        "total": 0,
    }
    cutoff_3d = today - timedelta(days=2)  # hoje + 2 dias atrás = 3 dias
    cutoff_week = today - timedelta(days=6)  # 7 dias
    cutoff_month = today - timedelta(days=29)  # 30 dias

    for path in sessions_dir.glob("*.jsonl"):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("_type") == "metadata":
                        continue
                    ts_str = (data.get("timestamp") or "").strip()
                    counts["total"] += 1
                    if not ts_str or len(ts_str) < 10:
                        continue
                    try:
                        msg_date = date.fromisoformat(ts_str[:10])
                    except (ValueError, TypeError):
                        continue
                    if msg_date == today:
                        counts["today"] += 1
                    if msg_date >= cutoff_3d:
                        counts["last_3_days"] += 1
                    if msg_date >= cutoff_week:
                        counts["week"] += 1
                    if msg_date >= cutoff_month:
                        counts["month"] += 1
        except Exception as e:
            logger.debug(f"#msgs: erro ao ler {path}: {e}")
            continue

    lines = [
        "#msgs",
        "Mensagens tocadas (user + assistant):",
        f"Hoje: {counts['today']}",
        f"Últimos 3 dias: {counts['last_3_days']}",
        f"Esta semana (7d): {counts['week']}",
        f"Este mês (30d): {counts['month']}",
        f"Histórico total: {counts['total']}",
    ]
    return "\n".join(lines)


def _bytes_short(n: int) -> str:
    for u, s in [(1 << 30, "G"), (1 << 20, "M"), (1 << 10, "K")]:
        if n >= u:
            return f"{n / u:.1f}{s}"
    return f"{n}B"


def _cmd_system(wa_channel: Any = None) -> str:
    """Erros últimos 60 min, latência média, fila Redis, health dos serviços."""
    lines = ["#system"]
    try:
        from backend.server_metrics import _load_metrics
        data = _load_metrics()
        events = data.get("today_events", {})
        lines.append(f"Erros (hoje): {events.get('errors', 0)} errors, {events.get('warnings', 0)} warnings")
    except Exception:
        lines.append("Erros: N/A – configurar logging agregado")
    lines.append("Latência média API: N/A – configurar métricas")
    # Fila Redis
    try:
        from zapista.bus.queue import MessageBus
        bus = MessageBus()
        if getattr(bus, "redis_url", None):
            import redis
            r = redis.from_url(bus.redis_url)
            keys = r.dbsize()
            info = r.info("memory")
            mem = info.get("used_memory_human", "N/A")
            lines.append(f"Fila Redis: {keys} chaves | memória: {mem}")
        else:
            lines.append("Fila: em memória (Redis não configurado)")
    except Exception as e:
        lines.append(f"Redis: {str(e)[:50]}")
    # Health: bridge
    if wa_channel:
        bridge = "conectado" if getattr(wa_channel, "_connected", None) else "desconectado"
        lines.append(f"Health WhatsApp bridge: {bridge}")
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


def _cmd_lockout() -> str:
    """Chats bloqueados por tentativas de senha god-mode erradas."""
    try:
        from backend.god_mode_lockout import get_lockout_stats
        stats = get_lockout_stats()
        if not stats:
            return "#lockout\nNenhum chat bloqueado ou com tentativas recentes."
        lines = ["#lockout", "Chat | Status | Tentativas | Tempo restante"]
        for s in stats[:20]:
            cid = s.get("chat_id", "?")
            status = s.get("status", "?")
            attempts = s.get("attempts", 0)
            rem = s.get("remaining_sec")
            rem_str = f"{rem}s" if rem is not None else "—"
            lines.append(f"  {cid} | {status} | {attempts} | {rem_str}")
        if len(stats) > 20:
            lines.append(f"  ... e mais {len(stats) - 20}")
        return "\n".join(lines)
    except Exception as e:
        logger.debug(f"admin #lockout failed: {e}")
        return "#lockout\nErro ao obter estatísticas."


async def _cmd_cleanup(
    db_session_factory: Any,
    cron_store_path: Path | None,
    *,
    days: int = 90,
) -> str:
    """
    Recursos pouco usados (últimos N dias). Mimo analisa e sugere o que retirar.
    """
    if not db_session_factory:
        return "#cleanup\nErro: DB não disponível."
    try:
        from pathlib import Path
        from backend.unused_resources import gather_unused_resources
        db = db_session_factory()
        try:
            path = cron_store_path or (Path.home() / ".zapista" / "cron" / "jobs.json")
            data = gather_unused_resources(db, path, days=days)
        finally:
            db.close()

        if not data["lists_unused"] and not data["cron_unused"]:
            return f"#cleanup\nNenhum recurso pouco usado nos últimos {days} dias. Tudo a ser utilizado."

        # Mimo: analisa e sugere (se disponível)
        try:
            from zapista.config.loader import load_config
            from zapista.providers.litellm_provider import LiteLLMProvider
            config = load_config()
            scope_model = (config.agents.defaults.scope_model or "").strip()
            p = config.get_provider(scope_model) if scope_model else None
            scope_provider = None
            if scope_model and p and (getattr(p, "api_key", None) or "").strip():
                try:
                    from backend.token_usage import record_usage
                    usage_cb = record_usage
                except ImportError:
                    usage_cb = None
                scope_provider = LiteLLMProvider(
                    api_key=p.api_key,
                    api_base=config.get_api_base(scope_model),
                    default_model=scope_model,
                    extra_headers=getattr(p, "extra_headers", None),
                    usage_callback=usage_cb,
                )
            if scope_provider:
                prompt = (
                    "Análise de recursos pouco usados num sistema de organização (listas, lembretes). "
                    "Com base nos dados abaixo, escreve um relatório curto (4-8 linhas) que:\n"
                    "1) Indique quantas listas e quantos lembretes estão sem uso recente\n"
                    "2) Sugira ao administrador o que pode remover ou arquivar (seja prático)\n"
                    "3) Use tom neutro e objetivo. Em português."
                )
                r = await scope_provider.chat(
                    messages=[{"role": "user", "content": f"{prompt}\n\nDados:\n{data['summary']}"}],
                    model=scope_model,
                    max_tokens=300,
                    temperature=0.3,
                )
                out = (r.content or "").strip()
                if out and len(out) <= 600:
                    return f"#cleanup\n{out}"
        except Exception as e:
            logger.debug(f"admin #cleanup Mimo failed: {e}")

        # Fallback: resumo simples
        lines = [f"#cleanup\nRecursos sem atividade nos últimos {days} dias:"]
        if data["lists_unused"]:
            lines.append(f"\nListas: {len(data['lists_unused'])}")
            for u in data["lists_unused"][:8]:
                lines.append(f"  - \"{u['list_name']}\" (user_id={u['user_id']}): {u['pending']} pendentes")
        if data["cron_unused"]:
            lines.append(f"\nLembretes (cron): {len(data['cron_unused'])}")
            for u in data["cron_unused"][:8]:
                lines.append(f"  - \"{u['message']}\" ***{u['to']}: {u['reason']}")
        return "\n".join(lines)
    except Exception as e:
        logger.debug(f"admin #cleanup failed: {e}")
        return "#cleanup\nErro ao analisar recursos."


def _cmd_blocked() -> str:
    """Tentativas de comandos bloqueados (shell, SQL, path) por cliente."""
    try:
        from backend.command_filter import get_blocked_stats
        stats = get_blocked_stats()
        if not stats:
            return "#blocked\nNenhum comando bloqueado registado."
        lines = ["#blocked", "Canal:Chat | Total | Razões (ex.: shell, sql_drop)"]
        for s in stats[:20]:
            cid = s.get("chat_id", "?")
            ch = s.get("channel", "?")
            total = s.get("total", 0)
            reasons = s.get("reasons", {})
            reason_str = ", ".join(f"{k}:{v}" for k, v in sorted(reasons.items()))[:60]
            lines.append(f"  {ch}:{cid} | {total} | {reason_str}")
        if len(stats) > 20:
            lines.append(f"  ... e mais {len(stats) - 20} clientes")
        return "\n".join(lines)
    except Exception as e:
        logger.debug(f"admin #blocked failed: {e}")
        return "#blocked\nErro ao obter estatísticas."


def _cmd_painpoints(cron_store_path: Path | None) -> str:
    """Heurísticas: jobs atrasados + clientes para atendimento contactar."""
    lines = ["#painpoints"]
    path = cron_store_path or (Path.home() / ".zapista" / "cron" / "jobs.json")
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


# ---------- Novos comandos admin ----------

def _cmd_hora() -> str:
    """Horário atual do servidor (host) e do container (TZ)."""
    from datetime import datetime, timezone
    tz_env = (os.environ.get("TZ") or "UTC").strip()
    now_utc = datetime.now(timezone.utc)
    try:
        from zoneinfo import ZoneInfo
        z = ZoneInfo(tz_env) if ("/" in tz_env or tz_env in ("UTC", "GMT")) else ZoneInfo("UTC")
        now_local = datetime.now(z)
        tz_str = str(now_local.strftime("%Z")) or tz_env
        local_str = now_local.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        now_local = now_utc
        tz_str = tz_env
        local_str = now_utc.strftime("%Y-%m-%d %H:%M:%S")
    utc_str = now_utc.strftime("%Y-%m-%d %H:%M:%S")
    return f"🕐 Servidor: {utc_str} (UTC) | Docker: {local_str} ({tz_str}) | TZ={tz_env}"


async def _cmd_ativos(db_session_factory: Any, arg: str) -> str:
    """Número de clientes ativos nos últimos N minutos (enviaram ou receberam mensagem)."""
    minutes = 15
    if arg and arg.isdigit():
        minutes = max(1, min(1440, int(arg)))
    try:
        from zapista.utils.helpers import get_sessions_path
        sessions_dir = get_sessions_path()
    except Exception:
        sessions_dir = Path.home() / ".zapista" / "sessions"
    if not sessions_dir.exists():
        return f"📱 Ativos últimos {minutes} min: 0 utilizadores (pasta de sessões não existe)."
    cutoff = time.time() - (minutes * 60)
    active_chats: set[str] = set()
    for path in sessions_dir.glob("*.jsonl"):
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line)
                    ts_str = (data.get("timestamp") or "").strip()
                    if not ts_str or len(ts_str) < 10:
                        continue
                    try:
                        from datetime import datetime
                        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                        ts = dt.timestamp()
                    except Exception:
                        continue
                    if ts >= cutoff:
                        active_chats.add(path.stem)
                        break
        except Exception:
            continue
    return f"📱 Ativos últimos {minutes} min: {len(active_chats)} utilizadores"


def _cmd_erros(arg: str) -> str:
    """Erros do sistema nas últimas N horas (logs ou Redis)."""
    hours = 1
    if arg and arg.replace(".", "").isdigit():
        hours = max(0.1, min(168, float(arg)))
    lines = [f"❌ Erros (últimas {hours}h)"]
    try:
        from backend.server_metrics import _load_metrics
        data = _load_metrics()
        events = data.get("today_events", {})
        errors = events.get("errors", 0)
        warnings = events.get("warnings", 0)
        info = events.get("info", 0)
        if errors or warnings or info:
            lines.append(f"  ERROR: {errors} | WARNING: {warnings} | INFO: {info}")
        else:
            lines.append("  Nenhum evento registado em today_events. Configurar record_event('errors') nos handlers.")
    except Exception:
        lines.append("  N/A (configurar logging agregado em server_metrics ou logs)")
    return "\n".join(lines)


async def _cmd_diagnostico(
    cron_store_path: Path | None,
    db_session_factory: Any,
    wa_channel: Any,
) -> str:
    """Verificação completa: Redis, bridge, API, recursos, usuários, jobs, erros recentes, latência LLM, WhatsApp."""
    lines = ["🔧 #diagnostico"]
    # Redis
    try:
        from zapista.bus.queue import MessageBus
        bus = MessageBus()
        if getattr(bus, "redis_url", None):
            import redis
            r = redis.from_url(bus.redis_url)
            r.ping()
            info = r.info("memory")
            keys = r.dbsize()
            lines.append(f"✅ Redis: conectado | chaves: {keys} | memória: {info.get('used_memory_human', 'N/A')}")
        else:
            lines.append("⚠ Redis: não configurado (fila em memória)")
    except Exception as e:
        lines.append(f"❌ Redis: {str(e)[:60]}")
    # Bridge WhatsApp
    bridge_st = "conectado" if (wa_channel and getattr(wa_channel, "_connected", None)) else "desconectado"
    lines.append(f"📱 WhatsApp: {bridge_st}")

    # Timezone Check
    try:
        import time
        from zoneinfo import ZoneInfo
        import importlib.util
        
        has_tzdata = importlib.util.find_spec("tzdata") is not None
        lines.append(f"🌍 System TZ: {time.tzname} | tzdata: {'✅' if has_tzdata else '❌'}")
        
        try:
            ZoneInfo("Europe/Lisbon")
            lines.append("✅ ZoneInfo('Europe/Lisbon'): OK")
        except Exception as e:
            lines.append(f"❌ ZoneInfo('Europe/Lisbon'): {e}")
            
        from datetime import datetime
        now_sys = datetime.now()
        lines.append(f"🕒 System Local: {now_sys.strftime('%H:%M:%S')}")
    except Exception as e:
        lines.append(f"❌ TZ Check Error: {e}")

    # Recursos
    try:
        import psutil
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        lines.append(f"💻 RAM: {mem.percent}% | CPU: {cpu}%")
    except Exception:
        lines.append("💻 Recursos: N/A (psutil)")
    # Usuários e jobs
    if db_session_factory:
        try:
            from backend.models_db import User
            db = db_session_factory()
            try:
                total_users = db.query(User).count()
                lines.append(f"👥 Utilizadores: {total_users}")
            finally:
                db.close()
        except Exception:
            lines.append("👥 Utilizadores: N/A")
    path = cron_store_path or (Path.home() / ".zapista" / "cron" / "jobs.json")
    if path.exists():
        try:
            data = json.loads(path.read_text())
            jobs = data.get("jobs", [])
            enabled = sum(1 for j in jobs if j.get("enabled", True))
            lines.append(f"📅 Jobs: {len(jobs)} total, {enabled} ativos")
        except Exception:
            lines.append("📅 Jobs: erro ao ler")
    else:
        lines.append("📅 Jobs: 0 (ficheiro não encontrado)")
    # Erros recentes (hoje)
    try:
        from backend.server_metrics import _load_metrics
        data = _load_metrics()
        events = data.get("today_events", {})
        err = events.get("errors", 0)
        warn = events.get("warnings", 0)
        lines.append(f"❌ Erros recentes (hoje): {err} errors, {warn} warnings")
    except Exception:
        lines.append("❌ Erros recentes: N/A")
    # Latência média LLM (a implementar em token_usage ou APM)
    lines.append("⏱ Latência LLM: N/A (configurar métricas)")
    return "\n".join(lines)


def _cmd_help() -> str:
    """Lista de todos os comandos admin com descrição e exemplos."""
    lines = [
        "#help / #comandos",
        "Comandos disponíveis (God Mode):",
        "",
        "🕐 #hora / #time — Horário do servidor e do container (TZ)",
        "📱 #ativos [min] — Clientes ativos nos últimos N min (padrão 15)",
        "❌ #erros [horas] — Erros do sistema nas últimas N horas (padrão 1)",
        "🔧 #diagnostico / #diag — Verificação completa (Redis, bridge, recursos, jobs, erros)",
        "👥 #clientes — Lista de clientes cadastrados (chat_id, nome, timezone, criação)",
        "📅 #jobs [chat_id] — Jobs de um usuário ou todos (job_id, mensagem, próximo run, status)",
        "🔴 #redis — Status Redis (conexão, chaves, memória)",
        "📲 #whatsapp — Status WhatsApp (conectado, msgs hoje, fila, última msg)",
        "",
        "#users — Total utilizadores | #cron [detalhado] — Jobs (incl. desativados e próxima execução)",
        "#server — Snapshot (RAM, CPU, disco, uptime, top 5 mem, temp CPU) + histórico 7d",
        "#system — Erros, latência API, fila Redis, health dos serviços",
        "#msgs — Mensagens tocadas | #lembretes <nr> — Lembretes do número",
        "#tz <nr> — Timezone do número | #history <nr> — Histórico",
        "#add <nr> / #remove <nr> — Lista allow | #mute <nr> — Silenciar",
        "#lockout — Bloqueios senha | #cleanup — Recursos pouco usados",
        "#quit — Desativar God Mode",
        "",
        "Exemplos:",
        "  #ativos 30   → ativos nos últimos 30 min",
        "  #erros 2     → erros nas últimas 2 horas",
        "  #jobs 5511999999999  → jobs desse número",
        "  #cron detalhado  → lista completa com desativados",
    ]
    return "\n".join(lines)


async def _cmd_clientes(db_session_factory: Any) -> str:
    """Lista de clientes cadastrados (chat_id, nome, timezone, criação)."""
    if not db_session_factory:
        return "#clientes\nErro: DB não disponível."
    try:
        from backend.models_db import User
        from datetime import datetime
        db = db_session_factory()
        try:
            users = db.query(User).order_by(User.created_at.desc()).limit(100).all()
            lines = [f"#clientes\nTotal: {len(users)} (mostrando até 100)"]
            for u in users:
                phone = getattr(u, "phone_truncated", "") or "?"
                name = (getattr(u, "preferred_name", None) or "")[:20]
                tz = getattr(u, "timezone", None) or "-"
                created = getattr(u, "created_at", None)
                created_str = created.strftime("%d/%m %Y") if created else "-"
                lines.append(f"  {phone} | {name} | {tz} | {created_str}")
            return "\n".join(lines)
        finally:
            db.close()
    except Exception as e:
        logger.debug(f"admin #clientes failed: {e}")
        return "#clientes\nErro ao listar."


def _cmd_jobs(cron_store_path: Path | None, arg: str) -> str:
    """Listar jobs de um usuário (#jobs chat_id) ou todos (#jobs)."""
    path = cron_store_path or (Path.home() / ".zapista" / "cron" / "jobs.json")
    if not path.exists():
        return "#jobs\n0 jobs (ficheiro não encontrado)."
    try:
        data = json.loads(path.read_text())
        jobs = data.get("jobs", [])
        if arg and _digits(arg):
            jobs = [j for j in jobs if _to_matches_user((j.get("payload") or {}).get("to"), arg)]
        lines = [f"#jobs\n{len(jobs)} jobs"]
        now_ms = int(time.time() * 1000)
        for j in jobs[:30]:
            payload = j.get("payload") or {}
            state = j.get("state") or {}
            sched = j.get("schedule") or {}
            name = (payload.get("message") or j.get("id", "?"))[:35]
            to = _digits((payload.get("to") or ""))[-8:]
            next_ms = state.get("nextRunAtMs")
            next_str = _ms_to_short(next_ms) if next_ms else "-"
            enabled = "✓" if j.get("enabled", True) else "✗"
            lines.append(f"  [{j.get('id', '?')[:8]}] {name} | ***{to} | next: {next_str} | {enabled}")
        if len(jobs) > 30:
            lines.append(f"  ... e mais {len(jobs) - 30}")
        return "\n".join(lines)
    except Exception as e:
        logger.debug(f"admin #jobs failed: {e}")
        return "#jobs\nErro ao ler jobs."


def _cmd_redis() -> str:
    """Status da conexão Redis, chaves e memória."""
    lines = ["#redis"]
    try:
        from zapista.bus.queue import MessageBus
        bus = MessageBus()
        if not getattr(bus, "redis_url", None):
            lines.append("Redis não configurado (fila em memória).")
            return "\n".join(lines)
        import redis
        r = redis.from_url(bus.redis_url)
        r.ping()
        info = r.info("memory")
        keys = r.dbsize()
        used = info.get("used_memory_human", "N/A")
        peak = info.get("used_memory_peak_human", "N/A")
        lines.append(f"Conectado. Chaves: {keys} | Memória: {used} (pico: {peak})")
        # Últimas chaves (sample)
        try:
            sample = r.keys("*")[:10]
            if sample:
                lines.append("Amostra de chaves: " + ", ".join(k.decode() if isinstance(k, bytes) else str(k) for k in sample[:5]))
        except Exception:
            pass
        return "\n".join(lines)
    except Exception as e:
        lines.append(f"Erro: {str(e)[:80]}")
        return "\n".join(lines)


def _cmd_whatsapp(wa_channel: Any) -> str:
    """Status da conexão WhatsApp, mensagens hoje e fila."""
    lines = ["#whatsapp"]
    if not wa_channel:
        lines.append("Canal WhatsApp não injetado.")
        return "\n".join(lines)
    connected = getattr(wa_channel, "_connected", False)
    lines.append(f"Conectado: {'sim' if connected else 'não'}")
    # Mensagens processadas hoje / fila: se houver atributos no canal
    msgs_today = getattr(wa_channel, "_messages_processed_today", None)
    if msgs_today is not None:
        lines.append(f"Mensagens processadas hoje: {msgs_today}")
    queue_len = getattr(wa_channel, "_outbound_queue_len", None)
    if queue_len is not None:
        lines.append(f"Mensagens na fila de envio: {queue_len}")
    last_msg = getattr(wa_channel, "_last_message_received_at", None)
    if last_msg:
        try:
            from datetime import datetime
            dt = datetime.fromtimestamp(last_msg)
            lines.append(f"Última mensagem recebida: {dt.strftime('%H:%M:%S')}")
        except Exception:
            pass
    return "\n".join(lines)
