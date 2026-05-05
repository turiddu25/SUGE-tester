"""Run Section 10 calibration tests against the live /api/mark endpoint."""

from __future__ import annotations

import json
import time

import httpx

URL = "http://127.0.0.1:8765/api/mark"
QID = "study_q12"

TESTS = [
    (
        "A",
        "Perfect",
        "expect 3/3",
        "GM = 1/(1-V). With V=0.52, GM = 1/0.48 = 2.08. With V=0.58, GM = 1/0.42 = 2.38. "
        "The improvement of 0.06 in V produces a 0.30 increase in GM, demonstrating compounding amplification.",
    ),
    (
        "B",
        "Right method, arithmetic error",
        "expect 1.5-2/3",
        "GM = 1/(1-V). V=0.52 gives 1/0.48 = 2.5 (wrong, should be 2.08). V=0.58 gives 1/0.42 = 2.5. Big improvement.",
    ),
    (
        "C",
        "Conceptual, no calculation",
        "expect 0.5-1/3",
        "Higher V means a much bigger growth multiplier because of compounding. Small changes in V produce big changes in GM.",
    ),
    (
        "D",
        "Empty / nonsense",
        "expect 0/3",
        "I don't know.",
    ),
    (
        "E",
        "Verbose but irrelevant",
        "expect 0/3",
        "Growth is very important for startups. They should focus on retention and CGMs to build a strong product.",
    ),
]


def main() -> None:
    print(f"Calibration: study_q12 (Growth Multiplier, 3 marks)\n")
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass
    for code, name, expected, answer in TESTS:
        t0 = time.time()
        try:
            resp = httpx.post(
                URL,
                json={"question_id": QID, "student_answer": answer},
                timeout=180,
            )
            resp.raise_for_status()
            r = resp.json()["result"]
        except Exception as exc:
            print(f"Test {code} — {name}: ERROR {exc}")
            continue
        elapsed = time.time() - t0
        if r.get("error"):
            print(f"Test {code} — {name}: API error: {r.get('message')}")
            continue
        awarded = r.get("marks_awarded")
        total = r.get("marks_total")
        fb = (r.get("general_feedback") or "").replace("\n", " ")[:160]
        print(f"Test {code} - {name} ({expected})")
        print(f"  -> {awarded}/{total}   [{elapsed:.1f}s]")
        print(f"  feedback: {fb}")
        print()


if __name__ == "__main__":
    main()
