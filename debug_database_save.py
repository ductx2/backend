#!/usr/bin/env python3
"""
Debug script to test database saving specifically
"""
import sys
import os
import asyncio
from datetime import datetime, timezone

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.optimized_rss_processor import ProcessedArticle, OptimizedRSSProcessor

async def test_database_save():
    """Test database saving with sample ProcessedArticle"""
    print("Testing database saving...")
    
    # Create sample ProcessedArticle objects (similar to what AI processing creates)
    sample_articles = [
        ProcessedArticle(**{
            'title': 'Test Economic Survey Article for DB Save',
            'content': 'The Economic Survey 2024 presents comprehensive analysis of India\'s economic performance including GDP growth and fiscal policy reforms. This is detailed content for testing database insertion.',
            'summary': 'Economic Survey highlights key policy reforms and growth projections.',
            'source': 'PIB',
            'source_url': 'https://pib.gov.in/test-article-1',
            'published_at': datetime.now(timezone.utc),
            'upsc_relevance': 55,  # Above 40 minimum
            'category': 'economics',
            'tags': ['economics', 'policy', 'survey'],
            'importance': 'high',
            'gs_paper': 'GS3',
            'content_hash': 'debug_test_hash_12345678901234567890_1'
        }),
        ProcessedArticle(**{
            'title': 'Test Government Scheme Article',
            'content': 'New government scheme launched for rural development focusing on infrastructure and digital connectivity. The scheme aims to bridge the urban-rural divide.',
            'summary': 'New rural development scheme focuses on infrastructure.',
            'source': 'The Hindu',
            'source_url': 'https://thehindu.com/test-scheme-article',
            'published_at': datetime.now(timezone.utc),
            'upsc_relevance': 48,  # Above 40 minimum
            'category': 'governance',
            'tags': ['scheme', 'rural', 'development'],
            'importance': 'medium',
            'gs_paper': 'GS2',
            'content_hash': 'debug_test_hash_12345678901234567890_2'
        })
    ]
    
    # Create processor instance
    processor = OptimizedRSSProcessor()
    
    print(f"Testing database save for {len(sample_articles)} sample articles...")
    
    try:
        # Test bulk save
        save_results = await processor.bulk_save_to_database(sample_articles)
        
        print(f"\nDatabase save results:")
        print(f"  Saved: {save_results.get('saved', 0)}")
        print(f"  Duplicates: {save_results.get('duplicates', 0)}")
        print(f"  Errors: {save_results.get('errors', 0)}")
        
        if save_results.get('saved', 0) > 0:
            print("✅ Database saving is working!")
        else:
            print("❌ No articles were saved to database")
            
    except Exception as e:
        print(f"Error during database save test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_database_save())