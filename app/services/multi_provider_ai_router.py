#!/usr/bin/env python3
"""
LEGACY Multi-Provider AI Router - REPLACED BY CENTRALIZED LLM SERVICE

This file is kept for backward compatibility but all functionality 
has been migrated to the centralized LLM service with 140+ API keys
across 7 providers for maximum reliability and cost optimization.

Migration: Use app.services.centralized_llm_service.llm_service directly
"""

import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

# Import centralized service
from app.services.centralized_llm_service import llm_service
from app.models.llm_schemas import LLMRequest, TaskType, ProviderPreference

logger = logging.getLogger(__name__)

class ProviderType(Enum):
    """Legacy enum - maintained for compatibility"""
    GEMINI = "gemini"
    OPENROUTER = "openrouter" 
    OPENAI_COMPATIBLE = "openai_compatible"
    CENTRALIZED = "centralized"  # New centralized service

@dataclass
class ProviderAccount:
    """Legacy class - maintained for compatibility"""
    provider_type: ProviderType
    api_key: str
    base_url: Optional[str] = None
    model: str = ""
    headers: Dict[str, str] = field(default_factory=dict)
    max_tokens: int = 4096
    temperature: float = 0.1
    success_count: int = 0
    failure_count: int = 0
    avg_response_time: float = 0.0
    last_used: float = 0.0
    is_healthy: bool = True

@dataclass
class ExtractionRequest:
    """Legacy class - maintained for compatibility"""
    content: str
    max_articles: int = 50
    categories: List[str] = field(default_factory=list)
    additional_instructions: str = ""

@dataclass
class ExtractionResult:
    """Legacy class - maintained for compatibility"""
    success: bool
    articles: List[Dict[str, Any]] = field(default_factory=list)
    provider_used: str = "centralized"
    response_time: float = 0.0
    error_message: Optional[str] = None

class MultiProviderAIRouter:
    """
    LEGACY CLASS - REPLACED BY CENTRALIZED LLM SERVICE
    
    This wrapper provides backward compatibility while using
    the new centralized LLM service under the hood.
    
    RECOMMENDED: Use llm_service directly from centralized_llm_service
    """
    
    def __init__(self):
        """Initialize with centralized service"""
        logger.warning("🔄 LEGACY: MultiProviderAIRouter is deprecated. Use centralized_llm_service.llm_service directly")
        self.centralized_service = llm_service
        
    async def extract_content(self, request: ExtractionRequest) -> ExtractionResult:
        """
        Legacy method - Routes to centralized LLM service
        
        DEPRECATED: Use llm_service.process_request() directly
        """
        try:
            # Convert legacy request to new format
            prompt = f"""Extract articles from the following content:
            
            {request.content}
            
            Additional instructions: {request.additional_instructions}
            
            Return JSON with articles array containing title, content, and category for each article.
            Maximum articles: {request.max_articles}
            """
            
            # Use centralized service
            llm_request = LLMRequest(
                task_type=TaskType.CONTENT_EXTRACTION,
                content=prompt,
                provider_preference=ProviderPreference.COST_OPTIMIZED,  # Use free models first
                max_tokens=4096,
                temperature=0.1
            )
            
            response = await self.centralized_service.process_request(llm_request)
            
            if response.success:
                # Convert centralized response to legacy format
                articles = []
                if isinstance(response.data, dict):
                    articles = response.data.get("articles", [])
                
                logger.info(f"✅ LEGACY WRAPPER: Extracted {len(articles)} articles using {response.provider_used}")
                
                return ExtractionResult(
                    success=True,
                    articles=articles,
                    provider_used=f"centralized-{response.provider_used}",
                    response_time=response.response_time,
                    error_message=None
                )
            else:
                return ExtractionResult(
                    success=False,
                    articles=[],
                    provider_used="centralized-failed",
                    response_time=response.response_time,
                    error_message=response.error_message
                )
                
        except Exception as e:
            logger.error(f"❌ LEGACY WRAPPER: Extraction failed: {e}")
            return ExtractionResult(
                success=False,
                articles=[],
                provider_used="centralized-error",
                response_time=0.0,
                error_message=str(e)
            )
    
    async def analyze_upsc_relevance(self, content: str) -> Dict[str, Any]:
        """
        Legacy method - Routes to centralized LLM service for UPSC analysis
        
        DEPRECATED: Use llm_service.process_request() with TaskType.UPSC_ANALYSIS
        """
        try:
            llm_request = LLMRequest(
                task_type=TaskType.UPSC_ANALYSIS,
                content=content,
                provider_preference=ProviderPreference.QUALITY_OPTIMIZED,
                max_tokens=2048,
                temperature=0.1
            )
            
            response = await self.centralized_service.process_request(llm_request)
            
            if response.success:
                logger.info(f"✅ LEGACY WRAPPER: UPSC analysis completed using {response.provider_used}")
                return response.data if isinstance(response.data, dict) else {}
            else:
                logger.error(f"❌ LEGACY WRAPPER: UPSC analysis failed: {response.error_message}")
                return {"error": response.error_message}
                
        except Exception as e:
            logger.error(f"❌ LEGACY WRAPPER: UPSC analysis error: {e}")
            return {"error": str(e)}
    
    def get_provider_stats(self) -> Dict[str, Any]:
        """
        Legacy method - Returns centralized service stats
        
        DEPRECATED: Use llm_service.health_monitor for detailed stats
        """
        return {
            "total_providers": "140+ API keys across 7 providers",
            "centralized_service": "active",
            "legacy_mode": True,
            "recommendation": "Use centralized_llm_service.llm_service directly"
        }

# Legacy compatibility instances
router = MultiProviderAIRouter()

# Legacy functions for backward compatibility
async def extract_content_legacy(content: str, max_articles: int = 50) -> ExtractionResult:
    """Legacy function - Use centralized_llm_service instead"""
    logger.warning("🔄 DEPRECATED: extract_content_legacy() - Use centralized_llm_service.llm_service")
    request = ExtractionRequest(content=content, max_articles=max_articles)
    return await router.extract_content(request)

async def analyze_upsc_legacy(content: str) -> Dict[str, Any]:
    """Legacy function - Use centralized_llm_service instead"""
    logger.warning("🔄 DEPRECATED: analyze_upsc_legacy() - Use centralized_llm_service.llm_service")
    return await router.analyze_upsc_relevance(content)