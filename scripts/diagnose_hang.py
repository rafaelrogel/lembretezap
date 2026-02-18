import sys
import asyncio
import os
import signal
import time
import logging

# Set timeout for the whole script
async def main():
    print("Starting diagnostics...")
    
    # Check if zapista module is importable
    try:
        import zapista
        print(f"Zapista module found at {zapista.__file__}")
    except ImportError as e:
        print(f"ERROR: Could not import zapista: {e}")
        return

    # 1. Check Clock Drift
    print("\n--- Checking clock drift ---")
    try:
        start_time = time.time()
        # Import inside try/except to catch import errors
        from zapista.clock_drift import check_clock_drift
        print("Imported check_clock_drift successfully.")
        
        # Wait max 10 seconds
        print("Running check_clock_drift()...")
        result = await asyncio.wait_for(check_clock_drift(), timeout=10.0)
        print(f"Clock drift result: {result} (took {time.time() - start_time:.2f}s)")
    except asyncio.TimeoutError:
        print("ERROR: Clock drift timed out!")
    except Exception as e:
        print(f"ERROR: Clock drift failed: {e}")
        import traceback
        traceback.print_exc()

    # 2. Check Message Bus (Redis)
    print("\n--- Checking Message Bus ---")
    try:
        from zapista.bus.queue import MessageBus
        bus = MessageBus()
        print(f"MessageBus created. Redis URL: {bus.redis_url}")
        
        if bus.redis_url:
            from zapista.bus.redis_queue import is_redis_available, get_redis_url
            avail = is_redis_available()
            print(f"Redis available checks: is_redis_available={avail}")
            
            # Try to connect if available
            if avail:
                try:
                    from zapista.bus.redis_queue import _get_redis_client
                    client = await _get_redis_client(bus.redis_url)
                    ping = await client.ping()
                    print(f"Redis PING result: {ping}")
                except Exception as ex:
                    print(f"Redis connect failed: {ex}")
    except Exception as e:
        print(f"ERROR: MessageBus check failed: {e}")
        import traceback
        traceback.print_exc()

    # 3. Check Config Load
    print("\n--- Checking Config Load ---")
    try:
        from zapista.config.loader import load_config
        config = load_config()
        print("Config loaded successfully.")
    except Exception as e:
        print(f"ERROR: Config load failed: {e}")
        import traceback
        traceback.print_exc()
        
    print("\nDiagnostics complete.")

if __name__ == "__main__":
    # Add current directory to sys.path
    cwd = os.getcwd()
    sys.path.insert(0, cwd)
    print(f"CWD: {cwd}")
    print(f"PYTHONPATH: {sys.path}")
    
    # Configure basic logging to stdout
    logging.basicConfig(level=logging.DEBUG)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted.")
    except Exception as e:
        print(f"Fatal error in main: {e}")
