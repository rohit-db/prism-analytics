"""Fail-soft loader for content.config.json — the user-facing copy layer.

Sibling of ``server/brand.py``: ``brand.config.json`` owns *identity* (name, colors,
logo) while ``content.config.json`` owns *copy* (hero text, KPI tile labels, suggested
questions, placeholders). Splitting them is what lets one build serve several verticals
— a retailer and a hotel group need different words, not just different colors.

Override the path with ``CONTENT_CONFIG_FILE``. Resolved per call (not at import) so an
operator can edit the file and see it on refresh, with no restart or rebuild. Missing or
malformed config falls back to the built-in Travel copy — never raises (AGENTS.md
fail-soft invariant).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("server.content")

_DEFAULT_CONTENT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "content.config.json"
)


def _content_path() -> str:
    return os.environ.get("CONTENT_CONFIG_FILE", "").strip() or _DEFAULT_CONTENT_PATH


# The current hardcoded Travel copy, so the default instance is byte-for-byte
# unchanged when no content.config.json exists.
DEFAULT_CONTENT: dict[str, Any] = {
    "hero": {
        "title": "Travel Intelligence",
        "subtitle": "Spend, sustainability and traveler insights across your programme.",
    },
    "kpis": [
        {"key": "spend", "label": "Total Spend", "format": "currency", "icon": "DollarSign"},
        {"key": "emissions", "label": "CO₂ Emissions", "format": "decimal", "icon": "Leaf",
         "unit": "t"},
        {"key": "travelers", "label": "Travelers", "format": "number", "icon": "Users"},
        {"key": "trips", "label": "Trips", "format": "number", "icon": "Plane"},
    ],
    "trend": {"title": "Spend Trend", "subtitle": "Monthly gross spend"},
    "suggestedQuestions": [
        "Total spend by category this year",
        "Top 5 countries by CO₂ emissions",
        "How is spend trending vs last year?",
    ],
    "askPlaceholder": "Ask about spend, emissions, bookings…",
}

_SECTIONS = ("hero", "trend")


def load_content() -> dict[str, Any]:
    """Return the parsed content config, or DEFAULT_CONTENT if unreadable."""
    try:
        with open(_content_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("content config must be a JSON object")
        # Shallow-merge over defaults so a partial config still works.
        merged = {**DEFAULT_CONTENT, **data}
        for key in _SECTIONS:
            merged[key] = {**DEFAULT_CONTENT[key], **(data.get(key) or {})}
        # Lists are replaced wholesale, not merged — a vertical that defines 3 KPI tiles
        # must not inherit a 4th from Travel. An absent, empty, or non-list value is
        # treated as "unset" and keeps the defaults, so the page is never tile-less.
        for key in ("kpis", "suggestedQuestions"):
            value = data.get(key)
            merged[key] = value if isinstance(value, list) and value else DEFAULT_CONTENT[key]
        return merged
    except FileNotFoundError:
        # Expected for the default instance; not worth a warning.
        return DEFAULT_CONTENT
    except Exception as exc:  # noqa: BLE001 — fail soft
        logger.warning("content.config.json unreadable (%s); using defaults", exc)
        return DEFAULT_CONTENT
