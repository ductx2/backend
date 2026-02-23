"""
TDD tests for supplementary RSS sources: Down To Earth, Business Standard, PRS Legislative
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone


# ─────────────────────────────────────────────────────────────────────────────
# Helper: build a minimal feedparser-like entry mock
# ─────────────────────────────────────────────────────────────────────────────


def _make_entry(
    title: str,
    link: str,
    published_parsed=None,
    author: str | None = None,
    summary: str | None = None,
    tags=None,
):
    """Return a mock feedparser entry object."""
    entry = MagicMock()
    entry.title = title
    entry.link = link
    entry.published_parsed = published_parsed or (2026, 2, 23, 10, 0, 0, 0, 0, 0)
    entry.get.return_value = author  # used by get("author", None)
    entry.summary = summary or "Test summary content for article."
    entry.description = summary or "Test summary content for article."
    # feedparser tags is a list of dicts with 'term' key
    if tags is not None:
        entry.tags = [{'term': t, 'scheme': None, 'label': None} for t in tags]
    else:
        entry.tags = []
    return entry


def _make_feed(entries):
    """Return a mock feedparser parsed feed."""
    feed = MagicMock()
    feed.entries = entries
    return feed


# ─────────────────────────────────────────────────────────────────────────────
# Tests for module structure
# ─────────────────────────────────────────────────────────────────────────────


class TestModuleImports:
    """Ensure the module and its public API are importable."""

    def test_module_importable(self):
        from app.services.supplementary_sources import SupplementarySources  # noqa: F401

    def test_class_has_fetch_all_method(self):
        from app.services.supplementary_sources import SupplementarySources

        assert hasattr(SupplementarySources, "fetch_all")

    def test_class_has_source_urls(self):
        from app.services.supplementary_sources import SupplementarySources

        assert hasattr(SupplementarySources, "SOURCES")


# ─────────────────────────────────────────────────────────────────────────────
# Tests for source configuration
# ─────────────────────────────────────────────────────────────────────────────


class TestSourceConfiguration:
    """Verify the three sources are configured with correct metadata."""

    def setup_method(self):
        from app.services.supplementary_sources import SupplementarySources

        self.ss = SupplementarySources()

    def test_three_sources_defined(self):
        assert len(self.ss.SOURCES) >= 9

    def test_dte_source_configured(self):
        names = [s["source_site"] for s in self.ss.SOURCES]
        assert "downtoearth" in names

    def test_business_standard_source_configured(self):
        names = [s["source_site"] for s in self.ss.SOURCES]
        assert "businessstandard" in names

    def test_prs_source_configured(self):
        names = [s["source_site"] for s in self.ss.SOURCES]
        assert "prs" in names

    def test_each_source_has_required_keys(self):
        required = {"source_site", "name", "url", "section"}
        for source in self.ss.SOURCES:
            assert required.issubset(source.keys()), (
                f"Source {source.get('source_site')} missing keys: "
                f"{required - source.keys()}"
            )

    def test_dte_url_is_rss(self):
        dte = next(s for s in self.ss.SOURCES if s["source_site"] == "downtoearth")
        assert "downtoearth.org" in dte["url"]

    def test_bs_url_is_rss(self):
        bs = next(s for s in self.ss.SOURCES if s["source_site"] == "businessstandard")
        # Accept either feedburner or business-standard.com URL
        assert "business-standard.com" in bs["url"] or "feedburner.com" in bs["url"]

    def test_prs_url_is_rss(self):
        prs = next(s for s in self.ss.SOURCES if s["source_site"] == "prs")
        assert "prsindia.org" in prs["url"]


# ─────────────────────────────────────────────────────────────────────────────
# Tests for article dict structure
# ─────────────────────────────────────────────────────────────────────────────


class TestArticleDictFormat:
    """Ensure _parse_entry returns the correct dict shape."""

    def setup_method(self):
        from app.services.supplementary_sources import SupplementarySources

        self.ss = SupplementarySources()
        self.dte_source = next(
            s for s in self.ss.SOURCES if s["source_site"] == "downtoearth"
        )

    def test_parse_entry_returns_dict(self):
        entry = _make_entry("Test article title here", "https://dte.org/article/1")
        result = self.ss._parse_entry(entry, self.dte_source)
        assert isinstance(result, dict)

    def test_parse_entry_has_all_required_keys(self):
        entry = _make_entry("Test article title here", "https://dte.org/article/1")
        result = self.ss._parse_entry(entry, self.dte_source)
        required_keys = {
            "title",
            "url",
            "published_date",
            "author",
            "section",
            "source_site",
        }
        assert required_keys.issubset(result.keys())

    def test_parse_entry_title(self):
        entry = _make_entry("Climate change impacts India", "https://dte.org/article/1")
        result = self.ss._parse_entry(entry, self.dte_source)
        assert result["title"] == "Climate change impacts India"

    def test_parse_entry_url(self):
        entry = _make_entry("Climate change", "https://dte.org/article/123")
        result = self.ss._parse_entry(entry, self.dte_source)
        assert result["url"] == "https://dte.org/article/123"

    def test_parse_entry_source_site(self):
        entry = _make_entry("Title here", "https://dte.org/article/1")
        result = self.ss._parse_entry(entry, self.dte_source)
        assert result["source_site"] == "downtoearth"

    def test_parse_entry_section_from_source(self):
        entry = _make_entry("Title here", "https://dte.org/article/1")
        result = self.ss._parse_entry(entry, self.dte_source)
        assert result["section"] == self.dte_source["section"]

    def test_parse_entry_published_date_is_datetime(self):
        entry = _make_entry("Title here", "https://dte.org/article/1")
        result = self.ss._parse_entry(entry, self.dte_source)
        assert isinstance(result["published_date"], datetime)

    def test_parse_entry_published_date_fallback_when_none(self):
        entry = _make_entry(
            "Title here", "https://dte.org/article/1", published_parsed=None
        )
        entry.published_parsed = None
        result = self.ss._parse_entry(entry, self.dte_source)
        # Should fallback to current time (not raise)
        assert isinstance(result["published_date"], datetime)

    def test_parse_entry_author_none_when_missing(self):
        entry = _make_entry("Title here", "https://dte.org/article/1")
        # Simulate missing author
        entry.get.return_value = None
        result = self.ss._parse_entry(entry, self.dte_source)
        # author is None or a string — not required to be non-None
        assert result["author"] is None or isinstance(result["author"], str)

    def test_parse_entry_author_when_present(self):
        entry = _make_entry(
            "Title here", "https://dte.org/article/1", author="Jane Doe"
        )
        entry.get.side_effect = (
            lambda key, default=None: "Jane Doe" if key == "author" else default
        )
        result = self.ss._parse_entry(entry, self.dte_source)
        assert result["author"] == "Jane Doe"

    def test_parse_entry_returns_none_for_empty_title(self):
        entry = _make_entry("", "https://dte.org/article/1")
        result = self.ss._parse_entry(entry, self.dte_source)
        assert result is None

    def test_parse_entry_returns_none_for_missing_url(self):
        entry = _make_entry("Some title here", "")
        result = self.ss._parse_entry(entry, self.dte_source)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# Tests for fetch_source (single source, mocked network)
# ─────────────────────────────────────────────────────────────────────────────


class TestFetchSource:
    """Test _fetch_source with mocked feedparser/httpx."""

    def setup_method(self):
        from app.services.supplementary_sources import SupplementarySources

        self.ss = SupplementarySources()
        self.dte_source = next(
            s for s in self.ss.SOURCES if s["source_site"] == "downtoearth"
        )

    @patch("app.services.supplementary_sources.feedparser")
    @patch("app.services.supplementary_sources.requests")
    def test_fetch_source_returns_list(self, mock_requests, mock_feedparser):
        # Setup mocks
        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        mock_feed = _make_feed(
            [
                _make_entry("Article A", "https://dte.org/a"),
                _make_entry("Article B", "https://dte.org/b"),
            ]
        )
        mock_feedparser.parse.return_value = mock_feed

        result = self.ss._fetch_source(self.dte_source)
        assert isinstance(result, list)

    @patch("app.services.supplementary_sources.feedparser")
    @patch("app.services.supplementary_sources.requests")
    def test_fetch_source_returns_correct_count(self, mock_requests, mock_feedparser):
        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        mock_feed = _make_feed(
            [
                _make_entry("Article A", "https://dte.org/a"),
                _make_entry("Article B", "https://dte.org/b"),
                _make_entry("Article C", "https://dte.org/c"),
            ]
        )
        mock_feedparser.parse.return_value = mock_feed

        result = self.ss._fetch_source(self.dte_source)
        assert len(result) == 3

    @patch("app.services.supplementary_sources.feedparser")
    @patch("app.services.supplementary_sources.requests")
    def test_fetch_source_article_has_source_site(self, mock_requests, mock_feedparser):
        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        mock_feed = _make_feed([_make_entry("Article A", "https://dte.org/a")])
        mock_feedparser.parse.return_value = mock_feed

        result = self.ss._fetch_source(self.dte_source)
        assert result[0]["source_site"] == "downtoearth"

    @patch("app.services.supplementary_sources.feedparser")
    @patch("app.services.supplementary_sources.requests")
    def test_fetch_source_returns_empty_on_network_error(
        self, mock_requests, mock_feedparser
    ):
        """If requests raises, return empty list (don't crash)."""
        mock_requests.get.side_effect = Exception("Connection refused")

        result = self.ss._fetch_source(self.dte_source)
        assert result == []

    @patch("app.services.supplementary_sources.feedparser")
    @patch("app.services.supplementary_sources.requests")
    def test_fetch_source_returns_empty_on_http_error(
        self, mock_requests, mock_feedparser
    ):
        """If HTTP raises, return empty list."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("404 Not Found")
        mock_requests.get.return_value = mock_response

        result = self.ss._fetch_source(self.dte_source)
        assert result == []

    @patch("app.services.supplementary_sources.feedparser")
    @patch("app.services.supplementary_sources.requests")
    def test_fetch_source_returns_empty_when_no_entries(
        self, mock_requests, mock_feedparser
    ):
        """Empty feed = empty list."""
        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        mock_feed = _make_feed([])
        mock_feedparser.parse.return_value = mock_feed

        result = self.ss._fetch_source(self.dte_source)
        assert result == []

    @patch("app.services.supplementary_sources.feedparser")
    @patch("app.services.supplementary_sources.requests")
    def test_fetch_source_skips_invalid_entries(self, mock_requests, mock_feedparser):
        """Entries with empty title should be skipped."""
        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        mock_feed = _make_feed(
            [
                _make_entry("", "https://dte.org/bad"),  # invalid — no title
                _make_entry("Good Article Here", "https://dte.org/good"),  # valid
            ]
        )
        mock_feedparser.parse.return_value = mock_feed

        result = self.ss._fetch_source(self.dte_source)
        assert len(result) == 1
        assert result[0]["title"] == "Good Article Here"


# ─────────────────────────────────────────────────────────────────────────────
# Tests for fetch_all (all three sources)
# ─────────────────────────────────────────────────────────────────────────────


class TestFetchAll:
    """Test fetch_all aggregates from all three sources."""

    def setup_method(self):
        from app.services.supplementary_sources import SupplementarySources

        self.ss = SupplementarySources()

    @patch("app.services.supplementary_sources.feedparser")
    @patch("app.services.supplementary_sources.requests")
    def test_fetch_all_returns_list(self, mock_requests, mock_feedparser):
        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        mock_feedparser.parse.return_value = _make_feed(
            [_make_entry("Article", "https://example.com/a")]
        )

        result = self.ss.fetch_all()
        assert isinstance(result, list)

    @patch("app.services.supplementary_sources.feedparser")
    @patch("app.services.supplementary_sources.requests")
    def test_fetch_all_combines_three_sources(self, mock_requests, mock_feedparser):
        """fetch_all should combine articles from all 3 sources."""
        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # Each call returns 2 articles → 11 sources × 2 = 22 total
        mock_feedparser.parse.return_value = _make_feed(
            [
                _make_entry("Article 1", "https://example.com/1"),
                _make_entry("Article 2", "https://example.com/2"),
            ]
        )

        result = self.ss.fetch_all()
        assert len(result) == 22

    @patch("app.services.supplementary_sources.feedparser")
    @patch("app.services.supplementary_sources.requests")
    def test_fetch_all_graceful_when_one_source_fails(
        self, mock_requests, mock_feedparser
    ):
        """If one source fails, others still return results."""
        call_count = 0

        def side_effect_get(url, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Network error on first source")
            mock_response = MagicMock()
            mock_response.content = b"<rss/>"
            mock_response.raise_for_status.return_value = None
            return mock_response

        mock_requests.get.side_effect = side_effect_get

        mock_feedparser.parse.return_value = _make_feed(
            [
                _make_entry("Article", "https://example.com/a"),
            ]
        )

        result = self.ss.fetch_all()
        # One source failed, remaining 10 sources succeeded with 1 article each → 10 total
        assert len(result) == 10

    @patch("app.services.supplementary_sources.feedparser")
    @patch("app.services.supplementary_sources.requests")
    def test_fetch_all_all_sources_represented(self, mock_requests, mock_feedparser):
        """All three source_site values should appear in combined result."""
        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        # Return 1 article per source
        mock_feedparser.parse.return_value = _make_feed(
            [
                _make_entry("Article", "https://example.com/a"),
            ]
        )

        result = self.ss.fetch_all()
        source_sites = {a["source_site"] for a in result}
        assert "downtoearth" in source_sites
        assert "businessstandard" in source_sites
        assert "prs" in source_sites

    @patch("app.services.supplementary_sources.feedparser")
    @patch("app.services.supplementary_sources.requests")
    def test_fetch_all_articles_have_required_keys(
        self, mock_requests, mock_feedparser
    ):
        """Every article from fetch_all must have all required keys."""
        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        mock_feedparser.parse.return_value = _make_feed(
            [
                _make_entry("Article", "https://example.com/a"),
            ]
        )

        result = self.ss.fetch_all()
        required_keys = {
            "title",
            "url",
            "published_date",
            "author",
            "section",
            "source_site",
        }
        for article in result:
            assert required_keys.issubset(article.keys()), (
                f"Article missing keys: {required_keys - article.keys()}"
            )



# ─────────────────────────────────────────────────────────────────────────────
# Tests for RBI RSS feeds
# ─────────────────────────────────────────────────────────────────────────────


class TestRBIFeeds:
    """Verify the 4 RBI RSS feeds are configured correctly."""

    def setup_method(self):
        from app.services.supplementary_sources import SupplementarySources

        self.ss = SupplementarySources()
        self.SOURCES = self.ss.SOURCES

    def test_rbi_feeds_count(self):
        """There should be exactly 4 RBI sources."""
        rbi_sources = [s for s in self.SOURCES if s["source_site"] == "rbi"]
        assert len(rbi_sources) == 4

    def test_total_source_count(self):
        """Total SOURCES list should have at least 9 entries (3 existing + 4 RBI + 1 Bar & Bench + 1 LiveLaw)."""
        assert len(self.SOURCES) >= 9

    def test_rbi_feeds_urls(self):
        """All 4 RBI URLs should be present in SOURCES."""
        urls = [s["url"] for s in self.SOURCES]
        assert "https://rbi.org.in/pressreleases_rss.xml" in urls
        assert "https://rbi.org.in/notifications_rss.xml" in urls
        assert "https://rbi.org.in/speeches_rss.xml" in urls
        assert "https://rbi.org.in/Publication_rss.xml" in urls

    def test_rbi_feeds_section(self):
        """All RBI entries should have section == 'economy'."""
        rbi_sources = [s for s in self.SOURCES if s["source_site"] == "rbi"]
        for source in rbi_sources:
            assert source["section"] == "economy", (
                f"RBI source '{source['name']}' has wrong section: {source['section']}"
            )

    @patch("app.services.supplementary_sources.requests")
    def test_rbi_feed_fetch_uses_browser_ua(self, mock_requests):
        """_fetch_source for RBI must call requests.get with Mozilla/5.0 User-Agent."""
        mock_response = MagicMock()
        mock_response.content = b"<rss/>"
        mock_response.raise_for_status.return_value = None
        mock_requests.get.return_value = mock_response

        with patch("app.services.supplementary_sources.feedparser") as mock_feedparser:
            mock_feedparser.parse.return_value = _make_feed([])

            rbi_source = next(s for s in self.SOURCES if s["source_site"] == "rbi")
            self.ss._fetch_source(rbi_source)

        # Assert requests.get was called with headers containing Mozilla/5.0
        assert mock_requests.get.called
        call_kwargs = mock_requests.get.call_args
        headers = call_kwargs[1].get("headers") or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs[1].get("headers")
        assert headers is not None, "requests.get was not called with headers"
        assert "Mozilla/5.0" in headers.get("User-Agent", ""), (
            f"User-Agent does not contain 'Mozilla/5.0': {headers.get('User-Agent')}"
        )



# ─────────────────────────────────────────────────────────────────────────────
# Tests for Bar & Bench RSS feed
# ─────────────────────────────────────────────────────────────────────────────


class TestBarAndBench:
    """Verify Bar & Bench RSS feed is configured and Dealstreet entries are filtered."""

    def setup_method(self):
        from app.services.supplementary_sources import SupplementarySources

        self.ss = SupplementarySources()
        self.SOURCES = self.ss.SOURCES
        self.bb_source = next(
            (s for s in self.SOURCES if s["source_site"] == "barandbench"), None
        )

    def test_barandbench_feed_present(self):
        """SOURCES must contain an entry with source_site='barandbench' and section='polity'."""
        assert self.bb_source is not None, "barandbench not found in SOURCES"
        assert self.bb_source["section"] == "polity"

    def test_barandbench_feed_url(self):
        """Bar & Bench URL must be the stories RSS feed."""
        assert self.bb_source is not None, "barandbench not found in SOURCES"
        assert self.bb_source["url"] == "https://www.barandbench.com/stories.rss"

    def test_total_source_count_after_barandbench(self):
        """Total SOURCES must be at least 8 after adding Bar & Bench."""
        assert len(self.SOURCES) >= 8

    def test_dealstreet_entry_filtered(self):
        """Entry with tag term='Dealstreet' must return None from _parse_entry."""
        assert self.bb_source is not None, "barandbench not found in SOURCES"
        entry = _make_entry(
            "Dealstreet: Company X acquires Company Y",
            "https://www.barandbench.com/dealstreet/article-1",
            tags=["Dealstreet"],
        )
        result = self.ss._parse_entry(entry, self.bb_source)
        assert result is None, "Dealstreet entry should be filtered out (return None)"

    def test_dealstreet_filter_case_insensitive(self):
        """Dealstreet filter must be case-insensitive."""
        assert self.bb_source is not None, "barandbench not found in SOURCES"
        entry = _make_entry(
            "dealstreet: merger news",
            "https://www.barandbench.com/dealstreet/article-2",
            tags=["dealstreet"],
        )
        result = self.ss._parse_entry(entry, self.bb_source)
        assert result is None, "Lowercase 'dealstreet' tag should also be filtered"

    def test_judicial_entry_passes(self):
        """Entry with tag term='Supreme Court' must pass through _parse_entry."""
        assert self.bb_source is not None, "barandbench not found in SOURCES"
        entry = _make_entry(
            "Supreme Court upholds constitutional validity of Article 370 abrogation",
            "https://www.barandbench.com/supreme-court/article-3",
            tags=["Supreme Court"],
        )
        result = self.ss._parse_entry(entry, self.bb_source)
        assert result is not None, "Judicial entry should NOT be filtered"
        assert result["source_site"] == "barandbench"
        assert result["section"] == "polity"

    def test_entry_without_tags_passes(self):
        """Entry with no tags at all must pass through (not filtered)."""
        assert self.bb_source is not None, "barandbench not found in SOURCES"
        entry = _make_entry(
            "High Court order on electoral bonds",
            "https://www.barandbench.com/high-court/article-4",
            tags=[],
        )
        result = self.ss._parse_entry(entry, self.bb_source)
        assert result is not None, "Entry without tags should NOT be filtered"


# ─────────────────────────────────────────────────────────────────────────────
# Tests for NITI Aayog RSS feed
# ─────────────────────────────────────────────────────────────────────────────


class TestNITIAayogFeed:
    """Verify NITI Aayog RSS feed is configured correctly."""

    def setup_method(self):
        from app.services.supplementary_sources import SupplementarySources

        self.ss = SupplementarySources()
        self.SOURCES = self.ss.SOURCES
        self.niti_source = next(
            (s for s in self.SOURCES if s["source_site"] == "niti"), None
        )

    def test_niti_feed_present(self):
        """SOURCES must contain entry with source_site='niti' and section='policy'."""
        assert self.niti_source is not None, "niti not found in SOURCES"
        assert self.niti_source["section"] == "policy"

    def test_niti_feed_url(self):
        """NITI Aayog URL must be https://niti.gov.in/rss.xml"""
        assert self.niti_source is not None, "niti not found in SOURCES"
        assert self.niti_source["url"] == "https://niti.gov.in/rss.xml"


# ─────────────────────────────────────────────────────────────────────────────
# Tests for Gateway House RSS feed
# ─────────────────────────────────────────────────────────────────────────────


class TestGatewayHouseFeed:
    """Verify Gateway House RSS feed is configured and parses correctly."""

    def setup_method(self):
        from app.services.supplementary_sources import SupplementarySources

        self.ss = SupplementarySources()
        self.SOURCES = self.ss.SOURCES
        self.gh_source = next(
            (s for s in self.SOURCES if s["source_site"] == "gatewayhouse"), None
        )

    def test_gatewayhouse_feed_present(self):
        """SOURCES must contain entry with source_site='gatewayhouse' and section='international_relations'."""
        assert self.gh_source is not None, "gatewayhouse not found in SOURCES"
        assert self.gh_source["section"] == "international_relations"

    def test_gatewayhouse_feed_url(self):
        """Gateway House URL must be https://www.gatewayhouse.in/feed"""
        assert self.gh_source is not None, "gatewayhouse not found in SOURCES"
        assert self.gh_source["url"] == "https://www.gatewayhouse.in/feed"

    def test_gatewayhouse_fulltext_parse(self):
        """Mock feedparser entry with content field; assert _parse_entry returns correct article."""
        assert self.gh_source is not None, "gatewayhouse not found in SOURCES"
        entry = _make_entry(
            "India's G20 Presidency and the Global South",
            "https://www.gatewayhouse.in/indias-g20-presidency/",
            author="Gateway House Analyst",
        )
        # Simulate WordPress feed content field
        entry.content = [{"type": "text/html", "value": "<p>Full article text here.</p>"}]
        result = self.ss._parse_entry(entry, self.gh_source)
        assert result is not None, "_parse_entry returned None for valid Gateway House entry"
        assert result["source_site"] == "gatewayhouse"
        assert result["section"] == "international_relations"


# ─────────────────────────────────────────────────────────────────────────────
# Tests for LiveLaw RSS feed
# ─────────────────────────────────────────────────────────────────────────────


class TestLiveLaw:
    """Verify LiveLaw top-stories RSS feed is configured and parsed correctly."""

    def setup_method(self):
        from app.services.supplementary_sources import SupplementarySources

        self.ss = SupplementarySources()
        self.SOURCES = self.ss.SOURCES
        self.ll_source = next(
            (s for s in self.SOURCES if s["source_site"] == "livelaw"), None
        )

    def test_livelaw_feed_present(self):
        """SOURCES must contain an entry with source_site='livelaw' and section='polity'."""
        assert self.ll_source is not None, "livelaw not found in SOURCES"
        assert self.ll_source["section"] == "polity"

    def test_livelaw_feed_url(self):
        """LiveLaw URL must be the top-stories Google feeds RSS endpoint."""
        assert self.ll_source is not None, "livelaw not found in SOURCES"
        assert self.ll_source["url"] == "https://www.livelaw.in/category/top-stories/google_feeds.xml"

    def test_livelaw_fulltext_parse(self):
        """_parse_entry on a LiveLaw entry with content:encoded returns correct article."""
        assert self.ll_source is not None, "livelaw not found in SOURCES"
        # Simulate feedparser entry with content:encoded (parsed into entry.content list)
        entry = _make_entry(
            "Supreme Court rules on electoral bonds",
            "https://www.livelaw.in/top-stories/supreme-court-electoral-bonds-123",
        )
        # Simulate content:encoded field that feedparser maps to entry.content[0].value
        content_item = MagicMock()
        content_item.value = "<p>Full article text about electoral bonds and Supreme Court ruling.</p>"
        entry.content = [content_item]

        result = self.ss._parse_entry(entry, self.ll_source)

        assert result is not None, "_parse_entry returned None for valid LiveLaw entry"
        assert result["source_site"] == "livelaw"
        assert result["section"] == "polity"

    def test_livelaw_polity_section(self):
        """Any article parsed from LiveLaw source has section='polity'."""
        assert self.ll_source is not None, "livelaw not found in SOURCES"
        entry = _make_entry(
            "High Court quashes FIR against journalist",
            "https://www.livelaw.in/top-stories/high-court-fir-journalist-456",
        )
        result = self.ss._parse_entry(entry, self.ll_source)
        assert result is not None
        assert result["section"] == "polity"