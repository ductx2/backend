"""
Full Pipeline Test - End-to-End Verification
Tests complete RSS processing pipeline with Vercel AI Gateway + DeepSeek V3.2
"""

import asyncio
import sys
import os
from datetime import datetime
import json

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))


async def main():
    print("=" * 80)
    print("FULL PIPELINE TEST: RSS -> AI Processing -> Supabase")
    print("=" * 80)
    print()

    # Import after path is set
    from app.api.simplified_flow import (
        step1_extract_rss,
        step2_analyze_relevance,
        step3_extract_content,
        step4_refine_content,
        step5_save_to_database,
        AnalysisRequest,
        RefinementRequest,
        SaveRequest,
    )
    from app.core.database import get_database

    # Mock admin user
    mock_admin = {"user_id": "test_admin", "role": "admin"}

    try:
        pipeline_start = datetime.utcnow()

        # Step 1: Extract RSS Feeds
        print("[STEP 1] Extracting RSS feeds from Hindu, IE, TOI...")
        step1_start = datetime.utcnow()

        step1_response = await step1_extract_rss(user=mock_admin)
        articles = step1_response["data"]["articles"]

        step1_time = (datetime.utcnow() - step1_start).total_seconds()
        print(f"[OK] STEP 1 COMPLETE ({step1_time:.2f}s)")
        print(f"   - Total articles extracted: {len(articles)}")
        print()

        # Step 2: AI Analysis for UPSC Relevance
        print("[STEP 2] AI Analysis with DeepSeek V3.2 (via Vercel AI Gateway)...")
        step2_start = datetime.utcnow()

        analysis_request = AnalysisRequest(articles=articles, min_relevance_score=40)
        step2_response = await step2_analyze_relevance(
            analysis_request, user=mock_admin
        )
        relevant_articles = step2_response["data"]["relevant_articles"]

        step2_time = (datetime.utcnow() - step2_start).total_seconds()
        print(f"[OK] STEP 2 COMPLETE ({step2_time:.2f}s)")
        print(f"   - Articles analyzed: {len(articles)}")
        print(f"   - UPSC relevant (score >=40): {len(relevant_articles)}")
        print(
            f"   - Average relevance: {step2_response['data']['stats']['avg_relevance']:.1f}/100"
        )
        print()

        # Step 3: Extract Full Content
        print("[STEP 3] Extracting full article content...")
        step3_start = datetime.utcnow()

        # Limit to top 10 for testing
        top_articles = relevant_articles[:10]
        extraction_request_data = {
            "selected_articles": [
                {"title": a["title"], "url": a["source_url"]} for a in top_articles
            ]
        }
        step3_response = await step3_extract_content(
            extraction_request_data, user=mock_admin
        )
        extracted_articles = step3_response["data"]["extracted_articles"]

        step3_time = (datetime.utcnow() - step3_start).total_seconds()
        print(f"[OK] STEP 3 COMPLETE ({step3_time:.2f}s)")
        print(f"   - Articles selected: {len(top_articles)}")
        print(f"   - Successfully extracted: {len(extracted_articles)}")
        print()

        # Step 4: AI Refinement
        print("[STEP 4] AI Content Refinement with DeepSeek V3.2...")
        step4_start = datetime.utcnow()

        refinement_request = RefinementRequest(articles=extracted_articles)
        step4_response = await step4_refine_content(refinement_request, user=mock_admin)
        refined_articles = step4_response["data"]["refined_articles"]

        step4_time = (datetime.utcnow() - step4_start).total_seconds()
        print(f"[OK] STEP 4 COMPLETE ({step4_time:.2f}s)")
        print(f"   - Articles refined: {len(refined_articles)}")
        print()

        # Step 5: Save to Supabase
        print("[STEP 5] Saving to Supabase current_affairs table...")
        step5_start = datetime.utcnow()

        save_request = SaveRequest(processed_articles=refined_articles)
        db = await get_database()
        step5_response = await step5_save_to_database(
            save_request, user=mock_admin, db=db
        )

        step5_time = (datetime.utcnow() - step5_start).total_seconds()
        print(f"[OK] STEP 5 COMPLETE ({step5_time:.2f}s)")
        print(f"   - Articles saved: {step5_response['data']['saved_articles']}")
        print(
            f"   - Duplicates skipped: {step5_response['data']['duplicates_skipped']}"
        )
        print()

        # Pipeline Summary
        total_time = (datetime.utcnow() - pipeline_start).total_seconds()

        print("=" * 80)
        print("PIPELINE SUMMARY")
        print("=" * 80)
        print(f"[OK] Total Pipeline Time: {total_time:.2f}s")
        print()
        print(f"Step Breakdown:")
        print(
            f"   1. RSS Extraction:     {step1_time:>6.2f}s ({len(articles)} articles)"
        )
        print(
            f"   2. AI Analysis:        {step2_time:>6.2f}s ({len(relevant_articles)} relevant)"
        )
        print(
            f"   3. Content Extraction: {step3_time:>6.2f}s ({len(extracted_articles)} extracted)"
        )
        print(
            f"   4. AI Refinement:      {step4_time:>6.2f}s ({len(refined_articles)} refined)"
        )
        print(
            f"   5. Database Save:      {step5_time:>6.2f}s ({step5_response['data']['saved_articles']} saved)"
        )
        print()
        print(f"Final Results:")
        print(f"   - Total RSS articles: {len(articles)}")
        print(f"   - UPSC relevant: {len(relevant_articles)}")
        print(f"   - Successfully saved: {step5_response['data']['saved_articles']}")
        print()

        # Save results for verification
        results = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_time_seconds": total_time,
            "steps": {
                "step1_rss_extraction": {
                    "time_seconds": step1_time,
                    "articles_extracted": len(articles),
                },
                "step2_ai_analysis": {
                    "time_seconds": step2_time,
                    "articles_analyzed": len(articles),
                    "relevant_articles": len(relevant_articles),
                    "avg_relevance": step2_response["data"]["stats"]["avg_relevance"],
                },
                "step3_content_extraction": {
                    "time_seconds": step3_time,
                    "articles_processed": len(extracted_articles),
                },
                "step4_ai_refinement": {
                    "time_seconds": step4_time,
                    "articles_refined": len(refined_articles),
                },
                "step5_database_save": {
                    "time_seconds": step5_time,
                    "articles_saved": step5_response["data"]["saved_articles"],
                    "duplicates_skipped": step5_response["data"]["duplicates_skipped"],
                },
            },
            "sample_article": refined_articles[0] if refined_articles else None,
        }

        with open("pipeline_result.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        print(f"[OK] Full results saved to: pipeline_result.json")
        print()
        print("=" * 80)
        print("[SUCCESS] PIPELINE TEST COMPLETED SUCCESSFULLY!")
        print("=" * 80)
        print()
        print("Next step: Verify data in Supabase using MCP tools")

        return results

    except Exception as e:
        print(f"\n[FAIL] PIPELINE FAILED: {e}")
        import traceback

        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(main())
    sys.exit(0 if result else 1)
