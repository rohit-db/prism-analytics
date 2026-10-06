"""Resolve the dashboard asset registry from the seed file (fail-soft).

Precedence mirrors ``server/auth/users.py``: a repo seed file is the default
source; a Lakebase override table can layer on later (PR3b). This module is the
single seam the server uses for dashboard ids (grants, resource catalog, embed
default), and it backs ``GET /api/assets`` for the frontend.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

from ..lakebase import connection as _connection, enabled as _lb_enabled

logger = logging.getLogger("server.assets.registry")

# Repo-relative seed. Override with ASSETS_SEED_FILE.
_DEFAULT_SEED = str(Path(__file__).resolve().parent / "dashboards.seed.json")
_SEED_PATH = os.environ.get("ASSETS_SEED_FILE", _DEFAULT_SEED).strip() or _DEFAULT_SEED

# ============================================================ Lakebase storage
ASSET_TABLE = "apex_asset_registry"
ASSET_META_TABLE = "apex_asset_registry_meta"

SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS {ASSET_TABLE} (
    asset_key   VARCHAR(128) PRIMARY KEY,
    spec        JSONB        NOT NULL,
    sort_order  INT          NOT NULL DEFAULT 0,
    active      BOOLEAN      NOT NULL DEFAULT TRUE,
    updated_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS {ASSET_META_TABLE} (
    id           INT PRIMARY KEY DEFAULT 1,
    seeded       BOOLEAN NOT NULL DEFAULT FALSE,
    seeded_at    TIMESTAMPTZ,
    CONSTRAINT {ASSET_META_TABLE}_singleton CHECK (id = 1)
);
"""


def _lakebase_list() -> list[dict]:
    with _connection() as conn:
        cur = conn.execute(
            f"SELECT asset_key, spec, sort_order, active FROM {ASSET_TABLE} "
            "ORDER BY sort_order, asset_key"
        )
        return [
            {"asset_key": r[0], "spec": r[1], "sort_order": r[2], "active": r[3]}
            for r in cur.fetchall()
        ]


def _lakebase_upsert(asset_key: str, spec: dict, sort_order: int, active: bool) -> None:
    from psycopg.types.json import Json

    with _connection() as conn:
        conn.execute(
            f"""
            INSERT INTO {ASSET_TABLE} (asset_key, spec, sort_order, active, updated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (asset_key) DO UPDATE SET
                spec       = EXCLUDED.spec,
                sort_order = EXCLUDED.sort_order,
                active     = EXCLUDED.active,
                updated_at = NOW()
            """,
            (asset_key, Json(spec), sort_order, active),
        )
        conn.commit()


def _lakebase_delete(asset_key: str) -> None:
    with _connection() as conn:
        conn.execute(f"DELETE FROM {ASSET_TABLE} WHERE asset_key = %s", (asset_key,))
        conn.commit()


def _read_seed_assets() -> dict[str, Any]:
    """Parse the seed file's assets object directly (no Lakebase), fail-soft."""
    try:
        data = json.loads(Path(_SEED_PATH).read_text(encoding="utf-8"))
        assets = data.get("assets")
        return assets if isinstance(assets, dict) else {}
    except Exception as exc:  # noqa: BLE001
        logger.warning("assets seed unreadable during import (%s)", exc)
        return {}


def _seed_import_once() -> None:
    """Import the seed rows into the table EXACTLY once (guarded by the meta marker).

    After this runs, the table is authoritative — an operator deleting all assets
    yields an empty registry that the seed does NOT resurrect.
    """
    with _connection() as conn:
        conn.execute(
            f"INSERT INTO {ASSET_META_TABLE} (id, seeded) VALUES (1, FALSE) "
            "ON CONFLICT (id) DO NOTHING"
        )
        cur = conn.execute(f"SELECT seeded FROM {ASSET_META_TABLE} WHERE id = 1")
        row = cur.fetchone()
        if row and row[0]:
            conn.commit()   # close the open transaction cleanly (INSERT above opened one)
            return  # already seeded — never import again
        from psycopg.types.json import Json

        for i, (key, spec) in enumerate(_read_seed_assets().items()):
            conn.execute(
                f"INSERT INTO {ASSET_TABLE} (asset_key, spec, sort_order, active) "
                "VALUES (%s, %s, %s, TRUE) ON CONFLICT (asset_key) DO NOTHING",
                (key, Json(spec), i),
            )
        conn.execute(
            f"UPDATE {ASSET_META_TABLE} SET seeded = TRUE, seeded_at = NOW() WHERE id = 1"
        )
        conn.commit()


def ensure_schema() -> None:
    """Create the asset tables + run the once-only seed import (best-effort)."""
    if not _lb_enabled():
        return
    with _connection() as conn:
        conn.execute(SCHEMA_SQL)
        conn.commit()
    # Seed import manages its own connection/transaction (separate from DDL above).
    _seed_import_once()


# The FilterKey vocabulary lives in frontend/src/config.ts FILTERS; the server
# validates seed/registry `filters` maps against the same known set.
_KNOWN_FILTER_KEYS = {"currentPeriod", "previousPeriod", "travelSector", "destinationRegion"}
_ASSET_KEY_RE = re.compile(r"^[a-z0-9_-]+$")


