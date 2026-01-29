#!/usr/bin/env python3
"""
Test the multi-provider integration in Drishti scraper
"""

import asyncio
import sys
import os
sys.path.append('.')

from app.services.drishti_scraper import DrishtiScraper

async def test_integration():
    """Test the updated extraction method with multi-provider router"""
    
    print("Testing Multi-Provider Integration in Drishti Scraper")
    print("=" * 60)
    
    # Initialize scraper
    scraper = DrishtiScraper()
    
    # Test URL
    test_url = "https://www.drishtiias.com/current-affairs-news-analysis-editorials/news-analysis/30-08-2025"
    
    print(f"Testing URL: {test_url}")
    print("Calling extract_articles_from_page_content with multi-provider router...")
    print("-" * 60)
    
    try:
        # This should now use the multi-provider router
        articles = await scraper.extract_articles_from_page_content(test_url)
        
        print(f"SUCCESS: Extracted {len(articles)} DrishtiArticle objects")
        
        if articles:
            print("\nExtracted Articles:")
            for i, article in enumerate(articles, 1):
                print(f"  {i}. {article.title[:60]}...")
                print(f"     Category: {article.category}")
                print(f"     Content length: {len(article.content)} chars")
        else:
            print("No articles extracted - checking for issues...")
            
        return articles
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return []

async def main():
    articles = await test_integration()
    
    print("\n" + "=" * 60)
    if len(articles) > 0:
        print(f"SUCCESS: Multi-provider integration working! Got {len(articles)} articles")
    else:
        print("FAILED: No articles extracted - integration needs debugging")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())