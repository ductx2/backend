"""
Simplified 5-Step RSS Processing Flow API
Clean, linear pipeline for RSS to database processing

This replaces the 52 redundant endpoints with a clear 5-step flow:
1. Extract RSS feeds
2. AI analysis for UPSC relevance
3. Extract full content from selected articles
4. AI refinement and enhancement
5. Save processed articles to database

Compatible with: FastAPI 0.116.1, Python 3.13.5
Created: 2025-08-31
"""

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks, Body
from typing import Dict, Any, List, Optional
import asyncio
import logging
import time
from datetime import datetime
from pydantic import BaseModel

# Local imports
from ..core.security import require_authentication, require_admin_access
from ..core.database import get_database, SupabaseConnection
from ..services.optimized_rss_processor import OptimizedRSSProcessor
from ..services.centralized_llm_service import llm_service
from ..services.content_extractor import UniversalContentExtractor
from ..models.llm_schemas import LLMRequest, TaskType, ProviderPreference

# Initialize router and logger
router = APIRouter(prefix="/api/flow", tags=["Simplified Flow"])
logger = logging.getLogger(__name__)


# Request models
class AnalysisRequest(BaseModel):
    articles: List[Dict[str, Any]]
    min_relevance_score: int = 40


class ExtractionRequest(BaseModel):
    # Allow rich objects coming from Step 2 (they may include nested fields like 'raw_entry')
    selected_articles: List[
        Dict[str, Any]
    ]  # expects at least 'title' and one of 'url'/'source_url'/'link'


class RefinementRequest(BaseModel):
    articles: List[Dict[str, Any]]


class SaveRequest(BaseModel):
    processed_articles: List[Dict[str, Any]]


# Step 1: RSS Extraction
@router.post("/step1/extract-rss", response_model=Dict[str, Any])
async def step1_extract_rss(user: dict = Depends(require_authentication)):
    """
    STEP 1: Extract raw articles from all 6 RSS sources

    Clean, parallel extraction without any AI processing.
    Returns raw RSS articles for next step.
    """
    try:
        logger.info("Step 1: Starting RSS extraction")
        start_time = time.time()

        processor = OptimizedRSSProcessor()
        raw_articles = await processor.fetch_all_sources_parallel()

        extraction_time = time.time() - start_time

        return {
            "success": True,
            "step": "1_rss_extraction",
            "message": f"Extracted {len(raw_articles)} raw articles from 6 RSS sources",
            "data": {
                "articles": raw_articles,
                "total_articles": len(raw_articles),
                "sources_processed": 6,
                "extraction_time": extraction_time,
            },
            "next_step": "POST /api/flow/step2/analyze-relevance",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Step 1 failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RSS extraction failed: {str(e)}",
        )


# Step 2: AI Analysis
@router.post("/step2/analyze-relevance", response_model=Dict[str, Any])
async def step2_analyze_relevance(
    request: AnalysisRequest, user: dict = Depends(require_authentication)
):
    """
    STEP 2: Analyze articles for UPSC relevance

    Processes articles through centralized LLM service to determine
    UPSC relevance scores and filter out irrelevant content.
    """
    try:
        logger.info(
            f"Step 2: Analyzing {len(request.articles)} articles for UPSC relevance"
        )
        start_time = time.time()

        relevant_articles = []

        for article in request.articles:
            # Create LLM request for UPSC analysis
            llm_request = LLMRequest(
                task_type=TaskType.UPSC_ANALYSIS,
                content=f"Title: {article.get('title', '')}\nContent: {article.get('content', '')}",
                provider_preference=ProviderPreference.COST_OPTIMIZED,
                temperature=0.1,
                max_tokens=500,
            )

            # Process through centralized LLM service
            llm_response = await llm_service.process_request(llm_request)

            if llm_response.success and llm_response.data:
                relevance_score = llm_response.data.get("upsc_relevance", 0)
                model_used = llm_response.model_used
                ai_analysis = llm_response.data
            else:
                # Skip article if LLM service fails
                logger.warning(
                    f"❌ LLM service failed for article: {article.get('title', 'Unknown')[:50]}"
                )
                logger.warning(f"   Error: {llm_response.error_message}")
                continue

            if relevance_score >= request.min_relevance_score:
                # Add AI analysis data to article
                enhanced_article = {**article}
                enhanced_article.update(
                    {
                        "upsc_relevance": relevance_score,
                        "ai_analysis": ai_analysis,
                        "model_used": model_used,
                    }
                )
                relevant_articles.append(enhanced_article)

        analysis_time = time.time() - start_time

        return {
            "success": True,
            "step": "2_ai_analysis",
            "message": f"Found {len(relevant_articles)} UPSC-relevant articles (>{request.min_relevance_score} score)",
            "data": {
                "relevant_articles": relevant_articles,
                "total_analyzed": len(request.articles),
                "total_relevant": len(relevant_articles),
                "min_relevance_score": request.min_relevance_score,
                "analysis_time": analysis_time,
            },
            "next_step": "POST /api/flow/step3/extract-content",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Step 2 failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"UPSC analysis failed: {str(e)}",
        )


