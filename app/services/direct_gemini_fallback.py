"""
Gemini 2.0 Flash Fallback Service for Enhanced UPSC Content Analysis
Drop-in replacement when Groq fails - returns IDENTICAL schema

Created: 2025-10-10
Purpose: Fallback service with Groq-compatible output schema
Model: gemini-2.0-flash-exp (Google's latest experimental model)
Features: Identical output structure, multi-key rotation, structured responses
"""

import google.generativeai as genai
import json
import asyncio
import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)

class GeminiAPIRotator:
    """
    API key rotation system for Gemini (identical to GroqAPIRotator)
    Manages 23 API keys with health tracking and failover
    """

    def __init__(self, api_keys: List[str]):
        """Initialize rotator with list of API keys"""
        self.api_keys = api_keys
        self.current_index = 0

        # Track health status for each key
        self.key_health = {key: {"healthy": True, "failures": 0, "last_failure": None} for key in api_keys}

        logger.info(f"🔄 Gemini API Rotator initialized with {len(api_keys)} keys")

    def get_next_healthy_key(self) -> str:
        """Get next healthy API key using round-robin"""
        attempts = 0
        max_attempts = len(self.api_keys)

        while attempts < max_attempts:
            key = self.api_keys[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.api_keys)

            if self.key_health[key]["healthy"]:
                logger.debug(f"🔑 Using Gemini API key index: {self.current_index - 1}")
                return key

            attempts += 1

        # No healthy keys available
        logger.critical(f"🚨 All Gemini API keys are unhealthy - system needs manual intervention")
        return None

    def record_success(self, key: str):
        """Record successful API call for a key"""
        if key in self.key_health:
            self.key_health[key]["healthy"] = True
            self.key_health[key]["failures"] = 0
            logger.debug(f"✅ Gemini key {key[:12]}... marked healthy")

    def record_failure(self, key: str, error_msg: str):
        """Record failed API call for a key"""
        if key in self.key_health:
            self.key_health[key]["failures"] += 1
            self.key_health[key]["last_failure"] = datetime.utcnow().isoformat()

            # Mark unhealthy after 3 consecutive failures
            if self.key_health[key]["failures"] >= 3:
                self.key_health[key]["healthy"] = False
                logger.warning(f"⚠️ Gemini key {key[:12]}... marked unhealthy after {self.key_health[key]['failures']} failures")

    def get_health_report(self) -> Dict[str, Any]:
        """Get health status report for all keys"""
        healthy_count = sum(1 for status in self.key_health.values() if status["healthy"])
        total_count = len(self.api_keys)

        return {
            "total_keys": total_count,
            "healthy_keys": healthy_count,
            "unhealthy_keys": total_count - healthy_count,
            "health_percentage": round((healthy_count / total_count) * 100, 2) if total_count > 0 else 0
        }

    @property
    def healthy_key_count(self) -> int:
        """Get count of currently healthy keys"""
        return sum(1 for status in self.key_health.values() if status["healthy"])


