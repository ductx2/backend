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


class CentralizedLLMService:
    def __init__(self):
        self.router = None
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
                    "brief_summary": {"type": "string"},
                    "detailed_summary": {"type": "string"},
                    "key_points": {"type": "array", "items": {"type": "string"}},
                    "upsc_relevance": {"type": "string"},
                    "exam_tip": {"type": "string"},
                },
                "required": [
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
            import os

            os.environ["LITELLM_LOG"] = "DEBUG"

            # Load environment variables from .env.llm file
            env_file = Path(__file__).parent.parent.parent / ".env.llm"
            if env_file.exists():
                from dotenv import load_dotenv

                load_dotenv(env_file)
                logger.info(f"✅ Loaded environment variables from {env_file}")
            else:
                logger.warning(f"❌ .env.llm file not found at {env_file}")

            # Also load from main .env file
            main_env_file = Path(__file__).parent.parent.parent / ".env"
            if main_env_file.exists():
                from dotenv import load_dotenv

                load_dotenv(main_env_file)
                logger.info(f"✅ Loaded environment variables from {main_env_file}")

            # Try to load from YAML configuration first
            config_path = (
                Path(__file__).parent.parent.parent / "config" / "litellm_config.yaml"
            )
            if config_path.exists():
                logger.info(f"📁 Found YAML config at {config_path}")
                await self._initialize_yaml_router(config_path)
            else:
                logger.warning("YAML config not found, using basic router")
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

            # Initialize router with YAML config
            self.router = Router(
                model_list=config.get("model_list", []),
                **config.get("router_settings", {}),
            )

            logger.info(
                f"✅ LiteLLM router initialized from YAML config with {len(config.get('model_list', []))} models"
            )
            logger.info(
                f"🔄 Round-robin strategy: {config.get('router_settings', {}).get('routing_strategy', 'default')}"
            )

        except Exception as e:
            logger.error(f"❌ Failed to load YAML config: {e}")
            raise

    async def _initialize_basic_router(self):
        """Fallback basic router initialization - VERCEL AI GATEWAY + DEEPSEEK V3.2

        Using Vercel AI Gateway with DeepSeek V3.2:
        - $0.27/M input, $0.40/M output (21x cheaper than Gemini)
        - Full structured output support (JSON Schema)
        - Built-in fallbacks and reliability
        """
        model_list = []

        # Use Vercel AI Gateway with DeepSeek V3.2
        api_key = os.environ.get("VERCEL_AI_GATEWAY_API_KEY")
        if api_key:
            model_list.append(
                {
                    "model_name": "deepseek-v3.2",
                    "litellm_params": {
                        "model": "openai/deepseek-v3.2",
                        "api_key": api_key,
                        "base_url": "https://ai-gateway.vercel.sh/v1",
                    },
                }
            )
        else:
            raise ValueError("VERCEL_AI_GATEWAY_API_KEY not found in environment")

        from litellm import Router

        self.router = Router(
            model_list=model_list,
            routing_strategy="simple-shuffle",
            num_retries=3,
            timeout=60,
            allowed_fails=2,
        )
        logger.info(
            f"✅ Basic LiteLLM router initialized with Vercel AI Gateway + DeepSeek V3.2"
        )

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
        }

    def _get_preferred_model(self, preference: ProviderPreference) -> str:
        """Select optimal model based on preference - DEEPSEEK V3.2 VIA VERCEL AI GATEWAY

        Using DeepSeek V3.2 via Vercel AI Gateway:
        - Cost: $0.27/M input, $0.40/M output
        - 21x cheaper than Gemini 2.5 Flash
        - Full structured output support
        """
        model = "deepseek-v3.2"
        logger.info(f"🎯 Selected model: {model} (preference: {preference})")
        return model

    async def process_request(self, request: LLMRequest) -> LLMResponse:
        """Main processing function - handles all LLM requests"""
        start_time = time.time()

        # Initialize router if not done
        if self.router is None:
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
            # Use official LiteLLM structured response with schema validation
            response = await self.router.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_object",
                    "response_schema": self.response_schemas["content_extraction"],
                    "enforce_validation": True,
                },
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            # Official structured response - strip markdown and parse
            clean_json = strip_markdown_json(response.choices[0].message.content)
            result_data = json.loads(clean_json)
            logger.info(f"✅ Official structured response received and validated")

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
                "static_connections": {"type": "array", "items": {"type": "string"}},
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
        }

        try:
            # Use official structured response format for Gemini
            response = await self.router.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "upsc_analysis",
                        "schema": upsc_analysis_schema,
                        "strict": True,
                    },
                },
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
        """Handle content summarization and key points extraction"""

        prompt = f"""You are an expert content summarizer focused on UPSC preparation.
        
        Content: {request.content}
        
        Create a comprehensive summary optimized for UPSC Civil Services preparation:
        
        Return JSON response:
        {{
            "generated_title": "Compelling, specific title (50-100 chars) that captures the key point for UPSC aspirants",
            "brief_summary": "2-3 sentence overview",
            "detailed_summary": "comprehensive summary for UPSC preparation", 
            "key_points": ["point1", "point2", "point3"],
            "upsc_relevance": "How this relates to UPSC syllabus",
            "exam_tip": "Strategic tip for exam preparation"
        }}
        
        Title requirements:
        - Make it specific and informative (not generic)
        - Focus on the key development/policy/issue
        - Use active language and avoid vague terms
        - Keep it between 50-100 characters
        - Make it UPSC exam relevant
        
        {request.custom_instructions or ""}
        """

        try:
            # Use official structured response format (OpenAI-compatible)
            response = await self.router.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "content_summarization",
                        "schema": self.response_schemas["summarization"],
                        "strict": True,
                    },
                },
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )

            # Official structured response - strip markdown and parse
            clean_json = strip_markdown_json(response.choices[0].message.content)
            result_data = json.loads(clean_json)
            logger.info(
                f"[OK] [Summarization] Official structured response received and validated"
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