# Step 3: Content Extraction
@router.post("/step3/extract-content", response_model=Dict[str, Any])
async def step3_extract_content(
    request: Dict[str, Any] = Body(...), user: dict = Depends(require_authentication)
):
    """
    STEP 3: Extract full content from selected article URLs

    Uses universal content extractor to get complete article content
    from the original source URLs.
    """
    try:
        selected_articles = request.get("selected_articles", []) or []
        logger.info(
            f"Step 3: Extracting full content from {len(selected_articles)} articles"
        )
        start_time = time.time()

        extractor = UniversalContentExtractor()
        extracted_articles = []

        for article_info in selected_articles:
            # Be robust to different keys coming from Step 2 or external sources
            url = (
                article_info.get("url")
                or article_info.get("source_url")
                or article_info.get("link")
            )
            title = (
                article_info.get("title", "")
                or article_info.get("original_title", "")
                or article_info.get("headline", "")
            )

            if url:
                try:
                    # Extract full content using universal extractor
                    extracted_content = await extractor.extract_content(url)

                    if extracted_content:
                        extracted_articles.append(
                            {
                                "original_title": title,
                                "url": url,
                                "extracted_content": extracted_content.to_dict(),
                            }
                        )

                except Exception as e:
                    logger.warning(f"Failed to extract content from {url}: {e}")

        extraction_time = time.time() - start_time

        return {
            "success": True,
            "step": "3_content_extraction",
            "message": f"Successfully extracted full content from {len(extracted_articles)} articles",
            "data": {
                "extracted_articles": extracted_articles,
                "total_requested": len(selected_articles),
                "total_extracted": len(extracted_articles),
                "extraction_time": extraction_time,
                "success_rate": (len(extracted_articles) / len(selected_articles) * 100)
                if selected_articles
                else 0,
            },
            "next_step": "POST /api/flow/step4/refine-content",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Step 3 failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Content extraction failed: {str(e)}",
        )


# Step 4: AI Refinement
@router.post("/step4/refine-content", response_model=Dict[str, Any])
async def step4_refine_content(
    request: RefinementRequest, user: dict = Depends(require_authentication)
):
    """
    STEP 4: AI refinement and enhancement of extracted content

    Processes extracted content through AI to create refined summaries,
    key points, and UPSC-focused enhancements.
    """
    try:
        logger.info(f"Step 4: Refining content for {len(request.articles)} articles")
        start_time = time.time()

        refined_articles = []

        for article in request.articles:
            content = article.get("extracted_content", {}).get("content", "")

            if content:
                # Create LLM request for content refinement
                llm_request = LLMRequest(
                    task_type=TaskType.SUMMARIZATION,
                    content=content,
                    provider_preference=ProviderPreference.QUALITY_OPTIMIZED,
                    temperature=0.2,
                    max_tokens=800,
                    custom_instructions="Create UPSC-focused summary with key points and exam relevance",
                )

                # Process through centralized LLM service
                llm_response = await llm_service.process_request(llm_request)

                if llm_response.success and llm_response.data:
                    ai_refinement = llm_response.data
                    refinement_model = llm_response.model_used
                    processing_time = llm_response.response_time
                else:
                    # Skip article if LLM service fails
                    logger.warning(f"❌ LLM service failed for content refinement")
                    logger.warning(f"   Error: {llm_response.error_message}")
                    continue

                refined_article = {
                    **article,
                    "ai_refinement": ai_refinement,
                    "refinement_model": refinement_model,
                    "processing_time": processing_time,
                }
                refined_articles.append(refined_article)

        refinement_time = time.time() - start_time

        return {
            "success": True,
            "step": "4_ai_refinement",
            "message": f"Successfully refined {len(refined_articles)} articles",
            "data": {
                "refined_articles": refined_articles,
                "total_processed": len(request.articles),
                "total_refined": len(refined_articles),
                "refinement_time": refinement_time,
            },
            "next_step": "POST /api/flow/step5/save-to-database",
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Step 4 failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Content refinement failed: {str(e)}",
        )


