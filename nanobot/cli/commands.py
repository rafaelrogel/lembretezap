"""CLI commands for nanobot."""

import asyncio
import logging
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from nanobot import __version__, __logo__, __title__

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="zapassist",
    help=f"{__logo__} {__title__} - WhatsApp AI Organizer",
    no_args_is_help=True,
)

console = Console()


def version_callback(value: bool):
    if value:
        console.print(f"{__logo__} {__title__} v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None, "--version", "-v", callback=version_callback, is_eager=True
    ),
):
    """ZapAssist - WhatsApp AI Organizer."""
    pass


# ============================================================================
# Onboard / Setup
# ============================================================================


@app.command()
def onboard():
    """Initialize nanobot configuration and workspace."""
    from nanobot.config.loader import get_config_path, save_config
    from nanobot.config.schema import Config
    from nanobot.utils.helpers import get_workspace_path
    
    config_path = get_config_path()
    
    if config_path.exists():
        console.print(f"[yellow]Config already exists at {config_path}[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit()
    
    # Create default config
    config = Config()
    save_config(config)
    console.print(f"[green]✓[/green] Created config at {config_path}")
    
    # Create workspace
    workspace = get_workspace_path()
    console.print(f"[green]✓[/green] Created workspace at {workspace}")
    
    # Create default bootstrap files
    _create_workspace_templates(workspace)
    
    console.print(f"\n{__logo__} {__title__} is ready!")
    console.print("\nNext steps:")
    console.print("  1. Add your API key to [cyan]~/.nanobot/config.json[/cyan]")
    console.print("     DeepSeek: https://platform.deepseek.com  |  Xiaomi MiMo: https://platform.xiaomimimo.com")
    console.print("  2. Chat: [cyan]zapassist agent -m \"Hello!\"[/cyan]")
    console.print("  3. Gateway (WhatsApp): [cyan]zapassist gateway[/cyan]")




def _create_workspace_templates(workspace: Path):
    """Create default workspace template files."""
    templates = {
        "AGENTS.md": """# Agent Instructions

You are a helpful AI assistant. Be concise, accurate, and friendly.
We only operate in private chats; we never respond in groups.

## Guidelines

- Always explain what you're doing before taking actions
- Ask for clarification when the request is ambiguous
- Use tools to help accomplish tasks
- Remember important information in your memory files
""",
        "SOUL.md": """# Soul

I am ZapAssist, your WhatsApp AI organizer.

## Personality

- Helpful and friendly
- Concise and to the point
- Curious and eager to learn

## Values

- Accuracy over speed
- User privacy and safety
- Transparency in actions
""",
        "USER.md": """# User

Information about the user goes here.

## Preferences

- Communication style: (casual/formal)
- Timezone: (your timezone)
- Language: (your preferred language)
""",
    }
    
    for filename, content in templates.items():
        file_path = workspace / filename
        if not file_path.exists():
            file_path.write_text(content)
            console.print(f"  [dim]Created {filename}[/dim]")
    
    # Create memory directory and MEMORY.md
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    memory_file = memory_dir / "MEMORY.md"
    if not memory_file.exists():
        memory_file.write_text("""# Long-term Memory

This file stores important information that should persist across sessions.

## User Information

(Important facts about the user)

## Preferences

(User preferences learned over time)

## Important Notes

(Things to remember)
""")
        console.print("  [dim]Created memory/MEMORY.md[/dim]")


def _make_provider(config):
    """Create LiteLLMProvider from config. Exits if no API key found."""
    import os
    from nanobot.providers.litellm_provider import LiteLLMProvider
    model = config.agents.defaults.model
    p = config.get_provider()
    # DEBUG (set NANOBOT_DEBUG=1 to see)
    if os.environ.get("NANOBOT_DEBUG"):
        print(f"DEBUG: p={p}")
        print(f"DEBUG: p.api_key='{getattr(p, 'api_key', None)}' len={len(p.api_key) if p and getattr(p, 'api_key', None) else 0}")
        print(f"DEBUG: model='{model}'")
    # Fallback: if matched provider has no (valid) api_key, use first provider that has one
    if not (p and getattr(p, "api_key", None) and (p.api_key or "").strip()):
        p = config.get_provider("")  # force fallback to first provider with api_key
    if not (p and p.api_key) and not model.startswith("bedrock/"):
        console.print("[red]Error: No API key configured.[/red]")
        console.print("Set one in ~/.nanobot/config.json under providers section")
        raise typer.Exit(1)
    usage_cb = None
    try:
        from backend.token_usage import record_usage
        usage_cb = record_usage
    except ImportError:
        pass
    return LiteLLMProvider(
        api_key=p.api_key if p else None,
        api_base=config.get_api_base(),
        default_model=model,
        extra_headers=p.extra_headers if p else None,
        usage_callback=usage_cb,
    )


def _make_provider_for_model(config, model_str: str):
    """Create LiteLLMProvider for a specific model (e.g. scope_model). Returns None if no API key for that model."""
    from nanobot.providers.litellm_provider import LiteLLMProvider
    if not model_str or not model_str.strip():
        return None
    p = config.get_provider(model_str.strip())
    if not p or not (getattr(p, "api_key", None) or "").strip():
        return None
    usage_cb = None
    try:
        from backend.token_usage import record_usage
        usage_cb = record_usage
    except ImportError:
        pass
    return LiteLLMProvider(
        api_key=p.api_key,
        api_base=config.get_api_base(model_str),
        default_model=model_str.strip(),
        extra_headers=p.extra_headers if p else None,
        usage_callback=usage_cb,
    )


# ============================================================================
# Gateway / Server
# ============================================================================


@app.command()
def gateway(
    port: int = typer.Option(18790, "--port", "-p", help="Gateway port"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
):
    """Start the ZapAssist gateway (WhatsApp + agent + cron)."""
    from nanobot.config.loader import load_config, get_data_dir
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop
    from nanobot.channels.manager import ChannelManager
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronJob
    from nanobot.heartbeat.service import HeartbeatService
    
    if verbose:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    try:
        from nanobot.utils.logging_config import configure_logging
        configure_logging()
    except Exception:
        pass
    console.print(f"{__logo__} Starting {__title__} gateway on port {port}...")
    
    config = load_config()
    bus = MessageBus()
    provider = _make_provider(config)
    scope_model = (config.agents.defaults.scope_model or "").strip() or None
    scope_provider = _make_provider_for_model(config, scope_model) if scope_model else None
    
    # Create cron service first (callback set after agent creation)
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)
    
    # Create agent with cron service
    agent = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        scope_model=scope_model or config.agents.defaults.model,
        scope_provider=scope_provider,
        max_iterations=config.agents.defaults.max_tool_iterations,
        cron_service=cron,
    )
    
    # Recap de Ano Novo (1º jan): system_event yearly_recap → DeepSeek + Mimo para cada utilizador
    async def on_cron_job(job: CronJob) -> str | None:
        from nanobot.bus.events import OutboundMessage
        if getattr(job.payload, "kind", None) == "system_event" and (job.payload.message or "").strip() == "yearly_recap":
            try:
                from backend.yearly_recap import run_year_recap
                sent, errors = await run_year_recap(
                    bus=bus,
                    session_manager=agent.sessions,
                    deepseek_provider=provider,
                    deepseek_model=config.agents.defaults.model or "",
                    mimo_provider=scope_provider,
                    mimo_model=scope_model or "",
                    default_channel="whatsapp",
                )
                return f"Recap Ano Novo: enviados={sent}, erros={errors}"
            except Exception as e:
                logger.exception(f"Yearly recap failed: {e}")
                return f"Recap Ano Novo falhou: {e}"

        if job.payload.deliver and job.payload.to and provider and (config.agents.defaults.model or "").strip():
            try:
                from backend.user_store import is_user_in_quiet_window
                if is_user_in_quiet_window(job.payload.to):
                    logger.info(f"Cron deliver skipped (quiet window): to={job.payload.to[:20]}...")
                    return "skipped (quiet window)"
            except Exception:
                pass
            try:
                # Idioma do destinatário (pt-PT, pt-BR, es, en) para a mensagem do lembrete
                user_lang = "en"
                try:
                    from backend.database import SessionLocal
                    from backend.user_store import get_user_language
                    db = SessionLocal()
                    try:
                        user_lang = get_user_language(db, job.payload.to)
                    finally:
                        db.close()
                except Exception:
                    pass
                lang_instruction = {
                    "pt-PT": "Escreve a mensagem em português de Portugal.",
                    "pt-BR": "Escreve a mensagem em português do Brasil.",
                    "es": "Escribe el mensaje en español.",
                    "en": "Write the message in English.",
                }.get(user_lang, "Write the message in English.")
                # DeepSeek: mensagem criativa e variada a partir do contexto do lembrete (sem frases fixas)
                prompt = (
                    "You are sending a reminder to the user. Below is the reminder content. "
                    "Write ONE short, friendly message that delivers this reminder. "
                    "Be CREATIVE and NATURAL: look at the context (e.g. jantar, médico, compras, cinema) and choose a tone that fits (warm, encouraging, light). "
                    "Use 1-2 emojis. Do NOT repeat the same phrase every time (e.g. avoid always saying 'hope you're well'). "
                    "Vary your wording. Be positive and human. One or two short sentences only. "
                    f"{lang_instruction} Reply only with the message text, nothing else.\n\nReminder: "
                ) + (job.payload.message or "")
                try:
                    r = await provider.chat(
                        messages=[{"role": "user", "content": prompt}],
                        model=config.agents.defaults.model or "",
                        max_tokens=220,
                        temperature=0.7,
                    )
                    response = (r.content or job.payload.message or "").strip()
                except Exception as e:
                    logger.warning(f"Cron (DeepSeek reminder message) failed: {e}")
                    response = job.payload.message or ""
            except Exception as e:
                logger.warning(f"Cron deliver failed: {e}")
                response = job.payload.message or ""
            ch, to = job.payload.channel or "cli", job.payload.to
            logger.info(f"Cron deliver: channel={ch} to={to[:20]}... content_len={len(response or '')}")
            try:
                from backend.database import SessionLocal
                from backend.reminder_history import add_delivered
                db = SessionLocal()
                try:
                    add_delivered(db, to, response or job.payload.message or "")
                finally:
                    db.close()
            except Exception:
                pass
            await bus.publish_outbound(OutboundMessage(
                channel=ch,
                chat_id=to,
                content=response or ""
            ))
            return response
        # Sem scope_provider ou job sem deliver: usa o agente completo (fallback)
        response = await agent.process_direct(
            job.payload.message,
            session_key=f"cron:{job.id}",
            channel=job.payload.channel or "cli",
            chat_id=job.payload.to or "direct",
        )
        if job.payload.deliver and job.payload.to:
            ch, to = job.payload.channel or "cli", job.payload.to
            logger.info(f"Cron deliver: channel={ch} to={to[:20]}... content_len={len(response or '')}")
            await bus.publish_outbound(OutboundMessage(
                channel=ch,
                chat_id=to,
                content=response or ""
            ))
        else:
            if not job.payload.deliver or not job.payload.to:
                logger.debug(f"Cron job {job.id}: not delivering (deliver={job.payload.deliver}, to={bool(job.payload.to)})")
        return response
    cron.on_job = on_cron_job

    # Garantir que o job de Recap de Ano Novo (1º de janeiro) existe
    try:
        from nanobot.cron.types import CronSchedule
        existing = [j for j in cron.list_jobs(include_disabled=True) if (getattr(j.payload, "message", None) or "") == "yearly_recap"]
        if not existing:
            cron.add_job(
                name="Recap Ano Novo",
                schedule=CronSchedule(kind="cron", expr="0 9 1 1 *"),  # 9h UTC todo 1º jan
                message="yearly_recap",
                payload_kind="system_event",
            )
            console.print("[dim]Job 'Recap Ano Novo' (1º jan) registado.[/dim]")
    except Exception as e:
        logger.debug(f"Yearly recap job setup: {e}")

    # Create heartbeat service (scope provider = Xiaomi barato; senão usa o agente completo)
    async def on_heartbeat(prompt: str) -> str:
        if scope_provider and scope_model:
            try:
                r = await scope_provider.chat(
                    messages=[{"role": "user", "content": prompt}],
                    model=scope_model,
                    max_tokens=500,
                    temperature=0,
                )
                return (r.content or "").strip()
            except Exception as e:
                logger.warning(f"Heartbeat (scope LLM) failed: {e}")
                return "HEARTBEAT_OK"
        return await agent.process_direct(prompt, session_key="heartbeat")
    
    heartbeat = HeartbeatService(
        workspace=config.workspace_path,
        on_heartbeat=on_heartbeat,
        interval_s=30 * 60,  # 30 minutes
        enabled=True
    )
    
    # Create channel manager
    channels = ChannelManager(config, bus)

    # Injetar cron_tool no canal WhatsApp para lembretes 15 min antes de eventos .ics
    wa_channel = channels.get_channel("whatsapp")
    if wa_channel is not None and hasattr(wa_channel, "set_ics_cron_tool"):
        cron_tool = agent.tools.get("cron") if getattr(agent, "tools", None) else None
        if cron_tool:
            wa_channel.set_ics_cron_tool(cron_tool)

    if channels.enabled_channels:
        console.print(f"[green]✓[/green] Channels enabled: {', '.join(channels.enabled_channels)}")
    else:
        console.print("[yellow]Warning: No channels enabled[/yellow]")
    
    cron_status = cron.status()
    if cron_status["jobs"] > 0:
        console.print(f"[green]✓[/green] Cron: {cron_status['jobs']} scheduled jobs")
    
    console.print(f"[green]✓[/green] Heartbeat: every 30m")
    
    async def run():
        # Fila Redis: iniciar feeder só com event loop a correr (evita RuntimeError: no running event loop)
        if bus.redis_url:
            bus.start_redis_feeder()
            console.print("[green]✓[/green] Redis outbound queue enabled")
        try:
            await cron.start()
            await heartbeat.start()
            await asyncio.gather(
                agent.run(),
                channels.start_all(),
            )
        except KeyboardInterrupt:
            console.print("\nShutting down...")
            heartbeat.stop()
            cron.stop()
            agent.stop()
            bus.stop()
            await channels.stop_all()
    
    asyncio.run(run())




