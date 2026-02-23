"""Tests for ORFScraper — scrapes Expert Speak articles from orfonline.org.

ORF (Observer Research Foundation) is a server-rendered site (Laravel/PHP + Bootstrap).
Content is NOT loaded via XHR — it is rendered in HTML with Bootstrap pagination (?page=N).
Discovered via Playwright: no WordPress REST API, no Vue SPA, no RSS feed.
The scraper uses httpx + BeautifulSoup to parse paginated HTML.
"""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.orf_scraper import ORFScraper


# ---------------------------------------------------------------------------
# Sample HTML fixtures (based on real ORF page structure discovered via Playwright)
# ---------------------------------------------------------------------------

# Page with 3 expert-speak articles (mirrors real DOM structure)
SAMPLE_PAGE_WITH_ARTICLES = """
<html>
<head><title>Expert Speak | ORF</title></head>
<body>
<div class="wrapper">
  <div class="row">
    <div class="col-sm-3">
      <a href="https://www.orfonline.org/expert-speak/adult-immunisation-kerala">
        <img src="/img/1.jpg" alt="img">
      </a>
    </div>
    <div class="col-sm-9">
      <div class="topic_story">
        <span class="topic_link"><span class="color_blue"><a href="/topic/healthcare">Healthcare</a></span></span>
        <span class="color_blue date show_date">{date_today}</span>
        <a href="https://www.orfonline.org/expert-speak/adult-immunisation-kerala">
          Adult Immunisation: An Ambitious Beginning in Kerala
        </a>
        <p>Kerala, with the highest proportion of older adults, becomes the first state in India to mainstream adult immunisation.</p>
      </div>
    </div>
  </div>
  <div class="row">
    <div class="col-sm-3">
      <a href="https://www.orfonline.org/expert-speak/gandhian-ideals-urbanising-india">
        <img src="/img/2.jpg" alt="img">
      </a>
    </div>
    <div class="col-sm-9">
      <div class="topic_story">
        <span class="topic_link"><span class="color_blue"><a href="/topic/urbanisation">Urbanisation</a></span></span>
        <span class="color_blue date show_date">{date_today}</span>
        <a href="https://www.orfonline.org/expert-speak/gandhian-ideals-urbanising-india">
          The Waning Relevance of Gandhian Ideals in Urbanising India
        </a>
        <p>India's rapid urbanisation and modernisation are eroding Gandhian ideals.</p>
      </div>
    </div>
  </div>
  <div class="row">
    <div class="col-sm-3">
      <a href="https://www.orfonline.org/expert-speak/biotechnology-dual-use-dilemma">
        <img src="/img/3.jpg" alt="img">
      </a>
    </div>
    <div class="col-sm-9">
      <div class="topic_story">
        <span class="topic_link"><span class="color_blue"><a href="/topic/healthcare">Healthcare</a></span></span>
        <span class="color_blue date show_date">{date_yesterday}</span>
        <a href="https://www.orfonline.org/expert-speak/biotechnology-dual-use-dilemma">
          Governing Biotechnology's Dual-Use Security Dilemma
        </a>
        <p>Treating biotechnology as a strategic security asset deepens the dual-use dilemma.</p>
      </div>
    </div>
  </div>
  <ul class="pagination">
    <li class="page-item disabled"><span class="page-link">&laquo; Previous</span></li>
    <li class="page-item"><a class="page-link" href="https://www.orfonline.org/expert-speak?page=2">Next &raquo;</a></li>
  </ul>
</div>
</body>
</html>
"""

# Page with articles from different dates (for date filtering test)
SAMPLE_PAGE_MIXED_DATES = """
<html>
<body>
<div class="wrapper">
  <div class="row">
    <div class="col-sm-9">
      <div class="topic_story">
        <span class="color_blue date show_date">{date_today}</span>
        <a href="https://www.orfonline.org/expert-speak/article-today">Article Today</a>
        <p>Recent article content.</p>
      </div>
    </div>
  </div>
  <div class="row">
    <div class="col-sm-9">
      <div class="topic_story">
        <span class="color_blue date show_date">{date_3_days_ago}</span>
        <a href="https://www.orfonline.org/expert-speak/article-3-days">Article 3 Days Ago</a>
        <p>Older article content.</p>
      </div>
    </div>
  </div>
  <div class="row">
    <div class="col-sm-9">
      <div class="topic_story">
        <span class="color_blue date show_date">{date_7_days_ago}</span>
        <a href="https://www.orfonline.org/expert-speak/article-7-days">Article 7 Days Ago</a>
        <p>Very old article content.</p>
      </div>
    </div>
  </div>
</div>
</body>
</html>
"""

