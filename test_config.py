#!/usr/bin/env python3
"""
Quick test script to verify configuration loading
Tests that all environment variables are loaded correctly from main project
"""

import sys
import os

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.core.config import get_settings
    
    print("Testing FastAPI Configuration Loading...")
    print("=" * 50)
    
    settings = get_settings()
    
    # Test configuration loading
    print(f"[OK] Settings loaded successfully")
    print(f"Environment: {settings.environment}")
    print(f"Host: {settings.host}:{settings.port}")
    print()
    
    # Test validation
    validation = settings.validate_required_settings()
    print("Configuration Validation:")
    for key, value in validation.items():
        status = "[OK]" if value else "[FAIL]"
        print(f"   {status} {key}: {value}")
    print()
    
    # Test key configurations (without exposing secrets)
    print("Key Configurations:")
    print(f"   Supabase URL: {settings.supabase_url[:30]}...")
    print(f"   Gemini API Key: {'[OK] Configured' if settings.gemini_api_key else '[FAIL] Missing'}")
    print(f"   FastAPI API Key: {'[OK] Configured' if settings.api_key else '[FAIL] Missing'}")
    print(f"   Site URL: {settings.site_url}")
    print()
    
    # Test computed properties
    print("Computed Properties:")
    print(f"   Is Development: {settings.is_development}")
    print(f"   Is Production: {settings.is_production}")
    print(f"   API Docs Enabled: {settings.api_docs_enabled}")
    print()
    
    # Test CORS configuration
    cors_config = settings.get_cors_config()
    print("CORS Configuration:")
    print(f"   Allowed Origins: {cors_config['allow_origins']}")
    print()
    
    if validation["all_required_configured"]:
        print("[SUCCESS] ALL TESTS PASSED! Configuration is ready for FastAPI!")
        exit_code = 0
    else:
        print("[WARNING] Some required configurations are missing. Check your .env file.")
        exit_code = 1
        
except ImportError as e:
    print(f"[ERROR] Import Error: {e}")
    print("Make sure you're running from the backend directory")
    exit_code = 1
    
except Exception as e:
    print(f"[ERROR] Configuration Error: {e}")
    print("Check your environment variables and .env file")
    exit_code = 1

print("=" * 50)
exit(exit_code)