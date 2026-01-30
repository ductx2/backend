"""
Test RSS sources return 200 OK
"""

import pytest
import httpx
import feedparser


RSS_SOURCES = [
    {
        "name": "The Hindu - National",
        "url": "https://www.thehindu.com/news/national/feeder/default.rss",
        "priority": 1,
    },
    {
        "name": "The Hindu - International",
        "url": "https://www.thehindu.com/news/international/feeder/default.rss",
        "priority": 1,
    },
    {
        "name": "Economic Times",
        "url": "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
        "priority": 1,
    },
    {
        "name": "Indian Express",
        "url": "https://indianexpress.com/section/india/feed/",
        "priority": 1,
    },
    {"name": "LiveMint", "url": "https://www.livemint.com/rss/politics", "priority": 2},
]


@pytest.mark.asyncio
async def test_all_rss_sources_return_200_ok():
    """Test that all 5 working RSS sources return 200 OK with valid feeds (DD News skipped - currently unreliable)"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        for source in RSS_SOURCES:
            print(f"Testing {source['name']}...")
            response = await client.get(source["url"], headers=headers)

            assert response.status_code == 200, (
                f"{source['name']} failed with {response.status_code}"
            )

            feed = feedparser.parse(response.content)
            assert len(feed.entries) > 0, f"{source['name']} has no entries"

            print(f"OK: {source['name']}: {len(feed.entries)} articles (200 OK)")
