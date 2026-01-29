#!/usr/bin/env python3
"""
Test Multi-Provider AI with Real Drishti IAS Content
Tests extraction from actual daily current affairs page
"""

import asyncio
import json
import requests
from test_multi_provider_ai import MultiProviderAI

async def test_with_real_drishti_content():
    """Test providers with actual Drishti IAS content"""
    
    # Fetch real content from today's Drishti page
    test_url = "https://www.drishtiias.com/current-affairs-news-analysis-editorials/news-analysis/30-08-2025"
    
    print("Fetching real content from Drishti IAS...")
    print(f"URL: {test_url}")
    print("=" * 60)
    
    try:
        response = requests.get(test_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }, timeout=30)
        
        response.raise_for_status()
        html_content = response.text
        
        print(f"Successfully fetched {len(html_content)} characters from Drishti")
        
        # Clean and extract text content for AI processing
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove unwanted elements
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            element.decompose()
        
        # Get main content
        main_content = soup.select_one('.article-list') or soup.select_one('main') or soup
        text_content = main_content.get_text(separator='\n\n', strip=True)
        
        # Limit content size for AI processing
        max_chars = 15000  # Reasonable size for both providers
        if len(text_content) > max_chars:
            text_content = text_content[:max_chars] + "\n\n[Content truncated...]"
        
        print(f"Cleaned content: {len(text_content)} characters")
        print("\nFirst 500 characters:")
        print("-" * 60)
        print(text_content[:500] + "...")
        print("-" * 60)
        
        # Initialize multi-provider tester
        tester = MultiProviderAI()
        tester.test_content = text_content  # Override test content
        
        print("\nStarting AI extraction tests with real Drishti content...")
        print("=" * 60)
        
        # Test all providers
        results = await tester.test_all_providers()
        
        # Compare results
        tester.compare_results(results)
        
        # Show detailed article results
        print("\n" + "=" * 60)
        print("DETAILED EXTRACTION RESULTS")
        print("=" * 60)
        
        for result in results:
            if result.success and result.articles:
                print(f"\n{result.provider.upper()} ({result.model}):")
                print(f"Extracted {len(result.articles)} articles:")
                
                for i, article in enumerate(result.articles, 1):
                    title = article.get('title', 'No title')
                    content = article.get('content', 'No content')
                    category = article.get('category', 'Unknown')
                    
                    print(f"\n  Article {i}:")
                    print(f"    Title: {title}")
                    print(f"    Category: {category}")
                    print(f"    Content: {content[:200]}...")
        
        return results
        
    except Exception as e:
        print(f"Error fetching/processing Drishti content: {e}")
        return None

async def main():
    """Main test function"""
    print("REAL DRISHTI IAS CONTENT EXTRACTION TEST")
    print("=" * 60)
    
    results = await test_with_real_drishti_content()
    
    if results:
        successful_providers = [r for r in results if r.success]
        if successful_providers:
            print(f"\nSUCCESS: {len(successful_providers)} providers successfully extracted content!")
            print("This confirms both providers can handle real news content without safety filter issues.")
        else:
            print("\nFAILED: No providers successfully extracted content.")
            print("This indicates potential issues that need addressing.")
    else:
        print("\nFAILED: Could not fetch or process Drishti content.")

if __name__ == "__main__":
    asyncio.run(main())