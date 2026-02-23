"""
Tests for Indian Express web scraper.
TDD-first: tests written before implementation.

All tests use mocked HTTP responses — NO real network calls.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.ie_scraper import IndianExpressScraper


# ============================================================================
# FIXTURE HTML: Realistic Indian Express section page HTML
# ============================================================================

EXPLAINED_SECTION_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>Explained News - Indian Express</title></head>
<body>
<div class="nation">
  <div class="articles">
    <div class="northeast-topbox">
      <div class="title">
        <h2><a href="https://indianexpress.com/article/explained/explained-economics/rbi-rate-cut-impact-12345678/">
          Explained: What the RBI rate cut means for your EMIs and the economy
        </a></h2>
      </div>
      <div class="date">February 22, 2026 10:30:15 AM</div>
      <div class="byline">
        <span class="author">By <a href="https://indianexpress.com/profile/author/anand-kumar/">Anand Kumar</a></span>
      </div>
    </div>

    <div class="northeast-topbox">
      <div class="title">
        <h2><a href="https://indianexpress.com/article/explained/explained-sci-tech/chandrayaan-4-mission-explained-12345679/">
          Chandrayaan-4: What is ISRO's next lunar mission about?
        </a></h2>
      </div>
      <div class="date">February 21, 2026 05:45:00 PM</div>
      <div class="byline">
        <span class="author">By <a href="https://indianexpress.com/profile/author/amitabh-sinha/">Amitabh Sinha</a></span>
      </div>
    </div>

    <div class="northeast-topbox">
      <div class="title">
        <h2><a href="https://indianexpress.com/article/explained/everyday-explainers/what-is-inflation-targeting-12345680/">
          What is inflation targeting and why does it matter?
        </a></h2>
      </div>
      <div class="date">February 20, 2026 08:00:00 AM</div>
    </div>
  </div>
</div>
</body>
</html>
"""

EDITORIAL_SECTION_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>Editorials - Indian Express</title></head>
<body>
<div class="nation">
  <div class="articles">
    <div class="northeast-topbox">
      <div class="title">
        <h2><a href="https://indianexpress.com/article/opinion/editorials/india-budget-reform-agenda-12345681/">
          The reform agenda: Budget must focus on structural changes
        </a></h2>
      </div>
      <div class="date">February 22, 2026 12:00:00 AM</div>
      <div class="byline">
        <span class="author">By <a href="https://indianexpress.com/profile/author/the-editorial-board/">The Editorial Board</a></span>
      </div>
    </div>

    <div class="northeast-topbox">
      <div class="title">
        <h2><a href="https://indianexpress.com/article/opinion/editorials/supreme-court-verdict-federalism-12345682/">
          On the Court's verdict: Strengthening federalism
        </a></h2>
      </div>
      <div class="date">February 21, 2026 12:00:00 AM</div>
    </div>
  </div>
</div>
</body>
</html>
"""

UPSC_CA_SECTION_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>UPSC Current Affairs - Indian Express</title></head>
<body>
<div class="nation">
  <div class="articles">
    <div class="northeast-topbox">
      <div class="title">
        <h2><a href="https://indianexpress.com/article/upsc-current-affairs/upsc-key-february-22-2026-12345683/">
          UPSC Key — February 22, 2026: RBI Policy, Chandrayaan-4, and More
        </a></h2>
      </div>
      <div class="date">February 22, 2026 07:00:00 AM</div>
      <div class="byline">
        <span class="author">By <a href="https://indianexpress.com/profile/author/upsc-team/">UPSC Team</a></span>
      </div>
    </div>
  </div>
</div>
</body>
</html>
"""

# Edge case: section with no articles
EMPTY_SECTION_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>Empty Section</title></head>
<body>
<div class="nation">
  <div class="articles">
  </div>
</div>
</body>
</html>
"""

# Edge case: malformed article (missing href)
MALFORMED_ARTICLE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>Malformed</title></head>
<body>
<div class="nation">
  <div class="articles">
    <div class="northeast-topbox">
      <div class="title">
        <h2><a>Article with missing href</a></h2>
      </div>
    </div>
    <div class="northeast-topbox">
      <div class="title">
        <h2><a href="https://indianexpress.com/article/explained/valid-article-12345684/">
          Valid article after malformed one
        </a></h2>
      </div>
      <div class="date">February 22, 2026 09:00:00 AM</div>
    </div>
  </div>
</div>
</body>
</html>
"""

