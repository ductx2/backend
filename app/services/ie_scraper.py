"""
Indian Express web scraper for UPSC-relevant sections.

Scrapes 3 specific sections:
  - Explained (https://indianexpress.com/section/explained/)
  - Editorials (https://indianexpress.com/section/opinion/editorials/)
  - UPSC Current Affairs (https://indianexpress.com/section/upsc-current-affairs/)

Returns article metadata dicts (title, url, published_date, author, section, source_site).
Does NOT fetch article body content — that is content_extractor.py's job.
"""

import asyncio
import logging
import random
import re
from typing import Dict, List, Optional

import httpx
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)


class IndianExpressScraper:
    """Focused scraper for 3 Indian Express UPSC-relevant sections."""

    SECTIONS: Dict[str, str] = {
        "explained": "https://indianexpress.com/section/explained/",
        "editorials": "https://indianexpress.com/section/opinion/editorials/",
        "upsc-current-affairs": "https://indianexpress.com/section/upsc-current-affairs/",
    }

    USER_AGENTS: List[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    ]

    def __init__(self) -> None:
        self.rate_limit_delay: float = 1.5  # seconds between section requests

    def _get_headers(self) -> Dict[str, str]:
        """Return request headers with a random User-Agent."""
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    def _extract_date(self, container: Tag) -> Optional[str]:
        """Extract published date from an article container."""
        # Look for date in sibling/child elements with class 'date'
        # Patterns: div.date, span.date, p.date
        for selector in ["div.date", "span.date", "p.date"]:
            date_el = container.select_one(selector)
            if date_el:
                date_text = date_el.get_text(strip=True)
                if date_text:
                    return date_text

        return None

    def _extract_author(self, container: Tag) -> Optional[str]:
        """Extract author name from an article container."""
        # Look for span.author within div.byline
        byline = container.select_one("div.byline span.author")
        if byline:
            # Author is usually inside an <a> tag
            author_link = byline.select_one("a")
            if author_link:
                name = author_link.get_text(strip=True)
            else:
                name = byline.get_text(strip=True)
            # Strip "By " prefix
            name = re.sub(r"^By\s+", "", name, flags=re.IGNORECASE)
            return name if name else None

        return None

    def _parse_articles(self, html: str, section_name: str) -> List[Dict]:
        """Parse article metadata from section page HTML."""
        soup = BeautifulSoup(html, "lxml")
        articles: List[Dict] = []
        seen_urls: set = set()  # deduplicate across both patterns

        # Pattern 1: div.title > h2 > a (primary IE structure)
        for container in soup.select("div.northeast-topbox"):
            link = container.select_one("div.title h2 a")
            if link:
                href = link.get("href")
                if not href:
                    logger.warning(
                        "[IE Scraper] Skipping article with missing href in section '%s'",
                        section_name,
                    )
                    continue

                href = str(href)
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                title = link.get_text(strip=True)
                # Collapse internal whitespace (newlines, tabs)
                title = re.sub(r"\s+", " ", title).strip()
                if not title:
                    logger.warning(
                        "[IE Scraper] Skipping article with empty title: %s", href
                    )
                    continue

                articles.append(
                    {
                        "title": title,
                        "url": href,
                        "published_date": self._extract_date(container),
                        "author": self._extract_author(container),
                        "section": section_name,
                        "source_site": "indianexpress",
                    }
                )

        # Pattern 2: h2.title > a (alternative IE structure)
        for container in soup.select("div.northeast-topbox"):
            link = container.select_one("h2.title a")
            if link:
                href = link.get("href")
                if not href:
                    logger.warning(
                        "[IE Scraper] Skipping alt-pattern article with missing href in section '%s'",
                        section_name,
                    )
                    continue

                href = str(href)
                if href in seen_urls:
                    continue
                seen_urls.add(href)

                title = link.get_text(strip=True)
                title = re.sub(r"\s+", " ", title).strip()
                if not title:
                    logger.warning(
                        "[IE Scraper] Skipping alt-pattern article with empty title: %s",
                        href,
                    )
                    continue

                articles.append(
                    {
                        "title": title,
                        "url": href,
                        "published_date": self._extract_date(container),
                        "author": self._extract_author(container),
                        "section": section_name,
                        "source_site": "indianexpress",
                    }
                )

        return articles

    async def scrape_section(self, section_name: str) -> List[Dict]:
        """
        Scrape a single IE section page and return article metadata.

        Args:
            section_name: One of 'explained', 'editorials', 'upsc-current-affairs'

        Returns:
            List of article dicts with keys: title, url, published_date, author, section, source_site
        """
        url = self.SECTIONS.get(section_name)
        if not url:
            logger.error(
                "[IE Scraper] Unknown section: '%s'. Valid sections: %s",
                section_name,
                list(self.SECTIONS.keys()),
            )
            return []

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, headers=self._get_headers())
                response.raise_for_status()

            articles = self._parse_articles(response.text, section_name)
            logger.info(
                "[IE Scraper] Scraped %d articles from '%s'",
                len(articles),
                section_name,
            )
            return articles

        except httpx.HTTPStatusError as e:
            logger.error(
                "[IE Scraper] HTTP %d for section '%s': %s",
                e.response.status_code,
                section_name,
                str(e),
            )
            return []
        except Exception as e:
            logger.error(
                "[IE Scraper] Failed to scrape section '%s': %s",
                section_name,
                str(e),
            )
            return []

    async def scrape_all_sections(self) -> List[Dict]:
        """
        Scrape all 3 IE sections with rate limiting between requests.

        Returns:
            Combined list of article dicts from all sections.
        """
        all_articles: List[Dict] = []
        section_names = list(self.SECTIONS.keys())

        for i, section_name in enumerate(section_names):
            articles = await self.scrape_section(section_name)
            all_articles.extend(articles)

            # Rate limit: sleep between sections (not after last)
            if i < len(section_names) - 1:
                await asyncio.sleep(self.rate_limit_delay)

        logger.info(
            "[IE Scraper] Total: scraped %d articles across %d sections",
            len(all_articles),
            len(section_names),
        )
        return all_articles