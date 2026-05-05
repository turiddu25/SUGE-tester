from __future__ import annotations

import random
from typing import Iterable

from . import db

TARGET_TOPIC_MARKS = {
    "activation_retention": 22,
    "compounding_growth": 17,
    "acquisition": 15,
    "organisation": 4,
    "investment": 2,
}

TARGET_TOTAL_MARKS = 60
TARGET_NUM_QUESTIONS = 16
TOLERANCE_PER_TOPIC = 2

PRIORITY_RANK = {"highest": 0, "high": 1, "medium": 2, "low": 3, None: 4}


def _sort_key_with_jitter(q: dict, jitter: dict[str, float]) -> tuple:
    # Priority first (lower index = higher priority), then random jitter within priority tier.
    # The jitter is what lets different seeds produce genuinely different papers.
    return (PRIORITY_RANK.get(q.get("priority"), 4), jitter.get(q["id"], 0.0))


def select_exam_questions(seed: int | None = None) -> list[dict]:
    rng = random.Random(seed)
    all_qs = db.list_questions()
    jitter = {q["id"]: rng.random() for q in all_qs}
    by_topic: dict[str, list[dict]] = {}
    for q in all_qs:
        by_topic.setdefault(q["topic"], []).append(q)

    selected: list[dict] = []
    selected_ids: set[str] = set()

    by_topic_selected: dict[str, list[dict]] = {t: [] for t in TARGET_TOPIC_MARKS}

    for topic, target in TARGET_TOPIC_MARKS.items():
        pool = list(by_topic.get(topic, []))
        pool.sort(key=lambda q: _sort_key_with_jitter(q, jitter))
        running = 0
        for q in pool:
            if running >= target:
                break
            if q["id"] in selected_ids:
                continue
            marks = int(q["marks"])
            if running + marks > target + TOLERANCE_PER_TOPIC:
                continue
            selected.append(q)
            selected_ids.add(q["id"])
            by_topic_selected[topic].append(q)
            running += marks

    # If over 16 questions, trim extras in two passes:
    #   pass 1 — only drops that keep each topic within ±tolerance,
    #   pass 2 — relaxed: any topic with >1 question (preserves coverage of all 5 topics).
    def _trim_pass(*, strict: bool) -> bool:
        candidates: list[tuple[int, int, int, str, str]] = []
        for topic, picks in by_topic_selected.items():
            target = TARGET_TOPIC_MARKS[topic]
            current = sum(int(p["marks"]) for p in picks)
            slack = current - (target - TOLERANCE_PER_TOPIC)
            if len(picks) <= 1:
                continue
            for p in picks:
                if strict and current - int(p["marks"]) < target - TOLERANCE_PER_TOPIC:
                    continue
                candidates.append((
                    slack,
                    PRIORITY_RANK.get(p.get("priority"), 4),
                    -int(p["marks"]),
                    topic,
                    p["id"],
                ))
        if not candidates:
            return False
        candidates.sort(reverse=True)
        _, _, _, topic, qid = candidates[0]
        nonlocal selected
        selected = [s for s in selected if s["id"] != qid]
        selected_ids.discard(qid)
        by_topic_selected[topic] = [s for s in by_topic_selected[topic] if s["id"] != qid]
        return True

    while len(selected) > TARGET_NUM_QUESTIONS:
        if not _trim_pass(strict=True):
            break
    while len(selected) > TARGET_NUM_QUESTIONS:
        if not _trim_pass(strict=False):
            break

    # Backfill if under 16 (rare).
    if len(selected) < TARGET_NUM_QUESTIONS:
        remaining = [q for q in all_qs if q["id"] not in selected_ids]
        remaining.sort(key=lambda q: _sort_key_with_jitter(q, jitter))
        for q in remaining:
            if len(selected) >= TARGET_NUM_QUESTIONS:
                break
            selected.append(q)
            selected_ids.add(q["id"])

    selected.sort(key=lambda q: (
        list(TARGET_TOPIC_MARKS.keys()).index(q["topic"]) if q["topic"] in TARGET_TOPIC_MARKS else 99,
        -int(q["marks"]),
        q["id"],
    ))
    return selected


def topic_breakdown(questions: Iterable[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for q in questions:
        out[q["topic"]] = out.get(q["topic"], 0) + int(q["marks"])
    return out