# Alternative HTML structure: articles using div.articles > div > h2.title pattern
ALTERNATIVE_STRUCTURE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head><title>Alternative Structure</title></head>
<body>
<div class="nation">
  <div class="articles">
    <div class="northeast-topbox">
      <h2 class="title"><a href="https://indianexpress.com/article/explained/alt-structure-article-12345685/">
        Article with h2.title class pattern
      </a></h2>
      <p class="date">February 22, 2026</p>
      <p class="byline">By <a>Some Author</a></p>
    </div>
  </div>
</div>
</body>
</html>
"""


# ============================================================================
# Helper to create mock httpx response
# ============================================================================


def _make_mock_response(html: str, status_code: int = 200):
    """Create a mock httpx.Response-like object."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.text = html
    mock_resp.raise_for_status = MagicMock()
    if status_code >= 400:
        import httpx

        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=mock_resp
        )
    return mock_resp


# ============================================================================
# TESTS: Scraper initialization and configuration
# ============================================================================


class TestScraperInit:
    """Test scraper initialization and configuration."""

    def test_scraper_creates_successfully(self):
        scraper = IndianExpressScraper()
        assert scraper is not None

    def test_scraper_has_correct_sections(self):
        scraper = IndianExpressScraper()
        section_keys = list(scraper.SECTIONS.keys())
        assert "explained" in section_keys
        assert "editorials" in section_keys
        assert "upsc-current-affairs" in section_keys
        assert len(section_keys) == 3

    def test_scraper_has_correct_section_urls(self):
        scraper = IndianExpressScraper()
        assert (
            scraper.SECTIONS["explained"]
            == "https://indianexpress.com/section/explained/"
        )
        assert (
            scraper.SECTIONS["editorials"]
            == "https://indianexpress.com/section/opinion/editorials/"
        )
        assert (
            scraper.SECTIONS["upsc-current-affairs"]
            == "https://indianexpress.com/section/upsc-current-affairs/"
        )

    def test_scraper_has_user_agents(self):
        scraper = IndianExpressScraper()
        assert len(scraper.USER_AGENTS) > 0
        for ua in scraper.USER_AGENTS:
            assert "Mozilla/5.0" in ua

    def test_scraper_has_rate_limit_delay(self):
        scraper = IndianExpressScraper()
        assert hasattr(scraper, "rate_limit_delay")
        assert scraper.rate_limit_delay >= 1.0


# ============================================================================
# TESTS: Single section scraping
# ============================================================================


