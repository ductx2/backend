"""
Linear Flow API Endpoints (6-step pipeline)

Exposes simple, individual steps plus a complete pipeline:
- POST /api/flow/step1/extract-rss
- POST /api/flow/step2/analyze-relevance
- POST /api/flow/step3/extract-content
- POST /api/flow/step4/refine-content
- POST /api/flow/step5/save-to-database
- POST /api/flow/complete-pipeline
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List, Optional
import logging

from ..core.security import require_authentication, require_admin_access
from ..core.config import get_settings
from ..core.database import get_database, SupabaseConnection
from ..services.optimized_rss_processor import OptimizedRSSProcessor, ProcessedArticle
from ..services.direct_gemini_fallback import direct_gemini_service
from ..services.groq_llm_service import GroqLLMService


router = APIRouter(prefix="/api/flow", tags=["Simplified Flow"])
logger = logging.getLogger(__name__)

_rss_processor: Optional[OptimizedRSSProcessor] = None
_groq_service: Optional[GroqLLMService] = None


def get_rss_processor() -> OptimizedRSSProcessor:
    global _rss_processor
    if _rss_processor is None:
        _rss_processor = OptimizedRSSProcessor()
    return _rss_processor


def get_groq_service() -> Optional[GroqLLMService]:
    global _groq_service
    if _groq_service is None:
        try:
            settings = get_settings()
            if settings.groq_api_key:
                _groq_service = GroqLLMService()
        except Exception as e:
            logger.warning(f"Groq service unavailable: {e}")
            _groq_service = None
    return _groq_service


@router.post("/step1/extract-rss", response_model=Dict[str, Any])
async def step1_extract_rss(
    user: dict = Depends(require_authentication),
    rss_processor: OptimizedRSSProcessor = Depends(get_rss_processor)
):
    try:
        raw_articles = await rss_processor.fetch_all_sources_parallel()
        return {
            "success": True,
            "step": 1,
            "message": f"Fetched {len(raw_articles)} raw RSS articles",
            "data": {"raw_articles": raw_articles[:100]},
        }
    except Exception as e:
        logger.error(f"Step1 extract RSS failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/step2/analyze-relevance", response_model=Dict[str, Any])
async def step2_analyze_relevance(
    payload: Dict[str, Any],
    user: dict = Depends(require_authentication),
    rss_processor: OptimizedRSSProcessor = Depends(get_rss_processor)
):
    try:
        raw_articles = payload.get("raw_articles", [])
        processed = await rss_processor.process_articles_with_single_ai_pass(raw_articles)
        # Serialize minimal fields for transport
        processed_serialized = [
            {
                "title": a.title,
                "content": a.content,
                "summary": a.summary,
                "source": a.source,
                "source_url": a.source_url,
                "factual_score": a.factual_score,
                "analytical_score": a.analytical_score,
                "upsc_relevance": a.upsc_relevance,
                "category": a.category,
                "tags": a.tags,
            }
            for a in processed
        ]
        return {"success": True, "step": 2, "message": f"Analyzed {len(processed)} articles", "data": {"processed_articles": processed_serialized}}
    except Exception as e:
        logger.error(f"Step2 analyze relevance failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/step3/extract-content", response_model=Dict[str, Any])
async def step3_extract_content(
    payload: Dict[str, Any],
    user: dict = Depends(require_authentication),
    rss_processor: OptimizedRSSProcessor = Depends(get_rss_processor)
):
    try:
        raw_or_processed = payload.get("articles", [])
        enriched = await rss_processor.extract_full_content_from_articles(raw_or_processed)
        return {"success": True, "step": 3, "message": f"Extracted full content for {len(enriched)} articles", "data": {"enriched_articles": enriched}}
    except Exception as e:
        logger.error(f"Step3 extract content failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/step4/refine-content", response_model=Dict[str, Any])
async def step4_refine_content(
    payload: Dict[str, Any],
    user: dict = Depends(require_authentication),
    groq: Optional[GroqLLMService] = Depends(get_groq_service)
):
    try:
        articles = payload.get("articles", [])
        refined: List[Dict[str, Any]] = []
        for article in articles:
            content = article.get("content") or article.get("summary") or ""
            if groq is not None:
                # Use Groq for enhanced structured refinement
                analysis = await groq.enhanced_upsc_analysis(content, article.get("category", "current_affairs"))
                refined.append({
                    **article, 
                    "groq_analysis": analysis,
                    "content": content,  # Keep original extracted content
                    "summary": analysis.get("summary", ""),  # AI-generated summary
                    "title": article.get("title", "")  # Keep original title for now
                })
            else:
                # Fallback to direct Gemini refinement
                result = await direct_gemini_service.refine_content(content)
                refined.append({
                    **article,
                    "refinement": result,
                    "content": content,  # Keep original extracted content
                    "summary": result.get("summary", result.get("detailed_summary", "")[:200]),  # Use summary from refinement
                    "title": result.get("generated_title", article.get("title", ""))  # Use refined title
                })
        return {"success": True, "step": 4, "message": f"Refined {len(refined)} articles", "data": {"refined_articles": refined}}
    except Exception as e:
        logger.error(f"Step4 refine content failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/step5/save-to-database", response_model=Dict[str, Any])
async def step5_save_to_database(
    payload: Dict[str, Any],
    user: dict = Depends(require_authentication),
    db: SupabaseConnection = Depends(get_database),
    rss_processor: OptimizedRSSProcessor = Depends(get_rss_processor)
):
    try:
        # Accept either refined or processed articles
        incoming = payload.get("articles", [])
        # Map incoming dicts to ProcessedArticle for save pipeline when possible
        processed_objs: List[ProcessedArticle] = []
        for a in incoming:
            # Extract Groq analysis data if present
            groq_data = a.get("groq_analysis", {})
            
            processed_objs.append(ProcessedArticle(**{
                "title": a.get("title", ""),
                "content": a.get("content", ""),
                "summary": a.get("summary", ""),
                "source": a.get("source", ""),
                "source_url": a.get("url") or a.get("source_url", ""),
                "factual_score": groq_data.get("factual_score", a.get("factual_score", 0)),
                "analytical_score": groq_data.get("analytical_score", a.get("analytical_score", 0)),
                "upsc_relevance": groq_data.get("upsc_relevance", a.get("upsc_relevance", 0)),
                "category": a.get("category", "current_affairs"),
                "tags": a.get("tags", []),
                # Enhanced Groq fields
                "key_facts": groq_data.get("key_facts", []),
                "key_vocabulary": groq_data.get("key_vocabulary", {}),
                "exam_angles": groq_data.get("exam_angles", {}),
                "syllabus_tags": groq_data.get("syllabus_tags", []),
                "revision_priority": groq_data.get("revision_priority", "medium"),
                "processing_status": groq_data.get("processing_status", "preliminary")
            }))
        save_res = await rss_processor.bulk_save_to_database(processed_objs)
        return {"success": True, "step": 5, "message": "Saved to database", "data": save_res}
    except Exception as e:
        logger.error(f"Step5 save to database failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


async def process_articles_individually_with_db_state(
    articles: List[Dict[str, Any]],
    use_groq: bool,
    groq: Optional[GroqLLMService],
    total_articles: int
) -> List[Dict[str, Any]]:
    """
    Batch collection of enhanced articles - NO database operations until validation completes

    Process flow:
    1. Collect all enhanced articles in memory
    2. Validation happens AFTER this function returns
    3. Bulk database save happens AFTER validation passes

    IMPORTANT: Both Groq and Gemini now return IDENTICAL schema structure
    """
    refined = []

    logger.info(f"🔄 Collecting {total_articles} articles in memory (no database operations yet)")
    logger.info(f"   Strategy: Try Groq → Fallback to Gemini → Skip on failure")

    for idx, article in enumerate(articles):
        try:
            title = article.get('title', 'Untitled')[:50]
            logger.info(f"📝 Article {idx + 1}/{total_articles}: {title}...")

            content = article.get("content") or article.get("summary") or ""
            result = None
            error_msg = ""

            # Try Groq first, fallback to Gemini on any error
            if use_groq and groq:
                try:
                    analysis = await groq.enhanced_upsc_analysis(content, article.get("category", "current_affairs"))
                    # Groq returns analysis directly - wrap in groq_analysis key
                    result = {**article, "groq_analysis": analysis, "summary": analysis.get("summary", "")}
                    logger.info(f"   ✅ Groq success (collected in memory)")
                except Exception as e:
                    error_msg = f"Groq: {str(e)[:100]}"
                    # Handle Unicode encoding issues in logs
                    safe_error = error_msg.encode('ascii', errors='replace').decode('ascii')
                    logger.warning(f"   ⚠️ Groq failed: {safe_error}")

            # Fallback to Gemini if Groq failed or not enabled
            if not result:
                try:
                    # NEW: Gemini now returns IDENTICAL schema via enhanced_upsc_analysis
                    gemini_analysis = await direct_gemini_service.enhanced_upsc_analysis(content, article.get("category", "current_affairs"))
                    # Wrap in gemini_analysis key (same structure as groq_analysis)
                    result = {**article, "gemini_analysis": gemini_analysis, "summary": gemini_analysis.get("summary", "")}
                    logger.info(f"   ✅ Gemini fallback success (collected in memory)")
                    if error_msg:
                        error_msg += " (recovered with Gemini 2.0 Flash)"
                except Exception as e:
                    error_msg += f" Gemini: {str(e)[:100]}"
                    # Handle Unicode encoding issues in logs
                    safe_error = error_msg.encode('ascii', errors='replace').decode('ascii')
                    logger.error(f"   ❌ Both Groq and Gemini failed: {safe_error} (skipping article)")
                    continue  # Skip this article, continue with next

            if result:
                refined.append(result)
                logger.debug(f"   ✅ Article collected in memory array ({len(refined)}/{total_articles} so far)")

        except Exception as e:
            # Handle Unicode encoding issues in logs
            safe_error = str(e)[:100].encode('ascii', errors='replace').decode('ascii')
            logger.error(f"   ❌ Critical error: {safe_error} (skipping article)")
            continue  # Skip this article, continue with next

    logger.info(f"📦 Collection complete: {len(refined)}/{total_articles} articles enhanced and collected in memory")
    logger.info(f"   Next: Validation → Bulk database save (if validation passes)")
    return refined


@router.post("/complete-pipeline", response_model=Dict[str, Any])
async def complete_pipeline(
    payload: Optional[Dict[str, Any]] = None,
    user: dict = Depends(require_authentication),
    rss_processor: OptimizedRSSProcessor = Depends(get_rss_processor),
    groq: Optional[GroqLLMService] = Depends(get_groq_service)
):
    try:
        # Extract optional parameters
        if payload is None:
            payload = {}
        max_articles = payload.get("max_articles", 25)  # Default to 25 for faster processing
        skip_groq = payload.get("skip_groq", False)  # Option to skip Groq for testing
        
        logger.info("🚀 Starting complete pipeline execution")
        logger.info(f"   📊 Configuration: max_articles={max_articles}, skip_groq={skip_groq}")
        logger.info(f"   📊 Groq service available: {groq is not None and not skip_groq}")
        
        # Step 1
        logger.info("📥 Step 1: Fetching RSS articles...")
        raw_articles = await rss_processor.fetch_all_sources_parallel()
        logger.info(f"   ✅ Step 1 complete: {len(raw_articles)} raw articles fetched")
        
        # Step 2
        logger.info("🔍 Step 2: Processing articles with AI analysis...")
        # Limit articles if specified
        articles_to_process = raw_articles[:max_articles] if max_articles else raw_articles
        logger.info(f"   📊 Processing {len(articles_to_process)} of {len(raw_articles)} articles (limit: {max_articles or 'none'})")
        
        with open("debug_step2_before.txt", "w") as f:
            f.write(f"About to call process_articles_with_single_ai_pass with {len(articles_to_process)} articles\n")
        
        processed = await rss_processor.process_articles_with_single_ai_pass(articles_to_process)
        
        with open("debug_step2_after.txt", "w") as f:
            f.write(f"Step 2 completed with {len(processed)} articles\n")
        
        logger.info(f"   ✅ Step 2 complete: {len(processed)} articles processed")
        
        # Step 3
        logger.info("📄 Step 3: Extracting full content...")
        logger.info(f"🔍 DEBUG: About to call extract_full_content_from_articles with {len(processed)} articles")
        
        # Prepare articles in the format expected by extract_full_content_from_articles
        articles_for_extraction = []
        for i, a in enumerate(processed):
            article_dict = {
                "title": a.title,
                "content": a.content,
                "summary": a.summary,
                "source_url": a.source_url,
                "source": a.source,
                "url": a.source_url,  # Add url field for compatibility
                "description": a.summary,  # Add description field
            }
            articles_for_extraction.append(article_dict)
            logger.info(f"   📄 Article {i+1}: {a.title[:50]}... URL: {a.source_url}")
        
        enriched = await rss_processor.extract_full_content_from_articles(articles_for_extraction)
        logger.info(f"   ✅ Step 3 complete: {len(enriched)} articles enriched")
        
        # Step 4 - Simple individual processing (no batches, no complex logic)
        logger.info("🧠 Step 4: Refining content...")
        use_groq = groq is not None and not skip_groq

        # OPTIMIZATION: Check Groq health ONCE before processing any articles
        if use_groq:
            try:
                groq_health = groq.rotator.get_health_report()
                if groq_health['healthy_keys'] == 0:
                    logger.warning(f"⚠️ All Groq API keys unhealthy ({groq_health['unhealthy_keys']}/{groq_health['total_keys']})")
                    logger.info(f"   🔄 Skipping Groq entirely, using Gemini for all {len(enriched)} articles")
                    use_groq = False  # Skip Groq to avoid wasting time
                else:
                    logger.info(f"   📊 Groq health: {groq_health['healthy_keys']}/{groq_health['total_keys']} keys healthy")
            except Exception as e:
                logger.warning(f"   ⚠️ Groq health check failed: {e}, proceeding anyway")

        logger.info(f"   📊 Processing strategy: {'GROQ with Gemini fallback' if use_groq else 'GEMINI ONLY'}")

        # Process articles one by one - simple and bulletproof
        refined = await process_articles_individually_with_db_state(enriched, use_groq, groq, len(enriched))

        logger.info(f"   ✅ Step 4 complete: {len(refined)} articles refined")

        # VALIDATION: Check if articles were properly enhanced before saving
        logger.info("🔍 Validating enhanced articles before database save...")
        valid_articles = []
        failed_articles = []

        for idx, article in enumerate(refined):
            # Check if article has either groq_analysis or gemini_analysis
            has_groq = "groq_analysis" in article and article.get("groq_analysis")
            has_gemini = "gemini_analysis" in article and article.get("gemini_analysis")

            if not (has_groq or has_gemini):
                logger.warning(f"   ❌ Article {idx + 1} FAILED validation: No enhancement data found")
                failed_articles.append(article.get("title", "Unknown")[:50])
                continue

            # Get the analysis data
            analysis = article.get("groq_analysis") or article.get("gemini_analysis")

            # Validate required fields exist and have valid values
            validation_checks = {
                "factual_score": analysis.get("factual_score", 0) > 0,
                "analytical_score": analysis.get("analytical_score", 0) > 0,
                "upsc_relevance": analysis.get("upsc_relevance", 0) > 0,
                "category": bool(analysis.get("category")),
                "key_facts": isinstance(analysis.get("key_facts"), list),
                "summary": bool(analysis.get("summary"))
            }

            failed_checks = [field for field, passed in validation_checks.items() if not passed]

            if failed_checks:
                logger.warning(f"   ❌ Article {idx + 1} FAILED validation: Missing/invalid fields: {', '.join(failed_checks)}")
                failed_articles.append(article.get("title", "Unknown")[:50])
                continue

            # Additional validation: Reject fallback scores (30/25/35 pattern)
            factual = analysis.get("factual_score", 0)
            analytical = analysis.get("analytical_score", 0)
            relevance = analysis.get("upsc_relevance", 0)

            # Detect fallback response pattern
            is_fallback = (factual == 30 and analytical == 25 and relevance == 35)

            if is_fallback:
                logger.warning(f"   ❌ Article {idx + 1} FAILED validation: Detected fallback scores (30/25/35) - enhancement failed")
                failed_articles.append(article.get("title", "Unknown")[:50])
                continue

            # Article passed validation
            valid_articles.append(article)
            logger.debug(f"   ✅ Article {idx + 1} passed validation")

        logger.info(f"   📊 Validation complete: {len(valid_articles)} passed, {len(failed_articles)} failed")

        if len(failed_articles) > 0:
            logger.warning(f"   ⚠️ Failed articles: {', '.join(failed_articles[:5])}{'...' if len(failed_articles) > 5 else ''}")

        # Only proceed if we have at least 1 valid article
        if len(valid_articles) == 0:
            logger.error(f"   🚨 CRITICAL: No articles passed validation! Aborting database save.")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Pipeline failed: 0/{len(refined)} articles passed enhancement validation. All articles failed to be properly enhanced by Groq or Gemini."
            )

        logger.info(f"   ✅ Proceeding with {len(valid_articles)} validated articles")

        # Step 5 - Save only validated articles
        logger.info("💾 Step 5: Saving validated articles to database...")
        processed_objs: List[ProcessedArticle] = []

        for idx, a in enumerate(valid_articles):
            logger.info(f"   📝 Preparing article {idx + 1}/{len(valid_articles)} for database save")

            # Extract analysis data from Groq or Gemini (IDENTICAL schema now)
            analysis = None
            if "groq_analysis" in a:
                logger.info(f"   🚀 Using Groq analysis data (article {idx + 1})")
                analysis = a.get("groq_analysis", {})
            elif "gemini_analysis" in a:
                logger.info(f"   🔄 Using Gemini analysis data (article {idx + 1})")
                analysis = a.get("gemini_analysis", {})

            # Unified processing for both Groq and Gemini (same schema)
            if analysis:
                factual_score = analysis.get("factual_score", 50)
                analytical_score = analysis.get("analytical_score", 50) 
                upsc_relevance = analysis.get("upsc_relevance", 50)
                
                # Map category to readable format
                category_map = {
                    "polity_governance": "Polity & Governance",
                    "economy_development": "Economy & Development", 
                    "environment_ecology": "Environment & Ecology",
                    "history_culture": "History & Culture",
                    "science_technology": "Science & Technology",
                    "current_affairs": "Current Affairs"
                }
                raw_category = analysis.get("category", "current_affairs")
                category = category_map.get(raw_category, raw_category)
                
                # Extract related topics from syllabus_tags
                related_topics = analysis.get("syllabus_tags", [])
                
                # Extract potential questions from exam_angles
                exam_angles = analysis.get("exam_angles", {})
                potential_questions = []
                if exam_angles.get("prelims_facts"):
                    potential_questions.extend([f"[Prelims] {q}" for q in exam_angles["prelims_facts"][:3]])
                if exam_angles.get("mains_angles"):
                    potential_questions.extend([f"[Mains] {q}" for q in exam_angles["mains_angles"][:3]])
                
                # Extract GS paper from syllabus_tags
                gs_paper = None
                for tag in related_topics:
                    if tag.startswith("GS"):
                        # Extract just GS1, GS2, etc. from tags like "GS2: Ministry of Youth Affairs"
                        import re
                        match = re.match(r'GS([1-4])', tag)
                        if match:
                            gs_paper = f"GS{match.group(1)}"
                            break
                
                tags = analysis.get("key_facts", [])[:5]  # Use key_facts as tags
                summary = a.get("summary") or analysis.get("summary", a.get("content", "")[:200])
            else:
                logger.info(f"   🔄 Using fallback data (article {idx + 1})")
                # Gemini fallback path or Step 2 data
                factual_score = a.get("factual_score", 50)
                analytical_score = a.get("analytical_score", 50)
                upsc_relevance = a.get("upsc_relevance", 50)
                category = a.get("category", "Current Affairs")  # Default to readable format
                tags = a.get("tags", [])
                summary = a.get("summary", a.get("content", "")[:200])
                related_topics = []  # Empty for fallback
                potential_questions = []  # Empty for fallback
                gs_paper = None  # None for fallback
            
            # Create ProcessedArticle with all enhanced fields INCLUDING key_facts, key_vocabulary, exam_angles
            article_obj = ProcessedArticle(**{
                "title": a.get("title", ""),
                "content": a.get("content", ""),
                "summary": summary,
                "source": a.get("source", ""),
                "source_url": a.get("url") or a.get("source_url", ""),
                "factual_score": factual_score,
                "analytical_score": analytical_score,
                "upsc_relevance": upsc_relevance,
                "category": category,
                "tags": tags,
                "syllabus_tags": related_topics,  # Map to syllabus_tags field
                "gs_paper": gs_paper,  # Add GS paper field
                # ADD MISSING ENHANCED FIELDS FROM ANALYSIS
                "key_facts": analysis.get("key_facts", []) if analysis else [],
                # Convert key_vocabulary from array to dict if needed (Gemini returns array, ProcessedArticle expects dict)
                "key_vocabulary": {term: f"UPSC term: {term}" for term in analysis.get("key_vocabulary", [])} if analysis and isinstance(analysis.get("key_vocabulary"), list) else (analysis.get("key_vocabulary", {}) if analysis else {}),
                "exam_angles": exam_angles if analysis else {},
                "revision_priority": analysis.get("revision_priority", "medium") if analysis else "medium",
                "processing_status": analysis.get("processing_status", "preliminary") if analysis else "preliminary",
            })
            
            # Add potential_questions as a custom attribute for database mapping
            article_obj.potential_questions = potential_questions
            article_obj.related_topics = related_topics
            
            processed_objs.append(article_obj)
        
        logger.info(f"   📊 Prepared {len(processed_objs)} articles for database save")
        logger.info("   💾 Executing bulk save to database...")
        save_res = await rss_processor.bulk_save_to_database(processed_objs)
        logger.info(f"   ✅ Step 5 complete: Database save result: {save_res}")
        
        logger.info("🎉 Complete pipeline execution successful!")
        logger.info(f"   📊 Final stats: Raw={len(raw_articles)}, Processed={len(processed)}, Enriched={len(enriched)}, Refined={len(refined)}")
        
        return {
            "success": True,
            "message": "Complete pipeline executed",
            "data": {
                "step1_raw_count": len(raw_articles),
                "step2_processed_count": len(processed),
                "step3_enriched_count": len(enriched),
                "step4_refined_sample": refined[:5],
                "step5_save": save_res,
            },
        }
    except Exception as e:
        logger.error(f"Complete pipeline failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


