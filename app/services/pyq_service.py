"""
PYQ (Previous Year Questions) Service — keyword-based question matching.

Queries the pyq_questions Supabase table to find PYQs related to
article content for Layer 4 (Connections) of knowledge cards.

Pure keyword-based matching (no LLM dependency).
Uses Supabase client from app.core.database.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# GS paper → pyq_questions.subject mapping
GS_PAPER_SUBJECT_MAP: dict[str, list[str]] = {
    "GS1": ["History", "Geography", "Society"],
    "GS2": ["Polity", "Governance", "International Relations"],
    "GS3": ["Economy", "Science", "Environment", "Security"],
    "GS4": ["Ethics"],
}


class PYQService:
    """Queries the pyq_questions table for keyword-based PYQ matching."""

    def __init__(self, supabase_client=None) -> None:
        """Initialize with optional Supabase client (for testing)."""
        if supabase_client is not None:
            self._client = supabase_client
        else:
            from app.core.database import get_database_sync
            db = get_database_sync()
            self._client = db.client

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_related_pyqs(
        self,
        keywords: list[str],
        topics: Optional[list[str]] = None,
        gs_paper: Optional[str] = None,
        max_results: int = 5,
    ) -> list[dict]:
        """Find PYQs related to given keywords/topics.

        Strategy:
        1. If topics provided, filter by topics array overlap.
        2. If gs_paper provided, filter by subject mapping.
        3. Text search in question_text for keywords.
        4. Return sorted by year DESC (recent questions first).

        Args:
            keywords: Search keywords extracted from article content.
            topics: Optional topic strings to match against pyq topics array.
            gs_paper: Optional GS paper id (e.g. "GS1", "GS2") for subject filtering.
            max_results: Maximum number of PYQs to return.

        Returns:
            List of dicts with keys: question_id, question_text, year,
            exam_type, subject, topics, relevance_score.
        """
        if not keywords:
            return []

        try:
            results = self._query_pyqs(keywords, topics, gs_paper, max_results)
            return self._score_and_sort(results, keywords, max_results)
        except Exception as e:
            logger.error(f"Failed to find related PYQs: {e}")
            return []

    def get_pyq_stats(self) -> dict:
        """Get basic stats about the PYQ database.

        Returns:
            Dict with total_count, year_range, and subject_distribution.
        """
        try:
            result = self._client.table("pyq_questions").select(
                "id, year, subject"
            ).execute()
            rows = result.data or []

            if not rows:
                return {
                    "total_count": 0,
                    "year_range": None,
                    "subject_distribution": {},
                }

            years = [r["year"] for r in rows if r.get("year")]
            subjects: dict[str, int] = {}
            for r in rows:
                subj = r.get("subject", "Unknown")
                subjects[subj] = subjects.get(subj, 0) + 1

            return {
                "total_count": len(rows),
                "year_range": {
                    "min": min(years) if years else None,
                    "max": max(years) if years else None,
                },
                "subject_distribution": subjects,
            }
        except Exception as e:
            logger.error(f"Failed to get PYQ stats: {e}")
            return {
                "total_count": 0,
                "year_range": None,
                "subject_distribution": {},
            }

    def format_for_knowledge_card(self, pyqs: list[dict]) -> dict:
        """Format PYQ results for Layer 4 (Connections) of knowledge cards.

        Args:
            pyqs: List of PYQ dicts as returned by find_related_pyqs.

        Returns:
            Dict with related_pyqs, pyq_count, year_range, exam_types.
        """
        if not pyqs:
            return {
                "related_pyqs": [],
                "pyq_count": 0,
                "year_range": None,
                "exam_types": [],
            }

        related: list[dict] = []
        years: list[int] = []
        exam_types_set: set[str] = set()

        for pyq in pyqs:
            year = pyq.get("year")
            exam_type = pyq.get("exam_type", "")
            question_text = pyq.get("question_text", "")

            # Create a summary (first 150 chars)
            summary = (
                question_text[:150] + "..."
                if len(question_text) > 150
                else question_text
            )

            related.append({
                "year": year,
                "exam_type": exam_type,
                "question_summary": summary,
                "subject": pyq.get("subject", ""),
            })

            if year:
                years.append(year)
            if exam_type:
                exam_types_set.add(exam_type)

        year_range = (
            f"{min(years)}-{max(years)}"
            if years and min(years) != max(years)
            else str(years[0]) if years
            else None
        )

        return {
            "related_pyqs": related,
            "pyq_count": len(related),
            "year_range": year_range,
            "exam_types": sorted(exam_types_set),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _query_pyqs(
        self,
        keywords: list[str],
        topics: Optional[list[str]],
        gs_paper: Optional[str],
        limit: int,
    ) -> list[dict]:
        """Build and execute the Supabase query.

        Combines topic overlap, subject filtering, and text search.
        """
        select_fields = (
            "id, question_text, year, exam_type, subject, topics, upsc_relevance"
        )

        # --- Strategy A: topic overlap ---
        topic_results: list[dict] = []
        if topics:
            try:
                resp = (
                    self._client.table("pyq_questions")
                    .select(select_fields)
                    .overlaps("topics", topics)
                    .order("year", desc=True)
                    .limit(limit)
                    .execute()
                )
                topic_results = resp.data or []
            except Exception as e:
                logger.warning(f"Topic overlap query failed: {e}")

        # --- Strategy B: subject filter from GS paper ---
        subject_results: list[dict] = []
        if gs_paper and gs_paper in GS_PAPER_SUBJECT_MAP:
            subjects = GS_PAPER_SUBJECT_MAP[gs_paper]
            try:
                resp = (
                    self._client.table("pyq_questions")
                    .select(select_fields)
                    .in_("subject", subjects)
                    .order("year", desc=True)
                    .limit(limit)
                    .execute()
                )
                subject_results = resp.data or []
            except Exception as e:
                logger.warning(f"Subject filter query failed: {e}")

        # --- Strategy C: text search on top-3 keywords ---
        text_results: list[dict] = []
        top_keywords = keywords[:3]
        for kw in top_keywords:
            if len(kw) < 3:
                continue  # skip very short keywords
            try:
                resp = (
                    self._client.table("pyq_questions")
                    .select(select_fields)
                    .ilike("question_text", f"%{kw}%")
                    .order("year", desc=True)
                    .limit(limit)
                    .execute()
                )
                text_results.extend(resp.data or [])
            except Exception as e:
                logger.warning(f"Text search for '{kw}' failed: {e}")

        # Merge and deduplicate by id
        seen: set[str] = set()
        merged: list[dict] = []
        for row in topic_results + subject_results + text_results:
            row_id = row.get("id", "")
            if row_id and row_id not in seen:
                seen.add(row_id)
                merged.append(row)

        return merged

    def _score_and_sort(
        self,
        rows: list[dict],
        keywords: list[str],
        max_results: int,
    ) -> list[dict]:
        """Score each row by keyword match density and sort.

        Scoring formula:
        - Base: 0.3 (appeared in query results)
        - +0.1 per keyword found in question_text (max +0.5)
        - +0.1 if upsc_relevance is high (>= 70)
        - +0.1 if year is recent (>= 2020)
        """
        keyword_lower = [kw.lower() for kw in keywords]
        scored: list[dict] = []

        for row in rows:
            score = 0.3  # base score for appearing in results

            question_text_lower = (row.get("question_text") or "").lower()

            # Keyword density bonus (up to 0.5)
            kw_hits = sum(
                1 for kw in keyword_lower if kw in question_text_lower
            )
            score += min(kw_hits * 0.1, 0.5)

            # UPSC relevance bonus
            if (row.get("upsc_relevance") or 0) >= 70:
                score += 0.1

            # Recency bonus
            if (row.get("year") or 0) >= 2020:
                score += 0.1

            score = round(min(score, 1.0), 2)

            scored.append({
                "question_id": row.get("id", ""),
                "question_text": row.get("question_text", ""),
                "year": row.get("year"),
                "exam_type": row.get("exam_type", ""),
                "subject": row.get("subject", ""),
                "topics": row.get("topics") or [],
                "relevance_score": score,
            })

        # Sort: highest score first, then year DESC for tie-breaking
        scored.sort(key=lambda r: (-r["relevance_score"], -(r["year"] or 0)))
        return scored[:max_results]