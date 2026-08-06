"""Fail-soft loader for the shared brand.config.json.

The SAME brand.config.json the React app consumes drives the server-rendered
login page (server/auth/login.py) and the FastAPI app title, so the login screen
always matches the app. Missing/unreadable config falls back to built-in
defaults — never raises (AGENTS.md fail-soft invariant).
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger("server.brand")

# Repo root = parent of the server/ package dir. Override with BRAND_CONFIG_FILE to
# run several differently-branded instances off ONE build (the multi-vertical demo).
# Resolved per call, not at import, so editing the file is picked up on refresh.
_DEFAULT_BRAND_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "brand.config.json"
)


def _brand_path() -> str:
    return os.environ.get("BRAND_CONFIG_FILE", "").strip() or _DEFAULT_BRAND_PATH

DEFAULT_BRAND: dict[str, Any] = {
    "identity": {
        "appName": "Prism",
        "shortName": "Prism",
        "tagline": "Travel Intelligence",
        "logo": "/brand/logo.svg",
        "logoMark": "/brand/mark.svg",
        "favicon": "/brand/favicon.svg",
    },
    "colors": {
        "primary": "#2272b4",        # DuBois blue-600
        "primaryDark": "#0e538b",    # blue-700
        "primaryLight": "#d7edfe",   # blue-200 (focus ring tint)
        "accent": "#2272b4",         # same as primary (single-accent brand)
        "accentDark": "#0e538b",
        "sidebarFrom": "#04355d",    # blue-800 (deep) — login bg gradient start
        "sidebarVia": "#0e538b",     # blue-700
        "sidebarTo": "#2272b4",      # blue-600
        "bg": "#f7f7f7",             # secondary warm-grey
        "border": "#ebebeb",         # neutral-100
    },
    "typography": {"fontSans": "Inter, system-ui, -apple-system, sans-serif"},
}


def load_brand() -> dict[str, Any]:
    """Return the parsed brand config, or DEFAULT_BRAND if unreadable."""
    try:
        with open(_brand_path(), encoding="utf-8") as fh:
            data = json.load(fh)
        # Shallow-merge over defaults so a partial config still works.
        merged = {**DEFAULT_BRAND, **data}
        for key in ("identity", "colors", "typography"):
            merged[key] = {**DEFAULT_BRAND[key], **(data.get(key) or {})}
        return merged
    except Exception as exc:  # noqa: BLE001 — fail soft
        logger.warning("brand.config.json unreadable (%s); using defaults", exc)
        return DEFAULT_BRAND


def brand_color(name: str) -> str:
    """One brand color hex by semantic name, falling back to the default."""
    return load_brand()["colors"].get(name, DEFAULT_BRAND["colors"].get(name, "#4f46e5"))
