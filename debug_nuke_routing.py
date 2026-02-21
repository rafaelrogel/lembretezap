import asyncio
import sys
import os

# Add the project root to sys.path
sys.path.append(os.getcwd())

async def debug_nuke():
    from backend.router import route
    from backend.handler_context import HandlerContext
    
    ctx = HandlerContext(
        channel="cli",
        chat_id="test_user",
        cron_service=None,
        cron_tool=None,
        list_tool=None,
        event_tool=None,
    )
    
    print("--- Debugging /nuke ---")
    content = "/nuke"
    print(f"Input: '{content}'")
    
    try:
        reply = await route(ctx, content)
        print(f"Router Reply: {reply}")
        
        if reply is None:
            print("WARNING: Router returned None for /nuke!")
            
    except Exception as e:
        print(f"Error during routing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_nuke())
