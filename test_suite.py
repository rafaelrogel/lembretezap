#!/usr/bin/env python3
"""
Zappelin System Stress Test Suite
=================================
Comprehensive stress testing for the Zappelin WhatsApp AI organizer.

Usage:
    python test_suite.py --all              # Run all tests
    python test_suite.py --api              # API stress tests only
    python test_suite.py --security         # Security tests only
    python test_suite.py --rate-limit       # Rate limiting tests only
    python test_suite.py --load             # Load tests only
    python test_suite.py --duration 60      # Custom duration in seconds
    python test_suite.py --concurrency 50   # Custom concurrency level
"""

import argparse
import asyncio
import aiohttp
import time
import json
import sys
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
API_KEY = "zappelin-test-secret-key-12345"  # Change to your test key

HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}


@dataclass
class TestResult:
    """Container for test results."""
    name: str
    total_requests: int = 0
    successes: int = 0
    failures: int = 0
    rate_limited: int = 0
    latencies: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return (self.successes / self.total_requests * 100) if self.total_requests > 0 else 0

    @property
    def avg_latency(self) -> float:
        return sum(self.latencies) / len(self.latencies) if self.latencies else 0

    @property
    def p50_latency(self) -> float:
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.5)
        return sorted_latencies[idx]

    @property
    def p95_latency(self) -> float:
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.95)
        return sorted_latencies[idx]

    @property
    def p99_latency(self) -> float:
        if not self.latencies:
            return 0
        sorted_latencies = sorted(self.latencies)
        idx = int(len(sorted_latencies) * 0.99)
        return sorted_latencies[idx]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "total_requests": self.total_requests,
            "successes": self.successes,
            "failures": self.failures,
            "rate_limited": self.rate_limited,
            "success_rate": f"{self.success_rate:.2f}%",
            "avg_latency_ms": f"{self.avg_latency:.2f}",
            "p50_latency_ms": f"{self.p50_latency:.2f}",
            "p95_latency_ms": f"{self.p95_latency:.2f}",
            "p99_latency_ms": f"{self.p99_latency:.2f}",
            "max_latency_ms": f"{max(self.latencies) if self.latencies else 0:.2f}",
        }


class Colors:
    """ANSI color codes for terminal output."""
    GREEN = "\033[92m"
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


def print_header(text: str):
    """Print a section header."""
    print(f"\n{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{text.center(60)}{Colors.RESET}")
    print(f"{Colors.BOLD}{Colors.CYAN}{'='*60}{Colors.RESET}\n")


def print_result(result: TestResult):
    """Print test result in a formatted table."""
    data = result.to_dict()
    print(f"\n{Colors.BOLD}{data['name']}{Colors.RESET}")
    print("-" * 50)
    print(f"  Requests:      {data['total_requests']}")
    print(f"  Successes:     {Colors.GREEN}{result.successes}{Colors.RESET}")
    print(f"  Failures:     {Colors.RED}{result.failures}{Colors.RESET}")
    print(f"  Rate Limited: {Colors.YELLOW}{result.rate_limited}{Colors.RESET}")
    print(f"  Success Rate: {Colors.GREEN}{data['success_rate']}{Colors.RESET}")
    print("-" * 50)
    print(f"  Latency Avg:  {data['avg_latency_ms']} ms")
    print(f"  Latency P50:  {data['p50_latency_ms']} ms")
    print(f"  Latency P95:  {data['p95_latency_ms']} ms")
    print(f"  Latency P99:  {data['p99_latency_ms']} ms")
    print(f"  Latency Max:  {data['max_latency_ms']} ms")

    if result.errors:
        print(f"\n  {Colors.RED}Errors:{Colors.RESET}")
        for error in result.errors[:5]:  # Show first 5 errors
            print(f"    - {error}")


# =============================================================================
# API STRESS TESTS
# =============================================================================

