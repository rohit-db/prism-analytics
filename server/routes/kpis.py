"""Live headline KPIs for the landing page.

Runs a small ``MEASURE()`` query against the ``travel_metrics`` metric view AS
the logged-in tenant's Service Principal — so the *same* Unity Catalog row filter
that scopes the embedded dashboards and Genie also scopes these numbers — falling
back to the app Service Principal when no tenant is resolved.

Fails soft on purpose: any misconfiguration or query error returns
``{"ok": false}`` with HTTP 200 so the landing page simply hides the KPI strip
instead of hard-failing.
"""
from __future__ import annotations

import logging
import os
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config import UC_CATALOG, UC_SCHEMA, get_sp_bearer

logger = logging.getLogger("server.routes.kpis")

router = APIRouter()

# The metric view backing the KPIs. Defaults to <catalog>.<schema>.travel_metrics
# and can be overridden with KPI_METRIC_VIEW.
_METRIC_VIEW = (
    os.environ.get("KPI_METRIC_VIEW")
    or (f"{UC_CATALOG}.{UC_SCHEMA}.travel_metrics" if UC_CATALOG and UC_SCHEMA else "")
).strip()

# metric-view measure -> response key. Travel is the default; other verticals override
# with KPI_MEASURES ("measure:key, measure:key, …") so one build serves any vertical.
# The response KEY is the contract with content.config.json's `kpis[].key`, which
# supplies the human label — server owns measure→key, config owns key→label.
_DEFAULT_MEASURES = [
    ("gross_spend_usd", "spend"),
    ("total_emissions_advito", "emissions"),
    ("traveler_count", "travelers"),
    ("component_count", "trips"),
]

# Metric-view identifiers are interpolated into SQL, so accept only safe identifiers.
_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _parse_measures(raw: str | None) -> list[tuple[str, str]]:
    """Parse "measure:key, measure:key" into pairs, falling back to Travel defaults.

    Fail-soft per the AGENTS.md invariant: any malformed entry is skipped, and an
    entirely unusable value falls back to the defaults rather than raising.
    """
    if not raw or not raw.strip():
        return _DEFAULT_MEASURES
    pairs: list[tuple[str, str]] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        measure, _, key = chunk.partition(":")
        measure, key = measure.strip(), key.strip()
        if not measure or not key:
            logger.warning("KPI_MEASURES entry %r is not measure:key; skipping", chunk)
            continue
        if not _IDENT_RE.match(measure) or not _IDENT_RE.match(key):
            logger.warning("KPI_MEASURES entry %r is not a safe identifier; skipping", chunk)
            continue
        pairs.append((measure, key))
    if not pairs:
        logger.warning("KPI_MEASURES produced no usable pairs; using Travel defaults")
        return _DEFAULT_MEASURES
    return pairs


_MEASURES = _parse_measures(os.environ.get("KPI_MEASURES"))

# The metric view's date dimension used to window every KPI query.
_DATE_COLUMN = (os.environ.get("KPI_DATE_COLUMN") or "travel_start_date").strip()
if not _IDENT_RE.match(_DATE_COLUMN):
    logger.warning("KPI_DATE_COLUMN %r is not a safe identifier; using travel_start_date",
                   _DATE_COLUMN)
    _DATE_COLUMN = "travel_start_date"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _valid_date(value: str, fallback: str) -> str:
    """Only allow plain ISO dates through to the SQL (guards against injection)."""
    return value if _DATE_RE.match(value or "") else fallback


def _resolve_token(request: Request) -> str | None:
    """Prefer the logged-in tenant SP token (row-scoped), else the app SP token."""
    try:
        from ..tenants.resolver import resolve_tenant_sp

        resolved = resolve_tenant_sp(request)
        if resolved:
            return resolved[0]
    except Exception:  # noqa: BLE001 - never block KPIs on the isolation layer
        pass
    return get_sp_bearer()


