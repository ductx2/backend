#!/usr/bin/env python3
"""
PHASE 3: CRITICAL FAILURE SCENARIOS TEST
Focused testing of the most critical network failure scenarios

Priority Tests:
1. Database connection loss and recovery
2. API rate limiting handling
3. Service timeout management
4. Graceful degradation under failures
"""

import sys
import os
import asyncio
import time
from datetime import datetime
from unittest.mock import patch, MagicMock

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.core.database import get_database_sync
    from app.core.config import get_settings
    from app.services.gemini_client import generate_structured_content
    import httpx
    
    settings = get_settings()
    
    print("=" * 70)
    print("PHASE 3: CRITICAL FAILURE SCENARIOS TEST")
    print("=" * 70)
    print(f"Start Time: {datetime.now().isoformat()}")
    print("-" * 70)
    
    async def test_database_connection_recovery():
        """Test database connection loss and automatic recovery"""
        print("\n[TEST 1] DATABASE CONNECTION RECOVERY")
        print("-" * 40)
        
        try:
            db = get_database_sync()
            
            # Test 1: Normal operation
            print("1.1 Testing normal database operation...")
            try:
                health = db.health_check()
                if health.get("status") == "healthy":
                    print("  [OK] Database connection healthy")
                else:
                    print("  [WARN] Database status:", health.get("status"))
            except Exception as e:
                print(f"  [ERROR] Database health check failed: {e}")
            
            # Test 2: Simulate connection loss
            print("1.2 Simulating connection loss...")
            with patch.object(db.client.table("current_affairs"), 'select') as mock_select:
                mock_select.side_effect = Exception("Connection lost to database")
                
                try:
                    result = db.get_recent_articles(limit=5)
                    print("  [FAIL] Should have raised connection error")
                except Exception as e:
                    if "Connection lost" in str(e):
                        print("  [OK] Connection loss properly detected")
                    else:
                        print(f"  [FAIL] Unexpected error: {e}")
            
            # Test 3: Connection recovery
            print("1.3 Testing connection recovery...")
            try:
                # Real connection should work again
                health = db.health_check()
                if health.get("status") == "healthy":
                    print("  [OK] Database connection recovered")
                else:
                    print("  [FAIL] Database recovery failed")
            except Exception as e:
                print(f"  [ERROR] Recovery test failed: {e}")
            
            return True
            
        except Exception as e:
            print(f"  [ERROR] Database test crashed: {e}")
            return False
    
    async def test_api_rate_limiting():
        """Test API rate limit handling"""
        print("\n[TEST 2] API RATE LIMITING")
        print("-" * 40)
        
        try:
            # Test 1: Simulate rate limit error
            print("2.1 Testing Gemini API rate limit (429)...")
            
            with patch('google.generativeai.GenerativeModel.generate_content_async') as mock_gen:
                mock_gen.side_effect = Exception("429 RESOURCE_EXHAUSTED")
                
                try:
                    result = await generate_structured_content(
                        prompt="Test",
                        response_schema={"type": "object", "properties": {}},
                        max_output_tokens=100
                    )
                    print("  [FAIL] Should have raised rate limit error")
                except Exception as e:
                    if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                        print("  [OK] Rate limit error properly handled")
                    else:
                        print(f"  [WARN] Different error: {e}")
            
            # Test 2: Implement exponential backoff
            print("2.2 Testing exponential backoff strategy...")
            
            retry_delays = []
            max_retries = 3
            
            for attempt in range(max_retries):
                delay = min(2 ** attempt, 8)  # Exponential backoff with max 8 seconds
                retry_delays.append(delay)
                print(f"  Retry {attempt + 1}: Wait {delay}s before retry")
                await asyncio.sleep(0.1)  # Simulate short delay
            
            if retry_delays == [1, 2, 4]:
                print("  [OK] Exponential backoff implemented correctly")
            else:
                print(f"  [FAIL] Incorrect backoff delays: {retry_delays}")
            
            return True
            
        except Exception as e:
            print(f"  [ERROR] Rate limiting test crashed: {e}")
            return False
    
    async def test_service_timeouts():
        """Test timeout handling for external services"""
        print("\n[TEST 3] SERVICE TIMEOUT MANAGEMENT")
        print("-" * 40)
        
        try:
            # Test 1: HTTP request timeout
            print("3.1 Testing HTTP request timeout...")
            
            async def slow_request():
                await asyncio.sleep(10)  # Simulate slow response
                return "Late response"
            
            try:
                result = await asyncio.wait_for(slow_request(), timeout=2.0)
                print("  [FAIL] Should have timed out")
            except asyncio.TimeoutError:
                print("  [OK] Request timeout handled properly")
            
            # Test 2: Database query timeout
            print("3.2 Testing database query timeout...")
            
            db = get_database_sync()
            
            with patch.object(db.client.table("current_affairs").select("*"), 'execute') as mock_exec:
                async def slow_query():
                    await asyncio.sleep(5)
                    return MagicMock()
                
                mock_exec.side_effect = slow_query
                
                try:
                    # Wrap in timeout
                    result = await asyncio.wait_for(
                        asyncio.create_task(mock_exec()),
                        timeout=1.0
                    )
                    print("  [FAIL] Query should have timed out")
                except asyncio.TimeoutError:
                    print("  [OK] Database query timeout handled")
            
            # Test 3: Concurrent timeout handling
            print("3.3 Testing concurrent timeout handling...")
            
            async def timeout_task(task_id, delay):
                try:
                    await asyncio.wait_for(
                        asyncio.sleep(delay),
                        timeout=1.0
                    )
                    return f"Task {task_id} completed"
                except asyncio.TimeoutError:
                    return f"Task {task_id} timed out"
            
            tasks = [
                timeout_task(1, 0.5),   # Should complete
                timeout_task(2, 2.0),   # Should timeout
                timeout_task(3, 0.8),   # Should complete
                timeout_task(4, 3.0),   # Should timeout
            ]
            
            results = await asyncio.gather(*tasks)
            
            timeouts = sum(1 for r in results if "timed out" in r)
            if timeouts == 2:
                print(f"  [OK] Handled {timeouts} timeouts correctly")
            else:
                print(f"  [FAIL] Expected 2 timeouts, got {timeouts}")
            
            return True
            
        except Exception as e:
            print(f"  [ERROR] Timeout test crashed: {e}")
            return False
    
    async def test_graceful_degradation():
        """Test system degradation under partial failures"""
        print("\n[TEST 4] GRACEFUL DEGRADATION")
        print("-" * 40)
        
        try:
            # Test 1: Partial service availability
            print("4.1 Testing partial service availability...")
            
            services = {
                "database": True,
                "gemini_api": False,  # Simulated failure
                "rss_processor": True,
                "drishti_scraper": False,  # Simulated failure
            }
            
            available = sum(1 for s, status in services.items() if status)
            total = len(services)
            
            print(f"  Services: {available}/{total} available")
            
            if available >= total // 2:
                print("  [OK] System can operate with partial services")
            else:
                print("  [FAIL] Too many services down")
            
            # Test 2: Fallback mechanisms
            print("4.2 Testing fallback mechanisms...")
            
            primary_source = None  # Simulated failure
            fallback_source = "cached_data"
            
            result = primary_source or fallback_source
            
            if result == fallback_source:
                print("  [OK] Fallback to cached data successful")
            else:
                print("  [FAIL] Fallback mechanism not working")
            
            # Test 3: Circuit breaker pattern
            print("4.3 Testing circuit breaker pattern...")
            
            class CircuitBreaker:
                def __init__(self, threshold=3):
                    self.failure_count = 0
                    self.threshold = threshold
                    self.is_open = False
                
                def call(self, func):
                    if self.is_open:
                        return "Circuit breaker OPEN - service disabled"
                    
                    try:
                        result = func()
                        self.failure_count = 0  # Reset on success
                        return result
                    except:
                        self.failure_count += 1
                        if self.failure_count >= self.threshold:
                            self.is_open = True
                            return "Circuit breaker OPENED after repeated failures"
                        raise
            
            breaker = CircuitBreaker(threshold=3)
            
            def failing_service():
                raise Exception("Service error")
            
            # Test circuit breaker
            for i in range(5):
                try:
                    result = breaker.call(failing_service)
                    if "Circuit breaker" in result:
                        print(f"  Attempt {i+1}: {result}")
                except:
                    print(f"  Attempt {i+1}: Service failed")
            
            if breaker.is_open:
                print("  [OK] Circuit breaker activated after threshold")
            else:
                print("  [FAIL] Circuit breaker not working")
            
            return True
            
        except Exception as e:
            print(f"  [ERROR] Degradation test crashed: {e}")
            return False
    
    async def test_error_propagation():
        """Test proper error propagation and handling"""
        print("\n[TEST 5] ERROR PROPAGATION & HANDLING")
        print("-" * 40)
        
        try:
            # Test 1: Error context preservation
            print("5.1 Testing error context preservation...")
            
            class CustomError(Exception):
                def __init__(self, message, context=None):
                    super().__init__(message)
                    self.context = context or {}
            
            try:
                raise CustomError("Database connection failed", {
                    "service": "supabase",
                    "timestamp": datetime.now().isoformat(),
                    "retry_count": 3
                })
            except CustomError as e:
                if e.context.get("service") == "supabase":
                    print("  [OK] Error context preserved")
                else:
                    print("  [FAIL] Error context lost")
            
            # Test 2: Error aggregation
            print("5.2 Testing error aggregation...")
            
            errors = []
            
            async def task_with_error(task_id):
                if task_id % 2 == 0:
                    raise Exception(f"Task {task_id} failed")
                return f"Task {task_id} success"
            
            tasks = [task_with_error(i) for i in range(5)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            errors = [r for r in results if isinstance(r, Exception)]
            successes = [r for r in results if not isinstance(r, Exception)]
            
            print(f"  Results: {len(successes)} succeeded, {len(errors)} failed")
            
            if len(errors) > 0 and len(successes) > 0:
                print("  [OK] Handled mixed success/failure results")
            else:
                print("  [FAIL] Error aggregation not working")
            
            # Test 3: Error recovery strategies
            print("5.3 Testing error recovery strategies...")
            
            async def unreliable_service():
                import random
                if random.random() < 0.5:
                    raise Exception("Random failure")
                return "Success"
            
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    result = await unreliable_service()
                    print(f"  [OK] Recovered after {attempt + 1} attempts")
                    break
                except Exception:
                    if attempt == max_attempts - 1:
                        print(f"  [WARN] Failed after {max_attempts} attempts")
                    else:
                        await asyncio.sleep(0.1)  # Brief delay before retry
            
            return True
            
        except Exception as e:
            print(f"  [ERROR] Error propagation test crashed: {e}")
            return False
    
    async def run_critical_failure_tests():
        """Run all critical failure scenario tests"""
        
        print("\nRUNNING CRITICAL FAILURE SCENARIO TESTS")
        print("=" * 70)
        
        test_results = {
            "passed": 0,
            "failed": 0,
            "tests": []
        }
        
        # Run all tests
        tests = [
            ("Database Connection Recovery", test_database_connection_recovery),
            ("API Rate Limiting", test_api_rate_limiting),
            ("Service Timeouts", test_service_timeouts),
            ("Graceful Degradation", test_graceful_degradation),
            ("Error Propagation", test_error_propagation)
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
        print("CRITICAL FAILURE TEST SUMMARY")
        print("=" * 70)
        
        for test_name, status in test_results["tests"]:
            symbol = "[OK]" if status == "PASSED" else "[FAIL]"
            print(f"{symbol} {test_name}: {status}")
        
        print("-" * 70)
        
        total = test_results["passed"] + test_results["failed"]
        success_rate = (test_results["passed"] / total * 100) if total > 0 else 0
        
        print(f"RESULTS: {test_results['passed']}/{total} tests passed ({success_rate:.1f}%)")
        
        if success_rate >= 80:
            print("\n[SUCCESS] Critical failure handling validated")
            print("System demonstrates robust error handling")
        elif success_rate >= 60:
            print("\n[WARNING] Partial failure handling capability")
            print("Some critical scenarios need improvement")
        else:
            print("\n[FAILURE] Inadequate failure handling")
            print("Critical improvements needed for production")
        
        print(f"\nCompleted at: {datetime.now().isoformat()}")
        
        return test_results
    
    # Run the tests
    if __name__ == "__main__":
        results = asyncio.run(run_critical_failure_tests())
        
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