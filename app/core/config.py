"""
Configuration management using Pydantic Settings
Preserves all existing environment variables from the main project

Environment Variables Preserved:
- SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY  
- GEMINI_API_KEY
- NEXT_PUBLIC_SITE_URL
- Plus new FastAPI-specific variables

Compatible with Python 3.13.5 and FastAPI 0.116.1
"""

from functools import lru_cache
from typing import Optional, List
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings using Pydantic Settings
    Automatically loads from .env files and environment variables
    """
    
    model_config = SettingsConfigDict(
        # Load from .env file in backend directory
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"  # Ignore extra variables not defined here
    )
    
    # =====================================
    # EXISTING VARIABLES (Preserve Exact)
    # =====================================
    
    # Supabase Configuration (Your Current Setup)
    supabase_url: str = Field(
        default="https://sxzrdqkbjdnrxuhjqxub.supabase.co",
        alias="NEXT_PUBLIC_SUPABASE_URL",
        description="Supabase project URL"
    )
    
    supabase_anon_key: str = Field(
        default="",
        alias="NEXT_PUBLIC_SUPABASE_ANON_KEY", 
        description="Supabase anonymous key"
    )
    
    supabase_service_key: str = Field(
        default="",
        alias="SUPABASE_SERVICE_ROLE_KEY",
        description="Supabase service role key (admin access)"
    )
    
    # AI Processing (Your Current Gemini Setup)
    gemini_api_key: str = Field(
        default="",
        alias="GEMINI_API_KEY",
        description="Google Gemini API key for AI processing"
    )
    
    # Raw multi-key environment variable
    groq_api_keys_raw: str = Field(
        default="",
        alias="GROQ_API_KEYS",
        description="Raw comma-separated Groq API keys"
    )
    
    # Note: groq_api_keys is computed in effective_groq_api_keys property
    
    # Legacy single key support (deprecated, use groq_api_keys)
    groq_api_key: str = Field(
        default="",
        alias="GROQ_API_KEY", 
        description="Single Groq API key (deprecated, use GROQ_API_KEYS instead)"
    )
    
    # Application URLs (Your Current Setup)
    site_url: str = Field(
        default="https://upsc-kappa.vercel.app",
        alias="NEXT_PUBLIC_SITE_URL",
        description="Main application URL"
    )
    
    app_url: str = Field(
        default="http://localhost:3000",
        alias="NEXT_PUBLIC_APP_URL", 
        description="Application URL for development"
    )
    
    # Payment Integration (Your Current Setup)
    razorpay_key_id: Optional[str] = Field(
        default=None,
        alias="RAZORPAY_KEY_ID",
        description="Razorpay key ID for payments"
    )
    
    razorpay_key_secret: Optional[str] = Field(
        default=None,
        alias="RAZORPAY_KEY_SECRET",
        description="Razorpay key secret"
    )
    
    # Mapbox (Your Current Setup)
    mapbox_token: Optional[str] = Field(
        default=None,
        alias="NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN",
        description="Mapbox access token for AI Maps"
    )
    
    # Current Affairs Automation (Your Current Setup)
    cron_secret: Optional[str] = Field(
        default=None,
        alias="CRON_SECRET",
        description="Secret for GitHub Actions automation (now deprecated)"
    )
    
    # =====================================
    # NEW FASTAPI-SPECIFIC VARIABLES
    # =====================================
    
    # FastAPI Backend Configuration
    api_key: str = Field(
        default="upsc_backend_secure_key_2025_development",
        alias="FASTAPI_API_KEY",
        description="API key for FastAPI backend authentication"
    )
    
    # Environment Configuration
    environment: str = Field(
        default="development",
        alias="NODE_ENV",
        description="Application environment (development/production)"
    )
    
    # Server Configuration
    host: str = Field(
        default="0.0.0.0",
        description="FastAPI server host"
    )
    
    port: int = Field(
        default=8000,
        description="FastAPI server port"
    )
    
    # CORS Configuration
    cors_origins: List[str] = Field(
        default=[
            "http://localhost:3000",
            "https://upsc-kappa.vercel.app"
        ],
        description="Allowed CORS origins"
    )
    
    # Content Processing Configuration
    max_articles_per_source: int = Field(
        default=25,
        description="Maximum articles to process per RSS source"
    )
    
    # Enhanced Intelligent Curation Configuration
    min_upsc_relevance: int = Field(
        default=30,
        description="Minimum UPSC relevance score for initial capture (lowered for wider net)"
    )
    
    # Tiered Processing Thresholds
    preliminary_threshold: int = Field(
        default=30,
        description="Threshold for preliminary tier processing (30-49)"
    )
    
    quality_threshold: int = Field(
        default=50,
        description="Threshold for quality tier processing (50-69)"
    )
    
    premium_threshold: int = Field(
        default=70,
        description="Threshold for premium tier processing (70+)"
    )
    
    # Daily Curation Targets
    target_articles_per_day: int = Field(
        default=25,
        description="Target number of curated articles to show users daily"
    )
    
    max_daily_capture: int = Field(
        default=150,
        description="Maximum articles to capture in background processing"
    )
    
    max_daily_processing: int = Field(
        default=75,
        description="Maximum articles to process through quality analysis"
    )
    
    # Multi-dimensional Scoring Configuration
    min_factual_score: int = Field(
        default=50,
        description="Minimum factual score for quality content"
    )
    
    min_analytical_score: int = Field(
        default=50,
        description="Minimum analytical score for quality content"
    )
    
    composite_score_threshold: int = Field(
        default=100,
        description="Minimum combined (factual + analytical) score for premium content"
    )
    
    # Category Balance Configuration (Based on UPSC Exam Pattern)
    category_balance_enabled: bool = Field(
        default=True,
        description="Enable intelligent category balance for daily curation"
    )
    
    # Scraping Configuration
    scraping_delay_seconds: float = Field(
        default=2.0,
        description="Delay between scraping requests (respect rate limits)"
    )
    
    request_timeout_seconds: int = Field(
        default=30,
        description="HTTP request timeout in seconds"
    )
    
    # Database Configuration
    max_database_connections: int = Field(
        default=10,
        description="Maximum database connection pool size"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG/INFO/WARNING/ERROR)"
    )
    
    # =====================================
    # COMPUTED PROPERTIES
    # =====================================
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode"""
        return self.environment.lower() == "development"
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return self.environment.lower() == "production"
    
    @property
    def database_url(self) -> str:
        """Get database URL from Supabase configuration"""
        return self.supabase_url
    
    @property
    def api_docs_enabled(self) -> bool:
        """Enable API docs only in development"""
        return self.is_development
    
    @property 
    def groq_api_keys(self) -> List[str]:
        """Parse and return Groq API keys from raw environment variable"""
        if self.groq_api_keys_raw:
            return [key.strip() for key in self.groq_api_keys_raw.split(',') if key.strip()]
        return []
    
    @property
    def effective_groq_api_keys(self) -> List[str]:
        """Get effective Groq API keys with backward compatibility"""
        keys = list(self.groq_api_keys)  # Start with multi-key list

        # Add legacy single key if provided and not already in the list
        if self.groq_api_key and self.groq_api_key not in keys:
            keys.append(self.groq_api_key)

        # Filter out empty strings
        return [key for key in keys if key and key.strip()]

    @property
    def all_gemini_api_keys(self) -> List[str]:
        """
        Get all Gemini API keys from environment with numbered suffix support
        Supports: GEMINI_API_KEY, GEMINI_API_KEY_2, ..., GEMINI_API_KEY_50

        This enables multi-key rotation to avoid Gemini's 5 requests/minute rate limit.
        With 23 keys, you get 115 requests/minute capacity.

        Returns:
            List of API keys loaded from environment
        """
        import os
        keys = []

        # Primary key (GEMINI_API_KEY)
        if self.gemini_api_key and self.gemini_api_key.strip():
            keys.append(self.gemini_api_key.strip())

        # Additional numbered keys (GEMINI_API_KEY_2 through GEMINI_API_KEY_50)
        for i in range(2, 51):  # Support up to 50 keys
            env_var_name = f"GEMINI_API_KEY_{i}"
            key = os.getenv(env_var_name)
            if key and key.strip():
                keys.append(key.strip())

        return keys
    
    # =====================================
    # FIELD VALIDATORS
    # =====================================
    
    # Note: Groq API keys are now parsed via properties
    
    # =====================================
    # VALIDATION METHODS
    # =====================================
    
    def validate_required_settings(self) -> dict:
        """
        Validate that all required settings are configured
        Returns dict with validation results
        """
        validations = {
            "supabase_configured": bool(self.supabase_url and self.supabase_service_key),
            "gemini_configured": bool(self.gemini_api_key),
            "api_key_configured": bool(self.api_key),
            "environment_set": bool(self.environment),
        }
        
        validations["all_required_configured"] = all(validations.values())
        return validations
    
    def get_cors_config(self) -> dict:
        """Get CORS configuration for FastAPI"""
        return {
            "allow_origins": self.cors_origins,
            "allow_credentials": True,
            "allow_methods": ["GET", "POST", "PUT", "DELETE"],
            "allow_headers": ["*"],
        }


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    Using lru_cache ensures settings are loaded once and reused
    """
    return Settings()


# Export for easy importing
settings = get_settings()