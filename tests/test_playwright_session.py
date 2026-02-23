"""
Tests for PlaywrightSessionManager — browser session management with cookie persistence.

TDD-first: tests written before implementation.
All tests use mocked Playwright objects — NO real browser needed.
"""

import json
import os
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.playwright_session import PlaywrightSessionManager


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def tmp_cookie_dir(tmp_path: Path) -> str:
    """Create a temporary cookie directory for tests."""
    cookie_dir = tmp_path / "cookies"
    cookie_dir.mkdir()
    return str(cookie_dir)


@pytest.fixture
def session_manager(tmp_cookie_dir: str) -> PlaywrightSessionManager:
    """Create a PlaywrightSessionManager with temp cookie dir."""
    return PlaywrightSessionManager(cookie_dir=tmp_cookie_dir)


@pytest.fixture
def mock_playwright():
    """Mock the entire playwright async API chain."""
    mock_pw = AsyncMock()
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()

    # Wire up the chain: playwright -> chromium.launch() -> browser
    mock_pw.chromium.launch.return_value = mock_browser
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page

    # storage_state returns a dict (simulating cookie data)
    mock_context.storage_state.return_value = {
        "cookies": [{"name": "session", "value": "abc123"}],
        "origins": [],
    }

    # Page navigation mock
    mock_page.goto.return_value = None
    mock_page.url = "https://www.thehindu.com/"
    mock_page.content.return_value = "<html><body>Premium content</body></html>"

    return {
        "playwright": mock_pw,
        "browser": mock_browser,
        "context": mock_context,
        "page": mock_page,
    }


# ============================================================================
# TEST: __init__ and configuration
# ============================================================================


class TestInit:
    """Test PlaywrightSessionManager initialization."""

    def test_default_cookie_dir(self):
        """Default cookie_dir is /data/cookies/."""
        mgr = PlaywrightSessionManager()
        assert mgr.cookie_dir == "/data/cookies/"

    def test_custom_cookie_dir(self, tmp_cookie_dir: str):
        """Custom cookie_dir is accepted."""
        mgr = PlaywrightSessionManager(cookie_dir=tmp_cookie_dir)
        assert mgr.cookie_dir == tmp_cookie_dir

    def test_browser_not_launched_on_init(
        self, session_manager: PlaywrightSessionManager
    ):
        """Browser should NOT be launched during __init__."""
        assert session_manager._browser is None
        assert session_manager._playwright is None

    def test_user_agent_is_realistic(self, session_manager: PlaywrightSessionManager):
        """User-Agent must contain Chrome version string."""
        assert "Chrome/120.0.0.0" in session_manager.USER_AGENT

    def test_viewport_is_1920x1080(self, session_manager: PlaywrightSessionManager):
        """Viewport must be 1920x1080."""
        assert session_manager.VIEWPORT == {"width": 1920, "height": 1080}


# ============================================================================
# TEST: get_context
# ============================================================================


