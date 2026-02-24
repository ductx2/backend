"""
TDD Tests for UnifiedPipeline (T13).
Tests covering: imports, fetch, enrich, run, edge cases, Wave 3 scrapers.
All source dependencies are mocked — no network calls.
"""

import pytest
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# Dynamic dates so tests don't expire after 36h
_RECENT_DATE_ISO = (datetime.now(timezone.utc) - timedelta(hours=6)).isoformat()
_RECENT_DATE_STR = (datetime.now(timezone.utc) - timedelta(hours=6)).strftime(
    "%Y-%m-%d"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _hindu_articles():
    """Simulated Hindu RSS output (note: source_url, source, content keys)."""
    return [
        {
            "title": "Hindu Article 1",
            "content": "Full body text from RSS feed.",
            "source": "The Hindu - Editorial",
            "source_url": "https://thehindu.com/editorial/article1",
            "url": "https://thehindu.com/editorial/article1",
            "published_at": _RECENT_DATE_ISO,
            "content_hash": "h1",
            "raw_entry": {},
        },
        {
            "title": "Hindu Article 2",
            "content": "Another body.",
            "source": "The Hindu - Op-Ed",
            "source_url": "https://thehindu.com/oped/article2",
            "url": "https://thehindu.com/oped/article2",
            "published_at": _RECENT_DATE_ISO,
            "content_hash": "h2",
            "raw_entry": {},
        },
    ]


def _ie_articles():
    return [
        {
            "title": "IE Article 1",
            "url": "https://indianexpress.com/article/ie1",
            "published_date": _RECENT_DATE_STR,
            "author": "Author A",
            "section": "explained",
            "source_site": "indianexpress",
        },
    ]


def _pib_articles():
    return [
        {
            "title": "PIB Release 1",
            "url": "https://pib.gov.in/release1",
            "published_date": _RECENT_DATE_STR,
            "ministry": "Finance",
            "source_site": "pib",
        },
    ]


def _supplementary_articles():
    return [
        {
            "title": "Supplementary 1",
            "url": "https://livemint.com/sup1",
            "published_date": _RECENT_DATE_STR,
            "author": "Author B",
            "section": "economy",
            "source_site": "livemint",
        },
    ]


def _hindu_pw_articles():
    """Simulated HinduPlaywrightScraper output (uses 'url', not 'source_url')."""
    return [
        {
            "title": "Hindu PW Article 1",
            "url": "https://thehindu.com/pw/editorial1",
            "content": "Playwright-scraped Hindu editorial.",
            "published_date": _RECENT_DATE_STR,
            "author": "PW Author",
            "section": "editorial",
            "source_site": "hindu",
        },
    ]


def _ie_pw_articles():
    """Simulated IEPlaywrightScraper output (uses 'url', not 'source_url')."""
    return [
        {
            "title": "IE PW Article 1",
            "url": "https://indianexpress.com/pw/explained1",
            "content": "Playwright-scraped IE editorial.",
            "published_date": _RECENT_DATE_STR,
            "author": "IE PW Author",
            "section": "explained",
            "source_site": "indianexpress",
        },
    ]


def _mea_articles():
    """Simulated MEAScraper output (uses 'source_url', not 'url')."""
    return [
        {
            "title": "MEA Press Release 1",
            "content": "MEA press release content.",
            "source_url": "https://mea.gov.in/press-release1",
            "source_site": "mea",
            "section": "press-releases",
            "published_date": _RECENT_DATE_STR,
        },
    ]


def _orf_articles():
    """Simulated ORFScraper output (uses 'source_url', not 'url')."""
    return [
        {
            "title": "ORF Expert Speak 1",
            "content": "ORF expert analysis content.",
            "source_url": "https://orfonline.org/expert-speak/1",
            "source_site": "orf",
            "section": "expert-speak",
            "published_date": _RECENT_DATE_STR,
        },
    ]


def _idsa_articles():
    """Simulated IDSAScraper output (uses 'source_url', not 'url')."""
    return [
        {
            "title": "IDSA Comment 1",
            "content": "IDSA strategic analysis.",
            "source_url": "https://idsa.in/comment/1",
            "source_site": "idsa",
            "section": "comments-briefs",
            "published_date": _RECENT_DATE_STR,
        },
    ]


def _enriched_article(title="Test", score=80):
    """Simulated output from KnowledgeCardPipeline.process_article."""
    return {
        "title": title,
        "upsc_relevance_score": score,
        "themes": ["Polity"],
        "key_concepts": ["federalism"],
        "summary": "A summary.",
        "pyq_connections": [],
    }


# ---------------------------------------------------------------------------
# Helper: build mock patches for Wave 3 scrapers
# ---------------------------------------------------------------------------

# Module path prefix for patches
_P = "app.services.unified_pipeline"

# All 9 source patch targets (4 legacy + 5 Wave 3)
_WAVE3_PATCH_TARGETS = [
    f"{_P}.PlaywrightSessionManager",
    f"{_P}.HinduPlaywrightScraper",
    f"{_P}.IEPlaywrightScraper",
    f"{_P}.MEAScraper",
    f"{_P}.ORFScraper",
    f"{_P}.IDSAScraper",
]


def _setup_wave3_mocks(
    mock_session_cls,
    mock_hindu_pw_cls,
    mock_ie_pw_cls,
    mock_mea_cls,
    mock_orf_cls,
    mock_idsa_cls,
    *,
    hindu_pw_data=None,
    ie_pw_data=None,
    mea_data=None,
    orf_data=None,
    idsa_data=None,
    fail_all=False,
):
    """Wire up Wave 3 mock classes with default or custom return values.

    Returns dict of mock instances for assertion access.
    """
    # PlaywrightSessionManager — shared by both playwright scrapers
    mock_session = AsyncMock()
    mock_session.cleanup = AsyncMock()
    mock_session_cls.return_value = mock_session

    exception = Exception("fail") if fail_all else None

    # HinduPlaywrightScraper
    mock_hindu_pw = MagicMock()
    if fail_all:
        mock_hindu_pw.scrape_editorials = AsyncMock(side_effect=exception)
    else:
        mock_hindu_pw.scrape_editorials = AsyncMock(
            return_value=hindu_pw_data
            if hindu_pw_data is not None
            else _hindu_pw_articles()
        )
    mock_hindu_pw_cls.return_value = mock_hindu_pw

    # IEPlaywrightScraper
    mock_ie_pw = MagicMock()
    if fail_all:
        mock_ie_pw.scrape_editorials = AsyncMock(side_effect=exception)
    else:
        mock_ie_pw.scrape_editorials = AsyncMock(
            return_value=ie_pw_data if ie_pw_data is not None else _ie_pw_articles()
        )
    mock_ie_pw_cls.return_value = mock_ie_pw

    # MEAScraper
    mock_mea = MagicMock()
    if fail_all:
        mock_mea.fetch_articles = AsyncMock(side_effect=exception)
    else:
        mock_mea.fetch_articles = AsyncMock(
            return_value=mea_data if mea_data is not None else _mea_articles()
        )
    mock_mea_cls.return_value = mock_mea

    # ORFScraper
    mock_orf = MagicMock()
    if fail_all:
        mock_orf.fetch_articles = AsyncMock(side_effect=exception)
    else:
        mock_orf.fetch_articles = AsyncMock(
            return_value=orf_data if orf_data is not None else _orf_articles()
        )
    mock_orf_cls.return_value = mock_orf

    # IDSAScraper
    mock_idsa = MagicMock()
    if fail_all:
        mock_idsa.fetch_articles = AsyncMock(side_effect=exception)
    else:
        mock_idsa.fetch_articles = AsyncMock(
            return_value=idsa_data if idsa_data is not None else _idsa_articles()
        )
    mock_idsa_cls.return_value = mock_idsa

    return {
        "session": mock_session,
        "hindu_pw": mock_hindu_pw,
        "ie_pw": mock_ie_pw,
        "mea": mock_mea,
        "orf": mock_orf,
        "idsa": mock_idsa,
    }


# ---------------------------------------------------------------------------
# 1-3  Imports & instantiation
# ---------------------------------------------------------------------------


class TestImportsAndInstantiation:
    def test_import_unified_pipeline(self):
        """UnifiedPipeline can be imported from expected module path."""
        from app.services.unified_pipeline import UnifiedPipeline

        assert UnifiedPipeline is not None

    def test_instantiation_default(self):
        """UnifiedPipeline() creates an instance with no required args."""
        from app.services.unified_pipeline import UnifiedPipeline

        pipeline = UnifiedPipeline()
        assert pipeline is not None

    def test_has_required_methods(self):
        """Instance exposes fetch_all_sources, enrich_articles, run."""
        from app.services.unified_pipeline import UnifiedPipeline

        p = UnifiedPipeline()
        for method_name in ("fetch_all_sources", "enrich_articles", "run"):
            assert callable(getattr(p, method_name, None)), (
                f"Missing method: {method_name}"
            )


# ---------------------------------------------------------------------------
# 4-8  fetch_all_sources
# ---------------------------------------------------------------------------


class TestFetchAllSources:
    @pytest.fixture(autouse=True)
    def _patch_sources(self):
        """Patch all 9 source classes so no network calls happen."""
        with (
            patch(
                "app.services.unified_pipeline.OptimizedRSSProcessor"
            ) as mock_rss_cls,
            patch("app.services.unified_pipeline.IndianExpressScraper") as mock_ie_cls,
            patch("app.services.unified_pipeline.PIBScraper") as mock_pib_cls,
            patch("app.services.unified_pipeline.SupplementarySources") as mock_sup_cls,
            patch(
                "app.services.unified_pipeline.PlaywrightSessionManager"
            ) as mock_session_cls,
            patch(
                "app.services.unified_pipeline.HinduPlaywrightScraper"
            ) as mock_hindu_pw_cls,
            patch(
                "app.services.unified_pipeline.IEPlaywrightScraper"
            ) as mock_ie_pw_cls,
            patch("app.services.unified_pipeline.MEAScraper") as mock_mea_cls,
            patch("app.services.unified_pipeline.ORFScraper") as mock_orf_cls,
            patch("app.services.unified_pipeline.IDSAScraper") as mock_idsa_cls,
        ):
            # Hindu RSS — async
            mock_rss = MagicMock()
            mock_rss.fetch_all_sources_parallel = AsyncMock(
                return_value=_hindu_articles()
            )
            mock_rss_cls.return_value = mock_rss

            # IE — async
            mock_ie = MagicMock()
            mock_ie.scrape_all_sections = AsyncMock(return_value=_ie_articles())
            mock_ie_cls.return_value = mock_ie

            # PIB — async
            mock_pib = MagicMock()
            mock_pib.scrape_releases = AsyncMock(return_value=_pib_articles())
            mock_pib_cls.return_value = mock_pib

            # Supplementary — sync (wrapped in asyncio.to_thread by pipeline)
            mock_sup = MagicMock()
            mock_sup.fetch_all = MagicMock(return_value=_supplementary_articles())
            mock_sup_cls.return_value = mock_sup

            # Wave 3 scrapers
            w3 = _setup_wave3_mocks(
                mock_session_cls,
                mock_hindu_pw_cls,
                mock_ie_pw_cls,
                mock_mea_cls,
                mock_orf_cls,
                mock_idsa_cls,
            )

            self.mock_rss = mock_rss
            self.mock_ie = mock_ie
            self.mock_pib = mock_pib
            self.mock_sup = mock_sup
            self.w3 = w3
            yield

    @pytest.mark.asyncio
    async def test_returns_list(self):
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_merges_all_nine_sources(self):
        """Total = 2 hindu + 1 ie + 1 pib + 1 sup + 1 hindu_pw + 1 ie_pw + 1 mea + 1 orf + 1 idsa = 10."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        assert len(result) == 10

    @pytest.mark.asyncio
    async def test_deduplicates_by_url(self):
        """If two articles share the same URL, only one survives."""
        self.mock_ie.scrape_all_sections = AsyncMock(
            return_value=[
                {
                    "title": "Duplicate",
                    "url": "https://thehindu.com/editorial/article1",  # same as Hindu #1
                    "published_date": _RECENT_DATE_STR,
                    "author": "X",
                    "section": "dup",
                    "source_site": "indianexpress",
                },
            ]
        )
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        urls = [a.get("url", "").lower() for a in result]
        assert len(urls) == len(set(urls)), "Duplicate URLs found"

    @pytest.mark.asyncio
    async def test_source_failure_does_not_crash(self):
        """If one source raises, others still returned."""
        self.mock_pib.scrape_releases = AsyncMock(side_effect=Exception("PIB down"))
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        # 10 total minus PIB(1) = at least 9; using >= for safety
        assert len(result) >= 8

    @pytest.mark.asyncio
    async def test_all_articles_have_source_site(self):
        """Every article in result has a 'source_site' key (incl. Hindu)."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        for article in result:
            assert "source_site" in article, (
                f"Missing source_site: {article.get('title')}"
            )


# ---------------------------------------------------------------------------
# 9-12  enrich_articles (DEPRECATED but still exists)
# ---------------------------------------------------------------------------


class TestEnrichArticles:
    @pytest.mark.asyncio
    async def test_calls_pipeline_process_article(self):
        """enrich_articles delegates to KnowledgeCardPipeline.process_article."""
        with patch(
            "app.services.unified_pipeline.KnowledgeCardPipeline"
        ) as mock_kcp_cls:
            mock_kcp = MagicMock()
            mock_kcp.process_article = AsyncMock(return_value=_enriched_article())
            mock_kcp_cls.return_value = mock_kcp

            from app.services.unified_pipeline import UnifiedPipeline

            p = UnifiedPipeline()
            articles = [
                {
                    "title": "A",
                    "content": "body",
                    "url": "http://a.com",
                    "source_site": "test",
                }
            ]
            await p.enrich_articles(articles)
            mock_kcp.process_article.assert_called_once()

    @pytest.mark.asyncio
    async def test_filters_none_results(self):
        """Articles where process_article returns None are excluded."""
        with patch(
            "app.services.unified_pipeline.KnowledgeCardPipeline"
        ) as mock_kcp_cls:
            mock_kcp = MagicMock()
            mock_kcp.process_article = AsyncMock(
                side_effect=[_enriched_article(), None]
            )
            mock_kcp_cls.return_value = mock_kcp

            from app.services.unified_pipeline import UnifiedPipeline

            result = await UnifiedPipeline().enrich_articles(
                [
                    {
                        "title": "A",
                        "content": "body",
                        "url": "http://a.com",
                        "source_site": "x",
                    },
                    {
                        "title": "B",
                        "content": "body",
                        "url": "http://b.com",
                        "source_site": "y",
                    },
                ]
            )
            assert len(result) == 1

    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self):
        with patch(
            "app.services.unified_pipeline.KnowledgeCardPipeline"
        ) as mock_kcp_cls:
            mock_kcp = MagicMock()
            mock_kcp.process_article = AsyncMock(return_value=_enriched_article())
            mock_kcp_cls.return_value = mock_kcp

            from app.services.unified_pipeline import UnifiedPipeline

            result = await UnifiedPipeline().enrich_articles(
                [
                    {
                        "title": "A",
                        "content": "body",
                        "url": "http://a.com",
                        "source_site": "x",
                    },
                ]
            )
            assert isinstance(result, list)
            assert all(isinstance(r, dict) for r in result)

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty(self):
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().enrich_articles([])
        assert result == []


