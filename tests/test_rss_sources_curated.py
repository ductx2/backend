"""Tests for curated RSS source configuration.

Uses sys.modules mocking to bypass Supabase/LLM dependency chain
that can't be resolved in local test environments.
"""

import sys
import types
import pytest
from unittest.mock import MagicMock
from dataclasses import dataclass


def _build_sources():
    """Build source list by importing the processor with all dependencies mocked."""
    mock_modules = {}
    deps_to_mock = [
        "supabase",
        "supabase_auth",
        "supabase_auth.http_clients",
        "httpx",
        "feedparser",
        "app.services.centralized_llm_service",
        "app.models.llm_schemas",
        "app.core.config",
        "app.core.database",
        "app.services.content_extractor",
    ]

    saved = {}
    for mod_name in deps_to_mock:
        saved[mod_name] = sys.modules.get(mod_name)
        mock_mod = types.ModuleType(mod_name)
        mock_mod.__dict__.update(
            {
                "get_settings": lambda: MagicMock(),
                "get_database_sync": lambda: MagicMock(),
                "SupabaseConnection": MagicMock,
                "UniversalContentExtractor": MagicMock,
                "llm_service": MagicMock(),
                "LLMRequest": MagicMock,
                "TaskType": MagicMock,
                "ProviderPreference": MagicMock,
                "create_client": MagicMock,
                "Client": MagicMock,
            }
        )
        sys.modules[mod_name] = mock_mod
        mock_modules[mod_name] = mock_mod

    try:
        # Force re-import of the module with mocked deps
        mod_key = "app.services.optimized_rss_processor"
        if mod_key in sys.modules:
            del sys.modules[mod_key]

        from app.services.optimized_rss_processor import (
            OptimizedRSSProcessor,
            PremiumRSSSource,
        )

        processor = OptimizedRSSProcessor()
        return processor.sources
    finally:
        for mod_name in deps_to_mock:
            if saved[mod_name] is not None:
                sys.modules[mod_name] = saved[mod_name]
            elif mod_name in sys.modules:
                del sys.modules[mod_name]


@pytest.fixture(scope="module")
def sources():
    return _build_sources()


class TestRSSSourceConfiguration:
    def test_all_sources_are_hindu_curated(self, sources):
        for source in sources:
            assert "thehindu.com" in source.url, (
                f"Non-Hindu source found: {source.name} ({source.url})"
            )

    def test_no_garbage_national_feed_as_primary(self, sources):
        national = [s for s in sources if "National" in s.name]
        assert len(national) == 1
        assert national[0].priority == 3, (
            f"National feed should have priority 3, got {national[0].priority}"
        )

    def test_editorial_has_highest_priority(self, sources):
        editorial = [s for s in sources if "Editorial" in s.name]
        assert len(editorial) == 1
        assert editorial[0].priority == 1

    def test_indian_express_removed(self, sources):
        ie = [
            s
            for s in sources
            if "indianexpress.com" in s.url or "indian express" in s.name.lower()
        ]
        assert len(ie) == 0, f"Indian Express should be removed: {[s.name for s in ie]}"

    def test_livemint_removed(self, sources):
        lm = [
            s
            for s in sources
            if "livemint.com" in s.url or "livemint" in s.name.lower()
        ]
        assert len(lm) == 0, f"LiveMint should be removed: {[s.name for s in lm]}"

    def test_economic_times_removed(self, sources):
        et = [
            s
            for s in sources
            if "economictimes" in s.url or "economic times" in s.name.lower()
        ]
        assert len(et) == 0, f"Economic Times should be removed: {[s.name for s in et]}"

    def test_source_count(self, sources):
        assert len(sources) == 8, (
            f"Expected 8, got {len(sources)}: {[s.name for s in sources]}"
        )

    def test_all_sources_enabled(self, sources):
        for source in sources:
            assert source.enabled is True, f"{source.name} should be enabled"

    def test_source_urls_are_valid_rss(self, sources):
        for source in sources:
            assert source.url.endswith(".rss") or "/feed/" in source.url, (
                f"{source.name} URL not RSS: {source.url}"
            )

    def test_expected_sections_present(self, sources):
        names = {s.name for s in sources}
        expected = {
            "The Hindu - Editorial",
            "The Hindu - Op-Ed",
            "The Hindu - Lead",
            "The Hindu - Economy",
            "The Hindu - Science",
            "The Hindu - Technology",
            "The Hindu - International",
            "The Hindu - National",
        }
        assert names == expected, (
            f"Missing: {expected - names}, Extra: {names - expected}"
        )

    def test_opinion_feeds_are_priority_1(self, sources):
        opinion_names = {
            "The Hindu - Editorial",
            "The Hindu - Op-Ed",
            "The Hindu - Lead",
        }
        for source in sources:
            if source.name in opinion_names:
                assert source.priority == 1, f"{source.name} should be priority 1"

    def test_technology_is_priority_2(self, sources):
        tech = [s for s in sources if "Technology" in s.name]
        assert len(tech) == 1
        assert tech[0].priority == 2

    def test_source_health_defaults(self, sources):
        for source in sources:
            assert source.health_score == 100.0
            assert source.consecutive_failures == 0
            assert source.last_fetch_time is None
