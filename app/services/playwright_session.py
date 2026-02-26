import asyncio
import json
import logging
import os
import random
import time
from datetime import datetime, timezone
from typing import Dict, Optional

from playwright.async_api import BrowserContext, Page, async_playwright

from app.core.config import settings

logger = logging.getLogger(__name__)

COOKIE_MAX_AGE_DAYS = 14

HINDU_LOGIN_URL = "https://www.thehindu.com/login/"
HINDU_CHECK_URL = "https://www.thehindu.com/opinion/editorial/"
IE_LOGIN_URL = "https://indianexpress.com/login/"
IE_CHECK_URL = "https://indianexpress.com/section/opinion/editorials/"

LOGIN_INDICATORS = ("login", "signin", "sign-in", "sign_in", "authenticate")


def _cookie_config_key(site: str) -> str:
    return f"playwright_cookies_{site}"


class PlaywrightSessionManager:
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    VIEWPORT = {"width": 1920, "height": 1080}

    def __init__(self) -> None:
        # No cookie_dir — cookies are stored in Supabase system_config table.
        self._playwright = None
        self._browser = None
        self._contexts: Dict[str, BrowserContext] = {}
        # In-memory cache of storage-state dicts keyed by site to avoid
        # repeated DB reads within the same pipeline run.
        self._cookie_cache: Dict[str, Optional[dict]] = {}

    # ------------------------------------------------------------------
    # Supabase cookie persistence
    # ------------------------------------------------------------------

    def _get_supabase_client(self):
        """Lazy import to avoid circular imports at module load time."""
        from app.core.database import SupabaseConnection

        return SupabaseConnection().client

    async def _load_cookies_from_supabase(self, site: str) -> Optional[dict]:
        """Return storage-state dict for site, or None if absent/expired."""
        if site in self._cookie_cache:
            return self._cookie_cache[site]

        try:
            client = self._get_supabase_client()
            key = _cookie_config_key(site)
            result = await asyncio.to_thread(
                lambda: client.table("system_config")
                .select("value")
                .eq("key", key)
                .maybe_single()
                .execute()
            )
            row = result.data if result else None
            if not row or not row.get("value"):
                logger.info("[PlaywrightSession] No cookies in Supabase for %s", site)
                self._cookie_cache[site] = None
                return None

            stored = row["value"]
            saved_at_str = stored.get("saved_at")
            if saved_at_str:
                saved_at = datetime.fromisoformat(saved_at_str)
                age_days = (
                    datetime.now(timezone.utc) - saved_at
                ).total_seconds() / 86400
                if age_days > COOKIE_MAX_AGE_DAYS:
                    logger.info(
                        "[PlaywrightSession] Cookies for %s are %.1f days old (max %d), treating as expired",
                        site,
                        age_days,
                        COOKIE_MAX_AGE_DAYS,
                    )
                    self._cookie_cache[site] = None
                    return None

            # stored["state"] is the raw Playwright storage-state dict
            state = stored.get("state")
            logger.info("[PlaywrightSession] Loaded cookies from Supabase for %s", site)
            self._cookie_cache[site] = state
            return state

        except Exception as e:
            logger.error(
                "[PlaywrightSession] Failed to load cookies from Supabase for %s: %s",
                site,
                e,
            )
            self._cookie_cache[site] = None
            return None

    async def _save_cookies_to_supabase(self, site: str, state: dict) -> None:
        """Persist Playwright storage-state dict to Supabase system_config."""
        try:
            client = self._get_supabase_client()
            key = _cookie_config_key(site)
            value = {
                "state": state,
                "saved_at": datetime.now(timezone.utc).isoformat(),
            }
            await asyncio.to_thread(
                lambda: client.table("system_config")
                .upsert(
                    {
                        "key": key,
                        "value": value,
                        "value_type": "json",
                        "category": "pipeline",
                        "description": f"Playwright session cookies for {site}",
                        "is_sensitive": True,
                    },
                    on_conflict="key",
                )
                .execute()
            )
            # Update in-memory cache
            self._cookie_cache[site] = state
            logger.info("[PlaywrightSession] Saved cookies to Supabase for %s", site)
        except Exception as e:
            logger.error(
                "[PlaywrightSession] Failed to save cookies to Supabase for %s: %s",
                site,
                e,
            )

    # ------------------------------------------------------------------
    # Browser lifecycle
    # ------------------------------------------------------------------

    async def _ensure_browser(self) -> None:
        if self._browser is not None:
            return
        pw = await async_playwright().start()
        self._playwright = pw
        self._browser = await pw.chromium.launch(headless=True)
        logger.info("[PlaywrightSession] Browser launched (headless)")

    async def _random_delay(self) -> None:
        delay = random.uniform(2.0, 5.0)
        await asyncio.sleep(delay)

    async def get_context(self, site: str) -> BrowserContext:
        if site in self._contexts:
            return self._contexts[site]

        await self._ensure_browser()

        kwargs: Dict = {
            "user_agent": self.USER_AGENT,
            "viewport": self.VIEWPORT,
        }

        # Load cookies from Supabase (if available)
        state = await self._load_cookies_from_supabase(site)
        if state:
            # Write to a temp file — Playwright requires a file path for storage_state
            import tempfile

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as tmp:
                json.dump(state, tmp)
                tmp_path = tmp.name
            kwargs["storage_state"] = tmp_path
            logger.info(
                "[PlaywrightSession] Applied Supabase cookies for %s via temp file",
                site,
            )

        context = await self._browser.new_context(**kwargs)
        self._contexts[site] = context

        # Clean up temp file after context is created
        if state and "storage_state" in kwargs:
            try:
                os.unlink(kwargs["storage_state"])
            except OSError:
                pass

        return context

    async def get_page(self, site: str) -> Page:
        context = await self.get_context(site)
        return await context.new_page()

    # ------------------------------------------------------------------
    # Login helpers
    # ------------------------------------------------------------------

    async def login_hindu(self, email: str, password: str) -> None:
        if not email or not email.strip():
            raise ValueError("Hindu email is required")
        if not password or not password.strip():
            raise ValueError("Hindu password is required")

        logger.info("[PlaywrightSession] Starting Hindu login for %s", email)

        try:
            # Fresh context — drop any existing one
            if "hindu" in self._contexts:
                await self._contexts["hindu"].close()
                del self._contexts["hindu"]
            self._cookie_cache.pop("hindu", None)

            await self._ensure_browser()
            context = await self._browser.new_context(
                user_agent=self.USER_AGENT, viewport=self.VIEWPORT
            )
            self._contexts["hindu"] = context
            page = await context.new_page()

            await page.goto(HINDU_LOGIN_URL, wait_until="networkidle")
            await self._random_delay()

            await page.fill('input[type="email"], input[name="email"], #email', email)
            await page.fill(
                'input[type="password"], input[name="password"], #password',
                password,
            )
            await page.click('button[type="submit"], input[type="submit"]')
            await page.wait_for_load_state("networkidle")
            await self._random_delay()

            # Capture storage state and persist to Supabase
            state = await context.storage_state()
            await self._save_cookies_to_supabase("hindu", state)

            await page.close()

        except ValueError:
            raise
        except Exception as e:
            logger.error("[PlaywrightSession] Hindu login failed: %s", str(e))
            raise

    async def login_ie(self, email: str, password: str) -> None:
        if not email or not email.strip():
            raise ValueError("IE email is required")
        if not password or not password.strip():
            raise ValueError("IE password is required")

        logger.info("[PlaywrightSession] Starting IE login for %s", email)

        try:
            if "ie" in self._contexts:
                await self._contexts["ie"].close()
                del self._contexts["ie"]
            self._cookie_cache.pop("ie", None)

            await self._ensure_browser()
            context = await self._browser.new_context(
                user_agent=self.USER_AGENT, viewport=self.VIEWPORT
            )
            self._contexts["ie"] = context
            page = await context.new_page()

            await page.goto(IE_LOGIN_URL, wait_until="networkidle")
            await self._random_delay()

            await page.fill('input[type="email"], input[name="email"], #email', email)
            await page.fill(
                'input[type="password"], input[name="password"], #password',
                password,
            )
            await page.click('button[type="submit"], input[type="submit"]')
            await page.wait_for_load_state("networkidle")
            await self._random_delay()

            state = await context.storage_state()
            await self._save_cookies_to_supabase("ie", state)

            await page.close()

        except ValueError:
            raise
        except Exception as e:
            logger.error("[PlaywrightSession] IE login failed: %s", str(e))
            raise

    # ------------------------------------------------------------------
    # Session validation / refresh
    # ------------------------------------------------------------------

    async def is_session_valid(self, site: str) -> bool:
        state = await self._load_cookies_from_supabase(site)
        if not state:
            logger.info("[PlaywrightSession] No cookies in Supabase for %s", site)
            return False

        try:
            await self._ensure_browser()
            context = await self.get_context(site)
            page = await context.new_page()

            check_url = HINDU_CHECK_URL if site == "hindu" else IE_CHECK_URL
            await page.goto(check_url, wait_until="networkidle")

            current_url = page.url.lower()
            is_login_page = any(
                indicator in current_url for indicator in LOGIN_INDICATORS
            )
            await page.close()

            if is_login_page:
                logger.info(
                    "[PlaywrightSession] Session expired for %s (redirected to login)",
                    site,
                )
                return False

            logger.info("[PlaywrightSession] Session valid for %s", site)
            return True

        except Exception as e:
            logger.error(
                "[PlaywrightSession] Session validation failed for %s: %s", site, str(e)
            )
            return False

    async def refresh_if_needed(self, site: str) -> None:
        state = await self._load_cookies_from_supabase(site)
        if state is not None:
            # Cookies exist and are not expired (age check done inside _load_cookies)
            logger.info(
                "[PlaywrightSession] Cookies for %s are fresh, no refresh needed", site
            )
            return

        logger.info("[PlaywrightSession] No valid cookies for %s, refresh needed", site)

        if site == "hindu":
            email = settings.HINDU_EMAIL
            password = settings.HINDU_PASSWORD
        elif site == "ie":
            email = settings.IE_EMAIL
            password = settings.IE_PASSWORD
        else:
            logger.warning("[PlaywrightSession] Unknown site for refresh: %s", site)
            return

        if not email or not password:
            logger.warning(
                "[PlaywrightSession] No credentials configured for %s, skipping refresh",
                site,
            )
            return

        if site == "hindu":
            await self.login_hindu(email, password)
        elif site == "ie":
            await self.login_ie(email, password)

        logger.info("[PlaywrightSession] Refreshed session for %s", site)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        for site, context in list(self._contexts.items()):
            try:
                await context.close()
            except Exception as e:
                logger.warning(
                    "[PlaywrightSession] Error closing context for %s: %s", site, str(e)
                )

        self._contexts = {}
        self._cookie_cache = {}

        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning("[PlaywrightSession] Error closing browser: %s", str(e))

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning(
                    "[PlaywrightSession] Error stopping playwright: %s", str(e)
                )

        self._browser = None
        self._playwright = None
        logger.info("[PlaywrightSession] Cleaned up all resources")