class DirectGeminiService:
    """
    Gemini 2.0 Flash fallback service with Groq-compatible schema
    Returns IDENTICAL output structure for seamless database integration
    """

    def __init__(self, api_keys: List[str]):
        """Initialize Gemini service with multi-key rotation"""
        if not api_keys:
            raise ValueError("At least one Gemini API key is required")

        self.api_keys = api_keys
        self.rotator = GeminiAPIRotator(api_keys)

        # Define IDENTICAL schema as Groq for structured output
        self.upsc_analysis_schema = {
            "type": "object",
            "properties": {
                "factual_score": {
                    "type": "integer",
                    "format": "int32",
                    "description": "Prelims MCQ potential (0-100)"
                },
                "analytical_score": {
                    "type": "integer",
                    "format": "int32",
                    "description": "Mains answer potential (0-100)"
                },
                "upsc_relevance": {
                    "type": "integer",
                    "format": "int32",
                    "description": "Overall UPSC relevance (0-100)"
                },
                "category": {
                    "type": "string",
                    "enum": ["current_affairs", "polity_governance", "economy_development", "environment_ecology", "history_culture", "science_technology"],
                    "description": "Primary UPSC category"
                },
                "key_facts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Important facts for exam preparation"
                },
                "key_vocabulary": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Technical terms and acronyms"
                },
                "syllabus_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "GS paper topics"
                },
                "exam_angles": {
                    "type": "object",
                    "properties": {
                        "prelims_facts": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "mains_angles": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "essay_themes": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["prelims_facts", "mains_angles", "essay_themes"]
                },
                "revision_priority": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "Study importance ranking"
                },
                "processing_status": {
                    "type": "string",
                    "enum": ["preliminary", "quality", "premium"],
                    "description": "Content quality tier"
                },
                "summary": {
                    "type": "string",
                    "description": "2-sentence UPSC-focused summary"
                },
                "enhanced_content_html": {
                    "type": "string",
                    "description": "Professionally formatted HTML content with semantic structure, headings, lists, and emphasis for rich display"
                }
            },
            "required": [
                "factual_score", "analytical_score", "upsc_relevance", "category",
                "key_facts", "key_vocabulary", "syllabus_tags", "exam_angles",
                "revision_priority", "processing_status", "summary", "enhanced_content_html"
            ]
        }

        logger.info(f"🚀 Gemini 2.0 Flash Fallback Service initialized with {len(api_keys)} API keys")
        logger.info(f"📊 Schema compatibility: Groq-identical (12 fields including HTML)")

    async def enhanced_upsc_analysis(self, content: str, category: str = "current_affairs") -> Dict[str, Any]:
        """
        Perform enhanced UPSC analysis - IDENTICAL to Groq output

        Args:
            content: Article content to analyze
            category: Content category for context

        Returns:
            Dict with EXACT same structure as Groq enhanced_upsc_analysis()
        """
        try:
            # Build analysis prompt (same as Groq)
            prompt = self._build_analysis_prompt(content, category)

            # Make API request with key rotation
            response = await self._make_gemini_structured_request(prompt)

            # Extract and validate response
            analysis_result = self._extract_structured_response(response)

            logger.info(f"✅ Gemini enhanced analysis completed:")
            logger.info(f"   📊 Factual: {analysis_result['factual_score']}/100")
            logger.info(f"   📝 Analytical: {analysis_result['analytical_score']}/100")
            logger.info(f"   🎯 UPSC Relevance: {analysis_result['upsc_relevance']}/100")
            logger.info(f"   📚 Category: {analysis_result['category']}")
            logger.info(f"   🎯 Status: {analysis_result['processing_status']}")

            return analysis_result

        except Exception as e:
            logger.error(f"❌ Gemini enhanced analysis failed: {e}")
            return self._get_fallback_response(category)

    def _build_analysis_prompt(self, content: str, category: str) -> str:
        """
        Build world-class analysis prompt with STRICT scoring + HTML generation
        IDENTICAL to Groq prompt for consistent output
        """
        # Optimize content length - save tokens for comprehensive HTML response
        content_length = min(len(content), 6000)
        analysis_content = content[:content_length] if len(content) > content_length else content

        prompt = f"""You are an expert UPSC Civil Services content analyst. Analyze this news article with STRICT standards and generate professional HTML-formatted content.

ARTICLE CONTENT:
{analysis_content}

=== TASK 1: STRICT SCORING (Be Conservative) ===

FACTUAL SCORE (0-100):
- Count concrete facts ONLY: dates, numbers, names, policies, statistics
- Most articles: 20-40 (basic facts)
- Exceptional: 50+ (rich factual content)

ANALYTICAL SCORE (0-100):
- Assess depth of policy analysis, cause-effect relationships, implications
- Basic news: 15-35 (surface level)
- Deep analysis: 50+ (comprehensive insights)

UPSC RELEVANCE (0-100):
- Direct UPSC syllabus alignment
- Peripheral topics: 20-40
- Core topics (GS Papers): 60+
- Critical exam topics: 80+

=== TASK 2: METADATA EXTRACTION ===

KEY_FACTS (Array):
- Extract 5-10 most important facts
- Focus on: dates, numbers, names, policies, locations
- Each fact should be self-contained and specific
- Example: "NHAI to deploy 100 Network Survey Vehicles across 20,000 km"

KEY_VOCABULARY (Array):
- Extract 5-10 technical terms, acronyms, important names
- UPSC-relevant terminology only
- Example: ["NHAI", "Network Survey Vehicles", "National Highways"]

SYLLABUS_TAGS (Array):
- Map to specific GS paper topics (max 5)
- Format: "GS3: Infrastructure Development", "GS2: Government Policies"

EXAM_ANGLES:
- prelims_facts: 5-8 MCQ-suitable factual points
- mains_angles: 3-5 analytical angles for 10/15 mark questions
- essay_themes: 2-3 broader themes for essay writing

=== TASK 3: HTML CONTENT GENERATION (CRITICAL) ===

Generate enhanced_content_html with PROFESSIONAL formatting:

STRUCTURE REQUIREMENTS:
1. Start with <h2> for main sections (e.g., "Overview", "Key Developments")
2. Use <h3> for subsections
3. Wrap ALL paragraphs in <p> tags
4. Format bullet points as <ul><li>...</li></ul>
5. Use <strong> for important numbers, dates, names, acronyms
6. Create scannable, well-organized content

CONTENT ENHANCEMENT:
- Reorganize content into logical sections
- Highlight UPSC-relevant information
- Add context where needed
- Make it visually appealing and easy to scan

EXAMPLE STRUCTURE:
<h2>Overview</h2>
<p>The <strong>National Highways Authority of India (NHAI)</strong> announced deployment of <strong>100 Network Survey Vehicles</strong> to monitor over <strong>20,000 km</strong> of national highways. This initiative aims to improve road infrastructure quality assessment.</p>

<h3>Key Developments</h3>
<ul>
  <li><strong>Timeline:</strong> Deployment begins <strong>January 2025</strong></li>
  <li><strong>Coverage:</strong> Focus on <strong>Golden Quadrilateral</strong> and <strong>North-South-East-West Corridor</strong></li>
  <li><strong>Technology:</strong> GPS-enabled vehicles with advanced sensors</li>
</ul>

<h3>UPSC Relevance</h3>
<p>This initiative connects to <strong>GS3: Infrastructure</strong> and demonstrates government focus on <strong>road network modernization</strong>. Key for Mains questions on infrastructure development.</p>

<h3>Important Facts</h3>
<ul>
  <li>India has over <strong>1.4 lakh km</strong> of national highways</li>
  <li>NHAI manages approximately <strong>1.3 lakh km</strong></li>
  <li>Budget allocation: <strong>₹2,000 crore</strong> for FY 2024-25</li>
</ul>

QUALITY STANDARDS:
- Content should be 2-3x the length of original (add context, structure)
- Every important number/date must be in <strong> tags
- Use semantic HTML (not just <div> tags)
- Make it readable and professional

=== OUTPUT FORMAT ===

Return ONLY valid JSON matching the schema. Be strict with scoring - most articles are preliminary (30-50 combined score), few are quality (50-70), very few are premium (70+).

PRIORITY: high (core UPSC), medium (relevant), low (peripheral)
SUMMARY: 2 sentences max, focus on exam utility"""

        return prompt

    async def _make_gemini_structured_request(self, prompt: str) -> Dict[str, Any]:
        """Make structured API request with key rotation"""
        max_retries = self.rotator.healthy_key_count or 1

        for attempt in range(max_retries):
            current_key = self.rotator.get_next_healthy_key()

            if not current_key:
                raise Exception("No healthy Gemini API keys available")

            try:
                # Configure Gemini with current API key
                genai.configure(api_key=current_key)

                # Create model with structured output
                model = genai.GenerativeModel(
                    model_name="gemini-2.0-flash-exp",
                    generation_config={
                        "temperature": 0.1,
                        "top_p": 0.8,
                        "top_k": 40,
                        "max_output_tokens": 5000,  # Increased from 3500 for HTML generation
                        "response_mime_type": "application/json",
                        "response_schema": self.upsc_analysis_schema
                    }
                )

                # Generate content
                response = await asyncio.to_thread(
                    model.generate_content,
                    prompt
                )

                # Check for successful response
                if response and response.text:
                    self.rotator.record_success(current_key)
                    logger.info(f"✅ Gemini API success with key {current_key[:12]}... (attempt {attempt + 1})")
                    return {"text": response.text}
                else:
                    raise Exception("Empty response from Gemini API")

            except Exception as e:
                self.rotator.record_failure(current_key, str(e))
                logger.error(f"❌ Gemini API request failed with key {current_key[:12]}... (attempt {attempt + 1}): {e}")

                if attempt < max_retries - 1:
                    await asyncio.sleep(2.0)

        # All keys failed
        health_report = self.rotator.get_health_report()
        logger.error(f"🚨 All {max_retries} Gemini API attempts failed. Health: {health_report['healthy_keys']}/{health_report['total_keys']} keys healthy")
        raise Exception(f"All {max_retries} Gemini API attempts failed")

    def _extract_structured_response(self, api_response: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and validate structured response"""
        try:
            # Parse JSON response (already structured by Gemini)
            analysis_data = json.loads(api_response["text"])

            # Validate required keys
            required_keys = [
                "factual_score", "analytical_score", "upsc_relevance", "category",
                "key_facts", "key_vocabulary", "syllabus_tags", "exam_angles",
                "revision_priority", "summary"
            ]

            missing_keys = [key for key in required_keys if key not in analysis_data]
            if missing_keys:
                logger.warning(f"⚠️ Structured response missing keys: {missing_keys}")
                return self._get_fallback_response("current_affairs")

            # Validate processing status based on combined scores
            combined_score = analysis_data["factual_score"] + analysis_data["analytical_score"]
            if combined_score >= 140:
                analysis_data["processing_status"] = "premium"
            elif combined_score >= 100:
                analysis_data["processing_status"] = "quality"
            else:
                analysis_data["processing_status"] = "preliminary"

            return analysis_data

        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.error(f"❌ Failed to extract structured response: {e}")
            return self._get_fallback_response("current_affairs")

    def _get_fallback_response(self, category: str) -> Dict[str, Any]:
        """Fallback response - IDENTICAL structure to Groq"""
        return {
            "factual_score": 30,
            "analytical_score": 25,
            "upsc_relevance": 35,
            "category": category,
            "key_facts": ["Fallback analysis performed - manual review recommended"],
            "key_vocabulary": ["Content processed with limited analysis"],
            "syllabus_tags": [f"GS - {category.replace('_', ' ').title()}"],
            "exam_angles": {
                "prelims_facts": ["Content available for review"],
                "mains_angles": ["Analysis pending service restoration"],
                "essay_themes": ["Topic identified for further study"]
            },
            "revision_priority": "low",
            "processing_status": "preliminary",
            "summary": f"Content categorized as {category}. Enhanced analysis temporarily unavailable - manual review recommended for complete UPSC preparation value.",
            "enhanced_content_html": "<p>Content pending enhancement. Basic information available for review.</p>"
        }

    # Legacy method for backward compatibility
    async def refine_content(self, content: str) -> Dict[str, Any]:
        """
        Legacy method that wraps enhanced_upsc_analysis
        Returns Groq-compatible structure wrapped as 'gemini_analysis'
        """
        analysis = await self.enhanced_upsc_analysis(content, "current_affairs")
        # Wrap in gemini_analysis key for flow.py compatibility
        return {"gemini_analysis": analysis}


def get_gemini_api_keys_from_env() -> List[str]:
    """
    Load Gemini API keys from environment variables

    Loads keys from environment in priority order:
    - GEMINI_API_KEY (primary, required)
    - GEMINI_API_KEY_2, GEMINI_API_KEY_3, ..., GEMINI_API_KEY_50 (additional, optional)

    Rate Limiting Context:
    - Gemini free tier: 5 requests/minute per key
    - Typical pipeline: 15-20 requests
    - Recommended: 5-23 keys for optimal performance

    Returns:
        List of Gemini API keys (minimum 1 required)

    Raises:
        ValueError: If no API keys found in environment
    """
    from ..core.config import get_settings

    settings = get_settings()
    env_keys = settings.all_gemini_api_keys

    if not env_keys:
        raise ValueError(
            "❌ No Gemini API keys found in environment!\n"
            "   Please set at least GEMINI_API_KEY environment variable.\n"
            "   For optimal performance (no rate limiting), add GEMINI_API_KEY_2 through GEMINI_API_KEY_23.\n"
            "   See backend/.env.example for template."
        )

    logger.info(f"✅ Loaded {len(env_keys)} Gemini API keys from environment")

    # Calculate and log rate limit capacity
    requests_per_min = len(env_keys) * 5  # 5 requests/min per key
    if len(env_keys) >= 20:
        logger.info(f"🚀 Excellent: {len(env_keys)} keys = {requests_per_min} requests/min (NO rate limits expected)")
    elif len(env_keys) >= 5:
        logger.info(f"✅ Good: {len(env_keys)} keys = {requests_per_min} requests/min (minimal rate limiting)")
    else:
        logger.warning(f"⚠️ Only {len(env_keys)} keys = {requests_per_min} requests/min")
        logger.warning(f"   ⚠️ Expect rate limiting! Pipeline may take 2-4 minutes instead of 60-90 seconds.")
        logger.warning(f"   💡 Recommendation: Add GEMINI_API_KEY_2, GEMINI_API_KEY_3, etc. for better performance")

    return env_keys


# Initialize service with environment-loaded keys
# Note: Keys are loaded at startup from environment variables
# No hardcoded keys for security (backend repo should be private)
direct_gemini_service = DirectGeminiService(get_gemini_api_keys_from_env())
