"""
Tests for backend/app/core/config.py

Verifies that all pipeline configuration settings have correct defaults.
Uses direct Settings() instantiation (not the lru_cache singleton) for test isolation.
"""

import os
import pytest
from unittest.mock import patch


def make_settings(**overrides):
    """Create a fresh Settings() instance with overrides applied as env vars."""
    from app.core.config import Settings

    # Patch env to avoid .env file interference
    env = {
        "NEXT_PUBLIC_SUPABASE_URL": "https://test.supabase.co",
        "NEXT_PUBLIC_SUPABASE_ANON_KEY": "test_anon_key",
        "SUPABASE_SERVICE_ROLE_KEY": "test_service_key",
        "GEMINI_API_KEY": "test_gemini_key",
        **overrides,
    }
    with patch.dict(os.environ, env, clear=False):
        return Settings(_env_file=None)  # type: ignore[call-arg]


def test_relevance_threshold_default_is_40():
    """relevance_threshold must default to 40 (pipeline filter)."""
    s = make_settings()
    assert s.relevance_threshold == 40


def test_playwright_cookie_dir_default():
    """PLAYWRIGHT_COOKIE_DIR must default to '/data/cookies/'."""
    s = make_settings()
    assert s.PLAYWRIGHT_COOKIE_DIR == "/data/cookies/"


def test_playwright_headless_default_is_true():
    """PLAYWRIGHT_HEADLESS must default to True."""
    s = make_settings()
    assert s.PLAYWRIGHT_HEADLESS is True


def test_cron_secret_is_optional():
    """cron_secret must be None when CRON_SECRET env var is not set."""
    env = {k: v for k, v in os.environ.items() if k != "CRON_SECRET"}
    with patch.dict(os.environ, env, clear=True):
        from app.core.config import Settings

        s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert s.cron_secret is None


def test_hindu_email_default_is_none():
    """HINDU_EMAIL must default to None when not set."""
    s = make_settings()
    assert s.HINDU_EMAIL is None
