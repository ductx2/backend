import asyncio
import os
import litellm
import json
from dotenv import load_dotenv

load_dotenv('.env')

async def test():
    api_key = os.environ.get('VERCEL_AI_GATEWAY_API_KEY') or os.environ.get('AI_GATEWAY_API_KEY')
    print(f"API Key found: {bool(api_key)}")

    # Test with legacy JSON format (type: json)
    response = await litellm.acompletion(
        model="openai/gpt-oss-120b",
        messages=[{"role": "user", "content": "Analyze for UPSC: Supreme Court upholds Article 370 abrogation"}],
        api_key=api_key,
        api_base="https://ai-gateway.vercel.sh/v1",
        response_format={
            "type": "json",
            "name": "upsc_analysis",
            "description": "UPSC relevance analysis",
            "schema": {
                "type": "object",
                "properties": {
                    "upsc_relevance": {"type": "integer"},
                    "category": {"type": "string"},
                    "relevant_papers": {"type": "array", "items": {"type": "string"}},
                    "key_topics": {"type": "array", "items": {"type": "string"}},
                    "key_vocabulary": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "term": {"type": "string"},
                                "definition": {"type": "string"}
                            }
                        }
                    },
                    "summary": {"type": "string"}
                },
                "required": ["upsc_relevance", "category", "relevant_papers", "key_topics", "summary"]
            }
        },
        temperature=0.1,
        max_tokens=800,
    )

    print(f"Model: {response.model}")
    content = response.choices[0].message.content
    data = json.loads(content)
    print(f"upsc_relevance: {data.get('upsc_relevance')}")
    print(f"category: {data.get('category')}")
    print(f"relevant_papers: {data.get('relevant_papers')}")
    print(f"key_topics: {data.get('key_topics')}")
    print(f"key_vocabulary count: {len(data.get('key_vocabulary', []))}")
    if data.get('key_vocabulary'):
        for v in data['key_vocabulary'][:2]:
            print(f"  - {v.get('term')}")

asyncio.run(test())
