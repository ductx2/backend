import logging
import re
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
        # GS-II Polity — SC/HC judgments, Constitutional bench cases
        # Focused purely on Supreme Court & High Court orders (not legal industry noise)
        {
            "source_site": "livelaw",
            "name": "LiveLaw",
            "url": "https://www.livelaw.in/category/top-stories/google_feeds.xml",
            "section": "polity",
        },
        # GS-II/III Policy — Government press releases (PIB)
        # Essential: scheme launches, policy updates, awards — UPSC setters use PIB directly
        {
            "source_site": "pib",
            "name": "PIB English National",
            "url": "https://pib.gov.in/RssMain.aspx?ModID=6&Lang=1&Regid=3",
            "section": "policy",
        },
    ]

    def _parse_entry(self, entry: Any, source: dict[str, str]) -> dict[str, Any] | None:
        title = getattr(entry, "title", "").strip()
        if not title:
            return None
        # Filter Hindi/Devanagari titles
        if re.search(r"[\u0900-\u097F]", title):
            logger.debug("[SupplementarySources] Filtered Hindi title: %s", title[:50])
            return None
        # Filter Premium articles
        if "premium" in title.lower():
            logger.debug(
                "[SupplementarySources] Filtered premium title: %s", title[:50]
            )
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
