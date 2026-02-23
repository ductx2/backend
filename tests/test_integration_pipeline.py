"""
T16: Integration tests for UnifiedPipeline.run() end-to-end flow.

These tests mock at method-boundary level (fetch_all_sources, enrich_articles,
save_articles) — NOT at class-import level like the unit tests.
Goal: catch wiring bugs between stages (wrong keys, wrong counts, missing
result keys, DB save not triggered).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


def _make_raw_article(
    title: str = "Test Article",
    url: str = "https://test.com/article",
    source_site: str = "indianexpress",
    section: str = "explained",
    content: str | None = None,
) -> dict:
    """Raw article as returned by fetch_all_sources."""
    article: dict = {
        "title": title,
        "url": url,
        "source_site": source_site,
        "section": section,
        "published_date": "2026-02-23",
    }
    if content is not None:
        article["content"] = content
    return article


def _make_enriched_article(
    title: str = "Test Article",
    url: str = "https://test.com/article",
) -> dict:
    """Enriched article as produced by KnowledgeCardPipeline.process_article."""
    return {
        "title": title,
        "url": url,
        "source_site": "indianexpress",
        "section": "explained",
        "published_date": "2026-02-23",
        "content": "Full article content text.",
        # Pass 1 fields
        "upsc_relevance": 82,
        "gs_paper": "GS3",
        "key_facts": ["key fact 1", "key fact 2"],
        "keywords": ["economy", "budget"],
        "syllabus_matches": [
            {
                "paper": "GS3",
                "topic": "Economy",
                "sub_topic": "Fiscal Policy",
                "confidence": 0.9,
            }
        ],
        "priority_triage": "must_know",
        # Pass 2 (5-layer fields)
        "headline_layer": "Test headline for the article.",
        "facts_layer": ["Fact 1", "Fact 2"],
        "context_layer": "Context for the article.",
        "connections_layer": {
            "syllabus_topics": ["Economy"],
            "related_pyqs": [],
            "pyq_count": 0,
            "year_range": "",
        },
        "mains_angle_layer": "Mains angle for the article.",
    }


# ---------------------------------------------------------------------------
# Class 1: TestIntegrationFullPipeline
# ---------------------------------------------------------------------------


class TestIntegrationFullPipeline:
    """Run UnifiedPipeline().run() with fetch_all_sources + enrich_articles
    patched at the method level. Verify the complete result shape."""

    @pytest.mark.asyncio
    async def test_result_contains_all_required_keys(self):
        """result must have articles, total_fetched, total_enriched, filtered."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [_make_raw_article(content="Body text")]
        enriched = [_make_enriched_article()]

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=AsyncMock(return_value=enriched),
            ),
        ):
            result = await UnifiedPipeline().run()

        for key in ("articles", "total_fetched", "total_enriched", "filtered"):
            assert key in result, f"Missing required key: {key}"

    @pytest.mark.asyncio
    async def test_counts_are_self_consistent(self):
        """total_fetched == total_enriched + filtered."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [
            _make_raw_article(title=f"Art {i}", url=f"https://t.com/{i}", content="c")
            for i in range(5)
        ]
        enriched = [_make_enriched_article(title="Art 0", url="https://t.com/0")]

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=AsyncMock(return_value=enriched),
            ),
        ):
            result = await UnifiedPipeline().run()

        assert result["total_fetched"] == result["total_enriched"] + result["filtered"]
        assert result["total_fetched"] == 5
        assert result["total_enriched"] == 1
        assert result["filtered"] == 4

    @pytest.mark.asyncio
    async def test_articles_is_list_of_dicts(self):
        """result['articles'] is a list where every element is a dict."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [_make_raw_article(content="Body")]
        enriched = [_make_enriched_article()]

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=AsyncMock(return_value=enriched),
            ),
        ):
            result = await UnifiedPipeline().run()

        assert isinstance(result["articles"], list)
        assert all(isinstance(a, dict) for a in result["articles"])

    @pytest.mark.asyncio
    async def test_enriched_articles_have_all_five_layer_keys(self):
        """Each article in result must have all 5-layer knowledge card keys."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [_make_raw_article(content="Body")]
        enriched = [_make_enriched_article()]

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=AsyncMock(return_value=enriched),
            ),
        ):
            result = await UnifiedPipeline().run()

        five_layer_keys = (
            "headline_layer",
            "facts_layer",
            "context_layer",
            "connections_layer",
            "mains_angle_layer",
        )
        for article in result["articles"]:
            for key in five_layer_keys:
                assert key in article, (
                    f"Article '{article.get('title')}' missing 5-layer key: {key}"
                )

    @pytest.mark.asyncio
    async def test_filtered_increases_when_enrichment_drops_articles(self):
        """When enrich_articles returns fewer articles than fetched,
        filtered count increases accordingly."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [
            _make_raw_article(title=f"Art {i}", url=f"https://t.com/{i}", content="c")
            for i in range(10)
        ]
        # Only 3 survive enrichment
        enriched = [
            _make_enriched_article(title=f"Art {i}", url=f"https://t.com/{i}")
            for i in range(3)
        ]

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=AsyncMock(return_value=enriched),
            ),
        ):
            result = await UnifiedPipeline().run()

        assert result["filtered"] == 7
        assert result["total_enriched"] == 3


