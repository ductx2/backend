"""Tests for PIBScraper — scrapes press releases from pib.gov.in."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.services.pib_scraper import PIBScraper


# ---------------------------------------------------------------------------
# Sample HTML fixtures (based on real PIB page structure)
# ---------------------------------------------------------------------------

# Minimal page with __VIEWSTATE and form fields (initial GET response)
SAMPLE_INITIAL_PAGE = """
<html>
<head><title>All Press Release</title></head>
<body>
<form method="post" action="./allRel.aspx?reg=3&amp;lang=1">
  <input type="hidden" name="__VIEWSTATE" value="FAKE_VIEWSTATE_VALUE" />
  <input type="hidden" name="__VIEWSTATEGENERATOR" value="CBED066B" />
  <input type="hidden" name="__EVENTVALIDATION" value="FAKE_EVENTVALIDATION" />
  <input type="hidden" name="__EVENTTARGET" value="" />
  <input type="hidden" name="__EVENTARGUMENT" value="" />
  <input type="hidden" name="__LASTFOCUS" value="" />
  <input type="hidden" name="__VIEWSTATEENCRYPTED" value="" />
  <input type="hidden" name="ctl00$ContentPlaceHolder1$hydregionid" value="3" />
  <input type="hidden" name="ctl00$ContentPlaceHolder1$hydLangid" value="1" />
  <select name="ctl00$ContentPlaceHolder1$ddlMinistry">
    <option value="0" selected="selected">All Ministry</option>
    <option value="15">Ministry of Finance</option>
    <option value="4">Ministry of External Affairs</option>
  </select>
  <select name="ctl00$ContentPlaceHolder1$ddlday">
    <option value="22" selected="selected">22</option>
  </select>
  <select name="ctl00$ContentPlaceHolder1$ddlMonth">
    <option value="2" selected="selected">February</option>
  </select>
  <select name="ctl00$ContentPlaceHolder1$ddlYear">
    <option value="2026" selected="selected">2026</option>
  </select>
  <div class="search_box_result">Displaying  0 Press Releases</div>
  <div class="content-area">***No Release Found***</div>
</form>
</body>
</html>
"""

# Page with press releases (POST response)
SAMPLE_RESULTS_PAGE = """
<html>
<head><title>All Press Release</title></head>
<body>
<form method="post" action="./allRel.aspx?reg=3&amp;lang=1">
  <input type="hidden" name="__VIEWSTATE" value="NEW_VIEWSTATE_VALUE" />
  <input type="hidden" name="__VIEWSTATEGENERATOR" value="CBED066B" />
  <input type="hidden" name="__EVENTVALIDATION" value="NEW_EVENTVALIDATION" />
  <input type="hidden" name="__EVENTTARGET" value="" />
  <input type="hidden" name="__EVENTARGUMENT" value="" />
  <input type="hidden" name="__LASTFOCUS" value="" />
  <input type="hidden" name="__VIEWSTATEENCRYPTED" value="" />
  <input type="hidden" name="ctl00$ContentPlaceHolder1$hydregionid" value="3" />
  <input type="hidden" name="ctl00$ContentPlaceHolder1$hydLangid" value="1" />
  <div class="search_box_result">Displaying  3 Press Releases</div>
  <div class="content-area">
    <ul><li><h3 class="font104">Ministry of Finance</h3><ul class="num">
      <li><a title="FM announces new fiscal policy measures" href="/PressReleasePage.aspx?PRID=2231001&amp;reg=3&amp;lang=1" target="_blank">FM announces new fiscal policy measures</a></li>
      <li><a title="GST revenue collection for January 2026" href="/PressReleasePage.aspx?PRID=2231002&amp;reg=3&amp;lang=1" target="_blank">GST revenue collection for January 2026</a></li>
    </ul></li></ul>
    <ul><li><h3 class="font104">Ministry of External Affairs</h3><ul class="num">
      <li><a title="India-Brazil bilateral talks conclude" href="/PressReleasePage.aspx?PRID=2231003&amp;reg=3&amp;lang=1" target="_blank">India-Brazil bilateral talks conclude</a></li>
    </ul></li></ul>
  </div>
</form>
</body>
</html>
"""

# Page with no results
SAMPLE_EMPTY_PAGE = """
<html>
<head><title>All Press Release</title></head>
<body>
<form method="post" action="./allRel.aspx?reg=3&amp;lang=1">
  <input type="hidden" name="__VIEWSTATE" value="FAKE_VIEWSTATE" />
  <input type="hidden" name="__VIEWSTATEGENERATOR" value="CBED066B" />
  <input type="hidden" name="__EVENTVALIDATION" value="FAKE_EVENTVALIDATION" />
  <input type="hidden" name="__EVENTTARGET" value="" />
  <input type="hidden" name="__EVENTARGUMENT" value="" />
  <input type="hidden" name="__LASTFOCUS" value="" />
  <input type="hidden" name="__VIEWSTATEENCRYPTED" value="" />
  <div class="search_box_result">Displaying  0 Press Releases</div>
  <div class="content-area">***No Release Found***</div>