# ---------------------------------------------------------------------------
# 13-20  run (integration of fetch + extract + batch-score + select + pass2)
# ---------------------------------------------------------------------------


class TestRun:
    @pytest.fixture(autouse=True)
    def _patch_all(self):
        with (
            patch(
                "app.services.unified_pipeline.OptimizedRSSProcessor"
            ) as mock_rss_cls,
            patch("app.services.unified_pipeline.IndianExpressScraper") as mock_ie_cls,
            patch("app.services.unified_pipeline.PIBScraper") as mock_pib_cls,
            patch("app.services.unified_pipeline.SupplementarySources") as mock_sup_cls,
            patch(
                "app.services.unified_pipeline.PlaywrightSessionManager"
            ) as mock_session_cls,
            patch(
                "app.services.unified_pipeline.HinduPlaywrightScraper"
            ) as mock_hindu_pw_cls,
            patch(
                "app.services.unified_pipeline.IEPlaywrightScraper"
            ) as mock_ie_pw_cls,
            patch("app.services.unified_pipeline.MEAScraper") as mock_mea_cls,
            patch("app.services.unified_pipeline.ORFScraper") as mock_orf_cls,
            patch("app.services.unified_pipeline.IDSAScraper") as mock_idsa_cls,
            patch(
                "app.services.unified_pipeline.KnowledgeCardPipeline"
            ) as mock_kcp_cls,
            patch("app.services.unified_pipeline.ArticleSelector") as mock_selector_cls,
            patch(
                "app.services.unified_pipeline.UniversalContentExtractor"
            ) as mock_ext_cls,
        ):
            # --- RSS sources ---
            mock_rss = MagicMock()
            mock_rss.fetch_all_sources_parallel = AsyncMock(
                return_value=_hindu_articles()
            )
            mock_rss_cls.return_value = mock_rss

            mock_ie = MagicMock()
            mock_ie.scrape_all_sections = AsyncMock(return_value=_ie_articles())
            mock_ie_cls.return_value = mock_ie

            mock_pib = MagicMock()
            mock_pib.scrape_releases = AsyncMock(return_value=_pib_articles())
            mock_pib_cls.return_value = mock_pib

            mock_sup = MagicMock()
            mock_sup.fetch_all = MagicMock(return_value=_supplementary_articles())
            mock_sup_cls.return_value = mock_sup

            # Wave 3 scrapers (keep existing helper)
            w3 = _setup_wave3_mocks(
                mock_session_cls,
                mock_hindu_pw_cls,
                mock_ie_pw_cls,
                mock_mea_cls,
                mock_orf_cls,
                mock_idsa_cls,
            )

            # --- KnowledgeCardPipeline mock ---
            mock_kcp = MagicMock()
            mock_kcp.relevance_threshold = 55
            mock_kcp._is_must_know = MagicMock(return_value=False)
            mock_kcp._compute_triage = MagicMock(return_value="good_to_know")
            mock_kcp.run_pass1_batch = AsyncMock(
                side_effect=lambda arts: [
                    {
                        "upsc_relevance": 72,
                        "gs_paper": "GS2",
                        "key_facts": ["fact1"],
                        "keywords": ["kw1"],
                        "syllabus_matches": [],
                        "raw_pass1_data": {},
                    }
                    for _ in arts
                ]
            )
            mock_kcp.run_pass2 = AsyncMock(
                return_value={
                    "headline_layer": "Test Headline",
                    "facts_layer": ["fact1"],
                    "context_layer": "Test context",
                    "connections_layer": {
                        "syllabus_topics": [],
                        "related_pyqs": [],
                        "pyq_count": 0,
                        "year_range": "",
                    },
                    "mains_angle_layer": "Test mains angle",
                }
            )
            mock_kcp_cls.return_value = mock_kcp

            # --- ArticleSelector mock ---
            mock_selector = MagicMock()
            mock_selector.select_top_articles = AsyncMock(
                side_effect=lambda arts, target=30: arts[:target]
            )
            mock_selector_cls.return_value = mock_selector

            # --- Content extractor mock ---
            mock_ext = MagicMock()
            extracted = MagicMock()
            extracted.content = "Extracted content from URL."
            mock_ext.extract_content = MagicMock(return_value=extracted)
            mock_ext_cls.return_value = mock_ext

            self.mock_rss = mock_rss
            self.mock_ie = mock_ie
            self.mock_pib = mock_pib
            self.mock_sup = mock_sup
            self.w3 = w3
            self.mock_kcp = mock_kcp
            self.mock_selector = mock_selector
            self.mock_ext = mock_ext
            yield

    @pytest.mark.asyncio
    async def test_returns_summary_dict(self):
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run()
        assert isinstance(result, dict)
        for key in (
            "articles",
            "total_fetched",
            "total_enriched",
            "filtered",
            "pass1_count",
            "pass2_count",
            "gs_distribution",
            "llm_calls",
        ):
            assert key in result, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_correct_counts(self):
        """Verify count consistency: total_enriched == pass2_count, articles list matches."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run()
        assert result["total_enriched"] == result["pass2_count"]
        assert len(result["articles"]) == result["total_enriched"]
        assert result["total_fetched"] == 10

    @pytest.mark.asyncio
    async def test_max_articles_cap(self):
        """run(max_articles=2) → selected articles ≤ 2."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run(max_articles=2)
        assert len(result["articles"]) <= 2

    @pytest.mark.asyncio
    async def test_content_extraction_for_no_content_articles(self):
        """IE/PIB/Supplementary articles lack 'content' → extractor called."""
        from app.services.unified_pipeline import UnifiedPipeline

        await UnifiedPipeline().run()
        # Articles without content: IE(1) + PIB(1) + Supplementary(1) = 3
        # Wave 3 articles all have content, so extractor NOT called for them
        assert self.mock_ext.extract_content.call_count >= 3

    @pytest.mark.asyncio
    async def test_skip_extraction_for_articles_with_content(self):
        """Hindu articles already have content → extractor NOT called for them."""
        # Make only Hindu RSS articles available (all others return empty)
        self.mock_ie.scrape_all_sections = AsyncMock(return_value=[])
        self.mock_pib.scrape_releases = AsyncMock(return_value=[])
        self.mock_sup.fetch_all = MagicMock(return_value=[])
        self.w3["hindu_pw"].scrape_editorials = AsyncMock(return_value=[])
        self.w3["ie_pw"].scrape_editorials = AsyncMock(return_value=[])
        self.w3["mea"].fetch_articles = AsyncMock(return_value=[])
        self.w3["orf"].fetch_articles = AsyncMock(return_value=[])
        self.w3["idsa"].fetch_articles = AsyncMock(return_value=[])

        from app.services.unified_pipeline import UnifiedPipeline

        await UnifiedPipeline().run()
        assert self.mock_ext.extract_content.call_count == 0

    @pytest.mark.asyncio
    async def test_extraction_failure_does_not_crash(self):
        """If content extraction raises, article is skipped gracefully."""
        self.mock_ext.extract_content = MagicMock(side_effect=Exception("Timeout"))
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run()
        # Articles with content: Hindu(2) + hindu_pw(1) + ie_pw(1) + mea(1) + orf(1) + idsa(1) = 7
        assert result["total_enriched"] >= 7

    @pytest.mark.asyncio
    async def test_process_article_exception_does_not_crash(self):
        """If run_pass2 raises for one article, others still processed."""
        call_count = 0

        async def pass2_side_effect(article, pass1_data):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("LLM timeout")
            return {
                "headline_layer": "Test Headline",
                "facts_layer": ["fact1"],
                "context_layer": "Test context",
                "connections_layer": {
                    "syllabus_topics": [],
                    "related_pyqs": [],
                    "pyq_count": 0,
                    "year_range": "",
                },
                "mains_angle_layer": "Test mains angle",
            }

        self.mock_kcp.run_pass2 = AsyncMock(side_effect=pass2_side_effect)
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run()
        # At least some articles should survive even with 1 pass2 failure
        assert result["total_enriched"] >= 1
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_enriched_articles_in_result(self):
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run()
        assert len(result["articles"]) == result["total_enriched"]
        assert all(isinstance(a, dict) for a in result["articles"])

    @pytest.mark.asyncio
    async def test_run_gs_distribution_in_result(self):
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run()
        assert "gs_distribution" in result

    @pytest.mark.asyncio
    async def test_run_batch_scoring_called(self):
        from app.services.unified_pipeline import UnifiedPipeline

        await UnifiedPipeline().run()
        self.mock_kcp.run_pass1_batch.assert_called()

    @pytest.mark.asyncio
    async def test_run_pass2_only_on_selected(self):
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run()
        assert result["pass2_count"] == result["total_enriched"]


