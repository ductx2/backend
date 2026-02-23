"""
TDD Tests for UnifiedPipeline (T13).
23 tests covering: imports, fetch, enrich, run, edge cases.
All source dependencies are mocked — no network calls.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


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
            "published_at": "2026-02-23T00:00:00Z",
            "content_hash": "h1",
            "raw_entry": {},
        },
        {
            "title": "Hindu Article 2",
            "content": "Another body.",
            "source": "The Hindu - Op-Ed",
            "source_url": "https://thehindu.com/oped/article2",
            "published_at": "2026-02-23T00:00:00Z",
            "content_hash": "h2",
            "raw_entry": {},
        },
    ]


def _ie_articles():
    return [
        {
            "title": "IE Article 1",
            "url": "https://indianexpress.com/article/ie1",
            "published_date": "2026-02-23",
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
            "published_date": "2026-02-23",
            "ministry": "Finance",
            "source_site": "pib",
        },
    ]


def _supplementary_articles():
    return [
        {
            "title": "Supplementary 1",
            "url": "https://livemint.com/sup1",
            "published_date": "2026-02-23",
            "author": "Author B",
            "section": "economy",
            "source_site": "livemint",
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
        """Patch all 4 source classes so no network calls happen."""
        with (
            patch(
                "app.services.unified_pipeline.OptimizedRSSProcessor"
            ) as mock_rss_cls,
            patch("app.services.unified_pipeline.IndianExpressScraper") as mock_ie_cls,
            patch("app.services.unified_pipeline.PIBScraper") as mock_pib_cls,
            patch("app.services.unified_pipeline.SupplementarySources") as mock_sup_cls,
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

            self.mock_rss = mock_rss
            self.mock_ie = mock_ie
            self.mock_pib = mock_pib
            self.mock_sup = mock_sup
            yield

    @pytest.mark.asyncio
    async def test_returns_list(self):
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_merges_all_four_sources(self):
        """Total = 2 hindu + 1 ie + 1 pib + 1 supplementary = 5."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().fetch_all_sources()
        assert len(result) == 5

    @pytest.mark.asyncio
    async def test_deduplicates_by_url(self):
        """If two articles share the same URL, only one survives."""
        self.mock_ie.scrape_all_sections = AsyncMock(
            return_value=[
                {
                    "title": "Duplicate",
                    "url": "https://thehindu.com/editorial/article1",  # same as Hindu #1
                    "published_date": "2026-02-23",
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
        # Hindu(2) + IE(1) + Supplementary(1) = 4, PIB failed
        assert len(result) >= 3

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
# 9-12  enrich_articles
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
# 13-20  run (integration of fetch + extract + enrich)
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
                "app.services.unified_pipeline.KnowledgeCardPipeline"
            ) as mock_kcp_cls,
            patch(
                "app.services.unified_pipeline.UniversalContentExtractor"
            ) as mock_ext_cls,
        ):
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

            mock_kcp = MagicMock()
            mock_kcp.process_article = AsyncMock(return_value=_enriched_article())
            mock_kcp_cls.return_value = mock_kcp

            mock_ext = MagicMock()
            extracted = MagicMock()
            extracted.content = "Extracted content from URL."
            mock_ext.extract_content = MagicMock(return_value=extracted)
            mock_ext_cls.return_value = mock_ext

            self.mock_rss = mock_rss
            self.mock_ie = mock_ie
            self.mock_pib = mock_pib
            self.mock_sup = mock_sup
            self.mock_kcp = mock_kcp
            self.mock_ext = mock_ext
            yield

    @pytest.mark.asyncio
    async def test_returns_summary_dict(self):
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run()
        assert isinstance(result, dict)
        for key in ("articles", "total_fetched", "total_enriched", "filtered"):
            assert key in result, f"Missing key: {key}"

    @pytest.mark.asyncio
    async def test_correct_counts(self):
        """5 fetched, all enriched (none filtered) → enriched=5, filtered=0."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run()
        assert result["total_fetched"] == 5
        assert result["total_enriched"] == 5
        assert result["filtered"] == 0

    @pytest.mark.asyncio
    async def test_max_articles_cap(self):
        """run(max_articles=2) should only process 2 articles."""
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run(max_articles=2)
        assert result["total_fetched"] <= 2
        assert len(result["articles"]) <= 2

    @pytest.mark.asyncio
    async def test_content_extraction_for_no_content_articles(self):
        """IE/PIB/Supplementary articles lack 'content' → extractor called."""
        from app.services.unified_pipeline import UnifiedPipeline

        await UnifiedPipeline().run()
        # 3 articles have no content: IE(1) + PIB(1) + Supplementary(1)
        assert self.mock_ext.extract_content.call_count >= 3

    @pytest.mark.asyncio
    async def test_skip_extraction_for_articles_with_content(self):
        """Hindu articles already have content → extractor NOT called for them."""
        # Make only Hindu articles available
        self.mock_ie.scrape_all_sections = AsyncMock(return_value=[])
        self.mock_pib.scrape_releases = AsyncMock(return_value=[])
        self.mock_sup.fetch_all = MagicMock(return_value=[])

        from app.services.unified_pipeline import UnifiedPipeline

        await UnifiedPipeline().run()
        assert self.mock_ext.extract_content.call_count == 0

    @pytest.mark.asyncio
    async def test_extraction_failure_does_not_crash(self):
        """If content extraction raises, article is skipped gracefully."""
        self.mock_ext.extract_content = MagicMock(side_effect=Exception("Timeout"))
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run()
        # Hindu articles (2) still have content → should still be enriched
        assert result["total_enriched"] >= 2

    @pytest.mark.asyncio
    async def test_process_article_exception_does_not_crash(self):
        """If KnowledgeCardPipeline.process_article raises for one article, others still processed."""
        call_count = 0

        async def side_effect_fn(article):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("LLM timeout")
            return _enriched_article(title=article.get("title", "?"))

        self.mock_kcp.process_article = AsyncMock(side_effect=side_effect_fn)
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run()
        # 5 articles total, 1 failed → at least 4 enriched
        assert result["total_enriched"] >= 4

    @pytest.mark.asyncio
    async def test_enriched_articles_in_result(self):
        from app.services.unified_pipeline import UnifiedPipeline

        result = await UnifiedPipeline().run()
        assert len(result["articles"]) == result["total_enriched"]
        assert all(isinstance(a, dict) for a in result["articles"])


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
                        "published_date": "2026-02-23",
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
                        "published_date": "2026-02-23",
                        "ministry": "Y",
                        "source_site": "pib",
                    },
                ]
            )
            mock_pib_cls.return_value = mock_pib

            mock_sup = MagicMock()
            mock_sup.fetch_all = MagicMock(return_value=[])
            mock_sup_cls.return_value = mock_sup

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
        "published_date": "2026-02-23",
        "content": "The Union Budget 2026 was presented today.",
        # Pass 1
        "upsc_relevance": 85,
        "gs_paper": "GS3",
        "key_facts": ["fiscal deficit target", "capital expenditure"],
        "keywords": ["budget", "fiscal policy"],
        "syllabus_matches": [
            {"paper": "GS3", "topic": "Economy", "sub_topic": "Government Budgeting", "confidence": 0.9},
        ],
        "priority_triage": "must_know",
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
        assert db_row["date"] == "2026-02-23"

        # Analysis fields
        assert db_row["upsc_relevance"] == 85
        assert db_row["gs_paper"] == "GS3"
        assert db_row["tags"] == ["budget", "fiscal policy"]
        assert db_row["category"] == "gs3"
        assert db_row["importance"] == "high"  # must_know -> high

        # 5-layer fields
        assert db_row["headline_layer"] == "Union Budget 2026 focuses on capital expenditure."
        assert db_row["facts_layer"] == ["Fiscal deficit at 5.1%", "Capex up 20%"]
        assert db_row["context_layer"] == "Continuation of fiscal consolidation path."
        assert db_row["connections_layer"]["pyq_count"] == 1
        assert db_row["mains_angle_layer"] == "Analyze the fiscal consolidation strategy."
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
                "app.services.unified_pipeline.KnowledgeCardPipeline"
            ) as mock_kcp_cls,
            patch(
                "app.services.unified_pipeline.UniversalContentExtractor"
            ) as mock_ext_cls,
            patch(
                "app.services.unified_pipeline.SupabaseConnection"
            ) as mock_db_cls,
        ):
            mock_rss = MagicMock()
            mock_rss.fetch_all_sources_parallel = AsyncMock(return_value=[])
            mock_rss_cls.return_value = mock_rss

            mock_ie = MagicMock()
            mock_ie.scrape_all_sections = AsyncMock(
                return_value=[{
                    "title": "Test Article",
                    "url": "http://test.com/1",
                    "content": "Test content body.",
                    "published_date": "2026-02-23",
                    "section": "explained",
                    "source_site": "indianexpress",
                }]
            )
            mock_ie_cls.return_value = mock_ie

            mock_pib = MagicMock()
            mock_pib.scrape_releases = AsyncMock(return_value=[])
            mock_pib_cls.return_value = mock_pib

            mock_sup = MagicMock()
            mock_sup.fetch_all = MagicMock(return_value=[])
            mock_sup_cls.return_value = mock_sup

            mock_kcp = MagicMock()
            mock_kcp.process_article = AsyncMock(
                return_value=_enriched_knowledge_card_article()
            )
            mock_kcp_cls.return_value = mock_kcp

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
