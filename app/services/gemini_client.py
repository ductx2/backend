"""
Gemini AI Client Service
Centralized Google Gemini 2.5 Flash client for FastAPI backend

Features:
- Gemini 2.5 Flash model standardization
- Structured output generation with responseSchema
- Rate limiting and error handling
- Configuration management
- Performance optimization

Compatible with: google-generativeai>=0.8.3
Created: 2025-08-29
"""

import google.generativeai as genai
import logging
from typing import Optional
from ..core.config import get_settings

logger = logging.getLogger(__name__)

# Global Gemini client instance
_gemini_client: Optional[genai.GenerativeModel] = None

def get_gemini_client():
    """
    Get or create Gemini 2.5 Flash client instance
    
    Returns configured Gemini client following CLAUDE.md standards:
    - Always uses gemini-2.5-flash model
    - Proper API key configuration
    - Error handling for client initialization
    """
    global _gemini_client
    
    if _gemini_client is None:
        try:
            settings = get_settings()
            
            if not settings.gemini_api_key:
                logger.error("❌ Gemini API key not configured")
                raise ValueError("Gemini API key not found in settings")
            
            # Configure Gemini with API key
            genai.configure(api_key=settings.gemini_api_key)
            
            # Create Gemini 2.5 Flash client (following CLAUDE.md standards)
            _gemini_client = genai
            
            logger.info("✅ Gemini 2.5 Flash client initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini client: {e}")
            raise
    
    return _gemini_client

def create_gemini_model(
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.7,
    top_p: float = 0.8,
    top_k: int = 40,
    max_output_tokens: int = 2048,
    response_schema: Optional[dict] = None
) -> genai.GenerativeModel:
    """
    Create a configured Gemini model instance
    
    Args:
        model_name: Model name (default: gemini-2.5-flash per CLAUDE.md)
        temperature: Sampling temperature
        top_p: Top-p sampling parameter
        top_k: Top-k sampling parameter
        max_output_tokens: Maximum output tokens
        response_schema: Schema for structured output
    
    Returns:
        Configured GenerativeModel instance
    """
    try:
        client = get_gemini_client()
        
        # Generation configuration
        generation_config = {
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_output_tokens": max_output_tokens,
        }
        
        # Add structured output configuration if schema provided
        if response_schema:
            generation_config["response_schema"] = response_schema
            generation_config["response_mime_type"] = "application/json"
        
        # Safety settings for factual UPSC content processing
        safety_settings = [
            {
                "category": "HARM_CATEGORY_HARASSMENT",
                "threshold": "BLOCK_ONLY_HIGH"
            },
            {
                "category": "HARM_CATEGORY_HATE_SPEECH",
                "threshold": "BLOCK_ONLY_HIGH"
            },
            {
                "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                "threshold": "BLOCK_ONLY_HIGH"
            },
            {
                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                "threshold": "BLOCK_ONLY_HIGH"
            }
        ]
        
        # Create model instance
        model = client.GenerativeModel(
            model_name=model_name,
            generation_config=generation_config,
            safety_settings=safety_settings
        )
        
        logger.info(f"✅ Gemini model created: {model_name}")
        return model
        
    except Exception as e:
        logger.error(f"❌ Failed to create Gemini model: {e}")
        raise

def validate_response_schema(schema: dict) -> dict:
    """
    Validate and sanitize response schema for Gemini API
    
    Removes unsupported fields like 'minimum', 'maximum' that cause
    "Unknown field for Schema" errors in Gemini API.
    
    Args:
        schema: Input JSON schema
        
    Returns:
        Sanitized schema compatible with Gemini API
    """
    if not isinstance(schema, dict):
        return schema
    
    # Create a copy to avoid modifying the original
    sanitized = schema.copy()
    
    # Remove unsupported fields that cause Gemini API errors
    unsupported_fields = ['minimum', 'maximum', 'minItems', 'maxItems', 
                         'minLength', 'maxLength', 'pattern', 'format']
    
    for field in unsupported_fields:
        if field in sanitized:
            logger.warning(f"⚠️ Removing unsupported schema field: {field}")
            sanitized.pop(field)
    
    # Recursively clean nested objects
    if 'properties' in sanitized and isinstance(sanitized['properties'], dict):
        for prop_name, prop_schema in sanitized['properties'].items():
            sanitized['properties'][prop_name] = validate_response_schema(prop_schema)
    
    # Clean array items
    if 'items' in sanitized and isinstance(sanitized['items'], dict):
        sanitized['items'] = validate_response_schema(sanitized['items'])
    
    return sanitized