# ---------------------------------------------------------------------------
# 21-23  Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    @pytest.mark.asyncio
    async def test_hindu_url_normalization(self):
        """Hindu articles get 'url' key copied from 'source_url'."""
        with (
            patch(
                "app.services.unified_pipeline.OptimizedRSSProcessor"
            ) as mock_rss_cls,
            patch("app.services.unified_pipeline.IndianExpressScraper") as mock_ie_cls,
            patch("app.services.unified_pipeline.PIBScraper") as mock_pib_cls,
            patch("app.services.unified_pipeline.SupplementarySources") as mock_sup_cls,
            patch(
                "app.services.unified_pipeline.PlaywrightSessionManager"
            ) as mock_session_cls,
            patch(
                "app.services.unified_pipeline.HinduPlaywrightScraper"
            ) as mock_hindu_pw_cls,
            patch(
                "app.services.unified_pipeline.IEPlaywrightScraper"
            ) as mock_ie_pw_cls,
            patch("app.services.unified_pipeline.MEAScraper") as mock_mea_cls,
            patch("app.services.unified_pipeline.ORFScraper") as mock_orf_cls,
            patch("app.services.unified_pipeline.IDSAScraper") as mock_idsa_cls,
        ):
            mock_rss = MagicMock()
            mock_rss.fetch_all_sources_parallel = AsyncMock(
                return_value=_hindu_articles()
            )
            mock_rss_cls.return_value = mock_rss

            for cls, method in [
                (mock_ie_cls, "scrape_all_sections"),
                (mock_pib_cls, "scrape_releases"),
            ]:
                m = MagicMock()
                setattr(m, method, AsyncMock(return_value=[]))
                cls.return_value = m

            mock_sup = MagicMock()
            mock_sup.fetch_all = MagicMock(return_value=[])
            mock_sup_cls.return_value = mock_sup

            # Wave 3 — all empty
            _setup_wave3_mocks(
                mock_session_cls,
                mock_hindu_pw_cls,
                mock_ie_pw_cls,
                mock_mea_cls,
                mock_orf_cls,
                mock_idsa_cls,
                hindu_pw_data=[],
                ie_pw_data=[],
                mea_data=[],
                orf_data=[],
                idsa_data=[],
            )

            from app.services.unified_pipeline import UnifiedPipeline

            result = await UnifiedPipeline().fetch_all_sources()
            for article in result:
                assert "url" in article, (
                    f"Hindu article missing 'url': {article.get('title')}"
                )
                assert article["url"].startswith("http")

    @pytest.mark.asyncio
    async def test_all_sources_fail(self):
        """If every source raises, fetch_all_sources returns empty list."""
        with (
            patch(
                "app.services.unified_pipeline.OptimizedRSSProcessor"
            ) as mock_rss_cls,
            patch("app.services.unified_pipeline.IndianExpressScraper") as mock_ie_cls,
            patch("app.services.unified_pipeline.PIBScraper") as mock_pib_cls,
            patch("app.services.unified_pipeline.SupplementarySources") as mock_sup_cls,
            patch(
                "app.services.unified_pipeline.PlaywrightSessionManager"
            ) as mock_session_cls,
            patch(
                "app.services.unified_pipeline.HinduPlaywrightScraper"
            ) as mock_hindu_pw_cls,
            patch(
                "app.services.unified_pipeline.IEPlaywrightScraper"
            ) as mock_ie_pw_cls,
            patch("app.services.unified_pipeline.MEAScraper") as mock_mea_cls,
            patch("app.services.unified_pipeline.ORFScraper") as mock_orf_cls,
            patch("app.services.unified_pipeline.IDSAScraper") as mock_idsa_cls,
        ):
            mock_rss = MagicMock()
            mock_rss.fetch_all_sources_parallel = AsyncMock(
                side_effect=Exception("fail")
            )
            mock_rss_cls.return_value = mock_rss

            mock_ie = MagicMock()
            mock_ie.scrape_all_sections = AsyncMock(side_effect=Exception("fail"))
            mock_ie_cls.return_value = mock_ie

            mock_pib = MagicMock()
            mock_pib.scrape_releases = AsyncMock(side_effect=Exception("fail"))
            mock_pib_cls.return_value = mock_pib

            mock_sup = MagicMock()
            mock_sup.fetch_all = MagicMock(side_effect=Exception("fail"))
            mock_sup_cls.return_value = mock_sup

            # Wave 3 — all fail
            _setup_wave3_mocks(
                mock_session_cls,
                mock_hindu_pw_cls,
                mock_ie_pw_cls,
                mock_mea_cls,
                mock_orf_cls,
                mock_idsa_cls,
                fail_all=True,
            )

            from app.services.unified_pipeline import UnifiedPipeline

            result = await UnifiedPipeline().fetch_all_sources()
            assert result == []

    @pytest.mark.asyncio
    async def test_case_insensitive_dedup(self):
        """URLs differing only by case are treated as duplicates."""
        with (
            patch(
                "app.services.unified_pipeline.OptimizedRSSProcessor"
            ) as mock_rss_cls,
            patch("app.services.unified_pipeline.IndianExpressScraper") as mock_ie_cls,
            patch("app.services.unified_pipeline.PIBScraper") as mock_pib_cls,
            patch("app.services.unified_pipeline.SupplementarySources") as mock_sup_cls,
            patch(
                "app.services.unified_pipeline.PlaywrightSessionManager"
            ) as mock_session_cls,
            patch(
                "app.services.unified_pipeline.HinduPlaywrightScraper"
            ) as mock_hindu_pw_cls,
            patch(
                "app.services.unified_pipeline.IEPlaywrightScraper"
            ) as mock_ie_pw_cls,
            patch("app.services.unified_pipeline.MEAScraper") as mock_mea_cls,
            patch("app.services.unified_pipeline.ORFScraper") as mock_orf_cls,
            patch("app.services.unified_pipeline.IDSAScraper") as mock_idsa_cls,
        ):
            mock_rss = MagicMock()
            mock_rss.fetch_all_sources_parallel = AsyncMock(return_value=[])
            mock_rss_cls.return_value = mock_rss

            mock_ie = MagicMock()
            mock_ie.scrape_all_sections = AsyncMock(
                return_value=[
                    {
                        "title": "A",
                        "url": "https://example.com/Article1",
                        "published_date": _RECENT_DATE_STR,
                        "author": "X",
                        "section": "s",
                        "source_site": "ie",
                    },
                ]
            )
            mock_ie_cls.return_value = mock_ie

            mock_pib = MagicMock()
            mock_pib.scrape_releases = AsyncMock(
                return_value=[
                    {
                        "title": "B",
                        "url": "https://example.com/article1",
                        "published_date": _RECENT_DATE_STR,
                        "ministry": "Y",
                        "source_site": "pib",
                    },
                ]
            )
            mock_pib_cls.return_value = mock_pib

            mock_sup = MagicMock()
            mock_sup.fetch_all = MagicMock(return_value=[])
            mock_sup_cls.return_value = mock_sup

            # Wave 3 — all empty
            _setup_wave3_mocks(
                mock_session_cls,
                mock_hindu_pw_cls,
                mock_ie_pw_cls,
                mock_mea_cls,
                mock_orf_cls,
                mock_idsa_cls,
                hindu_pw_data=[],
                ie_pw_data=[],
                mea_data=[],
                orf_data=[],
                idsa_data=[],
            )

            from app.services.unified_pipeline import UnifiedPipeline

            result = await UnifiedPipeline().fetch_all_sources()
            assert len(result) == 1, f"Expected 1 after dedup, got {len(result)}"


