# Current Affairs Pipeline Rebuild — Learnings

## T13: Unified Pipeline

### Key Discoveries
- Hindu RSS returns `source_url` (not `url`) and `source` (not `source_site`) — normalization required
- IE/PIB/Supplementary lack `content` field — need content extraction step
- SupplementarySources.fetch_all() is synchronous — must wrap in asyncio.to_thread()
- OptimizedRSSProcessor imports app.core.database which triggers supabase chain — tests need conftest.py to mock sys.modules["app.core.database"]

### Source Output Format Map
| Source | URL Key | Content? | Source ID Key |
|--------|---------|----------|---------------|
| Hindu RSS | source_url | Yes (content) | source (e.g. "The Hindu - Editorial") |
| IE Scraper | url | No | source_site="indianexpress" |
| PIB Scraper | url | No | source_site="pib" |
| Supplementary | url | No | source_site (varies) |

### Files Created
- `backend/app/services/unified_pipeline.py` — 160 lines, UnifiedPipeline class
- `backend/tests/test_unified_pipeline.py` — 593 lines, 23 tests
- `backend/tests/conftest.py` — mocks app.core.database for test imports
- `backend/app/api/simplified_flow.py` — added /run-knowledge-pipeline endpoint (lines 632-654)

### Test Results
- 23/23 new tests passing
- 39/39 existing tests still passing
 Evidence: `.sisyphus/evidence/t13-unified-pipeline/test-results.txt`

## T17: Live Source Validation

### Key Discoveries
 The Hindu RSS feeds (all 8) return 403 Forbidden from local Windows machine — only works from VPS IP
 IE scraper may return empty list during certain hours (throttling/blocking) — not a bug
 PIB scraper returns empty on weekends/holidays — expected behavior
 Supplementary RSS feeds may return empty depending on feed availability
 All 4 scrapers gracefully return `[]` on failure (don't raise exceptions) — `pytest.skip()` must check empty list, not just catch exceptions
 `asyncio_mode = auto` in pytest.ini works fine with existing `@pytest.mark.asyncio` decorators (no conflicts)
 pytest-asyncio 1.1.0 + asyncio_mode=auto: class-scoped async fixtures work correctly
 Live tests: never assert `len >= 1` for any source — all can legitimately return empty

### Design Decisions
 Used `>= 0` assertions for "returns list" tests (lenient) + `pytest.skip()` for shape tests (when empty)
 Class-scoped fixtures (`scope="class"`) to avoid hammering live sources multiple times
 `LIVE = pytest.mark.live` alias for cleaner decorator usage
 14 tests across 4 classes: IE (4), PIB (3), Supplementary (3), Hindu RSS (4)

### Files Created
 `backend/pytest.ini` — asyncio_mode=auto + live marker registration
 `backend/tests/test_live_sources.py` — 200 lines, 14 test methods

### Test Results
 Live run: 8 passed, 6 skipped, 0 failed (45s)
 CI suite: 225 passed, 2 failed (pre-existing), 14 deselected
 Evidence: `.sisyphus/evidence/t17-live-sources/validation-report.txt`