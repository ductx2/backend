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


# REMOVED: test_sources_list_contains_dd_news
# DD News was removed from sources (persistent SSL/TLS connection failures)
# See optimized_rss_processor.py line 106 for removal comment
