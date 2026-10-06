"""The edge front door's login page.

Presentation is **shared with the app** (``server.auth.login.render_login_page``)
so the sign-in screen the user meets at the edge is the same one the app would
serve: same brand, palette, type and chips. Only two things differ here — the
form posts to ``/__edge/login``, and the sample logins come from the *edge's*
user directory, which has its own Lakebase connection.

The edge used to carry its own copy of this HTML. It drifted, and kept serving
the previous brand long after the app was rebranded — which is why this is a
delegation and not a copy. (Contrast ``edge/appsession.py``, where duplicating
the crypto is deliberate: that is a wire contract with tests pinning it, not
presentation.)
"""
from __future__ import annotations

import html
import logging

from edge.auth import DEMO_PASSWORD, list_logins

logger = logging.getLogger("edge.login_page")

ACTION = "/__edge/login"


def render_login_page(error: str | None = None, next_url: str = "/", mode: str = "user") -> str:
    try:
        from server.auth.login import render_login_page as _render

        return _render(
            error=error,
            next_url=next_url,
            mode=mode,
            action=ACTION,
            logins=list_logins(),
            demo_password=DEMO_PASSWORD,
        )
    except Exception as exc:  # noqa: BLE001 — a login screen must always render
        logger.warning("shared login template unavailable (%s); using fallback", exc)
        return _fallback_page(error=error, next_url=next_url)


def _fallback_page(error: str | None = None, next_url: str = "/") -> str:
    """Unstyled last resort, used only if the shared template cannot be imported.

    Deliberately minimal: anything richer would be a second copy of the design,
    which is the drift this module exists to avoid.
    """
    error_html = f'<p style="color:#9e102c">{html.escape(error)}</p>' if error else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Sign in</title></head>
<body style="font-family:system-ui,sans-serif;max-width:22rem;margin:4rem auto">
  <h1 style="font-size:1.1rem">Sign in</h1>
  {error_html}
  <form method="post" action="{ACTION}">
    <input type="hidden" name="next" value="{html.escape(next_url, quote=True)}">
    <p><label>Email<br><input name="username" type="email" required style="width:100%"></label></p>
    <p><label>Password<br><input name="password" type="password" required style="width:100%"></label></p>
    <button type="submit">Sign in</button>
  </form>
</body></html>"""
