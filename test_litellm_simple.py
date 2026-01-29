#!/usr/bin/env python3
"""
Simple LiteLLM Testing Script
Tests basic functionality without Unicode characters

Created: 2025-08-31
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

async def test_basic_functionality():
    """Test basic LiteLLM functionality"""
    print("=" * 50)
    print("TESTING: Basic LiteLLM Functionality")
    print("=" * 50)
    
    try:
        print("Step 1: Initializing LiteLLM router...")
        await llm_service.initialize_router()
        
        if llm_service.router is None:
            print("FAILED: Router not initialized")
            return False
            
        print("SUCCESS: Router initialized")
        
        print("\nStep 2: Testing simple UPSC analysis request...")
        
        request = LLMRequest(
            task_type=TaskType.UPSC_ANALYSIS,
            content="Prime Minister announces new education policy with focus on digital literacy.",
            provider_preference=ProviderPreference.COST_OPTIMIZED,
            temperature=0.1,
            max_tokens=400
        )
        
        start_time = time.time()
        response = await llm_service.process_request(request)
        end_time = time.time()
        
        if response.success:
            print(f"SUCCESS: Request completed in {end_time - start_time:.2f}s")
            print(f"Model used: {response.model_used}")
            print(f"Provider: {response.provider_used}")
            print(f"Tokens: {response.tokens_used}")
            
            if response.data:
                if "upsc_relevance" in response.data:
                    relevance = response.data["upsc_relevance"]
                    print(f"UPSC Relevance Score: {relevance}")
                    
                print("Response data keys:", list(response.data.keys()))
                
            return True
        else:
            print(f"FAILED: {response.error_message}")
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_multiple_requests():
    """Test multiple requests to check round-robin"""
    print("\n" + "=" * 50)
    print("TESTING: Multiple Requests (Round-Robin)")
    print("=" * 50)
    
    test_content = "India launches new space mission to lunar south pole."
    
    for i in range(3):
        try:
            print(f"\nRequest {i+1}/3...")
            
            request = LLMRequest(
                task_type=TaskType.UPSC_ANALYSIS,
                content=f"{test_content} Test iteration {i+1}.",
                provider_preference=ProviderPreference.BALANCED,
                temperature=0.1,
                max_tokens=300
            )
            
            response = await llm_service.process_request(request)
            
            if response.success:
                print(f"  SUCCESS: {response.model_used}")
            else:
                print(f"  FAILED: {response.error_message}")
                
        except Exception as e:
            print(f"  ERROR: {e}")
    
    return True

async def test_environment_check():
    """Check environment variables"""
    print("\n" + "=" * 50)
    print("TESTING: Environment Variables")
    print("=" * 50)
    
    key_vars = [
        "OPENROUTER_API_KEY_1",
        "GROQ_API_KEY_1", 
        "DEEPSEEK_API_KEY_1",
        "GEMINI_API_KEY_1"
    ]
    
    configured = 0
    
    for var in key_vars:
        value = os.environ.get(var)
        if value:
            configured += 1
            print(f"  OK: {var} is configured")
        else:
            print(f"  MISSING: {var}")
    
    print(f"\nConfigured: {configured}/{len(key_vars)}")
    return configured > 0

async def main():
    """Main test function"""
    print("Starting LiteLLM Tests")
    print("=" * 50)
    
    # Test 1: Basic functionality
    test1_result = await test_basic_functionality()
    
    # Test 2: Multiple requests
    test2_result = await test_multiple_requests()
    
    # Test 3: Environment check
    test3_result = await test_environment_check()
    
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    
    print(f"Basic Functionality: {'PASS' if test1_result else 'FAIL'}")
    print(f"Multiple Requests: {'PASS' if test2_result else 'FAIL'}")
    print(f"Environment Check: {'PASS' if test3_result else 'FAIL'}")
    
    overall_success = test1_result and test3_result
    print(f"\nOVERALL: {'SUCCESS' if overall_success else 'NEEDS WORK'}")
    
    return overall_success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)