"""
ArticleSelector — Smart article selection for UPSC daily knowledge cards.

Implements 3-stage pipeline:
1. Semantic deduplication (TF-IDF cosine similarity — cross-source event dedup)
2. GS-balance pool creation (min coverage per GS paper before tournament)
3. Tournament selection (1 LLM call picks best 30 from ~50 balanced candidates)
"""

import hashlib
import json
import logging
from typing import Any

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.models.llm_schemas import LLMRequest, TaskType, ProviderPreference
from app.services.centralized_llm_service import llm_service

logger = logging.getLogger(__name__)


def _article_id(article: dict[str, Any]) -> str:
    """Stable URL-hash article ID (8-char MD5 hex prefix)."""
    url = article.get("url", article.get("source_url", ""))
    return hashlib.md5(url.encode()).hexdigest()[:8]


def _gs_paper(article: dict[str, Any]) -> str:
    """Extract primary GS paper from article, defaulting to GS2."""
    return article.get(
        "gs_paper",
        article.get("raw_pass1_data", {}).get("relevant_papers", ["GS2"])[0],
    )


class ArticleSelector:
    """Stateless service — selects the best 30 daily UPSC knowledge card articles."""

    # GS paper minimum quotas
    GS_MIN: dict[str, int] = {
        "GS1": 5,
        "GS2": 5,
        "GS3": 5,
        "GS4": 1,  # Ethics rarely in daily news
    }

    async def deduplicate_semantic(
        self,
        articles: list[dict[str, Any]],
        threshold: float = 0.40,
    ) -> list[dict[str, Any]]:
        """Remove near-duplicate articles (same event, different sources).

        For each pair with cosine similarity > threshold, keeps the one with
        higher upsc_relevance. Returns the deduplicated list.
        """
        if len(articles) < 2:
            return articles

        # Build corpus from titles (fast, effective for event dedup)
        corpus = [
            a.get("title", "") + " " + " ".join(
                a.get("raw_pass1_data", {}).get("key_topics", [])
                or a.get("key_facts", [])
                or []
            )
            for a in articles
        ]

        try:
            vectorizer = TfidfVectorizer(min_df=1)
            tfidf_matrix = vectorizer.fit_transform(corpus)
            sim_matrix = cosine_similarity(tfidf_matrix)
        except Exception as e:
            logger.warning("[ArticleSelector] TF-IDF failed, skipping dedup: %s", e)
            return articles

        # Greedy dedup: mark lower-scored duplicate as removed
        n = len(articles)
        removed = set()

        for i in range(n):
            if i in removed:
                continue
            for j in range(i + 1, n):
                if j in removed:
                    continue
                if sim_matrix[i, j] > threshold:
                    # Keep higher-scored article, remove the other
                    score_i = articles[i].get("upsc_relevance", 0)
                    score_j = articles[j].get("upsc_relevance", 0)
                    if score_i >= score_j:
                        removed.add(j)
                    else:
                        removed.add(i)
                        break  # i is removed, no need to compare further

        result = [a for idx, a in enumerate(articles) if idx not in removed]
        removed_count = n - len(result)
        if removed_count > 0:
            logger.info(
                "[ArticleSelector] Semantic dedup: removed %d duplicates, %d remain",
                removed_count,
                len(result),
            )
        return result

    async def balance_gs_pool(
        self,
        articles: list[dict[str, Any]],
        pool_size: int = 50,
    ) -> list[dict[str, Any]]:
        """Create a GS-balanced candidate pool before tournament.

        Reserves GS_MIN slots per paper (GS1≥5, GS2≥5, GS3≥5, GS4≥1), then
        fills remaining slots with highest-scored articles not already reserved.
        Returns up to pool_size articles.
        """
        if len(articles) <= pool_size:
            return articles

        # Group articles by GS paper (sort by relevance DESC within each group)
        by_gs: dict[str, list[dict[str, Any]]] = {}
        for article in articles:
            gs = _gs_paper(article)
            by_gs.setdefault(gs, []).append(article)

        for gs in by_gs:
            by_gs[gs].sort(key=lambda a: a.get("upsc_relevance", 0), reverse=True)

        # Reserve minimum quota per GS paper
        reserved: list[dict[str, Any]] = []
        reserved_ids: set[str] = set()

        for gs_paper, min_count in self.GS_MIN.items():
            candidates = by_gs.get(gs_paper, [])
            for article in candidates[:min_count]:
                aid = _article_id(article)
                if aid not in reserved_ids:
                    reserved.append(article)
                    reserved_ids.add(aid)

        # Fill remaining slots with highest-scored articles not already reserved
        remaining_slots = pool_size - len(reserved)
        if remaining_slots > 0:
            # Sort ALL articles by relevance DESC, skip already-reserved
            all_sorted = sorted(
                articles, key=lambda a: a.get("upsc_relevance", 0), reverse=True
            )
            for article in all_sorted:
                if remaining_slots <= 0:
                    break
                aid = _article_id(article)
                if aid not in reserved_ids:
                    reserved.append(article)
                    reserved_ids.add(aid)
                    remaining_slots -= 1

        logger.info(
            "[ArticleSelector] GS-balanced pool: %d articles (from %d)",
            len(reserved),
            len(articles),
        )
        return reserved

    async def tournament_select(
        self,
        articles: list[dict[str, Any]],
        target: int = 30,
    ) -> list[dict[str, Any]]:
        """Select top `target` articles via 1 LLM tournament call.

        Falls back to top-N-by-score deterministically if LLM call fails.
        """
        if len(articles) <= target:
            return articles

        # Build article index for lookup after LLM response
        id_to_article: dict[str, dict[str, Any]] = {_article_id(a): a for a in articles}

        # Build LLM payload
        tournament_payload = {
            "articles": [
                {
                    "article_id": _article_id(a),
                    "title": a.get("title", ""),
                    "upsc_relevance": a.get("upsc_relevance", 0),
                    "gs_paper": _gs_paper(a),
                    "summary": a.get("raw_pass1_data", {}).get("summary", "")[:200],
                }
                for a in articles
            ]
        }

        tournament_content = (
            f"Pool size: {len(articles)} articles. Select the TOP {target}.\n\n"
            + json.dumps(tournament_payload, ensure_ascii=False)
        )

        prompt_instructions = (
            f"You are selecting the TOP {target} articles for today's UPSC Current Affairs "
            f"from a pool of {len(articles)} candidates. "
            f"Criteria: exam relevance, topic diversity, factual significance, GS paper coverage. "
            f"Return the article_ids of your selections in order of importance."
        )

        try:
            response = await llm_service.process_request(
                LLMRequest(
                    task_type=TaskType.UPSC_BATCH_ANALYSIS,
                    content=tournament_content,
                    custom_instructions=prompt_instructions,
                    provider_preference=ProviderPreference.COST_OPTIMIZED,
                    temperature=0.1,
                )
            )

            if not response.success:
                raise RuntimeError(f"Tournament LLM failed: {response.error_message}")

            # Try to extract selected_article_ids from response
            selected_ids: list[str] = []
            data = response.data

            # Handle both direct response and articles-wrapped response
            if "selected_article_ids" in data:
                selected_ids = data["selected_article_ids"]
            elif "articles" in data:
                # Batch analysis response — order by upsc_relevance from LLM scores
                llm_articles = data["articles"]
                llm_sorted = sorted(
                    llm_articles,
                    key=lambda x: x.get("upsc_relevance", 0),
                    reverse=True,
                )
                selected_ids = [a["article_id"] for a in llm_sorted[:target]]

            # Map IDs back to articles
            selected = []
            for aid in selected_ids[:target]:
                if aid in id_to_article:
                    selected.append(id_to_article[aid])

            # If LLM returned fewer than target, pad with top-scored remaining
            if len(selected) < target:
                selected_set = {_article_id(a) for a in selected}
                for article in sorted(
                    articles,
                    key=lambda a: a.get("upsc_relevance", 0),
                    reverse=True,
                ):
                    if len(selected) >= target:
                        break
                    if _article_id(article) not in selected_set:
                        selected.append(article)

            logger.info(
                "[ArticleSelector] Tournament selected %d articles via LLM",
                len(selected),
            )
            return selected

        except Exception as e:
            logger.warning(
                "[ArticleSelector] Tournament LLM failed (%s), falling back to top-%d-by-score",
                e,
                target,
            )
            # SC4 fallback: deterministic top-N-by-score
            fallback = sorted(
                articles,
                key=lambda a: a.get("upsc_relevance", 0),
                reverse=True,
            )[:target]
            logger.info(
                "[ArticleSelector] Fallback selected %d articles by score",
                len(fallback),
            )
            return fallback

    async def select_top_articles(
        self,
        articles: list[dict[str, Any]],
        target: int = 30,
    ) -> list[dict[str, Any]]:
        """Orchestrator: dedup → GS-balance → tournament → final selection.

        Returns final list of up to `target` articles and logs GS distribution.
        """
        logger.info(
            "[ArticleSelector] Starting selection: %d articles → target %d",
            len(articles),
            target,
        )

        # Stage 1: Semantic deduplication
        deduped = await self.deduplicate_semantic(articles)

        # Stage 2: GS-balanced pool (~50 candidates)
        pool = await self.balance_gs_pool(deduped, pool_size=max(target + 20, 50))

        # Stage 3: Tournament selection
        selected = await self.tournament_select(pool, target=target)

        # Log GS distribution
        gs_dist: dict[str, int] = {}
        for article in selected:
            gs = _gs_paper(article)
            gs_dist[gs] = gs_dist.get(gs, 0) + 1

        logger.info(
            "[ArticleSelector] GS distribution: %s",
            ", ".join(f"{k}={v}" for k, v in sorted(gs_dist.items())),
        )

        return selected
