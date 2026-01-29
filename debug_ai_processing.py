#!/usr/bin/env python3
"""
Debug script to test AI processing and validation
"""
import sys
import os
import asyncio
from datetime import datetime, timezone

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.optimized_rss_processor import OptimizedRSSProcessor

async def test_ai_processing():
    """Test AI processing with sample RSS articles"""
    print("Testing AI processing and validation...")
    
    # Create sample RSS article (simulating what comes from RSS feeds)
    sample_articles = [{
        'title': 'Economic Survey 2024 Highlights Key Policy Reforms',
        'content': 'The Economic Survey 2024 presents comprehensive analysis of India\'s economic performance including GDP growth projections, inflation management strategies, and fiscal policy reforms. The survey emphasizes digital infrastructure development and sustainable growth initiatives.',
        'description': 'Economic Survey highlights key policy reforms and growth projections.',
        'source': 'PIB',
        'source_url': 'https://pib.gov.in/test-article',
        'published_at': datetime.now(timezone.utc),
        'content_hash': 'test_hash_12345678901234567890_1',
        'full_content_extracted': True,
        'content_quality_score': 0.8,
        'extraction_method': 'enhanced'
    }]
    
    # Create processor instance
    processor = OptimizedRSSProcessor()
    
    print(f"Processing {len(sample_articles)} sample articles...")
    
    try:
        # Test AI processing
        processed_articles = await processor.process_articles_with_single_ai_pass(sample_articles)
        
        print(f"AI processing completed. {len(processed_articles)} articles processed.")
        
        if processed_articles:
            article = processed_articles[0]
            print(f"\nProcessed article details:")
            print(f"  Title: {article.title}")
            print(f"  UPSC Relevance: {article.upsc_relevance}")
            print(f"  Category: {article.category}")
            print(f"  Tags: {article.tags}")
            print(f"  Content Hash: {article.content_hash}")
            print(f"  Source: {article.source}")
            
            # Test database preparation
            article_data = {
                'title': article.title[:500] if article.title else "Untitled",
                'content': article.content if article.content else "",
                'summary': article.summary[:1000] if article.summary else "",
                'source': article.source[:100] if article.source else "unknown",
                'source_url': article.source_url[:500] if article.source_url else "",
                'date': article.published_at.strftime('%Y-%m-%d'),
                'published_at': article.published_at.isoformat(),
                'upsc_relevance': max(0, min(100, int(article.upsc_relevance))),
                'category': article.category[:50] if article.category else "general",
                'tags': article.tags if isinstance(article.tags, list) else [],
                'importance': article.importance[:20] if article.importance else "medium",
                'gs_paper': article.gs_paper[:10] if article.gs_paper else None,
                'content_hash': article.content_hash,
                'status': 'published',
                'created_at': datetime.now(timezone.utc).isoformat(),
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            print(f"\nDatabase format validation:")
            validation_result = processor._validate_article_data(article_data)
            print(f"Validation result: {validation_result}")
            
            if not validation_result:
                print(f"Article data that failed validation:")
                for key, value in article_data.items():
                    print(f"  {key}: {repr(value)}")
                    
        else:
            print("No articles were processed by AI. Check AI service configuration.")
            
    except Exception as e:
        print(f"Error during AI processing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ai_processing())