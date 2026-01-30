"""
Test automation endpoint timeout fix
"""

import pytest
import httpx
import time


@pytest.mark.asyncio
async def test_automation_endpoint_returns_immediately():
    """Test that /api/automation/daily returns 200 OK without waiting for pipeline"""
    api_key = "upsc_backend_secure_key_2025_production"

    start_time = time.time()

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "http://localhost:8000/api/automation/daily", headers={"X-API-Key": api_key}
        )

    elapsed_time = time.time() - start_time

    assert elapsed_time < 5.0, (
        f"Endpoint took {elapsed_time:.2f}s (should return immediately)"
    )
    assert response.status_code == 200, f"Expected 200 OK, got {response.status_code}"

    data = response.json()
    assert data["success"] == True
    assert (
        "background" in data["message"].lower() or "started" in data["message"].lower()
    )

    print(f"OK: Endpoint returned in {elapsed_time:.2f}s (non-blocking)")
