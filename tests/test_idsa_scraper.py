"""Tests for IDSAScraper — scrapes comment briefs from idsa.in."""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.idsa_scraper import IDSAScraper


# ---------------------------------------------------------------------------
# Sample HTML fixtures (based on real IDSA page structure)
# ---------------------------------------------------------------------------


def _make_listing_html(articles: list[dict]) -> str:
    """Build a fake IDSA listing page with the given articles.

    Each article dict: {"title": str, "href": str, "date_str": str}
    Date format on IDSA: "23 Feb, 2026" or "February 23, 2026"
    """
    items = ""
    for a in articles:
        items += f"""
        <div class="views-row">
          <div class="views-field-title">
            <span class="field-content">
              <a href="{a["href"]}">{a["title"]}</a>
            </span>
          </div>
          <div class="views-field-created">
            <span class="field-content">{a["date_str"]}</span>
          </div>
        </div>
        """
    return f"""
    <html>
    <head><title>Comment Briefs - IDSA</title></head>
    <body>
      <div class="view-content">
        {items}
      </div>
    </body>
    </html>
    """


# Detail page: full article content
SAMPLE_DETAIL_HTML = """
<html>
<head><title>India's Arctic Policy: Strategic Imperatives - IDSA</title></head>
<body>
  <div class="field-items">
    <div class="field-item even">
      <h1 class="page-header">India's Arctic Policy: Strategic Imperatives</h1>
      <p>India's increasing engagement with the Arctic region reflects its evolving strategic vision
      and growing interest in resource security, scientific research, and global governance.</p>
      <p>The Arctic Council membership and bilateral ties with Norway and Iceland form the
      cornerstone of India's Arctic diplomacy. The National Centre for Polar and Ocean Research
      coordinates scientific expeditions to the region.</p>
      <p>Given rapid ice melt and emerging shipping routes, India must develop a comprehensive
      policy framework addressing both economic opportunities and security challenges.</p>
    </div>
  </div>
</body>
</html>
"""

# Today, yesterday, and a week ago
_NOW = datetime.now(timezone.utc)
_TODAY_STR = _NOW.strftime("%d %b, %Y")  # e.g. "23 Feb, 2026"
_YESTERDAY_STR = (_NOW - timedelta(days=1)).strftime("%d %b, %Y")
_WEEK_AGO_STR = (_NOW - timedelta(days=7)).strftime("%d %b, %Y")

SAMPLE_LISTING_ARTICLES = [
    {
        "title": "India's Arctic Policy: Strategic Imperatives",
        "href": "/comment/indias-arctic-policy-strategic-imperatives",
        "date_str": _TODAY_STR,
    },
    {
        "title": "China's Military Modernisation: Implications for India",
        "href": "/comment/chinas-military-modernisation-implications-india",
        "date_str": _YESTERDAY_STR,
    },
    {
        "title": "Nuclear Deterrence in South Asia: Revisiting Stability",
        "href": "/comment/nuclear-deterrence-south-asia-revisiting-stability",
        "date_str": _WEEK_AGO_STR,
    },
]

SAMPLE_LISTING_HTML = _make_listing_html(SAMPLE_LISTING_ARTICLES)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scraper():
    """Return an IDSAScraper instance."""
    return IDSAScraper()


def _make_mock_response(html: str, status_code: int = 200) -> MagicMock:
    """Create a mock httpx.Response with the given HTML body."""
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.text = html
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            message=f"{status_code} Error",
            request=MagicMock(),
            response=resp,
        )
    return resp


# ---------------------------------------------------------------------------
# Test 1: fetch listing page extracts ≥3 article links
# ---------------------------------------------------------------------------


