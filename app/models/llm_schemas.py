from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum

class TaskType(str, Enum):
    CONTENT_EXTRACTION = "content_extraction"
    UPSC_ANALYSIS = "upsc_analysis" 
    CATEGORIZATION = "categorization"
    SUMMARIZATION = "summarization"
    QUESTION_GENERATION = "question_generation"
    ANSWER_EVALUATION = "answer_evaluation"
    DEDUPLICATION = "deduplication"
    KNOWLEDGE_CARD = "knowledge_card"
    UPSC_BATCH_ANALYSIS = "upsc_batch_analysis"

class ProviderPreference(str, Enum):
    COST_OPTIMIZED = "cost_optimized"    # Free/cheap models first
    SPEED_OPTIMIZED = "speed_optimized"  # Groq, Cerebras first  
    QUALITY_OPTIMIZED = "quality_optimized"  # Gemini, DeepSeek first
    BALANCED = "balanced"  # Round-robin all

class LLMRequest(BaseModel):
    task_type: TaskType
    content: str = Field(..., description="Content to process")
    provider_preference: ProviderPreference = ProviderPreference.COST_OPTIMIZED
    max_tokens: int = Field(default=4096, ge=1, le=8192)
    temperature: float = Field(default=0.1, ge=0.0, le=1.0)
    response_format: Optional[Dict[str, Any]] = None
    custom_instructions: Optional[str] = None
    batch_processing: bool = False

class LLMResponse(BaseModel):
    success: bool
    task_type: TaskType
    provider_used: str
    model_used: str  
    response_time: float
    tokens_used: int
    estimated_cost: float
    data: Dict[str, Any]
    error_message: Optional[str] = None
    fallback_used: bool = False
    
# Task-Specific Response Schemas
class ArticleExtractionResponse(BaseModel):
    total_articles_found: int
    articles: List[Dict[str, str]]
    extraction_confidence: float
    processing_notes: str

class UPSCAnalysisResponse(BaseModel):
    upsc_relevance: int = Field(ge=1, le=100)
    relevant_papers: List[str] 
    key_topics: List[str]
    importance_level: str
    question_potential: str
    static_connections: List[str]
    summary: str

class CategorizationResponse(BaseModel):
    category: str
    confidence: float
    sub_categories: List[str]
    reasoning: str

class SummarizationResponse(BaseModel):
    summary: str
    key_points: List[str]  
    word_count_original: int
    word_count_summary: int
    compression_ratio: float