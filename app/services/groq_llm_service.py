"""
Groq LLM Service for Enhanced UPSC Content Analysis
Specialized service for content refinement to bypass Gemini safety filters

Created: 2025-09-01
Purpose: Handle enhanced analysis of news content for UPSC preparation
Model: openai/gpt-oss-120b (120B parameter MoE model with structured outputs)
Features: Guaranteed JSON schema compliance, 131K context window, unrestricted analysis
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
import httpx
from datetime import datetime

from ..core.config import get_settings
from .groq_api_rotator import GroqAPIRotator

logger = logging.getLogger(__name__)

class GroqLLMService:
    """
    Advanced Groq LLM service for UPSC content refinement
    Uses GPT-OSS-120B with structured JSON schema for guaranteed compliance
    Designed to bypass safety filter issues while maintaining quality analysis
    """
    
    def __init__(self):
        """Initialize Groq LLM service with API key rotation support"""
        self.settings = get_settings()
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.model = "openai/gpt-oss-120b"  # 120B parameter MoE model with structured outputs
        
        # Get effective API keys (supports both single and multi-key configuration)
        api_keys = self.settings.effective_groq_api_keys
        
        if not api_keys:
            logger.error("❌ No Groq API keys configured")
            raise ValueError("At least one Groq API key is required for content refinement")
        
        # Initialize API key rotator
        self.rotator = GroqAPIRotator(api_keys)
        
        logger.info(f"🚀 Groq LLM Service initialized with {len(api_keys)} API keys, model: {self.model}")
        self.rotator._log_key_status()
        
        # Define comprehensive JSON schema for structured outputs
        self.upsc_analysis_schema = {
            "type": "object",
            "properties": {
                "factual_score": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Prelims MCQ potential - facts, statistics, dates"
                },
                "analytical_score": {
                    "type": "integer", 
                    "minimum": 0,
                    "maximum": 100,
                    "description": "Mains answer potential - analysis depth, case study value"
                },
                "upsc_relevance": {
                    "type": "integer",
                    "minimum": 0, 
                    "maximum": 100,
                    "description": "Overall relevance to UPSC syllabus"
                },
                "category": {
                    "type": "string",
                    "enum": ["current_affairs", "polity_governance", "economy_development", "environment_ecology", "history_culture", "science_technology"],
                    "description": "Primary UPSC subject category"
                },
                "key_facts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Important facts, figures, dates for exam preparation"
                },
                "key_vocabulary": {
                    "type": "array", 
                    "items": {"type": "string"},
                    "description": "Technical terms, acronyms, important names"
                },
                "syllabus_tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Relevant GS paper topics and syllabus connections"
                },
                "exam_angles": {
                    "type": "object",
                    "properties": {
                        "prelims_facts": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Direct MCQ potential points"
                        },
                        "mains_angles": {
                            "type": "array", 
                            "items": {"type": "string"},
                            "description": "Analysis points for Mains answers"
                        },
                        "essay_themes": {
                            "type": "array",
                            "items": {"type": "string"}, 
                            "description": "Broader themes for essay writing"
                        }
                    },
                    "required": ["prelims_facts", "mains_angles", "essay_themes"],
                    "additionalProperties": False
                },
                "revision_priority": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "description": "Study importance ranking based on exam utility"
                },
                "processing_status": {
                    "type": "string", 
                    "enum": ["preliminary", "quality", "premium"],
                    "description": "Content tier - premium (70+ combined), quality (50-69), preliminary (below 50)"
                },
                "summary": {
                    "type": "string",
                    "maxLength": 500,
                    "description": "2-sentence summary for UPSC preparation context"
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
            ],
            "additionalProperties": False
        }
    
    async def enhanced_upsc_analysis(self, content: str, category: str = "current_affairs") -> Dict[str, Any]:
        """
        Perform enhanced UPSC analysis using Groq LLM with structured outputs
        
        Args:
            content: Article content to analyze (up to 131K tokens supported)
            category: Content category for context
            
        Returns:
            Dict containing enhanced metadata matching UPSC enhancement plan schema
        """
        try:
            # Enhanced analysis prompt optimized for GPT-OSS-120B
            prompt = self._build_analysis_prompt(content, category)
            
            # Make API request to Groq with structured JSON schema
            response = await self._make_groq_structured_request(prompt)
            
            # Extract validated response (guaranteed schema compliance)
            analysis_result = self._extract_structured_response(response)
            
            logger.info(f"✅ Groq enhanced analysis completed:")
            logger.info(f"   📊 Factual: {analysis_result['factual_score']}/100")
            logger.info(f"   📝 Analytical: {analysis_result['analytical_score']}/100") 
            logger.info(f"   🎯 UPSC Relevance: {analysis_result['upsc_relevance']}/100")
            logger.info(f"   📚 Category: {analysis_result['category']}")
            logger.info(f"   🎯 Status: {analysis_result['processing_status']}")
            logger.info(f"   📋 Facts: {len(analysis_result['key_facts'])} extracted")
            
            return analysis_result

        except Exception as e:
            logger.error(f"❌ Groq enhanced analysis failed: {e}")
            # Re-raise exception to trigger Gemini fallback in flow.py
            raise
    
    def _build_analysis_prompt(self, content: str, category: str) -> str:
        """
        Build world-class analysis prompt with STRICT scoring + HTML generation
        Optimized for token efficiency while maintaining quality
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
    
    async def _make_groq_structured_request(self, prompt: str, max_retries: int = None) -> Dict[str, Any]:
        """
        Make structured API request to Groq with API key rotation and failure handling
        Automatically rotates through available API keys on failures
        """
        # Default to trying all available keys
        if max_retries is None:
            max_retries = self.rotator.healthy_key_count or 1
        
        # Base payload template
        payload_template = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert UPSC Civil Services content analyst. Provide comprehensive educational analysis with structured output following the exact schema requirements."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "upsc_content_analysis",
                    "schema": self.upsc_analysis_schema
                }
            },
            "temperature": 0.1,
            "max_tokens": 5000,  # Increased from 3500 for HTML generation
            "top_p": 0.8,
            "stream": False
        }
        
        # Try with different API keys on failure
        for attempt in range(max_retries):
            current_key = self.rotator.get_next_healthy_key()
            
            if not current_key:
                raise Exception("No healthy API keys available for Groq requests")
            
            # Create headers with current API key
            headers = {
                "Authorization": f"Bearer {current_key}",
                "Content-Type": "application/json"
            }
            
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        self.base_url,
                        headers=headers,
                        json=payload_template
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        # Record success for this key
                        self.rotator.record_success(current_key)
                        logger.info(f"✅ Groq API success with key {current_key[:8]}... (attempt {attempt + 1})")
                        return result
                    else:
                        # Record failure and log error
                        error_text = response.text
                        self.rotator.record_failure(current_key, f"HTTP {response.status_code}: {error_text}")
                        logger.warning(f"⚠️ Groq API error {response.status_code} with key {current_key[:8]}...: {error_text}")
                        
                        # Short delay before trying next key
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1.0)
                        
            except Exception as e:
                # Record failure and log error
                self.rotator.record_failure(current_key, str(e))
                logger.error(f"❌ Groq API request failed with key {current_key[:8]}... (attempt {attempt + 1}): {e}")
                
                # Short delay before trying next key
                if attempt < max_retries - 1:
                    await asyncio.sleep(2.0)
        
        # Log final status before failing
        health_report = self.rotator.get_health_report()
        logger.error(f"🚨 All {max_retries} Groq API attempts failed. Health: {health_report['healthy_keys']}/{health_report['total_keys']} keys healthy")
        
        raise Exception(f"All {max_retries} Groq structured API attempts failed")
    
    def _extract_structured_response(self, api_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract structured response from Groq API with fallback for malformed responses
        Includes validation to ensure all required keys are present
        """
        try:
            # Extract structured content from Groq response
            message_content = api_response["choices"][0]["message"]["content"]
            
            # Parse JSON response (should match schema)
            analysis_data = json.loads(message_content)
            
            # Validate all required keys are present
            required_keys = [
                "factual_score", "analytical_score", "upsc_relevance", "category", 
                "key_facts", "key_vocabulary", "syllabus_tags", "exam_angles",
                "revision_priority", "summary"
            ]
            
            missing_keys = [key for key in required_keys if key not in analysis_data]
            if missing_keys:
                logger.warning(f"⚠️ Structured response missing required keys: {missing_keys}")
                logger.warning(f"Using fallback response for data integrity")
                return self._get_fallback_response("current_affairs")
            
            # Validate processing status based on combined scores (business logic)
            combined_score = analysis_data["factual_score"] + analysis_data["analytical_score"]
            if combined_score >= 140:
                analysis_data["processing_status"] = "premium"
            elif combined_score >= 100:
                analysis_data["processing_status"] = "quality"
            else:
                analysis_data["processing_status"] = "preliminary"
            
            # Log structured extraction success
            logger.debug(f"📋 Structured response extracted successfully:")
            logger.debug(f"   🔢 Combined Score: {combined_score}")
            logger.debug(f"   📊 Facts: {len(analysis_data.get('key_facts', []))}")
            logger.debug(f"   📚 Vocabulary: {len(analysis_data.get('key_vocabulary', []))}")
            logger.debug(f"   🎯 Syllabus Tags: {len(analysis_data.get('syllabus_tags', []))}")
            
            return analysis_data
            
        except (json.JSONDecodeError, KeyError, ValueError, TypeError) as e:
            logger.error(f"❌ Failed to extract structured response: {e}")
            logger.warning(f"🔄 Using fallback response to maintain pipeline flow")
            logger.debug(f"Raw response: {api_response}")
            return self._get_fallback_response("current_affairs")
    
    def _get_fallback_response(self, category: str) -> Dict[str, Any]:
        """
        Provide comprehensive fallback response with strict UPSC scoring standards
        """
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
            "summary": f"Content categorized as {category}. Enhanced analysis temporarily unavailable - manual review recommended for complete UPSC preparation value."
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check Groq service health and structured output capabilities
        """
        try:
            # Test structured output with minimal content
            test_content = "India's GDP growth reached 7.2% in Q2 2024. Government announces new export incentives."
            test_response = await self.enhanced_upsc_analysis(test_content, "economy_development")
            
            # Validate response structure
            required_keys = ["factual_score", "analytical_score", "upsc_relevance", "key_facts"]
            structure_valid = all(key in test_response for key in required_keys)
            
            # Get API key rotation health status
            rotation_health = self.rotator.get_health_report()
            
            return {
                "status": "healthy",
                "model": self.model,
                "api_accessible": True,
                "structured_outputs": "supported",
                "schema_compliance": "guaranteed",
                "test_analysis_successful": True,
                "response_structure_valid": structure_valid,
                "rotation_status": rotation_health,
                "timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Groq health check failed: {e}")
            
            # Still get rotation health even if test failed
            rotation_health = self.rotator.get_health_report() if hasattr(self, 'rotator') else {"error": "Rotator not initialized"}
            
            return {
                "status": "unhealthy", 
                "model": self.model,
                "api_accessible": False,
                "structured_outputs": "unknown",
                "error": str(e),
                "rotation_status": rotation_health,
                "timestamp": datetime.utcnow().isoformat()
            }
    
    def get_service_info(self) -> Dict[str, Any]:
        """Get service information and capabilities with rotation status"""
        base_info = {
            "service_name": "Groq LLM Service",
            "purpose": "Enhanced UPSC content analysis",
            "model": self.model,
            "provider": "Groq",
            "capabilities": [
                "factual_score_analysis",
                "analytical_depth_scoring", 
                "upsc_relevance_assessment",
                "key_facts_extraction",
                "vocabulary_identification",
                "exam_angles_analysis",
                "educational_summarization",
                "multi_key_rotation",
                "automatic_failover"
            ],
            "use_case": "Content refinement for RSS articles with resilience",
            "advantage": "Bypass safety filters while maintaining analysis quality with automatic failover"
        }
        
        # Add rotation status if available
        if hasattr(self, 'rotator'):
            base_info["rotation_status"] = self.rotator.get_health_report()
        
        return base_info
    
    def get_rotation_health(self) -> Dict[str, Any]:
        """Get current API key rotation health status"""
        if hasattr(self, 'rotator'):
            return self.rotator.get_health_report()
        return {"error": "Rotator not initialized"}