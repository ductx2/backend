import asyncio
import time
import json
import os
import re
import logging
import litellm
from typing import Dict, Any, Optional
from pathlib import Path
from app.models.llm_schemas import *

# Disable strict JSON schema validation (causes issues with Gemini responses)
litellm.enable_json_schema_validation = False

logger = logging.getLogger(__name__)


def strip_markdown_json(text: str) -> str:
    """Strip markdown code blocks from JSON response.

    Gemini often returns JSON wrapped in ```json ... ``` blocks.
    This function extracts the raw JSON content.
    """
    if not text:
        return text

    text = text.strip()

    # Pattern to match ```json ... ``` or ``` ... ```
    pattern = r"^```(?:json)?\s*\n?(.*?)\n?```$"
    match = re.match(pattern, text, re.DOTALL)

    if match:
        return match.group(1).strip()

    return text


def validate_summarization_response(data: dict) -> tuple[bool, str]:
    """Validate that summarization response contains actual content, not schema definitions.

    This prevents corrupted articles where the LLM returns JSON schema definitions
    like {"type": "string"} instead of actual content.

    Returns:
        tuple[bool, str]: (is_valid, error_message)
    """
    # Check required fields exist
    required_fields = ["generated_title", "enhanced_content", "brief_summary"]
    for field in required_fields:
        if field not in data:
            return False, f"Missing required field: {field}"

    # Detect schema-like responses (LLM returned schema instead of content)
    schema_patterns = [
        '{"type"',
        '"type":"string"',
        '"type": "string"',
        '{"type":"',
    ]

    title = str(data.get("generated_title", ""))
    content = str(data.get("enhanced_content", ""))
    summary = str(data.get("brief_summary", ""))

    for pattern in schema_patterns:
        if pattern in title or title.strip().startswith("{"):
            return False, f"generated_title contains schema definition: {title[:100]}"
        if pattern in summary or summary.strip().startswith("{"):
            return False, f"brief_summary contains schema definition: {summary[:100]}"

    # Validate minimum content length
    if len(title.strip()) < 10:
        return False, f"generated_title too short: {len(title)} chars"
    if len(content.strip()) < 50:
        return False, f"enhanced_content too short: {len(content)} chars"
    if len(summary.strip()) < 20:
        return False, f"brief_summary too short: {len(summary)} chars"

    # Validate title doesn't look like JSON
    title_stripped = title.strip()
    if title_stripped.startswith("{") or title_stripped.startswith("["):
        return False, f"generated_title looks like JSON: {title[:100]}"

    # Validate content has some HTML structure (expected format)
    if "<" not in content and ">" not in content:
        # Content should have HTML tags - warn but don't reject
        logger.warning(f"enhanced_content has no HTML tags - may be malformed")

    return True, ""


