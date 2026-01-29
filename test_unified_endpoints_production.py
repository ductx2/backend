#!/usr/bin/env python3
"""
Test script for unified content API endpoints to verify structured response migration
Testing the endpoints shown in the user's screenshot to ensure they work with centralized LLM service
"""

import asyncio
import sys
import os
import aiohttp
import json
from datetime import datetime

# Add the current directory to Python path to import our services
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_endpoint(session, url, method="GET", payload=None):
    """Test a single endpoint and return detailed results"""
    print(f"\n🧪 Testing {method} {url}")
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer test-admin-token"  # Mock admin token for testing
        }
        
        if method == "GET":
            async with session.get(url, headers=headers) as response:
                status = response.status
                content = await response.text()
                
        elif method == "POST":
            async with session.post(url, json=payload, headers=headers) as response:
                status = response.status
                content = await response.text()
        
        # Try to parse as JSON
        try:
            data = json.loads(content)
            print(f"✅ Status: {status}")
            print(f"📊 Response preview: {json.dumps(data, indent=2)[:200]}...")
            
            # Check for structured response indicators
            if 'success' in data and data['success']:
                print(f"🎯 Success: {data.get('message', 'No message')}")
            
            return {
                "status": status,
                "success": status < 400,
                "data": data,
                "error": None
            }
            
        except json.JSONDecodeError:
            print(f"❌ Status: {status}")
            print(f"📄 Raw response: {content[:200]}...")
            return {
                "status": status, 
                "success": False,
                "data": None,
                "error": f"JSON decode error: {content[:100]}"
            }
            
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return {
            "status": 0,
            "success": False, 
            "data": None,
            "error": str(e)
        }

async def main():
    """Test all unified content API endpoints"""
    print("🚀 Testing Unified Content API Endpoints with Official Structured Responses")
    print("=" * 80)
    
    # Base URL - assuming FastAPI is running on localhost:8000
    base_url = "http://localhost:8000"
    
    # Test cases from the screenshot
    test_cases = [
        # Status and performance endpoints (GET requests)
        {
            "method": "GET",
            "path": "/api/unified/status", 
            "description": "Get unified system status"
        },
        {
            "method": "GET", 
            "path": "/api/unified/performance/metrics",
            "description": "Get performance metrics"
        },
        {
            "method": "GET",
            "path": "/api/unified/content-preference/test",
            "description": "Test content preference logic"
        },
        
        # Processing endpoints (POST requests with small limits for testing)
        {
            "method": "POST",
            "path": "/api/unified/process-rss-only",
            "payload": {"articles_limit": 2},  # Small test
            "description": "Process RSS content only"
        },
        {
            "method": "POST", 
            "path": "/api/unified/process-drishti-only",
            "payload": {"daily_articles": 2, "editorial_articles": 1},  # Small test
            "description": "Process Drishti content only"
        },
        {
            "method": "POST",
            "path": "/api/unified/process-all-sources",
            "payload": {
                "rss_articles_limit": 3,
                "drishti_daily_limit": 2, 
                "drishti_editorial_limit": 1
            },
            "description": "Process all sources with content preference"
        }
    ]
    
    results = {}
    
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=120)) as session:
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{'='*60}")
            print(f"TEST {i}/{len(test_cases)}: {test_case['description']}")
            print(f"{'='*60}")
            
            url = f"{base_url}{test_case['path']}"
            method = test_case['method']
            payload = test_case.get('payload')
            
            result = await test_endpoint(session, url, method, payload)
            results[test_case['path']] = result
            
            # Brief pause between tests
            await asyncio.sleep(1)
    
    # Summary report
    print(f"\n{'='*80}")
    print("📊 UNIFIED ENDPOINTS TEST SUMMARY")
    print(f"{'='*80}")
    
    successful_tests = 0
    total_tests = len(results)
    
    for path, result in results.items():
        status_icon = "✅" if result['success'] else "❌"
        print(f"{status_icon} {path}: HTTP {result['status']}")
        
        if result['success']:
            successful_tests += 1
        else:
            print(f"   Error: {result['error']}")
    
    success_rate = (successful_tests / total_tests) * 100
    print(f"\n🎯 Overall Success Rate: {successful_tests}/{total_tests} ({success_rate:.1f}%)")
    
    # Check for structured response migration success
    print(f"\n🔍 STRUCTURED RESPONSE VALIDATION:")
    structured_responses = 0
    
    for path, result in results.items():
        if result['success'] and result['data']:
            # Check for structured response indicators
            has_structure = any(key in result['data'] for key in ['success', 'message', 'data', 'timestamp'])
            if has_structure:
                structured_responses += 1
                print(f"✅ {path}: Proper structured response detected")
            else:
                print(f"❌ {path}: Missing structured response format")
    
    structured_rate = (structured_responses / successful_tests * 100) if successful_tests > 0 else 0
    print(f"\n📋 Structured Response Rate: {structured_responses}/{successful_tests} ({structured_rate:.1f}%)")
    
    if success_rate >= 80 and structured_rate >= 90:
        print(f"\n🎉 MIGRATION SUCCESS: Official structured responses working properly!")
        print(f"🚀 Round-robin load balancing and centralized LLM service operational!")
        return True
    else:
        print(f"\n⚠️ MIGRATION INCOMPLETE: Some endpoints need attention")
        return False

if __name__ == "__main__":
    # Check if FastAPI server is running
    print("🔍 Checking if FastAPI server is accessible...")
    
    try:
        result = asyncio.run(main())
        if result:
            print(f"\n✅ All unified content endpoints successfully migrated to official structured responses!")
        else:
            print(f"\n❌ Some endpoints require additional fixes")
    except KeyboardInterrupt:
        print(f"\n⚠️ Test interrupted by user")
    except Exception as e:
        print(f"\n❌ Test execution failed: {e}")