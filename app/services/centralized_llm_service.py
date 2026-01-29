import asyncio
import time
import json
import os
import logging
import litellm
from typing import Dict, Any, Optional
from pathlib import Path
from app.models.llm_schemas import *

# Enable official LiteLLM structured response validation
litellm.enable_json_schema_validation = True

logger = logging.getLogger(__name__)

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
                                "category": {"type": "string"}
                            },
                            "required": ["title", "content", "category"]
                        }
                    },
                    "extraction_confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "processing_notes": {"type": "string"}
                },
                "required": ["total_articles_found", "articles", "extraction_confidence", "processing_notes"]
            },
            "upsc_analysis": {
                "type": "object",
                "properties": {
                    "upsc_relevance": {"type": "number", "minimum": 1, "maximum": 100},
                    "relevant_papers": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["GS1", "GS2", "GS3", "GS4"]}
                    },
                    "key_topics": {"type": "array", "items": {"type": "string"}},
                    "importance_level": {
                        "type": "string", 
                        "enum": ["Low", "Medium", "High", "Critical"]
                    },
                    "question_potential": {
                        "type": "string",
                        "enum": ["Low", "Medium", "High"] 
                    },
                    "static_connections": {"type": "array", "items": {"type": "string"}},
                    "summary": {"type": "string"}
                },
                "required": ["upsc_relevance", "relevant_papers", "key_topics", "importance_level", "question_potential", "summary"]
            },
            "summarization": {
                "type": "object",
                "properties": {
                    "brief_summary": {"type": "string"},
                    "detailed_summary": {"type": "string"},
                    "key_points": {"type": "array", "items": {"type": "string"}},
                    "upsc_relevance": {"type": "string"},
                    "exam_tip": {"type": "string"}
                },
                "required": ["brief_summary", "detailed_summary", "key_points", "upsc_relevance", "exam_tip"]
            }
        }
        
    async def initialize_router(self):
        """Initialize LiteLLM router with multi-provider configuration"""
        try:
            # Set up litellm logging
            import os
            os.environ['LITELLM_LOG'] = 'DEBUG'
            
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
            config_path = Path(__file__).parent.parent.parent / "config" / "litellm_config.yaml"
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
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # Initialize router with YAML config
            self.router = Router(
                model_list=config.get('model_list', []),
                **config.get('router_settings', {})
            )
            
            logger.info(f"✅ LiteLLM router initialized from YAML config with {len(config.get('model_list', []))} models")
            logger.info(f"🔄 Round-robin strategy: {config.get('router_settings', {}).get('routing_strategy', 'default')}")
            
        except Exception as e:
            logger.error(f"❌ Failed to load YAML config: {e}")
            raise
    
    async def _initialize_basic_router(self):
        """Fallback basic router initialization - LATEST 2024-2025 MODELS"""
        # Updated model list with round-robin support (same model names)
        model_list = [
            # Round-robin entries for deepseek-r1-free
            {
                "model_name": "deepseek-r1-free",
                "litellm_params": {
                    "model": "openrouter/deepseek/deepseek-r1:free",
                    "api_key": os.environ.get("OPENROUTER_API_KEY_1"),
                    "api_base": "https://openrouter.ai/api/v1"
                }
            },
            {
                "model_name": "deepseek-r1-free",
                "litellm_params": {
                    "model": "openrouter/deepseek/deepseek-r1:free",
                    "api_key": os.environ.get("OPENROUTER_API_KEY_1"),  # Using same key for demo
                    "api_base": "https://openrouter.ai/api/v1"
                }
            },
            {
                "model_name": "openrouter_deepseek_distill_free_1",
                "litellm_params": {
                    "model": "openrouter/deepseek/deepseek-r1-distill-llama-70b:free",
                    "api_key": os.environ.get("OPENROUTER_API_KEY_1"),
                    "api_base": "https://openrouter.ai/api/v1"
                }
            },
            # Gemini 2.5 Flash (latest)
            {
                "model_name": "gemini_25_flash_1",
                "litellm_params": {
                    "model": "gemini/gemini-2.5-flash",
                    "api_key": os.environ.get("GEMINI_API_KEY_1")
                }
            },
            # DeepSeek V3.1 Direct
            {
                "model_name": "deepseek_chat_v31_1",
                "litellm_params": {
                    "model": "deepseek/deepseek-chat",
                    "api_key": os.environ.get("DEEPSEEK_API_KEY_1")
                }
            }
        ]
        
        from litellm import Router
        self.router = Router(
            model_list=model_list,
            routing_strategy='simple-shuffle',  # Round-robin distribution
            num_retries=3,
            timeout=30,
            allowed_fails=2
        )
        logger.info("✅ Basic LiteLLM router initialized with round-robin support:")
        logger.info(f"📊 Models configured: {len(model_list)}")
        logger.info("🔄 Round-robin strategy enabled")
        logger.info("🆓 Priority: FREE OpenRouter models")
        
    def _initialize_task_handlers(self) -> Dict[str, callable]:
        """Map task types to their specific handlers"""
        return {
            TaskType.CONTENT_EXTRACTION: self._handle_content_extraction,
            TaskType.UPSC_ANALYSIS: self._handle_upsc_analysis,
            TaskType.CATEGORIZATION: self._handle_categorization,
            TaskType.SUMMARIZATION: self._handle_summarization,
            TaskType.QUESTION_GENERATION: self._handle_question_generation,
            TaskType.ANSWER_EVALUATION: self._handle_answer_evaluation,
            TaskType.DEDUPLICATION: self._handle_deduplication
        }
    
    def _get_preferred_model(self, preference: ProviderPreference) -> str:
        """Select optimal model based on preference - YAML CONFIG MODELS"""
        # Exact model names from YAML configuration (round-robin enabled)
        available_models = [
            "deepseek-r1-free",        # OpenRouter DeepSeek R1 Free (5 keys)
            "llama-3.1-8b-free",       # OpenRouter Llama 3.1 8B Free (5 keys)
            "llama-3.3-70b",           # Groq Llama 3.3 70B (5 keys) 
            "llama-3.1-8b-instant",    # Groq Llama 3.1 8B Instant (5 keys)
            "cerebras-llama-3.1-8b",   # Cerebras Llama 3.1 8B (5 keys)
            "cerebras-llama-3.1-70b",  # Cerebras Llama 3.1 70B (5 keys)
            "deepseek-chat-v3.1",      # DeepSeek Direct V3.1 (5 keys)
            "deepseek-reasoner-v3.1",  # DeepSeek Reasoner (5 keys)
            "together-llama-4-scout",  # Together AI Llama 4 Scout (5 keys)
            "mistral-large-2411",      # Mistral Large 2411 (5 keys)
            "gemini-2.5-flash"         # Gemini 2.5 Flash (5 keys)
        ]
        
        model_preferences = {
            ProviderPreference.COST_OPTIMIZED: ["llama-3.3-70b", "mixtral-8x7b", "llama-3.1-8b-instant"],  # Use powerful models first
            ProviderPreference.SPEED_OPTIMIZED: ["llama-3.3-70b", "mixtral-8x7b", "llama-3.1-8b-instant"],  # 70B is still fast on Groq
            ProviderPreference.QUALITY_OPTIMIZED: ["llama-3.3-70b", "gemini-2.5-flash", "mixtral-8x7b"],   # Best quality first
            ProviderPreference.BALANCED: ["llama-3.3-70b", "gemini-2.5-flash", "mixtral-8x7b"]             # Powerful models for reliability
        }
        
        preferred_models = model_preferences.get(preference, ["llama-3.3-70b"])
        
        # Return first available model from preference list
        for model in preferred_models:
            if model in available_models:
                logger.info(f"🎯 Selected model: {model} (preference: {preference})")
                return model
        
        # Fallback to Groq model since we have working keys
        fallback_model = "llama-3.3-70b"
        logger.info(f"🔄 Using fallback model: {fallback_model}")
        return fallback_model
    
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
                fallback_used=result.get("fallback_used", False)
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
                error_message=str(e)
            )
    
    async def _handle_content_extraction(self, request: LLMRequest, model: str) -> Dict[str, Any]:
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
                    "enforce_validation": True
                },
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
            # Official structured response - already validated JSON object
            result_data = json.loads(response.choices[0].message.content)
            logger.info(f"✅ Official structured response received and validated")
            
            return {
                "provider_used": response.model,
                "model_used": response.model,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "estimated_cost": 0.0,  # Calculate based on provider
                "data": result_data
            }
            
        except Exception as e:
            logger.error(f"Content extraction failed: {e}")
            raise
    
    async def _handle_upsc_analysis(self, request: LLMRequest, model: str) -> Dict[str, Any]:
        """Handle UPSC relevance analysis and scoring"""
        
        prompt = f"""You are a UPSC subject expert analyzing content for civil services exam relevance.
        
        Content: {request.content}
        
        Analyze this content for UPSC Civil Services Examination relevance across:
        - General Studies Paper 1 (History, Geography, Culture)  
        - General Studies Paper 2 (Governance, Constitution, Politics)
        - General Studies Paper 3 (Economy, Environment, Technology, Security)
        - General Studies Paper 4 (Ethics, Integrity, Aptitude)
        
        Provide detailed analysis with scoring from 1-100 where:
        - 1-30: Low relevance (general news)
        - 31-60: Medium relevance (useful context)  
        - 61-85: High relevance (exam important)
        - 86-100: Critical relevance (must-know for exam)
        
        Current minimum threshold is 40+ for content to be saved.
        
        Return ONLY a valid JSON response (no extra text):
        {{
            "upsc_relevance": score,
            "relevant_papers": ["GS1", "GS2"],
            "key_topics": ["topic1", "topic2"],
            "importance_level": "High/Medium/Low/Critical",
            "question_potential": "High/Medium/Low",
            "static_connections": ["connection1"],
            "summary": "brief summary"
        }}
        
        {request.custom_instructions or ""}
        """
        
        try:
            # Simple completion without complex structured response format
            response = await self.router.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
            # Extract and parse response text
            response_text = response.choices[0].message.content
            if not response_text:
                raise ValueError("Empty response from LLM")
            
            # Parse JSON from response
            result_data = json.loads(response_text.strip())
            logger.info(f"✅ [UPSC Analysis] JSON response received and parsed successfully")
            
            return {
                "provider_used": response.model,
                "model_used": response.model,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "estimated_cost": 0.0,
                "data": result_data
            }
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}")
            logger.error(f"Response text: {response_text}")
            raise
        except Exception as e:
            logger.error(f"UPSC analysis failed: {e}")
            raise
    
    # Additional handler stubs for other task types
    async def _handle_categorization(self, request: LLMRequest, model: str) -> Dict[str, Any]:
        """Handle content categorization"""
        # Implementation placeholder
        return {"provider_used": model, "model_used": model, "tokens_used": 0, "estimated_cost": 0.0, "data": {}}
    
    async def _handle_summarization(self, request: LLMRequest, model: str) -> Dict[str, Any]:
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
            # Use official LiteLLM structured response with schema validation
            response = await self.router.acompletion(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={
                    "type": "json_object",
                    "response_schema": self.response_schemas["summarization"],
                    "enforce_validation": True
                },
                temperature=request.temperature,
                max_tokens=request.max_tokens
            )
            
            # Official structured response - already validated JSON object
            result_data = json.loads(response.choices[0].message.content)
            logger.info(f"✅ [Summarization] Official structured response received and validated")
            
            return {
                "provider_used": response.model,
                "model_used": response.model,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "estimated_cost": 0.0,
                "data": result_data
            }
            
        except Exception as e:
            logger.error(f"Summarization failed: {e}")
            raise
        
    async def _handle_question_generation(self, request: LLMRequest, model: str) -> Dict[str, Any]:
        """Handle UPSC question generation"""
        # Implementation placeholder
        return {"provider_used": model, "model_used": model, "tokens_used": 0, "estimated_cost": 0.0, "data": {}}
        
    async def _handle_answer_evaluation(self, request: LLMRequest, model: str) -> Dict[str, Any]:
        """Handle mains answer evaluation"""
        # Implementation placeholder
        return {"provider_used": model, "model_used": model, "tokens_used": 0, "estimated_cost": 0.0, "data": {}}
        
    async def _handle_deduplication(self, request: LLMRequest, model: str) -> Dict[str, Any]:
        """Handle content deduplication"""
        # Implementation placeholder
        return {"provider_used": model, "model_used": model, "tokens_used": 0, "estimated_cost": 0.0, "data": {}}

# Global service instance
llm_service = CentralizedLLMService()