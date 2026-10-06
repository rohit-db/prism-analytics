"""Runtime app config — the seam that makes branding config-driven instead of baked.

``GET /api/config`` serves ``{brand, content}`` read from disk **per request**, so an
operator can edit ``brand.config.json`` / ``content.config.json`` and see the change on
refresh — no rebuild, no restart. Combined with ``BRAND_CONFIG_FILE`` /
``CONTENT_CONFIG_FILE``, one build serves any number of differently-branded instances.

Unauthenticated on purpose: the login page needs the brand before a session exists, and
the payload is pure presentation (names, colors, copy) with no tenant or customer data.
"""
from __future__ import annotations

from fastapi import APIRouter

from ..brand import load_brand
from ..content import load_content

router = APIRouter()


@router.get("/config")
def app_config() -> dict:
    """Brand identity + user-facing copy for the SPA's boot-time fetch."""
    return {"brand": load_brand(), "content": load_content()}
