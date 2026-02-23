"""
PIB (Press Information Bureau) web scraper for UPSC-relevant press releases.

Scrapes https://pib.gov.in/allRel.aspx (ASP.NET WebForms) for English press releases,
filtered by UPSC-relevant ministries.

Returns article metadata dicts (title, url, published_date, ministry, source_site).
Does NOT fetch article body content — that is content_extractor.py's job.
"""

import logging
import random
from datetime import date
from typing import Any, Dict, List, Optional

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class PIBScraper:
    """Focused scraper for PIB press releases (pib.gov.in)."""

    BASE_URL = "https://pib.gov.in"
    PAGE_URL = "https://pib.gov.in/allRel.aspx"

    # English language, national region
    DEFAULT_PARAMS = {"reg": "3", "lang": "1"}

    # ASP.NET WebForms hidden field names to extract
    ASPNET_HIDDEN_FIELDS = [
        "__VIEWSTATE",
        "__VIEWSTATEGENERATOR",
        "__EVENTVALIDATION",
        "__EVENTTARGET",
        "__EVENTARGUMENT",
        "__LASTFOCUS",
        "__VIEWSTATEENCRYPTED",
    ]

    # Form field IDs for date selection
    FIELD_MINISTRY = "ctl00$ContentPlaceHolder1$ddlMinistry"
    FIELD_DAY = "ctl00$ContentPlaceHolder1$ddlday"
    FIELD_MONTH = "ctl00$ContentPlaceHolder1$ddlMonth"
    FIELD_YEAR = "ctl00$ContentPlaceHolder1$ddlYear"
    FIELD_REGION = "ctl00$ContentPlaceHolder1$hydregionid"
    FIELD_LANG = "ctl00$ContentPlaceHolder1$hydLangid"

    # UPSC-relevant ministries (exact names as they appear on PIB)
    UPSC_RELEVANT_MINISTRIES: set = {
        "Ministry of Finance",
        "Ministry of External Affairs",
        "Ministry of Home Affairs",
        "Ministry of Environment, Forest and Climate Change",
        "Ministry of Science & Technology",
        "Ministry of Education",
        "Ministry of Agriculture & Farmers Welfare",
        "Ministry of Commerce & Industry",
        "Ministry of Health and Family Welfare",
        "NITI Aayog",
        "Ministry of Law and Justice",
        "Ministry of Defence",
    }

    USER_AGENTS: List[str] = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    ]

    def __init__(self) -> None:
        self.rate_limit_delay: float = 1.5  # seconds between requests

    def _get_headers(self) -> Dict[str, str]:
        """Return request headers with a random User-Agent."""
        return {
            "User-Agent": random.choice(self.USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    def _extract_form_fields(self, html: str) -> Dict[str, str]:
        """Extract ASP.NET hidden fields from HTML page.

        Returns dict of field name → value for __VIEWSTATE, __EVENTVALIDATION, etc.
        """
        soup = BeautifulSoup(html, "html.parser")
        fields: Dict[str, str] = {}

        for field_name in self.ASPNET_HIDDEN_FIELDS:
            input_tag = soup.find("input", {"name": field_name})
            if input_tag:
                fields[field_name] = input_tag.get("value", "")

        # Also extract PIB-specific hidden fields
        for extra_name in [self.FIELD_REGION, self.FIELD_LANG]:
            input_tag = soup.find("input", {"name": extra_name})
            if input_tag:
                fields[extra_name] = input_tag.get("value", "")

        return fields

    def _parse_releases_html(
        self, html: str, target_date: date
    ) -> List[Dict[str, Any]]:
        """Parse press release HTML, extracting article metadata.

        Args:
            html: HTML string from PIB response.
            target_date: The date these releases are for (used in published_date).

        Returns:
            List of article dicts with keys:
            title, url, published_date, ministry, source_site
        """
        soup = BeautifulSoup(html, "html.parser")
        articles: List[Dict[str, Any]] = []

        content_area = soup.find("div", class_="content-area")
        if not content_area:
            logger.warning("PIB: No content-area div found in HTML")
            return []

        # Check for empty results
        area_text = content_area.get_text(strip=True)
        if "No Release Found" in area_text:
            logger.info("PIB: No releases found for %s", target_date.isoformat())
            return []

        # Structure: content-area → ul → li → h3.font104 (ministry) + ul.num → li → a (release)
        ministry_groups = content_area.find_all("h3", class_="font104")

        for h3 in ministry_groups:
            ministry_name = h3.get_text(strip=True)
            if not ministry_name:
                logger.debug("PIB: Skipping h3 with empty ministry name")
                continue

            # Find the sibling ul.num containing release links
            release_list = h3.find_next_sibling("ul", class_="num")
            if not release_list:
                # Could also be in parent structure
                parent_li = h3.find_parent("li")
                if parent_li:
                    release_list = parent_li.find("ul", class_="num")

            if not release_list:
                logger.debug(
                    "PIB: No release list found for ministry '%s'", ministry_name
                )
                continue

            release_links = release_list.find_all("a", href=True)
            for link in release_links:
                title = link.get("title", "") or link.get_text(strip=True)
                href = link["href"]

                if not title:
                    logger.debug("PIB: Skipping link with no title under '%s'", ministry_name)
                    continue

                # Build fully qualified URL
                if href.startswith("/"):
                    url = f"{self.BASE_URL}{href}"
                elif href.startswith("http"):
                    url = href
                else:
                    url = f"{self.BASE_URL}/{href}"

                articles.append(
                    {
                        "title": title,
                        "url": url,
                        "published_date": target_date.isoformat(),
                        "ministry": ministry_name,
                        "source_site": "pib",
                    }
                )

        logger.info(
            "PIB: Parsed %d releases across %d ministries for %s",
            len(articles),
            len(ministry_groups),
            target_date.isoformat(),
        )
        return articles

    def _filter_upsc_relevant(
        self, articles: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Filter articles to only UPSC-relevant ministries.

        Args:
            articles: List of article dicts with 'ministry' key.

        Returns:
            Filtered list containing only articles from UPSC-relevant ministries.
        """
        filtered = [
            a for a in articles if a["ministry"] in self.UPSC_RELEVANT_MINISTRIES
        ]
        skipped = len(articles) - len(filtered)
        if skipped > 0:
            skipped_ministries = {
                a["ministry"]
                for a in articles
                if a["ministry"] not in self.UPSC_RELEVANT_MINISTRIES
            }
            logger.info(
                "PIB: Filtered out %d articles from non-UPSC ministries: %s",
                skipped,
                skipped_ministries,
            )
        return filtered

    async def _http_get(self, url: str) -> httpx.Response:
        """HTTP GET request (mockable for testing).

        Args:
            url: Full URL to GET.

        Returns:
            httpx.Response object.
        """
        async with httpx.AsyncClient(
            headers=self._get_headers(), timeout=30.0, follow_redirects=True
        ) as client:
            return await client.get(url)

    async def _http_post(self, url: str, data: Dict[str, str]) -> httpx.Response:
        """HTTP POST request (mockable for testing).

        Args:
            url: Full URL to POST to.
            data: Form data dict.

        Returns:
            httpx.Response object.
        """
        async with httpx.AsyncClient(
            headers=self._get_headers(), timeout=30.0, follow_redirects=True
        ) as client:
            return await client.post(url, data=data)

    async def scrape_releases(
        self,
        target_date: Optional[date] = None,
        filter_upsc_relevant: bool = True,
    ) -> List[Dict[str, Any]]:
        """Scrape PIB press releases for a given date.

        Flow:
            1. GET the page to obtain __VIEWSTATE and other hidden fields.
            2. POST with date fields + ViewState to trigger date selection.
            3. Parse the resulting HTML for press release listings.
            4. Optionally filter to UPSC-relevant ministries only.

        Args:
            target_date: Date to scrape releases for. Defaults to today.
            filter_upsc_relevant: If True, filter to UPSC-relevant ministries only.

        Returns:
            List of article dicts (title, url, published_date, ministry, source_site).
            Returns empty list on error.
        """
        if target_date is None:
            target_date = date.today()

        page_url = f"{self.PAGE_URL}?reg=3&lang=1"

        logger.info("PIB: Scraping releases for %s", target_date.isoformat())

        # Step 1: GET initial page to extract ViewState
        try:
            get_response = await self._http_get(page_url)
            get_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                "PIB: GET request failed with status %s: %s",
                e.response.status_code,
                str(e),
            )
            return []
        except Exception as e:
            logger.error("PIB: GET request failed: %s", str(e))
            return []

        # Step 2: Extract ASP.NET form fields
        form_fields = self._extract_form_fields(get_response.text)

        if not form_fields.get("__VIEWSTATE"):
            logger.error("PIB: No __VIEWSTATE found in initial page")
            return []

        # Step 3: Build POST data with date fields
        post_data = {
            **form_fields,
            "__EVENTTARGET": "ctl00$ContentPlaceHolder1$ddlday",
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": "",
            self.FIELD_MINISTRY: "0",  # All Ministry
            self.FIELD_DAY: str(target_date.day),
            self.FIELD_MONTH: str(target_date.month),
            self.FIELD_YEAR: str(target_date.year),
        }

        # Step 4: POST to trigger date selection
        try:
            post_response = await self._http_post(page_url, data=post_data)
            post_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                "PIB: POST request failed with status %s: %s",
                e.response.status_code,
                str(e),
            )
            return []
        except Exception as e:
            logger.error("PIB: POST request failed: %s", str(e))
            return []

        # Step 5: Parse results
        articles = self._parse_releases_html(post_response.text, target_date)

        # Step 6: Filter if requested
        if filter_upsc_relevant:
            articles = self._filter_upsc_relevant(articles)

        logger.info(
            "PIB: Returning %d articles for %s (filter=%s)",
            len(articles),
            target_date.isoformat(),
            filter_upsc_relevant,
        )
        return articles