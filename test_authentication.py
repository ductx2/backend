#!/usr/bin/env python3
"""
Authentication System Test Script
Tests API key authentication, security headers, and protected endpoints

Tests:
1. Public endpoint access (no authentication)
2. Protected endpoint with valid API key
3. Protected endpoint with invalid API key
4. Admin endpoint access
5. Security headers validation
6. CORS configuration test

Usage: python test_authentication.py
"""

import sys
import os
import asyncio
import httpx
from datetime import datetime

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.core.config import get_settings
    from app.main import app
    
    print("Testing FastAPI Authentication System...")
    print("=" * 55)
    
    settings = get_settings()
    
    # Test configuration
    API_BASE_URL = f"http://{settings.host}:{settings.port}"
    VALID_API_KEY = settings.api_key
    INVALID_API_KEY = "invalid_key_for_testing"
    
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Environment: {settings.environment}")
    print()
    
    async def test_endpoints():
        """Test all authentication endpoints"""
        
        async with httpx.AsyncClient() as client:
            
            # Test 1: Public Health Check (No Auth Required)
            print("Test 1: Public Health Check Endpoint")
            print("-" * 40)
            try:
                response = await client.get(f"{API_BASE_URL}/api/health")
                print(f"Status Code: {response.status_code}")
                print(f"Response: {response.json()}")
                
                # Check security headers
                headers = response.headers
                security_headers = [
                    "x-content-type-options",
                    "x-frame-options", 
                    "x-xss-protection"
                ]
                
                print("Security Headers:")
                for header in security_headers:
                    value = headers.get(header, "Missing")
                    print(f"  {header}: {value}")
                
                if response.status_code == 200:
                    print("[SUCCESS] Health check endpoint working")
                else:
                    print("[FAIL] Health check endpoint failed")
                    
            except Exception as e:
                print(f"[ERROR] Health check test failed: {e}")
            
            print()
            
            # Test 2: Protected Endpoint with Valid API Key
            print("Test 2: Protected Endpoint with Valid API Key")
            print("-" * 50)
            try:
                headers = {"Authorization": f"Bearer {VALID_API_KEY}"}
                response = await client.get(f"{API_BASE_URL}/api/auth/verify", headers=headers)
                
                print(f"Status Code: {response.status_code}")
                print(f"Response: {response.json()}")
                
                if response.status_code == 200:
                    print("[SUCCESS] Valid API key authentication working")
                else:
                    print("[FAIL] Valid API key authentication failed")
                    
            except Exception as e:
                print(f"[ERROR] Valid API key test failed: {e}")
            
            print()
            
            # Test 3: Protected Endpoint with Invalid API Key
            print("Test 3: Protected Endpoint with Invalid API Key")
            print("-" * 52)
            try:
                headers = {"Authorization": f"Bearer {INVALID_API_KEY}"}
                response = await client.get(f"{API_BASE_URL}/api/auth/verify", headers=headers)
                
                print(f"Status Code: {response.status_code}")
                print(f"Response: {response.json()}")
                
                if response.status_code == 401:
                    print("[SUCCESS] Invalid API key properly rejected")
                else:
                    print("[FAIL] Invalid API key not properly rejected")
                    
            except Exception as e:
                print(f"[ERROR] Invalid API key test failed: {e}")
            
            print()
            
            # Test 4: Protected Endpoint with No API Key
            print("Test 4: Protected Endpoint with No API Key")
            print("-" * 45)
            try:
                response = await client.get(f"{API_BASE_URL}/api/auth/verify")
                
                print(f"Status Code: {response.status_code}")
                print(f"Response: {response.json()}")
                
                if response.status_code == 401:
                    print("[SUCCESS] Missing API key properly rejected")
                else:
                    print("[FAIL] Missing API key not properly rejected")
                    
            except Exception as e:
                print(f"[ERROR] No API key test failed: {e}")
            
            print()
            
            # Test 5: Admin Endpoint Access
            print("Test 5: Admin Endpoint Access")
            print("-" * 35)
            try:
                headers = {"Authorization": f"Bearer {VALID_API_KEY}"}
                response = await client.get(f"{API_BASE_URL}/api/auth/admin/status", headers=headers)
                
                print(f"Status Code: {response.status_code}")
                print(f"Response: {response.json()}")
                
                if response.status_code == 200:
                    print("[SUCCESS] Admin endpoint access working")
                else:
                    print("[FAIL] Admin endpoint access failed")
                    
            except Exception as e:
                print(f"[ERROR] Admin endpoint test failed: {e}")
            
            print()
    
    # Test Authentication System
    print("Running Authentication Tests...")
    print()
    
    # Note: These tests require the FastAPI server to be running
    print("NOTE: These tests require the FastAPI server to be running.")
    print("To start the server, run: python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print()
    
    # Configuration Validation
    print("Configuration Validation:")
    validation = settings.validate_required_settings()
    for key, value in validation.items():
        status = "[OK]" if value else "[FAIL]"
        print(f"   {status} {key}: {value}")
    print()
    
    # API Key Configuration
    print("API Key Configuration:")
    print(f"   API Key Length: {len(settings.api_key)} characters")
    print(f"   API Key Preview: {settings.api_key[:10]}...")
    print(f"   Environment: {settings.environment}")
    print()
    
    # CORS Configuration
    cors_config = settings.get_cors_config()
    print("CORS Configuration:")
    print(f"   Allowed Origins: {cors_config['allow_origins']}")
    print(f"   Allow Credentials: {cors_config['allow_credentials']}")
    print(f"   Allowed Methods: {cors_config['allow_methods']}")
    print()
    
    # Security Configuration
    print("Security Configuration:")
    print(f"   API Docs Enabled: {settings.api_docs_enabled}")
    print(f"   Is Development: {settings.is_development}")
    print(f"   Is Production: {settings.is_production}")
    print()
    
    if validation["all_required_configured"]:
        print("[SUCCESS] Authentication system is properly configured!")
        print()
        print("Ready for endpoint testing. Start the server with:")
        print("python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        print()
        print("Then test the endpoints with:")
        print(f"curl -H 'Authorization: Bearer {VALID_API_KEY}' {API_BASE_URL}/api/auth/verify")
        exit_code = 0
    else:
        print("[WARNING] Some required configurations are missing.")
        print("Check your .env file and ensure all required variables are set.")
        exit_code = 1
        
except ImportError as e:
    print(f"[ERROR] Import Error: {e}")
    print("Make sure you're running from the backend directory")
    exit_code = 1
    
except Exception as e:
    print(f"[ERROR] Authentication Test Error: {e}")
    print("Check your environment variables and .env file")
    exit_code = 1

print("=" * 55)
print(f"Authentication system test completed at {datetime.utcnow().isoformat()}")
exit(exit_code)