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
            "source_site": "downtoearth",
            "name": "Down To Earth",
            "url": "https://www.downtoearth.org/rss/content",
            "section": "environment",
        },
        {
            "source_site": "businessstandard",
            "name": "Business Standard - Economy",
            "url": "https://www.business-standard.com/rss/economy-policy-1021.rss",
            "section": "economy",
        },
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
    ]

    def _parse_entry(self, entry: Any, source: dict[str, str]) -> dict[str, Any] | None:
        title = getattr(entry, "title", "").strip()
        if not title:
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
