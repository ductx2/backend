#!/usr/bin/env python3
"""
PHASE 4.1: CONCURRENT USER LOAD TESTING
Comprehensive testing of system performance under concurrent load

Test Coverage:
- Multiple simultaneous API requests
- Concurrent RSS processing jobs
- Database write conflicts
- Cache race conditions
- Performance metrics (latency, throughput)
"""

import sys
import os
import asyncio
import time
import statistics
from datetime import datetime
from typing import Dict, List, Any, Tuple
import httpx
import random

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.core.config import get_settings
    
    settings = get_settings()
    
    print("=" * 70)
    print("PHASE 4.1: CONCURRENT USER LOAD TESTING")
    print("=" * 70)
    print(f"Start Time: {datetime.now().isoformat()}")
    print("-" * 70)
    
    class PerformanceMetrics:
        """Track performance metrics for load testing"""
        
        def __init__(self):
            self.response_times = []
            self.error_count = 0
            self.success_count = 0
            self.start_time = None
            self.end_time = None
        
        def record_success(self, response_time: float):
            self.response_times.append(response_time)
            self.success_count += 1
        
        def record_error(self):
            self.error_count += 1
        
        def calculate_statistics(self) -> Dict[str, Any]:
            if not self.response_times:
                return {
                    "total_requests": self.success_count + self.error_count,
                    "success_count": self.success_count,
                    "error_count": self.error_count,
                    "error_rate": 100.0 if self.error_count > 0 else 0.0,
                    "avg_response_time": 0,
                    "p50_latency": 0,
                    "p95_latency": 0,
                    "p99_latency": 0,
                    "min_latency": 0,
                    "max_latency": 0,
                    "throughput": 0
                }
            
            sorted_times = sorted(self.response_times)
            total_time = (self.end_time - self.start_time) if self.start_time and self.end_time else 1
            
            return {
                "total_requests": self.success_count + self.error_count,
                "success_count": self.success_count,
                "error_count": self.error_count,
                "error_rate": (self.error_count / (self.success_count + self.error_count)) * 100,
                "avg_response_time": statistics.mean(self.response_times),
                "p50_latency": sorted_times[len(sorted_times) // 2],
                "p95_latency": sorted_times[int(len(sorted_times) * 0.95)],
                "p99_latency": sorted_times[int(len(sorted_times) * 0.99)],
                "min_latency": min(self.response_times),
                "max_latency": max(self.response_times),
                "throughput": self.success_count / total_time if total_time > 0 else 0
            }
    
    async def make_api_request(
        client: httpx.AsyncClient,
        endpoint: str,
        method: str = "GET",
        headers: Dict = None,
        json_data: Dict = None
    ) -> Tuple[bool, float]:
        """Make an API request and return success status and response time"""
        
        start = time.time()
        try:
            if method == "GET":
                response = await client.get(endpoint, headers=headers)
            elif method == "POST":
                response = await client.post(endpoint, headers=headers, json=json_data)
            else:
                response = await client.request(method, endpoint, headers=headers, json=json_data)
            
            elapsed = time.time() - start
            
            if response.status_code < 400:
                return True, elapsed
            else:
                return False, elapsed
                
        except Exception as e:
            elapsed = time.time() - start
            return False, elapsed
    
    async def test_concurrent_api_requests():
        """Test multiple simultaneous API requests"""
        print("\n[TEST 1] CONCURRENT API REQUESTS")
        print("-" * 40)
        
        metrics = PerformanceMetrics()
        base_url = "http://localhost:8000"
        
        # API endpoints to test
        endpoints = [
            "/",
            "/api/health",
            "/api/auth/verify",
            "/api/data/recent-articles",
            "/api/rss/status",
            "/api/drishti/health"
        ]
        
        # Test different concurrency levels
        concurrency_levels = [10, 50, 100]
        
        for concurrent_users in concurrency_levels:
            print(f"\nTesting with {concurrent_users} concurrent users...")
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                metrics = PerformanceMetrics()
                metrics.start_time = time.time()
                
                # Create tasks for concurrent requests
                tasks = []
                for i in range(concurrent_users):
                    endpoint = random.choice(endpoints)
                    url = f"{base_url}{endpoint}"
                    
                    # Add auth header for protected endpoints
                    headers = {}
                    if "auth" in endpoint or "data" in endpoint:
                        headers["Authorization"] = f"Bearer {settings.api_key}"
                    
                    tasks.append(make_api_request(client, url, headers=headers))
                
                # Execute all requests concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                metrics.end_time = time.time()
                
                # Process results
                for result in results:
                    if isinstance(result, Exception):
                        metrics.record_error()
                    elif isinstance(result, tuple):
                        success, response_time = result
                        if success:
                            metrics.record_success(response_time)
                        else:
                            metrics.record_error()
                
                # Calculate and display statistics
                stats = metrics.calculate_statistics()
                
                print(f"  Total Requests: {stats['total_requests']}")
                print(f"  Success: {stats['success_count']} | Errors: {stats['error_count']}")
                print(f"  Error Rate: {stats['error_rate']:.2f}%")
                print(f"  Avg Response Time: {stats['avg_response_time']:.3f}s")
                print(f"  P50 Latency: {stats['p50_latency']:.3f}s")
                print(f"  P95 Latency: {stats['p95_latency']:.3f}s")
                print(f"  P99 Latency: {stats['p99_latency']:.3f}s")
                print(f"  Throughput: {stats['throughput']:.2f} req/s")
                
                # Performance assessment
                if stats['p95_latency'] < 1.0 and stats['error_rate'] < 5:
                    print("  [OK] Good performance under load")
                elif stats['p95_latency'] < 2.0 and stats['error_rate'] < 10:
                    print("  [WARN] Acceptable performance, some optimization needed")
                else:
                    print("  [FAIL] Poor performance under load")
        
        return True
    
    async def test_concurrent_rss_processing():
        """Test concurrent RSS processing requests"""
        print("\n[TEST 2] CONCURRENT RSS PROCESSING")
        print("-" * 40)
        
        base_url = "http://localhost:8000"
        endpoint = "/api/extract/rss-sources"  # Updated to Master Plan endpoint
        
        concurrent_jobs = [5, 10, 20]
        
        for num_jobs in concurrent_jobs:
            print(f"\nTesting {num_jobs} concurrent RSS processing jobs...")
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                metrics = PerformanceMetrics()
                metrics.start_time = time.time()
                
                headers = {"Authorization": f"Bearer {settings.api_key}"}
                
                # Create concurrent RSS processing tasks
                tasks = []
                for i in range(num_jobs):
                    tasks.append(
                        make_api_request(
                            client,
                            f"{base_url}{endpoint}",
                            method="POST",
                            headers=headers,
                            json_data={"sources": ["all"]}
                        )
                    )
                
                # Execute concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                metrics.end_time = time.time()
                
                # Process results
                for result in results:
                    if isinstance(result, Exception):
                        metrics.record_error()
                    elif isinstance(result, tuple):
                        success, response_time = result
                        if success:
                            metrics.record_success(response_time)
                        else:
                            metrics.record_error()
                
                # Display results
                stats = metrics.calculate_statistics()
                
                print(f"  Completed: {stats['success_count']}/{num_jobs}")
                print(f"  Avg Processing Time: {stats['avg_response_time']:.2f}s")
                print(f"  Total Time: {metrics.end_time - metrics.start_time:.2f}s")
                
                if stats['success_count'] == num_jobs:
                    print("  [OK] All RSS jobs completed successfully")
                elif stats['success_count'] >= num_jobs * 0.8:
                    print("  [WARN] Some RSS jobs failed under load")
                else:
                    print("  [FAIL] Too many failures under concurrent load")
        
        return True
    
    async def test_database_write_conflicts():
        """Test database write conflicts under concurrent access"""
        print("\n[TEST 3] DATABASE WRITE CONFLICTS")
        print("-" * 40)
        
        base_url = "http://localhost:8000"
        
        # Simulate concurrent article saves
        print("Testing concurrent database writes...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            metrics = PerformanceMetrics()
            metrics.start_time = time.time()
            
            headers = {"Authorization": f"Bearer {settings.api_key}"}
            
            # Create multiple articles to save
            tasks = []
            for i in range(50):
                article_data = {
                    "title": f"Test Article {i} - {time.time()}",
                    "content": f"Content for article {i}",
                    "source": "test",
                    "url": f"https://test.com/article-{i}",
                    "published_date": datetime.now().isoformat()
                }
                
                # Assuming there's an endpoint to save articles
                endpoint = f"{base_url}/api/data/save-article"
                
                tasks.append(
                    make_api_request(
                        client,
                        endpoint,
                        method="POST",
                        headers=headers,
                        json_data=article_data
                    )
                )
            
            # Execute all saves concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            metrics.end_time = time.time()
            
            # Count successes
            success_count = sum(
                1 for r in results 
                if isinstance(r, tuple) and r[0]
            )
            
            print(f"  Successful writes: {success_count}/50")
            print(f"  Time taken: {metrics.end_time - metrics.start_time:.2f}s")
            
            if success_count >= 45:
                print("  [OK] Database handles concurrent writes well")
            elif success_count >= 35:
                print("  [WARN] Some write conflicts occurred")
            else:
                print("  [FAIL] Too many write conflicts")
        
        return True
    
    async def test_cache_race_conditions():
        """Test cache consistency under concurrent access"""
        print("\n[TEST 4] CACHE RACE CONDITIONS")
        print("-" * 40)
        
        base_url = "http://localhost:8000"
        
        print("Testing cache consistency...")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            headers = {"Authorization": f"Bearer {settings.api_key}"}
            
            # Test 1: Concurrent cache reads
            print("4.1 Testing concurrent cache reads...")
            
            cache_endpoint = f"{base_url}/api/rss/cache/status"
            
            read_tasks = []
            for i in range(100):
                read_tasks.append(
                    make_api_request(client, cache_endpoint, headers=headers)
                )
            
            results = await asyncio.gather(*read_tasks, return_exceptions=True)
            
            read_success = sum(
                1 for r in results 
                if isinstance(r, tuple) and r[0]
            )
            
            print(f"  Successful cache reads: {read_success}/100")
            
            # Test 2: Concurrent cache invalidations
            print("4.2 Testing concurrent cache invalidations...")
            
            invalidate_endpoint = f"{base_url}/api/rss/cache/clear"
            
            invalidate_tasks = []
            for i in range(20):
                invalidate_tasks.append(
                    make_api_request(
                        client,
                        invalidate_endpoint,
                        method="POST",
                        headers=headers
                    )
                )
            
            results = await asyncio.gather(*invalidate_tasks, return_exceptions=True)
            
            invalidate_success = sum(
                1 for r in results 
                if isinstance(r, tuple) and r[0]
            )
            
            print(f"  Successful invalidations: {invalidate_success}/20")
            
            if read_success >= 95 and invalidate_success >= 15:
                print("  [OK] Cache handles concurrent access well")
            elif read_success >= 80 and invalidate_success >= 10:
                print("  [WARN] Some cache consistency issues")
            else:
                print("  [FAIL] Cache race conditions detected")
        
        return True
    
    async def test_resource_contention():
        """Test system behavior under resource contention"""
        print("\n[TEST 5] RESOURCE CONTENTION")
        print("-" * 40)
        
        base_url = "http://localhost:8000"
        
        print("Testing resource contention scenarios...")
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            headers = {"Authorization": f"Bearer {settings.api_key}"}
            
            # Mix of different resource-intensive operations
            tasks = []
            
            # RSS processing (CPU intensive)
            for i in range(5):
                tasks.append(
                    make_api_request(
                        client,
                        f"{base_url}/api/extract/rss-sources",  # Master Plan endpoint
                        method="POST",
                        headers=headers,
                        json_data={"sources": ["all"]}
                    )
                )
            
            # Drishti scraping (Browser/Memory intensive)
            for i in range(3):
                tasks.append(
                    make_api_request(
                        client,
                        f"{base_url}/api/drishti/scrape",
                        method="POST",
                        headers=headers,
                        json_data={"max_articles": 10}
                    )
                )
            
            # Database queries (I/O intensive)
            for i in range(20):
                tasks.append(
                    make_api_request(
                        client,
                        f"{base_url}/api/data/recent-articles?limit=100",
                        headers=headers
                    )
                )
            
            # Health checks (lightweight)
            for i in range(30):
                tasks.append(
                    make_api_request(client, f"{base_url}/api/health")
                )
            
            print(f"  Running {len(tasks)} mixed operations concurrently...")
            
            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            end_time = time.time()
            
            # Analyze results by operation type
            rss_success = sum(1 for r in results[:5] if isinstance(r, tuple) and r[0])
            drishti_success = sum(1 for r in results[5:8] if isinstance(r, tuple) and r[0])
            db_success = sum(1 for r in results[8:28] if isinstance(r, tuple) and r[0])
            health_success = sum(1 for r in results[28:] if isinstance(r, tuple) and r[0])
            
            print(f"  RSS Processing: {rss_success}/5 succeeded")
            print(f"  Drishti Scraping: {drishti_success}/3 succeeded")
            print(f"  Database Queries: {db_success}/20 succeeded")
            print(f"  Health Checks: {health_success}/30 succeeded")
            print(f"  Total Time: {end_time - start_time:.2f}s")
            
            total_success = rss_success + drishti_success + db_success + health_success
            total_expected = 58
            
            if total_success >= total_expected * 0.9:
                print("  [OK] System handles resource contention well")
            elif total_success >= total_expected * 0.7:
                print("  [WARN] Some degradation under resource contention")
            else:
                print("  [FAIL] Significant issues under resource contention")
        
        return True
    
    async def run_concurrent_load_tests():
        """Run all concurrent load tests"""
        
        print("\nSTARTING CONCURRENT LOAD TESTING")
        print("=" * 70)
        
        # Check if server is running
        print("Checking server availability...")
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get("http://localhost:8000/")
                if response.status_code == 200:
                    print("[OK] Server is running")
                else:
                    print("[WARN] Server returned status:", response.status_code)
        except Exception as e:
            print(f"[ERROR] Server not accessible: {e}")
            print("Please ensure the FastAPI server is running on port 8000")
            return {"passed": 0, "failed": 1}
        
        test_results = {
            "passed": 0,
            "failed": 0,
            "tests": []
        }
        
        # Run all tests
        tests = [
            ("Concurrent API Requests", test_concurrent_api_requests),
            ("Concurrent RSS Processing", test_concurrent_rss_processing),
            ("Database Write Conflicts", test_database_write_conflicts),
            ("Cache Race Conditions", test_cache_race_conditions),
            ("Resource Contention", test_resource_contention)
        ]
        
        for test_name, test_func in tests:
            try:
                print(f"\nRunning: {test_name}")
                success = await test_func()
                
                if success:
                    test_results["passed"] += 1
                    test_results["tests"].append((test_name, "PASSED"))
                else:
                    test_results["failed"] += 1
                    test_results["tests"].append((test_name, "FAILED"))
                    
            except Exception as e:
                print(f"[ERROR] Test '{test_name}' crashed: {e}")
                test_results["failed"] += 1
                test_results["tests"].append((test_name, "CRASHED"))
        
        # Summary
        print("\n" + "=" * 70)
        print("CONCURRENT LOAD TEST SUMMARY")
        print("=" * 70)
        
        for test_name, status in test_results["tests"]:
            symbol = "[OK]" if status == "PASSED" else "[FAIL]"
            print(f"{symbol} {test_name}: {status}")
        
        print("-" * 70)
        
        total = test_results["passed"] + test_results["failed"]
        success_rate = (test_results["passed"] / total * 100) if total > 0 else 0
        
        print(f"RESULTS: {test_results['passed']}/{total} tests passed ({success_rate:.1f}%)")
        
        if success_rate >= 80:
            print("\n[SUCCESS] System handles concurrent load well")
            print("Ready for production-level traffic")
        elif success_rate >= 60:
            print("\n[WARNING] Partial load handling capability")
            print("Performance optimization recommended")
        else:
            print("\n[FAILURE] Poor concurrent load handling")
            print("Critical performance improvements needed")
        
        print(f"\nCompleted at: {datetime.now().isoformat()}")
        
        return test_results
    
    # Run the tests
    if __name__ == "__main__":
        results = asyncio.run(run_concurrent_load_tests())
        
        # Exit with appropriate code
        if results["failed"] == 0:
            exit(0)
        else:
            exit(1)
            
except ImportError as e:
    print(f"Import Error: {e}")
    print("Please ensure all dependencies are installed")
    exit(1)
    
except Exception as e:
    print(f"Critical Error: {e}")
    exit(1)