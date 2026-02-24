"""
T16: Integration tests for UnifiedPipeline.run() end-to-end flow.

These tests mock at method-boundary level (fetch_all_sources, KnowledgeCardPipeline,
ArticleSelector, save_articles) — NOT at class-import level like the unit tests.
Goal: catch wiring bugs between stages (wrong keys, wrong counts, missing
result keys, DB save not triggered).

Updated for batch-score-tournament flow in run():
  fetch_all_sources → _filter_by_date → content extraction →
  run_pass1_batch → threshold filter → select_top_articles →
  run_pass2 per article → build result dict
"""

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Dynamic date that always passes the 36-hour filter
_RECENT_DATE_ISO = datetime.now(timezone.utc).isoformat()


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
        "published_date": _RECENT_DATE_ISO,
    }
    if content is not None:
        article["content"] = content
    return article


def _make_pass1_result(
    upsc_relevance: int = 82,
    gs_paper: str = "GS3",
) -> dict:
    """Pass 1 result dict as returned by KnowledgeCardPipeline.run_pass1_batch."""
    return {
        "upsc_relevance": upsc_relevance,
        "gs_paper": gs_paper,
        "key_facts": ["key fact 1", "key fact 2"],
        "keywords": ["economy", "budget"],
        "syllabus_matches": [
            {
                "paper": gs_paper,
                "topic": "Economy",
                "sub_topic": "Fiscal Policy",
                "confidence": 0.9,
            }
        ],
        "raw_pass1_data": {
            "upsc_relevance": upsc_relevance,
            "relevant_papers": [gs_paper],
            "summary": "Test article summary.",
        },
    }


