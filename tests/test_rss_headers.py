"""
Test RSS header configuration
"""

import pytest
from app.services.optimized_rss_processor import OptimizedRSSProcessor


def test_get_optimized_headers_returns_user_agent_for_all_sources():
    """Test that _get_optimized_headers returns User-Agent for all sources"""
    processor = OptimizedRSSProcessor()

    # Test all 6 sources
    for source in processor.sources:
        headers = processor._get_optimized_headers(source)

        # Assert User-Agent exists
        assert "User-Agent" in headers, f"{source.name} missing User-Agent"

        # Assert Mozilla/5.0 User-Agent (standard bot bypass)
        assert "Mozilla/5.0" in headers["User-Agent"], (
            f"{source.name} has invalid User-Agent"
        )

        # Assert Accept header exists
        assert "Accept" in headers, f"{source.name} missing Accept header"

        print(f"OK: {source.name}: User-Agent applied correctly")


def test_sources_list_contains_dd_news():
    """Test that DD News is in sources list"""
    processor = OptimizedRSSProcessor()

    # Assert DD News exists
    dd_news_sources = [s for s in processor.sources if "DD News" in s.name]
    assert len(dd_news_sources) == 1, "DD News not found in sources"

    # Assert DD News has correct URL
    dd_news = dd_news_sources[0]
    assert "ddnews.gov.in" in dd_news.url, "DD News has incorrect URL"

    # Assert total source count is still 6
    assert len(processor.sources) == 6, (
        f"Expected 6 sources, got {len(processor.sources)}"
    )

    print("OK: DD News present in sources list")
