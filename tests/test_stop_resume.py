import asyncio
from backend.handler_context import HandlerContext
from backend.router import route
from backend.database import SessionLocal, Base, ENGINE, init_db
from backend.user_store import get_or_create_user
from backend.confirmations import set_pending, get_pending
import os
import sys

# Ensure UTF-8 output for emojis in Windows (only if running as script)
if __name__ == "__main__" and sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Mock bus and tools
class MockBus:
    async def publish_outbound(self, msg): pass

class MockTool:
    def set_context(self, *args, **kwargs): pass
    async def execute(self, *args, **kwargs): return "ok"

async def test_stop_flow():
    # Ensure DB is ready (is_paused column should be there now)
    init_db()
    Base.metadata.create_all(bind=ENGINE)
    
    chat_id = "test_user_stop@s.whatsapp.net"
    ctx = HandlerContext(
        channel="whatsapp",
        chat_id=chat_id,
        cron_service=None,
        cron_tool=MockTool(),
        list_tool=MockTool()
    )

    print("--- Testing /stop prompt ---")
    reply = await route(ctx, "/stop")
    print(f"Reply: {reply}")
    pending = get_pending("whatsapp", chat_id)
    print(f"Pending auto: {pending}")

    print("\n--- Testing confirmation (Sim) ---")
    reply = await route(ctx, "1")
    print(f"Reply: {reply}")
    
    db = SessionLocal()
    user = get_or_create_user(db, chat_id)
    print(f"User is_paused: {user.is_paused}")
    db.close()

    print("\n--- Testing /resume ---")
    reply = await route(ctx, "/resume")
    print(f"Reply: {reply}")
    
    db = SessionLocal()
    user = get_or_create_user(db, chat_id)
    print(f"User is_paused after resume: {user.is_paused}")
    db.close()

    print("\n--- Testing /stop then Não ---")
    await route(ctx, "/stop")
    reply = await route(ctx, "2")
    print(f"Reply: {reply}")
    
    db = SessionLocal()
    user = get_or_create_user(db, chat_id)
    print(f"User is_paused after Non: {user.is_paused}")
    db.close()

if __name__ == "__main__":
    asyncio.run(test_stop_flow())