class TestScrapeSection:
    """Test scraping a single section page."""

    @pytest.mark.asyncio
    async def test_scrape_explained_section(self):
        """Should parse 3 articles from explained section HTML."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(EXPLAINED_SECTION_HTML)

            articles = await scraper.scrape_section("explained")

        assert len(articles) == 3
        # Verify first article
        assert "RBI rate cut" in articles[0]["title"]
        assert (
            articles[0]["url"]
            == "https://indianexpress.com/article/explained/explained-economics/rbi-rate-cut-impact-12345678/"
        )
        assert articles[0]["section"] == "explained"
        assert articles[0]["source_site"] == "indianexpress"
        assert articles[0]["author"] == "Anand Kumar"

    @pytest.mark.asyncio
    async def test_scrape_editorial_section(self):
        """Should parse 2 articles from editorial section HTML."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(EDITORIAL_SECTION_HTML)

            articles = await scraper.scrape_section("editorials")

        assert len(articles) == 2
        assert "reform agenda" in articles[0]["title"]
        assert articles[0]["section"] == "editorials"
        assert articles[0]["source_site"] == "indianexpress"

    @pytest.mark.asyncio
    async def test_scrape_upsc_ca_section(self):
        """Should parse 1 article from UPSC current affairs section HTML."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(UPSC_CA_SECTION_HTML)

            articles = await scraper.scrape_section("upsc-current-affairs")

        assert len(articles) == 1
        assert "UPSC Key" in articles[0]["title"]
        assert articles[0]["section"] == "upsc-current-affairs"
        assert articles[0]["author"] == "UPSC Team"


# ============================================================================
# TESTS: Article dict structure
# ============================================================================


class TestArticleDictStructure:
    """Test that article dicts have all required keys with correct types."""

    @pytest.mark.asyncio
    async def test_article_has_required_keys(self):
        """Every article dict must have: title, url, published_date, author, section, source_site."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(EXPLAINED_SECTION_HTML)

            articles = await scraper.scrape_section("explained")

        required_keys = {
            "title",
            "url",
            "published_date",
            "author",
            "section",
            "source_site",
        }
        for article in articles:
            assert set(article.keys()) >= required_keys, (
                f"Article missing keys: {required_keys - set(article.keys())}"
            )

    @pytest.mark.asyncio
    async def test_article_field_types(self):
        """Verify types: title=str, url=str, published_date=str|None, author=str|None, section=str, source_site=str."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(EXPLAINED_SECTION_HTML)

            articles = await scraper.scrape_section("explained")

        for article in articles:
            assert isinstance(article["title"], str)
            assert isinstance(article["url"], str)
            assert article["published_date"] is None or isinstance(
                article["published_date"], str
            )
            assert article["author"] is None or isinstance(article["author"], str)
            assert isinstance(article["section"], str)
            assert isinstance(article["source_site"], str)

    @pytest.mark.asyncio
    async def test_source_site_is_always_indianexpress(self):
        """source_site must always be 'indianexpress'."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(EXPLAINED_SECTION_HTML)

            articles = await scraper.scrape_section("explained")

        for article in articles:
            assert article["source_site"] == "indianexpress"

    @pytest.mark.asyncio
    async def test_article_title_is_stripped(self):
        """Titles must be stripped of extra whitespace."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(EXPLAINED_SECTION_HTML)

            articles = await scraper.scrape_section("explained")

        for article in articles:
            assert article["title"] == article["title"].strip()
            assert "\n" not in article["title"]

    @pytest.mark.asyncio
    async def test_article_without_author_returns_none(self):
        """Articles without author info should have author=None."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(EXPLAINED_SECTION_HTML)

            articles = await scraper.scrape_section("explained")

        # Third article in fixture has no author
        third_article = articles[2]
        assert third_article["author"] is None

    @pytest.mark.asyncio
    async def test_urls_are_absolute(self):
        """All URLs should be absolute (start with https://)."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(EXPLAINED_SECTION_HTML)

            articles = await scraper.scrape_section("explained")

        for article in articles:
            assert article["url"].startswith("https://"), (
                f"URL not absolute: {article['url']}"
            )


# ============================================================================
# TESTS: Error handling
# ============================================================================


class TestErrorHandling:
    """Test graceful error handling."""

    @pytest.mark.asyncio
    async def test_http_error_returns_empty_list(self):
        """HTTP 403/500 errors should return empty list, not raise."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response("", status_code=403)

            articles = await scraper.scrape_section("explained")

        assert articles == []

    @pytest.mark.asyncio
    async def test_connection_error_returns_empty_list(self):
        """Network errors should return empty list, not raise."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = Exception("Connection refused")

            articles = await scraper.scrape_section("explained")

        assert articles == []

    @pytest.mark.asyncio
    async def test_empty_section_returns_empty_list(self):
        """Section page with no articles should return empty list."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(EMPTY_SECTION_HTML)

            articles = await scraper.scrape_section("explained")

        assert articles == []

    @pytest.mark.asyncio
    async def test_malformed_article_is_skipped_valid_articles_kept(self):
        """Malformed articles (missing href) should be skipped; valid ones kept."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(MALFORMED_ARTICLE_HTML)

            articles = await scraper.scrape_section("explained")

        # Only the valid article should be returned
        assert len(articles) == 1
        assert "Valid article" in articles[0]["title"]

    @pytest.mark.asyncio
    async def test_invalid_section_name_returns_empty_list(self):
        """Requesting an unknown section should return empty list."""
        scraper = IndianExpressScraper()
        articles = await scraper.scrape_section("nonexistent-section")
        assert articles == []


# ============================================================================
# TESTS: Scrape all sections
# ============================================================================


class TestScrapeAllSections:
    """Test scraping all 3 sections together."""

    @pytest.mark.asyncio
    async def test_scrape_all_returns_articles_from_all_sections(self):
        """scrape_all_sections() should return articles from all 3 sections."""
        scraper = IndianExpressScraper()

        section_html_map = {
            "https://indianexpress.com/section/explained/": EXPLAINED_SECTION_HTML,
            "https://indianexpress.com/section/opinion/editorials/": EDITORIAL_SECTION_HTML,
            "https://indianexpress.com/section/upsc-current-affairs/": UPSC_CA_SECTION_HTML,
        }

        async def mock_get(url, **kwargs):
            html = section_html_map.get(url, EMPTY_SECTION_HTML)
            return _make_mock_response(html)

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = mock_get

            # Patch sleep to speed up tests
            with patch("app.services.ie_scraper.asyncio.sleep", new_callable=AsyncMock):
                articles = await scraper.scrape_all_sections()

        # 3 explained + 2 editorial + 1 upsc-ca = 6
        assert len(articles) == 6

        # Verify sections are represented
        sections_found = set(a["section"] for a in articles)
        assert "explained" in sections_found
        assert "editorials" in sections_found
        assert "upsc-current-affairs" in sections_found

    @pytest.mark.asyncio
    async def test_scrape_all_continues_when_one_section_fails(self):
        """If one section fails, other sections should still be scraped."""
        scraper = IndianExpressScraper()

        call_count = 0

        async def mock_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if "explained" in url:
                raise Exception("Cloudflare blocked")
            elif "editorials" in url:
                return _make_mock_response(EDITORIAL_SECTION_HTML)
            else:
                return _make_mock_response(UPSC_CA_SECTION_HTML)

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.side_effect = mock_get

            with patch("app.services.ie_scraper.asyncio.sleep", new_callable=AsyncMock):
                articles = await scraper.scrape_all_sections()

        # 2 editorial + 1 upsc-ca = 3 (explained failed)
        assert len(articles) == 3
        sections_found = set(a["section"] for a in articles)
        assert "explained" not in sections_found
        assert "editorials" in sections_found
        assert "upsc-current-affairs" in sections_found


# ============================================================================
# TESTS: Rate limiting
# ============================================================================


class TestRateLimiting:
    """Test that rate limiting is applied between section requests."""

    @pytest.mark.asyncio
    async def test_sleep_called_between_sections(self):
        """asyncio.sleep should be called between section scrapes for rate limiting."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(EMPTY_SECTION_HTML)

            with patch(
                "app.services.ie_scraper.asyncio.sleep", new_callable=AsyncMock
            ) as mock_sleep:
                await scraper.scrape_all_sections()

            # Sleep should be called between sections (at least 2 times for 3 sections)
            assert mock_sleep.call_count >= 2
            # Each sleep should be at least 1.0 seconds
            for call in mock_sleep.call_args_list:
                delay = call[0][0]
                assert delay >= 1.0, f"Rate limit delay too short: {delay}s"


