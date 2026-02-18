"""Memory system for persistent agent memory. Isolado por session_key (channel:chat_id) para evitar vazamento entre usuários."""

from pathlib import Path
from datetime import datetime

from zapista.utils.helpers import ensure_dir, today_date, safe_filename


def _memory_dir_for_session(workspace: Path, session_key: str | None) -> Path:
    """Diretório de memória: global (workspace/memory) se session_key vazio; por usuário (workspace/memory/<safe_key>) caso contrário."""
    base = ensure_dir(workspace / "memory")
    if not session_key or not str(session_key).strip():
        return base
    safe_key = safe_filename(str(session_key).strip().replace(":", "_"))
    if not safe_key:
        return base
    return ensure_dir(base / safe_key)


class MemoryStore:
    """
    Memory system for the agent.
    
    Supports daily notes (YYYY-MM-DD.md) and long-term memory (MEMORY.md).
    When session_key is provided to get_memory_context(), memory is scoped per user (channel:chat_id)
    so that no data leaks between conversations.
    """
    
    def __init__(self, workspace: Path):
        self.workspace = workspace
        # Default dir (global) for backward compatibility when session_key is not used
        self.memory_dir = ensure_dir(workspace / "memory")
        self.memory_file = self.memory_dir / "MEMORY.md"
    
    def _dir(self, session_key: str | None) -> Path:
        return _memory_dir_for_session(self.workspace, session_key)
    
    def get_today_file(self, session_key: str | None = None) -> Path:
        """Get path to today's memory file (for the given session if provided)."""
        return self._dir(session_key) / f"{today_date()}.md"
    
    def read_today(self, session_key: str | None = None) -> str:
        """Read today's memory notes."""
        today_file = self.get_today_file(session_key)
        if today_file.exists():
            return today_file.read_text(encoding="utf-8")
        return ""
    
    def append_today(self, content: str, session_key: str | None = None) -> None:
        """Append content to today's memory notes."""
        today_file = self.get_today_file(session_key)
        
        if today_file.exists():
            existing = today_file.read_text(encoding="utf-8")
            content = existing + "\n" + content
        else:
            header = f"# {today_date()}\n\n"
            content = header + content
        
        today_file.write_text(content, encoding="utf-8")
    
    def read_long_term(self, session_key: str | None = None) -> str:
        """Read long-term memory (MEMORY.md) for the given session."""
        path = self._dir(session_key) / "MEMORY.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""
    
    def write_long_term(self, content: str, session_key: str | None = None) -> None:
        """Write to long-term memory (MEMORY.md) for the given session."""
        path = self._dir(session_key) / "MEMORY.md"
        path.write_text(content, encoding="utf-8")
    
    def get_recent_memories(self, days: int = 7, session_key: str | None = None) -> str:
        """Get memories from the last N days for the given session."""
        from datetime import timedelta
        
        memories = []
        try:
            from zapista.clock_drift import get_effective_time
            _now_ts = get_effective_time()
        except Exception:
            import time
            _now_ts = time.time()
        today = datetime.fromtimestamp(_now_ts).date()
        d = self._dir(session_key)
        
        for i in range(days):
            date = today - timedelta(days=i)
            date_str = date.strftime("%Y-%m-%d")
            file_path = d / f"{date_str}.md"
            if file_path.exists():
                content = file_path.read_text(encoding="utf-8")
                memories.append(content)
        
        return "\n\n---\n\n".join(memories)
    
    def list_memory_files(self, session_key: str | None = None) -> list[Path]:
        """List all memory files sorted by date (newest first) for the given session."""
        d = self._dir(session_key)
        if not d.exists():
            return []
        files = list(d.glob("????-??-??.md"))
        return sorted(files, reverse=True)
    
    def upsert_section(self, session_key: str | None, section_heading: str, section_content: str) -> None:
        """
        Atualiza ou insere uma secção no MEMORY.md do utilizador.
        section_heading deve ser do tipo "## Título" (com ##). Substitui o conteúdo
        dessa secção até à próxima ## ou fim do ficheiro; se não existir, acrescenta.
        """
        if not session_key or not str(session_key).strip():
            return
        current = self.read_long_term(session_key)
        lines = current.split("\n") if current else []
        new_section = section_heading.rstrip() + "\n\n" + section_content.strip() + "\n"
        marker = section_heading.strip().lower()
        out: list[str] = []
        i = 0
        replaced = False
        while i < len(lines):
            line = lines[i]
            if line.strip().lower() == marker:
                replaced = True
                out.append(new_section.rstrip())
                i += 1
                while i < len(lines) and not lines[i].strip().startswith("## "):
                    i += 1
                continue
            out.append(line)
            i += 1
        if not replaced:
            if out and out[-1].strip():
                out.append("")
            out.append(new_section.rstrip())
        self.write_long_term("\n".join(out), session_key)

    def get_memory_context(self, session_key: str | None = None) -> str:
        """
        Get memory context for the agent. Pass session_key (e.g. channel:chat_id) to scope
        memory per user and avoid leaking data between conversations.
        """
        parts = []
        long_term = self.read_long_term(session_key)
        if long_term:
            parts.append("## Long-term Memory\n" + long_term)
        today = self.read_today(session_key)
        if today:
            parts.append("## Today's Notes\n" + today)
        return "\n\n".join(parts) if parts else ""
