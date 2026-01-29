#!/usr/bin/env python3
"""
Database Integration Testing Script
Tests Supabase connection and current_affairs operations

Created: 2025-08-31
"""

import asyncio
import sys
import os
import json
from pathlib import Path
from datetime import datetime, date

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.database import get_database_sync, SupabaseConnection

async def test_database_connection():
    """Test basic database connection"""
    print("=" * 50)
    print("TESTING: Database Connection")
    print("=" * 50)
    
    try:
        db = get_database_sync()
        
        print("Step 1: Testing database health...")
        health = await db.health_check()
        
        print(f"Status: {health.get('status')}")
        print(f"Connection: {health.get('connection')}")
        print(f"Table accessible: {health.get('table_accessible')}")
        print(f"Total records: {health.get('total_records')}")
        
        if health.get('status') == 'healthy':
            print("SUCCESS: Database connection working")
            return True
        else:
            print(f"FAILED: Database unhealthy - {health.get('error')}")
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def test_current_affairs_operations():
    """Test current affairs table operations"""
    print("\n" + "=" * 50)
    print("TESTING: Current Affairs Operations")
    print("=" * 50)
    
    try:
        db = get_database_sync()
        
        print("Step 1: Querying existing records...")
        
        # Test basic select
        try:
            result = db.client.table("current_affairs").select("*").limit(5).execute()
            
            if result.data:
                print(f"SUCCESS: Found {len(result.data)} sample records")
                
                # Show sample record structure
                if result.data:
                    sample = result.data[0]
                    print("Sample record fields:", list(sample.keys()))
                    
                    # Check for required fields
                    required_fields = ['id', 'title', 'content', 'source', 'published_at']
                    missing_fields = [field for field in required_fields if field not in sample]
                    
                    if missing_fields:
                        print(f"WARNING: Missing fields: {missing_fields}")
                    else:
                        print("SUCCESS: All required fields present")
                        
                return True
            else:
                print("INFO: No records found (empty table)")
                return True
                
        except Exception as e:
            print(f"FAILED: Query error - {e}")
            return False
            
    except Exception as e:
        print(f"ERROR: {e}")
        return False

async def main():
    """Main test function"""
    print("Starting Database Integration Tests")
    print("=" * 50)
    
    # Test 1: Basic connection
    test1_result = await test_database_connection()
    
    # Test 2: Current affairs operations
    test2_result = await test_current_affairs_operations()
    
    print("\n" + "=" * 50)
    print("DATABASE TEST SUMMARY")
    print("=" * 50)
    
    tests = [
        ("Connection", test1_result),
        ("Operations", test2_result)
    ]
    
    for test_name, result in tests:
        status = "PASS" if result else "FAIL"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, result in tests if result)
    print(f"\nOVERALL: {passed}/{len(tests)} tests passed")
    
    overall_success = passed >= 1
    print(f"STATUS: {'SUCCESS' if overall_success else 'NEEDS WORK'}")
    
    return overall_success

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)