# Empty page (no articles)
SAMPLE_EMPTY_PAGE = """
<html>
<body>
<div class="wrapper">
  <div class="row">
    <div class="col-12 text-center">
      <p>No results found.</p>
    </div>
  </div>
</div>
</body>
</html>
"""

# Second page with 2 articles (for pagination test)
SAMPLE_PAGE_2 = """
<html>
<body>
<div class="wrapper">
  <div class="row">
    <div class="col-sm-9">
      <div class="topic_story">
        <span class="color_blue date show_date">{date_today}</span>
        <a href="https://www.orfonline.org/expert-speak/page2-article1">Page 2 Article 1</a>
        <p>Content from page 2.</p>
      </div>
    </div>
  </div>
  <div class="row">
    <div class="col-sm-9">
      <div class="topic_story">
        <span class="color_blue date show_date">{date_today}</span>
        <a href="https://www.orfonline.org/expert-speak/page2-article2">Page 2 Article 2</a>
        <p>More content from page 2.</p>
      </div>
    </div>
  </div>
  <ul class="pagination">
    <li class="page-item"><a class="page-link" href="https://www.orfonline.org/expert-speak?page=1">&laquo; Previous</a></li>
    <li class="page-item"><a class="page-link" href="https://www.orfonline.org/expert-speak?page=3">Next &raquo;</a></li>
  </ul>
</div>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_date(dt: datetime) -> str:
    """Format datetime to ORF date string (e.g. 'Feb 21, 2026')."""
    return dt.strftime("%b %d, %Y")


def _make_fixture_html(template: str) -> str:
    """Replace date placeholders in HTML template with real dates."""
    now = datetime.now(timezone.utc)
    return (
        template.replace("{date_today}", _format_date(now))
        .replace("{date_yesterday}", _format_date(now - timedelta(days=1)))
        .replace("{date_3_days_ago}", _format_date(now - timedelta(days=3)))
        .replace("{date_7_days_ago}", _format_date(now - timedelta(days=7)))
    )


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
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scraper():
    """Return an ORFScraper instance."""
    return ORFScraper()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAPIURLIsDocumented:
    """Test 1: ORFScraper.BASE_URL is a documented, non-empty https string."""

    def test_base_url_is_documented(self):
        assert isinstance(ORFScraper.BASE_URL, str)
        assert ORFScraper.BASE_URL.startswith("https://")
        assert len(ORFScraper.BASE_URL) > 10
        assert "orfonline.org" in ORFScraper.BASE_URL


class TestFetchArticlesFromHTML:
    """Test 2: Parse articles from server-rendered HTML response."""

    async def test_fetch_articles_returns_articles(self, scraper: ORFScraper):
        """Mock httpx GET returning HTML with article cards; assert ≥3 articles extracted."""
        html = _make_fixture_html(SAMPLE_PAGE_WITH_ARTICLES)
        mock_resp = _make_mock_response(html)

        with patch.object(
            scraper, "_http_get", new_callable=AsyncMock, return_value=mock_resp
        ):
            articles = await scraper.fetch_articles(hours=48)

        assert len(articles) >= 3
        for article in articles:
            assert article["title"]
            assert article["source_url"].startswith("https://")
            assert article["published_date"]


class TestPaginationHandling:
    """Test 3: Pagination — fetches multiple pages via ?page=N until no more articles."""

    async def test_pagination_fetches_multiple_pages(self, scraper: ORFScraper):
        """Mock page=1 with 3 articles + next link, page=2 with 2 articles, page=3 empty."""
        page1_html = _make_fixture_html(SAMPLE_PAGE_WITH_ARTICLES)
        page2_html = _make_fixture_html(SAMPLE_PAGE_2)
        page3_html = SAMPLE_EMPTY_PAGE

        call_count = 0

        async def mock_get(url: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            if "page=2" in url:
                return _make_mock_response(page2_html)
            elif "page=3" in url:
                return _make_mock_response(page3_html)
            else:
                return _make_mock_response(page1_html)

        with patch.object(scraper, "_http_get", side_effect=mock_get):
            articles = await scraper.fetch_articles(hours=9999)

        # 3 from page 1 + 2 from page 2 = 5 total
        assert len(articles) == 5
        # Should have fetched at least 2 pages (page 1 + page 2)
        assert call_count >= 2


class TestDateFiltering:
    """Test 4: Only articles within the specified hours window are returned."""

    async def test_date_filtering_48h(self, scraper: ORFScraper):
        """Provide articles spanning 7 days; assert only last 48h returned."""
        html = _make_fixture_html(SAMPLE_PAGE_MIXED_DATES)
        mock_resp = _make_mock_response(html)

        with patch.object(
            scraper, "_http_get", new_callable=AsyncMock, return_value=mock_resp
        ):
            articles = await scraper.fetch_articles(hours=48)

        # Only "Article Today" should pass 48h filter
        # "Article 3 Days Ago" and "Article 7 Days Ago" should be excluded
        assert len(articles) == 1
        assert articles[0]["title"] == "Article Today"


class TestContentFromHTML:
    """Test 5: Content (excerpt) field is populated from the HTML response."""

    async def test_content_populated(self, scraper: ORFScraper):
        """Assert content field is non-empty from parsed HTML excerpts."""
        html = _make_fixture_html(SAMPLE_PAGE_WITH_ARTICLES)
        mock_resp = _make_mock_response(html)

        with patch.object(
            scraper, "_http_get", new_callable=AsyncMock, return_value=mock_resp
        ):
            articles = await scraper.fetch_articles(hours=9999)

        assert len(articles) >= 1
        for article in articles:
            assert article.get("content"), f"Content empty for: {article['title']}"
            assert len(article["content"]) > 10


class TestAPIErrorResponse:
    """Test 6: HTTP errors return empty list and log error."""

    async def test_http_500_returns_empty(self, scraper: ORFScraper):
        """Mock 500 response; assert returns [], no exception raised."""
        mock_resp = _make_mock_response("", status_code=500)

        with patch.object(
            scraper, "_http_get", new_callable=AsyncMock, return_value=mock_resp
        ):
            articles = await scraper.fetch_articles(hours=48)

        assert articles == []

    async def test_http_404_returns_empty(self, scraper: ORFScraper):
        """Mock 404 response; assert returns []."""
        mock_resp = _make_mock_response("", status_code=404)

        with patch.object(
            scraper, "_http_get", new_callable=AsyncMock, return_value=mock_resp
        ):
            articles = await scraper.fetch_articles(hours=48)

        assert articles == []

    async def test_network_exception_returns_empty(self, scraper: ORFScraper):
        """Network exception returns [] gracefully."""
        with patch.object(
            scraper,
            "_http_get",
            new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            articles = await scraper.fetch_articles(hours=48)

        assert articles == []


class TestStandardizedFormat:
    """Test 7: Each article dict has standardized keys matching unified_pipeline format."""

    async def test_returns_standardized_format(self, scraper: ORFScraper):
        """Each dict must have: title, content, source_url, source_site='orf', section='expert-speak', published_date."""
        html = _make_fixture_html(SAMPLE_PAGE_WITH_ARTICLES)
        mock_resp = _make_mock_response(html)

        with patch.object(
            scraper, "_http_get", new_callable=AsyncMock, return_value=mock_resp
        ):
            articles = await scraper.fetch_articles(hours=9999)

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
            missing = required_keys - set(article.keys())
            assert not missing, (
                f"Missing keys {missing} in article: {article.get('title', '?')}"
            )
            assert article["source_site"] == "orf"
            assert article["section"] == "expert-speak"
            assert article["source_url"].startswith("https://")
            assert article["title"]
            assert article["published_date"]


class TestMaxPagesLimit:
    """Test 8 (bonus): Scraper respects MAX_PAGES limit to avoid runaway requests."""

    async def test_max_pages_respected(self, scraper: ORFScraper):
        """Even if every page has articles, stop after MAX_PAGES."""
        html = _make_fixture_html(SAMPLE_PAGE_WITH_ARTICLES)
        call_count = 0

        async def mock_get(url: str) -> MagicMock:
            nonlocal call_count
            call_count += 1
            return _make_mock_response(html)

        with patch.object(scraper, "_http_get", side_effect=mock_get):
            await scraper.fetch_articles(hours=9999)

        assert call_count <= ORFScraper.MAX_PAGES
