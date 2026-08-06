"""Session gate middleware for the white-label auth layer.

When ``AUTH_ENABLED`` is true, every request that is not in the public allowlist
must carry a valid session cookie. Otherwise:
  * HTML / navigation requests get a 302 redirect to ``/login`` (with ``?next=``).
  * ``/api/*`` requests get a 401 JSON response.

When a valid session exists, the decoded identity is attached to
``request.state.identity`` so downstream routes (e.g. the embed-token route) can
row-scope per tenant.

When ``AUTH_ENABLED`` is false the middleware is a no-op, preserving the existing
Databricks-Apps behavior exactly.
"""
from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from .sessions import SESSION_COOKIE, verify_session

# Exact-match public paths (no session required).
_ALLOW_EXACT = {
    "/login",
    "/logout",
    "/favicon.ico",
    "/api/health",
    # Brand + copy for the SPA's pre-session boot (presentation only, no tenant data).
    "/api/config",
}

# Prefix-match public paths.
_ALLOW_PREFIX = (
    "/api/auth/",   # /api/auth/me etc.
    "/assets/",     # built SPA assets
    "/static/",
)

# Static asset extensions that should always be reachable (SPA shell resources).
_ALLOW_EXTENSIONS = (
    ".js", ".css", ".map", ".ico", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".webp", ".woff", ".woff2", ".ttf", ".eot", ".json", ".txt",
)


def _auth_enabled() -> bool:
    raw = os.environ.get("AUTH_ENABLED")
    if raw is None:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _is_public(path: str) -> bool:
    if path in _ALLOW_EXACT:
        return True
    if any(path.startswith(p) for p in _ALLOW_PREFIX):
        return True
    if path.rsplit(".", 1)[-1:] and path.lower().endswith(_ALLOW_EXTENSIONS):
        return True
    return False


def _wants_html(request: Request) -> bool:
    if request.url.path.startswith("/api/"):
        return False
    accept = request.headers.get("accept", "")
    return "text/html" in accept or accept == "" or "*/*" in accept


class SessionGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # No-op when disabled — identical behavior to today's Databricks-Apps app.
        if not _auth_enabled():
            return await call_next(request)

        path = request.url.path
        identity = verify_session(request.cookies.get(SESSION_COOKIE))
        if identity:
            request.state.identity = identity
            return await call_next(request)

        # No valid session.
        if _is_public(path):
            return await call_next(request)

        if request.url.path.startswith("/api/"):
            return JSONResponse({"error": "not authenticated"}, status_code=401)

        if _wants_html(request):
            nxt = path + (f"?{request.url.query}" if request.url.query else "")
            return RedirectResponse(f"/login?next={nxt}", status_code=302)

        return JSONResponse({"error": "not authenticated"}, status_code=401)
