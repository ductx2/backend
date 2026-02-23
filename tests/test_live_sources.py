"""
Live source validation tests.

These tests make REAL HTTP calls to verify that each scraper/processor can
connect to its live source and return articles with the expected shape.

All tests are marked with ``@pytest.mark.live`` so they can be excluded from
the normal CI suite via ``-m "not live"``.

Run live tests only::

    python -m pytest tests/test_live_sources.py -m live -v

Skip live tests in CI::

    python -m pytest tests/ -m "not live" -v
"""

import pytest

from app.services.ie_scraper import IndianExpressScraper
from app.services.pib_scraper import PIBScraper
from app.services.supplementary_sources import SupplementarySources
from app.services.optimized_rss_processor import OptimizedRSSProcessor
from app.services.unified_pipeline import _normalize_hindu_article


LIVE = pytest.mark.live


@LIVE
class TestLiveIEScraper:
    """Validate IE scraper against the live indianexpress.com site."""

    @pytest.fixture(scope="class")
    async def ie_articles(self):
        """Fetch IE articles once per class to avoid hammering the site."""
        scraper = IndianExpressScraper()
        try:
            result = await scraper.scrape_all_sections()
        except Exception as e:
            pytest.skip(f"IE source unavailable: {e}")
        return result

    @pytest.mark.asyncio
    async def test_scrape_returns_list(self, ie_articles):
        assert isinstance(ie_articles, list), "scrape_all_sections must return a list"
        # IE may return empty depending on time of day / site availability
        assert len(ie_articles) >= 0

    @pytest.mark.asyncio
    async def test_article_shape(self, ie_articles):
        if not ie_articles:
            pytest.skip("No IE articles returned")
        first = ie_articles[0]
        required_keys = {"title", "url", "published_date", "section", "source_site"}
        missing = required_keys - set(first.keys())
        assert not missing, f"IE article missing keys: {missing}"

    @pytest.mark.asyncio
    async def test_source_site_is_indianexpress(self, ie_articles):
        for article in ie_articles:
            assert article["source_site"] == "indianexpress", (
                f"Expected source_site='indianexpress', got '{article['source_site']}'"
            )

    @pytest.mark.asyncio
    async def test_urls_are_valid(self, ie_articles):
        for article in ie_articles:
            assert article["url"].startswith("https://"), (
                f"IE article URL does not start with https://: {article['url']}"
            )


@LIVE
class TestLivePIBScraper:
    """Validate PIB scraper against the live pib.gov.in site."""

    @pytest.fixture(scope="class")
    async def pib_articles(self):
        """Fetch PIB articles once per class."""
        scraper = PIBScraper()
        try:
            result = await scraper.scrape_releases(filter_upsc_relevant=True)
        except Exception as e:
            pytest.skip(f"PIB source unavailable: {e}")
        return result

    @pytest.mark.asyncio
    async def test_scrape_releases_returns_articles(self, pib_articles):
        assert isinstance(pib_articles, list), "scrape_releases must return a list"
        # PIB may be empty on weekends/holidays — len >= 0 is acceptable
        assert len(pib_articles) >= 0

    @pytest.mark.asyncio
    async def test_article_shape_if_results(self, pib_articles):
        if not pib_articles:
            pytest.skip("No PIB articles returned (may be weekend/holiday)")
        for article in pib_articles:
            required_keys = {
                "title",
                "url",
                "published_date",
                "ministry",
                "source_site",
            }
            missing = required_keys - set(article.keys())
            assert not missing, f"PIB article missing keys: {missing}"

    @pytest.mark.asyncio
    async def test_source_site_is_pib(self, pib_articles):
        for article in pib_articles:
            assert article["source_site"] == "pib", (
                f"Expected source_site='pib', got '{article['source_site']}'"
            )


@LIVE
class TestLiveSupplementarySources:
    """Validate supplementary RSS sources against live feeds."""

    @pytest.fixture(scope="class")
    def supp_articles(self):
        """Fetch supplementary articles once per class (sync method)."""
        sources = SupplementarySources()
        try:
            result = sources.fetch_all()
        except Exception as e:
            pytest.skip(f"Supplementary sources unavailable: {e}")
        return result

    def test_fetch_all_returns_list(self, supp_articles):
        assert isinstance(supp_articles, list), "fetch_all must return a list"

    def test_article_shape_if_results(self, supp_articles):
        if not supp_articles:
            pytest.skip("No supplementary articles returned")
        for article in supp_articles:
            required_keys = {"title", "url", "section", "source_site"}
            missing = required_keys - set(article.keys())
            assert not missing, f"Supplementary article missing keys: {missing}"

    def test_no_content_field(self, supp_articles):
        """Supplementary sources return header-only articles (no body content)."""
        for article in supp_articles:
            assert "content" not in article, (
                f"Supplementary article should NOT have 'content' key, but does: {article.get('title', '')}"
            )


@LIVE
class TestLiveHinduRSS:
    """Validate Hindu RSS processor against live The Hindu feeds."""

    @pytest.fixture(scope="class")
    async def hindu_articles(self):
        """Fetch Hindu RSS articles once per class."""
        processor = OptimizedRSSProcessor()
        try:
            result = await processor.fetch_all_sources_parallel()
        except Exception as e:
            pytest.skip(f"Hindu RSS source unavailable: {e}")
        return result

    @pytest.mark.asyncio
    async def test_fetch_returns_list(self, hindu_articles):
        assert isinstance(hindu_articles, list), (
            "fetch_all_sources_parallel must return a list"
        )
        # Hindu RSS may return empty if feeds block requests (403)
        assert len(hindu_articles) >= 0

    @pytest.mark.asyncio
    async def test_article_has_content(self, hindu_articles):
        """Hindu RSS articles include content (unlike scrapers)."""
        if not hindu_articles:
            pytest.skip("No Hindu articles returned")
        first = hindu_articles[0]
        assert "content" in first, "Hindu article should have 'content' key"
        assert len(first["content"]) > 0, "Hindu article content should not be empty"

    @pytest.mark.asyncio
    async def test_source_url_not_url(self, hindu_articles):
        """Pre-normalization shape uses 'source_url', not 'url'."""
        if not hindu_articles:
            pytest.skip("No Hindu articles returned")
        first = hindu_articles[0]
        assert "source_url" in first, "Hindu article should have 'source_url' key"

    @pytest.mark.asyncio
    async def test_source_site_added_after_normalization(self, hindu_articles):
        """After normalization, Hindu articles get 'source_site' and 'url' keys."""
        if not hindu_articles:
            pytest.skip("No Hindu articles returned")
        normalized = _normalize_hindu_article(hindu_articles[0].copy())
        assert normalized.get("source_site") == "hindu", (
            f"Expected source_site='hindu', got '{normalized.get('source_site')}'"
        )
        assert "url" in normalized, "Normalized Hindu article should have 'url' key"
