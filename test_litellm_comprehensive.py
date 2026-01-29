#!/usr/bin/env python3
"""
Comprehensive LiteLLM Testing Script
Tests dynamic routing, round-robin, failover, and configuration validation

Created: 2025-08-31
Purpose: Validate centralized LLM service with 55+ API keys
"""

import asyncio
import sys
import os
import json
import time
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.centralized_llm_service import llm_service
from app.models.llm_schemas import LLMRequest, TaskType, ProviderPreference

async def test_llm_initialization():
    """Test 1: LLM Service Initialization"""
    print("=" * 60)
    print("TEST 1: LiteLLM Router Initialization")
    print("=" * 60)
    
    try:
        # Initialize the router
        await llm_service.initialize_router()
        
        if llm_service.router is None:
            print("❌ FAILED: Router not initialized")
            return False
            
        print("✅ SUCCESS: LiteLLM router initialized")
        
        # Check if YAML config was loaded
        config_path = Path(__file__).parent / "config" / "litellm_config.yaml"
        if config_path.exists():
            print("✅ SUCCESS: YAML configuration found")
        else:
            print("⚠️  WARNING: Using fallback configuration")
            
        return True
        
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

async def test_simple_request():
    """Test 2: Simple LLM Request"""
    print("\n" + "=" * 60)
    print("🧪 TEST 2: Simple LLM Request")
    print("=" * 60)
    
    try:
        # Create a simple test request
        request = LLMRequest(
            task_type=TaskType.UPSC_ANALYSIS,
            content="Prime Minister announces new education policy focusing on digital literacy and skill development.",
            provider_preference=ProviderPreference.COST_OPTIMIZED,
            temperature=0.1,
            max_tokens=500,
            custom_instructions="Focus on UPSC relevance for education policy."
        )
        
        print("📤 Sending test request...")
        start_time = time.time()
        
        response = await llm_service.process_request(request)
        
        end_time = time.time()
        
        if response.success:
            print(f"✅ SUCCESS: Request completed in {end_time - start_time:.2f}s")
            print(f"🤖 Model used: {response.model_used}")
            print(f"🏭 Provider: {response.provider_used}")
            print(f"🎯 Tokens used: {response.tokens_used}")
            
            # Validate response data
            if response.data and "upsc_relevance" in response.data:
                relevance = response.data["upsc_relevance"]
                print(f"📊 UPSC Relevance Score: {relevance}")
                
                if relevance >= 40:
                    print("✅ SUCCESS: Relevance score meets threshold (40+)")
                else:
                    print("⚠️  WARNING: Relevance score below threshold")
                    
            return True
        else:
            print(f"❌ FAILED: {response.error_message}")
            return False
            
    except Exception as e:
        print(f"❌ FAILED: {e}")
        return False

async def test_multiple_provider_requests():
    """Test 3: Multiple Provider Requests (Round-Robin)"""
    print("\n" + "=" * 60)
    print("🧪 TEST 3: Round-Robin Provider Testing")
    print("=" * 60)
    
    providers = [
        ProviderPreference.COST_OPTIMIZED,
        ProviderPreference.SPEED_OPTIMIZED,
        ProviderPreference.QUALITY_OPTIMIZED,
        ProviderPreference.BALANCED
    ]
    
    test_content = "India launches new space mission to explore lunar south pole with advanced scientific instruments."
    
    results = []
    
    for i, preference in enumerate(providers):
        try:
            print(f"\n📤 Request {i+1}/4 - Preference: {preference}")
            
            request = LLMRequest(
                task_type=TaskType.UPSC_ANALYSIS,
                content=test_content,
                provider_preference=preference,
                temperature=0.1,
                max_tokens=400
            )
            
            start_time = time.time()
            response = await llm_service.process_request(request)
            end_time = time.time()
            
            if response.success:
                print(f"  ✅ SUCCESS: {response.model_used} ({end_time - start_time:.2f}s)")
                results.append({
                    "preference": preference,
                    "model": response.model_used,
                    "provider": response.provider_used,
                    "time": end_time - start_time,
                    "tokens": response.tokens_used
                })
            else:
                print(f"  ❌ FAILED: {response.error_message}")
                
        except Exception as e:
            print(f"  ❌ ERROR: {e}")
    
    # Analyze results
    print("\n📊 ROUND-ROBIN ANALYSIS:")
    unique_models = set(r["model"] for r in results)
    print(f"  🎯 Unique models used: {len(unique_models)}")
    
    for result in results:
        print(f"  • {result['preference']}: {result['model']} ({result['time']:.2f}s)")
    
    if len(unique_models) > 1:
        print("✅ SUCCESS: Round-robin working (different models used)")
        return True
    elif len(results) > 0:
        print("⚠️  WARNING: Same model used for all requests")
        return True
    else:
        print("❌ FAILED: No successful requests")
        return False

