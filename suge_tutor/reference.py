"""Parses the lecture notes markdown into searchable chunks for the /reference page."""

from __future__ import annotations

import re
from pathlib import Path

from .config import config

LECTURES_PATH = config.PROJECT_ROOT / "SUGE" / "SUGE_Full_Lectures.md"

_HEADING_RE = re.compile(r"^(#{1,4})\s+(.+?)\s*$", re.MULTILINE)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(text: str) -> str:
    s = _SLUG_RE.sub("-", text.lower()).strip("-")
    return s[:80] or "section"


def _shorten(text: str, n: int = 240) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def parse_chunks(path: Path | None = None) -> list[dict]:
    """Return a list of {section, body, slug, length} chunks split at H1/H2/H3."""
    path = path or LECTURES_PATH
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")

    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        return [{"section": "Lectures", "body": text, "slug": "lectures", "length": len(text)}]

    chunks: list[dict] = []
    breadcrumb: list[str] = []
    for i, m in enumerate(matches):
        level = len(m.group(1))
        title = m.group(2).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        # Maintain a breadcrumb up to this heading's level.
        breadcrumb = breadcrumb[: level - 1] + [title]
        if not body:
            continue
        chunks.append(
            {
                "section": " › ".join(breadcrumb),
                "title": title,
                "level": level,
                "slug": f"{i}-{_slugify(title)}",
                "body": body,
                "preview": _shorten(body, 220),
                "length": len(body),
            }
        )
    return chunks


# Parse once at import time. Lectures are static markdown; restart resets cache.
CHUNKS: list[dict] = parse_chunks()


# Key formulas — always-visible card on the reference page.
KEY_FORMULAS = [
    {
        "name": "Growth Multiplier (GM)",
        "formula": "GM = 1 / (1 - V)",
        "where": "V = vitality (CGM strength). Small changes in V cause disproportionately large changes in GM — the core compounding insight.",
    },
    {
        "name": "Customer Acquisition Cost (CAC)",
        "formula": "CAC = total_acquisition_spend / new_customers_acquired",
        "where": "Use only the spend for the cohort acquired in the same window. A high-LTV product can sustain a higher CAC.",
    },
    {
        "name": "Lifetime Value (LTV)",
        "formula": "LTV = ARPU × gross_margin × average_lifetime",
        "where": "Or, for a steady cohort with monthly churn r: LTV ≈ ARPU × gross_margin / r.",
    },
    {
        "name": "Healthy unit economics",
        "formula": "LTV / CAC ≥ 3  (and CAC payback < 12 months)",
        "where": "Below 3 means acquisition isn't earning enough lifetime margin; above 5 may mean you're under-spending on growth.",
    },
    {
        "name": "Network as Product (NaP)",
        "formula": "atomic networks → bridge networks → universal network",
        "where": "Build dense small networks first, then bridge them, then connect everyone. Sparse global networks die (Google+, Threads).",
    },
    {
        "name": "Activation inequality",
        "formula": "activated_user_retention ≫ unactivated_user_retention",
        "where": "Activation is the moment a user discovers core value. ~60% retention floor is the typical social-media activation benchmark.",
    },
]