async def test_health_endpoint(duration: int, concurrency: int) -> TestResult:
    """Stress test the health endpoint."""
    result = TestResult(name="Health Endpoint Stress Test")

    print(f"{Colors.BLUE}Running health endpoint stress test...{Colors.RESET}")
    print(f"  Duration: {duration}s | Concurrency: {concurrency}")

    start_time = time.time()
    request_count = 0

    async with aiohttp.ClientSession() as session:
        while time.time() - start_time < duration:
            batch_start = time.time()

            async def single_request():
                req_start = time.time()
                try:
                    async with session.get(f"{BASE_URL}/health") as resp:
                        latency = (time.time() - req_start) * 1000
                        return {
                            "success": resp.status == 200,
                            "rate_limited": resp.status == 429,
                            "latency": latency,
                            "status": resp.status
                        }
                except Exception as e:
                    return {
                        "success": False,
                        "rate_limited": False,
                        "latency": 0,
                        "error": str(e)
                    }

            # Execute batch
            tasks = [single_request() for _ in range(concurrency)]
            batch_results = await asyncio.gather(*tasks)

            for r in batch_results:
                result.total_requests += 1
                request_count += 1
                if r.get("success"):
                    result.successes += 1
                else:
                    result.failures += 1
                    if r.get("error"):
                        result.errors.append(r["error"])
                if r.get("rate_limited"):
                    result.rate_limited += 1
                if r.get("latency"):
                    result.latencies.append(r["latency"])

            # Brief pause between batches
            await asyncio.sleep(0.1)

    return result


async def test_users_endpoint(duration: int, concurrency: int) -> TestResult:
    """Stress test the GET /users endpoint."""
    result = TestResult(name="GET /users Endpoint Stress Test")

    print(f"{Colors.BLUE}Running /users endpoint stress test...{Colors.RESET}")
    print(f"  Duration: {duration}s | Concurrency: {concurrency}")

    start_time = time.time()

    async with aiohttp.ClientSession() as session:
        while time.time() - start_time < duration:
            async def single_request():
                req_start = time.time()
                try:
                    async with session.get(
                        f"{BASE_URL}/users",
                        headers=HEADERS
                    ) as resp:
                        latency = (time.time() - req_start) * 1000
                        return {
                            "success": resp.status == 200,
                            "rate_limited": resp.status == 429,
                            "latency": latency,
                            "status": resp.status
                        }
                except Exception as e:
                    return {"success": False, "latency": 0, "error": str(e)}

            tasks = [single_request() for _ in range(concurrency)]
            batch_results = await asyncio.gather(*tasks)

            for r in batch_results:
                result.total_requests += 1
                if r.get("success"):
                    result.successes += 1
                else:
                    result.failures += 1
                    if r.get("error"):
                        result.errors.append(r["error"])
                if r.get("rate_limited"):
                    result.rate_limited += 1
                if r.get("latency"):
                    result.latencies.append(r["latency"])

            await asyncio.sleep(0.05)

    return result


async def test_user_lists(duration: int, concurrency: int) -> TestResult:
    """Stress test fetching user lists."""
    result = TestResult(name="GET /users/{id}/lists Endpoint Stress Test")

    print(f"{Colors.BLUE}Running /users/{{id}}/lists endpoint stress test...{Colors.RESET}")

    start_time = time.time()
    user_id = 1

    async with aiohttp.ClientSession() as session:
        while time.time() - start_time < duration:
            async def single_request(uid: int):
                req_start = time.time()
                try:
                    async with session.get(
                        f"{BASE_URL}/users/{uid}/lists",
                        headers=HEADERS
                    ) as resp:
                        latency = (time.time() - req_start) * 1000
                        return {
                            "success": resp.status == 200,
                            "rate_limited": resp.status == 429,
                            "latency": latency,
                            "status": resp.status
                        }
                except Exception as e:
                    return {"success": False, "latency": 0, "error": str(e)}

            # Rotate user IDs
            tasks = [single_request((user_id + i) % 10 + 1) for i in range(concurrency)]

            batch_results = await asyncio.gather(*tasks)

            for r in batch_results:
                result.total_requests += 1
                if r.get("success"):
                    result.successes += 1
                else:
                    result.failures += 1
                    if r.get("error"):
                        result.errors.append(r["error"])
                if r.get("rate_limited"):
                    result.rate_limited += 1
                if r.get("latency"):
                    result.latencies.append(r["latency"])

            user_id = (user_id + concurrency) % 100 + 1
            await asyncio.sleep(0.05)

    return result


