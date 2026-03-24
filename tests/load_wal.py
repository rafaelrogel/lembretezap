import asyncio
import time
import sys
import os
from pathlib import Path
import statistics

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from backend.database import SessionLocal, ENGINE
from zapista.agent.tools.list_tool import ListTool

async def add_item_worker(worker_id: int, results: list):
    """Worker task that adds an item to a test list."""
    tool = ListTool()
    tool.set_context(channel="test", chat_id=f"user_{worker_id}")
    
    start_time = time.perf_counter()
    try:
        # Simulate a write operation
        # We use a unique user per worker to avoid contention on the same List object,
        # but the WAL mode will handle the file-level concurrency.
        result = await tool.execute(action="add", list_name="load_test_list", item_text=f"item_from_worker_{worker_id}")
        latency = (time.perf_counter() - start_time) * 1000 # ms
        results.append(latency)
    except Exception as e:
        print(f"Worker {worker_id} failed: {e}")

async def run_load_test(concurrency: int = 50):
    print(f"🚀 Starting load test with {concurrency} concurrent workers...")
    
    # Ensure WAL is active for the test
    from sqlalchemy import text
    with ENGINE.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL;"))
        status = conn.execute(text("PRAGMA journal_mode;")).scalar()
        print(f"📊 Database journal mode: {status}")

    results = []
    tasks = [add_item_worker(i, results) for i in range(concurrency)]
    
    total_start = time.perf_counter()
    await asyncio.gather(*tasks)
    total_duration = time.perf_counter() - total_start
    
    if not results:
        print("❌ No successful requests.")
        return

    avg_latency = statistics.mean(results)
    p95_latency = statistics.quantiles(results, n=20)[18]  # 95th percentile
    throughput = len(results) / total_duration

    print("\n" + "="*40)
    print(f"🏁 Load Test Results ({len(results)} requests)")
    print("="*40)
    print(f"Total Duration: {total_duration:.2f} s")
    print(f"Throughput:     {throughput:.2f} req/s")
    print(f"Avg Latency:    {avg_latency:.2f} ms")
    print(f"P95 Latency:    {p95_latency:.2f} ms")
    print("="*40)
    
    if p95_latency < 100:
        print("✅ PERFORMANCE OK: P95 is below 100ms")
    else:
        print("⚠️ PERFORMANCE ALERT: P95 is above 100ms")

if __name__ == "__main__":
    asyncio.run(run_load_test(50))
