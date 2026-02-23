"""
Tests for HinduPlaywrightScraper — The Hindu editorial/opinion Playwright scraper.

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
    mock_page.url = "https://www.thehindu.com/opinion/editorial/"

    # query_selector_all returns a list of mock article link elements
    mock_article_el = AsyncMock()
    mock_article_el.get_attribute = AsyncMock(
        return_value="https://www.thehindu.com/opinion/editorial/sample-article/article12345.ece"
    )
    mock_page.query_selector_all = AsyncMock(return_value=[mock_article_el])

    # Article page extraction mocks
    mock_title_el = AsyncMock()
    mock_title_el.inner_text = AsyncMock(return_value="Sample Editorial Title")
    mock_page.query_selector = AsyncMock(return_value=mock_title_el)
    mock_page.inner_text = AsyncMock(
        return_value="Full body text of the editorial article."
    )

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
    """Verify HinduPlaywrightScraper importable and has expected API."""

    def test_class_exists(self):
        """HinduPlaywrightScraper is importable from app.services.hindu_playwright_scraper."""
        from app.services.hindu_playwright_scraper import HinduPlaywrightScraper

        assert HinduPlaywrightScraper is not None

    def test_scrape_editorials_method_exists(self):
        """Class has async method scrape_editorials()."""
        from app.services.hindu_playwright_scraper import HinduPlaywrightScraper

        mgr = AsyncMock()
        scraper = HinduPlaywrightScraper(mgr)
        assert hasattr(scraper, "scrape_editorials")
        assert callable(scraper.scrape_editorials)


# ============================================================================
# TEST: Return structure
# ============================================================================


class TestReturnStructure:
    """Verify scrape_editorials returns correct structure."""

    async def test_returns_list_of_dicts(self, mock_session_manager):
        """scrape_editorials returns a list of dicts."""
        from app.services.hindu_playwright_scraper import HinduPlaywrightScraper

        scraper = HinduPlaywrightScraper(mock_session_manager)
        result = await scraper.scrape_editorials()

        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, dict)

    async def test_all_required_keys_present(self, mock_session_manager):
        """Each dict has: title, url, content, published_date, author, section, source_site."""
        from app.services.hindu_playwright_scraper import HinduPlaywrightScraper

        scraper = HinduPlaywrightScraper(mock_session_manager)
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

    async def test_source_site_is_always_hindu(self, mock_session_manager):
        """Every article dict has source_site == 'hindu'."""
        from app.services.hindu_playwright_scraper import HinduPlaywrightScraper

        scraper = HinduPlaywrightScraper(mock_session_manager)
        result = await scraper.scrape_editorials()

        assert len(result) > 0
        for article in result:
            assert article["source_site"] == "hindu"

    async def test_section_values_are_valid(self, mock_session_manager):
        """section must be one of {'editorial', 'lead', 'opinion'} for every article."""
        from app.services.hindu_playwright_scraper import HinduPlaywrightScraper

        scraper = HinduPlaywrightScraper(mock_session_manager)
        result = await scraper.scrape_editorials()

        valid_sections = {"editorial", "lead", "opinion"}
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

    async def test_calls_get_page_with_hindu(self, mock_session_manager):
        """Mock verifies session_manager.get_page('hindu') is called."""
        from app.services.hindu_playwright_scraper import HinduPlaywrightScraper

        scraper = HinduPlaywrightScraper(mock_session_manager)
        await scraper.scrape_editorials()

        mock_session_manager.get_page.assert_called_with("hindu")


# ============================================================================
# TEST: Error handling
# ============================================================================


class TestErrorHandling:
    """Verify graceful degradation on errors."""

    async def test_graceful_on_playwright_timeout(self, mock_session_manager):
        """When page.goto raises TimeoutError, returns [] and logs error."""
        from app.services.hindu_playwright_scraper import HinduPlaywrightScraper

        # Make page.goto raise a TimeoutError (playwright-style)
        mock_page = mock_session_manager._mock_page
        mock_page.goto.side_effect = TimeoutError("Timeout 30000ms exceeded")

        scraper = HinduPlaywrightScraper(mock_session_manager)

        with patch("app.services.hindu_playwright_scraper.logger") as mock_logger:
            result = await scraper.scrape_editorials()

            assert result == []
            mock_logger.error.assert_called()


# ============================================================================
# TEST: Deduplication
# ============================================================================


class TestDeduplication:
    """Verify URL-based deduplication."""

    async def test_deduplication(self, mock_session_manager):
        """Same URL appearing twice in DOM → only one article returned."""
        from app.services.hindu_playwright_scraper import HinduPlaywrightScraper

        duplicate_url = (
            "https://www.thehindu.com/opinion/editorial/same-article/article99999.ece"
        )

        # Two elements with the same URL
        el1 = _make_article_element(duplicate_url)
        el2 = _make_article_element(duplicate_url)

        mock_page = mock_session_manager._mock_page
        mock_page.query_selector_all = AsyncMock(return_value=[el1, el2])

        scraper = HinduPlaywrightScraper(mock_session_manager)
        result = await scraper.scrape_editorials()

        # Count how many articles have this URL
        matching = [a for a in result if a["url"] == duplicate_url]
        assert len(matching) <= 1, f"Duplicate URL found {len(matching)} times"
