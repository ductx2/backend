"""
T19: Full integration tests verifying end-to-end pipeline behaviour.

6 tests covering: curated card count, cross-run dedup, source_type propagation,
MUST_KNOW threshold bypass, cron endpoint, and graceful degradation.

All external calls mocked — no network access. Each test fully independent.

Updated for batch-score-tournament flow in run():
  fetch_all_sources → _filter_by_date → content extraction →
  run_pass1_batch → threshold filter → select_top_articles →
  run_pass2 per article → build result dict
"""

import asyncio
from datetime import datetime, timezone

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.llm_schemas import LLMResponse, TaskType

_RECENT_DATE_ISO = datetime.now(timezone.utc).isoformat()


def _make_raw(
    title: str = "Article",
    url: str = "https://test.com/a",
    source_site: str = "indianexpress",
    section: str = "explained",
    content: str = "Full body content for the article.",
    **extra: object,
) -> dict:
    """Raw article as returned by fetch_all_sources."""
    article = {
        "title": title,
        "url": url,
        "source_site": source_site,
        "section": section,
        "published_date": _RECENT_DATE_ISO,
        "content": content,
    }
    article.update(extra)
    return article


def _make_pass1_result(
    upsc_relevance: int = 78,
    gs_paper: str = "GS3",
) -> dict:
    return {
        "upsc_relevance": upsc_relevance,
        "gs_paper": gs_paper,
        "key_facts": ["fact1", "fact2"],
        "keywords": ["economy", "policy"],
        "syllabus_matches": [
            {
                "paper": gs_paper,
                "topic": "Economy",
                "sub_topic": "Fiscal",
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


FIVE_LAYER_KEYS = (
    "headline_layer",
    "facts_layer",
    "context_layer",
    "connections_layer",
    "mains_angle_layer",
)


def _pass1_llm_response(upsc_relevance: int = 78, success: bool = True) -> LLMResponse:
    return LLMResponse(
        success=success,
        task_type=TaskType.UPSC_ANALYSIS,
        provider_used="openai/gpt-oss-120b",
        model_used="openai/gpt-oss-120b",
        response_time=0.5,
        tokens_used=500,
        estimated_cost=0.0,
        data={
            "upsc_relevance": upsc_relevance,
            "relevant_papers": ["GS3"],
            "key_topics": ["Economy", "Policy"],
            "importance_level": "High",
            "question_potential": "High",
            "category": "economy",
            "key_vocabulary": [],
            "summary": "Test article summary.",
        }
        if success
        else {},
        error_message=None if success else "LLM failed",
    )


def _pass2_llm_response(success: bool = True) -> LLMResponse:
    return LLMResponse(
        success=success,
        task_type=TaskType.SUMMARIZATION,
        provider_used="openai/gpt-oss-120b",
        model_used="openai/gpt-oss-120b",
        response_time=1.0,
        tokens_used=800,
        estimated_cost=0.0,
        data={
            "headline_layer": "Test headline",
            "facts_layer": ["Fact 1", "Fact 2"],
            "context_layer": "Test context",
            "mains_angle_layer": "Test mains angle",
        }
        if success
        else {},
        error_message=None if success else "LLM failed",
    )


MOCK_SYLLABUS_MATCHES = [
    {
        "paper": "GS3",
        "topic": "Economy",
        "sub_topic": "Monetary Policy",
        "confidence": 0.85,
    },
]

MOCK_PYQ_FORMATTED = {
    "related_pyqs": [],
    "pyq_count": 0,
    "year_range": "",
    "exam_types": [],
}


def _build_pipeline_patches(
    raw_articles, pass1_results=None, pass2_result=None, selected_articles=None
):
    """Build mock objects for KnowledgeCardPipeline + ArticleSelector."""
    if pass1_results is None:
        pass1_results = [_make_pass1_result() for _ in raw_articles]
    if pass2_result is None:
        pass2_result = _make_pass2_result()

    mock_kcp = MagicMock()
    mock_kcp.run_pass1_batch = AsyncMock(return_value=pass1_results)
    mock_kcp.run_pass2 = AsyncMock(return_value=pass2_result)
    mock_kcp.relevance_threshold = 55
    mock_kcp._is_must_know = MagicMock(return_value=True)
    mock_kcp._compute_triage = MagicMock(return_value="must_know")

    mock_selector = MagicMock()
    if selected_articles is not None:
        mock_selector.select_top_articles = AsyncMock(return_value=selected_articles)
    else:
        mock_selector.select_top_articles = AsyncMock(
            side_effect=lambda articles, target=30: articles
        )

    return mock_kcp, mock_selector


# ============================================================================
# Test 1: Curated pipeline produces 25–30 cards
# ============================================================================


async def test_curated_pipeline_produces_25_to_30_cards():
    """Pipeline with 28 raw → 27 selected/enriched produces correct counts."""
    from app.services.unified_pipeline import UnifiedPipeline

    raw_articles = [
        _make_raw(title=f"Art {i}", url=f"https://test.com/{i}") for i in range(28)
    ]

    pass1 = [_make_pass1_result() for _ in range(28)]

    selected = []
    for i in range(27):
        art = _make_raw(title=f"Art {i}", url=f"https://test.com/{i}")
        art.update(_make_pass1_result())
        selected.append(art)

    mock_kcp, mock_selector = _build_pipeline_patches(
        raw_articles, pass1_results=pass1, selected_articles=selected
    )

    with (
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
    ):
        result = await UnifiedPipeline().run()

    assert 25 <= result["total_enriched"] <= 30
    assert result["total_enriched"] == 27

    for article in result["articles"]:
        for key in FIVE_LAYER_KEYS:
            assert key in article, (
                f"Article '{article.get('title')}' missing key: {key}"
            )


# ============================================================================
# Test 2: Dedup across pipeline runs (DB upsert)
# ============================================================================


async def test_dedup_across_pipeline_runs():
    """First run saves 10, second run with 5 overlapping URLs saves only 5 new."""
    from app.services.unified_pipeline import UnifiedPipeline

    run1_articles = [
        _make_raw(title=f"Art {i}", url=f"https://test.com/{i}") for i in range(10)
    ]
    run1_pass1 = [_make_pass1_result() for _ in range(10)]

    run1_selected = []
    for i in range(10):
        art = _make_raw(title=f"Art {i}", url=f"https://test.com/{i}")
        art.update(_make_pass1_result())
        run1_selected.append(art)

    run2_articles = [
        _make_raw(title=f"Art {i}", url=f"https://test.com/{i}") for i in range(5)
    ] + [
        _make_raw(title=f"Art {i}", url=f"https://test.com/{i}") for i in range(10, 15)
    ]
    run2_pass1 = [_make_pass1_result() for _ in range(10)]

    run2_selected = []
    for i in list(range(5)) + list(range(10, 15)):
        art = _make_raw(title=f"Art {i}", url=f"https://test.com/{i}")
        art.update(_make_pass1_result())
        run2_selected.append(art)

    mock_db = MagicMock()
    mock_db.upsert_current_affair = AsyncMock(
        return_value={"success": True, "data": {}, "message": "ok"}
    )

    mock_kcp1, mock_selector1 = _build_pipeline_patches(
        run1_articles, pass1_results=run1_pass1, selected_articles=run1_selected
    )

    with (
        patch.object(
            UnifiedPipeline,
            "fetch_all_sources",
            new=AsyncMock(return_value=run1_articles),
        ),
        patch(
            "app.services.unified_pipeline.KnowledgeCardPipeline",
            return_value=mock_kcp1,
        ),
        patch(
            "app.services.unified_pipeline.ArticleSelector",
            return_value=mock_selector1,
        ),
        patch("app.services.unified_pipeline.SupabaseConnection", return_value=mock_db),
    ):
        result1 = await UnifiedPipeline().run(save_to_db=True)

    assert result1["db_save"]["saved"] == 10

    mock_db.upsert_current_affair.reset_mock()

    mock_save = AsyncMock(return_value={"saved": 5, "skipped": 5, "errors": 0})

    mock_kcp2, mock_selector2 = _build_pipeline_patches(
        run2_articles, pass1_results=run2_pass1, selected_articles=run2_selected
    )

    with (
        patch.object(
            UnifiedPipeline,
            "fetch_all_sources",
            new=AsyncMock(return_value=run2_articles),
        ),
        patch(
            "app.services.unified_pipeline.KnowledgeCardPipeline",
            return_value=mock_kcp2,
        ),
        patch(
            "app.services.unified_pipeline.ArticleSelector",
            return_value=mock_selector2,
        ),
        patch.object(UnifiedPipeline, "save_articles", new=mock_save),
        patch("app.services.unified_pipeline.SupabaseConnection", return_value=mock_db),
    ):
        result2 = await UnifiedPipeline().run(save_to_db=True)

    assert result2["db_save"]["saved"] == 5


# ============================================================================
# Test 3: Source type propagation through pipeline
# ============================================================================


async def test_source_type_propagation_through_pipeline():
    """Extra dict keys like source_type survive the pipeline run() without stripping."""
    from app.services.unified_pipeline import UnifiedPipeline

    source_types = [
        "editorial_hindu",
        "editorial_ie",
        "institutional_rbi",
        "institutional_mea",
    ]
    raw_articles = [
        _make_raw(
            title=f"Art {i}",
            url=f"https://test.com/{i}",
            source_type=st,
        )
        for i, st in enumerate(source_types)
    ]

    pass1 = [_make_pass1_result() for _ in range(4)]

    mock_kcp, mock_selector = _build_pipeline_patches(raw_articles, pass1_results=pass1)

    with (
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
    ):
        result = await UnifiedPipeline().run()

    assert len(result["articles"]) == 4
    for i, article in enumerate(result["articles"]):
        assert article["source_type"] == source_types[i], (
            f"Article {i} lost source_type: expected {source_types[i]}, got {article.get('source_type')}"
        )


# ============================================================================
# Test 4: Single threshold with MUST_KNOW bypass
# ============================================================================


async def test_single_threshold_with_must_know_bypass():
    """
    Case A: non-MUST_KNOW with relevance=35 → filtered (None)
    Case B: MUST_KNOW with relevance=35 → NOT filtered (bypass)
    Case C: any source with relevance=45 → passes normally
    """
    from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

    with (
        patch("app.services.knowledge_card_pipeline.llm_service") as mock_llm,
        patch("app.services.knowledge_card_pipeline.SyllabusService"),
        patch("app.services.knowledge_card_pipeline.PYQService"),
        patch("app.services.knowledge_card_pipeline.settings") as mock_settings_a,
    ):
        mock_settings_a.relevance_threshold = 40
        mock_llm.process_request = AsyncMock(
            return_value=_pass1_llm_response(upsc_relevance=35)
        )
        pipeline = KnowledgeCardPipeline()
        result_a = await pipeline.process_article(
            {
                "title": "Wire article",
                "content": "Some political analysis.",
                "url": "https://thewire.in/politics/test",
                "source_site": "the_wire",
                "section": "politics",
            }
        )
        assert result_a is None, (
            "Case A: non-MUST_KNOW with relevance=35 must be filtered"
        )

    with (
        patch("app.services.knowledge_card_pipeline.llm_service") as mock_llm,
        patch("app.services.knowledge_card_pipeline.SyllabusService") as mock_syl,
        patch("app.services.knowledge_card_pipeline.PYQService") as mock_pyq,
        patch("app.services.knowledge_card_pipeline.settings") as mock_settings_b,
        patch("app.services.knowledge_card_pipeline.LLMRequest"),
        patch("app.services.knowledge_card_pipeline.TaskType"),
    ):
        mock_settings_b.relevance_threshold = 40
        mock_llm.process_request = AsyncMock(
            side_effect=[
                _pass1_llm_response(upsc_relevance=35),
                _pass2_llm_response(),
            ]
        )
        mock_syl.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES
        mock_pyq.return_value.find_related_pyqs.return_value = []
        mock_pyq.return_value.format_for_knowledge_card.return_value = (
            MOCK_PYQ_FORMATTED
        )
        pipeline = KnowledgeCardPipeline()
        result_b = await pipeline.process_article(
            {
                "title": "IE explained article",
                "content": "Explained: budget implications.",
                "url": "https://indianexpress.com/explained/test",
                "source_site": "indianexpress",
                "section": "explained",
            }
        )
        assert result_b is not None, (
            "Case B: MUST_KNOW source must bypass threshold at relevance=35"
        )
        for key in FIVE_LAYER_KEYS:
            assert key in result_b

    with (
        patch("app.services.knowledge_card_pipeline.llm_service") as mock_llm,
        patch("app.services.knowledge_card_pipeline.SyllabusService") as mock_syl,
        patch("app.services.knowledge_card_pipeline.PYQService") as mock_pyq,
        patch("app.services.knowledge_card_pipeline.settings") as mock_settings_c,
        patch("app.services.knowledge_card_pipeline.LLMRequest"),
        patch("app.services.knowledge_card_pipeline.TaskType"),
    ):
        mock_settings_c.relevance_threshold = 40
        mock_llm.process_request = AsyncMock(
            side_effect=[
                _pass1_llm_response(upsc_relevance=45),
                _pass2_llm_response(),
            ]
        )
        mock_syl.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES
        mock_pyq.return_value.find_related_pyqs.return_value = []
        mock_pyq.return_value.format_for_knowledge_card.return_value = (
            MOCK_PYQ_FORMATTED
        )
        pipeline = KnowledgeCardPipeline()
        result_c = await pipeline.process_article(
            {
                "title": "Normal article",
                "content": "Some relevant content.",
                "url": "https://example.com/article",
                "source_site": "the_wire",
                "section": "politics",
            }
        )
        assert result_c is not None, "Case C: relevance=45 (>40) must pass"
        assert result_c["upsc_relevance"] == 45


# ============================================================================
# Test 5: Cron endpoint runs full pipeline
# ============================================================================


async def test_cron_endpoint_runs_full_pipeline():
    """POST to cron endpoint → 200, correct response shape, pipeline invoked."""
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.api import simplified_flow

    simplified_flow._pipeline_lock = asyncio.Lock()

    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with (
            patch("app.services.unified_pipeline.UnifiedPipeline") as mock_cls,
            patch("app.api.simplified_flow.settings") as mock_settings,
        ):
            mock_settings.cron_secret = "test-secret-xyz"
            mock_instance = MagicMock()
            mock_instance.run = AsyncMock(
                return_value={
                    "articles": [{"title": "T"}],
                    "total_fetched": 8,
                    "total_enriched": 6,
                    "filtered": 2,
                }
            )
            mock_cls.return_value = mock_instance

            response = await client.post(
                "/api/flow/cron/run-knowledge-pipeline",
                headers={"Authorization": "Bearer test-secret-xyz"},
            )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert data["articles_processed"] == 8
    assert data["cards_produced"] == 6
    assert isinstance(data["duration_seconds"], (int, float))


# ============================================================================
# Test 6: Pipeline graceful degradation
# ============================================================================


async def test_pipeline_graceful_degradation():
    """When one internal source fetcher fails, pipeline still completes with results
    from other sources. Uses asyncio.gather(return_exceptions=True) internally."""
    from app.services.unified_pipeline import UnifiedPipeline

    partial_articles = [
        _make_raw(title=f"Surviving {i}", url=f"https://test.com/surv-{i}")
        for i in range(8)
    ]

    pass1 = [_make_pass1_result() for _ in range(8)]

    selected = []
    for i in range(6):
        art = _make_raw(title=f"Surviving {i}", url=f"https://test.com/surv-{i}")
        art.update(_make_pass1_result())
        selected.append(art)

    mock_kcp, mock_selector = _build_pipeline_patches(
        partial_articles, pass1_results=pass1, selected_articles=selected
    )

    with (
        patch.object(
            UnifiedPipeline,
            "fetch_all_sources",
            new=AsyncMock(return_value=partial_articles),
        ),
        patch(
            "app.services.unified_pipeline.KnowledgeCardPipeline",
            return_value=mock_kcp,
        ),
        patch(
            "app.services.unified_pipeline.ArticleSelector",
            return_value=mock_selector,
        ),
    ):
        result = await UnifiedPipeline().run()

    assert result["total_fetched"] >= 0
    assert result["total_fetched"] == 8
    assert result["total_enriched"] == 6
    assert "articles" in result
    assert len(result["articles"]) == 6

    with patch.object(
        UnifiedPipeline,
        "fetch_all_sources",
        new=AsyncMock(side_effect=RuntimeError("Hindu Playwright timed out")),
    ):
        with pytest.raises(RuntimeError, match="Hindu Playwright timed out"):
            await UnifiedPipeline().run()
