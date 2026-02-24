"""
KnowledgeCardPipeline — two-pass LLM enrichment engine.

Pass 1: UPSC_ANALYSIS LLM + SyllabusService for relevance scoring, fact extraction, syllabus matching.
Pass 2: PYQService + KNOWLEDGE_CARD LLM for full 5-layer knowledge card generation.

No database writes here — that's T14.
"""

import logging
import hashlib
import json
import random
from app.core.config import settings
from typing import Any, Optional

from app.models.llm_schemas import LLMRequest, TaskType, ProviderPreference
from app.services.centralized_llm_service import llm_service
from app.services.syllabus_service import SyllabusService
from app.services.pyq_service import PYQService

logger = logging.getLogger(__name__)


class KnowledgeCardPipeline:
    """Two-pass LLM pipeline that enriches articles into 5-layer UPSC knowledge cards."""



    MUST_KNOW_SOURCES: set[tuple[str, str]] = {
        ("indianexpress", "explained"),
        ("indianexpress", "editorials"),
        ("hindu", "editorial"),
        ("hindu", "opinion"),
        ("mea", "press-releases"),
        ("orf", "expert-speak"),
        ("idsa", "comment-briefs"),
        ("rbi", "economy"),
    }

    def __init__(self) -> None:
        self.syllabus_service = SyllabusService()
        self.pyq_service = PYQService()
        self.relevance_threshold = settings.relevance_threshold

    # ------------------------------------------------------------------
    # Pass 1 — Relevance + Facts + Syllabus
    # ------------------------------------------------------------------

    async def run_pass1(self, article: dict[str, Any]) -> dict[str, Any]:
        """Run Pass 1: LLM UPSC_ANALYSIS + syllabus matching.

        Returns dict with keys:
            upsc_relevance, gs_paper, key_facts, keywords,
            syllabus_matches, raw_pass1_data
        """
        content = article.get("content") or ""
        title = article.get("title", "")

        if not content:
            logger.warning(
                "[Pass1] Article has no content, using title only: %s", title
            )
            content = title

        llm_input = f"Title: {title}\n\nContent: {content}"

        response = await llm_service.process_request(
            LLMRequest(
                task_type=TaskType.UPSC_ANALYSIS,
                content=llm_input,
                provider_preference=ProviderPreference.COST_OPTIMIZED,
                temperature=0.1,
            )
        )

        if not response.success:
            raise RuntimeError(
                f"Pass 1 LLM failed: {response.error_message}"
            )

        data = response.data
        relevant_papers: list[str] = data.get("relevant_papers", [])
        key_topics: list[str] = data.get("key_topics", [])

        gs_paper = relevant_papers[0] if relevant_papers else "GS2"

        # Syllabus matching
        syllabus_text = f"{title} {content}"
        syllabus_matches = self.syllabus_service.match_topics(
            text=syllabus_text,
            keywords=key_topics,
        )

        return {
            "upsc_relevance": data.get("upsc_relevance", 0),
            "gs_paper": gs_paper,
            "key_facts": key_topics,
            "keywords": key_topics,
            "syllabus_matches": syllabus_matches,
            "raw_pass1_data": data,
        }

    # ------------------------------------------------------------------
    # Pass 1 Batch — Batch scoring via UPSC_BATCH_ANALYSIS
    # ------------------------------------------------------------------

    async def run_pass1_batch(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Batch-score multiple articles via UPSC_BATCH_ANALYSIS (10 per call, 2 shuffled passes).
        
        Returns list of dicts with SAME shape as run_pass1() for each article.
        MUST_KNOW articles that fail batch scoring fall back to individual run_pass1().
        Non-MUST_KNOW articles that fail batch scoring are skipped.
        """
        BATCH_SIZE = 10
        results: list[dict[str, Any]] = []
        batches = [articles[i:i+BATCH_SIZE] for i in range(0, len(articles), BATCH_SIZE)]

        # Helper to build payload JSON
        def build_payload(ordered_articles: list[dict[str, Any]], ordered_ids: list[str]) -> str:
            return json.dumps({
                "articles": [
                    {
                        "article_id": aid,
                        "title": a.get("title", ""),
                        "content": (a.get("content") or "")[:500]
                    }
                    for aid, a in zip(ordered_ids, ordered_articles)
                ]
            })

        # Helper to call batch LLM
        async def call_batch(payload: str):
            return await llm_service.process_request(
                LLMRequest(
                    task_type=TaskType.UPSC_BATCH_ANALYSIS,
                    content=payload,
                    provider_preference=ProviderPreference.COST_OPTIMIZED,
                    temperature=0.1,
                )
            )

        for batch_idx, batch in enumerate(batches):
            # Build stable article IDs (URL hash → 8 chars)
            batch_with_ids: list[tuple[str, dict[str, Any]]] = [
                (hashlib.md5(a.get('url', a.get('source_url', '')).encode()).hexdigest()[:8], a)
                for a in batch
            ]
            id_to_article: dict[str, dict[str, Any]] = {aid: a for aid, a in batch_with_ids}

            # Pass A: original order
            pass_a_ids = [aid for aid, _ in batch_with_ids]
            pass_a_articles = [a for _, a in batch_with_ids]
            pass_a_payload = build_payload(pass_a_articles, pass_a_ids)

            # Pass B: shuffled order (seed 42 for test determinism)
            random.seed(42)
            pass_b_indices = random.sample(range(len(batch)), len(batch))
            pass_b_articles = [batch_with_ids[i][1] for i in pass_b_indices]
            pass_b_ids = [batch_with_ids[i][0] for i in pass_b_indices]
            pass_b_payload = build_payload(pass_b_articles, pass_b_ids)

            # Run LLM calls sequentially (no asyncio.gather)
            try:
                resp_a = await call_batch(pass_a_payload)
                if not resp_a.success:
                    raise RuntimeError(f"Pass A failed: {resp_a.error_message}")
                resp_b = await call_batch(pass_b_payload)
                if not resp_b.success:
                    raise RuntimeError(f"Pass B failed: {resp_b.error_message}")
            except Exception as exc:
                # Retry once
                logger.warning("[Pass1Batch] Batch %d/%d failed (%s), retrying...", batch_idx + 1, len(batches), exc)
                try:
                    resp_a = await call_batch(pass_a_payload)
                    if not resp_a.success:
                        raise RuntimeError(f"Pass A retry failed: {resp_a.error_message}")
                    resp_b = await call_batch(pass_b_payload)
                    if not resp_b.success:
                        raise RuntimeError(f"Pass B retry failed: {resp_b.error_message}")
                except Exception as retry_exc:
                    # Fallback: MUST_KNOW → individual run_pass1(), others skipped
                    must_know_count = sum(1 for _, a in batch_with_ids if self._is_must_know(a))
                    logger.warning(
                        "[Pass1Batch] Batch %d/%d failed after retry, falling back for %d MUST_KNOW articles",
                        batch_idx + 1, len(batches), must_know_count
                    )
                    for aid, article in batch_with_ids:
                        if self._is_must_know(article):
                            try:
                                pass1_result = await self.run_pass1(article)
                                results.append(pass1_result)
                            except Exception as ind_exc:
                                logger.error("[Pass1Batch] Individual fallback failed for %s: %s", article.get("title"), ind_exc)
                    continue

            # Build score maps from LLM responses
            # resp_a.data = {"articles": [{"article_id": ..., "upsc_relevance": int, ...}]}
            a_scored: dict[str, dict[str, Any]] = {
                art["article_id"]: art
                for art in resp_a.data.get("articles", [])
                if "article_id" in art
            }
            b_scored: dict[str, dict[str, Any]] = {
                art["article_id"]: art
                for art in resp_b.data.get("articles", [])
                if "article_id" in art
            }

            # For each article in batch, average scores
            for aid, article in batch_with_ids:
                a_data = a_scored.get(aid)
                b_data = b_scored.get(aid)

                if a_data is None and b_data is None:
                    logger.warning("[Pass1Batch] Article %s missing from both pass responses, skipping", aid)
                    continue

                # Use whichever pass has data; average if both present
                if a_data is not None and b_data is not None:
                    score_a = a_data.get("upsc_relevance", 0)
                    score_b = b_data.get("upsc_relevance", 0)
                    averaged_score = round((score_a + score_b) / 2)
                elif a_data is not None:
                    averaged_score = a_data.get("upsc_relevance", 0)
                else:
                    averaged_score = b_data.get("upsc_relevance", 0)

                # Non-numeric fields from Pass A (fall back to B if A missing)
                primary_data = a_data if a_data is not None else b_data
                relevant_papers: list[str] = primary_data.get("relevant_papers", [])
                key_topics: list[str] = primary_data.get("key_topics", [])

                # Syllabus matching
                syllabus_text = f"{article.get('title', '')} {article.get('content', '')}"
                syllabus_matches = self.syllabus_service.match_topics(
                    text=syllabus_text,
                    keywords=key_topics,
                )

                results.append({
                    "upsc_relevance": averaged_score,
                    "gs_paper": relevant_papers[0] if relevant_papers else "GS2",
                    "key_facts": key_topics,
                    "keywords": key_topics,
                    "syllabus_matches": syllabus_matches,
                    "raw_pass1_data": primary_data,
                })

        return results

    # ------------------------------------------------------------------
    # Pass 2 — Full 5-Layer Knowledge Card
    # ------------------------------------------------------------------

    async def run_pass2(
        self, article: dict[str, Any], pass1_result: dict[str, Any]
    ) -> dict[str, Any]:
        """Run Pass 2: PYQ lookup + KNOWLEDGE_CARD LLM.

        Returns dict with 5-layer knowledge card:
            headline_layer, facts_layer, context_layer,
            connections_layer, mains_angle_layer
        """
        keywords = pass1_result.get("keywords", [])
        gs_paper = pass1_result.get("gs_paper", "GS2")
        syllabus_matches = pass1_result.get("syllabus_matches", [])
        raw_data = pass1_result.get("raw_pass1_data", {})

        # PYQ lookup
        related_pyqs = self.pyq_service.find_related_pyqs(
            keywords=keywords,
            topics=keywords,
            gs_paper=gs_paper,
        )
        pyq_formatted = self.pyq_service.format_for_knowledge_card(related_pyqs)

        # Build context for LLM
        title = article.get("title", "")
        content = article.get("content") or title
        summary = raw_data.get("summary", "")

        syllabus_context = ", ".join(
            f"{m['paper']}/{m['topic']}/{m['sub_topic']}"
            for m in syllabus_matches[:5]
        ) or "No syllabus matches"

        pyq_context = ""
        for pyq in pyq_formatted.get("related_pyqs", [])[:3]:
            pyq_context += (
                f"- [{pyq.get('year', '')} {pyq.get('exam_type', '')}] "
                f"{pyq.get('question_summary', '')}\n"
            )
        pyq_context = pyq_context.strip() or "No related PYQs found"

        custom_instructions = (
            f"Article title: {title}\n"
            f"GS Paper: {gs_paper}\n"
            f"Key topics: {', '.join(keywords)}\n"
            f"Summary: {summary}\n"
            f"\nPYQ Context:\n{pyq_context}\n"
            f"\nSyllabus Context:\n{syllabus_context}"
        )

        llm_input = f"Title: {title}\n\nContent: {content}"

        response = await llm_service.process_request(
            LLMRequest(
                task_type=TaskType.KNOWLEDGE_CARD,
                content=llm_input,
                custom_instructions=custom_instructions,
                provider_preference=ProviderPreference.COST_OPTIMIZED,
                temperature=0.2,
            )
        )

        if not response.success:
            raise RuntimeError(
                f"Pass 2 LLM failed: {response.error_message}"
            )

        card_data = response.data

        # Build connections_layer (the 5th layer, assembled here not by LLM)
        connections_layer: dict[str, Any] = {
            "syllabus_topics": syllabus_matches,
            "related_pyqs": pyq_formatted.get("related_pyqs", []),
            "pyq_count": pyq_formatted.get("pyq_count", 0),
            "year_range": pyq_formatted.get("year_range", ""),
        }

        return {
            "headline_layer": card_data.get("headline_layer", ""),
            "facts_layer": card_data.get("facts_layer", []),
            "context_layer": card_data.get("context_layer", ""),
            "connections_layer": connections_layer,
            "mains_angle_layer": card_data.get("mains_angle_layer", ""),
        }

    # ------------------------------------------------------------------
    # Triage Logic
    # ------------------------------------------------------------------

    def _compute_triage(
        self, pass1_result: dict[str, Any], article: dict[str, Any]
    ) -> str:
        """Classify article priority: must_know, should_know, or good_to_know.

        Rules:
            - relevance >= 80 → must_know
            - source in MUST_KNOW_SOURCES → must_know
            - relevance >= 65 → should_know
            - else → good_to_know
        """
        relevance = pass1_result.get("upsc_relevance", 0)
        source_site = article.get("source_site", "")
        section = article.get("section", "")

        if relevance >= 80:
            return "must_know"

        if (source_site, section) in self.MUST_KNOW_SOURCES:
            return "must_know"

        if relevance >= 65:
            return "should_know"

        return "good_to_know"

    def _is_must_know(self, article: dict[str, Any]) -> bool:
        """Return True if the article source is in MUST_KNOW_SOURCES."""
        source_site = article.get("source_site", "")
        section = article.get("section", "")
        return (source_site, section) in self.MUST_KNOW_SOURCES

    # ------------------------------------------------------------------
    # Full Pipeline
    # ------------------------------------------------------------------

    async def process_article(
        self, article: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Full pipeline: pass1 → must_know check → filter → pass2 → triage.
        Returns enriched dict or None if below relevance threshold.
        MUST_KNOW sources always bypass the relevance filter.
        """

        title = article.get("title", "untitled")
        logger.info("[Pipeline] Processing: %s", title)

        pass1 = await self.run_pass1(article)
        relevance = pass1["upsc_relevance"]

        # MUST_KNOW check — bypass relevance filter if source is MUST_KNOW
        if self._is_must_know(article):
            logger.info(
                "[Pipeline] MUST_KNOW source, bypassing threshold: %s", title
            )
        elif relevance < self.relevance_threshold:
            # Filter non-MUST_KNOW articles below threshold
            logger.info(
                "[Pipeline] Filtered (relevance=%d < %d): %s",
                relevance,
                self.relevance_threshold,
                title,
            )
            return None

        pass2 = await self.run_pass2(article, pass1)

        triage = self._compute_triage(pass1, article)

        result: dict[str, Any] = {**article}
        result.update({
            "upsc_relevance": relevance,
            "gs_paper": pass1["gs_paper"],
            "key_facts": pass1["key_facts"],
            "keywords": pass1["keywords"],
            "syllabus_matches": pass1["syllabus_matches"],
            "priority_triage": triage,
            "headline_layer": pass2["headline_layer"],
            "facts_layer": pass2["facts_layer"],
            "context_layer": pass2["context_layer"],
            "connections_layer": pass2["connections_layer"],
            "mains_angle_layer": pass2["mains_angle_layer"],
        })

        logger.info(
            "[Pipeline] Enriched (%s, relevance=%d): %s",
            triage,
            relevance,
            title,
        )
        return result