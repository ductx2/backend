"""
MEA Press Releases httpx Scraper.

Scrapes press releases from the Ministry of External Affairs (mea.gov.in).
Server-rendered HTML — uses httpx + BeautifulSoup (no Playwright needed).
Returns articles within a configurable time window (default 48 hours).
"""

import logging
import random
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]


class MEAScraper:
    LISTING_URL = "https://www.mea.gov.in/whats-new-viewall.htm"
    BASE_URL = "https://www.mea.gov.in"

    # MEA date formats seen on the listing page: "February 23, 2026"
    DATE_FORMAT = "%B %d, %Y"

    def _get_headers(self) -> dict[str, str]:
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    async def _http_get(self, url: str) -> httpx.Response:
        """Mockable HTTP GET — single entry point for all network calls."""
        async with httpx.AsyncClient(
            headers=self._get_headers(), timeout=30.0, follow_redirects=True
        ) as client:
            return await client.get(url)

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse MEA date string into timezone-aware UTC datetime.

        MEA dates are in IST but displayed as plain strings like "February 23, 2026".
        We parse them and treat as start-of-day IST (UTC+5:30), then convert to UTC.
        """
        date_str = date_str.strip()
        try:
            # IST offset: +5:30
            ist = timezone(timedelta(hours=5, minutes=30))
            naive = datetime.strptime(date_str, self.DATE_FORMAT)
            return naive.replace(tzinfo=ist).astimezone(timezone.utc)
        except (ValueError, TypeError):
            logger.warning("MEA: Failed to parse date '%s'", date_str)
            return None

    def _parse_listing(self, html: str, cutoff: datetime) -> list[dict[str, str]]:
        """Extract article links from the MEA "What's New" listing page.

        Returns list of dicts with keys: title, href, published_date.
        Only articles newer than `cutoff` are included.

        Targets: <table class="table table-striped"> rows where each <tr> has
        a <td> with an <a> link and a <td> with date text.
        """
        soup = BeautifulSoup(html, "html.parser")
        articles: list[dict[str, str]] = []

        # MEA listing uses a table with class "table table-striped"
        table = soup.find("table", class_="table")
        if not table:
            logger.warning("MEA: No listing table found in HTML")
            return []

        rows = table.find_all("tr")
        if not rows:
            logger.warning("MEA: No rows found in listing table")
            return []

        for row in rows:
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            link = cells[0].find("a", href=True)
            if not link:
                continue

            title = link.get_text(strip=True)
            href = link["href"]
            date_text = cells[-1].get_text(strip=True)

            if not title or not href:
                continue

            parsed_date = self._parse_date(date_text)
            if parsed_date is None:
                logger.debug("MEA: Skipping article with unparseable date: %s", title)
                continue

            if parsed_date < cutoff:
                logger.debug("MEA: Skipping old article '%s' (%s)", title, date_text)
                continue

            articles.append(
                {
                    "title": title,
                    "href": href,
                    "published_date": parsed_date.isoformat(),
                }
            )

        logger.info(
            "MEA: Found %d articles within time window from listing", len(articles)
        )
        return articles

    def _parse_detail(
        self, html: str, source_url: str, listing_title: str, published_date: str
    ) -> dict[str, Any] | None:
        """Extract article content from an MEA detail page.

        Targets:
        - <h2 class="PageHead"> for the headline
        - <div id="ContentText"> for the body text
        - Falls back to listing title if headline not found
        """
        soup = BeautifulSoup(html, "html.parser")

        headline_tag = soup.find("h2", class_="PageHead")
        title = headline_tag.get_text(strip=True) if headline_tag else listing_title

        content_div = soup.find("div", id="ContentText")
        if not content_div:
            content_div = soup.find("div", class_="content-area")

        if not content_div:
            logger.warning("MEA: No content found on detail page: %s", source_url)
            return None

        content = content_div.get_text(separator="\n", strip=True)
        if not content:
            logger.warning("MEA: Empty content on detail page: %s", source_url)
            return None

        return {
            "title": title,
            "content": content,
            "source_url": source_url,
            "source_site": "mea",
            "section": "press-releases",
            "published_date": published_date,
        }

    def _build_detail_url(self, href: str) -> str:
        """Convert a relative MEA href to a fully qualified URL."""
        if href.startswith("http"):
            return href
        if href.startswith("/"):
            return f"{self.BASE_URL}{href}"
        return f"{self.BASE_URL}/{href}"

    async def fetch_articles(self, hours: int = 48) -> list[dict[str, Any]]:
        """Fetch recent MEA press releases within the given time window.

        1. GET the listing page (whats-new-viewall.htm)
        2. Parse links + dates, filter by cutoff
        3. GET each detail page, extract headline + body
        4. Return standardized dicts

        Returns empty list on any network error (never raises).
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)

        try:
            listing_response = await self._http_get(self.LISTING_URL)
            listing_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                "MEA: Listing page HTTP error %s: %s",
                e.response.status_code,
                self.LISTING_URL,
            )
            return []
        except Exception as e:
            logger.error(
                "MEA: Failed to fetch listing page %s: %s", self.LISTING_URL, e
            )
            return []

        listing_items = self._parse_listing(listing_response.text, cutoff)
        if not listing_items:
            logger.warning("MEA: No articles found within %d-hour window", hours)
            return []

        articles: list[dict[str, Any]] = []
        for item in listing_items:
            detail_url = self._build_detail_url(item["href"])
            try:
                detail_response = await self._http_get(detail_url)
                detail_response.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "MEA: Detail page HTTP error %s: %s",
                    e.response.status_code,
                    detail_url,
                )
                continue
            except Exception as e:
                logger.error("MEA: Failed to fetch detail page %s: %s", detail_url, e)
                continue

            article = self._parse_detail(
                detail_response.text,
                source_url=detail_url,
                listing_title=item["title"],
                published_date=item["published_date"],
            )
            if article:
                articles.append(article)

        logger.info(
            "MEA: Returning %d articles from %d listing items",
            len(articles),
            len(listing_items),
        )
        return articles
