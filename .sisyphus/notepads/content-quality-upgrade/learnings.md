# Content Quality Upgrade — Learnings

## Task 1: Replace Hardcoded Relevance Threshold (2026-02-23)

### What We Did
 Removed `RELEVANCE_THRESHOLD = 55` class constant from `KnowledgeCardPipeline`
 Added `relevance_threshold: int = 40` to `config.py` (renamed from `min_upsc_relevance`)
 Pipeline now reads threshold via `self.relevance_threshold = settings.relevance_threshold`
 Updated all usages: `main.py`, `optimized_rss_processor.py`, `simplified_flow.py`
 Wrote 5 TDD tests (2 structural + 3 boundary value tests) before implementing

### Key Learnings
 **TDD boundary values matter**: Testing score=39 (reject), score=40 (pass), score=50 (pass) gave confidence the boundary is correct
 **Single configurable value**: One `relevance_threshold` in config is cleaner than separate per-service thresholds
 **Rename is a breaking change**: `min_upsc_relevance` → `relevance_threshold` required updating 3 files beyond the pipeline itself — always grep for all usages before renaming
 **Class constants are inflexible**: Instance attributes set from `settings` allow per-test override via `monkeypatch` without touching the class

### Files Changed
 `backend/app/core/config.py` — field renamed + value changed 55→40
 `backend/app/services/knowledge_card_pipeline.py` — constant removed, instance attr added, 2 usages updated
 `backend/app/main.py` — updated settings reference
 `backend/app/services/optimized_rss_processor.py` — updated settings reference
 `backend/app/api/simplified_flow.py` — comment added for clarity
 `backend/tests/test_knowledge_card_pipeline.py` — 5 new TDD tests

### Evidence
 `evidence/content-quality-upgrade/task-1-threshold-pass.txt` — score=40 passes
 `evidence/content-quality-upgrade/task-1-threshold-filter.txt` — score=39 is filtered
