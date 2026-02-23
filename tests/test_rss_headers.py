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


def test_sources_list_contains_all_eight_hindu_feeds():
    """Test that all 8 curated Hindu feeds are in sources list"""
    processor = OptimizedRSSProcessor()
    # Assert total source count is 8
    assert len(processor.sources) == 8, (
        f"Expected 8 sources, got {len(processor.sources)}"
    )

    # Assert all sources are The Hindu feeds
    for source in processor.sources:
        assert "thehindu.com" in source.url, (
            f"Non-Hindu source found: {source.name} ({source.url})"
        )

    print("OK: All 8 curated Hindu feeds present in sources list")
