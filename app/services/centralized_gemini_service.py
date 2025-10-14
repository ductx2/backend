"""
Centralized Gemini Service - Drop-in Replacement for LiteLLM
Production-ready centralized AI service using Google Gemini 2.5 Flash

This service maintains the EXACT same API interface as the LiteLLM version
while using our enhanced Gemini rotation service with 22 API keys.

Features:
- 100% interface compatibility with existing LiteLLM service
- 22 API key rotation with intelligent failover
- Enhanced reliability and performance
- Structured JSON responses using Gemini responseSchema
- Task-specific optimizations

Production Service: Standard import pattern for all AI operations
Usage: from app.services.centralized_gemini_service import gemini_service as llm_service

Created: 2025-09-01
"""

import asyncio
import time
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime

# Import existing interface models (EXACT same interface)
from ..models.llm_schemas import LLMRequest, LLMResponse, TaskType, ProviderPreference

# Import our Gemini components
from .gemini_rotation_service import get_gemini_rotation_service
from .gemini_task_handlers import get_task_handlers

logger = logging.getLogger(__name__)

class CentralizedGeminiService:
    """
    Drop-in replacement for CentralizedLLMService using Gemini rotation
    
    Maintains EXACT same interface as the original LiteLLM service while
    providing enhanced reliability through 22 API key rotation.
    """
    
    def __init__(self):
        """Initialize the centralized Gemini service"""
        self.rotation_service = get_gemini_rotation_service()
        self.task_handlers = get_task_handlers()
        self.response_schemas = self._initialize_response_schemas()
        
        # Track service statistics (same as original)
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "start_time": datetime.utcnow()
        }
        
        logger.info("🚀 Centralized Gemini Service initialized (Drop-in LiteLLM replacement)")
    
    def _initialize_response_schemas(self) -> Dict[str, dict]:
        """
        Define response schemas for each task type
        EXACT same schemas as original LiteLLM service
        """
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
                                "summary": {"type": "string"},
                                "keywords": {"type": "array", "items": {"type": "string"}}
                            },
                            "required": ["title", "content", "category"]
                        }
                    },
                    "extraction_confidence": {"type": "number"},
                    "processing_notes": {"type": "string"}
                },
                "required": ["total_articles_found", "articles", "extraction_confidence", "processing_notes"]
            },
            
            "upsc_analysis": {
                "type": "object",
                "properties": {
                    "upsc_relevance": {"type": "number"},
                    "relevant_papers": {"type": "array", "items": {"type": "string"}},
                    "key_topics": {"type": "array", "items": {"type": "string"}},
                    "importance_level": {"type": "string"},
                    "question_potential": {"type": "string"},
                    "static_connections": {"type": "array", "items": {"type": "string"}},
                    "summary": {"type": "string"},
                    "exam_specific_analysis": {
                        "type": "object",
                        "properties": {
                            "prelims_relevance": {"type": "string"},
                            "mains_relevance": {"type": "string"},
                            "essay_potential": {"type": "string"}
                        }
                    }
                },
                "required": ["upsc_relevance", "relevant_papers", "key_topics", "importance_level", "summary"]
            },
            
            "summarization": {
                "type": "object", 
                "properties": {
                    "summary": {
                        "type": "object",
                        "properties": {
                            "brief": {"type": "string"},
                            "detailed": {"type": "string"},
                            "key_points": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["brief", "detailed", "key_points"]
                    },
                    "word_count_original": {"type": "number"},
                    "word_count_summary": {"type": "number"},
                    "compression_ratio": {"type": "number"}
                },
                "required": ["summary"]
            },
            
            "categorization": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "confidence": {"type": "number"},
                    "sub_categories": {"type": "array", "items": {"type": "string"}},
                    "reasoning": {"type": "string"},
                    "upsc_papers": {"type": "array", "items": {"type": "string"}}
                },
                "required": ["category", "confidence", "reasoning"]
            },
            
            "question_generation": {
                "type": "object",
                "properties": {
                    "questions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "question": {"type": "string"},
                                "type": {"type": "string"},
                                "difficulty": {"type": "string"},
                                "options": {"type": "array", "items": {"type": "string"}},
                                "correct_answer": {"type": "string"},
                                "explanation": {"type": "string"},
                                "upsc_paper": {"type": "string"}
                            },
                            "required": ["question", "type", "difficulty", "correct_answer", "explanation"]
                        }
                    },
                    "total_questions": {"type": "number"},
                    "difficulty_distribution": {
                        "type": "object",
                        "properties": {
                            "easy": {"type": "number"},
                            "medium": {"type": "number"},
                            "hard": {"type": "number"}
                        }
                    }
                },
                "required": ["questions", "total_questions"]
            },
            
            "answer_evaluation": {
                "type": "object",
                "properties": {
                    "overall_score": {"type": "number"},
                    "max_possible_score": {"type": "number"},
                    "percentage": {"type": "number"},
                    "evaluation_breakdown": {
                        "type": "object",
                        "properties": {
                            "content_quality": {"type": "number"},
                            "presentation": {"type": "number"},
                            "factual_accuracy": {"type": "number"},
                            "analytical_depth": {"type": "number"},
                            "conclusion": {"type": "number"}
                        }
                    },
                    "strengths": {"type": "array", "items": {"type": "string"}},
                    "areas_for_improvement": {"type": "array", "items": {"type": "string"}},
                    "detailed_feedback": {"type": "string"},
                    "grade": {"type": "string"}
                },
                "required": ["overall_score", "evaluation_breakdown", "detailed_feedback"]
            },
            
            "deduplication": {
                "type": "object",
                "properties": {
                    "is_duplicate": {"type": "boolean"},
                    "similarity_score": {"type": "number"},
                    "duplicate_type": {"type": "string"},
                    "reasoning": {"type": "string"},
                    "unique_elements": {"type": "array", "items": {"type": "string"}},
                    "recommendation": {"type": "string"}
                },
                "required": ["is_duplicate", "similarity_score", "reasoning", "recommendation"]
            }
        }
    
    async def process_request(self, request: LLMRequest) -> LLMResponse:
        """
        Main processing function - EXACT SAME INTERFACE as LiteLLM service
        
        This is the primary method that existing code calls. It maintains 100%
        compatibility while using our enhanced Gemini rotation backend.
        
        Args:
            request: LLMRequest object with task details
            
        Returns:
            LLMResponse object with results (same format as LiteLLM)
        """
        start_time = time.time()
        
        # Update statistics
        self.stats["total_requests"] += 1
        
        try:
            logger.info(f"🎯 Processing {request.task_type.value} request")
            
            # Route to appropriate task handler
            handler_map = {
                TaskType.CONTENT_EXTRACTION: self.task_handlers.handle_content_extraction,
                TaskType.UPSC_ANALYSIS: self.task_handlers.handle_upsc_analysis,
                TaskType.SUMMARIZATION: self.task_handlers.handle_summarization,
                TaskType.CATEGORIZATION: self.task_handlers.handle_categorization,
                TaskType.QUESTION_GENERATION: self.task_handlers.handle_question_generation,
                TaskType.ANSWER_EVALUATION: self.task_handlers.handle_answer_evaluation,
                TaskType.DEDUPLICATION: self.task_handlers.handle_deduplication
            }
            
            handler = handler_map.get(request.task_type)
            if not handler:
                raise ValueError(f"Unsupported task type: {request.task_type}")
            
            # Execute task with Gemini rotation service
            result_data = await handler(request)
            
            # Calculate response metrics
            response_time = time.time() - start_time
            
            # Estimate token usage (rough calculation)
            content_tokens = len(request.content.split()) if request.content else 0
            response_tokens = self._estimate_response_tokens(result_data)
            total_tokens = content_tokens + response_tokens
            
            # Estimate cost (rough calculation for Gemini)
            estimated_cost = total_tokens * 0.00001  # ~$0.01 per 1M tokens
            
            # Create response object (EXACT same format as LiteLLM)
            response = LLMResponse(
                success=True,
                task_type=request.task_type,
                provider_used="gemini-2.5-flash",  # Our provider
                model_used="gemini-2.5-flash",
                response_time=response_time,
                tokens_used=total_tokens,
                estimated_cost=estimated_cost,
                data=result_data,
                error_message=None,
                fallback_used=False  # Our rotation handles this internally
            )
            
            # Update success statistics
            self.stats["successful_requests"] += 1
            self.stats["total_response_time"] += response_time
            
            logger.info(f"✅ {request.task_type.value} completed in {response_time:.2f}s")
            return response
            
        except Exception as e:
            # Handle failures (same as LiteLLM service)
            response_time = time.time() - start_time
            
            self.stats["failed_requests"] += 1
            self.stats["total_response_time"] += response_time
            
            logger.error(f"❌ {request.task_type.value} failed: {e}")
            
            # Return error response (EXACT same format as LiteLLM)
            return LLMResponse(
                success=False,
                task_type=request.task_type,
                provider_used="gemini-2.5-flash",
                model_used="gemini-2.5-flash",
                response_time=response_time,
                tokens_used=0,
                estimated_cost=0.0,
                data={},
                error_message=str(e),
                fallback_used=False
            )
    
    def _estimate_response_tokens(self, data: Dict[str, Any]) -> int:
        """Estimate token usage from response data"""
        try:
            # Convert to string and rough word count
            response_text = json.dumps(data)
            return len(response_text.split())
        except:
            return 100  # Fallback estimate
    
    def get_service_stats(self) -> Dict[str, Any]:
        """
        Get service statistics - SAME INTERFACE as LiteLLM service
        
        Returns:
            Dictionary with service performance metrics
        """
        # Get stats from rotation service
        rotation_stats = self.rotation_service.get_service_stats()
        
        # Calculate our stats
        total_requests = max(self.stats["total_requests"], 1)
        success_rate = (self.stats["successful_requests"] / total_requests) * 100
        avg_response_time = (self.stats["total_response_time"] / 
                           max(self.stats["successful_requests"], 1))
        
        uptime = (datetime.utcnow() - self.stats["start_time"]).total_seconds()
        
        # Combine with rotation service stats (enhanced information)
        return {
            "service_info": {
                "name": "Centralized Gemini Service",
                "status": "healthy" if success_rate > 90 else "degraded" if success_rate > 70 else "critical",
                "uptime_seconds": round(uptime, 2),
                "provider": "Google Gemini 2.5 Flash",
                "api_keys_available": rotation_stats["service_info"]["total_keys"],
                "interface_compatibility": "100% LiteLLM Compatible"
            },
            
            "performance": {
                "total_requests": self.stats["total_requests"],
                "successful_requests": self.stats["successful_requests"],
                "failed_requests": self.stats["failed_requests"],
                "success_rate_percent": round(success_rate, 2),
                "avg_response_time_seconds": round(avg_response_time, 3),
                "total_response_time": round(self.stats["total_response_time"], 2)
            },
            
            "rotation_service": rotation_stats,  # Enhanced stats from rotation service
            
            "compatibility": {
                "litellm_interface": True,
                "supported_tasks": [
                    "content_extraction",
                    "upsc_analysis", 
                    "summarization",
                    "categorization",
                    "question_generation",
                    "answer_evaluation",
                    "deduplication"
                ]
            }
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform health check - SAME INTERFACE as LiteLLM service
        
        Returns:
            Health status information
        """
        logger.info("🏥 Performing service health check...")
        
        # Get health from rotation service
        rotation_health = await self.rotation_service.health_check()
        
        # Calculate overall service health
        service_stats = self.get_service_stats()
        
        overall_healthy = (
            service_stats["performance"]["success_rate_percent"] > 70 and
            rotation_health["overall_health"] in ["excellent", "good", "fair"]
        )
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "service_healthy": overall_healthy,
            "interface_compatible": True,
            "gemini_rotation_health": rotation_health,
            "service_performance": service_stats["performance"],
            "recommendations": [
                "Service is functioning normally" if overall_healthy 
                else "Review rotation service health for issues"
            ]
        }
    
    def reset_stats(self) -> None:
        """Reset service statistics - SAME INTERFACE as LiteLLM service"""
        logger.info("📊 Resetting Gemini service statistics...")
        
        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_response_time": 0.0,
            "start_time": datetime.utcnow()
        }
        
        # Also reset rotation service stats
        self.rotation_service.reset_stats()
        
        logger.info("✅ Statistics reset complete")


# Global service instance (EXACT SAME PATTERN as LiteLLM service)
_gemini_service: Optional[CentralizedGeminiService] = None

def get_gemini_service() -> CentralizedGeminiService:
    """
    Get or create global Gemini service instance
    
    This function maintains the same pattern as the original LiteLLM service
    for easy drop-in replacement.
    
    Returns:
        CentralizedGeminiService instance
    """
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = CentralizedGeminiService()
    return _gemini_service

# Alias for drop-in compatibility (main interface)
gemini_service = get_gemini_service()