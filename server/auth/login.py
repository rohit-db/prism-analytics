"""Login / logout / identity routes for the white-label auth layer.

A self-contained FastAPI ``APIRouter`` that makes this app its own OEM Identity
Provider: users sign in against the app's own directory and receive an
HMAC-signed session cookie. No Databricks login is ever shown.

Routes:
  * ``GET  /login``        — branded login HTML with clickable sample-login chips.
  * ``POST /login``        — validate credentials, set the session cookie, redirect.
  * ``GET  /logout``       — clear the cookie, redirect to /login.
  * ``POST /logout``       — same as GET (convenience).
  * ``GET  /api/auth/me``  — current session identity JSON (or 401).

The login HTML is ported/adapted from ``edge/login_page.py``.
"""
from __future__ import annotations

import html
import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from ..brand import brand_asset_exists, load_brand
from . import users as users_repo
from .sessions import SESSION_COOKIE, SESSION_TTL_SECONDS, create_session, verify_session

logger = logging.getLogger("server.auth.login")

router = APIRouter()


def _cookie_secure(request: Request) -> bool:
    """Set Secure when the request arrived over TLS (or AUTH_COOKIE_SECURE forces it)."""
    forced = os.environ.get("AUTH_COOKIE_SECURE")
    if forced is not None:
        return forced.strip().lower() in ("1", "true", "yes", "on")
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    return proto == "https"


