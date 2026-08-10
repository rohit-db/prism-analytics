"""Transparent reverse proxy with edge-SP bearer injection.

The browser only ever talks to the edge origin. For every request the edge:

  1. forwards method + path + query + body + cookies upstream to the
     Databricks App, unchanged;
  2. injects ``Authorization: Bearer <edge-sp-token>`` so the Apps OAuth
     proxy admits the request (the end user never sees Databricks SSO);
  3. relays the response back, rewriting ``Set-Cookie`` (drop ``Secure`` for
     local http, drop upstream ``Domain``) and any ``Location`` that points at
     the upstream host so redirects stay on the edge origin.

The app's own session cookie rides through in both directions. The edge bearer
is purely the "get past the front door" credential.

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
    bearer injected. If an authenticated edge ``identity`` is supplied, its
    tenant/viewer are forwarded as ``X-Apex-*`` headers so the app can scope
    embed tokens (``external_value``) per tenant."""
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

    if identity:
        headers["X-Apex-Viewer"] = str(identity.get("u", ""))
        headers["X-Apex-Tenant"] = str(identity.get("tenant", ""))
        headers["X-Apex-External-Value"] = str(identity.get("ext", ""))

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
