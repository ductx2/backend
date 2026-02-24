"""
Tests for ArticleSelector — 3-stage article selection pipeline.

Tests cover:
  - _article_id helper
  - _gs_paper helper
  - deduplicate_semantic (6 tests)
  - balance_gs_pool (3 tests)
  - tournament_select (4 tests)
  - select_top_articles orchestrator (2 tests)
"""

import hashlib
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.article_selector import (
    ArticleSelector,
    _article_id,
    _gs_paper,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_article(
    i: int,
    gs: str = "GS2",
    score: int = 70,
    title: str | None = None,
) -> dict[str, Any]:
    """Build a minimal article dict for testing."""
    return {
        "title": title or f"Article about topic {i}",
        "url": f"http://test.com/article-{i}",
        "upsc_relevance": score,
        "gs_paper": gs,
        "content": f"Content body for article {i}",
        "raw_pass1_data": {
            "relevant_papers": [gs],
            "summary": f"Summary {i}",
        },
    }


def _expected_id(url: str) -> str:
    """Mirror of _article_id logic for assertions."""
    return hashlib.md5(url.encode()).hexdigest()[:8]


# ---------------------------------------------------------------------------
# _article_id tests
# ---------------------------------------------------------------------------


class TestArticleId:
    def test_stable_hash_from_url(self) -> None:
        a = _make_article(1)
        expected = _expected_id("http://test.com/article-1")
        assert _article_id(a) == expected

    def test_falls_back_to_source_url(self) -> None:
        a = {"source_url": "http://alt.com/x"}
        expected = _expected_id("http://alt.com/x")
        assert _article_id(a) == expected

    def test_empty_url_gives_md5_of_empty(self) -> None:
        a: dict[str, Any] = {}
        expected = hashlib.md5(b"").hexdigest()[:8]
        assert _article_id(a) == expected


# ---------------------------------------------------------------------------
# _gs_paper tests
# ---------------------------------------------------------------------------


class TestGsPaper:
    def test_direct_gs_paper_key(self) -> None:
        a = _make_article(1, gs="GS3")
        assert _gs_paper(a) == "GS3"

    def test_falls_back_to_raw_pass1_data(self) -> None:
        a = {"raw_pass1_data": {"relevant_papers": ["GS1"]}}
        assert _gs_paper(a) == "GS1"

    def test_defaults_to_gs2(self) -> None:
        a: dict[str, Any] = {}
        assert _gs_paper(a) == "GS2"


# ---------------------------------------------------------------------------
# deduplicate_semantic tests
# ---------------------------------------------------------------------------


class TestDeduplicateSemantic:
    @pytest.fixture()
    def selector(self) -> ArticleSelector:
        return ArticleSelector()

    @pytest.mark.asyncio
    async def test_empty_list(self, selector: ArticleSelector) -> None:
        result = await selector.deduplicate_semantic([])
        assert result == []

    @pytest.mark.asyncio
    async def test_single_article(self, selector: ArticleSelector) -> None:
        articles = [_make_article(1)]
        result = await selector.deduplicate_semantic(articles)
        assert result == articles

    @pytest.mark.asyncio
    async def test_no_duplicates_kept(self, selector: ArticleSelector) -> None:
        """Distinct titles survive dedup."""
        articles = [
            _make_article(1, title="India economy grows"),
            _make_article(2, title="Mars rover discovery"),
            _make_article(3, title="Parliament session begins"),
        ]
        result = await selector.deduplicate_semantic(articles)
        assert len(result) == 3

    @pytest.mark.asyncio
    async def test_exact_duplicate_removes_lower_score(
        self, selector: ArticleSelector
    ) -> None:
        """Identical titles → keep higher-scored article."""
        articles = [
            _make_article(1, score=80, title="India GDP growth report"),
            _make_article(2, score=90, title="India GDP growth report"),
        ]
        result = await selector.deduplicate_semantic(articles)
        assert len(result) == 1
        assert result[0]["upsc_relevance"] == 90

    @pytest.mark.asyncio
    async def test_near_duplicate_keeps_higher_score(
        self, selector: ArticleSelector
    ) -> None:
        """Near-duplicate titles with default threshold (0.50)."""
        articles = [
            _make_article(1, score=60, title="India GDP growth report released today"),
            _make_article(2, score=85, title="India GDP growth report released"),
        ]
        result = await selector.deduplicate_semantic(articles)
        assert len(result) == 1
        assert result[0]["upsc_relevance"] == 85

    @pytest.mark.asyncio
    async def test_threshold_1_keeps_all(self, selector: ArticleSelector) -> None:
        """threshold=1.0 means nothing is similar enough to remove."""
        articles = [
            _make_article(1, title="India GDP growth report"),
            _make_article(2, title="India GDP growth report"),
        ]
        result = await selector.deduplicate_semantic(articles, threshold=1.0)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# balance_gs_pool tests
# ---------------------------------------------------------------------------


class TestBalanceGsPool:
    @pytest.fixture()
    def selector(self) -> ArticleSelector:
        return ArticleSelector()

    @pytest.mark.asyncio
    async def test_small_input_returned_as_is(
        self, selector: ArticleSelector
    ) -> None:
        """If articles count <= pool_size, return unchanged."""
        articles = [_make_article(i) for i in range(10)]
        result = await selector.balance_gs_pool(articles, pool_size=50)
        assert result == articles

    @pytest.mark.asyncio
    async def test_reserves_gs_min_quotas(self, selector: ArticleSelector) -> None:
        """GS papers with fewer articles than GS_MIN still get their share."""
        articles = []
        # 30 GS1, 30 GS2, 5 GS3, 5 GS4 = 70 total
        for i in range(30):
            articles.append(_make_article(i, gs="GS1", score=50 + i))
        for i in range(30, 60):
            articles.append(_make_article(i, gs="GS2", score=50 + i))
        for i in range(60, 65):
            articles.append(_make_article(i, gs="GS3", score=50 + i))
        for i in range(65, 70):
            articles.append(_make_article(i, gs="GS4", score=50 + i))

        result = await selector.balance_gs_pool(articles, pool_size=30)
        gs_counts: dict[str, int] = {}
        for a in result:
            gs = _gs_paper(a)
            gs_counts[gs] = gs_counts.get(gs, 0) + 1

        # At least GS_MIN for each paper that has enough articles
        assert gs_counts.get("GS1", 0) >= min(5, 30)
        assert gs_counts.get("GS2", 0) >= min(5, 30)
        assert gs_counts.get("GS3", 0) >= min(5, 5)
        assert gs_counts.get("GS4", 0) >= min(1, 5)
        assert len(result) == 30

    @pytest.mark.asyncio
    async def test_fills_remaining_with_highest_scored(
        self, selector: ArticleSelector
    ) -> None:
        """After reserves, remaining slots go to highest-scored articles."""
        articles = []
        # 20 GS1 (score 80-99), 20 GS2 (score 60-79), 10 GS3 (score 50-59), 5 GS4 (score 40-44)
        for i in range(20):
            articles.append(_make_article(i, gs="GS1", score=80 + i))
        for i in range(20, 40):
            articles.append(_make_article(i, gs="GS2", score=60 + i))
        for i in range(40, 50):
            articles.append(_make_article(i, gs="GS3", score=50 + i))
        for i in range(50, 55):
            articles.append(_make_article(i, gs="GS4", score=40 + i))

        # pool_size=25: reserves GS1=5, GS2=5, GS3=5, GS4=1 = 16, then 9 remaining
        result = await selector.balance_gs_pool(articles, pool_size=25)
        scores = [a["upsc_relevance"] for a in result]
        # High GS1 scores (99, 98, ...) should appear in the remaining slots
        assert any(s >= 90 for s in scores)
        assert len(result) == 25


# ---------------------------------------------------------------------------
# tournament_select tests
# ---------------------------------------------------------------------------


class TestTournamentSelect:
    @pytest.fixture()
    def selector(self) -> ArticleSelector:
        return ArticleSelector()

    @pytest.mark.asyncio
    async def test_fewer_than_target_returned_as_is(
        self, selector: ArticleSelector
    ) -> None:
        articles = [_make_article(i) for i in range(5)]
        result = await selector.tournament_select(articles, target=30)
        assert result == articles

    @pytest.mark.asyncio
    async def test_llm_success_selects_correct_articles(
        self, selector: ArticleSelector
    ) -> None:
        """LLM returns selected_article_ids → those articles are picked."""
        articles = [_make_article(i, score=50 + i) for i in range(40)]
        target = 10

        # Pick IDs of articles 30-39 (highest scored)
        wanted_ids = [_expected_id(f"http://test.com/article-{i}") for i in range(30, 40)]

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.data = {"selected_article_ids": wanted_ids}

        with patch(
            "app.services.article_selector.llm_service.process_request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await selector.tournament_select(articles, target=target)

        result_ids = {_article_id(a) for a in result}
        assert result_ids == set(wanted_ids)
        assert len(result) == target

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_top_n(
        self, selector: ArticleSelector
    ) -> None:
        """LLM exception → deterministic top-N-by-score fallback."""
        articles = [_make_article(i, score=i * 10) for i in range(40)]
        target = 5

        with patch(
            "app.services.article_selector.llm_service.process_request",
            new_callable=AsyncMock,
            side_effect=RuntimeError("LLM down"),
        ):
            result = await selector.tournament_select(articles, target=target)

        assert len(result) == target
        # Should be the 5 highest-scored (scores 390, 380, 370, 360, 350)
        expected_scores = sorted(
            [a["upsc_relevance"] for a in articles], reverse=True
        )[:target]
        result_scores = sorted(
            [a["upsc_relevance"] for a in result], reverse=True
        )
        assert result_scores == expected_scores

    @pytest.mark.asyncio
    async def test_llm_returns_fewer_than_target_pads(
        self, selector: ArticleSelector
    ) -> None:
        """LLM returns only 3 IDs for target=5 → pads with top-scored remaining."""
        articles = [_make_article(i, score=50 + i) for i in range(10)]
        target = 5

        # LLM picks only 3
        partial_ids = [_expected_id(f"http://test.com/article-{i}") for i in [0, 1, 2]]

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.data = {"selected_article_ids": partial_ids}

        with patch(
            "app.services.article_selector.llm_service.process_request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await selector.tournament_select(articles, target=target)

        assert len(result) == target
        # First 3 should be the LLM-picked ones
        result_ids = [_article_id(a) for a in result]
        for pid in partial_ids:
            assert pid in result_ids

    @pytest.mark.asyncio
    async def test_llm_articles_response_format(
        self, selector: ArticleSelector
    ) -> None:
        """LLM returns 'articles' key instead of 'selected_article_ids'."""
        articles = [_make_article(i, score=50 + i) for i in range(40)]
        target = 5

        # Build LLM response in the 'articles' format
        llm_articles = [
            {"article_id": _expected_id(f"http://test.com/article-{i}"), "upsc_relevance": 90 - i}
            for i in range(35, 40)
        ]

        mock_response = MagicMock()
        mock_response.success = True
        mock_response.data = {"articles": llm_articles}

        with patch(
            "app.services.article_selector.llm_service.process_request",
            new_callable=AsyncMock,
            return_value=mock_response,
        ):
            result = await selector.tournament_select(articles, target=target)

        assert len(result) == target


# ---------------------------------------------------------------------------
# select_top_articles orchestrator tests
# ---------------------------------------------------------------------------


class TestSelectTopArticles:
    @pytest.fixture()
    def selector(self) -> ArticleSelector:
        return ArticleSelector()

    @pytest.mark.asyncio
    async def test_orchestrator_calls_all_three_stages(
        self, selector: ArticleSelector
    ) -> None:
        """select_top_articles chains dedup → balance → tournament."""
        articles = [_make_article(i) for i in range(5)]

        with (
            patch.object(
                selector, "deduplicate_semantic", new_callable=AsyncMock, return_value=articles
            ) as mock_dedup,
            patch.object(
                selector, "balance_gs_pool", new_callable=AsyncMock, return_value=articles
            ) as mock_balance,
            patch.object(
                selector, "tournament_select", new_callable=AsyncMock, return_value=articles
            ) as mock_tournament,
        ):
            result = await selector.select_top_articles(articles, target=30)

        mock_dedup.assert_called_once_with(articles)
        mock_balance.assert_called_once_with(articles, pool_size=50)
        mock_tournament.assert_called_once_with(articles, target=30)
        assert result == articles

    @pytest.mark.asyncio
    async def test_end_to_end_with_mocked_llm(
        self, selector: ArticleSelector
    ) -> None:
        """Full pipeline with real dedup/balance but mocked LLM."""
        # Use completely distinct titles to avoid TF-IDF dedup
        distinct_titles = [
            "India GDP growth accelerates sharply",
            "Supreme Court ruling on privacy rights",
            "ISRO launches Mars orbiter mission",
            "Parliament passes farm reform bill",
            "Monsoon forecast predicts heavy rainfall",
            "RBI monetary policy rate unchanged",
            "Border tensions along northern frontier",
            "Education reforms digital infrastructure",
            "Renewable energy capacity solar power",
            "Healthcare system pandemic preparedness",
            "Space program chandrayaan exploration",
            "Women empowerment legislation passed",
            "Climate change adaptation strategies",
            "Digital payments UPI transaction record",
            "Semiconductor manufacturing plant announced",
            "Railway modernization bullet train project",
            "Water conservation drought management policy",
            "Forest protection biodiversity assessment",
            "Nuclear energy civilian reactor approved",
            "Artificial intelligence regulation framework",
        ]
        articles = []
        for i, title in enumerate(distinct_titles):
            gs = ["GS1", "GS2", "GS3"][i % 3]
            articles.append(_make_article(i, gs=gs, score=70 + i, title=title))

        # 20 articles, target=30 — no stage reduces the count:
        # dedup: all titles distinct → all kept
        # balance: pool_size=max(50,50)=50 > 20 → returned as-is
        # tournament: 20 <= 30 → returned as-is
        result = await selector.select_top_articles(articles, target=30)
        assert len(result) == 20
