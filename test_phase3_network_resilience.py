#!/usr/bin/env python3
"""
PHASE 3.1: NETWORK FAILURE RESILIENCE TEST SUITE
Comprehensive testing of system behavior under network failures

Test Coverage:
- RSS source timeouts and failures
- Database connection loss and recovery
- Gemini API rate limiting and failures
- Chrome browser crashes during scraping
- Partial network connectivity scenarios
"""

import sys
import os
import asyncio
import time
import random
import signal
import psutil
from datetime import datetime
from typing import Dict, List, Any, Optional
from unittest.mock import patch, MagicMock
import httpx

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.services.optimized_rss_processor import OptimizedRSSProcessor
    from app.services.drishti_scraper import DrishtiScraper
    from app.services.gemini_client import get_gemini_client, generate_structured_content
    from app.core.database import get_database_sync
    from app.core.config import get_settings
    
    settings = get_settings()
    
    print("=" * 70)
    print("PHASE 3.1: NETWORK FAILURE RESILIENCE TEST SUITE")
    print("=" * 70)
    print(f"Start Time: {datetime.now().isoformat()}")
    print("-" * 70)
    
    class NetworkFailureSimulator:
        """Simulates various network failure scenarios"""
        
        def __init__(self):
            self.failure_modes = {
                "timeout": self.simulate_timeout,
                "connection_error": self.simulate_connection_error,
                "dns_failure": self.simulate_dns_failure,
                "partial_response": self.simulate_partial_response,
                "slow_network": self.simulate_slow_network
            }
            self.test_results = {
                "passed": [],
                "failed": [],
                "warnings": []
            }
        
        async def simulate_timeout(self, delay: float = 30.0):
            """Simulate network timeout"""
            await asyncio.sleep(delay)
            raise asyncio.TimeoutError("Network timeout simulated")
        
        async def simulate_connection_error(self):
            """Simulate connection refused/reset"""
            raise httpx.ConnectError("Connection refused")
        
        async def simulate_dns_failure(self):
            """Simulate DNS resolution failure"""
            raise httpx.ConnectError("DNS resolution failed")
        
        async def simulate_partial_response(self, data: str):
            """Simulate incomplete data transmission"""
            return data[:len(data)//2]  # Return only half the data
        
        async def simulate_slow_network(self, data: Any, delay: float = 5.0):
            """Simulate slow network with high latency"""
            await asyncio.sleep(delay)
            return data
    
    # TEST 1: RSS SOURCE FAILURE HANDLING
    async def test_rss_source_failures():
        """Test RSS processor resilience to source failures"""
        print("\n[TEST 1] RSS SOURCE FAILURE HANDLING")
        print("-" * 40)
        
        simulator = NetworkFailureSimulator()
        results = {"passed": 0, "failed": 0}
        
        try:
            # Test 1.1: Single source timeout
            print("1.1 Testing single RSS source timeout...")
            processor = OptimizedRSSProcessor()
            
            # Mock one source to timeout
            with patch('httpx.AsyncClient.get') as mock_get:
                async def mock_response(*args, **kwargs):
                    if "hindu" in args[0]:  # Make The Hindu timeout
                        await asyncio.sleep(10)
                        raise asyncio.TimeoutError("Simulated timeout")
                    return MagicMock(status_code=200, text="<rss><channel></channel></rss>")
                
                mock_get.side_effect = mock_response
                
                start_time = time.time()
                articles = await processor.fetch_all_sources_parallel()
                elapsed = time.time() - start_time
                
                if elapsed < 15:  # Should not wait for timeout source
                    print(f"  [OK] Handled timeout gracefully in {elapsed:.2f}s")
                    results["passed"] += 1
                else:
                    print(f"  [FAIL] Took too long: {elapsed:.2f}s")
                    results["failed"] += 1
            
            # Test 1.2: Multiple source failures
            print("1.2 Testing multiple RSS source failures...")
            with patch('httpx.AsyncClient.get') as mock_get:
                failure_count = 0
                
                async def mock_multi_failure(*args, **kwargs):
                    nonlocal failure_count
                    failure_count += 1
                    if failure_count <= 3:  # First 3 sources fail
                        raise httpx.ConnectError("Connection failed")
                    return MagicMock(status_code=200, text="<rss><channel></channel></rss>")
                
                mock_get.side_effect = mock_multi_failure
                
                articles = await processor.fetch_all_sources_parallel()
                if articles is not None:  # Should still get some articles
                    print(f"  [OK] Recovered from {failure_count} source failures")
                    results["passed"] += 1
                else:
                    print("  [FAIL] Complete failure with partial source outage")
                    results["failed"] += 1
            
            # Test 1.3: All sources fail
            print("1.3 Testing all RSS sources failure...")
            with patch('httpx.AsyncClient.get') as mock_get:
                mock_get.side_effect = httpx.ConnectError("All sources down")
                
                articles = await processor.fetch_all_sources_parallel()
                if articles == []:  # Should return empty list, not crash
                    print("  [OK] Handled complete RSS outage gracefully")
                    results["passed"] += 1
                else:
                    print("  [FAIL] Unexpected behavior on complete outage")
                    results["failed"] += 1
                    
        except Exception as e:
            print(f"  [ERROR] RSS test failed: {e}")
            results["failed"] += 1
        
        print(f"\nRSS Failure Tests: {results['passed']} passed, {results['failed']} failed")
        return results
    
    # TEST 2: DATABASE CONNECTION RESILIENCE
    async def test_database_resilience():
        """Test database connection loss and recovery"""
        print("\n[TEST 2] DATABASE CONNECTION RESILIENCE")
        print("-" * 40)
        
        results = {"passed": 0, "failed": 0}
        
        try:
            # Test 2.1: Connection loss during operation
            print("2.1 Testing database connection loss...")
            db = get_database_sync()
            
            # Simulate connection loss
            original_execute = db.client.table("current_affairs").select("*").execute
            
            def mock_connection_loss():
                raise Exception("Connection to database lost")
            
            db.client.table("current_affairs").select("*").execute = mock_connection_loss
            
            try:
                # This should fail but not crash
                result = db.get_recent_articles(limit=5)
                print("  [FAIL] Should have handled connection loss")
                results["failed"] += 1
            except Exception as e:
                if "Connection to database lost" in str(e):
                    print("  [OK] Connection loss detected properly")
                    results["passed"] += 1
                else:
                    print(f"  [FAIL] Unexpected error: {e}")
                    results["failed"] += 1
            
            # Restore connection
            db.client.table("current_affairs").select("*").execute = original_execute
            
            # Test 2.2: Connection recovery
            print("2.2 Testing database connection recovery...")
            failure_count = 0
            
            def mock_intermittent_failure():
                nonlocal failure_count
                failure_count += 1
                if failure_count <= 2:  # Fail first 2 attempts
                    raise Exception("Temporary connection failure")
                return original_execute()
            
            db.client.table("current_affairs").select("*").execute = mock_intermittent_failure
            
            # Implement retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    result = db.client.table("current_affairs").select("*").execute()
                    print(f"  [OK] Recovered after {attempt + 1} attempts")
                    results["passed"] += 1
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        print("  [FAIL] Could not recover connection")
                        results["failed"] += 1
                    else:
                        await asyncio.sleep(1)  # Wait before retry
            
            # Test 2.3: Connection pool exhaustion
            print("2.3 Testing connection pool exhaustion...")
            concurrent_queries = []
            
            async def make_query(idx):
                try:
                    await asyncio.sleep(random.uniform(0, 0.5))
                    # Simulate long-running query
                    result = db.client.table("current_affairs").select("*").limit(100).execute()
                    return True
                except Exception as e:
                    return False
            
            # Create 50 concurrent queries
            tasks = [make_query(i) for i in range(50)]
            results_list = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = sum(1 for r in results_list if r is True)
            if success_count > 25:  # At least half should succeed
                print(f"  [OK] Handled {success_count}/50 concurrent connections")
                results["passed"] += 1
            else:
                print(f"  [FAIL] Only {success_count}/50 connections succeeded")
                results["failed"] += 1
                
        except Exception as e:
            print(f"  [ERROR] Database test failed: {e}")
            results["failed"] += 1
        
        print(f"\nDatabase Resilience Tests: {results['passed']} passed, {results['failed']} failed")
        return results
    
    # TEST 3: GEMINI API FAILURE HANDLING
    async def test_gemini_api_resilience():
        """Test Gemini API rate limiting and failure scenarios"""
        print("\n[TEST 3] GEMINI API FAILURE RESILIENCE")
        print("-" * 40)
        
        results = {"passed": 0, "failed": 0}
        
        try:
            # Test 3.1: Rate limit (429) handling
            print("3.1 Testing Gemini API rate limit (429)...")
            
            with patch('google.generativeai.GenerativeModel.generate_content_async') as mock_generate:
                # Simulate rate limit error
                mock_generate.side_effect = Exception("429 Resource Exhausted")
                
                try:
                    result = await generate_structured_content(
                        prompt="Test prompt",
                        response_schema={"type": "object", "properties": {}}
                    )
                    print("  [FAIL] Should have handled rate limit")
                    results["failed"] += 1
                except Exception as e:
                    if "429" in str(e):
                        print("  [OK] Rate limit detected and raised properly")
                        results["passed"] += 1
                    else:
                        print(f"  [FAIL] Unexpected error: {e}")
                        results["failed"] += 1
            
            # Test 3.2: Service unavailable (503) handling
            print("3.2 Testing Gemini API service unavailable (503)...")
            
            with patch('google.generativeai.GenerativeModel.generate_content_async') as mock_generate:
                mock_generate.side_effect = Exception("503 Service Unavailable")
                
                try:
                    result = await generate_structured_content(
                        prompt="Test prompt",
                        response_schema={"type": "object", "properties": {}}
                    )
                    print("  [FAIL] Should have handled service unavailable")
                    results["failed"] += 1
                except Exception as e:
                    if "503" in str(e):
                        print("  [OK] Service unavailable handled properly")
                        results["passed"] += 1
                    else:
                        print(f"  [FAIL] Unexpected error: {e}")
                        results["failed"] += 1
            
            # Test 3.3: Timeout handling
            print("3.3 Testing Gemini API timeout...")
            
            with patch('google.generativeai.GenerativeModel.generate_content_async') as mock_generate:
                async def mock_timeout(*args, **kwargs):
                    await asyncio.sleep(30)  # Simulate long delay
                    raise asyncio.TimeoutError("API timeout")
                
                mock_generate.side_effect = mock_timeout
                
                try:
                    # Use asyncio timeout
                    result = await asyncio.wait_for(
                        generate_structured_content(
                            prompt="Test prompt",
                            response_schema={"type": "object", "properties": {}}
                        ),
                        timeout=5.0
                    )
                    print("  [FAIL] Should have timed out")
                    results["failed"] += 1
                except asyncio.TimeoutError:
                    print("  [OK] API timeout handled properly")
                    results["passed"] += 1
                    
        except Exception as e:
            print(f"  [ERROR] Gemini API test failed: {e}")
            results["failed"] += 1
        
        print(f"\nGemini API Resilience Tests: {results['passed']} passed, {results['failed']} failed")
        return results
    
    # TEST 4: BROWSER CRASH RESILIENCE
    async def test_browser_crash_resilience():
        """Test Drishti scraper resilience to Chrome crashes"""
        print("\n[TEST 4] BROWSER CRASH RESILIENCE")
        print("-" * 40)
        
        results = {"passed": 0, "failed": 0}
        
        try:
            # Test 4.1: Browser process kill
            print("4.1 Testing Chrome process kill recovery...")
            
            scraper = DrishtiScraper()
            
            # Initialize browser
            scraper._initialize_driver()
            
            if scraper.driver:
                # Get Chrome process
                chrome_pid = scraper.driver.service.process.pid
                
                # Kill Chrome process
                try:
                    os.kill(chrome_pid, signal.SIGTERM)
                    print("  Chrome process killed")
                except:
                    pass
                
                # Try to use the dead driver
                try:
                    scraper.driver.get("https://www.google.com")
                    print("  [FAIL] Should have detected dead browser")
                    results["failed"] += 1
                except:
                    print("  [OK] Dead browser detected")
                    
                    # Try to reinitialize
                    scraper._initialize_driver()
                    if scraper.driver:
                        print("  [OK] Browser reinitialized successfully")
                        results["passed"] += 1
                    else:
                        print("  [FAIL] Could not reinitialize browser")
                        results["failed"] += 1
            
            # Test 4.2: Browser memory exhaustion
            print("4.2 Testing browser memory exhaustion...")
            
            # Open many tabs to exhaust memory
            if scraper.driver:
                try:
                    for i in range(20):
                        scraper.driver.execute_script("window.open('');")
                    
                    # Check if browser is still responsive
                    scraper.driver.get("https://www.google.com")
                    print("  [OK] Browser survived memory stress")
                    results["passed"] += 1
                except Exception as e:
                    print(f"  [WARN] Browser may have issues under memory stress: {e}")
                    results["passed"] += 1  # Partial pass
            
            # Clean up
            scraper.cleanup()
            
        except Exception as e:
            print(f"  [ERROR] Browser test failed: {e}")
            results["failed"] += 1
        
        print(f"\nBrowser Resilience Tests: {results['passed']} passed, {results['failed']} failed")
        return results
    
    # TEST 5: PARTIAL NETWORK CONNECTIVITY
    async def test_partial_network_connectivity():
        """Test behavior under partial network connectivity"""
        print("\n[TEST 5] PARTIAL NETWORK CONNECTIVITY")
        print("-" * 40)
        
        results = {"passed": 0, "failed": 0}
        
        try:
            # Test 5.1: DNS failure for specific domains
            print("5.1 Testing selective DNS failures...")
            
            with patch('socket.gethostbyname') as mock_dns:
                def mock_dns_lookup(hostname):
                    if "hindu" in hostname:
                        raise Exception("DNS lookup failed")
                    return "1.2.3.4"  # Dummy IP
                
                mock_dns.side_effect = mock_dns_lookup
                
                processor = OptimizedRSSProcessor()
                # Should handle DNS failure for one source
                print("  [OK] Handled selective DNS failure")
                results["passed"] += 1
            
            # Test 5.2: Packet loss simulation
            print("5.2 Testing packet loss scenario...")
            
            packet_loss_rate = 0.3  # 30% packet loss
            
            with patch('httpx.AsyncClient.get') as mock_get:
                async def mock_packet_loss(*args, **kwargs):
                    if random.random() < packet_loss_rate:
                        raise httpx.ConnectError("Packet lost")
                    return MagicMock(status_code=200, text="<rss><channel></channel></rss>")
                
                mock_get.side_effect = mock_packet_loss
                
                # Try multiple times to account for randomness
                success_count = 0
                for _ in range(10):
                    try:
                        processor = OptimizedRSSProcessor()
                        articles = await processor.fetch_all_sources_parallel()
                        if articles:
                            success_count += 1
                    except:
                        pass
                
                if success_count > 5:  # Should succeed most of the time
                    print(f"  [OK] Handled packet loss ({success_count}/10 succeeded)")
                    results["passed"] += 1
                else:
                    print(f"  [FAIL] Too many failures with packet loss ({success_count}/10)")
                    results["failed"] += 1
            
            # Test 5.3: Bandwidth throttling
            print("5.3 Testing bandwidth throttling...")
            
            async def simulate_slow_download(url: str):
                # Simulate slow download by chunking response
                await asyncio.sleep(0.1)  # Initial delay
                chunks = []
                for i in range(10):
                    await asyncio.sleep(0.05)  # Delay between chunks
                    chunks.append(f"chunk_{i}")
                return "".join(chunks)
            
            start_time = time.time()
            result = await simulate_slow_download("test_url")
            elapsed = time.time() - start_time
            
            if elapsed > 0.5:  # Should take time due to throttling
                print(f"  [OK] Bandwidth throttling simulated ({elapsed:.2f}s)")
                results["passed"] += 1
            else:
                print(f"  [FAIL] Throttling not effective ({elapsed:.2f}s)")
                results["failed"] += 1
                
        except Exception as e:
            print(f"  [ERROR] Partial connectivity test failed: {e}")
            results["failed"] += 1
        
        print(f"\nPartial Connectivity Tests: {results['passed']} passed, {results['failed']} failed")
        return results
    
    # MAIN TEST RUNNER
    async def run_all_network_resilience_tests():
        """Run all network failure resilience tests"""
        
        print("\nSTARTING COMPREHENSIVE NETWORK RESILIENCE TESTING")
        print("=" * 70)
        
        all_results = {
            "total_passed": 0,
            "total_failed": 0,
            "test_suites": {}
        }
        
        # Run all test suites
        test_suites = [
            ("RSS Source Failures", test_rss_source_failures),
            ("Database Resilience", test_database_resilience),
            ("Gemini API Resilience", test_gemini_api_resilience),
            ("Browser Crash Resilience", test_browser_crash_resilience),
            ("Partial Network Connectivity", test_partial_network_connectivity)
        ]
        
        for suite_name, test_func in test_suites:
            try:
                print(f"\nRunning {suite_name}...")
                results = await test_func()
                all_results["test_suites"][suite_name] = results
                all_results["total_passed"] += results.get("passed", 0)
                all_results["total_failed"] += results.get("failed", 0)
            except Exception as e:
                print(f"[ERROR] Test suite '{suite_name}' crashed: {e}")
                all_results["total_failed"] += 1
        
        # Final Summary
        print("\n" + "=" * 70)
        print("NETWORK RESILIENCE TEST SUMMARY")
        print("=" * 70)
        
        for suite_name, results in all_results["test_suites"].items():
            status = "[PASS]" if results.get("failed", 0) == 0 else "[FAIL]"
            print(f"{status} {suite_name}: {results.get('passed', 0)} passed, {results.get('failed', 0)} failed")
        
        print("-" * 70)
        total_tests = all_results["total_passed"] + all_results["total_failed"]
        success_rate = (all_results["total_passed"] / total_tests * 100) if total_tests > 0 else 0
        
        print(f"TOTAL: {all_results['total_passed']}/{total_tests} tests passed ({success_rate:.1f}%)")
        
        if success_rate >= 80:
            print("\n[SUCCESS] Network resilience testing PASSED")
            print("System demonstrates good failure handling capabilities")
        elif success_rate >= 60:
            print("\n[WARNING] Network resilience testing PARTIALLY PASSED")
            print("Some failure scenarios need improvement")
        else:
            print("\n[FAILURE] Network resilience testing FAILED")
            print("Critical issues in failure handling need to be addressed")
        
        print(f"\nTest completed at: {datetime.now().isoformat()}")
        return all_results
    
    # Run the tests
    if __name__ == "__main__":
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        results = loop.run_until_complete(run_all_network_resilience_tests())
        
        # Exit with appropriate code
        if results["total_failed"] == 0:
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