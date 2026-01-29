"""
Enhanced Drishti IAS Content Scraper - CHROME-FREE ARCHITECTURE
High-performance scraping system using HTTP + Gemini 2.5 Flash AI

Features:
- Daily current affairs scraping with intelligent content extraction
- Editorial content scraping from Important Editorials section
- Chrome-free HTTP + AI-powered content parsing
- Centralized LLM system integration with structured responses
- Premium content prioritization over RSS duplicates
- Cloud deployment ready (Railway, Heroku, AWS compatible)

Compatible with: Python 3.13.5, Gemini 2.5 Flash, BeautifulSoup 4.x
Created: 2025-08-29, Updated: 2025-08-31 (Chrome-free conversion)
"""

import asyncio
import time
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from urllib.parse import urljoin, urlparse
import re
import hashlib
import os

# HTTP-only imports - No browser automation needed
import httpx

# BeautifulSoup for HTML parsing
from bs4 import BeautifulSoup, Tag, NavigableString
import requests

# Local imports
from ..core.config import get_settings
from ..core.database import get_database
from app.services.centralized_llm_service import llm_service
from app.models.llm_schemas import LLMRequest, TaskType, ProviderPreference
from app.services.gemini_client import get_gemini_client, create_gemini_model

logger = logging.getLogger(__name__)


@dataclass
class DrishtiArticle:
    """Structured Drishti IAS article data"""

    title: str
    content: str
    url: str
    published_date: datetime
    category: str
    source: str = "Drishti IAS"
    article_type: str = "current_affairs"  # current_affairs, editorial, analysis
    upsc_relevance: int = 0
    gs_paper: Optional[str] = None
    tags: List[str] = None
    summary: str = ""
    key_points: List[str] = None
    content_hash: str = ""

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.key_points is None:
            self.key_points = []
        if not self.content_hash:
            self.content_hash = hashlib.md5(
                f"{self.title}{self.content[:500]}".encode()
            ).hexdigest()


