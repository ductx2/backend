#!/usr/bin/env python3
"""
Debug script to test article validation
"""
import sys
import os
from datetime import datetime, timezone

# Add app directory to Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from app.services.optimized_rss_processor import ProcessedArticle, OptimizedRSSProcessor

def test_validation():
    """Test article validation with sample data"""
    print("Testing article validation...")
    
    # Create a sample ProcessedArticle
    sample_article = ProcessedArticle(**{
        'title': 'Test Economic Survey Article',
        'content': 'The Economic Survey 2024 presents comprehensive analysis of India\'s economic performance including GDP growth and fiscal policy reforms.',
        'summary': 'Economic Survey highlights key policy reforms and growth projections.',
        'source': 'PIB',
        'source_url': 'https://pib.gov.in/test-article',
        'published_at': datetime.now(timezone.utc),
        'upsc_relevance': 75,
        'category': 'economics',
        'tags': ['economics', 'policy', 'survey'],
        'importance': 'high',
        'gs_paper': 'GS3',
        'content_hash': 'test_hash_12345678901234567890'
    })
    
    # Create processor instance
    processor = OptimizedRSSProcessor()
    
    # Prepare article data for database
    article_data = {
        'title': sample_article.title[:500] if sample_article.title else "Untitled",
        'content': sample_article.content if sample_article.content else "",
        'summary': sample_article.summary[:1000] if sample_article.summary else "",
        'source': sample_article.source[:100] if sample_article.source else "unknown",
        'source_url': sample_article.source_url[:500] if sample_article.source_url else "",
        'date': sample_article.published_at.strftime('%Y-%m-%d'),
        'published_at': sample_article.published_at.isoformat(),
        'upsc_relevance': max(0, min(100, int(sample_article.upsc_relevance))),
        'category': sample_article.category[:50] if sample_article.category else "general",
        'tags': sample_article.tags if isinstance(sample_article.tags, list) else [],
        'importance': sample_article.importance[:20] if sample_article.importance else "medium",
        'gs_paper': sample_article.gs_paper[:10] if sample_article.gs_paper else None,
        'content_hash': sample_article.content_hash,
        'status': 'published',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'updated_at': datetime.now(timezone.utc).isoformat()
    }
    
    print(f"Sample article data:")
    for key, value in article_data.items():
        print(f"  {key}: {value}")
    
    print(f"\nValidation result: {processor._validate_article_data(article_data)}")

if __name__ == "__main__":
    test_validation()