</form>
</body>
</html>
"""

# Page with mixed ministries (some UPSC-relevant, some not)
SAMPLE_MIXED_PAGE = """
<html>
<head><title>All Press Release</title></head>
<body>
<form method="post" action="./allRel.aspx?reg=3&amp;lang=1">
  <input type="hidden" name="__VIEWSTATE" value="FAKE_VIEWSTATE" />
  <input type="hidden" name="__VIEWSTATEGENERATOR" value="CBED066B" />
  <input type="hidden" name="__EVENTVALIDATION" value="FAKE_EVENTVALIDATION" />
  <input type="hidden" name="__EVENTTARGET" value="" />
  <input type="hidden" name="__EVENTARGUMENT" value="" />
  <input type="hidden" name="__LASTFOCUS" value="" />
  <input type="hidden" name="__VIEWSTATEENCRYPTED" value="" />
  <div class="search_box_result">Displaying  4 Press Releases</div>
  <div class="content-area">
    <ul><li><h3 class="font104">Ministry of Finance</h3><ul class="num">
      <li><a title="Budget 2026 highlights" href="/PressReleasePage.aspx?PRID=2230001&amp;reg=3&amp;lang=1" target="_blank">Budget 2026 highlights</a></li>
    </ul></li></ul>
    <ul><li><h3 class="font104">Ministry of Textiles</h3><ul class="num">
      <li><a title="Textile export data Q3" href="/PressReleasePage.aspx?PRID=2230002&amp;reg=3&amp;lang=1" target="_blank">Textile export data Q3</a></li>
    </ul></li></ul>
    <ul><li><h3 class="font104">NITI Aayog</h3><ul class="num">
      <li><a title="NITI Aayog releases SDG Index 2026" href="/PressReleasePage.aspx?PRID=2230003&amp;reg=3&amp;lang=1" target="_blank">NITI Aayog releases SDG Index 2026</a></li>
    </ul></li></ul>
    <ul><li><h3 class="font104">Ministry of Tourism</h3><ul class="num">
      <li><a title="Tourism sector growth stats" href="/PressReleasePage.aspx?PRID=2230004&amp;reg=3&amp;lang=1" target="_blank">Tourism sector growth stats</a></li>
    </ul></li></ul>
  </div>
</form>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def scraper():
    """Return a PIBScraper instance with default config."""
    return PIBScraper()


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
# Tests: HTML parsing
# ---------------------------------------------------------------------------


class TestParseReleasesHTML:
    """Tests for _parse_releases_html — extracts articles from response HTML."""

    def test_parse_results_page(self, scraper: PIBScraper):
        """Should extract all press releases grouped by ministry."""
        articles = scraper._parse_releases_html(SAMPLE_RESULTS_PAGE, target_date=date(2026, 2, 22))
        assert len(articles) == 3

        # Check first article
        assert articles[0]["title"] == "FM announces new fiscal policy measures"
        assert articles[0]["ministry"] == "Ministry of Finance"
        assert articles[0]["source_site"] == "pib"
        assert "PRID=2231001" in articles[0]["url"]
        assert articles[0]["published_date"] == "2026-02-22"

    def test_parse_empty_page(self, scraper: PIBScraper):
        """Should return empty list when no releases found."""
        articles = scraper._parse_releases_html(SAMPLE_EMPTY_PAGE, target_date=date(2026, 2, 22))
        assert articles == []

    def test_parse_extracts_url_correctly(self, scraper: PIBScraper):
        """URLs should be fully qualified with https://pib.gov.in prefix."""
        articles = scraper._parse_releases_html(SAMPLE_RESULTS_PAGE, target_date=date(2026, 2, 22))
        for article in articles:
            assert article["url"].startswith("https://pib.gov.in/")
            assert "PRID=" in article["url"]

    def test_parse_extracts_ministry_names(self, scraper: PIBScraper):
        """Each article should have the ministry from its group heading."""
        articles = scraper._parse_releases_html(SAMPLE_RESULTS_PAGE, target_date=date(2026, 2, 22))
        ministries = [a["ministry"] for a in articles]
        assert "Ministry of Finance" in ministries
        assert "Ministry of External Affairs" in ministries

    def test_parse_all_articles_have_required_fields(self, scraper: PIBScraper):
        """Every article dict must have title, url, published_date, ministry, source_site."""
        articles = scraper._parse_releases_html(SAMPLE_RESULTS_PAGE, target_date=date(2026, 2, 22))
        required_keys = {"title", "url", "published_date", "ministry", "source_site"}
        for article in articles:
            assert required_keys.issubset(article.keys()), f"Missing keys: {required_keys - article.keys()}"

    def test_parse_malformed_html_returns_empty(self, scraper: PIBScraper):
        """Should gracefully handle malformed HTML."""
        articles = scraper._parse_releases_html("<html><body>garbage</body></html>", target_date=date(2026, 2, 22))
        assert articles == []