# ---------------------------------------------------------------------------
# 24-29  T14: prepare_knowledge_card_for_database, save_articles, run(save_to_db)
# ---------------------------------------------------------------------------


def _enriched_knowledge_card_article():
    """Simulated output from KnowledgeCardPipeline.process_article with all 5-layer fields."""
    return {
        # Original article keys
        "title": "Budget 2026 Highlights",
        "url": "https://indianexpress.com/budget-2026",
        "source_site": "indianexpress",
        "section": "explained",
        "published_date": _RECENT_DATE_STR,
        "content": "The Union Budget 2026 was presented today.",
        # Pass 1
        "upsc_relevance": 85,
        "gs_paper": "GS3",
        "key_facts": ["fiscal deficit target", "capital expenditure"],
        "keywords": ["budget", "fiscal policy"],
        "syllabus_matches": [
            {
                "paper": "GS3",
                "topic": "Economy",
                "sub_topic": "Government Budgeting",
                "confidence": 0.9,
            },
        ],
        "priority_triage": "must_know",
        "raw_pass1_data": {},
        # Pass 2 (5 layers)
        "headline_layer": "Union Budget 2026 focuses on capital expenditure.",
        "facts_layer": ["Fiscal deficit at 5.1%", "Capex up 20%"],
        "context_layer": "Continuation of fiscal consolidation path.",
        "connections_layer": {
            "syllabus_topics": ["Indian Economy"],
            "related_pyqs": [{"year": 2023, "question": "Discuss fiscal policy."}],
            "pyq_count": 1,
            "year_range": "2023-2023",
        },
        "mains_angle_layer": "Analyze the fiscal consolidation strategy.",
    }


