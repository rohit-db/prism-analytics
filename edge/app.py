"""Edge gateway FastAPI app — the Firefly-style front door for APEX.

Run locally with:

    ./edge/run.sh            # or: uvicorn edge.app:app --reload --port 9000

It owns no UI of its own (the SPA stays served by the Databricks App). It is a
thin, transparent reverse proxy that injects the edge SP bearer to clear the
Apps OAuth proxy, so external users reach the app without Databricks SSO.
See docs/edge-gateway.md.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from edge.broker import broker
from edge.config import CONFIG
from edge import proxy
from edge.auth import SESSION_COOKIE, SESSION_TTL_SECONDS, authenticate, issue_session, verify_session
from edge.login_page import render_login_page

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("edge")


@asynccontextmanager
async def lifespan(app: FastAPI):
    missing = CONFIG.missing()
    if missing:
        logger.warning(
            "Edge starting with missing config: %s — proxied requests will fail "
            "until these are set in edge/.env.", ", ".join(missing),
        )
    else:
        logger.info("Edge front door -> %s (workspace OIDC %s, SP %s)",
                    CONFIG.upstream, CONFIG.workspace_host, CONFIG.sp_client_id)
    yield
    await proxy.aclose()


app = FastAPI(title="APEX — Edge Gateway (front door)", lifespan=lifespan)


@app.get("/__edge/health")
async def health() -> JSONResponse:
    """Edge's own health — does NOT touch upstream. Reports config readiness
    and whether the edge SP token can be minted."""
    missing = CONFIG.missing()
    token_ok, token_err = False, None
    if not missing:
        try:
            broker.bearer()
            token_ok = True
        except Exception as e:  # noqa: BLE001
            token_err = str(e)
    from edge.db import healthcheck as _db_health

    db_ok, db_detail = _db_health()
    return JSONResponse({
        "status": "healthy" if (not missing and token_ok) else "degraded",
        "upstream": CONFIG.upstream,
        "workspace_host": CONFIG.workspace_host,
        "sp_client_id": CONFIG.sp_client_id or None,
        "missing_config": missing,
        "edge_sp_token_mintable": token_ok,
        "edge_sp_token_error": token_err,
        "user_directory": "lakebase" if CONFIG.lakebase_enabled else "in-code fallback",
        "lakebase_ok": db_ok,
        "lakebase_detail": db_detail,
    })


@app.get("/__edge/login")
async def login_get(request: Request) -> HTMLResponse:
    """Branded custom-auth login page (the edge IdP stand-in)."""
    if verify_session(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse("/", status_code=303)  # type: ignore[return-value]
    next_url = request.query_params.get("next", "/")
    return HTMLResponse(render_login_page(next_url=next_url))


@app.post("/__edge/login")
async def login_post(request: Request) -> Response:
    form = await request.form()
    username = str(form.get("username", ""))
    password = str(form.get("password", ""))
    next_url = str(form.get("next", "/")) or "/"
    user = authenticate(username, password)
    if not user:
        return HTMLResponse(
            render_login_page(error="Invalid email or password.", next_url=next_url),
            status_code=401,
        )
    resp = RedirectResponse(next_url if next_url.startswith("/") else "/", status_code=303)
    resp.set_cookie(
        SESSION_COOKIE, issue_session(user),
        max_age=SESSION_TTL_SECONDS, httponly=True, samesite="lax",
        secure=not CONFIG.rewrite_secure_cookies,
    )
    logger.info("Edge login: %s (tenant=%s)", user.username, user.tenant)
    return resp


@app.get("/__edge/logout")
async def logout(request: Request) -> Response:
    resp = RedirectResponse("/__edge/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE)
    return resp


@app.api_route("/{full_path:path}",
               methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
async def gateway(request: Request, full_path: str) -> Response:
    # Custom-auth gate: require a valid edge session before proxying upstream.
    session = verify_session(request.cookies.get(SESSION_COOKIE))
    if not session:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            nxt = request.url.path + (f"?{request.url.query}" if request.url.query else "")
            return RedirectResponse(f"/__edge/login?next={nxt}", status_code=303)
        return JSONResponse({"error": "not authenticated at edge"}, status_code=401)
    return await proxy.proxy(request, identity=session)
