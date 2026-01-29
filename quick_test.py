#!/usr/bin/env python3
"""
🚀 QUICK COMPONENT TESTING SCRIPT
Test individual components of the content pipeline

Usage:
python quick_test.py
"""

import asyncio
import sys
import os

# Add the project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.content_extractor import UniversalContentExtractor
from app.services.ai_enhancement_service import AIEnhancementService
from app.services.optimized_rss_processor import OptimizedRSSProcessor

async def test_content_extractor():
    """Test the Universal Content Extractor"""
    print("🔍 Testing Universal Content Extractor...")
    
    extractor = UniversalContentExtractor()
    
    # Test with a simple URL
    test_url = "https://pib.gov.in/"
    
    try:
        result = await extractor.extract_content(test_url, strategy="auto")
        
        if result:
            print(f"✅ Content extraction successful!")
            print(f"   Title: {result.title[:60]}...")
            print(f"   Content length: {len(result.content)} characters")
            print(f"   Strategy used: {result.extraction_method}")
            print(f"   Quality score: {result.content_quality_score}")
            print(f"   Processing time: {result.processing_time:.2f}s")
            return True
        else:
            print("❌ Content extraction failed")
            return False
            
    except Exception as e:
        print(f"❌ Content extraction error: {e}")
        return False

async def test_ai_enhancement():
    """Test the AI Enhancement Service"""
    print("\n🤖 Testing AI Enhancement Service...")
    
    try:
        enhancer = AIEnhancementService()
        
        # Create test content
        from app.api.ai_enhancement_api import ContentEnhancementRequest
        
        test_request = ContentEnhancementRequest(
            title="Economic Survey 2024 Key Highlights",
            content="The Economic Survey presents comprehensive analysis of India's economic performance including GDP growth and policy reforms.",
            enhancement_mode="comprehensive",
            source_url="https://example.com/test"
        )
        
        result = await enhancer.enhance_content(test_request)
        
        if result and result.get('upsc_relevance', 0) > 0:
            print(f"✅ AI enhancement successful!")
            print(f"   UPSC Relevance: {result.get('upsc_relevance', 0)}/10")
            print(f"   Relevant papers: {len(result.get('relevant_papers', []))}")
            print(f"   Key topics: {len(result.get('key_topics', []))}")
            return True
        else:
            print("❌ AI enhancement failed")
            return False
            
    except Exception as e:
        print(f"❌ AI enhancement error: {e}")
        return False

async def test_rss_processor():
    """Test the RSS Processor"""
    print("\n📰 Testing RSS Processor...")
    
    try:
        processor = OptimizedRSSProcessor()
        
        # Test health status
        health_status = processor.get_source_health_status()
        
        if health_status:
            print(f"✅ RSS processor initialized successfully!")
            print(f"   Sources available: {len(health_status.get('sources', []))}")
            print(f"   Processing stats available: {bool(processor.processing_stats)}")
            return True
        else:
            print("❌ RSS processor initialization failed")
            return False
            
    except Exception as e:
        print(f"❌ RSS processor error: {e}")
        return False

async def main():
    """Run quick component tests"""
    print("🧪 QUICK COMPONENT TESTING SUITE")
    print("="*50)
    
    test_results = []
    
    # Test content extractor
    extractor_result = await test_content_extractor()
    test_results.append(("Content Extractor", extractor_result))
    
    # Test AI enhancement
    ai_result = await test_ai_enhancement()
    test_results.append(("AI Enhancement", ai_result))
    
    # Test RSS processor
    rss_result = await test_rss_processor()
    test_results.append(("RSS Processor", rss_result))
    
    # Summary
    print("\n" + "="*50)
    print("📊 TEST RESULTS SUMMARY")
    print("="*50)
    
    passed_tests = 0
    for test_name, result in test_results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name}: {status}")
        if result:
            passed_tests += 1
    
    print(f"\nOverall: {passed_tests}/{len(test_results)} tests passed")
    
    if passed_tests == len(test_results):
        print("\n🎉 All components working correctly!")
        print("Ready to test the full FastAPI server endpoints.")
    else:
        print("\n⚠️ Some components need attention before full testing.")

if __name__ == "__main__":
    asyncio.run(main())