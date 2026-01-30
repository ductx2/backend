import google.generativeai as genai
import json
import asyncio
from typing import Dict, Any, List
import os


class DirectGeminiService:
    """Direct Gemini service with round-robin API key rotation.

    Uses gemini-2.0-flash (1500 RPD free tier per key).
    Rotates through multiple API keys to maximize quota utilization.
    """

    def __init__(self):
        # Collect all available API keys
        self.api_keys: List[str] = []

        # Try numbered keys first (GEMINI_API_KEY_1, _2, _3, etc.)
        for i in range(1, 6):
            key = os.getenv(f"GEMINI_API_KEY_{i}")
            if key:
                self.api_keys.append(key)

        # Fallback to single key
        if not self.api_keys:
            key = os.getenv("GEMINI_API_KEY")
            if key:
                self.api_keys.append(key)

        if not self.api_keys:
            raise ValueError("No Gemini API keys found in environment")

        self.current_key_index = 0
        self.model_name = "gemini-2.5-flash"
        self.generation_config = {
            "temperature": 0.3,
            "top_p": 0.8,
            "top_k": 40,
            "max_output_tokens": 2000,
        }

        print(f"DirectGeminiService initialized with {len(self.api_keys)} API keys")

    def _get_model(self) -> genai.GenerativeModel:
        """Get a model instance with the current API key (round-robin)."""
        api_key = self.api_keys[self.current_key_index]
        genai.configure(api_key=api_key)

        # Rotate to next key for next call
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)

        return genai.GenerativeModel(
            model_name=self.model_name,
            generation_config=self.generation_config,
        )

    def _try_all_keys(self, prompt: str) -> str:
        """Try generating content with all available keys until one succeeds."""
        last_error = None

        for attempt in range(len(self.api_keys)):
            try:
                model = self._get_model()
                response = model.generate_content(prompt)
                if response and response.text:
                    return response.text
            except Exception as e:
                last_error = e
                print(f"Key {attempt + 1}/{len(self.api_keys)} failed: {str(e)[:100]}")
                continue

        raise last_error or Exception("All API keys exhausted")

    async def analyze_upsc_relevance(self, title: str, content: str) -> Dict[str, Any]:
        """Analyze UPSC relevance of an article"""
        prompt = f"""
Analyze this article for UPSC Civil Services exam relevance.

Title: {title}
Content: {content[:1000]}

Return JSON with this EXACT structure:
{{
  "upsc_relevance": <score 1-100>,
  "relevant_papers": ["Paper 1 GS", "Paper 2 GS", "Paper 3 GS", "Paper 4 GS"],
  "key_topics": ["topic1", "topic2", "topic3"],
  "importance_level": "High/Medium/Low",
  "question_potential": "High/Medium/Low",
  "summary": "brief relevance summary"
}}

Score criteria:
- 80-100: Highly relevant (current affairs, policy, governance)
- 60-79: Moderately relevant (general knowledge, background)
- 40-59: Somewhat relevant (tangential topics)
- 1-39: Low relevance (entertainment, sports, etc.)
"""

        try:
            text = self._try_all_keys(prompt)
            # Clean JSON response
            text = text.strip()
            if text.startswith("```json"):
                text = text.replace("```json", "").replace("```", "").strip()
            elif text.startswith("```"):
                text = text.replace("```", "").strip()

            data = json.loads(text)
            return data
        except Exception as e:
            print(f"Direct Gemini UPSC analysis failed: {e}")
            return {
                "upsc_relevance": 0,
                "relevant_papers": [],
                "key_topics": [],
                "importance_level": "Low",
                "question_potential": "Low",
                "summary": "Analysis failed",
            }

    async def refine_content(self, content: str) -> Dict[str, Any]:
        """Refine and summarize content for UPSC preparation"""
        prompt = f"""
Create a UPSC-focused summary and analysis of this content.

Content: {content[:2000]}

Return JSON with this EXACT structure:
{{
  "generated_title": "Compelling, descriptive title (50-100 chars) that captures the key point for UPSC aspirants",
  "brief_summary": "2-3 sentence summary",
  "detailed_summary": "comprehensive 1-2 paragraph summary",
  "key_points": ["point1", "point2", "point3", "point4", "point5"],
  "upsc_relevance": "explanation of UPSC exam relevance",
  "exam_tip": "specific tip for UPSC preparation"
}}

Title requirements:
- Make it specific and informative (not generic)
- Focus on the key development/policy/issue
- Use active language
- Keep it between 50-100 characters
- Make it UPSC exam relevant
"""

        try:
            text = self._try_all_keys(prompt)
            # Clean JSON response
            text = text.strip()
            if text.startswith("```json"):
                text = text.replace("```json", "").replace("```", "").strip()
            elif text.startswith("```"):
                text = text.replace("```", "").strip()

            data = json.loads(text)
            return data
        except Exception as e:
            print(f"Direct Gemini content refinement failed: {e}")
            return {
                "generated_title": "Content Processing Error",
                "brief_summary": "Summary failed",
                "detailed_summary": "Analysis unavailable",
                "key_points": [],
                "upsc_relevance": "Unknown",
                "exam_tip": "Review manually",
            }


# Global instance
direct_gemini_service = DirectGeminiService()