def _measure_row(token: str, date_from: str, date_to: str) -> dict:
    from ..tenants.unity_catalog import run_sql_as

    select = ", ".join(f"MEASURE({m}) AS {k}" for m, k in _MEASURES)
    sql = (
        f"SELECT {select} FROM {_METRIC_VIEW} "
        f"WHERE {_DATE_COLUMN} BETWEEN '{date_from}' AND '{date_to}'"
    )
    rows = run_sql_as(token, sql)
    values = rows[0] if rows else []
    out: dict = {}
    for i, (_, key) in enumerate(_MEASURES):
        raw = values[i] if i < len(values) else None
        try:
            out[key] = float(raw) if raw not in (None, "") else None
        except (TypeError, ValueError):
            out[key] = None
    return out


def _monthly_trend(token: str, date_from: str, date_to: str) -> list[dict]:
    """Monthly values for the landing-page trend charts (row-scoped by the SP token).

    Charts the FIRST TWO configured measures. Each point carries the values under both
    their configured keys and the legacy ``spend``/``emissions`` aliases, so the existing
    two trend charts render for every vertical without a frontend change.
    """
    from ..tenants.unity_catalog import run_sql_as

    charted = _MEASURES[:2]
    select = ", ".join(f"MEASURE({m}) AS {k}" for m, k in charted)
    sql = (
        f"SELECT date_format({_DATE_COLUMN}, 'yyyy-MM') AS month, {select} "
        f"FROM {_METRIC_VIEW} "
        f"WHERE {_DATE_COLUMN} BETWEEN '{date_from}' AND '{date_to}' "
        "GROUP BY 1 ORDER BY 1"
    )
    # Legacy aliases the frontend charts read positionally.
    aliases = ("spend", "emissions")
    out: list[dict] = []
    for row in run_sql_as(token, sql):
        month = row[0] if len(row) > 0 else None
        if not month:
            continue

        def _num(idx: int) -> float | None:
            try:
                raw = row[idx] if idx < len(row) else None
                return float(raw) if raw not in (None, "") else None
            except (TypeError, ValueError):
                return None

        point: dict = {"month": month, "spend": None, "emissions": None}
        for i, (_, key) in enumerate(charted):
            value = _num(i + 1)
            point[key] = value
            point[aliases[i]] = value
        out.append(point)
    return out


@router.get("/kpis")
def kpis(
    request: Request,
    current_from: str = "2025-01-01",
    current_to: str = "2025-12-31",
    previous_from: str = "2024-01-01",
    previous_to: str = "2024-12-31",
) -> JSONResponse:
    """Return current + previous-period headline metrics for the landing page."""
    if not _METRIC_VIEW:
        return JSONResponse({"ok": False, "error": "metric view not configured"})

    token = _resolve_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "no credentials"})

    cf = _valid_date(current_from, "2025-01-01")
    ct = _valid_date(current_to, "2025-12-31")
    pf = _valid_date(previous_from, "2024-01-01")
    pt = _valid_date(previous_to, "2024-12-31")

    try:
        current = _measure_row(token, cf, ct)
        previous = _measure_row(token, pf, pt)
        return JSONResponse({"ok": True, "current": current, "previous": previous})
    except Exception as e:  # noqa: BLE001
        logger.warning("kpi query failed: %s", e)
        return JSONResponse({"ok": False, "error": str(e)})


@router.get("/kpis/trend")
def kpis_trend(
    request: Request,
    date_from: str = "2025-01-01",
    date_to: str = "2025-12-31",
) -> JSONResponse:
    """Return monthly spend + emissions for the landing-page trend charts."""
    if not _METRIC_VIEW:
        return JSONResponse({"ok": False, "error": "metric view not configured"})

    token = _resolve_token(request)
    if not token:
        return JSONResponse({"ok": False, "error": "no credentials"})

    df = _valid_date(date_from, "2025-01-01")
    dt = _valid_date(date_to, "2025-12-31")

    try:
        return JSONResponse({"ok": True, "series": _monthly_trend(token, df, dt)})
    except Exception as e:  # noqa: BLE001
        logger.warning("kpi trend query failed: %s", e)
        return JSONResponse({"ok": False, "error": str(e)})
