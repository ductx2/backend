import asyncio
import sys
import json
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from app.services.centralized_llm_service import llm_service
from app.models.llm_schemas import LLMRequest, TaskType, ProviderPreference

async def test():
    await llm_service.initialize_router()

    request = LLMRequest(
        task_type=TaskType.UPSC_ANALYSIS,
        content="Title: India launches Aditya-L1 solar mission\nContent: ISRO successfully launched India's first dedicated solar observatory mission, Aditya-L1, to study the Sun's corona and solar wind. The spacecraft will be placed at the Lagrangian point L1, about 1.5 million km from Earth.",
        provider_preference=ProviderPreference.COST_OPTIMIZED,
        temperature=0.1,
        max_tokens=1000,
    )

    response = await llm_service.process_request(request)

    print(f"Success: {response.success}")
    print(f"Model: {response.model_used}")
    if response.data:
        print(f"upsc_relevance: {response.data.get('upsc_relevance')}")
        print(f"category: {response.data.get('category')}")
        print(f"relevant_papers: {response.data.get('relevant_papers')}")
        print(f"key_topics count: {len(response.data.get('key_topics', []))}")
        print(f"key_vocabulary count: {len(response.data.get('key_vocabulary', []))}")
        if response.data.get('key_vocabulary'):
            for v in response.data['key_vocabulary'][:3]:
                term = v.get('term', '').encode('ascii', 'replace').decode()
                print(f"  - term: {term}")
        # Write full response to file for inspection
        with open('test_output.json', 'w', encoding='utf-8') as f:
            json.dump(response.data, f, indent=2, ensure_ascii=False)
        print("Full response written to test_output.json")

asyncio.run(test())
