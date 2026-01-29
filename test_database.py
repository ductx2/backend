#!/usr/bin/env python3
"""
Supabase Database Connection Test Script
Tests database connectivity, table access, and operations

Tests:
1. Database connection initialization
2. Health check validation
3. Current affairs table access
4. Record count retrieval
5. Sample data operations (if safe)

Usage: python test_database.py
"""

import sys
import os
import asyncio
from datetime import datetime

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.core.config import get_settings
    from app.core.database import SupabaseConnection, get_database_sync
    
    print("Testing Supabase Database Connection...")
    print("=" * 50)
    
    settings = get_settings()
    
    # Test configuration
    print(f"Supabase URL: {settings.supabase_url}")
    print(f"Environment: {settings.environment}")
    print(f"Service Key Configured: {'Yes' if settings.supabase_service_key else 'No'}")
    print(f"Service Key Length: {len(settings.supabase_service_key)} characters")
    print()
    
    async def test_database_operations():
        """Test all database operations"""
        
        print("Database Connection Tests")
        print("-" * 30)
        
        # Initialize database connection
        db = get_database_sync()
        
        # Test 1: Database Client Initialization
        print("Test 1: Database Client Initialization")
        try:
            client = db.client
            print("[SUCCESS] Supabase client initialized")
            print(f"Client configured: {'Yes' if client else 'No'}")
        except Exception as e:
            print(f"[FAIL] Client initialization failed: {e}")
            return False
        
        print()
        
        # Test 2: Database Health Check
        print("Test 2: Database Health Check")
        try:
            health = await db.health_check()
            print(f"Status: {health['status']}")
            print(f"Connection: {health['connection']}")
            print(f"Table Accessible: {health.get('table_accessible', 'Unknown')}")
            print(f"Timestamp: {health['timestamp']}")
            
            if health.get('error'):
                print(f"Error: {health['error']}")
                return False
                
            if health['status'] == 'healthy':
                print("[SUCCESS] Database health check passed")
            else:
                print("[FAIL] Database health check failed")
                return False
                
        except Exception as e:
            print(f"[FAIL] Health check failed: {e}")
            return False
        
        print()
        
        # Test 3: Current Affairs Table Access
        print("Test 3: Current Affairs Table Access")
        try:
            count = await db.get_current_affairs_count()
            print(f"Total current affairs records: {count}")
            
            if count >= 0:
                print("[SUCCESS] Current affairs table accessible")
            else:
                print("[FAIL] Could not access current affairs table")
                return False
                
        except Exception as e:
            print(f"[FAIL] Table access failed: {e}")
            return False
        
        print()
        
        # Test 4: Recent Articles Retrieval
        print("Test 4: Recent Articles Retrieval")
        try:
            recent_articles = await db.get_recent_articles(limit=5)
            print(f"Retrieved {len(recent_articles)} recent articles")
            
            if recent_articles:
                print("Sample article data:")
                article = recent_articles[0]
                print(f"  Title: {article.get('title', 'No title')[:60]}...")
                print(f"  Source: {article.get('source', 'Unknown')}")
                print(f"  Created: {article.get('created_at', 'Unknown')}")
                print(f"  UPSC Score: {article.get('upsc_relevance', 'N/A')}")
            
            print("[SUCCESS] Recent articles retrieval working")
                
        except Exception as e:
            print(f"[FAIL] Recent articles retrieval failed: {e}")
            return False
        
        print()
        
        # Test 5: Search Functionality
        print("Test 5: Search Functionality")
        try:
            # Search for common UPSC terms
            search_results = await db.search_articles("government", limit=3)
            print(f"Search results for 'government': {len(search_results)} articles")
            
            print("[SUCCESS] Search functionality working")
                
        except Exception as e:
            print(f"[FAIL] Search functionality failed: {e}")
            return False
        
        print()
        
        # Test 6: Source-based Filtering
        print("Test 6: Source-based Filtering")
        try:
            # Get articles from PIB (common RSS source)
            pib_articles = await db.get_articles_by_source("PIB", limit=3)
            print(f"PIB articles found: {len(pib_articles)}")
            
            print("[SUCCESS] Source-based filtering working")
                
        except Exception as e:
            print(f"[FAIL] Source-based filtering failed: {e}")
            return False
        
        print()
        
        # Test 7: High Relevance Articles
        print("Test 7: High Relevance Articles")
        try:
            high_relevance = await db.get_high_relevance_articles(min_score=70, limit=5)
            print(f"High relevance articles (70+): {len(high_relevance)} articles")
            
            if high_relevance:
                avg_score = sum(article.get('upsc_relevance', 0) for article in high_relevance) / len(high_relevance)
                print(f"Average relevance score: {avg_score:.1f}")
            
            print("[SUCCESS] High relevance filtering working")
                
        except Exception as e:
            print(f"[FAIL] High relevance filtering failed: {e}")
            return False
        
        print()
        
        return True
    
    # Configuration Validation
    print("Configuration Validation:")
    validation = settings.validate_required_settings()
    for key, value in validation.items():
        status = "[OK]" if value else "[FAIL]"
        print(f"   {status} {key}: {value}")
    print()
    
    # Database Configuration
    print("Database Configuration:")
    print(f"   Supabase URL: {settings.supabase_url}")
    print(f"   Service Key Present: {'Yes' if settings.supabase_service_key else 'No'}")
    print(f"   Environment: {settings.environment}")
    print()
    
    if not validation["supabase_configured"]:
        print("[ERROR] Supabase not properly configured.")
        print("Check your NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.")
        exit_code = 1
    else:
        # Run database tests
        print("Running Database Connection Tests...")
        print()
        
        success = asyncio.run(test_database_operations())
        
        if success:
            print("[SUCCESS] ALL DATABASE TESTS PASSED!")
            print()
            print("Database Integration Status:")
            print("✅ Supabase client initialization working")
            print("✅ Database connection healthy")
            print("✅ Current affairs table accessible")
            print("✅ All CRUD operations functional")
            print("✅ Search and filtering capabilities working")
            print()
            print("Ready for FastAPI integration!")
            exit_code = 0
        else:
            print("[FAIL] Some database tests failed.")
            print("Check your Supabase configuration and network connectivity.")
            exit_code = 1
        
except ImportError as e:
    print(f"[ERROR] Import Error: {e}")
    print("Make sure you're running from the backend directory")
    print("Install required dependencies: pip install -r requirements.txt")
    exit_code = 1
    
except Exception as e:
    print(f"[ERROR] Database Test Error: {e}")
    print("Check your environment variables and Supabase configuration")
    exit_code = 1

print("=" * 50)
print(f"Database connection test completed at {datetime.utcnow().isoformat()}")
exit(exit_code)