# ---------------------------------------------------------------------------
# Tests: ViewState extraction
# ---------------------------------------------------------------------------


class TestExtractFormFields:
    """Tests for _extract_form_fields — extracts ASP.NET hidden fields from HTML."""

    def test_extract_viewstate(self, scraper: PIBScraper):
        """Should extract __VIEWSTATE and __EVENTVALIDATION from the page."""
        fields = scraper._extract_form_fields(SAMPLE_INITIAL_PAGE)
        assert fields["__VIEWSTATE"] == "FAKE_VIEWSTATE_VALUE"
        assert fields["__EVENTVALIDATION"] == "FAKE_EVENTVALIDATION"
        assert fields["__VIEWSTATEGENERATOR"] == "CBED066B"

    def test_extract_empty_fields(self, scraper: PIBScraper):
        """Should handle pages without hidden fields gracefully."""
        fields = scraper._extract_form_fields("<html><body></body></html>")
        assert fields.get("__VIEWSTATE") is None or fields.get("__VIEWSTATE") == ""


# ---------------------------------------------------------------------------
# Tests: UPSC-relevant ministry filtering
# ---------------------------------------------------------------------------


class TestMinistryFiltering:
    """Tests for filtering press releases to UPSC-relevant ministries only."""

    def test_filter_upsc_relevant_only(self, scraper: PIBScraper):
        """When filter_upsc_relevant=True, only UPSC-relevant ministries are kept."""
        all_articles = scraper._parse_releases_html(SAMPLE_MIXED_PAGE, target_date=date(2026, 2, 22))
        filtered = scraper._filter_upsc_relevant(all_articles)

        # Finance and NITI Aayog are UPSC-relevant; Textiles and Tourism are not
        assert len(filtered) == 2
        ministries = {a["ministry"] for a in filtered}
        assert "Ministry of Finance" in ministries
        assert "NITI Aayog" in ministries
        assert "Ministry of Textiles" not in ministries
        assert "Ministry of Tourism" not in ministries

    def test_filter_returns_all_when_disabled(self, scraper: PIBScraper):
        """When no filter is applied, all articles are returned."""
        all_articles = scraper._parse_releases_html(SAMPLE_MIXED_PAGE, target_date=date(2026, 2, 22))
        # Without filtering, all 4 should be present
        assert len(all_articles) == 4

    def test_upsc_relevant_ministries_list(self, scraper: PIBScraper):
        """Verify the UPSC-relevant ministries list includes core ministries."""
        relevant = scraper.UPSC_RELEVANT_MINISTRIES
        assert "Ministry of Finance" in relevant
        assert "Ministry of External Affairs" in relevant
        assert "Ministry of Home Affairs" in relevant
        assert "Ministry of Education" in relevant
        assert "NITI Aayog" in relevant
        assert "Ministry of Defence" in relevant


# ---------------------------------------------------------------------------
# Tests: Full scrape flow (mocked HTTP)
# ---------------------------------------------------------------------------


