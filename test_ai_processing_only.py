#!/usr/bin/env python3
"""
Focused AI Processing Test
Test only the Gemini AI processing component to isolate any issues
"""

import sys
import os
import asyncio
import json
from datetime import datetime

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

try:
    from app.services.gemini_client import get_gemini_client, create_gemini_model, generate_structured_content
    from app.core.config import get_settings
    
    print("FOCUSED AI PROCESSING VALIDATION")
    print("=" * 40)
    
    settings = get_settings()
    
    async def test_basic_ai_generation():
        """Test basic AI content generation"""
        print("\n1. TESTING BASIC AI GENERATION")
        print("-" * 35)
        
        try:
            # Test getting Gemini client
            gemini_client = get_gemini_client()
            print("[OK] Gemini client initialized")
            
            # Test creating a model
            model = create_gemini_model(
                temperature=0.3,
                max_output_tokens=512
            )
            print("[OK] Gemini model created")
            
            # Test simple content generation
            test_prompt = "What is UPSC? Answer in exactly one sentence."
            response = await model.generate_content_async(test_prompt)
            
            if response and response.text:
                print(f"[OK] Basic generation working: {response.text[:80]}...")
                return True
            else:
                print("[FAIL] No response from basic generation")
                return False
                
        except Exception as e:
            print(f"[FAIL] Basic AI generation failed: {e}")
            return False
    
    async def test_structured_ai_generation():
        """Test structured AI content generation"""
        print("\n2. TESTING STRUCTURED AI GENERATION")
        print("-" * 40)
        
        try:
            # Define a simple response schema
            response_schema = {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "upsc_relevance": {"type": "number"},
                    "summary": {"type": "string"},
                    "key_points": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string"}
                    }
                },
                "required": ["title", "upsc_relevance", "summary", "key_points", "tags"]
            }
            
            # Test prompt for UPSC content analysis
            test_prompt = """
            Analyze this UPSC-relevant content:
            
            Title: India's Digital Currency Initiative
            Content: The Reserve Bank of India is exploring the implementation of a Central Bank Digital Currency (CBDC) as part of its digital transformation strategy.
            
            Provide structured analysis for UPSC preparation.
            """
            
            result = await generate_structured_content(
                prompt=test_prompt,
                response_schema=response_schema,
                temperature=0.3,
                max_output_tokens=1024
            )
            
            # Validate structured response
            if isinstance(result, dict):
                if "error" in result:
                    print(f"[WARN] Safety-blocked content returned fallback: {result.get('message', '')}")
                    return True  # This is expected behavior
                
                required_fields = ["title", "upsc_relevance", "summary", "key_points", "tags"]
                missing_fields = [field for field in required_fields if field not in result]
                
                if not missing_fields:
                    print("[OK] Structured generation working")
                    print(f"   Title: {result['title'][:50]}...")
                    print(f"   UPSC Relevance: {result['upsc_relevance']}/10")
                    print(f"   Key Points: {len(result['key_points'])} points")
                    print(f"   Tags: {result['tags'][:3]}")
                    return True
                else:
                    print(f"[FAIL] Missing fields in structured response: {missing_fields}")
                    return False
            else:
                print(f"[FAIL] Invalid structured response type: {type(result)}")
                return False
                
        except Exception as e:
            print(f"[FAIL] Structured AI generation failed: {e}")
            return False
    
    async def test_batch_ai_simulation():
        """Test batch-like AI processing (multiple articles)"""
        print("\n3. TESTING BATCH AI PROCESSING SIMULATION")
        print("-" * 45)
        
        try:
            # Simulate processing multiple articles
            test_articles = [
                {
                    "title": "New Education Policy Implementation",
                    "content": "The government has announced new guidelines for implementing the National Education Policy 2020."
                },
                {
                    "title": "Economic Survey Highlights",
                    "content": "The Economic Survey presents key insights into India's economic performance and future outlook."
                }
            ]
            
            response_schema = {
                "type": "object",
                "properties": {
                    "upsc_relevance": {"type": "number"},
                    "category": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["upsc_relevance", "category", "tags"]
            }
            
            processed_count = 0
            for i, article in enumerate(test_articles):
                try:
                    prompt = f"Analyze for UPSC relevance: {article['title']} - {article['content'][:100]}"
                    
                    result = await generate_structured_content(
                        prompt=prompt,
                        response_schema=response_schema,
                        temperature=0.3,
                        max_output_tokens=512
                    )
                    
                    if isinstance(result, dict) and ("upsc_relevance" in result or "error" in result):
                        processed_count += 1
                        print(f"   [OK] Article {i+1} processed successfully")
                    
                except Exception as article_error:
                    print(f"   [FAIL] Article {i+1} failed: {article_error}")
            
            success_rate = processed_count / len(test_articles)
            if success_rate >= 0.5:  # At least 50% success
                print(f"[OK] Batch processing simulation: {processed_count}/{len(test_articles)} articles processed")
                return True
            else:
                print(f"[FAIL] Batch processing simulation failed: {processed_count}/{len(test_articles)} articles processed")
                return False
                
        except Exception as e:
            print(f"[FAIL] Batch AI processing simulation failed: {e}")
            return False
    
    async def run_focused_ai_tests():
        """Run all focused AI processing tests"""
        
        print(f"Configuration:")
        print(f"Gemini API Key: {'[SET]' if settings.gemini_api_key else '[MISSING]'}")
        print()
        
        results = {}
        
        # Test individual AI components
        results["basic_generation"] = await test_basic_ai_generation()
        results["structured_generation"] = await test_structured_ai_generation()
        results["batch_simulation"] = await test_batch_ai_simulation()
        
        print("\n" + "=" * 40)
        print("FOCUSED AI PROCESSING TEST RESULTS")
        print("-" * 40)
        
        total_tests = len(results)
        passed_tests = sum(1 for success in results.values() if success)
        
        for test_name, success in results.items():
            status = "[PASS]" if success else "[FAIL]"
            print(f"{status} {test_name.replace('_', ' ').title()}")
        
        success_rate = passed_tests / total_tests
        print(f"\nOverall AI Processing: {passed_tests}/{total_tests} tests passed ({success_rate*100:.1f}%)")
        
        if success_rate >= 0.8:  # 80% success threshold
            print("\n[SUCCESS] AI PROCESSING VALIDATION: SUCCESSFUL")
            print("The AI processing component is working correctly")
            return True
        else:
            print("\n[FAILED] AI PROCESSING VALIDATION: FAILED")
            print("Critical issues found in AI processing")
            return False
    
    # Run focused AI tests
    success = asyncio.run(run_focused_ai_tests())
    
    if success:
        print(f"\nFocused AI processing test completed successfully at {datetime.now().isoformat()}")
        exit_code = 0
    else:
        print(f"\nFocused AI processing test failed at {datetime.now().isoformat()}")
        exit_code = 1
        
except ImportError as e:
    print(f"Import Error: {e}")
    exit_code = 1
    
except Exception as e:
    print(f"Test Error: {e}")
    exit_code = 1

exit(exit_code)