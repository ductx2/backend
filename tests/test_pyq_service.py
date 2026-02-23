"""Tests for PYQService — keyword-based PYQ matching and formatting."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.pyq_service import GS_PAPER_SUBJECT_MAP, PYQService


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

SAMPLE_PYQ_ROWS = [
    {
        "id": "aaa-111",
        "question_text": "Which of the following statements about monetary policy is correct?",
        "year": 2023,
        "exam_type": "prelims",
        "subject": "Economy",
        "topics": ["monetary policy", "RBI", "inflation"],
        "upsc_relevance": 85,
    },
    {
        "id": "bbb-222",
        "question_text": "The fiscal deficit in the Union Budget refers to:",
        "year": 2021,
        "exam_type": "prelims",
        "subject": "Economy",
        "topics": ["fiscal policy", "budget"],
        "upsc_relevance": 75,
    },
    {
        "id": "ccc-333",
        "question_text": "Discuss the role of the judiciary in protecting fundamental rights in India.",
        "year": 2019,
        "exam_type": "mains",
        "subject": "Polity",
        "topics": ["judiciary", "fundamental rights", "constitution"],
        "upsc_relevance": 60,
    },
    {
        "id": "ddd-444",
        "question_text": "The Himalayan rivers are perennial because:",
        "year": 2018,
        "exam_type": "prelims",
        "subject": "Geography",
        "topics": ["rivers", "Himalayas", "drainage"],
        "upsc_relevance": 50,
    },
]


def _mock_execute(data):
    """Return a MagicMock whose .data attribute is *data*."""
    resp = MagicMock()
    resp.data = data
    return resp


def _build_mock_client(rows=None):
    """Build a mock Supabase client that returns *rows* for any query chain.

    The mock supports chaining: client.table(...).select(...).overlaps(...).order(...).limit(...).execute()
    """
    if rows is None:
        rows = SAMPLE_PYQ_ROWS

    chain = MagicMock()
    chain.execute.return_value = _mock_execute(rows)

    # Every chained method returns the same chain object
    chain.select.return_value = chain
    chain.overlaps.return_value = chain
    chain.in_.return_value = chain
    chain.ilike.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain

    client = MagicMock()
    client.table.return_value = chain
    return client


@pytest.fixture
def service():
    """PYQService with a mocked Supabase client."""
    return PYQService(supabase_client=_build_mock_client())


@pytest.fixture
def empty_service():
    """PYQService whose mock client returns no rows."""
    return PYQService(supabase_client=_build_mock_client(rows=[]))


# ---------------------------------------------------------------------------
# GS paper → subject mapping
# ---------------------------------------------------------------------------


class TestGSPaperSubjectMap:
    def test_gs1_subjects(self) -> None:
        assert "History" in GS_PAPER_SUBJECT_MAP["GS1"]
        assert "Geography" in GS_PAPER_SUBJECT_MAP["GS1"]
        assert "Society" in GS_PAPER_SUBJECT_MAP["GS1"]

    def test_gs2_subjects(self) -> None:
        assert "Polity" in GS_PAPER_SUBJECT_MAP["GS2"]
        assert "Governance" in GS_PAPER_SUBJECT_MAP["GS2"]
        assert "International Relations" in GS_PAPER_SUBJECT_MAP["GS2"]

    def test_gs3_subjects(self) -> None:
        expected = {"Economy", "Science", "Environment", "Security"}
        assert expected == set(GS_PAPER_SUBJECT_MAP["GS3"])

    def test_gs4_subjects(self) -> None:
        assert GS_PAPER_SUBJECT_MAP["GS4"] == ["Ethics"]

    def test_all_papers_present(self) -> None:
        assert set(GS_PAPER_SUBJECT_MAP.keys()) == {"GS1", "GS2", "GS3", "GS4"}


# ---------------------------------------------------------------------------
# find_related_pyqs
# ---------------------------------------------------------------------------


class TestFindRelatedPYQs:
    def test_returns_list(self, service: PYQService) -> None:
        results = service.find_related_pyqs(["monetary", "policy", "inflation"])
        assert isinstance(results, list)

    def test_result_structure(self, service: PYQService) -> None:
        results = service.find_related_pyqs(["monetary", "policy"])
        assert len(results) > 0
        first = results[0]
        assert "question_id" in first
        assert "question_text" in first
        assert "year" in first
        assert "exam_type" in first
        assert "subject" in first
        assert "topics" in first
        assert "relevance_score" in first

    def test_empty_keywords_returns_empty(self, service: PYQService) -> None:
        assert service.find_related_pyqs([]) == []

    def test_no_results_returns_empty(self, empty_service: PYQService) -> None:
        results = empty_service.find_related_pyqs(["nonexistent"])
        assert results == []

    def test_max_results_respected(self) -> None:
        # Return 10 rows, request max 3
        many_rows = SAMPLE_PYQ_ROWS * 3  # 12 rows with duplicated ids
        # Give each a unique id for dedup to keep all
        for i, row in enumerate(many_rows):
            many_rows[i] = {**row, "id": f"unique-{i}"}
        client = _build_mock_client(rows=many_rows)
        svc = PYQService(supabase_client=client)
        results = svc.find_related_pyqs(["monetary"], max_results=3)
        assert len(results) <= 3

    def test_topics_trigger_overlap_query(self) -> None:
        client = _build_mock_client()
        svc = PYQService(supabase_client=client)
        svc.find_related_pyqs(["inflation"], topics=["monetary policy"])
        # The chain should have called .overlaps at some point
        chain = client.table.return_value
        chain.overlaps.assert_called()

    def test_gs_paper_triggers_in_query(self) -> None:
        client = _build_mock_client()
        svc = PYQService(supabase_client=client)
        svc.find_related_pyqs(["inflation"], gs_paper="GS3")
        chain = client.table.return_value
        chain.in_.assert_called()

    def test_invalid_gs_paper_skips_subject_filter(self) -> None:
        client = _build_mock_client()
        svc = PYQService(supabase_client=client)
        svc.find_related_pyqs(["inflation"], gs_paper="GS99")
        chain = client.table.return_value
        chain.in_.assert_not_called()

    def test_short_keywords_skipped_in_text_search(self) -> None:
        """Keywords shorter than 3 chars should be skipped in ilike queries."""
        client = _build_mock_client()
        svc = PYQService(supabase_client=client)
        svc.find_related_pyqs(["ab", "cd"])  # both < 3 chars
        chain = client.table.return_value
        chain.ilike.assert_not_called()

    def test_exception_returns_empty(self) -> None:
        """If the Supabase client throws, return [] gracefully."""
        client = MagicMock()
        client.table.side_effect = Exception("connection lost")
        svc = PYQService(supabase_client=client)
        assert svc.find_related_pyqs(["economy"]) == []


# ---------------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------------


class TestRelevanceScoring:
    def test_scores_between_0_and_1(self, service: PYQService) -> None:
        results = service.find_related_pyqs(["monetary", "policy"])
        for r in results:
            assert 0 < r["relevance_score"] <= 1.0

    def test_sorted_by_score_desc(self, service: PYQService) -> None:
        results = service.find_related_pyqs(["monetary", "policy"])
        scores = [r["relevance_score"] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_keyword_match_boosts_score(self) -> None:
        """A row matching more keywords should score higher."""
        svc = PYQService(supabase_client=_build_mock_client())
        results = svc.find_related_pyqs(["monetary", "policy", "inflation"])
        # The first row (monetary policy + inflation) should have highest score
        if len(results) >= 2:
            assert results[0]["relevance_score"] >= results[-1]["relevance_score"]

    def test_recent_year_bonus(self) -> None:
        """Rows with year >= 2020 get a recency bonus."""
        # Two rows: one 2023, one 2015 — same question text
        rows = [
            {
                "id": "recent",
                "question_text": "Economy growth question",
                "year": 2023,
                "exam_type": "prelims",
                "subject": "Economy",
                "topics": [],
                "upsc_relevance": 50,
            },
            {
                "id": "old",
                "question_text": "Economy growth question",
                "year": 2015,
                "exam_type": "prelims",
                "subject": "Economy",
                "topics": [],
                "upsc_relevance": 50,
            },
        ]
        svc = PYQService(supabase_client=_build_mock_client(rows=rows))
        results = svc.find_related_pyqs(["economy", "growth"])
        if len(results) == 2:
            recent = next(r for r in results if r["question_id"] == "recent")
            old = next(r for r in results if r["question_id"] == "old")
            assert recent["relevance_score"] > old["relevance_score"]

    def test_high_upsc_relevance_bonus(self) -> None:
        """Rows with upsc_relevance >= 70 get a bonus."""
        rows = [
            {
                "id": "high-rel",
                "question_text": "Policy question",
                "year": 2019,
                "exam_type": "prelims",
                "subject": "Economy",
                "topics": [],
                "upsc_relevance": 90,
            },
            {
                "id": "low-rel",
                "question_text": "Policy question",
                "year": 2019,
                "exam_type": "prelims",
                "subject": "Economy",
                "topics": [],
                "upsc_relevance": 30,
            },
        ]
        svc = PYQService(supabase_client=_build_mock_client(rows=rows))
        results = svc.find_related_pyqs(["policy"])
        if len(results) == 2:
            high = next(r for r in results if r["question_id"] == "high-rel")
            low = next(r for r in results if r["question_id"] == "low-rel")
            assert high["relevance_score"] > low["relevance_score"]


# ---------------------------------------------------------------------------
# format_for_knowledge_card
# ---------------------------------------------------------------------------


class TestFormatForKnowledgeCard:
    def test_empty_input(self) -> None:
        svc = PYQService(supabase_client=_build_mock_client())
        result = svc.format_for_knowledge_card([])
        assert result == {
            "related_pyqs": [],
            "pyq_count": 0,
            "year_range": None,
            "exam_types": [],
        }

    def test_single_pyq(self) -> None:
        svc = PYQService(supabase_client=_build_mock_client())
        pyqs = [
            {
                "question_text": "What is inflation?",
                "year": 2023,
                "exam_type": "prelims",
                "subject": "Economy",
            }
        ]
        result = svc.format_for_knowledge_card(pyqs)
        assert result["pyq_count"] == 1
        assert result["year_range"] == "2023"
        assert result["exam_types"] == ["prelims"]
        assert result["related_pyqs"][0]["question_summary"] == "What is inflation?"

    def test_multiple_pyqs_year_range(self) -> None:
        svc = PYQService(supabase_client=_build_mock_client())
        pyqs = [
            {"question_text": "Q1", "year": 2023, "exam_type": "prelims", "subject": "Economy"},
            {"question_text": "Q2", "year": 2019, "exam_type": "mains", "subject": "Polity"},
            {"question_text": "Q3", "year": 2021, "exam_type": "prelims", "subject": "Economy"},
        ]
        result = svc.format_for_knowledge_card(pyqs)
        assert result["pyq_count"] == 3
        assert result["year_range"] == "2019-2023"
        assert set(result["exam_types"]) == {"prelims", "mains"}

    def test_long_question_truncated(self) -> None:
        svc = PYQService(supabase_client=_build_mock_client())
        long_text = "A" * 200
        pyqs = [
            {"question_text": long_text, "year": 2022, "exam_type": "prelims", "subject": "X"}
        ]
        result = svc.format_for_knowledge_card(pyqs)
        summary = result["related_pyqs"][0]["question_summary"]
        assert len(summary) == 153  # 150 chars + "..."
        assert summary.endswith("...")

    def test_exam_types_sorted(self) -> None:
        svc = PYQService(supabase_client=_build_mock_client())
        pyqs = [
            {"question_text": "Q1", "year": 2023, "exam_type": "prelims", "subject": "A"},
            {"question_text": "Q2", "year": 2022, "exam_type": "mains", "subject": "B"},
        ]
        result = svc.format_for_knowledge_card(pyqs)
        assert result["exam_types"] == ["mains", "prelims"]  # sorted alphabetically


# ---------------------------------------------------------------------------
# get_pyq_stats
# ---------------------------------------------------------------------------


class TestGetPYQStats:
    def test_returns_stats_structure(self, service: PYQService) -> None:
        stats = service.get_pyq_stats()
        assert "total_count" in stats
        assert "year_range" in stats
        assert "subject_distribution" in stats

    def test_total_count(self, service: PYQService) -> None:
        stats = service.get_pyq_stats()
        assert stats["total_count"] == len(SAMPLE_PYQ_ROWS)

    def test_year_range(self, service: PYQService) -> None:
        stats = service.get_pyq_stats()
        assert stats["year_range"]["min"] == 2018
        assert stats["year_range"]["max"] == 2023

    def test_subject_distribution(self, service: PYQService) -> None:
        stats = service.get_pyq_stats()
        assert stats["subject_distribution"]["Economy"] == 2
        assert stats["subject_distribution"]["Polity"] == 1
        assert stats["subject_distribution"]["Geography"] == 1

    def test_empty_database(self, empty_service: PYQService) -> None:
        stats = empty_service.get_pyq_stats()
        assert stats["total_count"] == 0
        assert stats["year_range"] is None
        assert stats["subject_distribution"] == {}

    def test_exception_returns_safe_defaults(self) -> None:
        client = MagicMock()
        client.table.side_effect = Exception("db down")
        svc = PYQService(supabase_client=client)
        stats = svc.get_pyq_stats()
        assert stats["total_count"] == 0
        assert stats["year_range"] is None


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_duplicate_ids_removed(self) -> None:
        """Same PYQ found via multiple strategies should appear only once."""
        # All three strategies return the same rows -> should dedup
        client = _build_mock_client(rows=SAMPLE_PYQ_ROWS)
        svc = PYQService(supabase_client=client)
        results = svc.find_related_pyqs(
            ["monetary", "policy"],
            topics=["monetary policy"],
            gs_paper="GS3",
        )
        ids = [r["question_id"] for r in results]
        assert len(ids) == len(set(ids)), "Duplicate question_ids found"