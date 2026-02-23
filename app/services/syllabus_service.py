"""
UPSC Syllabus Service — keyword-based topic matching.

Pure stdlib implementation (json, re, collections, pathlib).
No external dependencies.
"""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Optional


_SYLLABUS_PATH = Path(__file__).parent.parent / "data" / "upsc_syllabus.json"


class SyllabusService:
    """Loads the static UPSC syllabus JSON and provides keyword-based matching."""

    def __init__(self, syllabus_path: Optional[Path] = None) -> None:
        path = syllabus_path or _SYLLABUS_PATH
        with open(path, "r", encoding="utf-8") as f:
            self._data: dict = json.load(f)

        # Pre-compute a flat index for fast matching:
        # Each entry: {paper, topic, sub_topic, keywords: list[str], keyword_set: set[str]}
        self._index: list[dict] = []
        for paper_id, paper in self._data.get("papers", {}).items():
            for topic in paper.get("topics", []):
                for sub_topic in topic.get("sub_topics", []):
                    kw_list: list[str] = [
                        k.lower() for k in sub_topic.get("keywords", [])
                    ]
                    self._index.append(
                        {
                            "paper": paper_id,
                            "paper_name": paper.get("name", paper_id),
                            "topic": topic["name"],
                            "sub_topic": sub_topic["name"],
                            "keywords": kw_list,
                            "keyword_set": set(kw_list),
                        }
                    )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def match_topics(
        self,
        text: str,
        keywords: Optional[list[str]] = None,
        min_confidence: float = 0.1,
        max_results: int = 10,
    ) -> list[dict]:
        """Return syllabus sub-topics matching *text* (and optional *keywords*).

        Algorithm (keyword-overlap + TF-IDF-like weighting):
        1. Tokenise *text* into lowercase words.
        2. Build a term-frequency counter from the tokens.
        3. For each syllabus sub-topic, count how many of its keywords
           appear in the token set.  Weight each hit by its frequency in
           *text* (rewarding repeated mentions).
        4. Normalise by the sub-topic's keyword count to get a confidence
           score in [0, 1].
        5. If caller supplies explicit *keywords*, give a bonus for each
           that also appears in the sub-topic's keyword list.

        Returns a list of dicts sorted by descending confidence:
            [{"paper", "topic", "sub_topic", "confidence"}, ...]
        """
        tokens = self._tokenise(text)
        freq = Counter(tokens)
        token_set = set(tokens)

        # Optional caller-supplied keywords (lowered)
        extra_kw: set[str] = set()
        if keywords:
            for kw in keywords:
                extra_kw.update(self._tokenise(kw))

        results: list[dict] = []
        for entry in self._index:
            kw_set = entry["keyword_set"]
            kw_count = len(kw_set)
            if kw_count == 0:
                continue

            # Count keyword hits weighted by term frequency in text
            weighted_hits = 0.0
            raw_hits = 0
            for kw in kw_set:
                # A keyword can be multi-word; check if all its tokens appear
                kw_tokens = kw.split()
                if all(t in token_set for t in kw_tokens):
                    raw_hits += 1
                    # Weight: 1 + log-ish bonus for repeated mentions
                    max_freq = max(freq.get(t, 0) for t in kw_tokens)
                    weighted_hits += 1.0 + min(max_freq / 5.0, 1.0)

            if raw_hits == 0:
                continue

            # Base confidence: weighted hits / total keywords
            confidence = weighted_hits / kw_count

            # Bonus from caller-supplied keywords
            if extra_kw:
                extra_overlap = len(extra_kw & kw_set)
                if extra_overlap:
                    confidence += 0.15 * (extra_overlap / max(len(extra_kw), 1))

            confidence = min(confidence, 1.0)

            if confidence >= min_confidence:
                results.append(
                    {
                        "paper": entry["paper"],
                        "topic": entry["topic"],
                        "sub_topic": entry["sub_topic"],
                        "confidence": round(confidence, 4),
                    }
                )

        results.sort(key=lambda r: r["confidence"], reverse=True)
        return results[:max_results]

    def get_paper_topics(self, paper: str) -> list[dict]:
        """Return all topics (with sub-topics) for a given paper id.

        Example paper ids: "GS1", "GS2", "Prelims_GS", "Essay", etc.
        """
        paper_data = self._data.get("papers", {}).get(paper)
        if paper_data is None:
            return []

        out: list[dict] = []
        for topic in paper_data.get("topics", []):
            sub_topics = [
                {"name": st["name"], "keywords": st.get("keywords", [])}
                for st in topic.get("sub_topics", [])
            ]
            out.append({"name": topic["name"], "sub_topics": sub_topics})
        return out

    def get_all_keywords(self) -> set[str]:
        """Return the deduplicated set of every keyword across all papers."""
        kws: set[str] = set()
        for entry in self._index:
            kws.update(entry["keywords"])
        return kws

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenise(text: str) -> list[str]:
        """Lowercase and split on non-alphanumeric boundaries."""
        return re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", text.lower())
