#!/usr/bin/env python3
"""
Debug script to test Drishti article extraction directly
"""

import asyncio
import sys
import os

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.services.drishti_scraper import DrishtiScraper
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_drishti_extraction():
    """Test Drishti article extraction and log results"""
    try:
        logger.info("🔍 Starting Drishti extraction test...")
        
        # Create scraper instance
        scraper = DrishtiScraper()
        
        # Extract articles
        articles = await scraper.scrape_daily_current_affairs(max_articles=5)
        
        logger.info(f"📊 Extracted {len(articles)} articles total")
        
        # Analyze each article
        for i, article in enumerate(articles, 1):
            logger.info(f"\n🔍 ARTICLE {i} ANALYSIS:")
            logger.info(f"   Title: {repr(article.title)}")
            logger.info(f"   Title Length: {len(article.title)} chars")
            logger.info(f"   Content Length: {len(article.content)} chars") 
            logger.info(f"   Content Preview: {repr(article.content[:100])}...")
            logger.info(f"   UPSC Relevance: {article.upsc_relevance}")
            logger.info(f"   Content Hash: {article.content_hash}")
            logger.info(f"   Source: {article.source}")
            logger.info(f"   Category: {article.category}")
            
            # Check for Unicode issues
            content_combined = article.title + article.content
            has_unicode_issues = '�' in content_combined or '\ufffd' in content_combined or '\\x' in content_combined
            logger.info(f"   Unicode Issues: {'YES' if has_unicode_issues else 'NO'}")
            
            # Validation checks
            title_valid = article.title and len(article.title.strip()) >= 10
            content_valid = article.content and len(article.content.strip()) >= 50
            
            logger.info(f"   Title Valid: {'YES' if title_valid else 'NO'}")
            logger.info(f"   Content Valid: {'YES' if content_valid else 'NO'}")
            logger.info(f"   Overall Valid: {'YES' if title_valid and content_valid else 'NO'}")
        
        # Summary
        valid_articles = sum(1 for a in articles if a.title and len(a.title.strip()) >= 10 and a.content and len(a.content.strip()) >= 50)
        logger.info(f"\n📈 SUMMARY:")
        logger.info(f"   Total Articles: {len(articles)}")
        logger.info(f"   Valid Articles: {valid_articles}")
        logger.info(f"   Invalid Articles: {len(articles) - valid_articles}")
        
        return articles
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return []

if __name__ == "__main__":
    # Run the test
    articles = asyncio.run(test_drishti_extraction())
    print(f"\n🎯 Test completed. Found {len(articles)} articles.")