def render_login_page(
    error: str | None = None,
    next_url: str = "/",
    mode: str = "user",
    action: str = "/login",
    logins: list[dict] | None = None,
    demo_password: str | None = None,
) -> str:
    """The white-label sign-in page.

    Shared with the edge gateway (``edge/login_page.py``), which renders the same
    markup against its own user directory and posts to ``/__edge/login``. Keeping
    one renderer is deliberate: when the two were separate copies, the edge's
    drifted and kept serving the previous brand long after the app was rebranded.

    ``logins`` / ``demo_password`` default to this app's directory; callers with
    their own directory pass theirs. ``action`` is the form's POST target.
    """
    b = load_brand()
    ident = b["identity"]
    colors = b["colors"]
    app_name = html.escape(ident["appName"])
    tagline = html.escape(ident.get("tagline", ""))
    mark = html.escape(ident["shortName"][:1].upper())
    active_mode = "operator" if mode == "operator" else "user"
    show_demo = os.environ.get("AUTH_SHOW_DEMO_LOGINS", "true").strip().lower() not in ("0", "false", "no", "off")
    demo_pw = (
        users_repo.demo_password_hint() or "" if demo_password is None else demo_password
    )
    chips = ""
    if show_demo:
        rows = users_repo.list_logins() if logins is None else logins
        chips = "\n".join(
            f"""<button type="button" class="chip" data-role="{html.escape(u.get('role', 'user'))}" data-u="{html.escape(u['email'])}" data-p="{html.escape(demo_pw)}">
                  <span class="chip-name">{html.escape(u['name'])}</span>
                  <span class="chip-tenant">{html.escape(u['tenant'])}</span>
                  <span class="chip-cred">{html.escape(u['email'])}{(' &middot; ' + html.escape(demo_pw)) if demo_pw else ''}</span>
                </button>"""
            for u in rows
        )
    # Per-brand shape + type, so the login screen matches the app's identity rather than
    # being a generically-styled page with the brand's color swapped in.
    design = b.get("design") or {}
    font_sans = design.get("fontSans") or (
        '-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif'
    )
    font_display = design.get("fontDisplay") or font_sans
    radius = design.get("radius") or "0.25rem"
    tracking = design.get("headingTracking") or "-0.01em"
    font_link = (
        f'<link rel="stylesheet" href="{html.escape(design["fontUrl"], quote=True)}">'
        if design.get("fontUrl")
        else ""
    )
    # Logo mark, when the instance actually ships the file; else the monogram.
    # The path is always *named* in brand config, so existence is what decides —
    # otherwise an absent mark renders as a broken image instead of the monogram.
    logo_mark = ident.get("logoMark") or ""
    mark_html = (
        f'<img src="{html.escape(logo_mark, quote=True)}" alt="" width="30" height="30">'
        if logo_mark and brand_asset_exists(logo_mark)
        else mark
    )
    error_html = f'<div class="error">{html.escape(error)}</div>' if error else ""
    chips_block = (
        f'\n    <div class="divider">Sample logins</div>\n    <div class="chips">{chips}</div>'
        if show_demo else ""
    )
    return f"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in &middot; {app_name}</title>
{font_link}
<style>
  :root {{ --brand:{colors['primary']}; --brand-dark:{colors['primaryDark']}; --brand-accent:{colors['accent']}; --ring:{colors['primaryLight']};
          --r:{radius}; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; font-family:{font_sans};
         font-size:13px; line-height:20px; min-height:100vh; display:flex; align-items:center; justify-content:center;
         background:linear-gradient(135deg,{colors['sidebarFrom']} 0%,{colors['primaryDark']} 50%,{colors['primary']} 100%); color:#161616;
         -webkit-font-smoothing:antialiased; }}
  .card {{ width:380px; background:#ffffff; border-radius:calc(var(--r) + 4px); border:1px solid #ebebeb;
          box-shadow:0px 8px 40px 0px rgba(0,0,0,0.13); padding:28px 26px 24px; }}
  .brand {{ display:flex; align-items:center; gap:9px; margin-bottom:4px; }}
  .brand .logo {{ width:30px;height:30px;border-radius:calc(var(--r) + 2px); overflow:hidden;
                 background:linear-gradient(135deg,{colors['primary']} 0%,{colors['accent']} 100%);
                 display:flex;align-items:center;justify-content:center;color:#fff;font-weight:600;font-size:14px; }}
  .brand .logo img {{ display:block; width:100%; height:100%; }}
  .brand h1 {{ font-family:{font_display}; font-size:18px; line-height:24px; margin:0; font-weight:600;
              letter-spacing:{tracking}; color:#161616; }}
  .sub {{ color:#6f6f6f; font-size:13px; margin:4px 0 18px 1px; }}
  label {{ font-size:13px; font-weight:600; color:#161616; display:block; margin:12px 0 6px; }}
  input {{ width:100%; padding:8px 12px; border:1px solid #cbcbcb; border-radius:var(--r); font-size:13px; line-height:20px;
          color:#161616; background:#ffffff; }}
  input::placeholder {{ color:#6f6f6f; }}
  input:focus {{ outline:none; border-color:var(--brand); box-shadow:0 0 0 2px var(--ring); }}
  button.submit {{ width:100%; margin-top:18px; padding:9px; border:0; border-radius:var(--r); color:#ffffff;
                  font-size:13px; font-weight:600; cursor:pointer; background:var(--brand); transition:background .12s; }}
  button.submit:hover {{ background:var(--brand-dark); }}
  .divider {{ display:flex; align-items:center; gap:10px; color:#6f6f6f; font-size:12px;
             text-transform:uppercase; letter-spacing:.08em; margin:20px 0 12px; }}
  .divider::before, .divider::after {{ content:""; flex:1; height:1px; background:#ebebeb; }}
  .chips {{ display:flex; flex-direction:column; gap:8px; }}
  .chip {{ text-align:left; background:#f7f7f7; border:1px solid #ebebeb; border-radius:var(--r);
          padding:9px 11px; cursor:pointer; display:grid; grid-template-columns:1fr auto; row-gap:2px; transition:background .12s,border-color .12s; }}
  .chip:hover {{ border-color:var(--brand); background:#f0f8ff; }}
  .chip-name {{ font-size:13px; font-weight:600; color:#161616; }}
  .chip-tenant {{ font-size:12px; color:#fff; background:var(--brand); border-radius:999px;
                 padding:1px 8px; justify-self:end; font-weight:500; }}
  .chip-cred {{ grid-column:1 / -1; font-size:12px; color:#6f6f6f; font-family:ui-monospace,SFMono-Regular,Menlo,monospace; }}
  .error {{ background:#fff5f7; color:#9e102c; border:1px solid #fbd0d8; border-radius:var(--r);
           padding:8px 10px; font-size:13px; margin-bottom:12px; }}
  .foot {{ text-align:center; color:#6f6f6f; font-size:12px; margin-top:16px; }}
  .mode-toggle {{ display:flex; gap:4px; background:#f7f7f7; border:1px solid #ebebeb; border-radius:calc(var(--r) + 2px); padding:3px; margin-bottom:16px; }}
  .mode-btn {{ flex:1; border:0; background:transparent; padding:6px 10px; border-radius:4px;
              font-size:13px; font-weight:600; color:#6f6f6f; cursor:pointer; transition:background .12s,color .12s; }}
  .mode-btn.active {{ background:#ffffff; color:var(--brand); box-shadow:0px 1px 0px 0px rgba(0,0,0,0.05); }}
  body[data-active-mode="operator"] .brand h1::after {{
     content:" · Operator"; color:var(--brand); font-weight:600; font-size:13px; }}
  body[data-active-mode="user"] .chip[data-role="operator"] {{ display:none; }}
  body[data-active-mode="operator"] .chip[data-role="user"] {{ display:none; }}
</style></head>
<body data-active-mode="{active_mode}">
  <form class="card" method="post" action="{html.escape(action, quote=True)}">
    <div class="mode-toggle" data-mode-toggle>
      <button type="button" class="mode-btn" data-mode="user">Sign in</button>
      <button type="button" class="mode-btn" data-mode="operator">Operator</button>
    </div>
    <div class="brand"><div class="logo">{mark_html}</div><h1>{app_name}</h1></div>
    <div class="sub">{tagline if tagline else "Sign in to your analytics workspace"}</div>
    {error_html}
    <input type="hidden" name="next" value="{html.escape(next_url)}">
    <input type="hidden" name="mode" value="{active_mode}">
    <label for="u">Email</label>
    <input id="u" name="username" type="email" autocomplete="username" placeholder="you@company.com" required>
    <label for="p">Password</label>
    <input id="p" name="password" type="password" autocomplete="current-password" placeholder="&bull;&bull;&bull;&bull;&bull;&bull;" required>
    <button class="submit" type="submit">Sign in</button>

    {chips_block}
    <div class="foot">Custom authentication &middot; powered by Databricks behind the scenes</div>
  </form>
  <script>
    document.querySelectorAll(".chip").forEach(function(c) {{
      c.addEventListener("click", function() {{
        document.getElementById("u").value = c.dataset.u;
        if (c.dataset.p) document.getElementById("p").value = c.dataset.p;
      }});
    }});
    (function() {{
      var body = document.body;
      function setMode(m) {{
        body.setAttribute("data-active-mode", m);
        document.querySelectorAll(".mode-btn").forEach(function(b) {{
          b.classList.toggle("active", b.dataset.mode === m);
        }});
        document.querySelectorAll("input[name='mode']").forEach(function(i) {{ i.value = m; }});
        var u = new URL(window.location);
        if (m === "operator") u.searchParams.set("mode", "operator");
        else u.searchParams.delete("mode");
        window.history.replaceState({{}}, "", u);
      }}
      document.querySelectorAll("[data-mode-toggle] .mode-btn").forEach(function(b) {{
        b.addEventListener("click", function() {{ setMode(b.dataset.mode); }});
      }});
      setMode(body.getAttribute("data-active-mode") || "user");
    }})();
  </script>
</body></html>"""


def _safe_next(next_url: str) -> str:
    """Only allow same-site relative redirects."""
    return next_url if next_url.startswith("/") and not next_url.startswith("//") else "/"


@router.get("/login")
async def login_get(request: Request) -> Response:
    if verify_session(request.cookies.get(SESSION_COOKIE)):
        return RedirectResponse("/", status_code=303)
    next_url = _safe_next(request.query_params.get("next", "/"))
    mode = "operator" if request.query_params.get("mode") == "operator" else "user"
    return HTMLResponse(render_login_page(next_url=next_url, mode=mode))


@router.post("/login")
async def login_post(request: Request) -> Response:
    form = await request.form()
    username = str(form.get("username", ""))
    password = str(form.get("password", ""))
    next_url = _safe_next(str(form.get("next", "/")) or "/")
    mode = "operator" if str(form.get("mode", "")) == "operator" else "user"
    user = users_repo.verify_login(username, password)
    if not user:
        return HTMLResponse(
            render_login_page(error="Invalid email or password.", next_url=next_url, mode=mode),
            status_code=401,
        )
    identity = {
        "email": user.email,
        "display_name": user.display_name,
        "tenant": user.tenant,
        "tenant_id": user.tenant_id,
        "role": user.role,
    }
    resp = RedirectResponse(next_url, status_code=303)
    resp.set_cookie(
        SESSION_COOKIE,
        create_session(identity),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(request),
        path="/",
    )
    logger.info("Login: %s (tenant=%s)", user.email, user.tenant)
    return resp


@router.get("/logout")
@router.post("/logout")
async def logout() -> Response:
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie(SESSION_COOKIE, path="/")
    return resp


@router.get("/api/auth/me")
async def auth_me(request: Request) -> Response:
    identity = getattr(request.state, "identity", None) or verify_session(
        request.cookies.get(SESSION_COOKIE)
    )
    if not identity:
        return JSONResponse({"authenticated": False}, status_code=401)
    return JSONResponse({
        "authenticated": True,
        "email": identity.get("email"),
        "display_name": identity.get("display_name"),
        "tenant": identity.get("tenant"),
        "tenant_id": identity.get("tenant_id"),
        "role": identity.get("role", "user"),
    })