def _make_pass2_result() -> dict:
    """Pass 2 result dict as returned by KnowledgeCardPipeline.run_pass2."""
    return {
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


@contextmanager
def _patch_pipeline_internals(
    raw_articles: list[dict],
    *,
    pass1_results: list[dict] | None = None,
    pass2_result: dict | None = None,
    selected_articles: list[dict] | None = None,
    mock_extractor: MagicMock | None = None,
    mock_db: MagicMock | None = None,
):
    """Context manager that patches all internals of run() for integration tests.

    - fetch_all_sources → returns raw_articles
    - _filter_by_date → pass-through (dynamic dates already handle this)
    - KnowledgeCardPipeline → mock run_pass1_batch, run_pass2, _is_must_know, etc.
    - ArticleSelector → mock select_top_articles (pass-through by default)
    - UniversalContentExtractor → optional mock
    - SupabaseConnection → optional mock
    """
    from app.services.unified_pipeline import UnifiedPipeline

    # Build pass1_results matching the number of articles with content
    if pass1_results is None:
        # Default: one pass1 result per raw article that has content
        n = sum(1 for a in raw_articles if a.get("content"))
        pass1_results = [_make_pass1_result() for _ in range(n)]

    if pass2_result is None:
        pass2_result = _make_pass2_result()

    # Mock KnowledgeCardPipeline
    mock_kcp = MagicMock()
    mock_kcp.run_pass1_batch = AsyncMock(return_value=pass1_results)
    mock_kcp.run_pass2 = AsyncMock(return_value=pass2_result)
    mock_kcp.relevance_threshold = 55
    mock_kcp._is_must_know = MagicMock(return_value=True)  # all pass threshold
    mock_kcp._compute_triage = MagicMock(return_value="must_know")

    # Mock ArticleSelector — pass-through or custom
    mock_selector = MagicMock()
    if selected_articles is not None:
        mock_selector.select_top_articles = AsyncMock(return_value=selected_articles)
    else:
        # Pass-through: return whatever was given
        mock_selector.select_top_articles = AsyncMock(
            side_effect=lambda articles, target=30: articles
        )

    patches = [
        patch.object(
            UnifiedPipeline,
            "fetch_all_sources",
            new=AsyncMock(return_value=raw_articles),
        ),
        patch(
            "app.services.unified_pipeline.KnowledgeCardPipeline",
            return_value=mock_kcp,
        ),
        patch(
            "app.services.unified_pipeline.ArticleSelector",
            return_value=mock_selector,
        ),
    ]

    if mock_extractor is not None:
        patches.append(
            patch(
                "app.services.unified_pipeline.UniversalContentExtractor",
                return_value=mock_extractor,
            )
        )

    if mock_db is not None:
        patches.append(
            patch(
                "app.services.unified_pipeline.SupabaseConnection",
                return_value=mock_db,
            )
        )

    # Start all patches
    started = [p.start() for p in patches]
    try:
        yield {
            "kcp": mock_kcp,
            "selector": mock_selector,
            "extractor": mock_extractor,
            "db": mock_db,
        }
    finally:
        for p in patches:
            p.stop()


# ---------------------------------------------------------------------------
# Class 1: TestIntegrationFullPipeline
# ---------------------------------------------------------------------------


class TestIntegrationFullPipeline:
    """Run UnifiedPipeline().run() with internal components patched.
    Verify the complete result shape."""

    @pytest.mark.asyncio
    async def test_result_contains_all_required_keys(self):
        """result must have articles, total_fetched, total_enriched, filtered."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [_make_raw_article(content="Body text")]

        with _patch_pipeline_internals(raw):
            result = await UnifiedPipeline().run()

        for key in ("articles", "total_fetched", "total_enriched", "filtered"):
            assert key in result, f"Missing required key: {key}"

    @pytest.mark.asyncio
    async def test_result_contains_new_metrics_keys(self):
        """result must also have pass1_count, pass2_count, gs_distribution, llm_calls."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [_make_raw_article(content="Body text")]

        with _patch_pipeline_internals(raw):
            result = await UnifiedPipeline().run()

        for key in ("pass1_count", "pass2_count", "gs_distribution", "llm_calls"):
            assert key in result, f"Missing new metric key: {key}"

    @pytest.mark.asyncio
    async def test_counts_are_self_consistent(self):
        """total_fetched == total_enriched + filtered."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [
            _make_raw_article(title=f"Art {i}", url=f"https://t.com/{i}", content="c")
            for i in range(5)
        ]

        # All 5 get pass1 results, but selector only returns 1
        pass1 = [_make_pass1_result() for _ in range(5)]
        selected = [
            _make_raw_article(title="Art 0", url="https://t.com/0", content="c")
        ]
        # Merge pass1 data into selected for pass2 to work
        for key, val in _make_pass1_result().items():
            selected[0][key] = val

        with _patch_pipeline_internals(
            raw, pass1_results=pass1, selected_articles=selected
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

        with _patch_pipeline_internals(raw):
            result = await UnifiedPipeline().run()

        assert isinstance(result["articles"], list)
        assert all(isinstance(a, dict) for a in result["articles"])

    @pytest.mark.asyncio
    async def test_enriched_articles_have_all_five_layer_keys(self):
        """Each article in result must have all 5-layer knowledge card keys."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [_make_raw_article(content="Body")]

        with _patch_pipeline_internals(raw):
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
    async def test_filtered_increases_when_selection_drops_articles(self):
        """When selector returns fewer articles than fetched,
        filtered count increases accordingly."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [
            _make_raw_article(title=f"Art {i}", url=f"https://t.com/{i}", content="c")
            for i in range(10)
        ]

        pass1 = [_make_pass1_result() for _ in range(10)]

        # Only 3 survive selection
        selected = []
        for i in range(3):
            art = _make_raw_article(
                title=f"Art {i}", url=f"https://t.com/{i}", content="c"
            )
            art.update(_make_pass1_result())
            selected.append(art)

        with _patch_pipeline_internals(
            raw, pass1_results=pass1, selected_articles=selected
        ):
            result = await UnifiedPipeline().run()

        assert result["total_enriched"] == 3
        assert result["filtered"] == 7


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

        mock_db = MagicMock()
        mock_db.upsert_current_affair = AsyncMock(
            return_value={"success": True, "data": {}, "message": "ok"}
        )

        with _patch_pipeline_internals(raw, mock_db=mock_db):
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

        with _patch_pipeline_internals(raw):
            result = await UnifiedPipeline().run(save_to_db=False)

        assert "db_save" not in result

    @pytest.mark.asyncio
    async def test_save_to_db_true_all_filtered_no_db_connection(self):
        """When save_to_db=True but all articles fail pass2 (0 enriched),
        SupabaseConnection is NOT instantiated (no wasted DB connection)."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [_make_raw_article(content="Body")]

        # Make run_pass2 raise so 0 articles are enriched
        mock_kcp = MagicMock()
        mock_kcp.run_pass1_batch = AsyncMock(return_value=[_make_pass1_result()])
        mock_kcp.run_pass2 = AsyncMock(side_effect=Exception("Pass2 failure"))
        mock_kcp.relevance_threshold = 55
        mock_kcp._is_must_know = MagicMock(return_value=True)
        mock_kcp._compute_triage = MagicMock(return_value="must_know")

        mock_selector = MagicMock()
        mock_selector.select_top_articles = AsyncMock(
            side_effect=lambda articles, target=30: articles
        )

        with (
            patch.object(
                UnifiedPipeline,
                "fetch_all_sources",
                new=AsyncMock(return_value=raw),
            ),
            patch(
                "app.services.unified_pipeline.KnowledgeCardPipeline",
                return_value=mock_kcp,
            ),
            patch(
                "app.services.unified_pipeline.ArticleSelector",
                return_value=mock_selector,
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

        mock_db = MagicMock()
        mock_db.upsert_current_affair = AsyncMock(
            return_value={"success": True, "data": {}, "message": "ok"}
        )

        with _patch_pipeline_internals(raw, mock_db=mock_db):
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

        mock_extractor = MagicMock()
        mock_extractor.extract_content = MagicMock()

        with _patch_pipeline_internals(raw, mock_extractor=mock_extractor):
            await UnifiedPipeline().run()

        mock_extractor.extract_content.assert_not_called()

    @pytest.mark.asyncio
    async def test_articles_without_content_trigger_extractor(self):
        """Articles without 'content' but with 'url' → extractor called,
        extracted content attached, article sent to pass1."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [_make_raw_article(title="No Content", url="https://t.com/1")]
        # No content key at all

        extracted_mock = MagicMock()
        extracted_mock.content = "Extracted body text."

        mock_extractor = MagicMock()
        mock_extractor.extract_content = MagicMock(return_value=extracted_mock)

        # We need pass1 to return 1 result (since extractor will provide content)
        pass1 = [_make_pass1_result()]

        with _patch_pipeline_internals(
            raw, pass1_results=pass1, mock_extractor=mock_extractor
        ) as mocks:
            await UnifiedPipeline().run()

        # Extractor was called with the URL
        mock_extractor.extract_content.assert_called_once_with("https://t.com/1")

        # Verify run_pass1_batch received the article with extracted content
        call_args = mocks["kcp"].run_pass1_batch.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0]["content"] == "Extracted body text."

    @pytest.mark.asyncio
    async def test_articles_without_content_and_url_are_skipped(self):
        """Articles without 'content' AND without 'url' are skipped entirely."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [
            {
                "title": "No Content No URL",
                "source_site": "test",
                "section": "gen",
                "published_date": _RECENT_DATE_ISO,
            },
        ]

        mock_extractor = MagicMock()
        mock_extractor.extract_content = MagicMock()

        # 0 articles reach pass1 (all skipped)
        pass1: list[dict] = []

        with _patch_pipeline_internals(
            raw, pass1_results=pass1, mock_extractor=mock_extractor
        ) as mocks:
            await UnifiedPipeline().run()

        # Extractor never called (no URL to extract from)
        mock_extractor.extract_content.assert_not_called()

        # run_pass1_batch receives empty list (article was skipped)
        articles_sent = mocks["kcp"].run_pass1_batch.call_args[0][0]
        assert len(articles_sent) == 0

    @pytest.mark.asyncio
    async def test_extractor_error_does_not_block_other_articles(self):
        """If extractor raises for one article, other articles still processed."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [
            _make_raw_article(title="Fails", url="https://t.com/fail"),
            _make_raw_article(
                title="Has Content", url="https://t.com/ok", content="Body"
            ),
        ]

        mock_extractor = MagicMock()
        mock_extractor.extract_content = MagicMock(
            side_effect=Exception("Network timeout")
        )

        # Only 1 article (the one with content) reaches pass1
        pass1 = [_make_pass1_result()]

        with _patch_pipeline_internals(
            raw, pass1_results=pass1, mock_extractor=mock_extractor
        ) as mocks:
            result = await UnifiedPipeline().run()

        # The article with content should still be forwarded to pass1
        articles_sent = mocks["kcp"].run_pass1_batch.call_args[0][0]
        assert len(articles_sent) == 1
        assert articles_sent[0]["title"] == "Has Content"


# ---------------------------------------------------------------------------
# Class 4: TestIntegrationPipelineConfig
# ---------------------------------------------------------------------------


class TestIntegrationPipelineConfig:
    """Test configuration behavior of UnifiedPipeline.run()."""

    @pytest.mark.asyncio
    async def test_max_articles_passed_to_selector(self):
        """run(max_articles=3) passes target=3 to ArticleSelector.select_top_articles."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [
            _make_raw_article(title=f"Art {i}", url=f"https://t.com/{i}", content="c")
            for i in range(10)
        ]

        pass1 = [_make_pass1_result() for _ in range(10)]

        with _patch_pipeline_internals(raw, pass1_results=pass1) as mocks:
            result = await UnifiedPipeline().run(max_articles=3)

        # Verify selector was called with target=3
        call_kwargs = mocks["selector"].select_top_articles.call_args
        assert call_kwargs[1].get("target") == 3 or call_kwargs[0][1] == 3

    @pytest.mark.asyncio
    async def test_default_max_articles_no_crash_with_fewer(self):
        """run() with default max_articles (30) does not crash when only 2 available."""
        from app.services.unified_pipeline import UnifiedPipeline

        raw = [
            _make_raw_article(title="A", url="https://t.com/a", content="c"),
            _make_raw_article(title="B", url="https://t.com/b", content="c"),
        ]
        pass1 = [_make_pass1_result(), _make_pass1_result()]

        with _patch_pipeline_internals(raw, pass1_results=pass1):
            result = await UnifiedPipeline().run()  # default max_articles=30

        assert result["total_fetched"] == 2
        # Both pass through (selector pass-through, both get pass2)
        assert result["total_enriched"] == 2

    def test_max_articles_default_constant_is_importable(self):
        """_MAX_ARTICLES_DEFAULT is importable and equals 30."""
        from app.services.unified_pipeline import _MAX_ARTICLES_DEFAULT

        assert _MAX_ARTICLES_DEFAULT == 30