async def generate_structured_content(
    prompt: str,
    response_schema: dict,
    model_name: str = "gemini-2.5-flash",
    temperature: float = 0.3,
    max_output_tokens: int = 2048,
    max_retries: int = 3
) -> dict:
    """
    Generate structured content using Gemini with responseSchema
    
    Following CLAUDE.md standards for structured output generation:
    - Uses responseSchema parameter (not prompt formatting)
    - Returns parsed JSON object
    - Handles errors gracefully with retry logic
    - Validates and sanitizes schema for Gemini compatibility
    
    Args:
        prompt: Input prompt for generation
        response_schema: JSON schema for structured output
        model_name: Model to use (default: gemini-2.5-flash)
        temperature: Generation temperature
        max_output_tokens: Maximum output tokens
        max_retries: Maximum number of retry attempts
    
    Returns:
        Parsed JSON object from structured response
    """
    import json
    import asyncio
    
    # Validate and sanitize the response schema
    sanitized_schema = validate_response_schema(response_schema)
    
    last_exception = None
    
    for attempt in range(max_retries):
        try:
            logger.info(f"🔄 Gemini API attempt {attempt + 1}/{max_retries}")
            
            # Create model with structured output configuration
            model = create_gemini_model(
                model_name=model_name,
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                response_schema=sanitized_schema
            )
            
            # Generate content with error handling
            response = await model.generate_content_async(prompt)
            
            # Check if response exists and has candidates
            if not response or not response.candidates:
                logger.error("❌ No response or candidates from Gemini API")
                raise Exception("No response received from Gemini API")
                
            candidate = response.candidates[0]
            finish_reason = candidate.finish_reason if candidate else None
            
            # Map finish reasons for better debugging
            finish_reason_map = {
                1: "STOP",
                2: "SAFETY",
                3: "RECITATION",
                4: "MAX_TOKENS",
                5: "OTHER"
            }
            
            finish_reason_name = finish_reason_map.get(finish_reason, f"UNKNOWN({finish_reason})")
            
            # Check for content blocking before accessing response.text
            if finish_reason != 1:  # 1 = STOP (successful completion)
                logger.error(f"❌ Content generation blocked. Finish reason: {finish_reason_name}")
                
                # Log safety ratings if available for debugging
                if hasattr(candidate, 'safety_ratings') and candidate.safety_ratings:
                    logger.error("Safety ratings:")
                    for rating in candidate.safety_ratings:
                        logger.error(f"  {rating.category}: {rating.probability}")
                
                # Return a safe fallback for blocked content (non-retryable)
                if finish_reason == 2:  # SAFETY blocking
                    logger.warning("🔒 Content blocked by safety filters, returning fallback response")
                    return {
                        "error": "content_blocked_by_safety_filters",
                        "message": "The content could not be processed due to safety restrictions",
                        "finish_reason": finish_reason_name
                    }
                else:
                    raise Exception(f"Content generation blocked by Gemini API (reason: {finish_reason_name})")
            
            # Check if response has content parts
            if not candidate.content or not candidate.content.parts:
                logger.error("❌ No content parts in response")
                raise Exception("No content parts generated by Gemini API")
            
            # Parse structured JSON response (safe to access response.text now)
            try:
                response_text = response.text
                if not response_text:
                    raise Exception("Empty response text from Gemini API")
                    
                result = json.loads(response_text)
                
                logger.info(f"✅ Structured content generated successfully on attempt {attempt + 1}")
                return result
                
            except json.JSONDecodeError as json_error:
                logger.error(f"❌ JSON parsing error: {json_error}")
                logger.error(f"Raw response: {response.text[:500]}...")  # Truncate for logging
                raise Exception(f"Invalid JSON response from Gemini API: {json_error}")
        
        except Exception as e:
            last_exception = e
            
            # Check if this is a retryable error
            error_str = str(e).lower()
            retryable_errors = [
                "timeout", "connection", "503", "502", "429", 
                "rate limit", "service unavailable", "temporarily unavailable"
            ]
            
            is_retryable = any(error_text in error_str for error_text in retryable_errors)
            
            if attempt < max_retries - 1 and is_retryable:
                wait_time = (2 ** attempt) + 1  # Exponential backoff: 2, 3, 5 seconds
                logger.warning(f"⚠️ Retryable error on attempt {attempt + 1}: {e}")
                logger.info(f"🔄 Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
                continue
            else:
                # Non-retryable error or max retries reached
                logger.error(f"❌ Content generation failed on attempt {attempt + 1}: {e}")
                if attempt == max_retries - 1:
                    break  # Exit retry loop
                else:
                    raise  # Re-raise non-retryable errors immediately
    
    # If we get here, all retries failed
    logger.error(f"❌ All {max_retries} attempts failed. Last error: {last_exception}")
    raise Exception(f"Content generation failed after {max_retries} attempts: {last_exception}")