# Step 5: Database Save
@router.post("/step5/save-to-database", response_model=Dict[str, Any])
async def step5_save_to_database(
    request: SaveRequest,
    user: dict = Depends(require_authentication),
    db: SupabaseConnection = Depends(get_database),
):
    """
    STEP 5: Save processed articles to database

    Final step - saves all processed and refined articles to the
    current_affairs table with proper deduplication.
    """
    try:
        logger.info(
            f"Step 5: Saving {len(request.processed_articles)} articles to database"
        )
        start_time = time.time()

        saved_articles = []
        duplicate_count = 0

        for article in request.processed_articles:
            try:
                # Prepare article for database insertion
                db_article = prepare_article_for_database(article)

                # Check for duplicates using content hash
                content_hash = db_article.get("content_hash")
                if content_hash:
                    existing = (
                        db.client.table("current_affairs")
                        .select("id")
                        .eq("content_hash", content_hash)
                        .execute()
                    )

                    if existing.data:
                        duplicate_count += 1
                        continue

                # Insert into database
                result = db.client.table("current_affairs").insert(db_article).execute()

                if result.data:
                    saved_articles.append(result.data[0])

            except Exception as e:
                logger.warning(f"Failed to save article: {e}")

        save_time = time.time() - start_time

        return {
            "success": True,
            "step": "5_database_save",
            "message": f"Successfully saved {len(saved_articles)} articles to database",
            "data": {
                "saved_articles": len(saved_articles),
                "total_processed": len(request.processed_articles),
                "duplicates_skipped": duplicate_count,
                "save_time": save_time,
            },
            "pipeline_complete": True,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Step 5 failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database save failed: {str(e)}",
        )


# Complete pipeline endpoint
@router.post("/complete-pipeline", response_model=Dict[str, Any])
async def complete_pipeline(
    background_tasks: BackgroundTasks, user: dict = Depends(require_admin_access)
):
    """
    COMPLETE PIPELINE: Execute all 5 steps in sequence

    Admin-only endpoint that runs the entire pipeline from RSS extraction
    to database storage in one operation.
    """
    try:
        logger.info("Starting complete 5-step pipeline")
        pipeline_start = time.time()

        # Step 1: Extract RSS
        step1_response = await step1_extract_rss(user)
        articles = step1_response["data"]["articles"]

        # Step 2: Analyze relevance
        analysis_request = AnalysisRequest(articles=articles)
        step2_response = await step2_analyze_relevance(analysis_request, user)
        relevant_articles = step2_response["data"]["relevant_articles"]

        # Step 3: Extract content (from top 20 relevant articles)
        top_articles = relevant_articles[:20]  # Limit for performance
        extraction_request_data = {
            "selected_articles": [
                {"title": a["title"], "url": a["source_url"]} for a in top_articles
            ]
        }
        step3_response = await step3_extract_content(extraction_request_data, user)
        extracted_articles = step3_response["data"]["extracted_articles"]

        # Step 4: Refine content
        refinement_request = RefinementRequest(articles=extracted_articles)
        step4_response = await step4_refine_content(refinement_request, user)
        refined_articles = step4_response["data"]["refined_articles"]

        # Step 5: Save to database
        save_request = SaveRequest(processed_articles=refined_articles)
        db = await get_database()
        step5_response = await step5_save_to_database(save_request, user, db)

        total_time = time.time() - pipeline_start

        return {
            "success": True,
            "message": "Complete 5-step pipeline executed successfully",
            "pipeline_results": {
                "step1_rss_extraction": step1_response["data"],
                "step2_ai_analysis": step2_response["data"],
                "step3_content_extraction": step3_response["data"],
                "step4_ai_refinement": step4_response["data"],
                "step5_database_save": step5_response["data"],
            },
            "total_pipeline_time": total_time,
            "final_articles_saved": step5_response["data"]["saved_articles"],
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Complete pipeline failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline execution failed: {str(e)}",
        )