# ============================================================================
# Agent Commands
# ============================================================================


def _safe_print(text: str) -> None:
    """Print text without UnicodeEncodeError on Windows console (emojis -> ?)."""
    import sys
    enc = getattr(sys.stdout, "encoding", None) or "utf-8"
    if enc and not enc.lower().startswith("utf"):
        text = text.encode(enc, errors="replace").decode(enc)
    try:
        console.print(text)
    except (UnicodeEncodeError, UnicodeError):
        console.print(text.encode("ascii", errors="replace").decode("ascii"))


@app.command()
def agent(
    message: str = typer.Option(None, "--message", "-m", help="Message to send to the agent"),
    session_id: str = typer.Option("cli:default", "--session", "-s", help="Session ID"),
):
    """Interact with the agent directly."""
    from nanobot.config.loader import load_config, get_data_dir
    from nanobot.bus.queue import MessageBus
    from nanobot.agent.loop import AgentLoop
    from nanobot.cron.service import CronService
    
    config = load_config()
    
    bus = MessageBus()
    provider = _make_provider(config)
    scope_model = (config.agents.defaults.scope_model or "").strip() or None
    scope_provider = _make_provider_for_model(config, scope_model) if scope_model else None
    cron_store_path = get_data_dir() / "cron" / "jobs.json"
    cron = CronService(cron_store_path)
    
    agent_loop = AgentLoop(
        bus=bus,
        provider=provider,
        workspace=config.workspace_path,
        model=config.agents.defaults.model,
        scope_model=scope_model or config.agents.defaults.model,
        scope_provider=scope_provider,
        max_iterations=config.agents.defaults.max_tool_iterations,
        cron_service=cron,
    )
    
    if message:
        # Single message mode
        async def run_once():
            response = await agent_loop.process_direct(message, session_id)
            _safe_print(f"\n{__logo__} {response}")
        
        asyncio.run(run_once())
    else:
        # Interactive mode
        console.print(f"{__logo__} Interactive mode (Ctrl+C to exit)\n")
        
        async def run_interactive():
            while True:
                try:
                    user_input = console.input("[bold blue]You:[/bold blue] ")
                    if not user_input.strip():
                        continue
                    
                    response = await agent_loop.process_direct(user_input, session_id)
                    _safe_print(f"\n{__logo__} {response}\n")
                except KeyboardInterrupt:
                    console.print("\nGoodbye!")
                    break
        
        asyncio.run(run_interactive())


