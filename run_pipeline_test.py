"""
One-off script to test the full UnifiedPipeline locally.
Run from the backend/ directory:
    python run_pipeline_test.py
"""

import asyncio
import logging
import sys
import time

# Configure root logger FIRST so every module's logs are visible
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)

logger = logging.getLogger("pipeline_test")


async def main():
    from app.services.unified_pipeline import UnifiedPipeline

    logger.info("=" * 70)
    logger.info("FULL PIPELINE TEST — save_to_db=False (dry run)")
    logger.info("=" * 70)

    start = time.time()
    pipeline = UnifiedPipeline()
    result = await pipeline.run(save_to_db=False)
    elapsed = round(time.time() - start, 2)

    # ---- Summary ----
    logger.info("=" * 70)
    logger.info("PIPELINE FINISHED in %.2f seconds", elapsed)
    logger.info("  Total fetched   : %d", result.get("total_fetched", 0))
    logger.info("  Total enriched  : %d", result.get("total_enriched", 0))
    logger.info("  Filtered out    : %d", result.get("filtered", 0))
    logger.info("  Pass1 scored    : %d", result.get("pass1_count", 0))
    logger.info("  Pass2 cards     : %d", result.get("pass2_count", 0))
    logger.info("  GS distribution : %s", result.get("gs_distribution", {}))
    logger.info("  LLM calls       : %d", result.get("llm_calls", 0))
    logger.info("=" * 70)

    # ---- Per-article detail ----
    articles = result.get("articles", [])
    for i, a in enumerate(articles, 1):
        title = a.get("title", "???")
        content = a.get("content", "")
        summary = a.get("summary", "")
        has_key_term = '<span class="key-term"' in content if content else False
        content_len = len(content) if content else 0
        logger.info(
            "[%d/%d] %s  | content=%d chars | key-terms=%s | summary=%d chars | gs=%s | relevance=%s | triage=%s",
            i,
            len(articles),
            title[:80],
            content_len,
            has_key_term,
            len(summary) if summary else 0,
            a.get("gs_paper", "?"),
            a.get("upsc_relevance", "?"),
            a.get("priority_triage", "?"),
        )

    # ---- Spot-check: print first article's content snippet ----
    if articles:
        first = articles[0]
        logger.info("=" * 70)
        logger.info("SAMPLE ARTICLE — Title: %s", first.get("title", "???"))
        logger.info(
            "Content (first 500 chars):\n%s", (first.get("content", "") or "")[:500]
        )
        logger.info("Summary: %s", (first.get("summary", "") or "")[:300])
        logger.info("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
