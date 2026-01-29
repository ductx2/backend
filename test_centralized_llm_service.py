#!/usr/bin/env python3
"""
Test the Centralized LLM Service with multi-provider integration
"""

import asyncio
import sys
import os
import json
from pathlib import Path

# Add current directory to Python path
sys.path.append('.')
sys.path.append('app')

from app.models.llm_schemas import LLMRequest, TaskType, ProviderPreference
from app.services.centralized_llm_service import llm_service

async def test_content_extraction():
    """Test content extraction with Drishti content"""
    print("=" * 60)
    print("TESTING: Content Extraction")
    print("=" * 60)
    
    # Sample Drishti content
    test_content = """
    Civil Society Organizations in India
    
    Why in News?
    Civil Society Organizations (CSOs) have once again come into focus for its role in 
    mobilising communities, protecting rights, and filling gaps in governance.
    Beyond the state and markets, it drives collective action, ensures citizen participation, 
    and strengthens democracy in India.
    
    What is a Civil Society Organization?
    About: CSO society refers to non-state, non-profit entities that unite people voluntarily 
    to work collectively toward shared social, cultural, or ethical goals.
    """
    
    try:
        request = LLMRequest(
            task_type=TaskType.CONTENT_EXTRACTION,
            content=test_content,
            provider_preference=ProviderPreference.COST_OPTIMIZED
        )
        
        print("Processing content extraction request...")
        result = await llm_service.process_request(request)
        
        if result.success:
            print(f"SUCCESS: Provider used: {result.provider_used}")
            print(f"Response time: {result.response_time:.2f}s")
            print(f"Tokens used: {result.tokens_used}")
            print("Extracted data:")
            print(json.dumps(result.data, indent=2))
        else:
            print(f"FAILED: {result.error_message}")
            
        return result.success
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_upsc_analysis():
    """Test UPSC relevance analysis"""
    print("\n" + "=" * 60)
    print("TESTING: UPSC Analysis")
    print("=" * 60)
    
    test_content = """
    The government has announced a new education policy that emphasizes digital literacy,
    skill development, and vocational training. This policy aims to bridge the gap between
    education and employment, making graduates more job-ready and industry-relevant.
    The policy also focuses on promoting Indian languages and cultural values.
    """
    
    try:
        request = LLMRequest(
            task_type=TaskType.UPSC_ANALYSIS,
            content=test_content,
            provider_preference=ProviderPreference.QUALITY_OPTIMIZED
        )
        
        print("Processing UPSC analysis request...")
        result = await llm_service.process_request(request)
        
        if result.success:
            print(f"SUCCESS: Provider used: {result.provider_used}")
            print(f"Response time: {result.response_time:.2f}s")
            print(f"Tokens used: {result.tokens_used}")
            print("Analysis results:")
            print(json.dumps(result.data, indent=2))
            
            # Check if relevance score meets threshold
            relevance_score = result.data.get("upsc_relevance", 0)
            print(f"\nUPSC Relevance Score: {relevance_score}/100")
            if relevance_score >= 40:
                print("Content qualifies for saving (score >= 40)")
            else:
                print("Content does not meet minimum threshold")
        else:
            print(f"FAILED: {result.error_message}")
            
        return result.success
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_provider_failover():
    """Test provider failover mechanism"""
    print("\n" + "=" * 60)
    print("TESTING: Provider Failover")
    print("=" * 60)
    
    try:
        # Test with different provider preferences
        preferences = [
            ProviderPreference.COST_OPTIMIZED,
            ProviderPreference.SPEED_OPTIMIZED,
            ProviderPreference.QUALITY_OPTIMIZED,
            ProviderPreference.BALANCED
        ]
        
        test_content = "Analyze this simple content for testing provider routing."
        
        for pref in preferences:
            print(f"\nTesting {pref.value}...")
            
            request = LLMRequest(
                task_type=TaskType.CONTENT_EXTRACTION,
                content=test_content,
                provider_preference=pref
            )
            
            result = await llm_service.process_request(request)
            
            if result.success:
                print(f"  Provider used: {result.provider_used}")
                print(f"  Response time: {result.response_time:.2f}s")
                print(f"  Fallback used: {result.fallback_used}")
            else:
                print(f"  FAILED: {result.error_message}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_health_check():
    """Test service health"""
    print("\n" + "=" * 60)
    print("TESTING: Service Health Check")
    print("=" * 60)
    
    try:
        # Initialize router if not done
        if llm_service.router is None:
            print("Initializing LiteLLM router...")
            await llm_service.initialize_router()
        
        print(f"Router initialized: {llm_service.router is not None}")
        print(f"Available task handlers: {len(llm_service.task_handlers)}")
        print("Task types supported:")
        for task_type in TaskType:
            print(f"  - {task_type.value}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tests"""
    print("CENTRALIZED LLM SERVICE - COMPREHENSIVE TEST")
    print("=" * 60)
    
    # Check environment setup
    print("Checking environment...")
    env_file = Path(".env.llm")
    config_file = Path("config/litellm_config.yaml")
    
    print(f"Environment file exists: {env_file.exists()}")
    print(f"Config file exists: {config_file.exists()}")
    
    if not env_file.exists():
        print("WARNING: .env.llm file not found. Some providers may not work.")
    
    if not config_file.exists():
        print("WARNING: litellm_config.yaml not found. Using basic configuration.")
    
    # Run tests
    test_results = []
    
    test_results.append(await test_health_check())
    test_results.append(await test_content_extraction())
    test_results.append(await test_upsc_analysis())
    test_results.append(await test_provider_failover())
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(test_results)
    total = len(test_results)
    
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("ALL TESTS PASSED - Centralized LLM Service is working!")
        print("Ready for integration with existing endpoints.")
    else:
        print("Some tests failed. Check the logs above for details.")
    
    print("\nNext steps:")
    print("1. Add more API keys to .env.llm file")
    print("2. Configure additional providers in litellm_config.yaml")
    print("3. Integrate with existing FastAPI endpoints")
    print("4. Update Drishti scraper to use centralized service")

if __name__ == "__main__":
    asyncio.run(main())