async def test_audit_endpoint(duration: int, concurrency: int) -> TestResult:
    """Stress test the audit endpoint with various limits."""
    result = TestResult(name="GET /audit Endpoint Stress Test")

    print(f"{Colors.BLUE}Running /audit endpoint stress test...{Colors.RESET}")

    limits = [100, 250, 500]
    start_time = time.time()

    async with aiohttp.ClientSession() as session:
        while time.time() - start_time < duration:
            async def single_request(limit: int):
                req_start = time.time()
                try:
                    async with session.get(
                        f"{BASE_URL}/audit",
                        headers=HEADERS,
                        params={"limit": limit}
                    ) as resp:
                        latency = (time.time() - req_start) * 1000
                        return {
                            "success": resp.status == 200,
                            "rate_limited": resp.status == 429,
                            "latency": latency,
                            "status": resp.status,
                            "limit": limit
                        }
                except Exception as e:
                    return {"success": False, "latency": 0, "error": str(e)}

            tasks = [single_request(limits[i % len(limits)]) for i in range(concurrency)]
            batch_results = await asyncio.gather(*tasks)

            for r in batch_results:
                result.total_requests += 1
                if r.get("success"):
                    result.successes += 1
                else:
                    result.failures += 1
                    if r.get("error"):
                        result.errors.append(r["error"])
                if r.get("rate_limited"):
                    result.rate_limited += 1
                if r.get("latency"):
                    result.latencies.append(r["latency"])

            await asyncio.sleep(0.05)

    return result


# =============================================================================
# SECURITY TESTS
# =============================================================================

async def test_security_missing_api_key() -> TestResult:
    """Test endpoints without API key."""
    result = TestResult(name="Security: Missing API Key Test")

    print(f"{Colors.BLUE}Testing missing API key protection...{Colors.RESET}")

    endpoints = ["/users", "/users/1/lists", "/users/1/events", "/audit"]

    async with aiohttp.ClientSession() as session:
        for endpoint in endpoints:
            try:
                async with session.get(f"{BASE_URL}{endpoint}") as resp:
                    result.total_requests += 1
                    if resp.status == 401:
                        result.successes += 1
                    else:
                        result.failures += 1
                        result.errors.append(f"{endpoint} returned {resp.status}, expected 401")
            except Exception as e:
                result.total_requests += 1
                result.failures += 1
                result.errors.append(str(e))

    return result


async def test_security_invalid_api_key() -> TestResult:
    """Test endpoints with invalid API key."""
    result = TestResult(name="Security: Invalid API Key Test")

    print(f"{Colors.BLUE}Testing invalid API key protection...{Colors.RESET}")

    invalid_keys = [
        "invalid-key-12345",
        "wrong",
        "a" * 100,
        "",
        None
    ]

    endpoints = ["/users", "/audit"]

    async with aiohttp.ClientSession() as session:
        for invalid_key in invalid_keys:
            headers = {"X-API-Key": invalid_key} if invalid_key else {}

            for endpoint in endpoints:
                try:
                    async with session.get(
                        f"{BASE_URL}{endpoint}",
                        headers=headers
                    ) as resp:
                        result.total_requests += 1
                        if resp.status == 403:
                            result.successes += 1
                        else:
                            result.failures += 1
                            result.errors.append(
                                f"{endpoint} with key '{str(invalid_key)[:10]}...' returned {resp.status}"
                            )
                except Exception as e:
                    result.total_requests += 1
                    result.failures += 1
                    result.errors.append(str(e))

    return result