# ============================================================================
# Channel Commands
# ============================================================================


channels_app = typer.Typer(help="Manage channels")
app.add_typer(channels_app, name="channels")


@channels_app.command("status")
def channels_status():
    """Show channel status."""
    from nanobot.config.loader import load_config

    config = load_config()

    table = Table(title="Channel Status")
    table.add_column("Channel", style="cyan")
    table.add_column("Enabled", style="green")
    table.add_column("Configuration", style="yellow")

    wa = config.channels.whatsapp
    table.add_row(
        "WhatsApp",
        "✓" if wa.enabled else "✗",
        wa.bridge_url
    )
    console.print(table)


def _get_bridge_dir() -> Path:
    """Get the bridge directory, setting it up if needed."""
    import shutil
    import subprocess
    
    # User's bridge location
    user_bridge = Path.home() / ".nanobot" / "bridge"
    
    # Check if already built
    if (user_bridge / "dist" / "index.js").exists():
        return user_bridge
    
    # Check for npm
    if not shutil.which("npm"):
        console.print("[red]npm not found. Please install Node.js >= 18.[/red]")
        raise typer.Exit(1)
    
    # Find source bridge: first check package data, then source dir
    pkg_bridge = Path(__file__).parent.parent / "bridge"  # nanobot/bridge (installed)
    src_bridge = Path(__file__).parent.parent.parent / "bridge"  # repo root/bridge (dev)
    
    source = None
    if (pkg_bridge / "package.json").exists():
        source = pkg_bridge
    elif (src_bridge / "package.json").exists():
        source = src_bridge
    
    if not source:
        console.print("[red]Bridge source not found.[/red]")
        console.print("Try reinstalling: pip install --force-reinstall zapassist")
        raise typer.Exit(1)
    
    console.print(f"{__logo__} Setting up bridge...")
    
    # Copy to user directory
    user_bridge.parent.mkdir(parents=True, exist_ok=True)
    if user_bridge.exists():
        shutil.rmtree(user_bridge)
    shutil.copytree(source, user_bridge, ignore=shutil.ignore_patterns("node_modules", "dist"))
    
    # Install and build
    try:
        console.print("  Installing dependencies...")
        subprocess.run(["npm", "install"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("  Building...")
        subprocess.run(["npm", "run", "build"], cwd=user_bridge, check=True, capture_output=True)
        
        console.print("[green]✓[/green] Bridge ready\n")
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Build failed: {e}[/red]")
        if e.stderr:
            console.print(f"[dim]{e.stderr.decode()[:500]}[/dim]")
        raise typer.Exit(1)
    
    return user_bridge


@channels_app.command("login")
def channels_login():
    """Link device via QR code."""
    import subprocess
    
    bridge_dir = _get_bridge_dir()
    
    console.print(f"{__logo__} Starting bridge...")
    console.print("Scan the QR code to connect.\n")
    
    try:
        subprocess.run(["npm", "start"], cwd=bridge_dir, check=True)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Bridge failed: {e}[/red]")
    except FileNotFoundError:
        console.print("[red]npm not found. Please install Node.js.[/red]")


# ============================================================================
# Cron Commands
# ============================================================================

cron_app = typer.Typer(help="Manage scheduled tasks")
app.add_typer(cron_app, name="cron")


@cron_app.command("list")
def cron_list(
    all: bool = typer.Option(False, "--all", "-a", help="Include disabled jobs"),
):
    """List scheduled jobs."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    jobs = service.list_jobs(include_disabled=all)
    
    if not jobs:
        console.print("No scheduled jobs.")
        return
    
    table = Table(title="Scheduled Jobs")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Schedule")
    table.add_column("Status")
    table.add_column("Next Run")
    
    import time
    for job in jobs:
        # Format schedule
        if job.schedule.kind == "every":
            sched = f"every {(job.schedule.every_ms or 0) // 1000}s"
        elif job.schedule.kind == "cron":
            sched = job.schedule.expr or ""
        else:
            sched = "one-time"
        
        # Format next run
        next_run = ""
        if job.state.next_run_at_ms:
            next_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(job.state.next_run_at_ms / 1000))
            next_run = next_time
        
        status = "[green]enabled[/green]" if job.enabled else "[dim]disabled[/dim]"
        
        table.add_row(job.id, job.name, sched, status, next_run)
    
    console.print(table)


@cron_app.command("add")
def cron_add(
    name: str = typer.Option(..., "--name", "-n", help="Job name"),
    message: str = typer.Option(..., "--message", "-m", help="Message for agent"),
    every: int = typer.Option(None, "--every", "-e", help="Run every N seconds"),
    cron_expr: str = typer.Option(None, "--cron", "-c", help="Cron expression (e.g. '0 9 * * *')"),
    at: str = typer.Option(None, "--at", help="Run once at time (ISO format)"),
    deliver: bool = typer.Option(False, "--deliver", "-d", help="Deliver response to channel"),
    to: str = typer.Option(None, "--to", help="Recipient for delivery"),
    channel: str = typer.Option(None, "--channel", help="Channel for delivery (e.g. 'whatsapp')"),
):
    """Add a scheduled job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    from nanobot.cron.types import CronSchedule
    
    # Determine schedule type
    if every:
        schedule = CronSchedule(kind="every", every_ms=every * 1000)
    elif cron_expr:
        schedule = CronSchedule(kind="cron", expr=cron_expr)
    elif at:
        import datetime
        dt = datetime.datetime.fromisoformat(at)
        schedule = CronSchedule(kind="at", at_ms=int(dt.timestamp() * 1000))
    else:
        console.print("[red]Error: Must specify --every, --cron, or --at[/red]")
        raise typer.Exit(1)
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.add_job(
        name=name,
        schedule=schedule,
        message=message,
        deliver=deliver,
        to=to,
        channel=channel,
    )
    
    console.print(f"[green]✓[/green] Added job '{job.name}' ({job.id})")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="Job ID to remove"),
):
    """Remove a scheduled job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    if service.remove_job(job_id):
        console.print(f"[green]✓[/green] Removed job {job_id}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("enable")
def cron_enable(
    job_id: str = typer.Argument(..., help="Job ID"),
    disable: bool = typer.Option(False, "--disable", help="Disable instead of enable"),
):
    """Enable or disable a job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    job = service.enable_job(job_id, enabled=not disable)
    if job:
        status = "disabled" if disable else "enabled"
        console.print(f"[green]✓[/green] Job '{job.name}' {status}")
    else:
        console.print(f"[red]Job {job_id} not found[/red]")


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="Job ID to run"),
    force: bool = typer.Option(False, "--force", "-f", help="Run even if disabled"),
):
    """Manually run a job."""
    from nanobot.config.loader import get_data_dir
    from nanobot.cron.service import CronService
    
    store_path = get_data_dir() / "cron" / "jobs.json"
    service = CronService(store_path)
    
    async def run():
        return await service.run_job(job_id, force=force)
    
    if asyncio.run(run()):
        console.print(f"[green]✓[/green] Job executed")
    else:
        console.print(f"[red]Failed to run job {job_id}[/red]")


