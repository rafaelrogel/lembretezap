
import asyncio
import sys
import os
sys.path.append(os.getcwd())
from backend.router import route
from backend.handler_context import HandlerContext
from unittest.mock import AsyncMock, MagicMock

async def test():
    cron_tool = MagicMock()
    # Mocking as AsyncMock to be awaitable
    cron_tool.execute = AsyncMock(return_value="Registered!")
    cron_tool.set_context = MagicMock()
    
    ctx = HandlerContext(
        channel="cli",
        chat_id="user1",
        cron_service=MagicMock(),
        cron_tool=cron_tool,
        list_tool=MagicMock(),
        event_tool=MagicMock(),
        session_manager=MagicMock(),
        scope_provider=MagicMock(),
        scope_model="test-model",
        main_provider=MagicMock(),
        main_model="test-model",
    )
    # Using the exact content from the failing test
    content = "Me lembre de beber água a cada 2 horas"
    res = await route(ctx, content)
    print(f"Content: '{content}' -> Result: '{res}'")

if __name__ == "__main__":
    asyncio.run(test())
