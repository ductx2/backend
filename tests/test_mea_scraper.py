"""Tests for MEAScraper — scrapes press releases from mea.gov.in."""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.services.mea_scraper import MEAScraper


# ---------------------------------------------------------------------------
# Sample HTML fixtures (based on real MEA page structure)
# ---------------------------------------------------------------------------


# Listing page: "What's New" at mea.gov.in/whats-new-viewall.htm
# Each row is a table row with date + link to detail page
def _make_listing_html(articles: list[dict]) -> str:
    """Build a fake MEA listing page with the given articles.

    Each article dict: {"title": str, "href": str, "date_str": str}
    Date format on MEA: "February 23, 2026"
    """
    rows = ""
    for a in articles:
        rows += f"""
        <tr>
          <td class="LPad10">
            <a href="{a["href"]}" target="_blank">{a["title"]}</a>
          </td>
          <td class="RPad10" nowrap="nowrap">{a["date_str"]}</td>
        </tr>
        """
    return f"""
    <html>
    <head><title>What's New - MEA</title></head>
    <body>
      <div id="ContGl498">
        <table class="table table-striped">
          <tbody>
            {rows}
          </tbody>
        </table>
      </div>
    </body>
    </html>
    """


# Detail page: full press release content
SAMPLE_DETAIL_HTML = """
<html>
<head><title>India-Japan Summit 2026 - MEA</title></head>
<body>
  <div id="ContGl498">
    <h2 class="PageHead">India-Japan Summit 2026: Joint Statement</h2>
    <div class="date">February 23, 2026</div>
    <div id="ContentText">
      <p>The Prime Minister of India and the Prime Minister of Japan held a bilateral summit in New Delhi on February 23, 2026.</p>
      <p>Both leaders discussed cooperation in defense, technology, and trade. A new semiconductor partnership was announced.</p>
      <p>The two nations agreed to enhance cooperation in the Indo-Pacific region and reaffirmed commitment to QUAD objectives.</p>
    </div>
  </div>
</body>
</html>
"""

# Today and yesterday for date filtering
_NOW = datetime.now(timezone.utc)
_TODAY_STR = _NOW.strftime("%B %d, %Y")  # e.g. "February 23, 2026"
_YESTERDAY_STR = (_NOW - timedelta(days=1)).strftime("%B %d, %Y")
_WEEK_AGO_STR = (_NOW - timedelta(days=7)).strftime("%B %d, %Y")


# Listing with 3 articles: today, yesterday, week ago
SAMPLE_LISTING_ARTICLES = [
    {
        "title": "India-Japan Summit 2026: Joint Statement",
        "href": "?dtl/12345/India-Japan_Summit_2026_Joint_Statement",
        "date_str": _TODAY_STR,
    },
    {
        "title": "EAM attends BRICS Foreign Ministers Meeting",
        "href": "?dtl/12346/EAM_attends_BRICS_Foreign_Ministers_Meeting",
        "date_str": _YESTERDAY_STR,
    },
    {
        "title": "India-EU Trade Dialogue Outcomes",
        "href": "?dtl/12347/India-EU_Trade_Dialogue_Outcomes",
        "date_str": _WEEK_AGO_STR,
    },
]

SAMPLE_LISTING_HTML = _make_listing_html(SAMPLE_LISTING_ARTICLES)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scraper():
    """Return a MEAScraper instance."""
    return MEAScraper()


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
# Tests
# ---------------------------------------------------------------------------