class DrishtiScraper:
    """
    Enhanced Drishti IAS content scraper with Selenium automation and BeautifulSoup parsing
    """

    def __init__(self):
        self.settings = get_settings()
        # Using centralized LLM service - no client initialization needed
        self.base_url = "https://www.drishtiias.com"

        # Base Target URLs for different content types
        self.base_target_urls = {
            "daily_current_affairs": "https://www.drishtiias.com/current-affairs-news-analysis-editorials/news-analysis",
            "daily_updates": "https://www.drishtiias.com/daily-updates/daily-news-analysis",
            "important_editorials": "https://www.drishtiias.com/current-affairs-news-analysis-editorials/editorial-analysis",
            "weekly_current_affairs": "https://www.drishtiias.com/current-affairs-news-analysis-editorials/current-affairs-weekly",
            "monthly_current_affairs": "https://www.drishtiias.com/current-affairs-news-analysis-editorials/monthly-current-affairs",
        }

        # HTTP client for Chrome-free scraping
        self.http_client = None

        # Statistics tracking
        self.scraping_stats = {
            "articles_scraped": 0,
            "articles_processed": 0,
            "articles_saved": 0,
            "errors": 0,
            "start_time": None,
            "processing_time": 0,
        }

        # Cache for duplicate detection
        self._scraped_urls = set()
        # Track the exact URLs used during the last scrape (for stats/UI)
        self._last_used_urls: List[str] = []

    @property
    def target_urls(self) -> List[str]:
        """Return list of target URLs for status reporting"""
        return list(self.base_target_urls.values())

    def generate_date_specific_urls(
        self, target_date: Optional[datetime] = None
    ) -> Dict[str, List[str]]:
        """Generate URLs. If a date is provided, only target the dated News Analysis page.
        Otherwise, return general landing pages.
        """
        if target_date is None:
            target_date = datetime.now()
        date_str = target_date.strftime("%d-%m-%Y")

        # Only the dated News Analysis URL is relevant for this endpoint
        urls = {
            "daily_current_affairs": [
                f"https://www.drishtiias.com/current-affairs-news-analysis-editorials/news-analysis/{date_str}"
            ]
        }

        logger.info(
            f"📅 Using ONLY dated URL for {date_str}: {urls['daily_current_affairs'][0]}"
        )
        return urls

    async def _setup_http_client(self) -> httpx.AsyncClient:
        """Setup HTTP client for Chrome-free scraping"""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
        }

        return httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True)

    async def initialize_http_client(self) -> bool:
        """Initialize HTTP client for Chrome-free scraping"""
        try:
            logger.info("Initializing HTTP client for Chrome-free Drishti scraping")

            if not self.http_client:
                self.http_client = await self._setup_http_client()

            logger.info("SUCCESS: HTTP client initialized successfully")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to initialize HTTP client: {e}")
            return False

    async def close_http_client(self):
        """Safely close the HTTP client"""
        if self.http_client:
            try:
                await self.http_client.aclose()
                logger.info("HTTP client closed successfully")
            except Exception as e:
                logger.error(f"Error closing HTTP client: {e}")

    async def scrape_article_links(
        self, target_url: str, max_articles: int = 50
    ) -> List[str]:
        """Scrape article links from a Drishti IAS category page"""
        try:
            if not self.driver:
                await self.initialize_browser()

            logger.info(f"Scraping article links from: {target_url}")

            # Navigate to the page
            self.driver.get(target_url)

            # Wait for content to load
            wait = WebDriverWait(self.driver, 15)

            # Try different selectors for article links
            article_selectors = [
                "a[href*='/current-affairs-news-analysis-editorials/']",
                "a[href*='/daily-updates/']",
                ".article-link",
                ".news-link",
                "article a",
                ".content-item a",
            ]

            article_links = []

            for selector in article_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements[:max_articles]:
                        href = element.get_attribute("href")
                        if href and self._is_valid_article_url(href):
                            article_links.append(href)

                    if article_links:
                        logger.info(
                            f"Found {len(article_links)} article links using selector: {selector}"
                        )
                        break

                except NoSuchElementException:
                    continue

            # Remove duplicates and filter out already scraped
            unique_links = list(set(article_links))
            new_links = [url for url in unique_links if url not in self._scraped_urls]

            logger.info(
                f"SUCCESS: Found {len(new_links)} new article links from {target_url}"
            )
            return new_links[:max_articles]

        except Exception as e:
            logger.error(f"❌ Error scraping article links from {target_url}: {e}")
            return []

    async def extract_articles_from_page_content(
        self, page_url: str
    ) -> List[DrishtiArticle]:
        """
        Extract all articles directly from the main daily page content using Gemini LLM

        This method uses HTTP + Gemini 2.5 Flash for intelligent content parsing,
        eliminating Chrome dependency for cloud deployment.

        Args:
            page_url: URL of the daily news page to scrape

        Returns:
            List of DrishtiArticle objects extracted via Gemini LLM parsing
        """
        try:
            logger.info(f"INFO: Extracting articles with Gemini LLM from: {page_url}")
            start_time = time.time()

            # Step 1: Fetch HTML content via HTTP (with retry & 521 handling)
            logger.info("INFO: Fetching HTML content...")
            html_content = None
            for attempt in range(3):
                try:
                    response = requests.get(
                        page_url,
                        headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                            "Accept-Language": "en-US,en;q=0.5",
                            "Accept-Encoding": "gzip, deflate, br",
                            "DNT": "1",
                            "Connection": "keep-alive",
                        },
                        timeout=30,
                    )
                    if response.status_code == 521:
                        logger.warning(
                            f"WARNING: Received 521 from Drishti, retrying ({attempt + 1}/3)..."
                        )
                        await asyncio.sleep(1.5)
                        continue
                    response.raise_for_status()
                    html_content = response.text
                    break
                except Exception as http_err:
                    if attempt == 2:
                        raise http_err
                    await asyncio.sleep(1.0)
            if html_content is None:
                raise RuntimeError("Failed to fetch HTML content after retries")

            logger.info(f"SUCCESS: HTML fetched - {len(html_content)} characters")

            # Step 2: Clean HTML for better processing
            cleaned_html = self._clean_html_for_gemini(html_content)
            logger.info(f"INFO: HTML cleaned - {len(cleaned_html)} characters")

            # Step 3: Extract with Centralized LLM Service (Official Structured Response)
            # But for dated pages, first try a deterministic BeautifulSoup parser tailored to Drishti structure
            bs_articles = await self._extract_with_beautifulsoup(html_content, page_url)
            if bs_articles and len(bs_articles) >= 3:  # good signal we parsed properly
                logger.info(
                    f"SUCCESS: BeautifulSoup extracted {len(bs_articles)} articles; skipping LLM for speed"
                )
                gemini_articles = bs_articles
            else:
                logger.info(
                    "INFO: Sending to Centralized LLM Service with official structured response..."
                )
            from app.services.centralized_llm_service import llm_service
            from app.models.llm_schemas import LLMRequest, TaskType, ProviderPreference

            # Use centralized LLM service with official structured response
            llm_request = LLMRequest(
                task_type=TaskType.CONTENT_EXTRACTION,
                content=cleaned_html,
                provider_preference=ProviderPreference.QUALITY_OPTIMIZED,
                max_tokens=3000,
                temperature=0.3,
                custom_instructions=f"""
TASK: Extract ALL individual news articles from this Drishti IAS daily current affairs page.

This page contains multiple distinct news articles. Each article typically has:
- A clear headline/title
- Article content/summary
- May have source information or tags

IMPORTANT: Look for ALL separate articles on this page. Don't treat the entire page as one article.

Expected structure patterns:
- Multiple article blocks/sections
- Headlines followed by content
- Numbered articles (1., 2., 3., etc.)
- Article separators or dividers

Return EACH distinct article separately in the JSON array. If you find 5 articles, return 5 separate objects.
Target: Extract 5-15 individual articles typically found on Drishti daily pages.
""",
            )

            extraction_response = await llm_service.process_request(llm_request)

            if extraction_response.success:
                # Official structured response - no manual parsing needed
                extraction_data = extraction_response.data
                total_found = extraction_data.get("total_articles_found", 0)
                articles_list = extraction_data.get("articles", [])
                confidence = extraction_data.get("extraction_confidence", 0)

                # Convert to expected format
                gemini_articles = []
                for article in articles_list:
                    gemini_articles.append(
                        {
                            "title": article.get("title", ""),
                            "content": article.get("content", ""),
                            "category": article.get("category", "News Analysis"),
                            "url": page_url,
                            "date": datetime.now().strftime("%d-%m-%Y"),
                        }
                    )

                logger.info(
                    f"SUCCESS: Centralized LLM extraction successful with {extraction_response.provider_used}"
                )
                logger.info(
                    f"SUCCESS: Extracted {len(gemini_articles)} articles in {extraction_response.response_time:.2f}s"
                )
                logger.info(
                    f"SUCCESS: Confidence score: {confidence}, Total found: {total_found}"
                )
            else:
                logger.error(
                    f"ERROR: Centralized LLM extraction failed: {extraction_response.error_message}"
                )
                # First try direct Gemini fallback
                logger.info("🔧 Trying direct Gemini fallback...")
                gemini_articles = await self._extract_with_direct_gemini(
                    cleaned_html, page_url
                )

                if not gemini_articles:
                    # Final fallback to BeautifulSoup parsing
                    logger.info("INFO: Falling back to BeautifulSoup parsing...")
                    gemini_articles = await self._extract_with_beautifulsoup(
                        html_content, page_url
                    )

            # Step 4: Convert to DrishtiArticle objects
            articles = []
            for i, article in enumerate(gemini_articles):
                try:
                    # Extract date from URL (format: /30-08-2025)
                    published_date = self._extract_date_from_url(page_url)

                    # Clean Unicode characters that might cause encoding issues
                    title = (
                        article["title"]
                        .strip()
                        .encode("utf-8", errors="ignore")
                        .decode("utf-8")
                    )
                    content = (
                        article["content"]
                        .strip()
                        .encode("utf-8", errors="ignore")
                        .decode("utf-8")
                    )
                    category = (
                        article.get("category", "General")
                        .encode("utf-8", errors="ignore")
                        .decode("utf-8")
                    )

                    drishti_article = DrishtiArticle(
                        title=title,
                        content=content,
                        url=page_url,
                        published_date=published_date,
                        category=category,
                        source="Drishti IAS",
                        article_type="current_affairs",
                    )

                    articles.append(drishti_article)
                    logger.info(f"SUCCESS: Converted article {i + 1}: {title[:50]}...")

                except Exception as e:
                    logger.error(f"ERROR: Error converting article {i + 1}: {e}")
                    continue

            processing_time = time.time() - start_time
            logger.info(
                f"SUCCESS: Gemini extraction completed in {processing_time:.2f}s"
            )
            logger.info(f"SUCCESS: Successfully extracted {len(articles)} articles")

            self.scraping_stats["articles_scraped"] += len(articles)
            return articles

        except Exception as e:
            logger.error(f"❌ Error in Gemini LLM extraction: {e}")
            return []

    def _clean_html_for_gemini(self, html_content: str) -> str:
        """Clean HTML to focus on main content for Gemini LLM processing"""
        try:
            from bs4 import BeautifulSoup
            import html

            # Step 1: Fix encoding issues first
            if isinstance(html_content, bytes):
                html_content = html_content.decode("utf-8", errors="replace")

            # Step 2: Parse with proper encoding
            soup = BeautifulSoup(html_content, "html.parser", from_encoding="utf-8")

            # Remove unwanted elements
            for element in soup(
                [
                    "script",
                    "style",
                    "nav",
                    "header",
                    "footer",
                    "aside",
                    "advertisement",
                    ".ads",
                    ".sidebar",
                    ".menu",
                ]
            ):
                element.decompose()

            # Get main content area - Drishti specific selectors first
            main_content_selectors = [
                ".article-list .list-category",  # Drishti specific article container
                ".article-list",  # Broader Drishti container
                "main",
                ".main",
                ".main-content",
                ".content",
                ".page-content",
                ".post-content",
                ".article-content",
                "body",  # Fallback to body
            ]

            main_content = None
            for selector in main_content_selectors:
                main_element = soup.select_one(selector)
                if main_element:
                    main_content = main_element
                    logger.info(f"SUCCESS: Found content using selector: {selector}")
                    break

            if not main_content:
                main_content = soup  # Use entire cleaned soup as fallback

            # Extract clean text with proper Unicode handling
            cleaned_text = main_content.get_text(separator="\n\n", strip=True)

            # Step 3: Clean up encoding artifacts and normalize Unicode
            cleaned_text = html.unescape(cleaned_text)  # Decode HTML entities
            cleaned_text = cleaned_text.encode("utf-8", errors="ignore").decode(
                "utf-8"
            )  # Clean invalid UTF-8

            # Remove control characters but preserve newlines and tabs
            import re

            cleaned_text = re.sub(
                r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]", "", cleaned_text
            )

            # Limit content size to stay within token limits (approximately)
            max_chars = 100000  # About 25k tokens for Gemini
            if len(cleaned_text) > max_chars:
                cleaned_text = (
                    cleaned_text[:max_chars]
                    + "\n\n[Content truncated due to length...]"
                )
                logger.warning(f"WARNING: Content truncated to {max_chars} characters")

            return cleaned_text

        except Exception as e:
            logger.error(f"ERROR: HTML cleaning error: {e}")
            # Return safely encoded fallback
            try:
                safe_content = html_content.encode("utf-8", errors="ignore").decode(
                    "utf-8"
                )
                return safe_content[:50000]
            except:
                return "Error processing content"

    async def _extract_with_direct_gemini(
        self, cleaned_html: str, page_url: str
    ) -> List[Dict[str, str]]:
        """FALLBACK: Extract articles using direct Gemini client (bypassing broken LiteLLM)"""
        try:
            import json

            logger.info("🔧 Using DIRECT Gemini fallback (LiteLLM bypass)")

            # Get direct Gemini client with API key from environment
            import google.generativeai as genai

            genai.configure(api_key=os.getenv("GEMINI_API_KEY", ""))

            model = genai.GenerativeModel(
                model_name="gemini-2.5-flash",
                generation_config={
                    "temperature": 0.3,
                    "top_p": 0.8,
                    "top_k": 40,
                    "max_output_tokens": 3000,
                },
            )

            # Create extraction prompt
            prompt = f"""Extract ALL individual news articles from this Drishti IAS daily current affairs page.

TASK: This page contains multiple distinct news articles. Find each separate article.

Expected structure patterns:
- Multiple article blocks/sections  
- Headlines followed by content
- Numbered articles (1., 2., 3., etc.)
- Article separators or dividers

Return EACH distinct article separately. Target: 5-15 individual articles.

Return JSON with this EXACT structure:
{{
  "total_articles_found": <number>,
  "articles": [
    {{
      "title": "exact article title",
      "content": "complete article content and analysis", 
      "category": "Politics/Economy/International/Social/Environment/Technology"
    }}
  ],
  "extraction_confidence": <0.0-1.0>,
  "processing_notes": "extraction notes"
}}

Content to extract from URL {page_url}:
{cleaned_html[:15000]}"""  # Limit content size

            # Generate content with direct Gemini
            response = model.generate_content(prompt)

            if response and response.text:
                # Try to parse JSON response
                try:
                    # Extract JSON from response (might have markdown formatting)
                    text = response.text.strip()
                    if text.startswith("```json"):
                        text = text.replace("```json", "").replace("```", "").strip()
                    elif text.startswith("```"):
                        text = text.replace("```", "").strip()

                    data = json.loads(text)
                    articles = data.get("articles", [])

                    logger.info(f"✅ Direct Gemini extracted {len(articles)} articles")
                    return articles

                except json.JSONDecodeError as e:
                    logger.warning(f"⚠️ Direct Gemini response not valid JSON: {e}")
                    logger.info(f"Raw response: {response.text[:200]}...")
                    return []
            else:
                logger.error("❌ No response from direct Gemini")
                return []

        except Exception as e:
            logger.error(f"❌ Direct Gemini extraction failed: {e}")
            return []

    async def _extract_with_llm_service(
        self, cleaned_html: str, page_url: str, original_html: str = None
    ) -> List[Dict[str, str]]:
        """Extract articles using centralized LLM service with direct Gemini fallback"""
        try:
            import json

            # Create extraction prompt for single-page structure
            prompt = f"""You are an expert content analyst analyzing a Drishti IAS daily current affairs page that contains MULTIPLE news articles on ONE SINGLE PAGE.

URL: {page_url}
CRITICAL UNDERSTANDING: This page contains approximately 5+ different news articles, each within separate <article> tags or article sections.

Your Task:
1. Find ALL separate news articles embedded within this single page
2. Look for multiple distinct news stories/topics (typically 5+ articles)
3. For each article, extract:
   - Title: The main headline (usually in <h1> or heading tags)
   - Content: Complete article content including analysis, key points, and details
   - Category: Topic area (Politics, Economy, International, Social Issues, etc.)

IMPORTANT NOTES:
- This is NOT individual article links - all articles are embedded in this single page
- Look for patterns like <article> tags, repeated headline structures, or content divisions
- Each article covers a different news topic or current affairs subject
- Extract COMPLETE content from each article section, not just summaries
- Expected output: 5+ distinct articles from this single page

Content to analyze:
{cleaned_html}

Return a JSON response with:
{{
    "total_articles_found": number,
    "articles": [
        {{
            "title": "article title",
            "content": "complete article content",
            "category": "category name"
        }}
    ],
    "processing_notes": "any relevant notes"
}}"""

            # Create LLM request for centralized service
            llm_request = LLMRequest(
                task_type=TaskType.CONTENT_EXTRACTION,
                content=prompt,
                provider_preference=ProviderPreference.COST_OPTIMIZED,  # Use free models first
                max_tokens=4096,
                temperature=0.1,
            )

            # Process with centralized service (automatic multi-provider failover)
            response = await llm_service.process_request(llm_request)

            if not response.success:
                logger.error(f"❌ Centralized LLM failed: {response.error_message}")
                # Fall back to BeautifulSoup
                logger.warning(
                    "WARNING: Centralized LLM failed - falling back to BeautifulSoup parsing"
                )
                return await self._extract_with_beautifulsoup(
                    original_html or cleaned_html, page_url
                )

            # Parse response data from centralized LLM service
            try:
                # Handle different response formats
                if isinstance(response.data, dict):
                    articles_data = response.data.get("articles", [])
                    total_found = response.data.get(
                        "total_articles_found", len(articles_data)
                    )
                    page_analysis = response.data.get(
                        "processing_notes",
                        f"Successfully processed with {response.provider_used}",
                    )
                elif isinstance(response.data, str):
                    # If response is JSON string, parse it
                    result = json.loads(response.data)
                    articles_data = result.get("articles", [])
                    total_found = result.get("total_articles_found", len(articles_data))
                    page_analysis = result.get(
                        "processing_notes",
                        f"Successfully processed with {response.provider_used}",
                    )
                else:
                    # Fallback if unexpected format
                    logger.warning(
                        "WARNING: Unexpected response format from centralized LLM"
                    )
                    return await self._extract_with_beautifulsoup(
                        original_html or cleaned_html, page_url
                    )

                logger.info(
                    f"✅ SUCCESS: Centralized LLM extracted {len(articles_data)} articles using {response.provider_used}"
                )
                logger.info(
                    f"📊 Processing time: {response.response_time:.2f}s, Tokens used: {response.tokens_used}"
                )

                # Convert to expected format
                articles = []
                for i, article in enumerate(articles_data, 1):
                    articles.append(
                        {
                            "title": article.get("title", f"Article {i}"),
                            "content": article.get("content", ""),
                            "category": article.get("category", "General"),
                            "article_number": i,
                        }
                    )

                # Log individual articles for debugging
                for i, article in enumerate(articles, 1):
                    title_preview = article.get("title", "No title")[:50]
                    logger.info(f"  ✅ Article {i}: {title_preview}...")

                # If centralized LLM failed to extract articles, fall back to BeautifulSoup
                if not articles or len(articles) == 0:
                    logger.warning(
                        "WARNING: Centralized LLM extracted 0 articles - falling back to BeautifulSoup parsing"
                    )
                    return await self._extract_with_beautifulsoup(
                        original_html or cleaned_html, page_url
                    )

                return articles

            except json.JSONDecodeError as e:
                logger.error(
                    f"❌ ERROR: Failed to parse centralized LLM JSON response: {e}"
                )
                logger.warning(
                    "WARNING: JSON parsing failed - falling back to BeautifulSoup parsing"
                )
                return await self._extract_with_beautifulsoup(
                    original_html or cleaned_html, page_url
                )

        except Exception as e:
            logger.error(f"❌ ERROR: Centralized LLM extraction error: {e}")
            logger.warning(
                "WARNING: Centralized LLM completely failed - falling back to BeautifulSoup parsing"
            )
            try:
                return await self._extract_with_beautifulsoup(
                    original_html or cleaned_html, page_url
                )
            except Exception as fallback_error:
                logger.error(
                    f"❌ ERROR: BeautifulSoup fallback also failed: {fallback_error}"
                )
                return []

    async def _extract_with_beautifulsoup(
        self, html_content: str, page_url: str
    ) -> List[Dict[str, str]]:
        """Extract articles using BeautifulSoup when centralized LLM fails"""
        try:
            logger.info("INFO: Starting BeautifulSoup extraction as fallback")
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(html_content, "html.parser")
            articles = []

            # Try multiple selectors for robust extraction
            article_selectors = [
                ".article-list .list-category article",  # Primary Drishti selector
                "article",  # Generic article tags
                ".article-content",  # Alternative article containers
                ".news-item",  # Alternative news containers
                ".content-item",  # Fallback content containers
                'div[class*="article"]',  # Divs with "article" in class name
                'div[class*="news"]',  # Divs with "news" in class name
            ]

            containers = []
            used_selector = None

            for selector in article_selectors:
                containers = soup.select(selector)
                if containers and len(containers) > 0:
                    used_selector = selector
                    logger.info(
                        f"SUCCESS: Found {len(containers)} containers using selector: {selector}"
                    )
                    break

            if not containers:
                logger.warning(
                    "WARNING: No article containers found with CSS selectors - trying text-based extraction"
                )
                # Fallback: Parse as cleaned text structure
                articles = self._extract_from_cleaned_text(html_content)
                return articles

            for i, container in enumerate(containers, 1):
                try:
                    # Extract title using multiple strategies
                    title = self._extract_title_from_container(container, i)

                    # Extract content using multiple strategies
                    content = self._extract_content_from_container(container)

                    # Validate article quality
                    if self._validate_article_content(title, content):
                        articles.append(
                            {
                                "title": title,
                                "content": content,
                                "category": self._detect_category_from_content(
                                    title, content
                                ),
                                "article_number": i,
                            }
                        )
                        logger.info(f"SUCCESS: Extracted article {i}: {title[:50]}...")
                    else:
                        logger.debug(
                            f"❌ Skipped low-quality content for container {i}"
                        )

                except Exception as e:
                    logger.warning(f"WARNING: Error extracting article {i}: {e}")
                    continue

            logger.info(f"🎉 BeautifulSoup extracted {len(articles)} valid articles")
            return articles

        except Exception as e:
            logger.error(f"❌ BeautifulSoup extraction failed: {e}")
            return []

    def _extract_title_from_container(self, container, article_num: int) -> str:
        """Extract title from article container using multiple strategies"""
        title_selectors = [
            "h1",  # Primary heading
            "h2",  # Secondary heading
            "h3",  # Tertiary heading
            ".article-title",  # Article title class
            ".news-title",  # News title class
            ".headline",  # Headline class
            ".title",  # Generic title class
            "strong",  # Strong text (often titles)
            "b",  # Bold text fallback
        ]

        for selector in title_selectors:
            title_elem = container.select_one(selector)
            if title_elem:
                title = title_elem.get_text(strip=True)
                if title and len(title) > 10:  # Ensure substantial title
                    return title

        # Fallback: use first substantial text in container
        all_text = container.get_text(strip=True)
        if all_text:
            lines = [line.strip() for line in all_text.split("\n") if line.strip()]
            for line in lines[:3]:  # Check first 3 lines
                if len(line) > 15 and len(line) < 200:  # Reasonable title length
                    return line

        return f"Article {article_num}"  # Final fallback

    def _extract_content_from_container(self, container) -> str:
        """Extract content from article container"""
        content_selectors = [
            ".article-detail p",  # Drishti specific paragraphs
            ".content p",  # Generic content paragraphs
            ".article-body p",  # Article body paragraphs
            "p",  # All paragraphs
            ".article-detail ul li",  # List items
            ".article-detail div",  # Content divs
            "div",  # All divs as fallback
            "span",  # Spans as final fallback
        ]

        content_parts = []

        for selector in content_selectors:
            elements = container.select(selector)
            for elem in elements:
                text = elem.get_text(strip=True)
                # Filter out short or repetitive content
                if text and len(text) > 20 and text not in content_parts:
                    content_parts.append(text)

        if content_parts:
            return " ".join(content_parts[:10])  # Limit to first 10 substantial parts

        # Fallback: get all text from container
        all_text = container.get_text(strip=True)
        return all_text if all_text else "Content not available"

    def _validate_article_content(self, title: str, content: str) -> bool:
        """Validate that extracted content is substantial enough"""
        if not title or len(title.strip()) < 10:
            return False
        if not content or len(content.strip()) < 50:  # Minimum content length
            return False

        # Filter out obvious non-articles
        skip_keywords = [
            "advertisement",
            "subscribe",
            "login",
            "cookie",
            "privacy",
            "terms",
        ]
        title_lower = title.lower()
        if any(keyword in title_lower for keyword in skip_keywords):
            return False

        return True

    def _detect_category_from_content(self, title: str, content: str) -> str:
        """Detect article category from title and content"""
        combined_text = (title + " " + content).lower()

        # Category keywords mapping
        category_keywords = {
            "Politics": [
                "election",
                "government",
                "minister",
                "parliament",
                "policy",
                "bill",
            ],
            "Economy": [
                "economic",
                "finance",
                "budget",
                "gdp",
                "inflation",
                "market",
                "trade",
            ],
            "International": [
                "china",
                "usa",
                "pakistan",
                "international",
                "bilateral",
                "treaty",
            ],
            "Social Issues": [
                "education",
                "health",
                "women",
                "child",
                "social",
                "welfare",
            ],
            "Environment": [
                "climate",
                "environment",
                "pollution",
                "green",
                "renewable",
                "carbon",
            ],
            "Technology": [
                "digital",
                "technology",
                "cyber",
                "internet",
                "ai",
                "innovation",
            ],
            "Defense": ["defense", "military", "army", "security", "border", "weapon"],
        }

        for category, keywords in category_keywords.items():
            if any(keyword in combined_text for keyword in keywords):
                return category

        return "Current Affairs"  # Default category

    def _extract_from_cleaned_text(self, html_content: str) -> List[Dict[str, str]]:
        """Extract articles from cleaned text when HTML structure parsing fails"""
        try:
            import html
            import re

            logger.info("🔍 Attempting text-based extraction from cleaned content")

            # Step 1: Fix encoding issues in the input
            if isinstance(html_content, bytes):
                html_content = html_content.decode("utf-8", errors="replace")

            # Step 2: Decode HTML entities and clean Unicode
            html_content = html.unescape(html_content)
            html_content = html_content.encode("utf-8", errors="ignore").decode("utf-8")

            # Step 3: Remove control characters and normalize whitespace
            html_content = re.sub(
                r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F-\x9F]", "", html_content
            )
            html_content = re.sub(r"\s+", " ", html_content)  # Normalize whitespace

            # Split content into potential articles based on patterns
            lines = [
                line.strip()
                for line in html_content.split("\n")
                if line.strip() and len(line) > 3
            ]

            # Step 4: Clean each line individually
            cleaned_lines = []
            for line in lines:
                # Additional Unicode cleaning per line
                try:
                    line = (
                        line.encode("ascii", errors="ignore").decode("ascii")
                        if line.isascii()
                        else line
                    )
                    # Only keep lines with readable text (filter out binary/corrupted content)
                    if any(c.isalpha() for c in line) and len(line.strip()) > 5:
                        cleaned_lines.append(line.strip())
                except:
                    continue  # Skip lines that can't be properly encoded

            lines = cleaned_lines
            logger.info(f"📝 Processing {len(lines)} cleaned text lines")

            articles = []
            current_article = None
            current_content = []

            # Look for article boundaries and titles
            for i, line in enumerate(lines):
                # Skip very short lines (likely formatting)
                if len(line) < 5:
                    continue

                # Check if this looks like a title (longer lines that could be headlines)
                is_potential_title = (
                    len(line) > 15
                    and len(line) < 200
                    and not line.endswith(".")  # Titles usually don't end with periods
                    and line
                    not in [
                        "Tags:",
                        "For Prelims:",
                        "For Mains:",
                        "Source:",
                        "Why in News?",
                    ]
                    and not line.startswith("GS Paper")
                    and ":" not in line[:20]  # Avoid lines with colons near the start
                    and "�" not in line
                    and "\ufffd" not in line
                    and "\\x" not in line  # Filter corrupted characters
                )

                # Look for article start patterns
                if is_potential_title and (
                    # Check if this could be a new article title
                    i == 0  # First line
                    or (i > 0 and len(lines[i - 1]) < 10)  # Previous line was short
                    or any(
                        keyword in line.lower()
                        for keyword in [
                            "civil society",
                            "government",
                            "india",
                            "policy",
                            "social",
                            "economic",
                            "political",
                        ]
                    )
                ):
                    # Save previous article if it exists
                    if current_article and current_content:
                        content_text = " ".join(current_content)
                        if len(content_text) > 100:  # Ensure substantial content
                            articles.append(
                                {
                                    "title": current_article,
                                    "content": content_text,
                                    "category": self._detect_category_from_content(
                                        current_article, content_text
                                    ),
                                    "article_number": len(articles) + 1,
                                }
                            )

                    # Start new article
                    current_article = line
                    current_content = []
                    logger.info(f"🎯 Found potential article title: {line[:50]}...")

                else:
                    # Add to current article content
                    if current_article:
                        # Filter out metadata lines
                        if not any(
                            skip in line.lower()
                            for skip in [
                                "prev",
                                "next",
                                "tags:",
                                "gs paper",
                                "for prelims",
                                "for mains",
                                "source:",
                            ]
                        ):
                            if len(line) > 10:  # Only substantial content
                                current_content.append(line)

            # Don't forget the last article
            if current_article and current_content:
                content_text = " ".join(current_content)
                if len(content_text) > 100:
                    articles.append(
                        {
                            "title": current_article,
                            "content": content_text,
                            "category": self._detect_category_from_content(
                                current_article, content_text
                            ),
                            "article_number": len(articles) + 1,
                        }
                    )

            # If we didn't find articles with title detection, create one big article
            if not articles and lines:
                # Find the main content by looking for substantial paragraphs
                substantial_content = []
                potential_title = None

                for line in lines[:20]:  # Check first 20 lines for title
                    if (
                        len(line) > 20
                        and len(line) < 150
                        and not any(
                            skip in line.lower() for skip in ["prev", "next", "tags"]
                        )
                    ):
                        potential_title = line
                        break

                for line in lines:
                    if len(line) > 20 and line not in [
                        "Tags:",
                        "For Prelims:",
                        "For Mains:",
                    ]:
                        substantial_content.append(line)

                if substantial_content:
                    from datetime import datetime

                    articles.append(
                        {
                            "title": potential_title
                            or "Daily Current Affairs - "
                            + str(datetime.now().strftime("%d-%m-%Y")),
                            "content": " ".join(
                                substantial_content[:50]
                            ),  # Limit content
                            "category": "Current Affairs",
                            "article_number": 1,
                        }
                    )

            logger.info(f"🎉 Text-based extraction found {len(articles)} articles")
            for i, article in enumerate(articles, 1):
                logger.info(f"  📰 Article {i}: {article['title'][:50]}...")

            return articles

        except Exception as e:
            logger.error(f"❌ Text-based extraction failed: {e}")
            return []

    def _extract_date_from_url(self, url: str) -> Optional[datetime]:
        """Extract date from URL format like /30-08-2025"""
        try:
            import re
            from datetime import datetime

            # Look for date pattern in URL
            date_match = re.search(r"/(\d{2}-\d{2}-\d{4})", url)
            if date_match:
                date_str = date_match.group(1)
                return datetime.strptime(date_str, "%d-%m-%Y")

            return None

        except Exception as e:
            logger.warning(f"Could not extract date from URL {url}: {e}")
            return None

    def _is_valid_article_url(self, url: str) -> bool:
        """Validate if URL is a valid Drishti article"""
        if not url or not isinstance(url, str):
            return False

        # Check if it's a Drishti IAS URL
        if "drishtiias.com" not in url:
            return False

        # Check for article patterns
        article_patterns = [
            "/current-affairs-news-analysis-editorials/",
            "/daily-updates/",
            "/news-analysis/",
            "/editorial-analysis/",
        ]

        return any(pattern in url for pattern in article_patterns)

    async def scrape_article_content(
        self, article_url: str
    ) -> Optional[DrishtiArticle]:
        """Scrape individual article content using BeautifulSoup for better parsing"""
        try:
            if not self.driver:
                await self.initialize_browser()

            logger.info(f"Scraping content from: {article_url}")

            # Navigate to article
            self.driver.get(article_url)

            # Wait for content to load
            time.sleep(3)  # Give time for dynamic content

            # Get page source and parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")

            # Extract article data
            article_data = self._extract_article_data(soup, article_url)

            if article_data:
                self._scraped_urls.add(article_url)
                self.scraping_stats["articles_scraped"] += 1
                logger.info(
                    f"SUCCESS: Successfully scraped: {article_data.title[:60]}..."
                )
                return article_data
            else:
                logger.warning(
                    f"WARNING: Could not extract content from: {article_url}"
                )
                return None

        except Exception as e:
            logger.error(f"❌ Error scraping article {article_url}: {e}")
            self.scraping_stats["errors"] += 1
            return None

    def _extract_article_data(
        self, soup: BeautifulSoup, article_url: str
    ) -> Optional[DrishtiArticle]:
        """Extract structured data from article HTML using BeautifulSoup"""
        try:
            # Extract title
            title = self._extract_title(soup)
            if not title:
                return None

            # Extract content
            content = self._extract_content(soup)
            if not content or len(content.strip()) < 100:
                return None

            # Extract metadata
            published_date = self._extract_date(soup)
            category = self._extract_category(article_url, soup)
            article_type = self._determine_article_type(article_url)

            return DrishtiArticle(
                title=title,
                content=content,
                url=article_url,
                published_date=published_date,
                category=category,
                article_type=article_type,
                source="Drishti IAS",
            )

        except Exception as e:
            logger.error(f"Error extracting article data: {e}")
            return None

    def _extract_title(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article title from various possible selectors"""
        title_selectors = [
            "h1.article-title",
            "h1.news-title",
            "h1.post-title",
            ".article-header h1",
            ".content-header h1",
            "h1",
            "title",
        ]

        for selector in title_selectors:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                if title and len(title) > 10:
                    return title

        return None

    def _extract_content(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract article content from various possible selectors"""
        content_selectors = [
            ".article-content",
            ".news-content",
            ".post-content",
            ".content-body",
            ".article-body",
            ".main-content",
            "article .content",
        ]

        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                # Remove unwanted elements
                for unwanted in content_div.find_all(
                    ["script", "style", "nav", "aside", ".advertisement"]
                ):
                    unwanted.decompose()

                # Extract clean text
                content = content_div.get_text(separator="\n", strip=True)

                # Clean up content
                content = re.sub(r"\n\s*\n", "\n\n", content)  # Normalize line breaks
                content = re.sub(r"\s+", " ", content)  # Normalize spaces

                if len(content.strip()) > 100:
                    return content.strip()

        # Fallback: try to get main content area
        main_content = soup.find("main") or soup.find("article") or soup.find(".main")
        if main_content:
            content = main_content.get_text(separator="\n", strip=True)
            content = re.sub(r"\n\s*\n", "\n\n", content)
            content = re.sub(r"\s+", " ", content)
            if len(content.strip()) > 100:
                return content.strip()

        return None

    def _extract_date(self, soup: BeautifulSoup) -> datetime:
        """Extract publication date from article"""
        date_selectors = [
            ".publish-date",
            ".article-date",
            ".news-date",
            "time",
            ".date-published",
            ".post-date",
        ]

        for selector in date_selectors:
            element = soup.select_one(selector)
            if element:
                date_text = element.get_text(strip=True)
                # Try to parse common date formats
                parsed_date = self._parse_date_string(date_text)
                if parsed_date:
                    return parsed_date

        # Check meta tags
        meta_date = (
            soup.find("meta", {"property": "article:published_time"})
            or soup.find("meta", {"name": "date"})
            or soup.find("meta", {"name": "publish_date"})
        )

        if meta_date:
            date_content = meta_date.get("content")
            if date_content:
                parsed_date = self._parse_date_string(date_content)
                if parsed_date:
                    return parsed_date

        # Default to current date if not found
        return datetime.utcnow()

    def _parse_date_string(self, date_str: str) -> Optional[datetime]:
        """Parse date string in various formats"""
        if not date_str:
            return None

        # Common date formats
        date_formats = [
            "%Y-%m-%d",
            "%d-%m-%Y",
            "%m/%d/%Y",
            "%d/%m/%Y",
            "%B %d, %Y",
            "%d %B %Y",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ]

        # Clean the date string
        date_str = re.sub(r"[^\w\s\-/:,]", "", date_str.strip())

        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        return None

    def _extract_category(self, article_url: str, soup: BeautifulSoup) -> str:
        """Extract or infer article category"""
        # Check for category in URL
        if "/editorial-analysis/" in article_url:
            return "Editorial Analysis"
        elif "/news-analysis/" in article_url:
            return "News Analysis"
        elif "/daily-updates/" in article_url:
            return "Daily Updates"
        elif "/weekly-current-affairs/" in article_url:
            return "Weekly Current Affairs"
        elif "/monthly-current-affairs/" in article_url:
            return "Monthly Current Affairs"

        # Check for category in HTML
        category_selectors = [
            ".category",
            ".article-category",
            ".news-category",
            ".post-category",
        ]

        for selector in category_selectors:
            element = soup.select_one(selector)
            if element:
                category = element.get_text(strip=True)
                if category:
                    return category

        return "Current Affairs"

    def _determine_article_type(self, article_url: str) -> str:
        """Determine article type based on URL pattern"""
        if "/editorial-analysis/" in article_url:
            return "editorial"
        elif "/news-analysis/" in article_url:
            return "analysis"
        else:
            return "current_affairs"

    async def process_articles_with_ai(
        self, articles: List[DrishtiArticle]
    ) -> List[DrishtiArticle]:
        """Process articles with Gemini AI for enhanced analysis"""
        if not articles:
            return []

        logger.info(f"Processing {len(articles)} Drishti articles with AI analysis")

        try:
            # Batch process articles for efficiency
            processed_articles = []
            batch_size = 5  # Process in batches to avoid token limits

            for i in range(0, len(articles), batch_size):
                batch = articles[i : i + batch_size]
                batch_processed = await self._process_article_batch_with_ai(batch)
                processed_articles.extend(batch_processed)

                # Small delay between batches
                await asyncio.sleep(1)

            self.scraping_stats["articles_processed"] = len(processed_articles)
            logger.info(
                f"SUCCESS: Successfully processed {len(processed_articles)} articles with AI"
            )

            return processed_articles

        except Exception as e:
            logger.error(f"❌ Error in AI processing: {e}")
            # Return original articles without AI enhancement
            return articles

    async def _process_article_batch_with_ai(
        self, articles: List[DrishtiArticle]
    ) -> List[DrishtiArticle]:
        """Process a batch of articles with single AI call for efficiency"""
        try:
            # Create batch prompt
            batch_data = []
            for article in articles:
                batch_data.append(
                    {
                        "title": article.title,
                        "content": article.content[
                            :2000
                        ],  # Limit content for token efficiency
                        "url": article.url,
                        "type": article.article_type,
                    }
                )

            # AI analysis prompt
            prompt = f"""
            Analyze the following {len(articles)} Drishti IAS articles for UPSC relevance and categorization:
            
            Articles to analyze:
            {json.dumps(batch_data, indent=2)}
            
            For each article, provide:
            1. UPSC relevance score (1-100)
            2. Relevant GS Paper (GS1/GS2/GS3/GS4 or combination)
            3. Key UPSC topics (max 5)
            4. 2-sentence summary
            5. Key learning points (max 3)
            
            Focus on UPSC exam relevance, current affairs importance, and potential question areas.
            """

            # Define response schema for structured output
            response_schema = {
                "type": "object",
                "properties": {
                    "analyses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "upsc_relevance": {"type": "number"},
                                "gs_paper": {"type": "string"},
                                "topics": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                                "summary": {"type": "string"},
                                "key_points": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            },
                            "required": [
                                "upsc_relevance",
                                "gs_paper",
                                "topics",
                                "summary",
                                "key_points",
                            ],
                        },
                    }
                },
                "required": ["analyses"],
            }

            # Get AI analysis using centralized LLM service
            llm_request = LLMRequest(
                task_type=TaskType.UPSC_ANALYSIS,
                content=prompt,
                provider_preference=ProviderPreference.QUALITY_OPTIMIZED,  # Use high-quality models for analysis
                max_tokens=2048,
                temperature=0.3,
            )

            response = await llm_service.process_request(llm_request)

            if response.success:
                logger.info(
                    f"✅ UPSC analysis completed using {response.provider_used}"
                )
                if isinstance(response.data, dict):
                    result = response.data
                else:
                    result = (
                        json.loads(response.data)
                        if isinstance(response.data, str)
                        else {"analyses": []}
                    )
            else:
                logger.error(f"❌ UPSC analysis failed: {response.error_message}")
                result = {"analyses": []}

            # Apply AI analysis to articles
            processed_articles = []
            analyses = result.get("analyses", [])

            for i, article in enumerate(articles):
                if i < len(analyses):
                    analysis = analyses[i]
                    article.upsc_relevance = analysis.get("upsc_relevance", 50)
                    article.gs_paper = analysis.get("gs_paper", "")
                    article.tags = analysis.get("topics", [])
                    article.summary = analysis.get("summary", "")
                    article.key_points = analysis.get("key_points", [])

                processed_articles.append(article)

            return processed_articles

        except Exception as e:
            logger.error(f"Error in AI batch processing: {e}")
            # Return articles without AI enhancement
            return articles

    async def scrape_daily_current_affairs(
        self, max_articles: int = 20, target_date: Optional[datetime] = None
    ) -> List[DrishtiArticle]:
        """Scrape daily current affairs from Drishti IAS with NEW direct content extraction"""
        if target_date is None:
            target_date = datetime.now()

        date_str = target_date.strftime("%d-%m-%Y")
        logger.info(
            f"🔄 Starting NEW direct content extraction from Drishti IAS for {date_str}"
        )
        self.scraping_stats["start_time"] = time.time()

        try:
            # Chrome-free approach - no browser initialization needed
            articles = []

            # Generate date-specific URLs with fallback strategy
            date_urls = self.generate_date_specific_urls(target_date)

            # Only use the dated URL(s)
            daily_urls = date_urls["daily_current_affairs"]

            logger.info(
                f"📍 Generated {len(daily_urls)} date-specific URLs for {date_str}"
            )

            for url in daily_urls:
                logger.info(f"🔍 Processing URL: {url}")
                self._last_used_urls.append(url)

                # NEW APPROACH: Extract articles directly from page content
                page_articles = await self.extract_articles_from_page_content(url)

                if page_articles:
                    logger.info(
                        f"SUCCESS: Extracted {len(page_articles)} articles from {url}"
                    )
                    articles.extend(page_articles)

                    # Limit total articles
                    if len(articles) >= max_articles:
                        articles = articles[:max_articles]
                        logger.info(f"🎯 Reached max articles limit ({max_articles})")
                        break
                else:
                    logger.warning(f"WARNING: No articles found on {url}")

                # Delay between pages
                await asyncio.sleep(2)

            if not articles:
                logger.warning(
                    "WARNING: No articles found with new direct extraction method"
                )
                return []

            # Process with AI
            logger.info(
                f"INFO: Processing {len(articles)} articles with AI enhancement"
            )
            articles = await self.process_articles_with_ai(articles)

            self.scraping_stats["processing_time"] = (
                time.time() - self.scraping_stats["start_time"]
            )
            logger.info(
                f"SUCCESS: Successfully extracted {len(articles)} daily current affairs articles in {self.scraping_stats['processing_time']:.2f}s using NEW direct method"
            )

            return articles

        except Exception as e:
            logger.error(f"❌ Error in NEW daily current affairs scraping: {e}")
            return []

    async def scrape_editorial_content(
        self, max_articles: int = 10
    ) -> List[DrishtiArticle]:
        """Scrape editorial content from Important Editorials section"""
        logger.info("📰 Starting editorial content scraping from Drishti IAS")

        try:
            # Chrome-free approach using HTTP + Gemini LLM
            editorial_url = self.base_target_urls["important_editorials"]
            logger.info(f"🎯 Extracting editorial content from: {editorial_url}")

            # Use the same Chrome-free extraction method as daily content
            articles = await self.extract_articles_from_page_content(editorial_url)

            # Mark all articles as editorial type and limit results
            limited_articles = []
            for article in articles[:max_articles]:
                article.article_type = "editorial"  # Mark as editorial
                article.category = "editorial"  # Set category
                limited_articles.append(article)

            # Update stats
            self.scraping_stats["articles_scraped"] = len(limited_articles)
            self.scraping_stats["processing_time"] = (
                time.time() - self.scraping_stats["start_time"]
            )

            logger.info(
                f"SUCCESS: Successfully scraped {len(limited_articles)} editorial articles using Chrome-free method"
            )
            return limited_articles

        except Exception as e:
            logger.error(f"❌ Error in editorial scraping: {e}")
            return []
        finally:
            pass  # No browser cleanup needed in Chrome-free version

    async def _extract_title_from_container(self, container) -> Optional[str]:
        """Extract article title from container element - SIMPLIFIED"""
        try:
            # Simplified approach with error handling
            title_selectors = [
                "h1",
                "h2",
                "h3",
                "h4",  # Headings first
                "a",  # Links
                ".title",  # Title classes
            ]

            for selector in title_selectors:
                try:
                    elements = container.find_elements(By.CSS_SELECTOR, selector)
                    for element in elements[:3]:  # Check max 3 elements per selector
                        try:
                            title = element.text.strip()
                            if (
                                title and len(title) > 5 and len(title) < 200
                            ):  # Reasonable title length
                                logger.debug(f"📝 Title found: {title[:50]}...")
                                return title
                        except:
                            continue
                except:
                    continue

            # Fallback: Get first text content from container
            try:
                container_text = container.text.strip()
                if container_text:
                    # Take first line as potential title
                    first_line = container_text.split("\n")[0].strip()
                    if first_line and len(first_line) > 5:
                        logger.debug(f"📝 Fallback title: {first_line[:50]}...")
                        return first_line
            except:
                pass

            logger.warning("WARNING: No title found in container")
            return "Untitled Article"

        except Exception as e:
            logger.error(f"❌ Error extracting title: {e}")
            return "Untitled Article"

    async def _extract_content_from_container(self, container) -> Optional[str]:
        """Extract article content from container element - SIMPLIFIED & FAST"""
        try:
            # SUPER SIMPLIFIED: Just get the text content from container
            container_text = container.text.strip()
            if container_text and len(container_text) > 30:
                # Limit content to prevent hanging and excessive processing
                limited_content = container_text[:3000]  # Max 3000 characters
                logger.debug(f"📄 Content extracted: {len(limited_content)} characters")
                return limited_content

            logger.warning("WARNING: No meaningful content in container")
            return "No content available"

        except Exception as e:
            logger.error(f"❌ Content extraction error: {e}")
            return "Content extraction failed"

    async def _extract_date_from_container(
        self, container, page_url: str
    ) -> Optional[datetime]:
        """Extract published date from container or infer from URL"""
        try:
            # Try to find date elements within container
            date_selectors = [
                ".date",
                ".published-date",
                ".article-date",
                ".timestamp",
                ".publish-time",
                "time",
            ]

            for selector in date_selectors:
                try:
                    element = container.find_element(By.CSS_SELECTOR, selector)
                    date_text = element.text.strip()
                    if date_text:
                        # Try to parse various date formats
                        parsed_date = self._parse_date_text(date_text)
                        if parsed_date:
                            return parsed_date
                except:
                    continue

            # Fallback: extract date from page URL
            # URL format: .../news-analysis/30-08-2025
            date_match = re.search(r"(\d{2})-(\d{2})-(\d{4})", page_url)
            if date_match:
                day, month, year = date_match.groups()
                return datetime(int(year), int(month), int(day))

            # Default to current date
            logger.warning("WARNING: Using current date as fallback")
            return datetime.now()

        except Exception as e:
            logger.error(f"❌ Error extracting date: {e}")
            return datetime.now()

    async def _extract_category_from_container(self, container) -> Optional[str]:
        """Extract category from container element"""
        try:
            # Try to find category elements
            category_selectors = [
                ".category",
                ".tag",
                ".subject",
                ".article-category",
                ".news-category",
            ]

            for selector in category_selectors:
                try:
                    element = container.find_element(By.CSS_SELECTOR, selector)
                    category = element.text.strip()
                    if category:
                        return category
                except:
                    continue

            # Default category for current affairs
            return "Current Affairs"

        except Exception as e:
            logger.error(f"❌ Error extracting category: {e}")
            return "Current Affairs"

    async def _extract_content_sections_fallback(
        self, page_url: str
    ) -> List[Dict[str, str]]:
        """Fallback method to extract content sections from the page"""
        try:
            logger.info("🔄 Using fallback content extraction method")

            # Get page source and parse with BeautifulSoup
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, "html.parser")

            sections = []

            # Look for article sections in the page
            article_selectors = [
                "article",
                ".article",
                ".news-item",
                ".content-section",
                ".analysis-section",
            ]

            for selector in article_selectors:
                elements = soup.select(selector)
                for element in elements:
                    # Extract title
                    title_elem = element.find(["h1", "h2", "h3", "h4"])
                    title = (
                        title_elem.get_text(strip=True) if title_elem else "Untitled"
                    )

                    # Extract content
                    # Remove title from content
                    if title_elem:
                        title_elem.decompose()

                    content = element.get_text(separator="\n\n", strip=True)

                    if title and content and len(content) > 100:
                        sections.append({"title": title, "content": content})

            logger.info(f"📄 Fallback method extracted {len(sections)} sections")
            return sections

        except Exception as e:
            logger.error(f"❌ Fallback content extraction failed: {e}")
            return []

    def _parse_date_text(self, date_text: str) -> Optional[datetime]:
        """Parse various date text formats"""
        try:
            # Common date patterns
            patterns = [
                r"(\d{1,2})[/-](\d{1,2})[/-](\d{4})",  # DD/MM/YYYY or DD-MM-YYYY
                r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})",  # YYYY/MM/DD or YYYY-MM-DD
                r"(\d{1,2})\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})",  # DD Mon YYYY
            ]

            for pattern in patterns:
                match = re.search(pattern, date_text, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) == 3:
                        if groups[1].isalpha():  # Month name format
                            month_names = {
                                "jan": 1,
                                "feb": 2,
                                "mar": 3,
                                "apr": 4,
                                "may": 5,
                                "jun": 6,
                                "jul": 7,
                                "aug": 8,
                                "sep": 9,
                                "oct": 10,
                                "nov": 11,
                                "dec": 12,
                            }
                            month = month_names.get(groups[1][:3].lower())
                            if month:
                                return datetime(int(groups[2]), month, int(groups[0]))
                        else:  # Numeric format
                            # Determine if it's DD/MM/YYYY or YYYY/MM/DD
                            if len(groups[0]) == 4:  # YYYY/MM/DD
                                return datetime(
                                    int(groups[0]), int(groups[1]), int(groups[2])
                                )
                            else:  # DD/MM/YYYY
                                return datetime(
                                    int(groups[2]), int(groups[1]), int(groups[0])
                                )

            return None

        except Exception as e:
            logger.error(f"❌ Error parsing date text '{date_text}': {e}")
            return None

    def get_scraping_stats(self) -> Dict[str, Any]:
        """Get current scraping statistics - synchronous version"""
        performance = {
            "articles_scraped": self.scraping_stats["articles_scraped"],
            "articles_processed": self.scraping_stats["articles_processed"],
            "articles_saved": self.scraping_stats["articles_saved"],
            "errors": self.scraping_stats["errors"],
            "start_time": self.scraping_stats["start_time"],
            "processing_time": time.time()
            - (self.scraping_stats["start_time"] or time.time()),
        }

        return {
            "performance": performance,
            "urls_scraped": len(self._scraped_urls),
            "success_rate": (
                performance["articles_saved"] / performance["articles_scraped"]
            )
            * 100
            if performance["articles_scraped"] > 0
            else 0,
            "scraper_status": "active",  # Chrome-free scraper is always active
            # Report only the URLs actually used in this scrape if available
            "target_urls": self._last_used_urls or self.target_urls,
        }

    def __del__(self):
        """Cleanup resources on object destruction (Chrome-free version)"""
        pass  # No browser cleanup needed in Chrome-free version
