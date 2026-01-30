"""
Test GS Paper & Tags Fix
Verifies that DeepSeek now returns proper GS papers and key topics
"""

import asyncio
import sys
import os
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "."))


async def test_upsc_analysis_fix():
    print("=" * 80)
    print("TEST: GS Paper & Tags Fix Verification")
    print("=" * 80)
    print()

    from app.services.centralized_llm_service import llm_service
    from app.models.llm_schemas import LLMRequest, TaskType, ProviderPreference

    # Test article about Indian politics
    test_content = """
    Supreme Court Ruling on Electoral Bonds: Major Implications for Democracy
    
    The Supreme Court of India has struck down the electoral bonds scheme as unconstitutional, 
    calling it a violation of citizens' right to information. The 5-judge bench unanimously 
    ruled that the scheme, which allowed anonymous political donations, compromised transparency 
    in political funding and gave undue advantage to ruling parties.
    
    The court directed the State Bank of India to disclose all donor details to the Election 
    Commission within three weeks. This landmark judgment is expected to significantly impact 
    political funding mechanisms in India and strengthen democratic accountability.
    
    Constitutional experts hail this as a victory for transparency and the right to information 
    under Article 19(1)(a) of the Constitution.
    """

    print("[TEST 1] Analyzing article about Supreme Court & Electoral Bonds...")
    print()

    request = LLMRequest(
        task_type=TaskType.UPSC_ANALYSIS,
        content=test_content,
        provider_preference=ProviderPreference.COST_OPTIMIZED,
        temperature=0.1,
        max_tokens=2000,
    )

    try:
        # Initialize LLM service
        await llm_service.initialize_router()

        # Process request
        response = await llm_service.process_request(request)

        print(f"[OK] Analysis completed successfully!")
        print(f"   - Model used: {response.model_used}")
        print(f"   - Response time: {response.response_time:.2f}s")
        print(f"   - Tokens used: {response.tokens_used}")
        print()

        # Verify GS Paper & Tags
        data = response.data

        print("=" * 80)
        print("VERIFICATION RESULTS")
        print("=" * 80)
        print()

        print(f"UPSC Relevance Score: {data.get('upsc_relevance')}/100")
        print()

        # Check GS Papers
        gs_papers = data.get("relevant_papers", [])
        print(f"GS Papers (relevant_papers): {gs_papers}")
        if len(gs_papers) >= 1:
            print(f"   [PASS] At least 1 GS paper returned (got {len(gs_papers)})")
        else:
            print(f"   [FAIL] No GS papers returned! (expected at least 1)")
        print()

        # Check Key Topics
        key_topics = data.get("key_topics", [])
        print(f"Key Topics (key_topics): {key_topics}")
        if len(key_topics) >= 3:
            print(f"   [PASS] At least 3 key topics returned (got {len(key_topics)})")
        else:
            print(
                f"   [FAIL] Not enough key topics! (got {len(key_topics)}, expected at least 3)"
            )
        print()

        # Other fields
        print(f"Importance Level: {data.get('importance_level')}")
        print(f"Question Potential: {data.get('question_potential')}")
        print(f"Summary: {data.get('summary', '')[:100]}...")
        print()

        # Final verdict
        print("=" * 80)
        if len(gs_papers) >= 1 and len(key_topics) >= 3:
            print("[SUCCESS] GS Paper & Tags Fix VERIFIED!")
            print()
            print("Expected Database Values:")
            print(f"   - gs_paper: {', '.join(gs_papers)}")
            print(f"   - tags: {key_topics}")
            return True
        else:
            print("[FAILED] GS Paper & Tags still empty!")
            print()
            print("Issue persists - prompt may need further tuning")
            return False
        print("=" * 80)

    except Exception as e:
        print(f"\n[FAIL] Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_upsc_analysis_fix())
    sys.exit(0 if result else 1)
