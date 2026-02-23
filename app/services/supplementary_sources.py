import logging
from datetime import datetime, timezone
from typing import Any

import feedparser
import requests

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/rss+xml, application/xml, text/xml, application/atom+xml, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "DNT": "1",
}


class SupplementarySources:
    SOURCES: list[dict[str, str]] = [
        {
            "source_site": "prs",
            "name": "PRS Legislative Research",
            "url": "https://www.prsindia.org/parliamenttrack/rss",
            "section": "legislature",
        },
        # Economy — RBI
        {
            "source_site": "rbi",
            "name": "RBI Press Releases",
            "url": "https://rbi.org.in/pressreleases_rss.xml",
            "section": "economy",
        },
        {
            "source_site": "rbi",
            "name": "RBI Notifications",
            "url": "https://rbi.org.in/notifications_rss.xml",
            "section": "economy",
        },
        {
            "source_site": "rbi",
            "name": "RBI Speeches",
            "url": "https://rbi.org.in/speeches_rss.xml",
            "section": "economy",
        },
        {
            "source_site": "rbi",
            "name": "RBI Publications",
            "url": "https://rbi.org.in/Publication_rss.xml",
            "section": "economy",
        },
        # GS-II Polity — Supreme Court, High Courts, legal analysis
        {
            "source_site": "barandbench",
            "name": "Bar & Bench",
            "url": "https://www.barandbench.com/stories.rss",
            "section": "polity",
        },
        # GS-II Polity — SC/HC judgments, legal news
        {
            "source_site": "livelaw",
            "name": "LiveLaw",
            "url": "https://www.livelaw.in/category/top-stories/google_feeds.xml",
            "section": "polity",
        },
        # GS-II/III Policy + GS-II International Relations
        {
            "source_site": "niti",
            "name": "NITI Aayog",
            "url": "https://niti.gov.in/rss.xml",
            "section": "policy",
        },
        {
            "source_site": "gatewayhouse",
            "name": "Gateway House",
            "url": "https://www.gatewayhouse.in/feed",
            "section": "international_relations",
        },
    ]

    def _parse_entry(self, entry: Any, source: dict[str, str]) -> dict[str, Any] | None:
        title = getattr(entry, "title", "").strip()
        if not title:
            return None
        # Filter out Dealstreet entries (business law, not UPSC-relevant)
        tags = getattr(entry, 'tags', []) or []
        if any('dealstreet' in (tag.get('term', '') or '').lower() for tag in tags):
            return None

        url = getattr(entry, "link", "").strip()
        if not url:
            return None

        published_date: datetime = datetime.now(timezone.utc)
        raw_parsed = getattr(entry, "published_parsed", None)
        if raw_parsed:
            try:
                published_date = datetime(*raw_parsed[:6], tzinfo=timezone.utc)
            except Exception:
                pass

        author: str | None = entry.get("author", None)

        return {
            "title": title,
            "url": url,
            "published_date": published_date,
            "author": author,
            "section": source["section"],
            "source_site": source["source_site"],
        }

    def _fetch_source(self, source: dict[str, str]) -> list[dict[str, Any]]:
        try:
            response = requests.get(source["url"], headers=_HEADERS, timeout=30)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            if not feed.entries:
                logger.warning("No entries in feed for %s", source["name"])
                return []

            articles: list[dict[str, Any]] = []
            for entry in feed.entries:
                article = self._parse_entry(entry, source)
                if article is not None:
                    articles.append(article)

            logger.info("Fetched %d articles from %s", len(articles), source["name"])
            return articles

        except Exception as exc:
            logger.error("Failed to fetch %s: %s", source["name"], exc)
            return []

    def fetch_all(self) -> list[dict[str, Any]]:
        all_articles: list[dict[str, Any]] = []
        for source in self.SOURCES:
            articles = self._fetch_source(source)
            all_articles.extend(articles)
        return all_articles
