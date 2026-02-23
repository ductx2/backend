"""
TDD Tests for the cron-triggered knowledge pipeline endpoint.

Endpoint: POST /api/flow/cron/run-knowledge-pipeline
Auth: Bearer token matching settings.cron_secret
Concurrency: asyncio.Lock prevents parallel runs (409 if held)

VPS crontab schedule (for documentation, NOT implemented here):
  0 2 * * *   → 7:30 AM IST (2:00 UTC)
  30 12 * * * → 6:00 PM IST (12:30 UTC)

All pipeline dependencies are mocked — no network calls.
"""

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import app


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CRON_URL = "/api/flow/cron/run-knowledge-pipeline"
VALID_SECRET = "test-cron-secret-abc123"
HEADERS_VALID = {"Authorization": f"Bearer {VALID_SECRET}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_settings():
    """Patch settings.cron_secret to a known test value."""
    with patch("app.api.simplified_flow.settings") as mock_s:
        mock_s.cron_secret = VALID_SECRET
        yield mock_s


@pytest.fixture
def mock_pipeline():
    """Patch UnifiedPipeline so it returns deterministic results without I/O."""
    with patch("app.services.unified_pipeline.UnifiedPipeline") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(
            return_value={
                "articles": [{"title": "Test"}],
                "total_fetched": 5,
                "total_enriched": 3,
                "filtered": 2,
            }
        )
        mock_cls.return_value = mock_instance
        yield mock_cls


@pytest.fixture
def reset_pipeline_lock():
    """Ensure the module-level _pipeline_lock is released between tests."""
    from app.api import simplified_flow


    simplified_flow._pipeline_lock = asyncio.Lock()
    yield simplified_flow._pipeline_lock


@pytest.fixture
def client():
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# 1. Successful execution with valid token
# ---------------------------------------------------------------------------


async def test_cron_endpoint_returns_200_with_valid_token(
    client, mock_settings, mock_pipeline, reset_pipeline_lock
):
    """Valid Bearer token + successful pipeline → HTTP 200 with structured response."""
    response = await client.post(CRON_URL, headers=HEADERS_VALID)
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "completed"
    assert data["articles_processed"] == 5
    assert data["cards_produced"] == 3
    assert isinstance(data["duration_seconds"], (int, float))

    # Pipeline was called with save_to_db=True
    mock_pipeline.return_value.run.assert_awaited_once_with(save_to_db=True)


# ---------------------------------------------------------------------------
# 2. Missing Authorization header → 401
# ---------------------------------------------------------------------------


async def test_cron_endpoint_returns_401_missing_auth(
    client, mock_settings, reset_pipeline_lock
):
    """No Authorization header → HTTP 401 Unauthorized."""
    response = await client.post(CRON_URL)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 3. Invalid Bearer token → 401
# ---------------------------------------------------------------------------


async def test_cron_endpoint_returns_401_invalid_token(
    client, mock_settings, reset_pipeline_lock
):
    """Wrong Bearer token → HTTP 401 Unauthorized."""
    response = await client.post(
        CRON_URL, headers={"Authorization": "Bearer wrong-secret"}
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# 4. Concurrent execution blocked → 409
# ---------------------------------------------------------------------------


async def test_cron_endpoint_returns_409_when_already_running(
    client, mock_settings, mock_pipeline, reset_pipeline_lock
):
    """If the pipeline lock is already held, return HTTP 409 Conflict."""
    # Acquire the lock before the request
    await reset_pipeline_lock.acquire()

    try:
        response = await client.post(CRON_URL, headers=HEADERS_VALID)
        assert response.status_code == 409
        data = response.json()
        assert "already running" in data["error"].lower()
    finally:
        reset_pipeline_lock.release()


# ---------------------------------------------------------------------------
# 5. Response shape validation
# ---------------------------------------------------------------------------


async def test_cron_endpoint_response_shape(
    client, mock_settings, mock_pipeline, reset_pipeline_lock
):
    """Response body contains exactly the expected fields with correct types."""
    response = await client.post(CRON_URL, headers=HEADERS_VALID)
    assert response.status_code == 200

    data = response.json()
    # All required fields present
    assert set(data.keys()) == {
        "status",
        "articles_processed",
        "cards_produced",
        "duration_seconds",
    }
    # Type checks
    assert isinstance(data["status"], str)
    assert isinstance(data["articles_processed"], int)
    assert isinstance(data["cards_produced"], int)
    assert isinstance(data["duration_seconds"], (int, float))


# ---------------------------------------------------------------------------
# 6. Pipeline failure → 500
# ---------------------------------------------------------------------------


async def test_cron_endpoint_returns_500_on_pipeline_error(
    client, mock_settings, reset_pipeline_lock
):
    """If UnifiedPipeline.run() raises, return HTTP 500 with error detail."""
    with patch("app.services.unified_pipeline.UnifiedPipeline") as mock_cls:
        mock_instance = MagicMock()
        mock_instance.run = AsyncMock(side_effect=RuntimeError("Gemini quota exceeded"))
        mock_cls.return_value = mock_instance

        response = await client.post(CRON_URL, headers=HEADERS_VALID)
        assert response.status_code == 500
        data = response.json()
        assert "error" in data
        assert "Gemini quota exceeded" in data["error"]


# ---------------------------------------------------------------------------
# 7. cron_secret not configured → 401 (prevents open access)
# ---------------------------------------------------------------------------


async def test_cron_endpoint_returns_401_when_secret_not_configured(
    client, reset_pipeline_lock
):
    """If settings.cron_secret is None, all requests are rejected."""
    with patch("app.api.simplified_flow.settings") as mock_s:
        mock_s.cron_secret = None
        response = await client.post(
            CRON_URL, headers={"Authorization": "Bearer anything"}
        )
        assert response.status_code == 401
