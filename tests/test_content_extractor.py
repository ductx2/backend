"""
Unit tests for UniversalContentExtractor.

Covers: HTML output, sanitization, quality score, newline preservation,
and newspaper3k paragraph wrapping.

All external dependencies are mocked — no real network calls.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Module path prefix for patches
_P = "app.services.content_extractor"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def extractor():
    """Create a fresh UniversalContentExtractor instance."""
    from app.services.content_extractor import UniversalContentExtractor

    return UniversalContentExtractor()


# ---------------------------------------------------------------------------
# Test 1: trafilatura returns HTML with <p> tags
# ---------------------------------------------------------------------------


@patch(f"{_P}.trafilatura")
@patch(f"{_P}.requests")
async def test_trafilatura_returns_html(mock_requests, mock_traf, extractor):
    """trafilatura extraction should return sanitized HTML containing <p> tags."""
    # Mock requests.get (used by _extract_with_trafilatura)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<html><body><p>Raw page</p></body></html>"
    mock_requests.get.return_value = mock_response

    # Mock trafilatura.extract to return HTML content
    mock_traf.extract.return_value = "<p>Extracted content paragraph.</p>"

    # Mock trafilatura.extract_metadata
    mock_metadata = MagicMock()
    mock_metadata.title = "Test Title For Quality"
    mock_metadata.author = "Test Author"
    mock_metadata.date = None
    mock_metadata.language = "en"
    mock_metadata.description = ""
    mock_metadata.sitename = ""
    mock_traf.extract_metadata.return_value = mock_metadata

    result = await extractor._extract_with_trafilatura("https://example.com/article")

    assert result is not None
    assert len(result.content) > 0
    assert "<p>" in result.content


# ---------------------------------------------------------------------------
# Test 2: _sanitize_html removes <script> tags
# ---------------------------------------------------------------------------


def test_sanitize_html_removes_script_tags(extractor):
    """Sanitization must strip <script> tags while preserving allowed content."""
    dirty = "<p>Hello</p><script>alert('xss')</script><p>World</p>"
    result = extractor._sanitize_html(dirty)

    # <script> tag must be gone
    assert "<script>" not in result
    # Allowed <p> content must survive
    assert "<p>Hello</p>" in result
    assert "<p>World</p>" in result


# ---------------------------------------------------------------------------
# Test 3: _calculate_quality_score counts <p> tags for HTML
# ---------------------------------------------------------------------------


def test_quality_score_counts_p_tags_for_html(extractor):
    """HTML with 3 <p> tags should yield a quality score > 0.3."""
    html_content = "<p>Para 1</p><p>Para 2</p><p>Para 3</p>"
    score = extractor._calculate_quality_score(html_content, "A Decent Title For Test")

    assert score > 0.3


# ---------------------------------------------------------------------------
# Test 4: _sanitize_html preserves newlines (regex fix validation)
# ---------------------------------------------------------------------------


def test_readability_newline_preserved(extractor):
    r"""Newline characters inside HTML text must survive sanitization (not collapsed to space)."""
    html_with_newline = "<p>Line one\nLine two</p>"
    result = extractor._sanitize_html(html_with_newline)

    assert "\n" in result


# ---------------------------------------------------------------------------
# Test 5: newspaper3k wraps plain text paragraphs in <p> tags
# ---------------------------------------------------------------------------


@patch(f"{_P}.asyncio")
@patch(f"{_P}.Article")
async def test_newspaper_wraps_text_in_p_tags(
    mock_article_cls, mock_asyncio, extractor
):
    """newspaper3k extraction should wrap article.text paragraphs in <p> tags."""
    # Build a fake article object
    mock_article = MagicMock()
    mock_article.text = "First paragraph\n\nSecond paragraph"
    mock_article.title = "Newspaper Test Article Title"
    mock_article.publish_date = None
    mock_article.tags = set()
    mock_article.authors = ["Test Author"]
    mock_article.summary = "A summary."
    mock_article.meta_description = ""
    mock_article.meta_keywords = []
    mock_article.canonical_link = ""
    mock_article.meta_lang = "en"

    # asyncio.to_thread should call _newspaper3k_extract synchronously
    # and return the mock article
    mock_asyncio.to_thread = AsyncMock(return_value=mock_article)

    result = await extractor._extract_with_newspaper3k("https://example.com/news")

    assert result is not None
    assert "<p>" in result.content
    assert "First paragraph" in result.content