class CentralizedLLMService:
    def __init__(self):
        self.api_key = None
        self.api_base = None
        self.model_name = None
        self.task_handlers = self._initialize_task_handlers()
        self.provider_stats = {}
        self.response_schemas = self._initialize_response_schemas()

    def _initialize_response_schemas(self) -> Dict[str, dict]:
        """Define official LiteLLM response schemas for each task type"""
        return {
            "content_extraction": {
                "type": "object",
                "properties": {
                    "total_articles_found": {"type": "number"},
                    "articles": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string"},
                                "content": {"type": "string"},
                                "category": {"type": "string"},
                            },
                            "required": ["title", "content", "category"],
                        },
                    },
                    "extraction_confidence": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 1,
                    },
                    "processing_notes": {"type": "string"},
                },
                "required": [
                    "total_articles_found",
                    "articles",
                    "extraction_confidence",
                    "processing_notes",
                ],
            },
            "upsc_analysis": {
                "type": "object",
                "properties": {
                    "upsc_relevance": {"type": "number", "minimum": 1, "maximum": 100},
                    "relevant_papers": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["GS1", "GS2", "GS3", "GS4"],
                        },
                    },
                    "key_topics": {"type": "array", "items": {"type": "string"}},
                    "importance_level": {
                        "type": "string",
                        "enum": ["Low", "Medium", "High", "Critical"],
                    },
                    "question_potential": {
                        "type": "string",
                        "enum": ["Low", "Medium", "High"],
                    },
                    "static_connections": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "summary": {"type": "string"},
                },
                "required": [
                    "upsc_relevance",
                    "relevant_papers",
                    "key_topics",
                    "importance_level",
                    "question_potential",
                    "summary",
                ],
            },
            "summarization": {
                "type": "object",
                "properties": {
                    "generated_title": {"type": "string"},
                    "enhanced_content": {"type": "string"},
                    "brief_summary": {"type": "string"},
                    "detailed_summary": {"type": "string"},
                    "key_points": {"type": "array", "items": {"type": "string"}},
                    "upsc_relevance": {"type": "string"},
                    "exam_tip": {"type": "string"},
                },
                "required": [
                    "generated_title",
                    "enhanced_content",
                    "brief_summary",
                    "detailed_summary",
                    "key_points",
                    "upsc_relevance",
                    "exam_tip",
                ],
            },
        }

    async def initialize_router(self):
        """Initialize LiteLLM router with multi-provider configuration"""
        try:
            # Set up litellm logging
            os.environ["LITELLM_LOG"] = "DEBUG"

            # Load environment variables from .env.llm file
            env_file = Path(__file__).parent.parent.parent / ".env.llm"
            if env_file.exists():
                from dotenv import load_dotenv

                load_dotenv(env_file)
                logger.info(f"✅ Loaded environment variables from {env_file}")
            else:
                logger.debug(f"❌ .env.llm file not found at {env_file}")

            # Also load from main .env file
            main_env_file = Path(__file__).parent.parent.parent / ".env"
            if main_env_file.exists():
                from dotenv import load_dotenv

                load_dotenv(main_env_file)
                logger.info(f"✅ Loaded environment variables from {main_env_file}")

            # Use basic router directly (more reliable on Render)
            # YAML config env var resolution was unreliable
            logger.info("🔧 Initializing basic router with Vercel AI Gateway")
            await self._initialize_basic_router()

        except Exception as e:
            logger.error(f"Failed to initialize LiteLLM router: {e}")
            await self._initialize_basic_router()

    async def _initialize_yaml_router(self, config_path: Path):
        """Initialize router from YAML configuration with round-robin support"""
        try:
            from litellm import Router
            import yaml

            # Load YAML configuration
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)

            # Resolve environment variables in model_list
            model_list = config.get("model_list", [])
            for model in model_list:
                litellm_params = model.get("litellm_params", {})
                api_key = litellm_params.get("api_key", "")
                # Resolve os.environ/VARNAME syntax
                if isinstance(api_key, str) and api_key.startswith("os.environ/"):
                    env_var = api_key.replace("os.environ/", "")
                    resolved_key = os.environ.get(env_var)
                    if resolved_key:
                        litellm_params["api_key"] = resolved_key
                        logger.info(f"✅ Resolved API key from {env_var}")
                    else:
                        logger.warning(f"⚠️ Environment variable {env_var} not found")

            # Initialize router with resolved config
            self.router = Router(
                model_list=model_list,
                **config.get("router_settings", {}),
            )

            logger.info(
                f"✅ LiteLLM router initialized from YAML config with {len(model_list)} models"
            )
            logger.info(
                f"🔄 Round-robin strategy: {config.get('router_settings', {}).get('routing_strategy', 'default')}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to load YAML config: {e}")
            raise

    async def _initialize_basic_router(self):
        """Basic router initialization - VERCEL AI GATEWAY + GPT-OSS-120B

        Using Vercel AI Gateway with GPT-OSS-120B (Cerebras):
        - Ultra-fast inference: 3000 tokens/sec
        - Full structured output support (JSON)
        - Pipeline will complete in ~2-3 minutes
        """
        from litellm import Router

        # Check for API key with detailed logging
        api_key = os.environ.get("VERCEL_AI_GATEWAY_API_KEY")
        if api_key:
            logger.info(f"✅ Found VERCEL_AI_GATEWAY_API_KEY (length: {len(api_key)})")
        else:
            api_key = os.environ.get("AI_GATEWAY_API_KEY")
            if api_key:
                logger.info(f"✅ Found AI_GATEWAY_API_KEY (length: {len(api_key)})")
            else:
                # List available env vars for debugging (without values)
                llm_related_vars = [
                    k
                    for k in os.environ.keys()
                    if "KEY" in k.upper()
                    or "API" in k.upper()
                    or "GATEWAY" in k.upper()
                ]
                logger.error(
                    f"❌ No API key found. Available related env vars: {llm_related_vars}"
                )
                raise ValueError(
                    "VERCEL_AI_GATEWAY_API_KEY or AI_GATEWAY_API_KEY not found in environment"
                )

        # Store API key for direct calls (bypassing Router health checks)
        self.api_key = api_key
        self.api_base = "https://ai-gateway.vercel.sh/v1"
        self.model_name = "openai/gpt-oss-120b"

        logger.info(
            f"✅ LiteLLM initialized with Vercel AI Gateway + GPT-OSS-120B (direct mode)"
        )

    async def _direct_completion(self, **kwargs):
        """Direct litellm completion call bypassing Router health checks"""
        import litellm

        # Override model params with our config
        kwargs["model"] = self.model_name
        kwargs["api_key"] = self.api_key
        kwargs["api_base"] = self.api_base

        logger.info(f"🔄 Direct LLM call to {self.model_name}")
        return await litellm.acompletion(**kwargs)

    def _initialize_task_handlers(self) -> Dict[str, callable]:
        """Map task types to their specific handlers"""
        return {
            TaskType.CONTENT_EXTRACTION: self._handle_content_extraction,
            TaskType.UPSC_ANALYSIS: self._handle_upsc_analysis,
            TaskType.CATEGORIZATION: self._handle_categorization,
            TaskType.SUMMARIZATION: self._handle_summarization,
            TaskType.QUESTION_GENERATION: self._handle_question_generation,
            TaskType.ANSWER_EVALUATION: self._handle_answer_evaluation,
            TaskType.DEDUPLICATION: self._handle_deduplication,
            TaskType.KNOWLEDGE_CARD: self._handle_knowledge_card,
            TaskType.UPSC_BATCH_ANALYSIS: self._handle_upsc_batch_analysis,
        }

    def _get_preferred_model(self, preference: ProviderPreference) -> str:
        model = "gpt-oss-120b"
        logger.info(
            f"🎯 Selected model: {model} (GPT-OSS-120B via Vercel AI Gateway - 3000 tok/s Cerebras) (preference: {preference})"
        )
        return model

    async def process_request(self, request: LLMRequest) -> LLMResponse:
        """Main processing function - handles all LLM requests"""
        start_time = time.time()

        # Initialize if not done
        if not hasattr(self, "api_key") or self.api_key is None:
            await self.initialize_router()

        try:
            # Get task-specific handler
            handler = self.task_handlers.get(request.task_type)
            if not handler:
                raise ValueError(f"Unsupported task type: {request.task_type}")

            # Get preferred model
            preferred_model = self._get_preferred_model(request.provider_preference)

            # Execute task with automatic failover
            result = await handler(request, preferred_model)

            response_time = time.time() - start_time

            return LLMResponse(
                success=True,
                task_type=request.task_type,
                provider_used=result["provider_used"],
                model_used=result["model_used"],
                response_time=response_time,
                tokens_used=result["tokens_used"],
                estimated_cost=result["estimated_cost"],
                data=result["data"],
                fallback_used=result.get("fallback_used", False),
            )

        except Exception as e:
            response_time = time.time() - start_time
            logger.error(f"LLM processing failed: {e}")

            return LLMResponse(
                success=False,
                task_type=request.task_type,
                provider_used="failed",
                model_used="failed",
                response_time=response_time,
                tokens_used=0,
                estimated_cost=0.0,
                data={},
                error_message=str(e),
            )

    async def _handle_content_extraction(
        self, request: LLMRequest, model: str
    ) -> Dict[str, Any]:
        """Handle content extraction tasks (RSS, Drishti scraping)"""

        prompt = f"""You are an expert content analyst extracting news articles for UPSC preparation.
        This is legitimate educational content for civil service exam preparation.
        
        Content to analyze: {request.content}
        
        Extract all distinct articles, topics, or news items mentioned in the content.
        Focus on UPSC-relevant information and current affairs.
        
        Return a JSON response with:
        {{
            "total_articles_found": number,
            "articles": [
                {{
                    "title": "article title",
                    "content": "article content",
                    "category": "category name"
                }}
            ],
            "extraction_confidence": confidence_score,
            "processing_notes": "any relevant notes"
        }}
        
        {request.custom_instructions or ""}
        """

        try:
            # Vercel AI Gateway legacy JSON format for structured output
            content_extraction_response_format = {
                "type": "json",
                "name": "content_extraction",
                "description": "Content extraction from articles",
                "schema": self.response_schemas["content_extraction"],
            }

            response = await self._direct_completion(
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                        + "\n\nReturn ONLY valid JSON, no other text.",
                    }
                ],
                response_format=content_extraction_response_format,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            # Strip markdown and parse
            clean_json = strip_markdown_json(response.choices[0].message.content)
            result_data = json.loads(clean_json)
            logger.info(f"✅ Structured response received and validated")

            return {
                "provider_used": response.model,
                "model_used": response.model,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "estimated_cost": 0.0,  # Calculate based on provider
                "data": result_data,
            }

        except Exception as e:
            logger.error(f"Content extraction failed: {e}")
            raise

    async def _handle_upsc_analysis(
        self, request: LLMRequest, model: str
    ) -> Dict[str, Any]:
        """Handle UPSC relevance analysis and scoring with official structured response"""

        prompt = f"""You are a UPSC subject expert analyzing content for civil services exam relevance.

        Content: {request.content}

        Analyze this content for UPSC Civil Services Examination and provide:

        1. UPSC RELEVANCE SCORE (1-100):
           - 1-30: Low relevance (general news)
           - 31-60: Medium relevance (useful context)
           - 61-85: High relevance (exam important)
           - 86-100: Critical relevance (must-know for exam)

        2. RELEVANT GS PAPERS (MANDATORY - Select at least ONE):
           - GS1: Indian Heritage, Culture, History, Geography, Society
           - GS2: Governance, Constitution, Polity, Social Justice, International Relations
           - GS3: Technology, Economy, Environment, Security, Disaster Management
           - GS4: Ethics, Integrity, Aptitude

           IMPORTANT: You MUST select at least one GS paper. Return them as an array like ["GS2", "GS3"].

        3. KEY TOPICS (MANDATORY - Extract 3-7 specific topics):
           Extract the main subjects/themes from this content. Examples:
           - For politics: ["Parliament", "Elections", "Supreme Court"]
           - For economy: ["GDP", "Inflation", "Trade Policy"]
           - For environment: ["Climate Change", "Renewable Energy", "Pollution"]

           IMPORTANT: You MUST extract at least 3 key topics as an array of strings.

        4. IMPORTANCE LEVEL: Low, Medium, High, or Critical

        5. QUESTION POTENTIAL: Low, Medium, or High

        6. SUMMARY: Brief 2-3 sentence summary of the content

        7. CATEGORY: Select the BEST category for this article:
           - politics (governance, elections, constitutional matters)
           - economy (finance, trade, GDP, inflation, budget)
           - international (foreign relations, bilateral talks, global affairs)
           - science (technology, space, research, innovation)
           - environment (climate, pollution, wildlife, ecology)
           - society (social issues, education, health, culture)
           - defence (military, security, border issues)
           - schemes (government schemes, welfare programs)

        8. KEY VOCABULARY (MANDATORY - Extract 3-5 important terms):
           Extract technical terms, acts, organizations, or concepts that a UPSC aspirant should know.
           For each term, provide a brief definition explaining its relevance to UPSC.
           Format: array of objects with "term" and "definition" keys.
           Example: [{{"term": "Article 370", "definition": "Constitutional provision granting special status to J&K. GS2: Polity."}}]

        {request.custom_instructions or ""}
        """

        # Official Google structured response schema
        upsc_analysis_schema = {
            "type": "object",
            "properties": {
                "upsc_relevance": {"type": "integer", "minimum": 1, "maximum": 100},
                "relevant_papers": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["GS1", "GS2", "GS3", "GS4"]},
                    "minItems": 1,  # MUST return at least 1 GS paper
                },
                "key_topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 3,  # MUST return at least 3 key topics
                },
                "importance_level": {
                    "type": "string",
                    "enum": ["Low", "Medium", "High", "Critical"],
                },
                "question_potential": {
                    "type": "string",
                    "enum": ["Low", "Medium", "High"],
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "politics",
                        "economy",
                        "international",
                        "science",
                        "environment",
                        "society",
                        "defence",
                        "schemes",
                    ],
                },
                "key_vocabulary": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "term": {"type": "string"},
                            "definition": {"type": "string"},
                        },
                        "required": ["term", "definition"],
                    },
                    "minItems": 3,  # MUST return at least 3 key vocabulary terms
                },
                "static_connections": {"type": "array", "items": {"type": "string"}},
                "summary": {"type": "string"},
            },
            "required": [
                "upsc_relevance",
                "relevant_papers",
                "key_topics",
                "importance_level",
                "question_potential",
                "category",
                "key_vocabulary",
                "summary",
            ],
        }

        # Vercel AI Gateway legacy JSON schema for structured output
        upsc_response_format = {
            "type": "json",
            "name": "upsc_analysis",
            "description": "UPSC Civil Services exam relevance analysis",
            "schema": upsc_analysis_schema,
        }

        try:
            # Use Vercel AI Gateway's legacy JSON format for structured output
            response = await self._direct_completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format=upsc_response_format,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            # Parse structured response (should be clean JSON)
            response_text = response.choices[0].message.content
            if not response_text:
                raise ValueError("Empty response from LLM")

            # Strip markdown if present (fallback) and parse
            clean_json = strip_markdown_json(response_text)
            result_data = json.loads(clean_json)
            logger.info(
                f"✅ [UPSC Analysis] Structured response received from {response.model}"
            )

            return {
                "provider_used": response.model,
                "model_used": response.model,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "estimated_cost": 0.0,
                "data": result_data,
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Response text: {response_text}")
            raise
        except Exception as e:
            logger.error(f"UPSC analysis failed: {e}")
            raise


    async def _handle_knowledge_card(
        self, request: LLMRequest, model: str
    ) -> Dict[str, Any]:
        """Handle UPSC knowledge card generation (Pass 2).

        Produces the 4 LLM-generated layers consumed by run_pass2():
          - headline_layer   : punchy exam-ready headline
          - facts_layer      : bullet facts for quick revision
          - context_layer    : deeper analytical context
          - mains_angle_layer: Mains answer-writing angle
        connections_layer is assembled by Python (NOT by this handler).
        """

        prompt = f"""You are an elite UPSC Mains content strategist.
Your task is to create a high-quality knowledge card for a current affairs article.

{request.content}

{request.custom_instructions or ""}

Generate a 4-layer knowledge card optimised for UPSC Civil Services (Prelims + Mains):

LAYER 1 – HEADLINE (headline_layer):
  A single, punchy sentence (≤15 words) that captures the exam-relevant essence.
  Focus on WHY it matters for UPSC, not just what happened.

LAYER 2 – KEY FACTS (facts_layer):
  5–7 crisp bullet facts a student must memorise.
  Each fact must be self-contained, specific, and exam-relevant.
  Include numbers, dates, organisations, acts, or constitutional articles where applicable.

LAYER 3 – CONTEXT & ANALYSIS (context_layer):
  2–3 sentences of background context explaining the issue in the UPSC syllabus framework.
  Connect to broader themes (governance, polity, economy, environment, etc.).

LAYER 4 – MAINS ANGLE (mains_angle_layer):
  1–2 sentences framing this topic as a Mains answer.
  Suggest the GS paper and a likely question direction.

LAYER 5 – PRACTICE QUESTIONS (practice_questions):
  Exactly 3 UPSC practice questions. Mix types: one Prelims MCQ, one Mains Short Answer, one Mains Essay or Case Study.
  Each must have: title (the question text), type, gsPaper, difficulty, marks, topic (syllabus topic), explanation (brief answer hint), keywords (array of strings).
"""

        knowledge_card_schema = {
            "type": "object",
            "properties": {
                "headline_layer": {"type": "string"},
                "facts_layer": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 5,
                },
                "context_layer": {"type": "string"},
                "mains_angle_layer": {"type": "string"},
                "practice_questions": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title":       {"type": "string"},
                            "type":        {"type": "string", "enum": ["Prelims MCQ", "Mains Short Answer", "Mains Essay", "Case Study"]},
                            "gsPaper":     {"type": "string", "enum": ["GS1", "GS2", "GS3", "GS4", "Prelims"]},
                            "difficulty":  {"type": "string", "enum": ["Easy", "Medium", "Hard"]},
                            "marks":       {"type": "integer"},
                            "topic":       {"type": "string"},
                            "explanation": {"type": "string"},
                            "keywords":    {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["title", "type", "gsPaper", "difficulty", "marks", "topic", "keywords"]
                    },
                    "minItems": 3,
                    "maxItems": 3
                },
            },
            "required": [
                "headline_layer",
                "facts_layer",
                "context_layer",
                "mains_angle_layer",
                "practice_questions",
            ],
        }

        knowledge_card_response_format = {
            "type": "json",
            "name": "knowledge_card",
            "description": "5-layer UPSC knowledge card for current affairs article",
            "schema": knowledge_card_schema,
        }

        try:
            response = await self._direct_completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format=knowledge_card_response_format,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
            response_text = response.choices[0].message.content
            if not response_text:
                raise ValueError("Empty response from LLM")
            clean_json = strip_markdown_json(response_text)
            result_data = json.loads(clean_json)
            logger.info(
                f"✅ [Knowledge Card] Structured response received from {response.model}"
            )

            return {
                "provider_used": response.model,
                "model_used": response.model,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "estimated_cost": 0.0,
                "data": result_data,
            }
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed for knowledge card: {e}")
            logger.error(f"Response text: {response_text}")
            raise
        except Exception as e:
            logger.error(f"Knowledge card generation failed: {e}")
            raise

    async def _handle_upsc_batch_analysis(
        self, request: LLMRequest, model: str
    ) -> Dict[str, Any]:
        """Handle batch UPSC relevance scoring of multiple articles in one LLM call.
        
        request.content: JSON string containing {"articles": [{"article_id", "title", "content"}, ...]}
        Returns: {"provider_used", "model_used", "tokens_used", "estimated_cost", "data": {"articles": [...]}}
        """

        prompt = f"""You are a UPSC Civil Services expert scoring multiple articles for exam relevance.

Batch of articles to score:
{request.content}

For EACH article in the batch, follow this reasoning chain:
1. Identify which UPSC syllabus topic it maps to (e.g., "GS2/Polity/Parliament", "GS3/Economy/Monetary Policy")
2. Assess: Could this appear as a UPSC Prelims fact, Mains question, or Current Affairs question?
3. Score 1-100 based on: syllabus relevance (40%), question potential (30%), factual density (30%)

Scoring guide:
- 1-30: Low relevance (general news, not in UPSC syllabus)
- 31-60: Medium relevance (useful context, may appear as passing reference)
- 61-85: High relevance (directly in UPSC syllabus, exam important)
- 86-100: Critical relevance (must-know, high chance of Prelims/Mains question)

For each article, return:
- article_id: the exact article_id provided
- upsc_relevance: integer 1-100
- relevant_papers: which GS papers (at least one of GS1, GS2, GS3, GS4)
- key_topics: 3-7 specific UPSC-relevant topics extracted from the article
- importance_level: Low / Medium / High / Critical
- question_potential: Low / Medium / High
- category: politics / economy / international / science / environment / society / defence / schemes
- summary: 1-2 sentence summary of the article's UPSC relevance

{request.custom_instructions or ""}"""

        # Batch analysis schema — wraps array in object for GPT-OSS-120B compatibility
        upsc_batch_schema = {
            "type": "object",
            "properties": {
                "articles": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "article_id": {"type": "string"},
                            "upsc_relevance": {"type": "integer", "minimum": 1, "maximum": 100},
                            "relevant_papers": {
                                "type": "array",
                                "items": {"type": "string", "enum": ["GS1", "GS2", "GS3", "GS4"]},
                                "minItems": 1,
                            },
                            "key_topics": {
                                "type": "array",
                                "items": {"type": "string"},
                                "minItems": 3,
                            },
                            "importance_level": {
                                "type": "string",
                                "enum": ["Low", "Medium", "High", "Critical"],
                            },
                            "question_potential": {
                                "type": "string",
                                "enum": ["Low", "Medium", "High"],
                            },
                            "category": {
                                "type": "string",
                                "enum": [
                                    "politics",
                                    "economy",
                                    "international",
                                    "science",
                                    "environment",
                                    "society",
                                    "defence",
                                    "schemes",
                                ],
                            },
                            "summary": {"type": "string"},
                        },
                        "required": [
                            "article_id",
                            "upsc_relevance",
                            "relevant_papers",
                            "key_topics",
                            "importance_level",
                            "question_potential",
                            "category",
                            "summary",
                        ],
                    },
                }
            },
            "required": ["articles"],
        }

        batch_response_format = {
            "type": "json",
            "name": "upsc_batch_analysis",
            "description": "Batch UPSC relevance scoring of multiple articles",
            "schema": upsc_batch_schema,
        }

        try:
            response = await self._direct_completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format=batch_response_format,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            response_text = response.choices[0].message.content
            if not response_text:
                raise ValueError("Empty response from LLM")

            clean_json = strip_markdown_json(response_text)
            result_data = json.loads(clean_json)
            logger.info(
                f"✅ [Batch Analysis] Scored {len(result_data.get('articles', []))} articles from {response.model}"
            )

            return {
                "provider_used": response.model,
                "model_used": response.model,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "estimated_cost": 0.0,
                "data": result_data,
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed for batch analysis: {e}")
            logger.error(f"Response text: {response_text}")
            # Recovery: extract "articles" array directly when LLM echoes schema preamble
            import re as _re
            _match = _re.search(r'"articles"\s*:\s*(\[.*\])\s*[,}]', response_text, _re.DOTALL)
            if _match:
                try:
                    _articles_list = json.loads(_match.group(1))
                    logger.info(f"[Batch Analysis] Recovered {len(_articles_list)} articles from malformed JSON")
                    return {
                        "provider_used": response.model,
                        "model_used": response.model,
                        "tokens_used": response.usage.total_tokens if response.usage else 0,
                        "estimated_cost": 0.0,
                        "data": {"articles": _articles_list},
                    }
                except Exception:
                    pass
            raise
        except Exception as e:
            logger.error(f"Batch UPSC analysis failed: {e}")
            raise

    # Additional handler stubs for other task types
    async def _handle_categorization(
        self, request: LLMRequest, model: str
    ) -> Dict[str, Any]:
        """Handle content categorization"""
        # Implementation placeholder
        return {
            "provider_used": model,
            "model_used": model,
            "tokens_used": 0,
            "estimated_cost": 0.0,
            "data": {},
        }

    async def _handle_summarization(
        self, request: LLMRequest, model: str
    ) -> Dict[str, Any]:
        """Handle content summarization and key points extraction with HTML formatting"""

        prompt = f"""You are an expert content summarizer focused on UPSC Civil Services preparation.

Content to analyze:
{request.content}

Create a comprehensive, well-structured article optimized for UPSC aspirants.

CRITICAL: You MUST return a JSON response with the following structure:

{{
    "generated_title": "Compelling, specific title (50-100 chars) that captures the key point for UPSC aspirants",
    "enhanced_content": "HTML-formatted article content (see format below)",
    "brief_summary": "2-3 sentence overview",
    "detailed_summary": "Comprehensive 1-2 paragraph summary for UPSC preparation",
    "key_points": ["key point 1", "key point 2", "key point 3", "key point 4", "key point 5"],
    "upsc_relevance": "How this topic relates to UPSC syllabus (GS papers, optional subjects)",
    "exam_tip": "Strategic tip for exam preparation"
}}

ENHANCED_CONTENT FORMAT (HTML):
The "enhanced_content" field MUST be properly formatted HTML with the following structure:

<h2>Overview</h2>
<p>Opening paragraph with <strong>key entities</strong>, <strong>dates</strong>, and <strong>important terms</strong> highlighted using strong tags. Provide context and significance.</p>

<h3>Key Developments</h3>
<ul>
  <li><strong>Development 1:</strong> Description of the first key development or fact.</li>
  <li><strong>Development 2:</strong> Description of the second key development or fact.</li>
  <li><strong>Development 3:</strong> Description of the third key development or fact.</li>
</ul>

<h3>Important Facts</h3>
<ul>
  <li><strong>Fact 1:</strong> Important statistic, date, or data point.</li>
  <li><strong>Fact 2:</strong> Another significant fact relevant for UPSC.</li>
</ul>

<h3>UPSC Relevance</h3>
<p>Explain how this topic connects to the UPSC syllabus, which GS papers it relates to, and potential question angles.</p>

<h3>Way Forward</h3>
<p>Conclude with implications, future outlook, or policy recommendations if applicable.</p>

IMPORTANT RULES:
1. Use <strong> tags to highlight: names of people, organizations, policies, acts, dates, statistics
2. Use proper HTML hierarchy: h2 for main sections, h3 for subsections
3. Use <ul> and <li> for bullet points
4. Use <p> tags for paragraphs
5. Make content factual, comprehensive, and UPSC exam-focused
6. Include specific facts, dates, figures from the source content
7. The enhanced_content should be 300-600 words of well-structured HTML

Title requirements:
- Specific and informative (not generic)
- Focus on the key development/policy/issue
- Active language, avoid vague terms
- 50-100 characters
- UPSC exam relevant

{request.custom_instructions or ""}
        """

        try:
            # Vercel AI Gateway legacy JSON format for structured output
            summarization_response_format = {
                "type": "json",
                "name": "content_summarization",
                "description": "UPSC content summarization with HTML formatting",
                "schema": self.response_schemas["summarization"],
            }

            response = await self._direct_completion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format=summarization_response_format,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            # Parse structured response - strip markdown and parse
            clean_json = strip_markdown_json(response.choices[0].message.content)
            result_data = json.loads(clean_json)

            # Validate response contains actual content, not schema definitions
            is_valid, error_msg = validate_summarization_response(result_data)
            if not is_valid:
                logger.error(
                    f"[REJECTED] Summarization response failed validation: {error_msg}"
                )
                logger.error(f"[REJECTED] Raw response: {clean_json[:500]}")
                raise ValueError(f"LLM returned invalid content: {error_msg}")

            logger.info(
                f"[OK] [Summarization] Validated response received from {response.model}"
            )

            return {
                "provider_used": response.model,
                "model_used": response.model,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "estimated_cost": 0.0,
                "data": result_data,
            }

        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            raise

    async def _handle_question_generation(
        self, request: LLMRequest, model: str
    ) -> Dict[str, Any]:
        """Handle UPSC question generation"""
        # Implementation placeholder
        return {
            "provider_used": model,
            "model_used": model,
            "tokens_used": 0,
            "estimated_cost": 0.0,
            "data": {},
        }

    async def _handle_answer_evaluation(
        self, request: LLMRequest, model: str
    ) -> Dict[str, Any]:
        """Handle mains answer evaluation"""
        # Implementation placeholder
        return {
            "provider_used": model,
            "model_used": model,
            "tokens_used": 0,
            "estimated_cost": 0.0,
            "data": {},
        }

    async def _handle_deduplication(
        self, request: LLMRequest, model: str
    ) -> Dict[str, Any]:
        """Handle content deduplication"""
        # Implementation placeholder
        return {
            "provider_used": model,
            "model_used": model,
            "tokens_used": 0,
            "estimated_cost": 0.0,
            "data": {},
        }


# Global service instance
llm_service = CentralizedLLMService()