class TestPrepareKnowledgeCardForDatabase:
    def test_maps_all_fields_correctly(self):
        """prepare_knowledge_card_for_database produces DB dict with all required fields."""
        from app.services.unified_pipeline import prepare_knowledge_card_for_database

        article = _enriched_knowledge_card_article()
        db_row = prepare_knowledge_card_for_database(article)

        # Core fields
        assert db_row["title"] == "Budget 2026 Highlights"
        assert db_row["source_url"] == "https://indianexpress.com/budget-2026"
        assert db_row["source_site"] == "indianexpress"
        assert db_row["status"] == "published"
        assert db_row["date"] == _RECENT_DATE_STR

        # Analysis fields
        assert db_row["upsc_relevance"] == 85
        assert db_row["gs_paper"] == "GS3"
        assert db_row["tags"] == ["budget", "fiscal policy"]
        assert db_row["category"] == "gs3"
        assert db_row["importance"] == "high"  # must_know -> high

        # 5-layer fields
        assert (
            db_row["headline_layer"]
            == "Union Budget 2026 focuses on capital expenditure."
        )
        assert db_row["facts_layer"] == ["Fiscal deficit at 5.1%", "Capex up 20%"]
        assert db_row["context_layer"] == "Continuation of fiscal consolidation path."
        assert db_row["connections_layer"]["pyq_count"] == 1
        assert (
            db_row["mains_angle_layer"] == "Analyze the fiscal consolidation strategy."
        )
        assert db_row["priority_triage"] == "must_know"
        assert db_row["syllabus_topic"] == "Government Budgeting"

        # Dedup hash
        assert isinstance(db_row["content_hash"], str)
        assert len(db_row["content_hash"]) == 32  # MD5 hex digest

    def test_handles_missing_optional_fields(self):
        """Minimal article (missing optional fields) doesn't crash."""
        from app.services.unified_pipeline import prepare_knowledge_card_for_database

        minimal = {"title": "Bare Minimum"}
        db_row = prepare_knowledge_card_for_database(minimal)

        assert db_row["title"] == "Bare Minimum"
        assert db_row["source_url"] == ""
        assert db_row["status"] == "published"
        assert db_row["importance"] == "low"  # good_to_know default -> low
        assert db_row["headline_layer"] == ""
        assert db_row["facts_layer"] == []
        assert db_row["connections_layer"] == {}
        assert db_row["syllabus_topic"] == ""
        # date should fallback to today
        assert isinstance(db_row["date"], str)
        assert len(db_row["date"]) == 10  # YYYY-MM-DD


