"""
AI Enhancement Service
Standalone Gemini 2.5 Flash enhancement and analysis system

This service provides comprehensive AI-powered content enhancement capabilities
including UPSC relevance analysis, summarization, keyword extraction, and 
specialized UPSC-focused analysis modes.

Features:
- Multiple enhancement modes (comprehensive, UPSC-focused, summary-only, keywords-only)
- Structured JSON output using Gemini's responseSchema 
- Comprehensive UPSC relevance scoring and analysis
- Batch processing capabilities
- Performance tracking and statistics
- Error handling and retry logic

Compatible with: Google Gemini 2.5 Flash, Python 3.13.5
Created: 2025-08-30
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
# REMOVED: import google.generativeai as genai - MIGRATED TO CENTRALIZED SERVICE

# Local imports - MIGRATED TO CENTRALIZED SERVICE
from app.services.centralized_llm_service import llm_service
from app.models.llm_schemas import LLMRequest, TaskType, ProviderPreference
from ..core.config import get_settings

# Initialize logger and settings
logger = logging.getLogger(__name__)
settings = get_settings()


# Request Models (for service use)
class ContentEnhancementRequest(BaseModel):
    """Content enhancement request"""
    title: str = Field(..., description="Article title")
    content: str = Field(..., description="Article content to enhance")
    source: str = Field(default="unknown", description="Content source (e.g. RSS feed name)")
    enhancement_mode: str = Field(default="comprehensive", description="Enhancement mode: comprehensive, upsc_focused, summary_only, keywords_only")
    include_summary: bool = Field(default=True, description="Include AI-generated summary")
    include_keywords: bool = Field(default=True, description="Include keyword extraction")
    include_upsc_analysis: bool = Field(default=True, description="Include UPSC relevance analysis")
    focus_areas: List[str] = Field(default=[], description="Specific focus areas for analysis")


class AIEnhancementService:
    """Service for AI-powered content enhancement using Gemini 2.5 Flash"""
    
    def __init__(self):
        """Initialize the AI enhancement service"""
        # MIGRATED: Now using centralized LLM service instead of direct Gemini client
        self.centralized_service = llm_service
        self.processing_stats = {
            "requests_processed": 0,
            "successful_enhancements": 0,
            "failed_enhancements": 0,
            "total_processing_time": 0.0,
            "enhancement_modes_used": {
                "comprehensive": 0,
                "upsc_focused": 0,
                "summary_only": 0,
                "keywords_only": 0,
                "quick_analysis": 0,
                "custom": 0
            }
        }
        logger.info("🤖 AI Enhancement Service initialized with Gemini 2.5 Flash")
        
    async def enhance_content(self, request: ContentEnhancementRequest) -> Dict[str, Any]:
        """
        Main content enhancement method
        
        Processes content through specified enhancement mode and returns
        structured analysis results with UPSC relevance scoring.
        
        Args:
            request: ContentEnhancementRequest with content and parameters
            
        Returns:
            Dict containing enhanced content analysis
        """
        try:
            logger.info(f"🧠 Enhancing content: {request.title[:50]}...")
            start_time = datetime.utcnow()
            
            # Route to appropriate enhancement method based on mode
            if request.enhancement_mode == "comprehensive":
                result = await self._comprehensive_enhancement(request)
            elif request.enhancement_mode == "upsc_focused":
                result = await self._upsc_focused_enhancement(request)
            elif request.enhancement_mode == "summary_only":
                result = await self._summary_only_enhancement(request)
            elif request.enhancement_mode == "keywords_only":
                result = await self._keywords_only_enhancement(request)
            elif request.enhancement_mode == "quick_analysis":
                result = await self._quick_analysis_enhancement(request)
            elif request.enhancement_mode == "custom":
                result = await self._custom_focus_enhancement(request)
            else:
                raise ValueError(f"Unknown enhancement mode: {request.enhancement_mode}")
            
            # Calculate processing time
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            result["processing_time"] = processing_time
            result["enhancement_mode"] = request.enhancement_mode
            result["timestamp"] = datetime.utcnow().isoformat()
            
            # Update statistics
            self._update_stats(request.enhancement_mode, processing_time, success=True)
            
            logger.info(f"✅ Content enhancement completed in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            self._update_stats(request.enhancement_mode, 0, success=False)
            logger.error(f"❌ Content enhancement failed: {e}")
            raise e
    
    async def _comprehensive_enhancement(self, request: ContentEnhancementRequest) -> Dict[str, Any]:
        """
        Comprehensive content enhancement with full UPSC analysis
        
        Provides complete analysis including relevance scoring, summaries,
        keywords, and detailed UPSC-specific insights.
        """
        
        # Create structured response schema for comprehensive analysis
        response_schema = {
            "type": "object",
            "properties": {
                "upsc_relevance": {"type": "number", "minimum": 0, "maximum": 100},
                "relevant_papers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Relevant UPSC papers (Prelims GS 1-4, Mains GS 1-4, Essay)"
                },
                "importance_level": {
                    "type": "string",
                    "enum": ["Low", "Medium", "High", "Critical"]
                },
                "summary": {
                    "type": "object",
                    "properties": {
                        "brief": {"type": "string", "description": "Brief 2-3 sentence summary"},
                        "detailed": {"type": "string", "description": "Detailed summary for UPSC preparation"},
                        "key_points": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key points for quick revision"
                        }
                    },
                    "required": ["brief", "detailed", "key_points"]
                },
                "keywords": {
                    "type": "object",
                    "properties": {
                        "primary_topics": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Primary topics covered"
                        },
                        "secondary_topics": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Secondary/related topics"
                        },
                        "important_terms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Important terms and concepts"
                        }
                    },
                    "required": ["primary_topics", "secondary_topics", "important_terms"]
                },
                "upsc_analysis": {
                    "type": "object",
                    "properties": {
                        "prelims_relevance": {"type": "string", "description": "Relevance for Prelims exam"},
                        "mains_relevance": {"type": "string", "description": "Relevance for Mains exam"},
                        "potential_questions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Potential UPSC questions"
                        },
                        "study_approach": {"type": "string", "description": "How to study this topic for UPSC"},
                        "current_affairs_link": {"type": "string", "description": "How this connects to current affairs"}
                    },
                    "required": ["prelims_relevance", "mains_relevance", "potential_questions", "study_approach"]
                }
            },
            "required": ["upsc_relevance", "relevant_papers", "importance_level", "summary", "keywords", "upsc_analysis"]
        }
        
        # Create comprehensive analysis prompt
        prompt = f"""
        Analyze this article comprehensively for UPSC Civil Services preparation:

        Title: {request.title}
        Source: {request.source}
        Content: {request.content[:3500]}  # Limit content to manage tokens

        Provide comprehensive analysis including:

        1. UPSC RELEVANCE SCORING:
        - Score from 0-100 based on UPSC exam relevance
        - Consider current affairs importance, syllabus coverage, and question potential
        - Factor in both Prelims and Mains relevance

        2. PAPER MAPPING:
        - Which specific UPSC papers this content relates to
        - Consider: Prelims GS 1-4, Mains GS 1-4, Essay writing

        3. IMPORTANCE CLASSIFICATION:
        - Classify as Low, Medium, High, or Critical importance for UPSC

        4. COMPREHENSIVE SUMMARIES:
        - Brief summary (2-3 sentences) for quick understanding
        - Detailed summary optimized for UPSC preparation
        - Key bullet points for revision notes

        5. KEYWORD ANALYSIS:
        - Primary topics that are central to the content
        - Secondary topics that provide context
        - Important terms and concepts to memorize

        6. UPSC-SPECIFIC ANALYSIS:
        - Specific relevance for Prelims exam (factual, current affairs)
        - Specific relevance for Mains exam (analytical, essay potential)
        - Potential questions that could be asked
        - Recommended study approach for this topic
        - How this connects to broader current affairs themes

        Focus on practical UPSC preparation value, current exam trends, and actionable insights.
        """
        
        # Use centralized LLM service for comprehensive analysis
        llm_request = LLMRequest(
            task_type=TaskType.UPSC_ANALYSIS,
            content=prompt,
            provider_preference=ProviderPreference.QUALITY_OPTIMIZED,
            max_tokens=2048,
            temperature=0.3,
            custom_instructions=f"Use schema: {json.dumps(response_schema)}"
        )
        
        response = await self.centralized_service.process_request(llm_request)
        if response.success and response.data:
            return response.data
        else:
            logger.error(f"Comprehensive enhancement failed: {response.error_message}")
            raise Exception(f"AI analysis failed: {response.error_message}")
    
    async def _upsc_focused_enhancement(self, request: ContentEnhancementRequest) -> Dict[str, Any]:
        """
        UPSC-focused enhancement with exam-specific analysis
        
        Specialized for UPSC preparation with focus on exam utility,
        question potential, and strategic preparation insights.
        """
        
        response_schema = {
            "type": "object",
            "properties": {
                "upsc_relevance": {"type": "number", "minimum": 0, "maximum": 100},
                "exam_utility": {
                    "type": "object",
                    "properties": {
                        "prelims_utility": {"type": "string", "description": "How useful for Prelims"},
                        "mains_utility": {"type": "string", "description": "How useful for Mains"},
                        "essay_potential": {"type": "string", "description": "Potential for essay writing"},
                        "relevant_papers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Specific papers where this is relevant"
                        }
                    },
                    "required": ["prelims_utility", "mains_utility", "essay_potential", "relevant_papers"]
                },
                "key_facts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key facts that could appear in UPSC questions"
                },
                "static_connections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Connections to static UPSC syllabus topics"
                },
                "preparation_strategy": {
                    "type": "object",
                    "properties": {
                        "priority_level": {"type": "string", "enum": ["Low", "Medium", "High", "Must-Know"]},
                        "study_method": {"type": "string", "description": "How to study this effectively"},
                        "revision_tips": {"type": "string", "description": "Tips for revision"},
                        "integration_advice": {"type": "string", "description": "How to integrate with other topics"}
                    },
                    "required": ["priority_level", "study_method", "revision_tips"]
                },
                "focus_area_analysis": {
                    "type": "object",
                    "description": "Analysis based on specified focus areas"
                }
            },
            "required": ["upsc_relevance", "exam_utility", "key_facts", "static_connections", "preparation_strategy"]
        }
        
        # Add focus area analysis if specified
        focus_areas_text = ""
        if request.focus_areas:
            focus_areas_text = f"\n\nSPECIAL FOCUS AREAS: {', '.join(request.focus_areas)}\nProvide specific analysis for these focus areas in the focus_area_analysis section."
        
        prompt = f"""
        Analyze this content specifically for UPSC Civil Services exam preparation:

        Title: {request.title}
        Source: {request.source}
        Content: {request.content[:3000]}
        {focus_areas_text}

        Provide UPSC-focused analysis with:

        1. UPSC RELEVANCE SCORE (0-100):
        - Consider direct exam utility
        - Factor in question-asking potential
        - Assess current affairs importance

        2. EXAM UTILITY ANALYSIS:
        - Specific utility for Prelims (facts, current affairs, basic concepts)
        - Specific utility for Mains (analysis, case studies, examples)
        - Essay writing potential and themes
        - Exact papers where this content is most relevant

        3. EXAM-CRITICAL FACTS:
        - Facts that could directly appear in MCQs
        - Data points worth memorizing
        - Current affairs elements for exam

        4. SYLLABUS CONNECTIONS:
        - How this connects to static syllabus topics
        - Integration with fundamental concepts
        - Cross-subject linkages

        5. PREPARATION STRATEGY:
        - Priority level for UPSC preparation
        - Most effective study method for this content
        - Revision and retention tips
        - How to integrate with broader preparation

        Focus exclusively on UPSC exam utility and strategic preparation value.
        """
        
        # Use centralized LLM service for UPSC-focused analysis
        llm_request = LLMRequest(
            task_type=TaskType.UPSC_ANALYSIS,
            content=prompt,
            provider_preference=ProviderPreference.QUALITY_OPTIMIZED,
            max_tokens=1536,
            temperature=0.2,
            custom_instructions=f"Use schema: {json.dumps(response_schema)}"
        )
        
        response = await self.centralized_service.process_request(llm_request)
        if response.success and response.data:
            result = response.data
        else:
            logger.error(f"UPSC-focused enhancement failed: {response.error_message}")
            raise Exception(f"AI analysis failed: {response.error_message}")
        
        # Add focus area analysis if provided
        if request.focus_areas:
            result["focus_areas_requested"] = request.focus_areas
        
        return result
    
    async def _summary_only_enhancement(self, request: ContentEnhancementRequest) -> Dict[str, Any]:
        """Summary-only enhancement with multiple summary formats"""
        
        response_schema = {
            "type": "object",
            "properties": {
                "summary": {
                    "type": "object",
                    "properties": {
                        "brief": {"type": "string", "description": "Brief 2-3 sentence summary"},
                        "detailed": {"type": "string", "description": "Detailed summary (200-250 words)"},
                        "bullet_points": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key points as bullet points (5-8 points)"
                        },
                        "upsc_summary": {"type": "string", "description": "UPSC preparation focused summary"}
                    },
                    "required": ["brief", "detailed", "bullet_points", "upsc_summary"]
                }
            },
            "required": ["summary"]
        }
        
        prompt = f"""
        Create comprehensive summaries of this content:

        Title: {request.title}
        Source: {request.source}  
        Content: {request.content[:3500]}

        Provide multiple summary formats:

        1. BRIEF SUMMARY (2-3 sentences):
        - Capture the essence in minimal words
        - Focus on the most important point

        2. DETAILED SUMMARY (200-250 words):
        - Comprehensive overview of all key points
        - Maintain logical flow and completeness
        - Include important details and context

        3. BULLET POINT SUMMARY (5-8 points):
        - Key points in digestible bullet format
        - Each point should be concise but complete
        - Arranged in logical order

        4. UPSC PREPARATION SUMMARY:
        - Summary specifically formatted for UPSC study
        - Include exam-relevant points
        - Connect to broader preparation themes

        Focus on clarity, completeness, and UPSC preparation utility.
        """
        
        # Use centralized LLM service for summary enhancement
        llm_request = LLMRequest(
            task_type=TaskType.SUMMARIZATION,
            content=prompt,
            provider_preference=ProviderPreference.BALANCED,
            max_tokens=1024,
            temperature=0.4,
            custom_instructions=f"Use schema: {json.dumps(response_schema)}"
        )
        
        response = await self.centralized_service.process_request(llm_request)
        if response.success and response.data:
            return response.data
        else:
            logger.error(f"Summary enhancement failed: {response.error_message}")
            raise Exception(f"AI analysis failed: {response.error_message}")
    
    async def _keywords_only_enhancement(self, request: ContentEnhancementRequest) -> Dict[str, Any]:
        """Keywords and topics extraction with comprehensive categorization"""
        
        response_schema = {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "object",
                    "properties": {
                        "primary_topics": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Main topics (5-8 items)"
                        },
                        "secondary_topics": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Related topics (3-5 items)"
                        },
                        "important_terms": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Key terms and concepts to remember"
                        },
                        "categories": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Content categories (e.g., Politics, Economy, Environment)"
                        },
                        "upsc_keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "UPSC-specific keywords and terms"
                        }
                    },
                    "required": ["primary_topics", "secondary_topics", "important_terms", "categories", "upsc_keywords"]
                }
            },
            "required": ["keywords"]
        }
        
        prompt = f"""
        Extract comprehensive keywords and topics from this content:

        Title: {request.title}
        Source: {request.source}
        Content: {request.content[:3000]}

        Provide detailed keyword analysis:

        1. PRIMARY TOPICS (5-8 items):
        - Main topics that the content is primarily about
        - Core themes and subjects

        2. SECONDARY TOPICS (3-5 items):
        - Related topics that provide context
        - Supporting themes and connections

        3. IMPORTANT TERMS (8-12 items):
        - Key terms, concepts, and terminology
        - Technical terms worth remembering
        - Names, places, organizations mentioned

        4. CATEGORIES:
        - Broad content categories (Politics, Economy, Environment, etc.)
        - Subject classifications for organization

        5. UPSC-SPECIFIC KEYWORDS:
        - Terms particularly relevant for UPSC preparation
        - Concepts that frequently appear in UPSC questions
        - Current affairs keywords for exam preparation

        Focus on comprehensive topic coverage and UPSC relevance.
        """
        
        # Use centralized LLM service for keyword extraction
        llm_request = LLMRequest(
            task_type=TaskType.CATEGORIZATION,
            content=prompt,
            provider_preference=ProviderPreference.COST_OPTIMIZED,
            max_tokens=768,
            temperature=0.3,
            custom_instructions=f"Use schema: {json.dumps(response_schema)}"
        )
        
        response = await self.centralized_service.process_request(llm_request)
        if response.success and response.data:
            return response.data
        else:
            logger.error(f"Keyword enhancement failed: {response.error_message}")
            raise Exception(f"AI analysis failed: {response.error_message}")

    async def _quick_analysis_enhancement(self, request: ContentEnhancementRequest) -> Dict[str, Any]:
        """Quick analysis mode for high-volume processing"""
        
        response_schema = {
            "type": "object",
            "properties": {
                "upsc_relevance": {"type": "number", "minimum": 0, "maximum": 100},
                "quick_summary": {"type": "string", "description": "One-sentence summary"},
                "key_topics": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "3-5 key topics",
                    "maxItems": 5
                },
                "exam_potential": {"type": "string", "enum": ["Low", "Medium", "High"]},
                "category": {"type": "string", "description": "Primary content category"}
            },
            "required": ["upsc_relevance", "quick_summary", "key_topics", "exam_potential", "category"]
        }
        
        prompt = f"""
        Provide quick analysis of this content for UPSC preparation:

        Title: {request.title}
        Content: {request.content[:2000]}

        Provide:
        1. UPSC relevance score (0-100)
        2. One-sentence summary
        3. 3-5 key topics
        4. Exam potential (Low/Medium/High)
        5. Primary category

        Keep analysis brief but accurate.
        """
        
        # Use centralized LLM service for quick analysis
        llm_request = LLMRequest(
            task_type=TaskType.UPSC_ANALYSIS,
            content=prompt,
            provider_preference=ProviderPreference.SPEED_OPTIMIZED,
            max_tokens=512,
            temperature=0.2,
            custom_instructions=f"Use schema: {json.dumps(response_schema)}"
        )
        
        response = await self.centralized_service.process_request(llm_request)
        if response.success and response.data:
            return response.data
        else:
            logger.error(f"Quick analysis failed: {response.error_message}")
            raise Exception(f"AI analysis failed: {response.error_message}")

    async def _custom_focus_enhancement(self, request: ContentEnhancementRequest) -> Dict[str, Any]:
        """Custom enhancement based on user-specified focus areas"""
        
        if not request.focus_areas:
            # Fallback to comprehensive if no focus areas specified
            return await self._comprehensive_enhancement(request)
        
        response_schema = {
            "type": "object",
            "properties": {
                "upsc_relevance": {"type": "number", "minimum": 0, "maximum": 100},
                "focus_area_analysis": {
                    "type": "object",
                    "description": "Analysis for each specified focus area"
                },
                "summary": {"type": "string", "description": "Summary focused on specified areas"},
                "key_insights": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Key insights for focus areas"
                },
                "connections": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "How focus areas connect to UPSC preparation"
                }
            },
            "required": ["upsc_relevance", "focus_area_analysis", "summary", "key_insights", "connections"]
        }
        
        focus_areas_text = ', '.join(request.focus_areas)
        
        prompt = f"""
        Analyze this content with specific focus on: {focus_areas_text}

        Title: {request.title}
        Content: {request.content[:3000]}

        Provide focused analysis:
        1. UPSC relevance score considering focus areas
        2. Detailed analysis for each focus area specified
        3. Summary highlighting focus area elements
        4. Key insights related to focus areas
        5. How these focus areas connect to UPSC preparation

        Focus areas to analyze: {focus_areas_text}

        Tailor the entire analysis to these specific focus areas.
        """
        
        # Use centralized LLM service for custom focus enhancement
        llm_request = LLMRequest(
            task_type=TaskType.UPSC_ANALYSIS,
            content=prompt,
            provider_preference=ProviderPreference.QUALITY_OPTIMIZED,
            max_tokens=1536,
            temperature=0.3,
            custom_instructions=f"Use schema: {json.dumps(response_schema)}"
        )
        
        response = await self.centralized_service.process_request(llm_request)
        if response.success and response.data:
            result = response.data
            result["focus_areas_analyzed"] = request.focus_areas
            return result
        else:
            logger.error(f"Custom focus enhancement failed: {response.error_message}")
            raise Exception(f"AI analysis failed: {response.error_message}")

    async def batch_enhance_content(self, requests: List[ContentEnhancementRequest], max_concurrent: int = 3) -> List[Dict[str, Any]]:
        """
        Process multiple content enhancement requests concurrently
        
        Args:
            requests: List of ContentEnhancementRequest objects
            max_concurrent: Maximum number of concurrent API calls
            
        Returns:
            List of enhancement results (same order as input)
        """
        logger.info(f"📦 Starting batch enhancement for {len(requests)} items with {max_concurrent} concurrent")
        
        # Use semaphore to limit concurrency
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def enhance_single(request: ContentEnhancementRequest) -> Dict[str, Any]:
            async with semaphore:
                try:
                    return await self.enhance_content(request)
                except Exception as e:
                    logger.error(f"Batch enhancement failed for item {request.title[:30]}: {e}")
                    return {
                        "error": str(e),
                        "title": request.title,
                        "enhancement_mode": request.enhancement_mode,
                        "success": False
                    }
        
        # Process all requests concurrently
        results = await asyncio.gather(
            *[enhance_single(req) for req in requests],
            return_exceptions=True
        )
        
        # Handle any exceptions that weren't caught
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    "error": str(result),
                    "title": requests[i].title,
                    "enhancement_mode": requests[i].enhancement_mode,
                    "success": False
                })
            else:
                processed_results.append(result)
        
        successful = sum(1 for r in processed_results if not r.get("error"))
        logger.info(f"✅ Batch enhancement completed: {successful}/{len(requests)} successful")
        
        return processed_results

    def get_processing_stats(self) -> Dict[str, Any]:
        """Get comprehensive processing statistics"""
        
        total_requests = max(self.processing_stats["requests_processed"], 1)
        avg_processing_time = self.processing_stats["total_processing_time"] / total_requests
        success_rate = (self.processing_stats["successful_enhancements"] / total_requests) * 100
        
        return {
            "performance": {
                "requests_processed": self.processing_stats["requests_processed"],
                "successful_enhancements": self.processing_stats["successful_enhancements"],
                "failed_enhancements": self.processing_stats["failed_enhancements"],
                "success_rate": round(success_rate, 2),
                "average_processing_time": round(avg_processing_time, 3),
                "total_processing_time": round(self.processing_stats["total_processing_time"], 2)
            },
            "enhancement_modes": dict(self.processing_stats["enhancement_modes_used"]),
            "service_status": {
                "status": "healthy" if success_rate > 90 else "degraded" if success_rate > 70 else "unhealthy",
                "uptime": "Service operational",
                "last_update": datetime.utcnow().isoformat()
            }
        }

    def reset_stats(self) -> None:
        """Reset processing statistics"""
        self.processing_stats = {
            "requests_processed": 0,
            "successful_enhancements": 0,
            "failed_enhancements": 0,
            "total_processing_time": 0.0,
            "enhancement_modes_used": {
                "comprehensive": 0,
                "upsc_focused": 0,
                "summary_only": 0,
                "keywords_only": 0,
                "quick_analysis": 0,
                "custom": 0
            }
        }
        logger.info("📊 Processing statistics reset")

    def _update_stats(self, enhancement_mode: str, processing_time: float, success: bool) -> None:
        """Update internal processing statistics"""
        self.processing_stats["requests_processed"] += 1
        
        if success:
            self.processing_stats["successful_enhancements"] += 1
            self.processing_stats["total_processing_time"] += processing_time
        else:
            self.processing_stats["failed_enhancements"] += 1
            
        # Track enhancement mode usage
        if enhancement_mode in self.processing_stats["enhancement_modes_used"]:
            self.processing_stats["enhancement_modes_used"][enhancement_mode] += 1
        else:
            self.processing_stats["enhancement_modes_used"][enhancement_mode] = 1

    def get_supported_modes(self) -> Dict[str, Any]:
        """Get information about supported enhancement modes"""
        return {
            "comprehensive": {
                "description": "Complete analysis with UPSC scoring, summaries, keywords, and exam insights",
                "features": ["UPSC relevance scoring", "Multi-format summaries", "Keyword extraction", "Exam-specific analysis"],
                "use_cases": ["General content analysis", "Complete UPSC preparation", "Detailed study material"],
                "processing_time": "Medium (3-5 seconds)"
            },
            "upsc_focused": {
                "description": "UPSC-specific analysis with exam utility and preparation strategy",
                "features": ["Exam utility assessment", "Question potential analysis", "Preparation strategy", "Static connections"],
                "use_cases": ["UPSC exam preparation", "Strategic study planning", "Content prioritization"],
                "processing_time": "Medium (2-4 seconds)"
            },
            "summary_only": {
                "description": "Multiple summary formats without detailed analysis",
                "features": ["Brief summary", "Detailed summary", "Bullet points", "UPSC-focused summary"],
                "use_cases": ["Quick understanding", "Content summarization", "Note preparation"],
                "processing_time": "Fast (1-2 seconds)"
            },
            "keywords_only": {
                "description": "Comprehensive keyword and topic extraction",
                "features": ["Primary/secondary topics", "Important terms", "Categories", "UPSC keywords"],
                "use_cases": ["Topic identification", "Keyword research", "Content categorization"],
                "processing_time": "Fast (1-2 seconds)"
            },
            "quick_analysis": {
                "description": "Rapid analysis for high-volume processing",
                "features": ["UPSC score", "Quick summary", "Key topics", "Exam potential"],
                "use_cases": ["Bulk processing", "Content filtering", "Quick assessment"],
                "processing_time": "Very Fast (<1 second)"
            },
            "custom": {
                "description": "Custom analysis based on user-specified focus areas",
                "features": ["Focus area analysis", "Targeted insights", "Custom connections", "Flexible scope"],
                "use_cases": ["Specialized analysis", "Topic-focused study", "Research projects"],
                "processing_time": "Medium (2-4 seconds)"
            }
        }


# Global service instance management
_ai_enhancement_service: Optional[AIEnhancementService] = None

def get_ai_enhancement_service() -> AIEnhancementService:
    """
    Get or create AI enhancement service singleton
    
    Returns:
        AIEnhancementService instance
    """
    global _ai_enhancement_service
    if _ai_enhancement_service is None:
        _ai_enhancement_service = AIEnhancementService()
    return _ai_enhancement_service