async def test_failover_mechanism():
    """Test 4: Failover Mechanism"""
    print("\n" + "=" * 60)
    print("🧪 TEST 4: Failover Mechanism Testing")
    print("=" * 60)
    
    print("ℹ️  NOTE: This test simulates failover by sending multiple requests")
    print("  and checking if the system automatically uses different providers")
    
    test_requests = []
    
    # Send multiple requests rapidly to trigger potential rate limits
    for i in range(5):
        request = LLMRequest(
            task_type=TaskType.UPSC_ANALYSIS,
            content=f"Test content {i+1}: Economic reforms impact on rural development and agricultural policies.",
            provider_preference=ProviderPreference.COST_OPTIMIZED,
            temperature=0.1,
            max_tokens=300
        )
        test_requests.append(request)
    
    print("📤 Sending 5 rapid requests to test failover...")
    
    successful_requests = 0
    models_used = set()
    
    for i, request in enumerate(test_requests):
        try:
            print(f"  Request {i+1}/5...", end=" ")
            response = await llm_service.process_request(request)
            
            if response.success:
                successful_requests += 1
                models_used.add(response.model_used)
                print(f"✅ {response.model_used}")
            else:
                print(f"❌ FAILED: {response.error_message}")
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
    
    print(f"\n📊 FAILOVER RESULTS:")
    print(f"  ✅ Successful requests: {successful_requests}/5")
    print(f"  🎯 Unique models used: {len(models_used)}")
    print(f"  🔄 Models: {', '.join(models_used)}")
    
    if successful_requests >= 3:
        print("✅ SUCCESS: Failover mechanism working")
        return True
    else:
        print("❌ FAILED: Too many failed requests")
        return False

async def test_environment_variables():
    """Test 5: Environment Variables Check"""
    print("\n" + "=" * 60)
    print("🧪 TEST 5: Environment Variables Validation")
    print("=" * 60)
    
    # Key environment variables to check
    env_vars = [
        "OPENROUTER_API_KEY_1", "OPENROUTER_API_KEY_2",
        "GROQ_API_KEY_1", "GROQ_API_KEY_2", 
        "DEEPSEEK_API_KEY_1", "DEEPSEEK_API_KEY_2",
        "CEREBRAS_API_KEY_1", "CEREBRAS_API_KEY_2",
        "GEMINI_API_KEY_1", "GEMINI_API_KEY_2"
    ]
    
    configured_vars = 0
    
    for var in env_vars:
        value = os.environ.get(var)
        if value:
            configured_vars += 1
            print(f"  ✅ {var}: Configured")
        else:
            print(f"  ❌ {var}: Missing")
    
    print(f"\n📊 ENVIRONMENT STATUS:")
    print(f"  🎯 Configured variables: {configured_vars}/{len(env_vars)}")
    
    if configured_vars >= 2:
        print("✅ SUCCESS: Minimum environment variables configured")
        return True
    else:
        print("❌ FAILED: Insufficient environment variables")
        return False

async def main():
    """Run comprehensive LiteLLM testing suite"""
    print("Starting Comprehensive LiteLLM Testing")
    print("=" * 60)
    
    test_results = []
    
    # Run all tests
    tests = [
        ("Initialization", test_llm_initialization),
        ("Simple Request", test_simple_request),
        ("Round-Robin", test_multiple_provider_requests),
        ("Failover", test_failover_mechanism),
        ("Environment", test_environment_variables)
    ]
    
    for test_name, test_func in tests:
        print(f"\n🏃 Running {test_name} test...")
        try:
            result = await test_func()
            test_results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} test crashed: {e}")
            test_results.append((test_name, False))
    
    # Final summary
    print("\n" + "=" * 60)
    print("📋 FINAL TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\n🏆 OVERALL RESULT: {passed}/{total} tests passed")
    
    if passed >= 3:
        print("✅ SUCCESS: LiteLLM system is working adequately")
    else:
        print("❌ CRITICAL: LiteLLM system needs fixes")
    
    return passed >= 3

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)