def map_to_proper_category(ai_category: str) -> str:
    """Map AI-generated categories to proper database categories"""
    ai_category = ai_category.lower().strip()

    category_mapping = {
        "politics": "politics",
        "political": "politics",
        "governance": "politics",
        "government": "politics",
        "parliament": "politics",
        "minister": "politics",
        "election": "politics",
        "economy": "economy",
        "economic": "economy",
        "finance": "economy",
        "financial": "economy",
        "trade": "economy",
        "budget": "economy",
        "gdp": "economy",
        "inflation": "economy",
        "market": "economy",
        "international": "international",
        "foreign": "international",
        "bilateral": "international",
        "china": "international",
        "usa": "international",
        "pakistan": "international",
        "science": "science",
        "technology": "science",
        "tech": "science",
        "digital": "science",
        "innovation": "science",
        "cyber": "science",
        "environment": "environment",
        "environmental": "environment",
        "climate": "environment",
        "green": "environment",
        "pollution": "environment",
        "renewable": "environment",
        "society": "society",
        "social": "society",
        "culture": "culture",
        "cultural": "culture",
        "education": "society",
        "health": "society",
        "women": "society",
        "defence": "defence",
        "defense": "defence",
        "security": "defence",
        "military": "defence",
        "army": "defence",
        "border": "defence",
        "schemes": "schemes",
        "scheme": "schemes",
        "welfare": "schemes",
        "yojana": "schemes",
    }

    # Check for exact matches first
    if ai_category in category_mapping:
        return category_mapping[ai_category]

    # Check for partial matches
    for key, category in category_mapping.items():
        if key in ai_category:
            return category

    # Default fallback
    return "politics"  # Use politics as default instead of general


def prepare_article_for_database(article: Dict[str, Any]) -> Dict[str, Any]:
    """Prepare article data for database insertion"""
    import hashlib

    extracted_content = article.get("extracted_content", {})
    ai_refinement = article.get("ai_refinement", {})
    ai_analysis = article.get("ai_analysis", {})

    # Create content hash for deduplication
    content_text = extracted_content.get("content", "")
    content_hash = hashlib.md5(content_text.encode()).hexdigest()

    # Extract and process date field
    published_date = extracted_content.get(
        "publish_date", datetime.utcnow().isoformat()
    )
    try:
        if isinstance(published_date, str):
            # Handle different ISO formats
            if published_date.endswith("Z"):
                date_obj = datetime.fromisoformat(published_date.replace("Z", "+00:00"))
            else:
                date_obj = datetime.fromisoformat(published_date)
        else:
            date_obj = published_date

        date_field = date_obj.date().isoformat()
    except (ValueError, AttributeError):
        # Fallback to current date if parsing fails
        date_field = datetime.utcnow().date().isoformat()

    return {
        "title": (
            ai_refinement.get("generated_title")  # AI-generated title (priority 1)
            or ai_refinement.get("enhanced_title")  # Alternative AI title field
            or extracted_content.get("title", "")  # Fallback to extracted
            or article.get("original_title", "")  # RSS title fallback
            or "Current Affairs Update"  # Final fallback
        ),
        "content": ai_refinement.get("enhanced_content", content_text)
        if ai_refinement.get("enhanced_content")
        else content_text,
        "summary": ai_refinement.get("brief_summary", ""),
        "source": extracted_content.get("author", "RSS Feed"),
        "source_url": article.get("url", ""),
        "published_at": extracted_content.get(
            "publish_date", datetime.utcnow().isoformat()
        ),
        "date": date_field,  # Add required date field
        "upsc_relevance": ai_analysis.get("upsc_relevance", 50),
        "category": map_to_proper_category(
            ai_analysis.get("key_topics", ["general"])[0]
            if ai_analysis.get("key_topics")
            else "general"
        ),
        "tags": ai_analysis.get("key_topics", []),
        "importance": ai_analysis.get("importance_level", "medium").lower(),
        "gs_paper": ", ".join(ai_analysis.get("relevant_papers", [])) or None,
        "ai_summary": ai_refinement.get("detailed_summary", ""),
        "content_hash": content_hash,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
