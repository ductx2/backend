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
from pydantic import Field
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
        extra="ignore",  # Ignore extra variables not defined here
    )

    # =====================================
    # EXISTING VARIABLES (Preserve Exact)
    # =====================================

    # Supabase Configuration (Your Current Setup)
    supabase_url: str = Field(
        default="https://sxzrdqkbjdnrxuhjqxub.supabase.co",
        alias="NEXT_PUBLIC_SUPABASE_URL",
        description="Supabase project URL",
    )

    supabase_anon_key: str = Field(
        default="",
        alias="NEXT_PUBLIC_SUPABASE_ANON_KEY",
        description="Supabase anonymous key",
    )

    supabase_service_key: str = Field(
        default="",
        alias="SUPABASE_SERVICE_ROLE_KEY",
        description="Supabase service role key (admin access)",
    )

    # AI Processing (Your Current Gemini Setup)
    gemini_api_key: str = Field(
        default="",
        alias="GEMINI_API_KEY",
        description="Google Gemini API key for AI processing",
    )

    # Application URLs (Your Current Setup)
    site_url: str = Field(
        default="https://www.vaidra.in",
        alias="NEXT_PUBLIC_SITE_URL",
        description="Main application URL",
    )

    app_url: str = Field(
        default="http://localhost:3000",
        alias="NEXT_PUBLIC_APP_URL",
        description="Application URL for development",
    )

    # Payment Integration (Your Current Setup)
    razorpay_key_id: Optional[str] = Field(
        default=None,
        alias="RAZORPAY_KEY_ID",
        description="Razorpay key ID for payments",
    )

    razorpay_key_secret: Optional[str] = Field(
        default=None, alias="RAZORPAY_KEY_SECRET", description="Razorpay key secret"
    )

    # Mapbox (Your Current Setup)
    mapbox_token: Optional[str] = Field(
        default=None,
        alias="NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN",
        description="Mapbox access token for AI Maps",
    )

    # Current Affairs Automation (Your Current Setup)
    cron_secret: Optional[str] = Field(
        default=None,
        alias="CRON_SECRET",
        description="Secret for GitHub Actions automation (now deprecated)",
    )

    # =====================================
    # NEW FASTAPI-SPECIFIC VARIABLES
    # =====================================

    # FastAPI Backend Configuration
    api_key: str = Field(
        default="upsc_backend_secure_key_2025_development",
        alias="FASTAPI_API_KEY",
        description="API key for FastAPI backend authentication",
    )

    # Environment Configuration
    environment: str = Field(
        default="development",
        alias="NODE_ENV",
        description="Application environment (development/production)",
    )

    # Server Configuration
    host: str = Field(default="0.0.0.0", description="FastAPI server host")

    port: int = Field(default=8000, description="FastAPI server port")

    # CORS Configuration
    cors_origins: List[str] = Field(
        default=["http://localhost:3000", "https://www.vaidra.in"],
        description="Allowed CORS origins",
    )

    # Content Processing Configuration
    max_articles_per_source: int = Field(
        default=25, description="Maximum articles to process per RSS source"
    )

    relevance_threshold: int = Field(
        default=40, description="Minimum UPSC relevance score to pass articles through the pipeline"
    )

    # Scraping Configuration
    scraping_delay_seconds: float = Field(
        default=2.0, description="Delay between scraping requests (respect rate limits)"
    )

    request_timeout_seconds: int = Field(
        default=30, description="HTTP request timeout in seconds"
    )

    # Database Configuration
    max_database_connections: int = Field(
        default=10, description="Maximum database connection pool size"
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO", description="Logging level (DEBUG/INFO/WARNING/ERROR)"
    )


    # Playwright Session Configuration
    HINDU_EMAIL: str | None = None
    HINDU_PASSWORD: str | None = None
    IE_EMAIL: str | None = None
    IE_PASSWORD: str | None = None
    PLAYWRIGHT_COOKIE_DIR: str = "/data/cookies/"
    PLAYWRIGHT_HEADLESS: bool = True

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

    # =====================================
    # VALIDATION METHODS
    # =====================================

    def validate_required_settings(self) -> dict:
        """
        Validate that all required settings are configured
        Returns dict with validation results
        """
        validations = {
            "supabase_configured": bool(
                self.supabase_url and self.supabase_service_key
            ),
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
