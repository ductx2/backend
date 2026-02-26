"""
The Hindu Multi-Section Playwright Scraper.

Scrapes all UPSC-relevant sections from The Hindu:
  - Opinion: editorial                      (GS All Papers — lead/op-ed are 100% paywalled)
  - National news                           (GS2 — Governance/Polity)
  - International news                      (GS2 — IR)
  - Economy                                 (GS3 — Economy)
  - Science & Technology                    (GS3 — S&T)
  - Environment                             (GS3 — Environment)

Requires PlaywrightSessionManager with a valid Hindu session.
"""

import asyncio
import logging
import re
from typing import List, Optional, Tuple

from app.services.playwright_session import PlaywrightSessionManager

logger = logging.getLogger(__name__)


class HinduPlaywrightScraper:
    # (section_name, listing_url, url_path_filter, max_articles)
    # url_path_filter: substring that must appear in the article href
    # max_articles: how many to scrape from that section per run
    SECTIONS: List[Tuple[str, str, str, int]] = [
        # Opinion / Analysis ─ highest UPSC value
        # NOTE: lead + op-ed removed — 100% paywalled (verified Feb 2026)
        ("editorial",     "https://www.thehindu.com/opinion/editorial/",                   "/opinion/editorial/",        10),
        # National news ─ GS2 Governance/Polity
        ("national",      "https://www.thehindu.com/news/national/",                       "/news/national/",            20),
        # International Relations ─ GS2 IR
        ("international", "https://www.thehindu.com/news/international/",                  "/news/international/",       15),
        # Economy ─ GS3
        ("economy",       "https://www.thehindu.com/business/Economy/",                    "/business/Economy/",         12),
        # Science & Technology ─ GS3
        ("sci_tech",      "https://www.thehindu.com/sci-tech/",                            "/sci-tech/",                 10),
        # Environment ─ GS3
        ("environment",   "https://www.thehindu.com/sci-tech/energy-and-environment/",     "/energy-and-environment/",    8),
    ]

    INTER_SECTION_DELAY = 1.5

    def __init__(self, session_manager: PlaywrightSessionManager) -> None:
        self.session_manager = session_manager

    async def scrape_editorials(self) -> List[dict]:
        """Scrape all configured sections. Name kept for pipeline compatibility."""
        all_articles: List[dict] = []
        seen_urls: set = set()

        for idx, (section_name, section_url, path_filter, max_articles) in enumerate(self.SECTIONS):
            if idx > 0:
                await asyncio.sleep(self.INTER_SECTION_DELAY)
            try:
                section_articles = await self._scrape_section(
                    section_name, section_url, path_filter, max_articles, seen_urls
                )
                all_articles.extend(section_articles)
                logger.info(
                    "[HinduScraper] %s: %d articles", section_name, len(section_articles)
                )
            except Exception as exc:
                logger.error(
                    "[HinduScraper] Section '%s' failed: %s", section_name, str(exc)
                )

        logger.info("[HinduScraper] Total articles scraped: %d", len(all_articles))
        return all_articles

    async def _scrape_section(
        self,
        section_name: str,
        section_url: str,
        path_filter: str,
        max_articles: int,
        seen_urls: set,
    ) -> List[dict]:
        articles: List[dict] = []

        try:
            page = await self.session_manager.get_page("hindu")
            await page.goto(section_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(1)

            # Extract .ece article links from raw HTML using regex.
            # This is more reliable than CSS selectors across all sections.
            html = await page.content()
            raw_links = re.findall(
                r'href="(https://www\.thehindu\.com/[^"]+\.ece)"', html
            )

            article_urls: List[str] = []
            for href in raw_links:
                if href in seen_urls:
                    continue
                if path_filter.lower() not in href.lower():
                    continue
                seen_urls.add(href)
                article_urls.append(href)
                if len(article_urls) >= max_articles:
                    break

            # DEBUG: log raw vs matching counts to diagnose zero-article sections
            matching = sum(1 for h in raw_links if path_filter.lower() in h.lower())
            logger.info(
                "[HinduScraper] %s: raw_ece=%d matching_filter=%d candidate_urls=%d",
                section_name, len(raw_links), matching, len(article_urls)
            )

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
            await page.goto(article_url, wait_until="domcontentloaded", timeout=30000)

            title = await self._get_text(page, "h1.title, h1")
            if not title:
                logger.warning(
                    "[HinduScraper] No title found for %s (page_url=%s), skipping",
                    article_url, page.url
                )
                return None
            # Normalize title: collapse whitespace/newlines
            title = " ".join(title.split())
            # Skip subscriber-only premium articles
            if "premium" in title.lower():
                logger.warning("[HinduScraper] Skipping premium title '%s': %s", title[:60], article_url)
                return None
            logger.debug("[HinduScraper] Title OK: '%s'", title[:60])

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
                "[HinduScraper] Failed to extract %s: %s", article_url, str(exc)
            )
            return None

    async def _get_text(self, page, selector: str) -> Optional[str]:
        el = await page.query_selector(selector)
        if el:
            return await el.inner_text()
        return None