class TestScrapeReleases:
    """Tests for scrape_releases — full async flow with mocked HTTP calls."""

    @pytest.mark.asyncio
    async def test_scrape_success(self, scraper: PIBScraper):
        """Should GET the page, POST with form data, and parse the results."""
        mock_get_response = _make_mock_response(SAMPLE_INITIAL_PAGE)
        mock_post_response = _make_mock_response(SAMPLE_RESULTS_PAGE)

        with patch.object(scraper, "_http_get", new_callable=AsyncMock, return_value=mock_get_response):
            with patch.object(scraper, "_http_post", new_callable=AsyncMock, return_value=mock_post_response):
                articles = await scraper.scrape_releases(
                    target_date=date(2026, 2, 22),
                    filter_upsc_relevant=False,
                )

        assert len(articles) == 3
        assert articles[0]["source_site"] == "pib"

    @pytest.mark.asyncio
    async def test_scrape_with_ministry_filter(self, scraper: PIBScraper):
        """Should filter to only UPSC-relevant ministries when requested."""
        mock_get_response = _make_mock_response(SAMPLE_INITIAL_PAGE)
        mock_post_response = _make_mock_response(SAMPLE_MIXED_PAGE)

        with patch.object(scraper, "_http_get", new_callable=AsyncMock, return_value=mock_get_response):
            with patch.object(scraper, "_http_post", new_callable=AsyncMock, return_value=mock_post_response):
                articles = await scraper.scrape_releases(
                    target_date=date(2026, 2, 22),
                    filter_upsc_relevant=True,
                )

        # Only Finance and NITI Aayog from the mixed page
        assert len(articles) == 2
        ministries = {a["ministry"] for a in articles}
        assert "Ministry of Finance" in ministries
        assert "NITI Aayog" in ministries

    @pytest.mark.asyncio
    async def test_scrape_empty_results(self, scraper: PIBScraper):
        """Should return empty list when PIB has no releases for the date."""
        mock_get_response = _make_mock_response(SAMPLE_INITIAL_PAGE)
        mock_post_response = _make_mock_response(SAMPLE_EMPTY_PAGE)

        with patch.object(scraper, "_http_get", new_callable=AsyncMock, return_value=mock_get_response):
            with patch.object(scraper, "_http_post", new_callable=AsyncMock, return_value=mock_post_response):
                articles = await scraper.scrape_releases(
                    target_date=date(2026, 2, 22),
                    filter_upsc_relevant=False,
                )

        assert articles == []

    @pytest.mark.asyncio
    async def test_scrape_http_error_on_get(self, scraper: PIBScraper):
        """Should return empty list and log error on GET failure."""
        mock_get_response = _make_mock_response("", status_code=500)

        with patch.object(scraper, "_http_get", new_callable=AsyncMock, return_value=mock_get_response):
            articles = await scraper.scrape_releases(
                target_date=date(2026, 2, 22),
            )

        assert articles == []

    @pytest.mark.asyncio
    async def test_scrape_http_error_on_post(self, scraper: PIBScraper):
        """Should return empty list and log error on POST failure."""
        mock_get_response = _make_mock_response(SAMPLE_INITIAL_PAGE)
        mock_post_response = _make_mock_response("", status_code=500)

        with patch.object(scraper, "_http_get", new_callable=AsyncMock, return_value=mock_get_response):
            with patch.object(scraper, "_http_post", new_callable=AsyncMock, return_value=mock_post_response):
                articles = await scraper.scrape_releases(
                    target_date=date(2026, 2, 22),
                )

        assert articles == []

    @pytest.mark.asyncio
    async def test_scrape_network_exception(self, scraper: PIBScraper):
        """Should handle network exceptions gracefully."""
        with patch.object(
            scraper, "_http_get", new_callable=AsyncMock,
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            articles = await scraper.scrape_releases(
                target_date=date(2026, 2, 22),
            )

        assert articles == []

    @pytest.mark.asyncio
    async def test_scrape_builds_correct_form_data(self, scraper: PIBScraper):
        """POST should include ViewState + correct date fields."""
        mock_get_response = _make_mock_response(SAMPLE_INITIAL_PAGE)
        mock_post_response = _make_mock_response(SAMPLE_RESULTS_PAGE)

        mock_post = AsyncMock(return_value=mock_post_response)

        with patch.object(scraper, "_http_get", new_callable=AsyncMock, return_value=mock_get_response):
            with patch.object(scraper, "_http_post", mock_post):
                await scraper.scrape_releases(
                    target_date=date(2026, 2, 22),
                    filter_upsc_relevant=False,
                )

        # Verify _http_post was called with correct form data
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        form_data = call_args[1].get("data") or call_args[0][1]

        assert form_data["__VIEWSTATE"] == "FAKE_VIEWSTATE_VALUE"
        assert form_data["__EVENTVALIDATION"] == "FAKE_EVENTVALIDATION"
        assert form_data["ctl00$ContentPlaceHolder1$ddlday"] == "22"
        assert form_data["ctl00$ContentPlaceHolder1$ddlMonth"] == "2"
        assert form_data["ctl00$ContentPlaceHolder1$ddlYear"] == "2026"

    @pytest.mark.asyncio
    async def test_scrape_defaults_to_today(self, scraper: PIBScraper):
        """When no target_date is provided, should use today's date."""
        mock_get_response = _make_mock_response(SAMPLE_INITIAL_PAGE)
        mock_post_response = _make_mock_response(SAMPLE_EMPTY_PAGE)
        mock_post = AsyncMock(return_value=mock_post_response)

        today = date.today()

        with patch.object(scraper, "_http_get", new_callable=AsyncMock, return_value=mock_get_response):
            with patch.object(scraper, "_http_post", mock_post):
                await scraper.scrape_releases()

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        form_data = call_args[1].get("data") or call_args[0][1]

        assert form_data["ctl00$ContentPlaceHolder1$ddlday"] == str(today.day)
        assert form_data["ctl00$ContentPlaceHolder1$ddlMonth"] == str(today.month)
        assert form_data["ctl00$ContentPlaceHolder1$ddlYear"] == str(today.year)