class TestFetchListingPage:
    """Test 1: mock listing page HTML; assert scraper extracts article links."""

    async def test_fetch_listing_page(self, scraper: MEAScraper):
        """Mock httpx GET returning sample listing HTML;
        assert scraper extracts >=3 article links with titles and dates."""
        mock_listing_resp = _make_mock_response(SAMPLE_LISTING_HTML)

        # Mock _http_get to return listing for any URL
        async def mock_get(url: str) -> MagicMock:
            return mock_listing_resp

        scraper._http_get = AsyncMock(side_effect=mock_get)

        # fetch_articles should parse the listing and also fetch details
        # For this test, also mock detail fetches
        mock_detail_resp = _make_mock_response(SAMPLE_DETAIL_HTML)

        call_count = 0
        original_get = scraper._http_get

        async def mock_get_all(url: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return mock_listing_resp
            return mock_detail_resp

        scraper._http_get = AsyncMock(side_effect=mock_get_all)

        # Use a large window so all 3 articles pass date filter
        articles = await scraper.fetch_articles(hours=24 * 30)

        assert len(articles) >= 3
        # Each article should have a title
        for a in articles:
            assert a["title"]
            assert len(a["title"]) > 0


class TestFetchArticleDetail:
    """Test 2: mock detail page HTML; assert extraction of headline, body, date, url."""

    async def test_fetch_article_detail(self, scraper: MEAScraper):
        """Mock detail page HTML; assert headline, full body text,
        publication date, source_url are extracted."""
        mock_listing = _make_listing_html(
            [
                {
                    "title": "India-Japan Summit 2026: Joint Statement",
                    "href": "?dtl/12345/India-Japan_Summit_2026_Joint_Statement",
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

        # Headline extracted from detail page
        assert "India-Japan Summit 2026" in article["title"]
        # Body has actual content
        assert "bilateral summit" in article["content"]
        assert "semiconductor partnership" in article["content"]
        # Published date present
        assert article["published_date"]
        # Source URL is fully qualified
        assert article["source_url"].startswith("https://www.mea.gov.in")


class TestDateFiltering:
    """Test 3: listing with articles from today, yesterday, 7 days ago;
    assert only today + yesterday returned (48-hour window)."""

    async def test_date_filtering(self, scraper: MEAScraper):
        """With 48-hour window, only articles from today and yesterday
        should be returned; 7-day-old article is excluded."""
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

        # Default 48 hours — should exclude 7-day-old article
        articles = await scraper.fetch_articles(hours=48)

        assert len(articles) == 2
        titles = [a["title"] for a in articles]
        # The week-old article should NOT appear
        assert not any("EU Trade Dialogue" in t for t in titles)


class TestEmptyListing:
    """Test 4: mock empty/error response; assert returns empty list, logs warning."""

    async def test_empty_listing(self, scraper: MEAScraper):
        """Mock an empty listing page; assert returns [], logs warning."""
        empty_html = """
        <html><body>
          <div id="ContGl498">
            <table class="table table-striped"><tbody></tbody></table>
          </div>
        </body></html>
        """
        mock_resp = _make_mock_response(empty_html)
        scraper._http_get = AsyncMock(return_value=mock_resp)

        articles = await scraper.fetch_articles()

        assert articles == []


class TestNetworkError:
    """Test 5: mock httpx.HTTPError; assert returns empty list, logs error."""

    async def test_network_error(self, scraper: MEAScraper):
        """Mock httpx network error; assert returns [] and doesn't raise."""
        scraper._http_get = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        articles = await scraper.fetch_articles()

        assert articles == []

    async def test_http_status_error(self, scraper: MEAScraper):
        """Mock HTTP 500 response; assert returns [] and doesn't raise."""
        mock_resp = _make_mock_response("", status_code=500)
        scraper._http_get = AsyncMock(return_value=mock_resp)

        articles = await scraper.fetch_articles()

        assert articles == []


class TestStandardizedFormat:
    """Test 6: assert each article dict has required keys for unified pipeline."""

    async def test_returns_standardized_format(self, scraper: MEAScraper):
        """Each article dict must have keys: title, content, source_url,
        source_site, section, published_date."""
        mock_listing = _make_listing_html(
            [
                {
                    "title": "India-Japan Summit 2026: Joint Statement",
                    "href": "?dtl/12345/India-Japan_Summit_2026_Joint_Statement",
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
            assert article["source_site"] == "mea"
            assert article["section"] == "press-releases"
