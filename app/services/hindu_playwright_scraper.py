"""
The Hindu Editorial Playwright Scraper.

Scrapes opinion/editorial content from The Hindu (editorial, lead, op-ed sections).
Requires PlaywrightSessionManager with valid Hindu session.
Does NOT scrape national/international news — those are handled by RSS feeds.
"""

import asyncio
import logging
from typing import List, Optional

from app.services.playwright_session import PlaywrightSessionManager

logger = logging.getLogger(__name__)


class HinduPlaywrightScraper:
    SECTIONS = {
        "editorial": "https://www.thehindu.com/opinion/editorial/",
        "lead": "https://www.thehindu.com/opinion/lead/",
        "opinion": "https://www.thehindu.com/opinion/op-ed/",
    }

    MAX_ARTICLES_PER_SECTION = 10
    INTER_SECTION_DELAY = 1.5

    def __init__(self, session_manager: PlaywrightSessionManager) -> None:
        self.session_manager = session_manager

    async def scrape_editorials(self) -> List[dict]:
        all_articles: List[dict] = []
        seen_urls: set = set()

        try:
            for section_idx, (section_name, section_url) in enumerate(
                self.SECTIONS.items()
            ):
                if section_idx > 0:
                    await asyncio.sleep(self.INTER_SECTION_DELAY)

                section_articles = await self._scrape_section(
                    section_name, section_url, seen_urls
                )
                all_articles.extend(section_articles)

        except Exception as exc:
            logger.error(
                "[HinduScraper] Fatal error during scrape_editorials: %s", str(exc)
            )
            return []

        return all_articles

    async def _scrape_section(
        self, section_name: str, section_url: str, seen_urls: set
    ) -> List[dict]:
        articles: List[dict] = []

        try:
            page = await self.session_manager.get_page("hindu")

            await page.goto(section_url, wait_until="domcontentloaded")
            await page.wait_for_selector(
                "div.element, div.story-card, article",
                timeout=15000,
            )

            # Listing page: extract article links from <a> tags inside headings
            link_elements = await page.query_selector_all(
                "div.element a[href*='/opinion/'], "
                "div.story-card a[href*='/opinion/'], "
                "article a[href*='/opinion/']"
            )

            article_urls: List[str] = []
            for el in link_elements[: self.MAX_ARTICLES_PER_SECTION * 2]:
                href = await el.get_attribute("href")
                if not href or href in seen_urls:
                    continue
                if "/opinion/" not in href:
                    continue
                # Skip listing/section pages, only keep article URLs (.ece suffix)
                if not href.rstrip("/").endswith(".ece") and "article" not in href:
                    continue
                seen_urls.add(href)
                article_urls.append(href)
                if len(article_urls) >= self.MAX_ARTICLES_PER_SECTION:
                    break

            for article_url in article_urls:
                article = await self._extract_article(page, article_url, section_name)
                if article:
                    articles.append(article)

            await page.close()

        except Exception as exc:
            logger.error(
                "[HinduScraper] Error scraping section '%s': %s",
                section_name,
                str(exc),
            )

        return articles

    async def _extract_article(
        self, page, article_url: str, section_name: str
    ) -> Optional[dict]:
        try:
            await page.goto(article_url, wait_until="domcontentloaded")

            title = await self._get_text(page, "h1.title, h1")
            if not title:
                logger.warning(
                    "[HinduScraper] No title found for %s, skipping", article_url
                )
                return None
            # Normalize title: collapse whitespace/newlines to single space
            title = ' '.join(title.split())
            # Filter Premium articles (The Hindu marks subscriber-only content)
            if 'premium' in title.lower():
                logger.debug(
                    "[HinduScraper] Filtered premium title: %s", article_url
                )
                return None

            author = await self._get_text(
                page, ".author-name, .person-name, .auth-nm a, .auth-nm"
            )
            published_date = await self._get_text(
                page, ".publish-time, time, .update-publish"
            )
            content = await self._get_text(
                page, "div.articlebodycontent, div.article-body, article"
            )

            return {
                "title": title.strip(),
                "url": article_url,
                "content": (content or "").strip(),
                "published_date": (published_date or "").strip() or None,
                "author": (author or "").strip() or None,
                "section": section_name,
                "source_site": "hindu",
            }

        except Exception as exc:
            logger.warning(
                "[HinduScraper] Failed to extract article %s: %s",
                article_url,
                str(exc),
            )
            return None

    async def _get_text(self, page, selector: str) -> Optional[str]:
        el = await page.query_selector(selector)
        if el:
            return await el.inner_text()
        return None