class TestGetContext:
    """Test context creation and cookie loading."""

    async def test_creates_new_context_when_no_cookies(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """When no cookie file exists, creates a fresh context."""
        with patch("app.services.playwright_session.async_playwright") as mock_pw_cm:
            mock_pw_cm.return_value.__aenter__.return_value = mock_playwright[
                "playwright"
            ]
            # Manually set playwright/browser so _ensure_browser works
            session_manager._playwright = mock_playwright["playwright"]
            session_manager._browser = mock_playwright["browser"]

            context = await session_manager.get_context("hindu")

            # Should have called new_context with user_agent and viewport
            mock_playwright["browser"].new_context.assert_called_once()
            call_kwargs = mock_playwright["browser"].new_context.call_args[1]
            assert "user_agent" in call_kwargs
            assert "viewport" in call_kwargs
            assert context == mock_playwright["context"]

    async def test_loads_existing_cookies(
        self,
        session_manager: PlaywrightSessionManager,
        mock_playwright,
        tmp_cookie_dir: str,
    ):
        """When cookie file exists, loads it via storage_state parameter."""
        # Create a cookie file
        cookie_path = os.path.join(tmp_cookie_dir, "hindu.json")
        with open(cookie_path, "w") as f:
            json.dump(
                {"cookies": [{"name": "session", "value": "abc"}], "origins": []}, f
            )

        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        context = await session_manager.get_context("hindu")

        call_kwargs = mock_playwright["browser"].new_context.call_args[1]
        assert call_kwargs["storage_state"] == cookie_path

    async def test_caches_context_per_site(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """Calling get_context twice for same site returns cached context."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        ctx1 = await session_manager.get_context("hindu")
        ctx2 = await session_manager.get_context("hindu")

        assert ctx1 is ctx2
        # new_context should only be called once
        assert mock_playwright["browser"].new_context.call_count == 1

    async def test_different_sites_get_different_contexts(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """Different site names produce separate contexts."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        # Return different mocks for each call
        ctx_hindu = AsyncMock()
        ctx_ie = AsyncMock()
        mock_playwright["browser"].new_context.side_effect = [ctx_hindu, ctx_ie]

        result_hindu = await session_manager.get_context("hindu")
        result_ie = await session_manager.get_context("ie")

        assert result_hindu is not result_ie
        assert mock_playwright["browser"].new_context.call_count == 2


# ============================================================================
# TEST: get_page
# ============================================================================


class TestGetPage:
    """Test page creation from context."""

    async def test_returns_new_page_from_context(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """get_page returns a new page from the site's context."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        page = await session_manager.get_page("hindu")

        assert page == mock_playwright["page"]
        mock_playwright["context"].new_page.assert_called_once()


# ============================================================================
# TEST: login_hindu
# ============================================================================


class TestLoginHindu:
    """Test The Hindu login flow."""

    async def test_navigates_to_login_page(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """Login navigates to The Hindu login URL."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        await session_manager.login_hindu("test@example.com", "password123")

        # Should navigate to Hindu login page
        page = mock_playwright["page"]
        calls = [str(c) for c in page.goto.call_args_list]
        assert any("thehindu.com" in c for c in calls)

    async def test_fills_credentials(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """Login fills email and password fields."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        await session_manager.login_hindu("test@example.com", "password123")

        page = mock_playwright["page"]
        # Should fill email and password fields
        page.fill.assert_any_await('input[type="email"], input[name="email"], #email', "test@example.com")

    async def test_saves_cookies_after_login(
        self,
        session_manager: PlaywrightSessionManager,
        mock_playwright,
        tmp_cookie_dir: str,
    ):
        """After login, saves cookies to disk via storage_state."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        await session_manager.login_hindu("test@example.com", "password123")

        expected_path = os.path.join(tmp_cookie_dir, "hindu.json")
        mock_playwright["context"].storage_state.assert_called_once_with(
            path=expected_path
        )

    async def test_login_raises_on_missing_credentials(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """Login raises ValueError when credentials are empty."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        with pytest.raises(ValueError, match="email.*required"):
            await session_manager.login_hindu("", "password123")

        with pytest.raises(ValueError, match="password.*required"):
            await session_manager.login_hindu("test@example.com", "")


# ============================================================================
# TEST: login_ie
# ============================================================================


class TestLoginIE:
    """Test Indian Express login flow."""

    async def test_navigates_to_ie_login_page(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """Login navigates to Indian Express login URL."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        await session_manager.login_ie("test@example.com", "password123")

        page = mock_playwright["page"]
        calls = [str(c) for c in page.goto.call_args_list]
        assert any("indianexpress.com" in c for c in calls)

    async def test_saves_cookies_after_ie_login(
        self,
        session_manager: PlaywrightSessionManager,
        mock_playwright,
        tmp_cookie_dir: str,
    ):
        """After IE login, saves cookies to ie.json."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        await session_manager.login_ie("test@example.com", "password123")

        expected_path = os.path.join(tmp_cookie_dir, "ie.json")
        mock_playwright["context"].storage_state.assert_called_once_with(
            path=expected_path
        )

    async def test_ie_login_raises_on_missing_credentials(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """IE Login raises ValueError when credentials are empty."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        with pytest.raises(ValueError, match="email.*required"):
            await session_manager.login_ie("", "password123")

        with pytest.raises(ValueError, match="password.*required"):
            await session_manager.login_ie("test@example.com", "")


# ============================================================================
# TEST: is_session_valid
# ============================================================================


class TestIsSessionValid:
    """Test session validity checking."""

    async def test_returns_false_when_no_cookie_file(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """No cookie file → session is invalid."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        result = await session_manager.is_session_valid("hindu")
        assert result is False

    async def test_returns_true_when_content_visible(
        self,
        session_manager: PlaywrightSessionManager,
        mock_playwright,
        tmp_cookie_dir: str,
    ):
        """Valid cookies + content visible → session is valid."""
        # Create cookie file
        cookie_path = os.path.join(tmp_cookie_dir, "hindu.json")
        with open(cookie_path, "w") as f:
            json.dump(
                {"cookies": [{"name": "session", "value": "abc"}], "origins": []}, f
            )

        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        # Page URL stays on content page (no redirect to login)
        mock_playwright["page"].url = "https://www.thehindu.com/some-article/"
        mock_playwright[
            "page"
        ].content.return_value = (
            "<html><body>Premium article content here</body></html>"
        )

        result = await session_manager.is_session_valid("hindu")
        assert result is True

    async def test_returns_false_when_redirected_to_login(
        self,
        session_manager: PlaywrightSessionManager,
        mock_playwright,
        tmp_cookie_dir: str,
    ):
        """Redirect to login page → session is invalid."""
        cookie_path = os.path.join(tmp_cookie_dir, "hindu.json")
        with open(cookie_path, "w") as f:
            json.dump(
                {"cookies": [{"name": "session", "value": "expired"}], "origins": []}, f
            )

        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        # Simulate redirect to login
        mock_playwright["page"].url = "https://www.thehindu.com/login/"

        result = await session_manager.is_session_valid("hindu")
        assert result is False


# ============================================================================
# TEST: refresh_if_needed
# ============================================================================


class TestRefreshIfNeeded:
    """Test cookie staleness check and auto-refresh."""

    async def test_fresh_cookies_not_refreshed(
        self,
        session_manager: PlaywrightSessionManager,
        mock_playwright,
        tmp_cookie_dir: str,
    ):
        """Cookie file < 14 days old → no re-login."""
        cookie_path = os.path.join(tmp_cookie_dir, "hindu.json")
        with open(cookie_path, "w") as f:
            json.dump({"cookies": [], "origins": []}, f)

        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        with patch.object(
            session_manager, "login_hindu", new_callable=AsyncMock
        ) as mock_login:
            with patch.object(
                session_manager,
                "is_session_valid",
                new_callable=AsyncMock,
                return_value=True,
            ):
                await session_manager.refresh_if_needed("hindu")
                mock_login.assert_not_called()

    async def test_stale_cookies_trigger_relogin(
        self,
        session_manager: PlaywrightSessionManager,
        mock_playwright,
        tmp_cookie_dir: str,
    ):
        """Cookie file > 14 days old → re-login triggered."""
        cookie_path = os.path.join(tmp_cookie_dir, "hindu.json")
        with open(cookie_path, "w") as f:
            json.dump({"cookies": [], "origins": []}, f)

        # Make the file appear 15 days old
        old_time = time.time() - (15 * 24 * 60 * 60)
        os.utime(cookie_path, (old_time, old_time))

        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        with patch("app.services.playwright_session.settings") as mock_settings:
            mock_settings.HINDU_EMAIL = "test@example.com"
            mock_settings.HINDU_PASSWORD = "password123"

            with patch.object(
                session_manager, "login_hindu", new_callable=AsyncMock
            ) as mock_login:
                await session_manager.refresh_if_needed("hindu")
                mock_login.assert_called_once_with("test@example.com", "password123")

    async def test_no_cookie_file_triggers_relogin(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """Missing cookie file → re-login triggered."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        with patch("app.services.playwright_session.settings") as mock_settings:
            mock_settings.HINDU_EMAIL = "test@example.com"
            mock_settings.HINDU_PASSWORD = "password123"

            with patch.object(
                session_manager, "login_hindu", new_callable=AsyncMock
            ) as mock_login:
                await session_manager.refresh_if_needed("hindu")
                mock_login.assert_called_once()

    async def test_ie_stale_cookies_trigger_ie_relogin(
        self,
        session_manager: PlaywrightSessionManager,
        mock_playwright,
        tmp_cookie_dir: str,
    ):
        """IE cookie file > 14 days old → IE re-login triggered."""
        cookie_path = os.path.join(tmp_cookie_dir, "ie.json")
        with open(cookie_path, "w") as f:
            json.dump({"cookies": [], "origins": []}, f)

        old_time = time.time() - (15 * 24 * 60 * 60)
        os.utime(cookie_path, (old_time, old_time))

        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        with patch("app.services.playwright_session.settings") as mock_settings:
            mock_settings.IE_EMAIL = "ie@example.com"
            mock_settings.IE_PASSWORD = "iepass123"

            with patch.object(
                session_manager, "login_ie", new_callable=AsyncMock
            ) as mock_login:
                await session_manager.refresh_if_needed("ie")
                mock_login.assert_called_once_with("ie@example.com", "iepass123")

    async def test_no_credentials_skips_refresh(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """If no credentials in env, refresh logs warning and skips."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        with patch("app.services.playwright_session.settings") as mock_settings:
            mock_settings.HINDU_EMAIL = None
            mock_settings.HINDU_PASSWORD = None

            with patch.object(
                session_manager, "login_hindu", new_callable=AsyncMock
            ) as mock_login:
                # Should not raise, just skip
                await session_manager.refresh_if_needed("hindu")
                mock_login.assert_not_called()


# ============================================================================
# TEST: close
# ============================================================================


class TestClose:
    """Test cleanup of browser resources."""

    async def test_closes_browser_and_playwright(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """close() shuts down browser and playwright."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]
        session_manager._contexts = {"hindu": mock_playwright["context"]}

        await session_manager.close()

        mock_playwright["context"].close.assert_called_once()
        mock_playwright["browser"].close.assert_called_once()
        mock_playwright["playwright"].stop.assert_called_once()

    async def test_close_is_safe_when_not_initialized(
        self, session_manager: PlaywrightSessionManager
    ):
        """close() does not raise when browser was never launched."""
        # Should not raise
        await session_manager.close()

    async def test_close_clears_internal_state(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """After close(), internal state is cleaned up."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]
        session_manager._contexts = {"hindu": mock_playwright["context"]}

        await session_manager.close()

        assert session_manager._browser is None
        assert session_manager._playwright is None
        assert session_manager._contexts == {}


# ============================================================================
# TEST: Navigation delay
# ============================================================================


class TestNavigationDelay:
    """Test that random delays are applied between navigations."""

    async def test_random_delay_between_2_and_5_seconds(
        self, session_manager: PlaywrightSessionManager
    ):
        """_random_delay sleeps between 2 and 5 seconds."""
        with patch(
            "app.services.playwright_session.asyncio.sleep", new_callable=AsyncMock
        ) as mock_sleep:
            await session_manager._random_delay()
            mock_sleep.assert_called_once()
            delay = mock_sleep.call_args[0][0]
            assert 2.0 <= delay <= 5.0


# ============================================================================
# TEST: Cookie path helper
# ============================================================================


class TestCookiePath:
    """Test cookie path generation."""

    def test_cookie_path_for_hindu(
        self, session_manager: PlaywrightSessionManager, tmp_cookie_dir: str
    ):
        """Cookie path for hindu is {cookie_dir}/hindu.json."""
        path = session_manager._cookie_path("hindu")
        assert path == os.path.join(tmp_cookie_dir, "hindu.json")

    def test_cookie_path_for_ie(
        self, session_manager: PlaywrightSessionManager, tmp_cookie_dir: str
    ):
        """Cookie path for ie is {cookie_dir}/ie.json."""
        path = session_manager._cookie_path("ie")
        assert path == os.path.join(tmp_cookie_dir, "ie.json")


# ============================================================================
# TEST: _ensure_browser (lazy initialization)
# ============================================================================


class TestEnsureBrowser:
    """Test lazy browser initialization."""

    async def test_launches_browser_on_first_call(
        self, session_manager: PlaywrightSessionManager
    ):
        """_ensure_browser starts playwright and launches chromium."""
        mock_pw = AsyncMock()
        mock_browser = AsyncMock()
        mock_pw.chromium.launch.return_value = mock_browser

        with patch("app.services.playwright_session.async_playwright") as mock_pw_cm:
            mock_pw_instance = AsyncMock()
            mock_pw_instance.start.return_value = mock_pw
            mock_pw_cm.return_value = mock_pw_instance

            await session_manager._ensure_browser()

            assert session_manager._playwright == mock_pw
            assert session_manager._browser == mock_browser
            mock_pw.chromium.launch.assert_called_once_with(headless=True)

    async def test_does_not_relaunch_if_already_running(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """If browser is already running, _ensure_browser is a no-op."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        # Call again — should not launch a second time
        await session_manager._ensure_browser()

        # chromium.launch should NOT be called again
        mock_playwright["playwright"].chromium.launch.assert_not_called()


# ============================================================================
# TEST: Error handling
# ============================================================================


class TestErrorHandling:
    """Test that errors are logged with context, not swallowed."""

    async def test_login_hindu_logs_error_on_failure(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """If Hindu login fails, error is logged and re-raised."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        mock_playwright["page"].goto.side_effect = Exception("Network timeout")

        with pytest.raises(Exception, match="Network timeout"):
            await session_manager.login_hindu("test@example.com", "password123")

    async def test_login_ie_logs_error_on_failure(
        self, session_manager: PlaywrightSessionManager, mock_playwright
    ):
        """If IE login fails, error is logged and re-raised."""
        session_manager._playwright = mock_playwright["playwright"]
        session_manager._browser = mock_playwright["browser"]

        mock_playwright["page"].goto.side_effect = Exception("Connection refused")

        with pytest.raises(Exception, match="Connection refused"):
            await session_manager.login_ie("test@example.com", "password123")