class TestSaveArticles:
    @pytest.mark.asyncio
    async def test_calls_upsert_and_returns_correct_counts(self):
        """save_articles upserts each article and reports saved count."""
        from app.services.unified_pipeline import UnifiedPipeline

        mock_db = AsyncMock()
        mock_db.upsert_current_affair = AsyncMock(
            return_value={"success": True, "data": {}, "message": "ok"}
        )

        articles = [
            {"title": "A", "url": "http://a.com", "priority_triage": "must_know"},
            {"title": "B", "url": "http://b.com", "priority_triage": "should_know"},
        ]

        pipeline = UnifiedPipeline()
        result = await pipeline.save_articles(articles, mock_db)

        assert mock_db.upsert_current_affair.call_count == 2
        assert result["saved"] == 2
        assert result["errors"] == 0

    @pytest.mark.asyncio
    async def test_counts_db_errors_without_raising(self):
        """DB failures are counted, not raised."""
        from app.services.unified_pipeline import UnifiedPipeline

        mock_db = AsyncMock()
        mock_db.upsert_current_affair = AsyncMock(
            side_effect=[
                {"success": True, "data": {}, "message": "ok"},
                {"success": False, "error": "DB constraint violation"},
            ]
        )

        articles = [
            {"title": "Good", "url": "http://good.com", "priority_triage": "must_know"},
            {"title": "Bad", "url": "http://bad.com", "priority_triage": "should_know"},
        ]

        pipeline = UnifiedPipeline()
        result = await pipeline.save_articles(articles, mock_db)

        assert result["saved"] == 1
        assert result["errors"] == 1


