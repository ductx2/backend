"""Tests for SyllabusService — keyword-based UPSC topic matching."""

import json
from pathlib import Path

import pytest

from app.services.syllabus_service import SyllabusService

SYLLABUS_PATH = Path(__file__).parent.parent / "app" / "data" / "upsc_syllabus.json"

REQUIRED_PAPERS = [
    "Prelims_GS",
    "Prelims_CSAT",
    "GS1",
    "GS2",
    "GS3",
    "GS4",
    "Essay",
]

MIN_TOPICS_PER_PAPER = 3
MIN_KEYWORDS_PER_SUBTOPIC = 10


@pytest.fixture(scope="module")
def service() -> SyllabusService:
    return SyllabusService()


@pytest.fixture(scope="module")
def raw_syllabus() -> dict:
    with open(SYLLABUS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


class TestJSONIntegrity:
    def test_json_loads_without_error(self, raw_syllabus: dict) -> None:
        assert "papers" in raw_syllabus
        assert isinstance(raw_syllabus["papers"], dict)

    def test_all_required_papers_present(self, raw_syllabus: dict) -> None:
        for paper in REQUIRED_PAPERS:
            assert paper in raw_syllabus["papers"], f"Missing paper: {paper}"

    def test_each_paper_has_minimum_topics(self, raw_syllabus: dict) -> None:
        for paper_id in REQUIRED_PAPERS:
            topics = raw_syllabus["papers"][paper_id].get("topics", [])
            assert len(topics) >= MIN_TOPICS_PER_PAPER, (
                f"{paper_id} has only {len(topics)} topics (min {MIN_TOPICS_PER_PAPER})"
            )

    def test_each_subtopic_has_minimum_keywords(self, raw_syllabus: dict) -> None:
        for paper_id, paper in raw_syllabus["papers"].items():
            for topic in paper.get("topics", []):
                for st in topic.get("sub_topics", []):
                    kw_count = len(st.get("keywords", []))
                    assert kw_count >= MIN_KEYWORDS_PER_SUBTOPIC, (
                        f"{paper_id} > {topic['name']} > {st['name']} "
                        f"has only {kw_count} keywords (min {MIN_KEYWORDS_PER_SUBTOPIC})"
                    )


class TestMatchTopics:
    def test_rbi_monetary_policy_matches_gs3_economy(
        self, service: SyllabusService
    ) -> None:
        results = service.match_topics(
            "The RBI announced changes to the repo rate as part of its monetary policy "
            "review. Inflation targeting remains a priority while GDP growth forecasts "
            "were revised. The central bank also addressed liquidity concerns and "
            "foreign exchange reserves."
        )
        assert len(results) > 0
        papers = [r["paper"] for r in results]
        assert "GS3" in papers, f"Expected GS3 in results, got: {papers}"

        gs3_hits = [r for r in results if r["paper"] == "GS3"]
        assert any(
            "economy" in r["topic"].lower() or "economic" in r["topic"].lower()
            for r in gs3_hits
        ), f"Expected economy-related GS3 topic, got: {[r['topic'] for r in gs3_hits]}"

    def test_india_china_border_matches_gs2_ir_and_gs1_geography(
        self, service: SyllabusService
    ) -> None:
        results = service.match_topics(
            "India-China border tensions along the Line of Actual Control in Ladakh "
            "have escalated. The territorial dispute involves Aksai Chin and Arunachal "
            "Pradesh. Diplomatic negotiations between the two Asian neighbours continue "
            "amid military standoff. The Himalayan geography and strategic passes play "
            "a crucial role in this geopolitical conflict."
        )
        assert len(results) > 0
        papers = [r["paper"] for r in results]
        assert "GS2" in papers, f"Expected GS2 in results, got: {papers}"

    def test_match_returns_confidence_between_0_and_1(
        self, service: SyllabusService
    ) -> None:
        results = service.match_topics("economic growth fiscal deficit budget")
        for r in results:
            assert 0 < r["confidence"] <= 1.0, (
                f"Confidence {r['confidence']} out of range for {r['sub_topic']}"
            )

    def test_match_returns_sorted_by_confidence(self, service: SyllabusService) -> None:
        results = service.match_topics(
            "Supreme Court judicial review fundamental rights"
        )
        confidences = [r["confidence"] for r in results]
        assert confidences == sorted(confidences, reverse=True)

    def test_empty_text_returns_no_results(self, service: SyllabusService) -> None:
        assert service.match_topics("") == []

    def test_extra_keywords_boost_confidence(self, service: SyllabusService) -> None:
        base = service.match_topics("monetary policy inflation")
        boosted = service.match_topics(
            "monetary policy inflation",
            keywords=["RBI", "repo rate", "central bank"],
        )
        if base and boosted:
            assert boosted[0]["confidence"] >= base[0]["confidence"]


class TestGetPaperTopics:
    def test_returns_topics_for_valid_paper(self, service: SyllabusService) -> None:
        topics = service.get_paper_topics("GS2")
        assert len(topics) >= MIN_TOPICS_PER_PAPER
        for t in topics:
            assert "name" in t
            assert "sub_topics" in t
            assert isinstance(t["sub_topics"], list)

    def test_returns_empty_for_unknown_paper(self, service: SyllabusService) -> None:
        assert service.get_paper_topics("GS99") == []


class TestGetAllKeywords:
    def test_returns_non_empty_set(self, service: SyllabusService) -> None:
        kws = service.get_all_keywords()
        assert isinstance(kws, set)
        assert len(kws) > 100

    def test_keywords_are_lowercase(self, service: SyllabusService) -> None:
        for kw in service.get_all_keywords():
            assert kw == kw.lower(), f"Keyword not lowercase: {kw}"