class TestFetchListingPage:
    """Test 1: mock listing page HTML; assert scraper extracts >=3 article links."""

    async def test_fetch_listing_page(self, scraper: IDSAScraper):
        """Mock httpx GET returning sample listing HTML with 3 articles;
        assert scraper extracts >= 3 article links."""
        mock_listing_resp = _make_mock_response(SAMPLE_LISTING_HTML)
        mock_detail_resp = _make_mock_response(SAMPLE_DETAIL_HTML)

        call_count = 0

        async def mock_get(url: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_listing_resp
            return mock_detail_resp

        scraper._http_get = AsyncMock(side_effect=mock_get)

        # Large window so all 3 articles pass date filter
        articles = await scraper.fetch_articles(hours=24 * 30)

        assert len(articles) >= 3
        for a in articles:
            assert a["title"]
            assert len(a["title"]) > 0


# ---------------------------------------------------------------------------
# Test 2: fetch article detail extracts headline + full body text
# ---------------------------------------------------------------------------


class TestFetchArticleDetail:
    """Test 2: mock detail page HTML; assert full article text extracted."""

    async def test_fetch_article_detail(self, scraper: IDSAScraper):
        """Mock a single-article listing + detail page;
        assert headline and full body content are extracted."""
        mock_listing = _make_listing_html(
            [
                {
                    "title": "India's Arctic Policy: Strategic Imperatives",
                    "href": "/comment/indias-arctic-policy-strategic-imperatives",
                    "date_str": _TODAY_STR,
                }
            ]
        )
        mock_listing_resp = _make_mock_response(mock_listing)
        mock_detail_resp = _make_mock_response(SAMPLE_DETAIL_HTML)

        call_count = 0

        async def mock_get(url: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_listing_resp
            return mock_detail_resp

        scraper._http_get = AsyncMock(side_effect=mock_get)

        articles = await scraper.fetch_articles(hours=24 * 30)

        assert len(articles) >= 1
        article = articles[0]

        # Headline present
        assert "Arctic" in article["title"]
        # Body has actual content from detail page
        assert "Arctic" in article["content"]
        # Published date present
        assert article["published_date"]
        # Source URL is fully qualified
        assert article["source_url"].startswith("https://idsa.in")


# ---------------------------------------------------------------------------
# Test 3: date filtering — only 48h window returned
# ---------------------------------------------------------------------------


class TestDateFiltering:
    """Test 3: listing with articles spanning 7 days; only 48h window returned."""

    async def test_date_filtering(self, scraper: IDSAScraper):
        """Listing has today + yesterday + 7-days-ago articles.
        48-hour window must exclude the week-old article."""
        mock_listing_resp = _make_mock_response(SAMPLE_LISTING_HTML)
        mock_detail_resp = _make_mock_response(SAMPLE_DETAIL_HTML)

        call_count = 0

        async def mock_get(url: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_listing_resp
            return mock_detail_resp

        scraper._http_get = AsyncMock(side_effect=mock_get)

        articles = await scraper.fetch_articles(hours=48)

        assert len(articles) == 2
        titles = [a["title"] for a in articles]
        # The week-old article should NOT appear
        assert not any("Nuclear Deterrence" in t for t in titles)


# ---------------------------------------------------------------------------
# Test 4: network error — returns [], logs error
# ---------------------------------------------------------------------------


class TestNetworkError:
    """Test 4: mock httpx.HTTPError; assert returns [], logs error."""

    async def test_network_error(self, scraper: IDSAScraper):
        """Mock httpx.ConnectError; assert returns [] and doesn't raise."""
        scraper._http_get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        articles = await scraper.fetch_articles()

        assert articles == []

    async def test_http_status_error(self, scraper: IDSAScraper):
        """Mock HTTP 500 response; assert returns [] and doesn't raise."""
        mock_resp = _make_mock_response("", status_code=500)
        scraper._http_get = AsyncMock(return_value=mock_resp)

        articles = await scraper.fetch_articles()

        assert articles == []


# ---------------------------------------------------------------------------
# Test 5: standardized format — all required keys present
# ---------------------------------------------------------------------------


class TestStandardizedFormat:
    """Test 5: each dict has: title, content, source_url, source_site='idsa',
    section='comment-briefs', published_date."""

    async def test_returns_standardized_format(self, scraper: IDSAScraper):
        """Each article dict must have all required keys for unified pipeline."""
        mock_listing = _make_listing_html(
            [
                {
                    "title": "India's Arctic Policy: Strategic Imperatives",
                    "href": "/comment/indias-arctic-policy-strategic-imperatives",
                    "date_str": _TODAY_STR,
                }
            ]
        )
        mock_listing_resp = _make_mock_response(mock_listing)
        mock_detail_resp = _make_mock_response(SAMPLE_DETAIL_HTML)

        call_count = 0

        async def mock_get(url: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_listing_resp
            return mock_detail_resp

        scraper._http_get = AsyncMock(side_effect=mock_get)

        articles = await scraper.fetch_articles(hours=24 * 30)

        assert len(articles) >= 1
        required_keys = {
            "title",
            "content",
            "source_url",
            "source_site",
            "section",
            "published_date",
        }
        for article in articles:
            assert required_keys.issubset(article.keys()), (
                f"Missing keys: {required_keys - article.keys()}"
            )
            assert article["source_site"] == "idsa"
            assert article["section"] == "comment-briefs"


# ---------------------------------------------------------------------------
# Bonus Test 6: PDF links skipped — PDF URL ignored, HTML articles returned
# ---------------------------------------------------------------------------


class TestPDFSkip:
    """Test 6: listing HTML with a .pdf link mixed in;
    assert PDF link skipped, HTML articles returned normally."""

    async def test_pdf_skip(self, scraper: IDSAScraper):
        """Listing contains one PDF link and two HTML article links.
        PDF must be skipped; both HTML articles must be in results."""
        listing_with_pdf_html = _make_listing_html(
            [
                {
                    "title": "IDSA Annual Report 2025 (PDF)",
                    "href": "/sites/default/files/IDSA_Annual_Report_2025.pdf",
                    "date_str": _TODAY_STR,
                },
                {
                    "title": "India's Arctic Policy: Strategic Imperatives",
                    "href": "/comment/indias-arctic-policy-strategic-imperatives",
                    "date_str": _TODAY_STR,
                },
                {
                    "title": "China's Military Modernisation: Implications for India",
                    "href": "/comment/chinas-military-modernisation-implications-india",
                    "date_str": _TODAY_STR,
                },
            ]
        )
        mock_listing_resp = _make_mock_response(listing_with_pdf_html)
        mock_detail_resp = _make_mock_response(SAMPLE_DETAIL_HTML)

        call_count = 0

        async def mock_get(url: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_listing_resp
            return mock_detail_resp

        scraper._http_get = AsyncMock(side_effect=mock_get)

        articles = await scraper.fetch_articles(hours=24 * 30)

        # PDF skipped — only 2 HTML articles returned
        assert len(articles) == 2
        urls = [a["source_url"] for a in articles]
        # No PDF URL in results
        assert not any(u.lower().endswith(".pdf") for u in urls)
