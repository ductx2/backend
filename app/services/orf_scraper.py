"""
ORF Expert Speak scraper.

ORF (Observer Research Foundation) is a server-rendered site (not a Vue SPA or WordPress).
Discovered via Playwright inspection of https://www.orfonline.org/expert-speak:
- No XHR/Fetch API calls for article data
- No WordPress REST API (/wp-json/wp/v2/ returns 404)
- No RSS feed available
- Content rendered in HTML with Bootstrap pagination (?page=N)
- ~9 articles per page
- Article structure: .col-sm-9 > .topic_story > span.show_date + a[href*=expert-speak/] + p

This scraper uses httpx + BeautifulSoup against the server-rendered HTML pages.
"""

import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ORFScraper:
    # Discovered via Playwright: ORF expert-speak listing page with ?page=N pagination
    # Network inspection showed NO JSON API — content is server-rendered HTML
    BASE_URL = "https://www.orfonline.org/expert-speak"

    MAX_PAGES = 5
    PER_PAGE = 9  # ~9 articles per page (observed via Playwright)

    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]

    def _get_headers(self) -> dict[str, str]:
        import random

        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    async def _http_get(self, url: str) -> httpx.Response:
        async with httpx.AsyncClient(
            headers=self._get_headers(), timeout=30.0, follow_redirects=True
        ) as client:
            return await client.get(url)

    def _parse_date(self, date_str: str) -> datetime | None:
        """Parse ORF date format 'Feb 21, 2026' to UTC datetime."""
        date_str = re.sub(r"\s+", " ", date_str.strip())
        for fmt in ("%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y"):
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    def _parse_page_html(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        articles: list[dict[str, Any]] = []

        col_containers = soup.select(".col-sm-9")
        for col in col_containers:
            link = col.select_one('a[href*="expert-speak/"]')
            if not link:
                continue

            title = link.get_text(strip=True)
            if not title:
                continue

            href = link.get("href", "")
            if not href.startswith("http"):
                href = f"https://www.orfonline.org{href}"

            date_span = col.select_one("span.show_date")
            published_date: datetime | None = None
            if date_span:
                published_date = self._parse_date(date_span.get_text(strip=True))

            excerpt_p = col.select_one("p")
            content = excerpt_p.get_text(strip=True) if excerpt_p else ""

            articles.append(
                {
                    "title": title,
                    "content": content,
                    "source_url": href,
                    "source_site": "orf",
                    "section": "expert-speak",
                    "published_date": published_date,
                }
            )

        return articles

    def _has_next_page(self, html: str) -> bool:
        soup = BeautifulSoup(html, "html.parser")
        pagination = soup.select_one(".pagination")
        if not pagination:
            return False
        next_link = pagination.select_one('a.page-link[href*="page="]')
        if not next_link:
            return False
        link_text = next_link.get_text(strip=True).lower()
        return "next" in link_text

    async def fetch_articles(self, hours: int = 48) -> list[dict[str, Any]]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        all_articles: list[dict[str, Any]] = []

        for page_num in range(1, self.MAX_PAGES + 1):
            url = self.BASE_URL if page_num == 1 else f"{self.BASE_URL}?page={page_num}"

            try:
                response = await self._http_get(url)
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.error(
                    "ORF: HTTP %s fetching %s: %s",
                    e.response.status_code,
                    url,
                    str(e),
                )
                return all_articles if all_articles else []
            except Exception as e:
                logger.error("ORF: Request failed for %s: %s", url, str(e))
                return all_articles if all_articles else []

            page_articles = self._parse_page_html(response.text)

            if not page_articles:
                logger.info(
                    "ORF: No articles on page %d, stopping pagination", page_num
                )
                break

            all_articles.extend(page_articles)

            if not self._has_next_page(response.text):
                break

        filtered = [
            a
            for a in all_articles
            if a["published_date"] is not None and a["published_date"] >= cutoff
        ]

        logger.info(
            "ORF: Fetched %d total, %d within %dh window",
            len(all_articles),
            len(filtered),
            hours,
        )
        return filtered