async def test_security_timing_attack() -> TestResult:
    """Test timing attack resistance."""
    result = TestResult(name="Security: Timing Attack Resistance Test")

    print(f"{Colors.BLUE}Testing timing attack resistance...{Colors.RESET}")

    correct_key = API_KEY
    timings_correct = []
    timings_wrong = []

    async with aiohttp.ClientSession() as session:
        # Test correct key
        for _ in range(20):
            start = time.time()
            try:
                async with session.get(
                    f"{BASE_URL}/users",
                    headers={"X-API-Key": correct_key}
                ) as resp:
                    elapsed = time.time() - start
                    if resp.status == 200:
                        timings_correct.append(elapsed)
            except:
                pass

        # Test wrong key
        for i in range(20):
            wrong_key = correct_key[:-1] + ("0" if i % 2 == 0 else "1")
            start = time.time()
            try:
                async with session.get(
                    f"{BASE_URL}/users",
                    headers={"X-API-Key": wrong_key}
                ) as resp:
                    elapsed = time.time() - start
                    if resp.status == 403:
                        timings_wrong.append(elapsed)
            except:
                pass

    if timings_correct and timings_wrong:
        avg_correct = sum(timings_correct) / len(timings_correct)
        avg_wrong = sum(timings_wrong) / len(timings_wrong)
        diff = abs(avg_correct - avg_wrong)

        result.total_requests = len(timings_correct) + len(timings_wrong)
        result.successes = len(timings_correct) + len(timings_wrong)

        print(f"  Correct key avg: {avg_correct*1000:.2f}ms")
        print(f"  Wrong key avg: {avg_wrong*1000:.2f}ms")
        print(f"  Difference: {diff*1000:.2f}ms")

        # Timing difference should be minimal (< 10ms)
        if diff < 0.01:
            print(f"  {Colors.GREEN}PASS: Timing difference is acceptable{Colors.RESET}")
        else:
            print(f"  {Colors.YELLOW}WARN: Timing difference is high{Colors.RESET}")

        result.latencies = timings_correct + timings_wrong

    return result


async def test_security_rate_limit_bypass() -> TestResult:
    """Test rate limit bypass attempts."""
    result = TestResult(name="Security: Rate Limit Bypass Test")

    print(f"{Colors.BLUE}Testing rate limit bypass attempts...{Colors.RESET}")

    bypass_attempts = [
        ("Empty key", {}),
        ("Very long key", {"X-API-Key": "a" * 10000}),
        ("Path traversal", {"X-API-Key": "../../../etc/passwd"}),
        ("XSS attempt", {"X-API-Key": "<script>alert(1)</script>"}),
        ("SQL injection", {"X-API-Key": "1' OR '1'='1"}),
    ]

    async with aiohttp.ClientSession() as session:
        for name, headers in bypass_attempts:
            try:
                async with session.get(
                    f"{BASE_URL}/users",
                    headers=headers
                ) as resp:
                    result.total_requests += 1
                    if resp.status in [401, 403]:
                        result.successes += 1
                    else:
                        result.failures += 1
                        result.errors.append(f"{name}: unexpected status {resp.status}")
            except Exception as e:
                result.total_requests += 1
                result.failures += 1
                result.errors.append(f"{name}: {str(e)}")

    return result


# =============================================================================
# RATE LIMITING TESTS
# =============================================================================

async def test_rate_limit_token_bucket() -> TestResult:
    """Test rate limiting with token bucket algorithm."""
    result = TestResult(name="Rate Limiting: Token Bucket Test")

    print(f"{Colors.BLUE}Testing token bucket rate limiting...{Colors.RESET}")
    print("  Sending 100 rapid requests to test rate limiting...")

    async with aiohttp.ClientSession() as session:
        for i in range(100):
            try:
                req_start = time.time()
                async with session.get(
                    f"{BASE_URL}/users",
                    headers=HEADERS
                ) as resp:
                    latency = (time.time() - req_start) * 1000
                    result.total_requests += 1

                    if resp.status == 200:
                        result.successes += 1
                    elif resp.status == 429:
                        result.rate_limited += 1
                        result.failures += 1
                    else:
                        result.failures += 1

                    result.latencies.append(latency)
            except Exception as e:
                result.total_requests += 1
                result.failures += 1
                result.errors.append(str(e))

    print(f"  Total requests: {result.total_requests}")
    print(f"  Successful: {result.successes}")
    print(f"  Rate limited (429): {result.rate_limited}")

    # Rate limiting should kick in after ~15 requests
    if result.rate_limited > 0:
        print(f"  {Colors.GREEN}PASS: Rate limiting is working{Colors.RESET}")
    else:
        print(f"  {Colors.YELLOW}INFO: No rate limiting triggered (may be disabled){Colors.RESET}")

    return result