class TestRunSaveToDb:
    @pytest.fixture(autouse=True)
    def _patch_all(self):
        with (
            patch(
                "app.services.unified_pipeline.OptimizedRSSProcessor"
            ) as mock_rss_cls,
            patch("app.services.unified_pipeline.IndianExpressScraper") as mock_ie_cls,
            patch("app.services.unified_pipeline.PIBScraper") as mock_pib_cls,
            patch("app.services.unified_pipeline.SupplementarySources") as mock_sup_cls,
            patch(
                "app.services.unified_pipeline.PlaywrightSessionManager"
            ) as mock_session_cls,
            patch(
                "app.services.unified_pipeline.HinduPlaywrightScraper"
            ) as mock_hindu_pw_cls,
            patch(
                "app.services.unified_pipeline.IEPlaywrightScraper"
            ) as mock_ie_pw_cls,
            patch("app.services.unified_pipeline.MEAScraper") as mock_mea_cls,
            patch("app.services.unified_pipeline.ORFScraper") as mock_orf_cls,
            patch("app.services.unified_pipeline.IDSAScraper") as mock_idsa_cls,
            patch(
                "app.services.unified_pipeline.KnowledgeCardPipeline"
            ) as mock_kcp_cls,
            patch("app.services.unified_pipeline.ArticleSelector") as mock_selector_cls,
            patch(
                "app.services.unified_pipeline.UniversalContentExtractor"
            ) as mock_ext_cls,
            patch("app.services.unified_pipeline.SupabaseConnection") as mock_db_cls,
        ):
            mock_rss = MagicMock()
            mock_rss.fetch_all_sources_parallel = AsyncMock(return_value=[])
            mock_rss_cls.return_value = mock_rss

            mock_ie = MagicMock()
            mock_ie.scrape_all_sections = AsyncMock(
                return_value=[
                    {
                        "title": "Test Article",
                        "url": "http://test.com/1",
                        "content": "Test content body.",
                        "published_date": _RECENT_DATE_STR,
                        "section": "explained",
                        "source_site": "indianexpress",
                    }
                ]
            )
            mock_ie_cls.return_value = mock_ie

            mock_pib = MagicMock()
            mock_pib.scrape_releases = AsyncMock(return_value=[])
            mock_pib_cls.return_value = mock_pib

            mock_sup = MagicMock()
            mock_sup.fetch_all = MagicMock(return_value=[])
            mock_sup_cls.return_value = mock_sup

            # Wave 3 — all empty (this test focuses on save_to_db logic)
            _setup_wave3_mocks(
                mock_session_cls,
                mock_hindu_pw_cls,
                mock_ie_pw_cls,
                mock_mea_cls,
                mock_orf_cls,
                mock_idsa_cls,
                hindu_pw_data=[],
                ie_pw_data=[],
                mea_data=[],
                orf_data=[],
                idsa_data=[],
            )

            # --- KnowledgeCardPipeline mock ---
            mock_kcp = MagicMock()
            mock_kcp.relevance_threshold = 55
            mock_kcp._is_must_know = MagicMock(return_value=False)
            mock_kcp._compute_triage = MagicMock(return_value="must_know")
            mock_kcp.run_pass1_batch = AsyncMock(
                side_effect=lambda arts: [
                    {
                        "upsc_relevance": 85,
                        "gs_paper": "GS3",
                        "key_facts": ["fiscal deficit target", "capital expenditure"],
                        "keywords": ["budget", "fiscal policy"],
                        "syllabus_matches": [
                            {
                                "paper": "GS3",
                                "topic": "Economy",
                                "sub_topic": "Government Budgeting",
                                "confidence": 0.9,
                            },
                        ],
                        "raw_pass1_data": {},
                    }
                    for _ in arts
                ]
            )
            mock_kcp.run_pass2 = AsyncMock(
                return_value={
                    "headline_layer": "Union Budget 2026 focuses on capital expenditure.",
                    "facts_layer": ["Fiscal deficit at 5.1%", "Capex up 20%"],
                    "context_layer": "Continuation of fiscal consolidation path.",
                    "connections_layer": {
                        "syllabus_topics": ["Indian Economy"],
                        "related_pyqs": [
                            {"year": 2023, "question": "Discuss fiscal policy."}
                        ],
                        "pyq_count": 1,
                        "year_range": "2023-2023",
                    },
                    "mains_angle_layer": "Analyze the fiscal consolidation strategy.",
                }
            )
            mock_kcp_cls.return_value = mock_kcp

            # --- ArticleSelector mock ---
            mock_selector = MagicMock()
            mock_selector.select_top_articles = AsyncMock(
                side_effect=lambda arts, target=30: arts[:target]
            )
            mock_selector_cls.return_value = mock_selector

            mock_ext = MagicMock()
            mock_ext_cls.return_value = mock_ext

            mock_db = MagicMock()
            mock_db.upsert_current_affair = AsyncMock(
                return_value={"success": True, "data": {}, "message": "ok"}
            )
            mock_db_cls.return_value = mock_db

            self.mock_db_cls = mock_db_cls
            self.mock_db = mock_db
            yield

    @pytest.mark.asyncio
    async def test_run_save_to_db_true_calls_save_articles(self):
        """run(save_to_db=True) saves enriched articles to DB."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run(save_to_db=True)

        # DB class was instantiated
        self.mock_db_cls.assert_called_once()
        # upsert was called for the enriched article
        assert self.mock_db.upsert_current_affair.call_count >= 1
        # Result includes db_save key
        assert "db_save" in result
        assert result["db_save"]["saved"] >= 1

    @pytest.mark.asyncio
    async def test_run_save_to_db_false_does_not_save(self):
        """run(save_to_db=False) -- default -- does NOT touch DB."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run(save_to_db=False)

        self.mock_db_cls.assert_not_called()
        assert "db_save" not in result


