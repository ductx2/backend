import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.optimized_rss_processor import OptimizedRSSProcessor
from app.services.ie_scraper import IndianExpressScraper
from app.services.pib_scraper import PIBScraper
from app.services.supplementary_sources import SupplementarySources
from app.services.playwright_session import PlaywrightSessionManager
from app.services.hindu_playwright_scraper import HinduPlaywrightScraper
from app.services.ie_playwright_scraper import IEPlaywrightScraper
from app.services.mea_scraper import MEAScraper
from app.services.orf_scraper import ORFScraper
from app.services.idsa_scraper import IDSAScraper
from app.services.content_extractor import UniversalContentExtractor
from app.services.knowledge_card_pipeline import KnowledgeCardPipeline
from app.services.article_selector import ArticleSelector
from app.core.database import SupabaseConnection

logger = logging.getLogger(__name__)

# Pipeline configuration
# NOTE: RELEVANCE_THRESHOLD = 55 lives in KnowledgeCardPipeline (knowledge_card_pipeline.py)
_MAX_ARTICLES_DEFAULT = 30


_HINDU_SOURCE_TO_SECTION: dict[str, str] = {
    "editorial": "editorial",
    "op-ed": "opinion",
    "opinion": "opinion",
    "national": "national",
    "international": "international",
    "business": "business",
    "science": "science",
}


def _derive_section(source_name: str) -> str:
    lower = source_name.lower()
    for keyword, section in _HINDU_SOURCE_TO_SECTION.items():
        if keyword in lower:
            return section
    return "general"


def _normalize_hindu_article(article: dict[str, Any]) -> dict[str, Any]:
    article["url"] = article.get("source_url", "")
    article["source_site"] = "hindu"
    article["section"] = _derive_section(article.get("source", ""))
    return article




def _normalize_httpx_article(article: dict[str, Any]) -> dict[str, Any]:
    """Normalize httpx scraper output: copy source_url -> url for dedup."""
    if "url" not in article and "source_url" in article:
        article["url"] = article["source_url"]
    return article