async def test_rate_limit_concurrent_users() -> TestResult:
    """Simulate multiple concurrent users."""
    result = TestResult(name="Rate Limiting: Concurrent Users Test")

    print(f"{Colors.BLUE}Simulating 20 concurrent users...{Colors.RESET}")

    async def user_session(user_id: int):
        user_results = []
        async with aiohttp.ClientSession() as session:
            for i in range(30):  # Each user sends 30 requests
                try:
                    req_start = time.time()
                    async with session.get(
                        f"{BASE_URL}/users",
                        headers=HEADERS
                    ) as resp:
                        latency = (time.time() - req_start) * 1000
                        user_results.append({
                            "user": user_id,
                            "request": i,
                            "status": resp.status,
                            "latency": latency,
                            "limited": resp.status == 429
                        })
                except Exception as e:
                    user_results.append({
                        "user": user_id,
                        "request": i,
                        "error": str(e)
                    })
                await asyncio.sleep(0.01)
        return user_results

    # Run 20 users concurrently
    tasks = [user_session(i) for i in range(20)]
    all_results = await asyncio.gather(*tasks)

    for user_results in all_results:
        for r in user_results:
            result.total_requests += 1
            if r.get("status") == 200:
                result.successes += 1
            elif r.get("limited"):
                result.rate_limited += 1
                result.failures += 1
            else:
                result.failures += 1
            if r.get("latency"):
                result.latencies.append(r["latency"])

    print(f"  Total requests: {result.total_requests}")
    print(f"  Successful: {result.successes}")
    print(f"  Rate limited: {result.rate_limited}")
    print(f"  Success rate: {result.success_rate:.1f}%")

    return result


# =============================================================================
# MAIN TEST RUNNER
# =============================================================================

async def run_api_stress_tests(duration: int, concurrency: int) -> List[TestResult]:
    """Run all API stress tests."""
    results = []

    print_header("API STRESS TESTS")

    results.append(await test_health_endpoint(duration, concurrency))
    results.append(await test_users_endpoint(duration, concurrency))
    results.append(await test_user_lists(duration, concurrency))
    results.append(await test_audit_endpoint(duration, concurrency))

    return results


async def run_security_tests() -> List[TestResult]:
    """Run all security tests."""
    results = []

    print_header("SECURITY TESTS")

    results.append(await test_security_missing_api_key())
    results.append(await test_security_invalid_api_key())
    results.append(await test_security_timing_attack())
    results.append(await test_security_rate_limit_bypass())

    return results


async def run_rate_limit_tests() -> List[TestResult]:
    """Run all rate limiting tests."""
    results = []

    print_header("RATE LIMITING TESTS")

    results.append(await test_rate_limit_token_bucket())
    results.append(await test_rate_limit_concurrent_users())

    return results


async def run_all_tests(duration: int, concurrency: int) -> List[TestResult]:
    """Run all tests."""
    all_results = []

    all_results.extend(await run_api_stress_tests(duration, concurrency))
    all_results.extend(await run_security_tests())
    all_results.extend(await run_rate_limit_tests())

    return all_results