def validate_asset(asset_key: str, spec: dict) -> None:
    """Raise ValueError if the asset_key/spec is malformed."""
    if not asset_key or not _ASSET_KEY_RE.match(asset_key):
        raise ValueError("asset_key must match [a-z0-9_-]+")
    if len(asset_key) > 128:
        raise ValueError("asset_key must be at most 128 characters")
    if not isinstance(spec, dict):
        raise ValueError("spec must be an object")
    dashboard_id = spec.get("dashboardId")
    if not isinstance(dashboard_id, str) or not dashboard_id.strip():
        raise ValueError("spec.dashboardId is required and must be a non-empty string")
    filters = spec.get("filters") or {}
    if not isinstance(filters, dict):
        raise ValueError("spec.filters must be an object")
    bad = set(filters) - _KNOWN_FILTER_KEYS
    if bad:
        raise ValueError(f"unknown filter key(s): {sorted(bad)}")
    pages = spec.get("pages", [])
    if not isinstance(pages, list):
        raise ValueError("spec.pages must be a list")
    _validate_nav(spec.get("nav"))


_NAV_SECTIONS = {"insights", "exploration"}


def _validate_nav(nav: Any) -> None:
    """Validate the optional ``nav`` object that drives sidebar/route generation.

    Every field is individually optional (partial nav is allowed); when present
    each must be well-formed so the frontend can build a route from it.
    """
    if nav is None:
        return
    if not isinstance(nav, dict):
        raise ValueError("spec.nav must be an object")
    path = nav.get("path")
    if path is not None and (not isinstance(path, str) or not path.startswith("/")):
        raise ValueError("spec.nav.path must be a string starting with '/'")
    icon = nav.get("icon")
    if icon is not None and not isinstance(icon, str):
        raise ValueError("spec.nav.icon must be a string")
    section = nav.get("section")
    if section is not None and section not in _NAV_SECTIONS:
        raise ValueError(f"spec.nav.section must be one of {sorted(_NAV_SECTIONS)}")
    order = nav.get("order")
    # bool is an int subclass — reject it explicitly so True/False isn't an "order".
    if order is not None and (isinstance(order, bool) or not isinstance(order, int)):
        raise ValueError("spec.nav.order must be an integer")
    placeholder = nav.get("placeholder")
    if placeholder is not None and not isinstance(placeholder, bool):
        raise ValueError("spec.nav.placeholder must be a boolean")


def registry_writable() -> bool:
    return _lb_enabled()


def list_assets() -> list[dict]:
    """Resolved assets (Lakebase-or-seed): [{asset_key, spec, sort_order, active}]."""
    if _lb_enabled():
        try:
            return _lakebase_list()
        except Exception as e:  # noqa: BLE001
            logger.warning("Lakebase asset list failed, using seed: %s", e)
    return [
        {"asset_key": k, "spec": v, "sort_order": i, "active": True}
        for i, (k, v) in enumerate(_read_seed_assets().items())
    ]


def save_asset(asset_key: str, spec: dict, sort_order: int = 0, active: bool = True) -> None:
    validate_asset(asset_key, spec)
    if not _lb_enabled():
        raise RuntimeError("Asset management requires LAKEBASE_ENABLED=true")
    ensure_schema()
    _lakebase_upsert(asset_key, spec, sort_order, active)
    global _cache
    _cache = None  # invalidate resolved cache


def delete_asset(asset_key: str) -> None:
    if not _lb_enabled():
        raise RuntimeError("Asset management requires LAKEBASE_ENABLED=true")
    ensure_schema()
    _lakebase_delete(asset_key)
    global _cache
    _cache = None


_cache: dict[str, Any] | None = None


def load_registry() -> dict[str, Any]:
    """Resolved registry {"assets": {key: spec}} — Lakebase-or-seed; never raises."""
    if _lb_enabled():
        try:
            rows = _lakebase_list()
            return {"assets": {r["asset_key"]: r["spec"] for r in rows if r["active"]}}
        except Exception as e:  # noqa: BLE001
            logger.warning("Lakebase registry resolve failed, using seed: %s", e)
    # seed path (PR3a behavior, memoized)
    global _cache
    if _cache is not None:
        return _cache
    try:
        data = json.loads(Path(_SEED_PATH).read_text(encoding="utf-8"))
        assets = data.get("assets")
        if not isinstance(assets, dict):
            raise ValueError("seed missing an 'assets' object")
        _cache = {"assets": assets}
    except FileNotFoundError:
        logger.warning("assets seed not found at %s; empty registry", _SEED_PATH)
        _cache = {"assets": {}}
    except Exception as exc:  # noqa: BLE001 — fail soft
        logger.warning("assets seed unreadable (%s); empty registry", exc)
        _cache = {"assets": {}}
    return _cache


def _assets() -> dict[str, Any]:
    return load_registry().get("assets", {})


def dashboard_ids() -> list[str]:
    """Deduped physical dashboard ids across all assets, order-preserving."""
    out: list[str] = []
    for spec in _assets().values():
        did = (spec or {}).get("dashboardId")
        if did and did not in out:
            out.append(did)
    return out


def default_dashboard_id() -> str | None:
    """The first asset's dashboard id, or None when the registry is empty."""
    ids = dashboard_ids()
    return ids[0] if ids else None


def catalog_dashboards() -> list[dict]:
    """``[{id, name}]`` for the grantable-resource catalog, deduped by id."""
    out: list[dict] = []
    seen: set[str] = set()
    for spec in _assets().values():
        did = (spec or {}).get("dashboardId")
        if not did or did in seen:
            continue
        seen.add(did)
        out.append({"id": did, "name": (spec or {}).get("label") or did})
    return out