# ---------------------------------------------------------------------------
# Class 2: TestIntegrationDbStorage
# ---------------------------------------------------------------------------


class TestIntegrationDbStorage:
    """Verify DB storage wiring: save_to_db flag, db_save key shape,
    SupabaseConnection instantiation, and DB row field mapping."""

    @pytest.mark.asyncio
    async def test_save_to_db_true_produces_db_save_key(self):
        """run(save_to_db=True) → result has db_save with saved/errors counts."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [_make_raw_article(content="Body")]
        enriched = [_make_enriched_article()]

        mock_db = MagicMock()
        mock_db.upsert_current_affair = AsyncMock(
            return_value={"success": True, "data": {}, "message": "ok"}
        )

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=AsyncMock(return_value=enriched),
            ),
            patch(
                "app.services.unified_pipeline.SupabaseConnection",
                return_value=mock_db,
            ),
        ):
            result = await UnifiedPipeline().run(save_to_db=True)

        assert "db_save" in result
        assert "saved" in result["db_save"]
        assert "errors" in result["db_save"]
        assert result["db_save"]["saved"] == 1

    @pytest.mark.asyncio
    async def test_save_to_db_false_no_db_save_key(self):
        """run(save_to_db=False) → result does NOT have db_save key."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [_make_raw_article(content="Body")]
        enriched = [_make_enriched_article()]

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=AsyncMock(return_value=enriched),
            ),
        ):
            result = await UnifiedPipeline().run(save_to_db=False)

        assert "db_save" not in result

    @pytest.mark.asyncio
    async def test_save_to_db_true_all_filtered_no_db_connection(self):
        """When save_to_db=True but all articles filtered (0 enriched),
        SupabaseConnection is NOT instantiated (no wasted DB connection)."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [_make_raw_article(content="Body")]
        enriched: list[dict] = []  # All filtered

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=AsyncMock(return_value=enriched),
            ),
            patch(
                "app.services.unified_pipeline.SupabaseConnection",
            ) as mock_db_cls,
        ):
            result = await UnifiedPipeline().run(save_to_db=True)

        mock_db_cls.assert_not_called()
        assert "db_save" not in result

    @pytest.mark.asyncio
    async def test_db_row_has_correct_field_mapping(self):
        """DB row sent to upsert_current_affair uses source_url (not url),
        status='published', importance set from priority_triage."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [_make_raw_article(content="Body")]
        enriched = [_make_enriched_article()]

        mock_db = MagicMock()
        mock_db.upsert_current_affair = AsyncMock(
            return_value={"success": True, "data": {}, "message": "ok"}
        )

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=AsyncMock(return_value=enriched),
            ),
            patch(
                "app.services.unified_pipeline.SupabaseConnection",
                return_value=mock_db,
            ),
        ):
            await UnifiedPipeline().run(save_to_db=True)

        # Extract the db_row passed to upsert_current_affair
        db_row = mock_db.upsert_current_affair.call_args[0][0]

        assert db_row["source_url"] == "https://test.com/article"
        assert "url" not in db_row  # url should be mapped to source_url
        assert db_row["status"] == "published"
        assert db_row["importance"] == "high"  # must_know -> high


# ---------------------------------------------------------------------------
# Class 3: TestIntegrationContentExtraction
# ---------------------------------------------------------------------------


