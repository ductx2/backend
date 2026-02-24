"""
Tests for IEPlaywrightScraper — Indian Express editorial Playwright scraper.

TDD-first: tests written before implementation.
All tests use mocked Playwright objects — NO real browser needed.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_session_manager():
    """Mock PlaywrightSessionManager with all async methods."""
    mgr = AsyncMock()
    mock_page = AsyncMock()

    # Default mock page behaviors
    mock_page.goto = AsyncMock(return_value=None)
    mock_page.wait_for_selector = AsyncMock(return_value=None)
    mock_page.close = AsyncMock(return_value=None)
    mock_page.url = "https://indianexpress.com/section/explained/"

    # query_selector_all returns a list of mock article link elements
    mock_article_el = AsyncMock()
    mock_article_el.get_attribute = AsyncMock(
        return_value="https://indianexpress.com/article/explained/sample-explained-article-12345/"
    )
    mock_page.query_selector_all = AsyncMock(return_value=[mock_article_el])

    # Article page extraction mocks
    mock_title_el = AsyncMock()
    mock_title_el.inner_text = AsyncMock(return_value="Sample IE Editorial Title")

    mock_content_el = AsyncMock()
    mock_content_el.inner_text = AsyncMock(
        return_value="A" * 250  # >= 200 chars for fulltext test
    )

    mock_author_el = AsyncMock()
    mock_author_el.inner_text = AsyncMock(return_value="IE Author Name")

    mock_date_el = AsyncMock()
    mock_date_el.inner_text = AsyncMock(return_value="February 23, 2026")

    def query_selector_side_effect(selector: str):
        """Return different mock elements depending on CSS selector."""
        if "h1" in selector:
            return mock_title_el
        if "author" in selector or "byline" in selector:
            return mock_author_el
        if "date" in selector or "time" in selector or "publish" in selector:
            return mock_date_el
        if "body" in selector or "article" in selector or "content" in selector:
            return mock_content_el
        return mock_title_el  # fallback

    mock_page.query_selector = AsyncMock(side_effect=query_selector_side_effect)

    mgr.get_page = AsyncMock(return_value=mock_page)
    mgr._mock_page = mock_page  # expose for test assertions

    return mgr


def _make_article_element(url: str) -> AsyncMock:
    """Helper: create a mock article link element with a given URL."""
    el = AsyncMock()
    el.get_attribute = AsyncMock(return_value=url)
    return el


# ============================================================================
# TEST: Class existence and API
# ============================================================================


class TestClassAPI:
    """Verify IEPlaywrightScraper importable and has expected API."""

    def test_class_exists(self):
        """IEPlaywrightScraper is importable from app.services.ie_playwright_scraper."""
        from app.services.ie_playwright_scraper import IEPlaywrightScraper

        assert IEPlaywrightScraper is not None

    def test_scrape_editorials_method_exists(self):
        """Class has async method scrape_editorials()."""
        from app.services.ie_playwright_scraper import IEPlaywrightScraper

        mgr = AsyncMock()
        scraper = IEPlaywrightScraper(mgr)
        assert hasattr(scraper, "scrape_editorials")
        assert callable(scraper.scrape_editorials)


# ============================================================================
# TEST: Return structure
# ============================================================================


class TestReturnStructure:
    """Verify scrape_editorials returns correct structure."""

    async def test_returns_list_of_dicts(self, mock_session_manager):
        """scrape_editorials returns a list of dicts."""
        from app.services.ie_playwright_scraper import IEPlaywrightScraper

        scraper = IEPlaywrightScraper(mock_session_manager)
        result = await scraper.scrape_editorials()

        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, dict)

    async def test_all_required_keys_present(self, mock_session_manager):
        """Each dict has: title, url, content, published_date, author, section, source_site."""
        from app.services.ie_playwright_scraper import IEPlaywrightScraper

        scraper = IEPlaywrightScraper(mock_session_manager)
        result = await scraper.scrape_editorials()

        required_keys = {
            "title",
            "url",
            "content",
            "published_date",
            "author",
            "section",
            "source_site",
        }
        assert len(result) > 0, "Expected at least one article from mocked scraper"
        for article in result:
            assert required_keys.issubset(article.keys()), (
                f"Missing keys: {required_keys - article.keys()}"
            )


# ============================================================================
# TEST: Field values
# ============================================================================


class TestFieldValues:
    """Verify field values are correct."""

    async def test_source_site_is_always_indianexpress(self, mock_session_manager):
        """Every article dict has source_site == 'indianexpress'."""
        from app.services.ie_playwright_scraper import IEPlaywrightScraper

        scraper = IEPlaywrightScraper(mock_session_manager)
        result = await scraper.scrape_editorials()

        assert len(result) > 0
        for article in result:
            assert article["source_site"] == "indianexpress"

    async def test_section_values_are_valid(self, mock_session_manager):
        """section must be one of {'explained', 'editorials', 'upsc-current-affairs'} for every article."""
        from app.services.ie_playwright_scraper import IEPlaywrightScraper

        scraper = IEPlaywrightScraper(mock_session_manager)
        result = await scraper.scrape_editorials()

        valid_sections = {"explained", "editorials", "upsc-current-affairs"}
        assert len(result) > 0
        for article in result:
            assert article["section"] in valid_sections, (
                f"Invalid section: {article['section']}"
            )


# ============================================================================
# TEST: Session manager interaction
# ============================================================================


class TestSessionManagerInteraction:
    """Verify correct calls to PlaywrightSessionManager."""

    async def test_calls_get_page_with_ie(self, mock_session_manager):
        """Mock verifies session_manager.get_page('ie') is called."""
        from app.services.ie_playwright_scraper import IEPlaywrightScraper

        scraper = IEPlaywrightScraper(mock_session_manager)
        await scraper.scrape_editorials()

        mock_session_manager.get_page.assert_called_with("ie")


# ============================================================================
# TEST: Full-text extraction
# ============================================================================


class TestFulltextExtraction:
    """Verify articles include full body content (not just summary)."""

    async def test_fulltext_extraction(self, mock_session_manager):
        """Each article has 'content' key with len >= 200 (full body, not just summary)."""
        from app.services.ie_playwright_scraper import IEPlaywrightScraper

        scraper = IEPlaywrightScraper(mock_session_manager)
        result = await scraper.scrape_editorials()

        assert len(result) > 0, "Expected at least one article"
        for article in result:
            assert "content" in article, "Article missing 'content' key"
            assert len(article["content"]) >= 200, (
                f"Content too short ({len(article['content'])} chars), expected >= 200"
            )


# ============================================================================
# TEST: Error handling
# ============================================================================


class TestErrorHandling:
    """Verify graceful degradation on errors."""

    async def test_graceful_on_runtime_error(self, mock_session_manager):
        """When session_manager.get_page() raises RuntimeError('Browser not initialized'),
        returns [] and logger.error called with 'Browser not initialized'."""
        from app.services.ie_playwright_scraper import IEPlaywrightScraper

        mock_session_manager.get_page.side_effect = RuntimeError(
            "Browser not initialized"
        )

        scraper = IEPlaywrightScraper(mock_session_manager)

        with patch("app.services.ie_playwright_scraper.logger") as mock_logger:
            result = await scraper.scrape_editorials()

            assert result == []
            mock_logger.error.assert_called()
            # Verify the error message contains the RuntimeError text
            call_args = mock_logger.error.call_args
            assert "Browser not initialized" in str(call_args)


# ============================================================================
# TEST: Deduplication
# ============================================================================


class TestDeduplication:
    """Verify URL-based deduplication."""

    async def test_deduplication(self, mock_session_manager):
        """Same URL appearing twice in DOM → only one article returned."""
        from app.services.ie_playwright_scraper import IEPlaywrightScraper

        duplicate_url = (
            "https://indianexpress.com/article/explained/same-article-99999/"
        )

        # Two elements with the same URL
        el1 = _make_article_element(duplicate_url)
        el2 = _make_article_element(duplicate_url)

        mock_page = mock_session_manager._mock_page
        mock_page.query_selector_all = AsyncMock(return_value=[el1, el2])

        scraper = IEPlaywrightScraper(mock_session_manager)
        result = await scraper.scrape_editorials()

        # Count how many articles have this URL
        matching = [a for a in result if a["url"] == duplicate_url]
        assert len(matching) <= 1, f"Duplicate URL found {len(matching)} times"
