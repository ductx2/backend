"""
TDD tests for KnowledgeCardPipeline — two-pass LLM enrichment engine.

All tests use mocked LLM, SyllabusService, and PYQService — NO real network calls.
Minimum 25 tests covering: init, pass1, pass2, triage, process_article, edge cases.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.llm_schemas import LLMResponse, TaskType


# ============================================================================
# FIXTURES: Reusable test data
# ============================================================================

SAMPLE_ARTICLE = {
    "title": "RBI cuts repo rate by 25 bps to 6.25% to boost growth",
    "content": "The Reserve Bank of India cut the repo rate by 25 basis points to 6.25 percent, citing the need to support growth amid global uncertainty. Governor Sanjay Malhotra announced the decision after a three-day MPC meeting. This is the first rate cut in five years.",
    "url": "https://indianexpress.com/article/business/rbi-rate-cut-12345/",
    "source_site": "indianexpress",
    "section": "explained",
}

SAMPLE_ARTICLE_NO_CONTENT = {
    "title": "PM launches new education policy initiative",
    "content": None,
    "url": "https://indianexpress.com/article/india/nep-initiative-67890/",
    "source_site": "indianexpress",
    "section": "editorials",
}

SAMPLE_ARTICLE_EMPTY_CONTENT = {
    "title": "Supreme Court verdict on federalism",
    "content": "",
    "url": "https://indianexpress.com/article/india/sc-federalism-11111/",
    "source_site": "hindu",
    "section": "editorial",
}

SAMPLE_ARTICLE_LOW_RELEVANCE = {
    "title": "Celebrity chef opens new restaurant in Mumbai",
    "content": "A famous chef opened a new Italian restaurant in Bandra, Mumbai, attracting food lovers.",
    "url": "https://example.com/food-article/",
    "source_site": "other",
    "section": "lifestyle",
}


_SENTINEL = object()  # Distinguish None (use default) from [] (explicitly empty)

def _make_pass1_llm_response(
    upsc_relevance: int = 78,
    relevant_papers: list | object = _SENTINEL,
    key_topics: list | None = None,
    success: bool = True,
    error_message: str | None = None,
) -> LLMResponse:
    """Create a mock LLMResponse for Pass 1 (UPSC_ANALYSIS)."""
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
            "relevant_papers": ["GS3", "GS2"] if relevant_papers is _SENTINEL else relevant_papers,
            "key_topics": key_topics
            or ["Repo Rate", "Monetary Policy", "RBI", "Inflation Targeting"],
            "importance_level": "High",
            "question_potential": "High",
            "category": "economy",
            "key_vocabulary": [
                {"term": "Repo Rate", "definition": "Rate at which RBI lends to banks"}
            ],
            "summary": "RBI cut repo rate by 25 bps to support economic growth.",
        }
        if success
        else {},
        error_message=error_message,
    )


def _make_pass2_llm_response(
    success: bool = True,
    error_message: str | None = None,
) -> LLMResponse:
    """Create a mock LLMResponse for Pass 2 (KNOWLEDGE_CARD)."""
    return LLMResponse(
        success=success,
        task_type=TaskType.KNOWLEDGE_CARD,
        provider_used="openai/gpt-oss-120b",
        model_used="openai/gpt-oss-120b",
        response_time=1.0,
        tokens_used=800,
        estimated_cost=0.0,
        data={
            "headline_layer": "RBI cuts repo rate by 25 bps to 6.25%, first cut in five years",
            "facts_layer": [
                "Repo rate reduced from 6.50% to 6.25%",
                "First rate cut since 2019",
                "MPC voted 4-2 in favour of the cut",
            ],
            "context_layer": "The RBI's rate cut comes amid slowing GDP growth and benign inflation. This signals a shift towards accommodative monetary policy.",
            "mains_angle_layer": "Discuss the role of monetary policy in balancing growth and inflation in the Indian economy. (GS3: Economy)",
        }
        if success
        else {},
        error_message=error_message,
    )


MOCK_SYLLABUS_MATCHES = [
    {
        "paper": "GS3",
        "topic": "Indian Economy",
        "sub_topic": "Monetary Policy",
        "confidence": 0.85,
    },
    {
        "paper": "GS3",
        "topic": "Indian Economy",
        "sub_topic": "Inflation",
        "confidence": 0.65,
    },
]

MOCK_PYQS = [
    {
        "question_id": "pyq-001",
        "question_text": "Discuss the role of RBI in controlling inflation.",
        "year": 2023,
        "exam_type": "Mains",
        "subject": "Economy",
        "topics": ["RBI", "Inflation"],
        "relevance_score": 0.8,
    },
    {
        "question_id": "pyq-002",
        "question_text": "What is repo rate? How does it affect the economy?",
        "year": 2021,
        "exam_type": "Prelims",
        "subject": "Economy",
        "topics": ["Repo Rate"],
        "relevance_score": 0.7,
    },
]

MOCK_PYQ_FORMATTED = {
    "related_pyqs": [
        {
            "year": 2023,
            "exam_type": "Mains",
            "question_summary": "Discuss the role of RBI in controlling inflation.",
            "subject": "Economy",
        },
        {
            "year": 2021,
            "exam_type": "Prelims",
            "question_summary": "What is repo rate? How does it affect the economy?",
            "subject": "Economy",
        },
    ],
    "pyq_count": 2,
    "year_range": "2021-2023",
    "exam_types": ["Mains", "Prelims"],
}


# ============================================================================
# TESTS: Module imports and class initialization
# ============================================================================


class TestModuleImports:
    """Ensure the module and class are importable."""

    def test_module_importable(self):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline  # noqa: F401

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_class_instantiates(self, mock_pyq_cls, mock_syllabus_cls):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        assert pipeline is not None

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_class_has_required_methods(self, mock_pyq_cls, mock_syllabus_cls):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        assert hasattr(pipeline, "process_article")
        assert hasattr(pipeline, "run_pass1")
        assert hasattr(pipeline, "run_pass2")
        assert hasattr(pipeline, "_compute_triage")

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_init_creates_syllabus_service(self, mock_pyq_cls, mock_syllabus_cls):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        mock_syllabus_cls.assert_called_once()
        assert pipeline.syllabus_service is not None

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_init_creates_pyq_service(self, mock_pyq_cls, mock_syllabus_cls):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        mock_pyq_cls.assert_called_once()
        assert pipeline.pyq_service is not None

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_relevance_threshold_from_settings(self, mock_pyq_cls, mock_syllabus_cls):
        """FAILING UNTIL IMPL: pipeline.relevance_threshold should read from settings (40)."""
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline
        pipeline = KnowledgeCardPipeline()
        # Must be an instance attribute, not a class constant
        assert hasattr(pipeline, "relevance_threshold")
        assert pipeline.relevance_threshold == 40
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_no_hardcoded_class_constant(self, mock_pyq_cls, mock_syllabus_cls):
        """FAILING UNTIL IMPL: RELEVANCE_THRESHOLD class constant should be removed."""
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        # Class-level constant should not exist; threshold lives on instance only
        assert not hasattr(KnowledgeCardPipeline, "RELEVANCE_THRESHOLD")


# ============================================================================
# TESTS: Pass 1 — Relevance + Facts + Syllabus
# ============================================================================


class TestRunPass1:
    """Test run_pass1 — LLM relevance scoring + fact extraction + syllabus matching."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass1_returns_dict(self, mock_pyq_cls, mock_syllabus_cls, mock_llm):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(return_value=_make_pass1_llm_response())
        mock_syllabus_cls.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.run_pass1(SAMPLE_ARTICLE)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass1_has_required_keys(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(return_value=_make_pass1_llm_response())
        mock_syllabus_cls.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.run_pass1(SAMPLE_ARTICLE)
        required_keys = {
            "upsc_relevance",
            "gs_paper",
            "key_facts",
            "keywords",
            "syllabus_matches",
            "raw_pass1_data",
        }
        assert required_keys.issubset(result.keys())

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass1_extracts_upsc_relevance(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            return_value=_make_pass1_llm_response(upsc_relevance=82)
        )
        mock_syllabus_cls.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.run_pass1(SAMPLE_ARTICLE)
        assert result["upsc_relevance"] == 82

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass1_extracts_gs_paper_first_element(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            return_value=_make_pass1_llm_response(relevant_papers=["GS2", "GS3"])
        )
        mock_syllabus_cls.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.run_pass1(SAMPLE_ARTICLE)
        assert result["gs_paper"] == "GS2"

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass1_gs_paper_defaults_to_gs2_when_empty(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            return_value=_make_pass1_llm_response(relevant_papers=[])
        )
        mock_syllabus_cls.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.run_pass1(SAMPLE_ARTICLE)
        assert result["gs_paper"] == "GS2"

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass1_key_facts_from_key_topics(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        topics = ["Monetary Policy", "RBI", "GDP Growth"]
        mock_llm.process_request = AsyncMock(
            return_value=_make_pass1_llm_response(key_topics=topics)
        )
        mock_syllabus_cls.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.run_pass1(SAMPLE_ARTICLE)
        assert result["key_facts"] == topics

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass1_calls_syllabus_service(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(return_value=_make_pass1_llm_response())
        mock_syllabus_instance = mock_syllabus_cls.return_value
        mock_syllabus_instance.match_topics.return_value = MOCK_SYLLABUS_MATCHES

        pipeline = KnowledgeCardPipeline()
        await pipeline.run_pass1(SAMPLE_ARTICLE)
        mock_syllabus_instance.match_topics.assert_called_once()

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass1_raises_on_llm_failure(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            return_value=_make_pass1_llm_response(
                success=False, error_message="API quota exceeded"
            )
        )

        pipeline = KnowledgeCardPipeline()
        with pytest.raises(RuntimeError, match="Pass 1 LLM failed"):
            await pipeline.run_pass1(SAMPLE_ARTICLE)

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass1_handles_none_content(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        """Pass 1 should work when article content is None (use title only)."""
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            return_value=_make_pass1_llm_response(upsc_relevance=60)
        )
        mock_syllabus_cls.return_value.match_topics.return_value = []

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.run_pass1(SAMPLE_ARTICLE_NO_CONTENT)
        assert result["upsc_relevance"] == 60

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass1_handles_empty_content(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        """Pass 1 should work when article content is empty string."""
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            return_value=_make_pass1_llm_response(upsc_relevance=70)
        )
        mock_syllabus_cls.return_value.match_topics.return_value = []

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.run_pass1(SAMPLE_ARTICLE_EMPTY_CONTENT)
        assert result["upsc_relevance"] == 70


# ============================================================================
# TESTS: Pass 2 — Full 5-Layer Knowledge Card
# ============================================================================


class TestRunPass2:
    """Test run_pass2 — PYQ lookup + full knowledge card generation."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass2_returns_dict(self, mock_pyq_cls, mock_syllabus_cls, mock_llm):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(return_value=_make_pass2_llm_response())
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = MOCK_PYQS
        mock_pyq_instance.format_for_knowledge_card.return_value = MOCK_PYQ_FORMATTED

        pipeline = KnowledgeCardPipeline()
        pass1 = {
            "upsc_relevance": 78,
            "gs_paper": "GS3",
            "key_facts": ["Repo Rate", "Monetary Policy", "RBI"],
            "keywords": ["Repo Rate", "Monetary Policy", "RBI"],
            "syllabus_matches": MOCK_SYLLABUS_MATCHES,
            "raw_pass1_data": {"summary": "RBI cut repo rate."},
        }
        result = await pipeline.run_pass2(SAMPLE_ARTICLE, pass1)
        assert isinstance(result, dict)

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass2_has_5_layer_keys(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(return_value=_make_pass2_llm_response())
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = MOCK_PYQS
        mock_pyq_instance.format_for_knowledge_card.return_value = MOCK_PYQ_FORMATTED

        pipeline = KnowledgeCardPipeline()
        pass1 = {
            "upsc_relevance": 78,
            "gs_paper": "GS3",
            "key_facts": ["Repo Rate", "Monetary Policy", "RBI"],
            "keywords": ["Repo Rate", "Monetary Policy", "RBI"],
            "syllabus_matches": MOCK_SYLLABUS_MATCHES,
            "raw_pass1_data": {"summary": "RBI cut repo rate."},
        }
        result = await pipeline.run_pass2(SAMPLE_ARTICLE, pass1)
        required_keys = {
            "headline_layer",
            "facts_layer",
            "context_layer",
            "connections_layer",
            "mains_angle_layer",
        }
        assert required_keys.issubset(result.keys())

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass2_connections_layer_has_pyq_data(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(return_value=_make_pass2_llm_response())
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = MOCK_PYQS
        mock_pyq_instance.format_for_knowledge_card.return_value = MOCK_PYQ_FORMATTED

        pipeline = KnowledgeCardPipeline()
        pass1 = {
            "upsc_relevance": 78,
            "gs_paper": "GS3",
            "key_facts": ["Repo Rate", "Monetary Policy", "RBI"],
            "keywords": ["Repo Rate", "Monetary Policy", "RBI"],
            "syllabus_matches": MOCK_SYLLABUS_MATCHES,
            "raw_pass1_data": {"summary": "RBI cut repo rate."},
        }
        result = await pipeline.run_pass2(SAMPLE_ARTICLE, pass1)
        conn = result["connections_layer"]
        assert "syllabus_topics" in conn
        assert "related_pyqs" in conn
        assert "pyq_count" in conn
        assert conn["pyq_count"] == 2
        assert conn["related_pyqs"] == MOCK_PYQ_FORMATTED["related_pyqs"]

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass2_calls_pyq_service(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(return_value=_make_pass2_llm_response())
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = MOCK_PYQS
        mock_pyq_instance.format_for_knowledge_card.return_value = MOCK_PYQ_FORMATTED

        pipeline = KnowledgeCardPipeline()
        pass1 = {
            "upsc_relevance": 78,
            "gs_paper": "GS3",
            "key_facts": ["Repo Rate", "Monetary Policy", "RBI"],
            "keywords": ["Repo Rate", "Monetary Policy", "RBI"],
            "syllabus_matches": MOCK_SYLLABUS_MATCHES,
            "raw_pass1_data": {"summary": "RBI cut repo rate."},
        }
        await pipeline.run_pass2(SAMPLE_ARTICLE, pass1)
        mock_pyq_instance.find_related_pyqs.assert_called_once()
        mock_pyq_instance.format_for_knowledge_card.assert_called_once_with(MOCK_PYQS)

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass2_facts_layer_is_list(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(return_value=_make_pass2_llm_response())
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = MOCK_PYQS
        mock_pyq_instance.format_for_knowledge_card.return_value = MOCK_PYQ_FORMATTED

        pipeline = KnowledgeCardPipeline()
        pass1 = {
            "upsc_relevance": 78,
            "gs_paper": "GS3",
            "key_facts": ["Repo Rate"],
            "keywords": ["Repo Rate"],
            "syllabus_matches": MOCK_SYLLABUS_MATCHES,
            "raw_pass1_data": {"summary": "RBI cut."},
        }
        result = await pipeline.run_pass2(SAMPLE_ARTICLE, pass1)
        assert isinstance(result["facts_layer"], list)
        assert all(isinstance(f, str) for f in result["facts_layer"])

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass2_raises_on_llm_failure(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            return_value=_make_pass2_llm_response(
                success=False, error_message="Rate limited"
            )
        )
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = []
        mock_pyq_instance.format_for_knowledge_card.return_value = {
            "related_pyqs": [],
            "pyq_count": 0,
            "year_range": None,
            "exam_types": [],
        }

        pipeline = KnowledgeCardPipeline()
        pass1 = {
            "upsc_relevance": 78,
            "gs_paper": "GS3",
            "key_facts": ["Repo Rate"],
            "keywords": ["Repo Rate"],
            "syllabus_matches": [],
            "raw_pass1_data": {"summary": "RBI cut."},
        }
        with pytest.raises(RuntimeError, match="Pass 2 LLM failed"):
            await pipeline.run_pass2(SAMPLE_ARTICLE, pass1)

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_pass2_connections_layer_has_year_range(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(return_value=_make_pass2_llm_response())
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = MOCK_PYQS
        mock_pyq_instance.format_for_knowledge_card.return_value = MOCK_PYQ_FORMATTED

        pipeline = KnowledgeCardPipeline()
        pass1 = {
            "upsc_relevance": 78,
            "gs_paper": "GS3",
            "key_facts": ["Repo Rate"],
            "keywords": ["Repo Rate"],
            "syllabus_matches": MOCK_SYLLABUS_MATCHES,
            "raw_pass1_data": {"summary": "RBI cut."},
        }
        result = await pipeline.run_pass2(SAMPLE_ARTICLE, pass1)
        conn = result["connections_layer"]
        assert "year_range" in conn
        assert conn["year_range"] == "2021-2023"


# ============================================================================
# TESTS: Priority Triage Logic
# ============================================================================


class TestComputeTriage:
    """Test _compute_triage — priority classification logic."""

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_triage_must_know_high_relevance(self, mock_pyq_cls, mock_syllabus_cls):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        pass1 = {"upsc_relevance": 85}
        article = {"source_site": "other", "section": "news"}
        assert pipeline._compute_triage(pass1, article) == "must_know"

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_triage_must_know_editorial_source(self, mock_pyq_cls, mock_syllabus_cls):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        pass1 = {"upsc_relevance": 60}  # below 80 but editorial source
        article = {"source_site": "indianexpress", "section": "editorials"}
        assert pipeline._compute_triage(pass1, article) == "must_know"

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_triage_must_know_hindu_editorial(self, mock_pyq_cls, mock_syllabus_cls):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        pass1 = {"upsc_relevance": 58}
        article = {"source_site": "hindu", "section": "editorial"}
        assert pipeline._compute_triage(pass1, article) == "must_know"

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_triage_should_know(self, mock_pyq_cls, mock_syllabus_cls):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        pass1 = {"upsc_relevance": 72}
        article = {"source_site": "prs", "section": "legislation"}
        assert pipeline._compute_triage(pass1, article) == "should_know"

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_triage_good_to_know(self, mock_pyq_cls, mock_syllabus_cls):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        pass1 = {"upsc_relevance": 58}
        article = {"source_site": "other", "section": "news"}
        assert pipeline._compute_triage(pass1, article) == "good_to_know"

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_triage_boundary_80_is_must_know(self, mock_pyq_cls, mock_syllabus_cls):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        pass1 = {"upsc_relevance": 80}
        article = {"source_site": "other", "section": "news"}
        assert pipeline._compute_triage(pass1, article) == "must_know"

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_triage_boundary_65_is_should_know(self, mock_pyq_cls, mock_syllabus_cls):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        pass1 = {"upsc_relevance": 65}
        article = {"source_site": "other", "section": "news"}
        assert pipeline._compute_triage(pass1, article) == "should_know"

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_triage_missing_section_defaults_to_empty(
        self, mock_pyq_cls, mock_syllabus_cls
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        pass1 = {"upsc_relevance": 58}
        article = {"source_site": "other"}  # no section key
        assert pipeline._compute_triage(pass1, article) == "good_to_know"


# ============================================================================
# TESTS: Full process_article flow
# ============================================================================


class TestProcessArticle:
    """Test process_article — full pipeline: pass1 → filter → pass2 → triage."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_process_article_returns_enriched_dict(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            side_effect=[
                _make_pass1_llm_response(upsc_relevance=78),
                _make_pass2_llm_response(),
            ]
        )
        mock_syllabus_cls.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = MOCK_PYQS
        mock_pyq_instance.format_for_knowledge_card.return_value = MOCK_PYQ_FORMATTED

        # Use article NOT in MUST_KNOW_SOURCES so relevance=78 → should_know
        neutral_article = {
            "title": "RBI cuts repo rate by 25 bps to 6.25% to boost growth",
            "content": "The Reserve Bank of India cut the repo rate by 25 basis points.",
            "url": "https://livemint.com/economy/rbi-rate-cut-12345/",
            "source_site": "livemint",
            "section": "economy",
        }
        pipeline = KnowledgeCardPipeline()
        result = await pipeline.process_article(neutral_article)
        assert result is not None
        assert result["title"] == neutral_article["title"]
        assert result["upsc_relevance"] == 78
        assert result["gs_paper"] == "GS3"
        assert result["priority_triage"] == "should_know"
        assert "headline_layer" in result
        assert "facts_layer" in result
        assert "context_layer" in result
        assert "connections_layer" in result
        assert "mains_angle_layer" in result

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_process_article_filters_low_relevance(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            return_value=_make_pass1_llm_response(upsc_relevance=30)
        )
        mock_syllabus_cls.return_value.match_topics.return_value = []

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.process_article(SAMPLE_ARTICLE_LOW_RELEVANCE)
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_process_article_filters_at_threshold_boundary(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        """Score exactly 39 (just below 40) should be filtered."""
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            return_value=_make_pass1_llm_response(upsc_relevance=39)
        )
        mock_syllabus_cls.return_value.match_topics.return_value = []

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.process_article(SAMPLE_ARTICLE_LOW_RELEVANCE)
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_process_article_passes_at_threshold_boundary(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        """Score exactly 40 should pass the filter."""
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            side_effect=[
                _make_pass1_llm_response(upsc_relevance=40),
                _make_pass2_llm_response(),
            ]
        )
        mock_syllabus_cls.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = []
        mock_pyq_instance.format_for_knowledge_card.return_value = {
            "related_pyqs": [],
            "pyq_count": 0,
            "year_range": "",
            "exam_types": [],
        }

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.process_article(SAMPLE_ARTICLE)
        assert result is not None
        assert result["upsc_relevance"] == 40

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_process_article_must_know_triage(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            side_effect=[
                _make_pass1_llm_response(upsc_relevance=90),
                _make_pass2_llm_response(),
            ]
        )
        mock_syllabus_cls.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = MOCK_PYQS
        mock_pyq_instance.format_for_knowledge_card.return_value = MOCK_PYQ_FORMATTED

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.process_article(SAMPLE_ARTICLE)
        assert result["priority_triage"] == "must_know"

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_process_article_preserves_original_article_keys(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            side_effect=[
                _make_pass1_llm_response(upsc_relevance=70),
                _make_pass2_llm_response(),
            ]
        )
        mock_syllabus_cls.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = []
        mock_pyq_instance.format_for_knowledge_card.return_value = {
            "related_pyqs": [],
            "pyq_count": 0,
            "year_range": "",
            "exam_types": [],
        }

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.process_article(SAMPLE_ARTICLE)
        # Original article keys preserved
        assert result["title"] == SAMPLE_ARTICLE["title"]
        assert result["url"] == SAMPLE_ARTICLE["url"]
        assert result["source_site"] == SAMPLE_ARTICLE["source_site"]

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_process_article_does_not_call_pass2_when_filtered(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        """When article is filtered, Pass 2 LLM should NOT be called."""
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            return_value=_make_pass1_llm_response(upsc_relevance=30)
        )
        mock_syllabus_cls.return_value.match_topics.return_value = []

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.process_article(SAMPLE_ARTICLE_LOW_RELEVANCE)
        assert result is None
        # process_request called only once (Pass 1), not twice
        assert mock_llm.process_request.call_count == 1


# ============================================================================
# TESTS: TaskType enum addition
# ============================================================================


class TestTaskTypeEnum:
    """Test that KNOWLEDGE_CARD TaskType exists."""

    def test_knowledge_card_task_type_exists(self):
        from app.models.llm_schemas import TaskType

        assert hasattr(TaskType, "KNOWLEDGE_CARD")
        assert TaskType.KNOWLEDGE_CARD.value == "knowledge_card"


# ============================================================================
# TESTS: MUST_KNOW bypass in process_article
# ============================================================================


class TestMustKnowBypass:
    """Test that MUST_KNOW sources bypass the relevance filter in process_article."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_must_know_source_bypasses_relevance_filter(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        """Hindu editorial with relevance=30 should NOT be filtered — bypass must_know."""
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            side_effect=[
                _make_pass1_llm_response(upsc_relevance=30),
                _make_pass2_llm_response(),
            ]
        )
        mock_syllabus_cls.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = MOCK_PYQS
        mock_pyq_instance.format_for_knowledge_card.return_value = MOCK_PYQ_FORMATTED

        hindu_editorial = {
            "title": "The governance deficit in India",
            "content": "An editorial about governance challenges in modern India.",
            "url": "https://thehindu.com/opinion/editorial/governance-deficit/",
            "source_site": "hindu",
            "section": "editorial",
        }
        pipeline = KnowledgeCardPipeline()
        result = await pipeline.process_article(hindu_editorial)
        assert result is not None, "Hindu editorial must NOT be filtered even with relevance=30"
        assert result["priority_triage"] == "must_know"

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_non_must_know_source_filtered_at_low_relevance(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        """Non-MUST_KNOW article with relevance=30 SHOULD be filtered (None)."""
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            return_value=_make_pass1_llm_response(upsc_relevance=30)
        )
        mock_syllabus_cls.return_value.match_topics.return_value = []

        non_must_know = {
            "title": "Celebrity gossip article",
            "content": "Some irrelevant content.",
            "url": "https://example.com/gossip/",
            "source_site": "example",
            "section": "entertainment",
        }
        pipeline = KnowledgeCardPipeline()
        result = await pipeline.process_article(non_must_know)
        assert result is None, "Non-MUST_KNOW article with relevance=30 must be filtered"

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_non_must_know_source_passes_at_high_relevance(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        """Non-MUST_KNOW article with relevance=60 (>= threshold) is NOT filtered."""
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            side_effect=[
                _make_pass1_llm_response(upsc_relevance=60),
                _make_pass2_llm_response(),
            ]
        )
        mock_syllabus_cls.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = []
        mock_pyq_instance.format_for_knowledge_card.return_value = {
            "related_pyqs": [],
            "pyq_count": 0,
            "year_range": "",
            "exam_types": [],
        }

        normal_article = {
            "title": "Parliament passes new bill",
            "content": "Parliament passed a significant bill on governance.",
            "url": "https://livemint.com/news/parliament-bill/",
            "source_site": "livemint",
            "section": "politics",
        }
        pipeline = KnowledgeCardPipeline()
        result = await pipeline.process_article(normal_article)
        assert result is not None, "Normal article with relevance=60 must pass the filter"

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_is_must_know_method_exists(self, mock_pyq_cls, mock_syllabus_cls):
        """_is_must_know() private method must exist on KnowledgeCardPipeline."""
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        assert hasattr(pipeline, "_is_must_know"), "_is_must_know method must exist"

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_is_must_know_returns_true_for_hindu_editorial(
        self, mock_pyq_cls, mock_syllabus_cls
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        article = {"source_site": "hindu", "section": "editorial"}
        assert pipeline._is_must_know(article) is True

    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    def test_is_must_know_returns_false_for_non_must_know(
        self, mock_pyq_cls, mock_syllabus_cls
    ):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        pipeline = KnowledgeCardPipeline()
        article = {"source_site": "example", "section": "entertainment"}
        assert pipeline._is_must_know(article) is False



# ============================================================================
# TESTS: Threshold boundary with new value (40, from config)
# ============================================================================


class TestThresholdConfigurable:
    """Verify that the threshold comes from settings and is 40, not 55."""

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_process_article_filters_below_40(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        """FAILING UNTIL IMPL: score 39 is below new threshold (40) and must be filtered."""
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            return_value=_make_pass1_llm_response(upsc_relevance=39)
        )
        mock_syllabus_cls.return_value.match_topics.return_value = []

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.process_article(SAMPLE_ARTICLE_LOW_RELEVANCE)
        assert result is None

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_process_article_passes_at_exactly_40(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        """FAILING UNTIL IMPL: score exactly 40 should PASS the new threshold."""
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            side_effect=[
                _make_pass1_llm_response(upsc_relevance=40),
                _make_pass2_llm_response(),
            ]
        )
        mock_syllabus_cls.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = []
        mock_pyq_instance.format_for_knowledge_card.return_value = {
            "related_pyqs": [],
            "pyq_count": 0,
            "year_range": "",
            "exam_types": [],
        }

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.process_article(SAMPLE_ARTICLE)
        assert result is not None
        assert result["upsc_relevance"] == 40

    @pytest.mark.asyncio
    @patch("app.services.knowledge_card_pipeline.llm_service")
    @patch("app.services.knowledge_card_pipeline.SyllabusService")
    @patch("app.services.knowledge_card_pipeline.PYQService")
    async def test_process_article_score_50_passes_new_threshold(
        self, mock_pyq_cls, mock_syllabus_cls, mock_llm
    ):
        """FAILING UNTIL IMPL: score 50 is ABOVE 40 so must pass (was incorrectly filtered at 55)."""
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        mock_llm.process_request = AsyncMock(
            side_effect=[
                _make_pass1_llm_response(upsc_relevance=50),
                _make_pass2_llm_response(),
            ]
        )
        mock_syllabus_cls.return_value.match_topics.return_value = MOCK_SYLLABUS_MATCHES
        mock_pyq_instance = mock_pyq_cls.return_value
        mock_pyq_instance.find_related_pyqs.return_value = []
        mock_pyq_instance.format_for_knowledge_card.return_value = {
            "related_pyqs": [],
            "pyq_count": 0,
            "year_range": "",
            "exam_types": [],
        }

        pipeline = KnowledgeCardPipeline()
        result = await pipeline.process_article(SAMPLE_ARTICLE)
        assert result is not None
        assert result["upsc_relevance"] == 50


# ============================================================================
# TESTS: MUST_KNOW_SOURCES updated with new curated institutional sources
# ============================================================================


class TestMustKnowSourcesUpdated:
    """Verify MUST_KNOW_SOURCES contains 8 tuples including new Wave 2-3 sources."""

    def test_must_know_sources_count(self):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        assert len(KnowledgeCardPipeline.MUST_KNOW_SOURCES) == 8

    def test_mea_press_releases_is_must_know(self):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        assert ("mea", "press-releases") in KnowledgeCardPipeline.MUST_KNOW_SOURCES

    def test_orf_expert_speak_is_must_know(self):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        assert ("orf", "expert-speak") in KnowledgeCardPipeline.MUST_KNOW_SOURCES

    def test_rbi_economy_is_must_know(self):
        from app.services.knowledge_card_pipeline import KnowledgeCardPipeline

        assert ("rbi", "economy") in KnowledgeCardPipeline.MUST_KNOW_SOURCES