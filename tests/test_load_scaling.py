"""
LOAD SCALING TESTS - 50, 100, 200, 500 concurrent users
========================================================
Tests system behavior under increasing load.
"""

import asyncio
import random
import time
import os
import sys

import pytest

if os.path.dirname(os.path.dirname(os.path.abspath(__file__))) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


COMMAND_TEMPLATES = [
    "/help", "/ajuda", "/ayuda",
    "/hoje", "/hoy", "/today",
    "/semana", "/week",
    "/hora", "/time", "/data", "/date",
    "/start",
]


async def _run_load_test(num_users: int, commands_per_user: int = 10):
    """Run a load test with N concurrent users, each sending M commands."""
    from backend.handler_context import HandlerContext
    from backend.router import route
    from backend.database import SessionLocal, init_db
    from backend.user_store import get_or_create_user

    init_db()

    results = {
        "success": 0, "failures": 0, "exceptions": [],
        "response_times": [],
    }

    async def simulate_user(uid: int):
        user_results = {"success": 0, "failures": 0, "exceptions": [], "times": []}
        chat_id = f"load_{num_users}u_{uid}_{random.randint(1000, 9999)}"

        db = SessionLocal()
        try:
            get_or_create_user(db, chat_id)
        finally:
            db.close()

        ctx = HandlerContext(
            channel="test", chat_id=chat_id,
            cron_service=None, cron_tool=None,
            list_tool=None, event_tool=None,
        )

        for _ in range(commands_per_user):
            cmd = random.choice(COMMAND_TEMPLATES)
            start = time.perf_counter()
            try:
                await route(ctx, cmd)
                user_results["times"].append(time.perf_counter() - start)
                user_results["success"] += 1
            except Exception as e:
                user_results["failures"] += 1
                user_results["exceptions"].append(f"U{uid}: {type(e).__name__}: {str(e)[:80]}")
        return user_results

    total_ops = num_users * commands_per_user
    print(f"\n[LOAD {num_users}U] {num_users} users x {commands_per_user} cmds = {total_ops} ops...")
    t0 = time.perf_counter()

    tasks = [simulate_user(i) for i in range(num_users)]
    raw = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed = time.perf_counter() - t0

    for res in raw:
        if isinstance(res, Exception):
            results["failures"] += 1
            results["exceptions"].append(f"Task: {type(res).__name__}: {str(res)[:80]}")
        else:
            results["success"] += res["success"]
            results["failures"] += res["failures"]
            results["exceptions"].extend(res["exceptions"])
            results["response_times"].extend(res["times"])

    avg_ms = (sum(results["response_times"]) / len(results["response_times"]) * 1000) if results["response_times"] else 0
    p95_ms = sorted(results["response_times"])[int(len(results["response_times"]) * 0.95)] * 1000 if results["response_times"] else 0
    max_ms = max(results["response_times"]) * 1000 if results["response_times"] else 0
    ops_s = total_ops / elapsed if elapsed > 0 else 0

    print(f"[LOAD {num_users}U] RESULTS:")
    print(f"  OK: {results['success']}  FAIL: {results['failures']}")
    print(f"  Time: {elapsed:.2f}s  Ops/s: {ops_s:.0f}")
    print(f"  Latency avg: {avg_ms:.1f}ms  p95: {p95_ms:.1f}ms  max: {max_ms:.1f}ms")

    if results["exceptions"]:
        print(f"  Exceptions ({len(results['exceptions'])}):")
        for exc in results["exceptions"][:5]:
            print(f"    - {exc}")

    return results, elapsed, total_ops


@pytest.mark.asyncio
async def test_load_50_users():
    """50 concurrent users, 10 commands each = 500 ops."""
    results, elapsed, total = await _run_load_test(50)
    assert results["failures"] == 0, f"{results['failures']} failures: {results['exceptions'][:3]}"
    assert results["success"] == total
    assert elapsed < 30, f"Too slow: {elapsed:.1f}s"


@pytest.mark.asyncio
async def test_load_100_users():
    """100 concurrent users, 10 commands each = 1000 ops."""
    results, elapsed, total = await _run_load_test(100)
    assert results["failures"] == 0, f"{results['failures']} failures: {results['exceptions'][:3]}"
    assert results["success"] == total
    assert elapsed < 60, f"Too slow: {elapsed:.1f}s"


@pytest.mark.asyncio
async def test_load_200_users():
    """200 concurrent users, 10 commands each = 2000 ops."""
    results, elapsed, total = await _run_load_test(200)
    assert results["failures"] == 0, f"{results['failures']} failures: {results['exceptions'][:3]}"
    assert results["success"] == total
    assert elapsed < 120, f"Too slow: {elapsed:.1f}s"


@pytest.mark.asyncio
async def test_load_500_users():
    """500 concurrent users, 10 commands each = 5000 ops."""
    results, elapsed, total = await _run_load_test(500)
    assert results["failures"] == 0, f"{results['failures']} failures: {results['exceptions'][:3]}"
    assert results["success"] == total
    assert elapsed < 300, f"Too slow: {elapsed:.1f}s"
