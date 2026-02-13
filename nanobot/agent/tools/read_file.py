"""Read file tool for loading workspace files and skills on demand."""

from pathlib import Path
from typing import Any

from nanobot.agent.tools.base import Tool


class ReadFileTool(Tool):
    """Tool to read files from workspace (bootstrap, skills, rules)."""

    def __init__(self, workspace: Path):
        self.workspace = workspace.resolve()

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return (
            "Read a file from the workspace. Use to load: "
            "RULES_DATAS.md (dates/times), RULES_ONBOARDING.md, SOUL.md, USER.md, TOOLS.md, "
            "or skills like skills/cron/SKILL.md, skills/summarize/SKILL.md when needed."
        )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path relative to workspace, e.g. AGENTS.md, RULES_DATAS.md, skills/cron/SKILL.md",
                }
            },
            "required": ["path"],
        }

    async def execute(self, path: str, **kwargs: Any) -> str:
        path = (path or "").strip()
        if not path:
            return "Error: path is required"

        # Normalize: remove leading slashes, resolve .. (but stay inside workspace)
        parts = Path(path).parts
        if not parts:
            return "Error: invalid path"
        # Block path traversal
        if ".." in parts or (len(parts) > 1 and parts[0] in (".", "..")):
            return "Error: path traversal not allowed"

        full_path = (self.workspace / path).resolve()
        ws_resolved = self.workspace.resolve()
        try:
            full_path.relative_to(ws_resolved)
        except (ValueError, AttributeError):
            return "Error: path must be inside workspace"

        if not full_path.exists():
            return f"Error: file not found: {path}"
        if not full_path.is_file():
            return f"Error: not a file: {path}"

        # Limit size (e.g. 100KB)
        max_size = 100 * 1024
        if full_path.stat().st_size > max_size:
            return f"Error: file too large (max {max_size // 1024}KB): {path}"

        try:
            content = full_path.read_text(encoding="utf-8", errors="replace")
            return content
        except Exception as e:
            return f"Error reading file: {e}"