class TestIntegrationContentExtraction:
    """Test the content extraction wiring inside run()."""

    @pytest.mark.asyncio
    async def test_articles_with_content_bypass_extractor(self):
        """Articles that already have 'content' key should NOT trigger extractor."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [_make_raw_article(title="Has Content", content="Full body")]
        enriched = [_make_enriched_article()]

        mock_extractor = MagicMock()
        mock_extractor.extract_content = MagicMock()

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch(
                "app.services.unified_pipeline.UniversalContentExtractor",
                return_value=mock_extractor,
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=AsyncMock(return_value=enriched),
            ),
        ):
            await UnifiedPipeline().run()

        mock_extractor.extract_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_articles_without_content_trigger_extractor(self):
        """Articles without 'content' but with 'url' → extractor called,
        extracted content attached, article forwarded to enrichment."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [_make_raw_article(title="No Content", url="https://t.com/1")]
        # No content key at all

        extracted_mock = MagicMock()
        extracted_mock.content = "Extracted body text."

        mock_extractor = MagicMock()
        mock_extractor.extract_content = MagicMock(return_value=extracted_mock)

        # Capture what enrich_articles receives
        enrich_spy = AsyncMock(return_value=[_make_enriched_article()])

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch(
                "app.services.unified_pipeline.UniversalContentExtractor",
                return_value=mock_extractor,
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=enrich_spy,
            ),
        ):
            await UnifiedPipeline().run()

        # Extractor was called with the URL
        mock_extractor.extract_content.assert_called_once_with("https://t.com/1")

        # Article forwarded to enrichment with extracted content attached
        articles_sent = enrich_spy.call_args[0][0]
        assert len(articles_sent) == 1
        assert articles_sent[0]["content"] == "Extracted body text."

    @pytest.mark.asyncio
    async def test_articles_without_content_and_url_are_skipped(self):
        """Articles without 'content' AND without 'url' are skipped entirely."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [
            {"title": "No Content No URL", "source_site": "test",
             "section": "gen", "published_date": "2026-02-23"},
        ]

        mock_extractor = MagicMock()
        mock_extractor.extract_content = MagicMock()

        enrich_spy = AsyncMock(return_value=[])

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch(
                "app.services.unified_pipeline.UniversalContentExtractor",
                return_value=mock_extractor,
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=enrich_spy,
            ),
        ):
            await UnifiedPipeline().run()

        # Extractor never called (no URL to extract from)
        mock_extractor.extract_content.assert_not_called()

        # enrich_articles receives empty list (article was skipped)
        articles_sent = enrich_spy.call_args[0][0]
        assert len(articles_sent) == 0

    @pytest.mark.asyncio
    async def test_extractor_error_does_not_block_other_articles(self):
        """If extractor raises for one article, other articles still processed."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [
            _make_raw_article(title="Fails", url="https://t.com/fail"),
            _make_raw_article(title="Has Content", url="https://t.com/ok", content="Body"),
        ]

        mock_extractor = MagicMock()
        mock_extractor.extract_content = MagicMock(
            side_effect=Exception("Network timeout")
        )

        enrich_spy = AsyncMock(return_value=[_make_enriched_article()])

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch(
                "app.services.unified_pipeline.UniversalContentExtractor",
                return_value=mock_extractor,
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=enrich_spy,
            ),
        ):
            result = await UnifiedPipeline().run()

        # The article with content should still be forwarded to enrichment
        articles_sent = enrich_spy.call_args[0][0]
        assert len(articles_sent) == 1
        assert articles_sent[0]["title"] == "Has Content"


# ---------------------------------------------------------------------------
# Class 4: TestIntegrationPipelineConfig
# ---------------------------------------------------------------------------


class TestIntegrationPipelineConfig:
    """Test configuration behavior of UnifiedPipeline.run()."""

    @pytest.mark.asyncio
    async def test_max_articles_limits_fetch(self):
        """run(max_articles=3) limits articles to 3 even when sources return 10."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [
            _make_raw_article(title=f"Art {i}", url=f"https://t.com/{i}", content="c")
            for i in range(10)
        ]

        enrich_spy = AsyncMock(return_value=[])

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=enrich_spy,
            ),
        ):
            result = await UnifiedPipeline().run(max_articles=3)

        assert result["total_fetched"] == 3
        # enrich_articles received at most 3 articles
        articles_sent = enrich_spy.call_args[0][0]
        assert len(articles_sent) <= 3

    @pytest.mark.asyncio
    async def test_default_max_articles_no_crash_with_fewer(self):
        """run() with default max_articles (60) does not crash when only 2 available."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [
            _make_raw_article(title="A", url="https://t.com/a", content="c"),
            _make_raw_article(title="B", url="https://t.com/b", content="c"),
        ]
        enriched = [_make_enriched_article(title="A", url="https://t.com/a")]

        with (
            patch.object(
                UnifiedPipeline, "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch.object(
                UnifiedPipeline, "enrich_articles",
                new=AsyncMock(return_value=enriched),
            ),
        ):
            result = await UnifiedPipeline().run()  # default max_articles=60

        assert result["total_fetched"] == 2
        assert result["total_enriched"] == 1

    def test_max_articles_default_constant_is_importable(self):
        """_MAX_ARTICLES_DEFAULT is importable and equals 60."""
        from app.services.unified_pipeline import _MAX_ARTICLES_DEFAULT

        assert _MAX_ARTICLES_DEFAULT == 60