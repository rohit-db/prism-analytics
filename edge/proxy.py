"""Transparent reverse proxy with edge-SP bearer injection.

The browser only ever talks to the edge origin. For every request the edge:

  1. forwards method + path + query + body + cookies upstream to the
     Databricks App, unchanged;
  2. injects ``Authorization: Bearer <edge-sp-token>`` so the Apps OAuth
     proxy admits the request (the end user never sees Databricks SSO);
  3. injects the signed-in user's identity as a cookie in the app's own session
     format (see ``edge.appsession``), so the app can resolve the per-tenant
     Service Principal instead of serving everyone as the app SP;
  4. relays the response back, rewriting ``Set-Cookie`` (drop ``Secure`` for
     local http, drop upstream ``Domain``) and any ``Location`` that points at
     the upstream host so redirects stay on the edge origin.

Two distinct credentials are at play and it is worth keeping them straight: the
bearer is "get past the front door" (authenticates the *edge* to Databricks),
while the injected session cookie is "who is asking" (authenticates the *end
user* to the app). Only the former clears the OAuth proxy; only the latter
drives tenant isolation.

Note: AI/BI dashboards embedded via *basic embedding* load their iframe
directly from the workspace origin (not through this edge), so they still rely
on a Databricks browser session. That is exactly the boundary the showcase
demonstrates — see docs/edge-gateway.md.
"""
from __future__ import annotations

import logging
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import Request
from fastapi.responses import Response

from edge import appsession
from edge.broker import broker
from edge.config import CONFIG

logger = logging.getLogger("edge.proxy")

_HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade",
    "host", "content-length", "authorization",
}

_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0), follow_redirects=False)


async def aclose() -> None:
    await _client.aclose()


def _filter_request_headers(headers) -> dict[str, str]:
    return {k: v for k, v in headers.items() if k.lower() not in _HOP_BY_HOP}


def _set_upstream_cookie(cookie_header: str, name: str, value: str | None) -> str:
    """Return ``cookie_header`` with ``name`` set to ``value`` (or removed).

    Any client-supplied copy of ``name`` is dropped first. The browser talks
    only to the edge, so a session cookie arriving from it is either stale or
    forged — the edge is the sole authority on who the user is, and mints that
    claim fresh on every request.
    """
    kept = [
        c.strip()
        for c in cookie_header.split(";")
        if c.strip() and c.strip().split("=", 1)[0].strip() != name
    ]
    if value:
        kept.append(f"{name}={value}")
    return "; ".join(kept)


def _rewrite_set_cookie(value: str) -> str:
    parts = [p.strip() for p in value.split(";")]
    kept = []
    for p in parts:
        low = p.lower()
        if CONFIG.rewrite_secure_cookies and low == "secure":
            continue
        if low.startswith("domain="):
            continue
        kept.append(p)
    return "; ".join(kept)


def _rewrite_location(value: str, edge_origin: str) -> str:
    up = urlsplit(CONFIG.upstream)
    loc = urlsplit(value)
    if loc.scheme and loc.netloc and (loc.scheme, loc.netloc) == (up.scheme, up.netloc):
        edge = urlsplit(edge_origin)
        return urlunsplit((edge.scheme, edge.netloc, loc.path, loc.query, loc.fragment))
    return value


def _filter_response_headers(resp: httpx.Response, edge_origin: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for k, v in resp.headers.multi_items():
        low = k.lower()
        if low in _HOP_BY_HOP or low == "content-encoding":
            continue
        if low == "set-cookie":
            out.append((k, _rewrite_set_cookie(v)))
        elif low == "location":
            out.append((k, _rewrite_location(v, edge_origin)))
        else:
            out.append((k, v))
    return out


async def proxy(request: Request, identity: dict | None = None) -> Response:
    """Forward one request upstream (the Databricks App) with the edge SP
    bearer injected. When an authenticated edge ``identity`` is supplied, a
    session cookie in the app's own format is minted and injected so the app
    resolves that user's tenant Service Principal."""
    url = f"{CONFIG.upstream}{request.url.path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = _filter_request_headers(request.headers)
    try:
        headers["Authorization"] = f"Bearer {broker.bearer()}"
    except Exception as e:  # noqa: BLE001
        logger.error("Edge SP token mint failed: %s", e)
        return Response(content=f"edge: could not mint SP token: {e}",
                        status_code=502, media_type="text/plain")

    # Hand the signed-in identity to the app in its own session format, and
    # scrub any client-supplied copy even when unauthenticated.
    app_session = appsession.mint_from_session(identity) if identity else None
    if identity and not app_session:
        logger.warning(
            "AUTH_SESSION_SECRET is unset — %s will be served as the app SP, "
            "not as tenant %r", identity.get("u"), identity.get("tenant_id"),
        )
    inbound = "; ".join(headers.pop(k) for k in list(headers) if k.lower() == "cookie")
    cookies = _set_upstream_cookie(inbound, CONFIG.app_session_cookie, app_session)
    if cookies:
        headers["Cookie"] = cookies

    body = await request.body()
    try:
        upstream = await _client.request(request.method, url, headers=headers, content=body)
    except httpx.RequestError as e:
        logger.error("Upstream request failed: %s", e)
        return Response(content=f"edge: upstream unreachable: {e}",
                        status_code=502, media_type="text/plain")

    logger.info("%s %s -> %s", request.method, request.url.path[:80], upstream.status_code)
    edge_origin = f"{request.url.scheme}://{request.headers.get('host', '')}"
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        headers=dict(_filter_response_headers(upstream, edge_origin)),
    )