def print_summary(results: List[TestResult]):
    """Print test summary."""
    print_header("TEST SUMMARY")

    total_requests = sum(r.total_requests for r in results)
    total_successes = sum(r.successes for r in results)
    total_failures = sum(r.failures for r in results)
    total_rate_limited = sum(r.rate_limited for r in results)

    all_latencies = []
    for r in results:
        all_latencies.extend(r.latencies)

    print(f"Total Requests:      {total_requests}")
    print(f"Total Successes:    {Colors.GREEN}{total_successes}{Colors.RESET}")
    print(f"Total Failures:     {Colors.RED}{total_failures}{Colors.RESET}")
    print(f"Total Rate Limited: {Colors.YELLOW}{total_rate_limited}{Colors.RESET}")
    print(f"Overall Success:    {Colors.GREEN}{(total_successes/total_requests*100):.2f}%{Colors.RESET}")

    if all_latencies:
        all_latencies.sort()
        print(f"\nOverall Latency:")
        print(f"  Average: {sum(all_latencies)/len(all_latencies):.2f}ms")
        print(f"  P50:      {all_latencies[int(len(all_latencies)*0.5)]:.2f}ms")
        print(f"  P95:      {all_latencies[int(len(all_latencies)*0.95)]:.2f}ms")
        print(f"  P99:      {all_latencies[int(len(all_latencies)*0.99)]:.2f}ms")

    # Print individual results
    print("\n" + "="*60)
    for result in results:
        print_result(result)

    # Save results to JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"stress_test_results_{timestamp}.json"

    with open(filename, "w") as f:
        json.dump({
            "timestamp": timestamp,
            "summary": {
                "total_requests": total_requests,
                "total_successes": total_successes,
                "total_failures": total_failures,
                "total_rate_limited": total_rate_limited,
                "overall_success_rate": f"{(total_successes/total_requests*100):.2f}%"
            },
            "results": [r.to_dict() for r in results]
        }, f, indent=2)

    print(f"\n{Colors.GREEN}Results saved to: {filename}{Colors.RESET}")


async def check_server():
    """Check if the server is running."""
    print(f"{Colors.BLUE}Checking if server is running at {BASE_URL}...{Colors.RESET}")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/health") as resp:
                if resp.status == 200:
                    print(f"{Colors.GREEN}Server is running!{Colors.RESET}")
                    return True
                else:
                    print(f"{Colors.RED}Server returned unexpected status: {resp.status}{Colors.RESET}")
                    return False
    except Exception as e:
        print(f"{Colors.RED}Server is not running: {e}{Colors.RESET}")
        print(f"\n{Colors.YELLOW}Please start the server first:{Colors.RESET}")
        print(f"  uvicorn backend.app:app --host 0.0.0.0 --port 8000")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Zappelin System Stress Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_suite.py --all                    # Run all tests
  python test_suite.py --api                    # API tests only
  python test_suite.py --security               # Security tests only
  python test_suite.py --rate-limit             # Rate limit tests only
  python test_suite.py --duration 60 --concurrency 100  # Custom settings
        """
    )

    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--api", action="store_true", help="Run API stress tests only")
    parser.add_argument("--security", action="store_true", help="Run security tests only")
    parser.add_argument("--rate-limit", action="store_true", help="Run rate limiting tests only")
    parser.add_argument("--duration", type=int, default=10, help="Test duration in seconds (default: 10)")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrent requests (default: 20)")
    parser.add_argument("--check", action="store_true", help="Check if server is running")

    args = parser.parse_args()

    # Check mode
    if args.check:
        asyncio.run(check_server())
        return

    # Check server first
    if not asyncio.run(check_server()):
        sys.exit(1)

    # Determine which tests to run
    run_all = args.all or not (args.api or args.security or args.rate_limit)

    print(f"{Colors.BOLD}")
    print("="*60)
    print("ZAPPELIN SYSTEM STRESS TEST SUITE")
    print("="*60)
    print(f"{Colors.RESET}")
    print(f"Configuration:")
    print(f"  Base URL:     {BASE_URL}")
    print(f"  API Key:      {API_KEY[:10]}...")
    print(f"  Duration:     {args.duration}s per test")
    print(f"  Concurrency:  {args.concurrency} requests")

    results = []

    async def run_tests():
        if run_all:
            return await run_all_tests(args.duration, args.concurrency)
        else:
            tests = []
            if args.api:
                tests.extend(await run_api_stress_tests(args.duration, args.concurrency))
            if args.security:
                tests.extend(await run_security_tests())
            if args.rate_limit:
                tests.extend(await run_rate_limit_tests())
            return tests

    results = asyncio.run(run_tests())
    print_summary(results)


if __name__ == "__main__":
    main()
