import asyncio
import logging
import os
import random
import time
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


class PlaywrightSessionManager:
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    VIEWPORT = {"width": 1920, "height": 1080}

    def __init__(self, cookie_dir: str = "/data/cookies/") -> None:
        self.cookie_dir = cookie_dir
        self._playwright = None
        self._browser = None
        self._contexts: Dict[str, BrowserContext] = {}

    def _cookie_path(self, site: str) -> str:
        return os.path.join(self.cookie_dir, f"{site}.json")

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

        cookie_path = self._cookie_path(site)
        if os.path.exists(cookie_path):
            kwargs["storage_state"] = cookie_path
            logger.info("[PlaywrightSession] Loading cookies from %s", cookie_path)

        context = await self._browser.new_context(**kwargs)
        self._contexts[site] = context
        return context

    async def get_page(self, site: str) -> Page:
        context = await self.get_context(site)
        return await context.new_page()

    async def login_hindu(self, email: str, password: str) -> None:
        if not email or not email.strip():
            raise ValueError("Hindu email is required")
        if not password or not password.strip():
            raise ValueError("Hindu password is required")

        logger.info("[PlaywrightSession] Starting Hindu login for %s", email)

        try:
            if "hindu" in self._contexts:
                await self._contexts["hindu"].close()
                del self._contexts["hindu"]

            context = await self.get_context("hindu")
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

            cookie_path = self._cookie_path("hindu")
            os.makedirs(os.path.dirname(cookie_path), exist_ok=True)
            await context.storage_state(path=cookie_path)
            logger.info("[PlaywrightSession] Hindu cookies saved to %s", cookie_path)

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

            context = await self.get_context("ie")
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

            cookie_path = self._cookie_path("ie")
            os.makedirs(os.path.dirname(cookie_path), exist_ok=True)
            await context.storage_state(path=cookie_path)
            logger.info("[PlaywrightSession] IE cookies saved to %s", cookie_path)

            await page.close()

        except ValueError:
            raise
        except Exception as e:
            logger.error("[PlaywrightSession] IE login failed: %s", str(e))
            raise

    async def is_session_valid(self, site: str) -> bool:
        cookie_path = self._cookie_path(site)
        if not os.path.exists(cookie_path):
            logger.info("[PlaywrightSession] No cookie file for %s", site)
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
                "[PlaywrightSession] Session validation failed for %s: %s",
                site,
                str(e),
            )
            return False

    async def refresh_if_needed(self, site: str) -> None:
        cookie_path = self._cookie_path(site)
        needs_refresh = False

        if not os.path.exists(cookie_path):
            logger.info("[PlaywrightSession] No cookies for %s, refresh needed", site)
            needs_refresh = True
        else:
            file_age_seconds = time.time() - os.path.getmtime(cookie_path)
            file_age_days = file_age_seconds / (24 * 60 * 60)
            if file_age_days > COOKIE_MAX_AGE_DAYS:
                logger.info(
                    "[PlaywrightSession] Cookies for %s are %.1f days old (max %d), refresh needed",
                    site,
                    file_age_days,
                    COOKIE_MAX_AGE_DAYS,
                )
                needs_refresh = True

        if not needs_refresh:
            return

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

    async def close(self) -> None:
        for site, context in list(self._contexts.items()):
            try:
                await context.close()
            except Exception as e:
                logger.warning(
                    "[PlaywrightSession] Error closing context for %s: %s", site, str(e)
                )

        self._contexts = {}

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
