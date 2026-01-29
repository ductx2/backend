#!/usr/bin/env python3
"""
Simple test script for unified content API endpoints
Testing endpoints to verify structured response migration works
"""

import asyncio
import sys
import os
import requests
import json
from datetime import datetime

def test_endpoint(url, method="GET", payload=None):
    """Test a single endpoint synchronously"""
    print(f"\nTesting {method} {url}")
    
    try:
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer upsc_backend_secure_key_2025_development"
        }
        
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            response = requests.post(url, json=payload, headers=headers, timeout=60)
        
        status = response.status_code
        
        try:
            data = response.json()
            print(f"Status: {status}")
            print(f"Response: {json.dumps(data, indent=2)[:300]}...")
            
            return {
                "status": status,
                "success": status < 400,
                "data": data,
                "error": None
            }
            
        except json.JSONDecodeError:
            print(f"Status: {status}")
            print(f"Raw response: {response.text[:200]}...")
            return {
                "status": status, 
                "success": False,
                "data": None,
                "error": f"JSON decode error"
            }
            
    except Exception as e:
        print(f"Request failed: {e}")
        return {
            "status": 0,
            "success": False, 
            "data": None,
            "error": str(e)
        }

def main():
    """Test unified content API endpoints"""
    print("Testing Unified Content API Endpoints")
    print("=" * 60)
    
    # Base URL
    base_url = "http://localhost:8000"
    
    # Simple test cases
    test_cases = [
        {
            "method": "GET",
            "path": "/api/unified/status", 
            "description": "System status"
        },
        {
            "method": "GET", 
            "path": "/api/unified/performance/metrics",
            "description": "Performance metrics"
        },
        {
            "method": "POST",
            "path": "/api/unified/process-rss-only",
            "payload": {"articles_limit": 2},
            "description": "RSS processing"
        }
    ]
    
    results = {}
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTEST {i}: {test_case['description']}")
        print("-" * 40)
        
        url = f"{base_url}{test_case['path']}"
        method = test_case['method']
        payload = test_case.get('payload')
        
        result = test_endpoint(url, method, payload)
        results[test_case['path']] = result
    
    # Summary
    print(f"\n{'='*60}")
    print("TEST SUMMARY")
    print(f"{'='*60}")
    
    successful_tests = 0
    total_tests = len(results)
    
    for path, result in results.items():
        status_icon = "OK" if result['success'] else "FAIL"
        print(f"{status_icon}: {path} (HTTP {result['status']})")
        
        if result['success']:
            successful_tests += 1
            # Check for structured response
            if result['data'] and 'success' in result['data']:
                print(f"  -> Structured response: {result['data']['success']}")
        else:
            print(f"  -> Error: {result['error']}")
    
    success_rate = (successful_tests / total_tests) * 100
    print(f"\nSuccess Rate: {successful_tests}/{total_tests} ({success_rate:.1f}%)")
    
    return success_rate >= 50

if __name__ == "__main__":
    try:
        result = main()
        if result:
            print("\nMigration appears successful!")
        else:
            print("\nSome endpoints need attention")
    except Exception as e:
        print(f"\nTest failed: {e}")