# ============================================================================
# TESTS: User-Agent rotation
# ============================================================================


class TestUserAgentRotation:
    """Test that User-Agent headers are realistic browser strings."""

    @pytest.mark.asyncio
    async def test_request_uses_browser_user_agent(self):
        """HTTP requests must include a realistic browser User-Agent."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(EXPLAINED_SECTION_HTML)

            await scraper.scrape_section("explained")

        # Verify headers were passed
        call_args = mock_client.get.call_args
        headers = call_args.kwargs.get("headers", {})
        assert "User-Agent" in headers
        assert "Mozilla/5.0" in headers["User-Agent"]


# ============================================================================
# TESTS: Alternative HTML structure handling
# ============================================================================


class TestAlternativeHTMLStructure:
    """Test that scraper handles alternative HTML patterns on IE pages."""

    @pytest.mark.asyncio
    async def test_h2_title_class_pattern(self):
        """Should handle <h2 class='title'><a>...</a></h2> pattern."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(
                ALTERNATIVE_STRUCTURE_HTML
            )

            articles = await scraper.scrape_section("explained")

        assert len(articles) >= 1
        assert "Article with h2.title class pattern" in articles[0]["title"]


# ============================================================================
# TESTS: Date parsing
# ============================================================================


class TestDateParsing:
    """Test date extraction and parsing."""

    @pytest.mark.asyncio
    async def test_date_parsed_from_section(self):
        """Dates should be extracted when present."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(EXPLAINED_SECTION_HTML)

            articles = await scraper.scrape_section("explained")

        # First article has a date
        assert articles[0]["published_date"] is not None
        # Should be ISO format string or parseable date string
        assert isinstance(articles[0]["published_date"], str)

    @pytest.mark.asyncio
    async def test_missing_date_returns_none(self):
        """Articles without date should have published_date=None."""
        scraper = IndianExpressScraper()

        # Use malformed HTML which has an article without date
        no_date_html = """
        <div class="nation"><div class="articles">
          <div class="northeast-topbox">
            <div class="title">
              <h2><a href="https://indianexpress.com/article/test/no-date-article-123/">No date article</a></h2>
            </div>
          </div>
        </div></div>
        """

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(no_date_html)

            articles = await scraper.scrape_section("explained")

        assert len(articles) == 1
        assert articles[0]["published_date"] is None


# ============================================================================
# TESTS: No article body content (metadata only)
# ============================================================================


class TestMetadataOnly:
    """Verify scraper does NOT fetch article body content."""

    @pytest.mark.asyncio
    async def test_article_dict_has_no_content_key(self):
        """Article dicts should NOT have 'content' or 'body' keys — body extraction is content_extractor.py's job."""
        scraper = IndianExpressScraper()

        with patch("app.services.ie_scraper.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(
                return_value=mock_client
            )
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.get.return_value = _make_mock_response(EXPLAINED_SECTION_HTML)

            articles = await scraper.scrape_section("explained")

        for article in articles:
            assert "content" not in article, (
                "Scraper should NOT extract article body content"
            )
            assert "body" not in article, "Scraper should NOT extract article body"