def _deduplicate(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for article in articles:
        url_key = article.get("url", "").lower()
        if not url_key:
            logger.warning(
                "Skipping article with no URL: '%s'",
                article.get("title", "unknown"),
            )
            continue
        if url_key in seen:
            continue
        seen.add(url_key)
        unique.append(article)
    return unique




def _filter_by_date(articles: list[dict[str, Any]], max_age_hours: int = 36) -> list[dict[str, Any]]:
    """Remove articles older than max_age_hours. Articles with no date are kept (with warning)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    filtered = []
    for article in articles:
        pub_date = article.get("published_date") or article.get("published_at")
        if not pub_date:
            logger.warning("Article has no date, keeping with today's date: '%s'", article.get('title', 'unknown'))
            article['published_date'] = datetime.now(timezone.utc).isoformat()
            filtered.append(article)
            continue
        try:
            if isinstance(pub_date, str):
                parsed = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
            elif isinstance(pub_date, datetime):
                parsed = pub_date if pub_date.tzinfo else pub_date.replace(tzinfo=timezone.utc)
            else:
                filtered.append(article)
                continue
            if parsed >= cutoff:
                filtered.append(article)
            else:
                logger.debug("Date-filtered: '%s' (published %s)", article.get('title', 'unknown'), pub_date)
        except (ValueError, TypeError):
            filtered.append(article)  # Keep on parse error
    return filtered

def _parse_date(published_date: Any) -> str:
    """Parse published_date to YYYY-MM-DD string; fallback to today."""
    if not published_date:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if isinstance(published_date, datetime):
        return published_date.strftime("%Y-%m-%d")
    s = str(published_date).strip()
    # Already YYYY-MM-DD
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    # Try ISO parse
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _triage_to_importance(triage: str) -> str:
    """Map priority_triage to importance: must_know->high, should_know->medium, else->low."""
    mapping = {"must_know": "high", "should_know": "medium", "good_to_know": "low"}
    return mapping.get(triage, "low")


def _to_iso_str(value: Any) -> str:
    """Convert a datetime object or ISO string to an ISO string; fallback to empty string."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return ""

def prepare_knowledge_card_for_database(article: dict[str, Any]) -> dict[str, Any]:
    """Map enriched article dict to DB row with all 5-layer fields populated."""
    syllabus_matches = article.get("syllabus_matches") or []
    syllabus_topic = syllabus_matches[0].get("sub_topic", "") if syllabus_matches else ""

    return {
        # Core fields
        "title": article.get("title", ""),
        "content": article.get("content", ""),
        "source_url": article.get("url", ""),
        "source_site": article.get("source_site", ""),
        "published_at": _to_iso_str(article.get("published_date")) or datetime.now(timezone.utc).isoformat(),
        "date": _parse_date(article.get("published_date")),
        "status": "published",
        # Analysis fields
        "upsc_relevance": article.get("upsc_relevance", 0),
        "gs_paper": article.get("gs_paper", ""),
        "tags": article.get("keywords") or [],
        "category": (article.get("gs_paper") or "general").lower(),
        "importance": _triage_to_importance(article.get("priority_triage", "good_to_know")),
        # 5-layer knowledge card fields
        "headline_layer": article.get("headline_layer", ""),
        "facts_layer": article.get("facts_layer") or [],
        "context_layer": article.get("context_layer", ""),
        "connections_layer": article.get("connections_layer") or {},
        "mains_angle_layer": article.get("mains_angle_layer", ""),
        "practice_questions_layer": article.get("practice_questions_layer") or [],
        "priority_triage": article.get("priority_triage", "good_to_know"),
        "syllabus_topic": syllabus_topic,
        # Deduplication
        "content_hash": hashlib.md5(article.get("content", "").encode()).hexdigest(),
    }


class UnifiedPipeline:
    async def fetch_all_sources(self) -> list[dict[str, Any]]:
        all_articles: list[dict[str, Any]] = []

        async def _fetch_hindu() -> list[dict[str, Any]]:
            processor = OptimizedRSSProcessor()
            raw = await processor.fetch_all_sources_parallel()
            return [_normalize_hindu_article(a) for a in raw]

        async def _fetch_ie() -> list[dict[str, Any]]:
            scraper = IndianExpressScraper()
            return await scraper.scrape_all_sections()

        async def _fetch_pib() -> list[dict[str, Any]]:
            scraper = PIBScraper()
            return await scraper.scrape_releases()

        async def _fetch_supplementary() -> list[dict[str, Any]]:
            sources = SupplementarySources()
            return await asyncio.to_thread(sources.fetch_all)

        async def _fetch_hindu_playwright() -> list[dict[str, Any]]:
            session = PlaywrightSessionManager()
            scraper = HinduPlaywrightScraper(session)
            try:
                return await scraper.scrape_editorials()
            finally:
                await session.close()

        async def _fetch_ie_playwright() -> list[dict[str, Any]]:
            session = PlaywrightSessionManager()
            scraper = IEPlaywrightScraper(session)
            try:
                return await scraper.scrape_editorials()
            finally:
                await session.close()

        async def _fetch_mea() -> list[dict[str, Any]]:
            scraper = MEAScraper()
            articles = await scraper.fetch_articles()
            return [_normalize_httpx_article(a) for a in articles]

        async def _fetch_orf() -> list[dict[str, Any]]:
            scraper = ORFScraper()
            articles = await scraper.fetch_articles()
            return [_normalize_httpx_article(a) for a in articles]

        async def _fetch_idsa() -> list[dict[str, Any]]:
            scraper = IDSAScraper()
            articles = await scraper.fetch_articles()
            return [_normalize_httpx_article(a) for a in articles]

        tasks = {
            "hindu": _fetch_hindu(),
            "ie": _fetch_ie(),
            "pib": _fetch_pib(),
            "supplementary": _fetch_supplementary(),
            "hindu_playwright": _fetch_hindu_playwright(),
            "ie_playwright": _fetch_ie_playwright(),
            "mea": _fetch_mea(),
            "orf": _fetch_orf(),
            "idsa": _fetch_idsa(),
        }

        results = await asyncio.gather(*tasks.values(), return_exceptions=True)

        for source_name, result in zip(tasks.keys(), results):
            if isinstance(result, Exception):
                logger.error("Source '%s' failed: %s", source_name, result)
                continue
            count = len(result) if isinstance(result, list) else 0
            logger.info("Source '%s' returned %d articles", source_name, count)
            if isinstance(result, list):
                all_articles.extend(result)

        deduped = _deduplicate(all_articles)
        logger.info(
            "Total articles: %d raw → %d after dedup",
            len(all_articles),
            len(deduped),
        )
        return deduped

    async def enrich_articles(
        self, articles: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        # DEPRECATED: Used by tests only. New flow uses run() directly.
        if not articles:
            return []

        pipeline = KnowledgeCardPipeline()
        enriched: list[dict[str, Any]] = []

        for article in articles:
            try:
                result = await pipeline.process_article(article)
                if result is not None:
                    enriched.append(result)
            except Exception as e:
                logger.error(
                    "process_article failed for '%s': %s",
                    article.get("title", "unknown"),
                    e,
                )

        return enriched

    async def save_articles(
        self,
        articles: list[dict[str, Any]],
        db: SupabaseConnection,
    ) -> dict[str, Any]:
        """Save enriched articles to DB via upsert. Never raises; accumulates counts."""
        saved = 0
        skipped = 0
        errors = 0

        for article in articles:
            title = article.get("title", "unknown")
            triage = article.get("priority_triage", "unknown")
            try:
                db_row = prepare_knowledge_card_for_database(article)
                result = await db.upsert_current_affair(db_row, match_field="source_url")
                if result.get("success"):
                    saved += 1
                    logger.info("Saved: '%s' [%s]", title, triage)
                else:
                    errors += 1
                    logger.error(
                        "Failed to save '%s': %s", title, result.get("error", "unknown")
                    )
            except Exception as e:
                errors += 1
                logger.error("Failed to save '%s': %s", title, e)

        return {"saved": saved, "skipped": skipped, "errors": errors}

    async def run(self, max_articles: int = 30, save_to_db: bool = False) -> dict[str, Any]:
        # Step 1: Fetch all sources (existing — already includes URL dedup)
        raw_articles = await self.fetch_all_sources()
        # Step 2: Date filter (NEW — remove articles > 36h old)
        date_filtered = _filter_by_date(raw_articles)
        logger.info("Date filter: %d → %d articles", len(raw_articles), len(date_filtered))

        # Step 2b: Filter UPSC prep/coaching articles (not real current affairs)
        import re as _re
        _prep_pattern = _re.compile(
            r'(?i)UPSC\s+(Key|Essentials|Weekly|Prelims\s*Ready|Quiz|Simplified)'
        )
        date_filtered = [
            a for a in date_filtered
            if not _prep_pattern.search(a.get('title', ''))
        ]
        logger.info("Prep-article filter: kept %d articles", len(date_filtered))

        # Step 3: Content extraction (on ALL date-filtered articles, no blind cap)
        extractor = UniversalContentExtractor()
        articles_with_content: list[dict[str, Any]] = []
        for article in date_filtered:
            if article.get('content'):
                articles_with_content.append(article)
                continue
            url = article.get('url', '')
            if not url:
                logger.warning("Skipping article without URL or content: '%s'", article.get('title', 'unknown'))
                continue
            try:
                extracted = await extractor.extract_content(url)
                if extracted is None or not extracted.content:
                    logger.warning("Content extraction returned empty for '%s'", article.get('title', 'unknown'))
                    continue
                article['content'] = extracted.content
                articles_with_content.append(article)
            except Exception as e:
                logger.error("Content extraction failed for '%s': %s", article.get('title', 'unknown'), e)

        # Step 4: Batch scoring via run_pass1_batch() (NEW)
        pipeline = KnowledgeCardPipeline()
        pass1_results = await pipeline.run_pass1_batch(articles_with_content)

        # Merge pass1 results back into article dicts (keyed by URL)
        scored_articles: list[dict[str, Any]] = []
        for article in articles_with_content:
            url = article.get('url', article.get('source_url', ''))
            pass1 = pass1_results.get(url)
            if pass1 is None:
                logger.warning('[Pipeline] No pass1 result for article: %s', article.get('title', 'unknown'))
                continue
            merged = {**article}
            merged.update({
                'upsc_relevance': pass1['upsc_relevance'],
                'gs_paper': pass1['gs_paper'],
                'key_facts': pass1['key_facts'],
                'keywords': pass1['keywords'],
                'syllabus_matches': pass1['syllabus_matches'],
                'raw_pass1_data': pass1['raw_pass1_data'],
            })
            scored_articles.append(merged)
        if len(scored_articles) < len(articles_with_content):
            lost = len(articles_with_content) - len(scored_articles)
            logger.warning(
                '[Pipeline] %d articles lost during pass1 scoring (%d in, %d out)',
                lost, len(articles_with_content), len(scored_articles)
            )

        # Step 5: Relevance threshold filter + MUST_KNOW bypass
        threshold = pipeline.relevance_threshold  # 55 from config
        above_threshold: list[dict[str, Any]] = []
        for article in scored_articles:
            relevance = article.get('upsc_relevance', 0)
            if pipeline._is_must_know(article):
                logger.info("MUST_KNOW source bypasses threshold: '%s'", article.get('title', ''))
                above_threshold.append(article)
            elif relevance >= threshold:
                above_threshold.append(article)
            else:
                logger.debug("Filtered (relevance=%d < %d): '%s'", relevance, threshold, article.get('title', ''))
        logger.info("Threshold filter (%d): %d → %d articles", threshold, len(scored_articles), len(above_threshold))

        # Step 6: Article selection (semantic dedup + GS-balance + tournament) (NEW)
        selector = ArticleSelector()
        selected = await selector.select_top_articles(above_threshold, target=max_articles)
        logger.info("Selected %d articles for Pass 2", len(selected))

        # Step 7: Pass 2 knowledge card generation on final selected articles ONLY
        enriched: list[dict[str, Any]] = []
        for article in selected:
            try:
                pass1_data = {
                    'upsc_relevance': article['upsc_relevance'],
                    'gs_paper': article['gs_paper'],
                    'key_facts': article['key_facts'],
                    'keywords': article['keywords'],
                    'syllabus_matches': article['syllabus_matches'],
                    'raw_pass1_data': article['raw_pass1_data'],
                }
                pass2 = await pipeline.run_pass2(article, pass1_data)
                triage = pipeline._compute_triage(pass1_data, article)
                result = {**article}
                result.update({
                    'priority_triage': triage,
                    'headline_layer': pass2['headline_layer'],
                    'facts_layer': pass2['facts_layer'],
                    'context_layer': pass2['context_layer'],
                    'connections_layer': pass2['connections_layer'],
                    'mains_angle_layer': pass2['mains_angle_layer'],
                    'practice_questions_layer': pass2['practice_questions_layer'],
                })
                enriched.append(result)
            except Exception as e:
                logger.error("Pass 2 failed for '%s': %s", article.get('title', 'unknown'), e)

        # Step 8: Build result dict with new metrics
        gs_distribution: dict[str, int] = {}
        for article in enriched:
            gs = article.get('gs_paper', 'unknown')
            gs_distribution[gs] = gs_distribution.get(gs, 0) + 1
        logger.info("GS distribution: %s", gs_distribution)

        llm_calls = (len(articles_with_content) // 10 + (1 if len(articles_with_content) % 10 else 0)) * 2 + 1 + len(enriched)
        result = {
            'articles': enriched,
            'total_fetched': len(raw_articles),
            'total_enriched': len(enriched),
            'filtered': len(raw_articles) - len(enriched),
            'pass1_count': len(pass1_results),
            'pass2_count': len(enriched),
            'gs_distribution': gs_distribution,
            'llm_calls': llm_calls,
        }
        logger.info(
            'Pipeline complete: fetched=%d date_filtered=%d scored=%d threshold_passed=%d selected=%d enriched=%d llm_calls=%d',
            len(raw_articles), len(date_filtered), len(scored_articles), len(above_threshold), len(selected), len(enriched), llm_calls,
        )
        if save_to_db and enriched:
            db = SupabaseConnection()
            db_save = await self.save_articles(enriched, db)
            result['db_save'] = db_save
        return result