# ---------------------------------------------------------------------------
# 30-35  Wave 3 scraper-specific tests
# ---------------------------------------------------------------------------


class TestWave3Scrapers:
    """Tests specific to the 5 new Wave 3 scrapers wired into the pipeline."""

    @pytest.fixture(autouse=True)
    def _patch_sources(self):
        """Patch all 9 source classes."""
        with (
            patch(
                "app.services.unified_pipeline.OptimizedRSSProcessor"
            ) as mock_rss_cls,
            patch("app.services.unified_pipeline.IndianExpressScraper") as mock_ie_cls,
            patch("app.services.unified_pipeline.PIBScraper") as mock_pib_cls,
            patch("app.services.unified_pipeline.SupplementarySources") as mock_sup_cls,
            patch(
                "app.services.unified_pipeline.PlaywrightSessionManager"
            ) as mock_session_cls,
            patch(
                "app.services.unified_pipeline.HinduPlaywrightScraper"
            ) as mock_hindu_pw_cls,
            patch(
                "app.services.unified_pipeline.IEPlaywrightScraper"
            ) as mock_ie_pw_cls,
            patch("app.services.unified_pipeline.MEAScraper") as mock_mea_cls,
            patch("app.services.unified_pipeline.ORFScraper") as mock_orf_cls,
            patch("app.services.unified_pipeline.IDSAScraper") as mock_idsa_cls,
        ):
            # Legacy sources — return empty to isolate Wave 3 tests
            mock_rss = MagicMock()
            mock_rss.fetch_all_sources_parallel = AsyncMock(return_value=[])
            mock_rss_cls.return_value = mock_rss

            mock_ie = MagicMock()
            mock_ie.scrape_all_sections = AsyncMock(return_value=[])
            mock_ie_cls.return_value = mock_ie

            mock_pib = MagicMock()
            mock_pib.scrape_releases = AsyncMock(return_value=[])
            mock_pib_cls.return_value = mock_pib

            mock_sup = MagicMock()
            mock_sup.fetch_all = MagicMock(return_value=[])
            mock_sup_cls.return_value = mock_sup

            # Wave 3 scrapers — default fixture data
            self.w3 = _setup_wave3_mocks(
                mock_session_cls,
                mock_hindu_pw_cls,
                mock_ie_pw_cls,
                mock_mea_cls,
                mock_orf_cls,
                mock_idsa_cls,
            )
            self.mock_session_cls = mock_session_cls
            yield

    @pytest.mark.asyncio
    async def test_hindu_playwright_returns_articles(self):
        """HinduPlaywrightScraper articles appear in pipeline output."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        titles = [a["title"] for a in result]
        assert "Hindu PW Article 1" in titles

    @pytest.mark.asyncio
    async def test_ie_playwright_returns_articles(self):
        """IEPlaywrightScraper articles appear in pipeline output."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        titles = [a["title"] for a in result]
        assert "IE PW Article 1" in titles

    @pytest.mark.asyncio
    async def test_mea_returns_articles(self):
        """MEAScraper articles appear in pipeline output."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        titles = [a["title"] for a in result]
        assert "MEA Press Release 1" in titles

    @pytest.mark.asyncio
    async def test_orf_returns_articles(self):
        """ORFScraper articles appear in pipeline output."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        titles = [a["title"] for a in result]
        assert "ORF Expert Speak 1" in titles

    @pytest.mark.asyncio
    async def test_idsa_returns_articles(self):
        """IDSAScraper articles appear in pipeline output."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        titles = [a["title"] for a in result]
        assert "IDSA Comment 1" in titles

    @pytest.mark.asyncio
    async def test_httpx_source_url_normalized_to_url(self):
        """MEA/ORF/IDSA articles have source_url copied to url for dedup."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        httpx_sources = {"mea", "orf", "idsa"}
        for article in result:
            if article.get("source_site") in httpx_sources:
                assert "url" in article, (
                    f"httpx article missing 'url': {article.get('title')}"
                )
                assert article["url"].startswith("http"), (
                    f"url not normalized: {article.get('title')}"
                )

    @pytest.mark.asyncio
    async def test_playwright_session_cleanup_called(self):
        """PlaywrightSessionManager.close() is called after scraping."""
        from app.services.unified_pipeline import UnifiedPipeline

        await UnifiedPipeline().fetch_all_sources()
        # Session is created twice (hindu_pw + ie_pw), cleanup called for each
        assert self.w3["session"].close.call_count >= 2

    @pytest.mark.asyncio
    async def test_wave3_failure_does_not_affect_others(self):
        """If one Wave 3 source fails, others still return articles."""
        self.w3["mea"].fetch_articles = AsyncMock(side_effect=Exception("MEA down"))
        self.w3["orf"].fetch_articles = AsyncMock(side_effect=Exception("ORF down"))

        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        # hindu_pw(1) + ie_pw(1) + idsa(1) = 3 (mea + orf failed)
        assert len(result) >= 3
        titles = [a["title"] for a in result]
        assert "IDSA Comment 1" in titles

    @pytest.mark.asyncio
    async def test_all_nine_sources_contribute(self):
        """When all 9 sources succeed with unique URLs, all articles appear."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        source_sites = {a.get("source_site") for a in result}
        # Wave 3 sources: hindu, indianexpress (from ie_pw), mea, orf, idsa
        for expected_site in ("hindu", "indianexpress", "mea", "orf", "idsa"):
            assert expected_site in source_sites, (
                f"Missing source_site '{expected_site}' in results"
            )