# ============================================================================
# Status Commands
# ============================================================================


@app.command()
def status():
    """Show ZapAssist status."""
    from nanobot.config.loader import load_config, get_config_path

    config_path = get_config_path()
    config = load_config()
    workspace = config.workspace_path

    console.print(f"{__logo__} {__title__} Status\n")

    console.print(f"Config: {config_path} {'[green]✓[/green]' if config_path.exists() else '[red]✗[/red]'}")
    console.print(f"Workspace: {workspace} {'[green]✓[/green]' if workspace.exists() else '[red]✗[/red]'}")

    if config_path.exists():
        console.print(f"Model: {config.agents.defaults.model}")
        
        # Check API keys
        has_deepseek = bool(config.providers.deepseek.api_key)
        has_xiaomi = bool(config.providers.xiaomi.api_key)
        has_openrouter = bool(config.providers.openrouter.api_key)
        has_anthropic = bool(config.providers.anthropic.api_key)
        has_openai = bool(config.providers.openai.api_key)
        has_gemini = bool(config.providers.gemini.api_key)
        has_zhipu = bool(config.providers.zhipu.api_key)
        has_vllm = bool(config.providers.vllm.api_base)
        has_aihubmix = bool(config.providers.aihubmix.api_key)
        
        console.print(f"DeepSeek API: {'[green]✓[/green]' if has_deepseek else '[dim]not set[/dim]'}")
        console.print(f"Xiaomi MiMo API: {'[green]✓[/green]' if has_xiaomi else '[dim]not set[/dim]'}")
        if has_openrouter:
            console.print("OpenRouter API: [green]✓[/green] (opcional)")
        console.print(f"Anthropic API: {'[green]✓[/green]' if has_anthropic else '[dim]not set[/dim]'}")
        console.print(f"OpenAI API: {'[green]✓[/green]' if has_openai else '[dim]not set[/dim]'}")
        console.print(f"Gemini API: {'[green]✓[/green]' if has_gemini else '[dim]not set[/dim]'}")
        console.print(f"Zhipu AI API: {'[green]✓[/green]' if has_zhipu else '[dim]not set[/dim]'}")
        console.print(f"AiHubMix API: {'[green]✓[/green]' if has_aihubmix else '[dim]not set[/dim]'}")
        vllm_status = f"[green]✓ {config.providers.vllm.api_base}[/green]" if has_vllm else "[dim]not set[/dim]"
        console.print(f"vLLM/Local: {vllm_status}")


if __name__ == "__main__":
    app()
