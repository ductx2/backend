import httpx
import logging
from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

_DATE_FORMATS = [
    "%d %b, %Y",
    "%B %d, %Y",
    "%d %B %Y",
    "%Y-%m-%d",
]


def _parse_date(date_str: str) -> datetime | None:
    cleaned = date_str.strip()
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(cleaned, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


class IDSAScraper:
    LISTING_URL = "https://idsa.in/comment-briefs/"
    BASE_URL = "https://idsa.in"

    async def _http_get(self, url: str) -> httpx.Response:
        async with httpx.AsyncClient(
            headers=_HEADERS, follow_redirects=True, timeout=30.0
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            return resp

    async def fetch_articles(self, hours: int = 48) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        try:
            listing_resp = await self._http_get(self.LISTING_URL)
        except httpx.HTTPError as exc:
            logger.error("IDSAScraper: failed to fetch listing page: %s", exc)
            return []

        soup = BeautifulSoup(listing_resp.text, "html.parser")
        candidates = _extract_listing_links(soup, cutoff)

        articles: list[dict] = []
        for href, title, pub_date in candidates:
            if href.lower().endswith(".pdf"):
                logger.info("Skipping PDF link: %s", href)
                continue

            full_url = href if href.startswith("http") else self.BASE_URL + href
            try:
                detail_resp = await self._http_get(full_url)
                detail_resp.raise_for_status()
            except httpx.HTTPError as exc:
                logger.error(
                    "IDSAScraper: failed to fetch article %s: %s", full_url, exc
                )
                continue

            content = _extract_article_content(detail_resp.text)
            headline = _extract_article_title(detail_resp.text) or title

            articles.append(
                {
                    "title": headline,
                    "content": content,
                    "source_url": full_url,
                    "source_site": "idsa",
                    "section": "comment-briefs",
                    "published_date": pub_date.isoformat(),
                }
            )

        return articles


def _extract_listing_links(
    soup: BeautifulSoup, cutoff: datetime
) -> list[tuple[str, str, datetime]]:
    results: list[tuple[str, str, datetime]] = []

    rows = soup.select("div.views-row")
    for row in rows:
        title_el = row.select_one("div.views-field-title a, .views-field-title a")
        date_el = row.select_one(
            "div.views-field-created span.field-content, .views-field-created span"
        )

        if not title_el or not date_el:
            continue

        href = title_el.get("href", "")
        title = title_el.get_text(strip=True)
        date_str = date_el.get_text(strip=True)

        pub_date = _parse_date(date_str)
        if pub_date is None:
            logger.warning(
                "IDSAScraper: could not parse date '%s' for '%s'", date_str, title
            )
            continue

        if pub_date < cutoff:
            logger.info(
                "IDSAScraper: skipping old article (date=%s): %s",
                pub_date.date(),
                title,
            )
            continue

        results.append((href, title, pub_date))

    return results


def _extract_article_content(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")

    for container_sel in [
        "div.field-item.even",
        "div.field-items",
        "div#ContentText",
        "article",
        "div.node-content",
        "div.content",
        "main",
    ]:
        container = soup.select_one(container_sel)
        if container:
            paragraphs = container.find_all("p")
            if paragraphs:
                return "\n\n".join(
                    p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)
                )
            text = container.get_text(separator="\n", strip=True)
            if text:
                return text

    return soup.get_text(separator="\n", strip=True)


def _extract_article_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "html.parser")

    for sel in ["h1.page-header", "h1", "h2.PageHead"]:
        el = soup.select_one(sel)
        if el:
            return el.get_text(strip=True)

    return None
