"""Mint the *app's* session cookie at the edge — the identity handoff.

The edge authenticates the end user (see ``edge.auth``), but the Databricks App
sits behind the Apps OAuth proxy and only ever sees the edge Service Principal.
Without a handoff the app cannot tell tenants apart and falls back to the app SP
for everyone, defeating the Unity Catalog row filter.

Rather than invent a bespoke trust path (e.g. ``X-Tenant`` headers the app would
have to be taught to trust), the edge mints a cookie in the app's **own** session
format, signed with the app's **own** secret. The app then verifies it through
the same ``server.auth.sessions.verify_session`` it uses for its in-process
logins, so there is exactly one verifier and one signing key.

Two properties worth preserving:

* The minted token is injected on the **upstream request only** — it is never
  set on the browser, so it cannot leak from the client or drift out of sync
  with the edge's own session.
* It is minted per request with a short TTL derived from the edge session, so a
  stolen upstream token expires with the session it came from.

This module deliberately mirrors ``server/auth/sessions.py`` rather than
importing it: the edge stays a standalone process with no dependency on the
``server`` package. The wire format is the contract; see the test in
``tests/test_edge_identity.py`` that pins the two implementations together.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from edge.auth import DemoUser
from edge.config import CONFIG


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _sign(payload_b64: str) -> str:
    mac = hmac.new(
        CONFIG.app_session_secret.encode(), payload_b64.encode(), hashlib.sha256
    )
    return _b64e(mac.digest())


def enabled() -> bool:
    """True when the edge is configured to hand identity to the app."""
    return bool(CONFIG.app_session_secret)


def mint(user: DemoUser, *, expires_at: int | None = None) -> str:
    """Return a signed cookie value the app will accept as a login session.

    Key names match ``server.auth.sessions.create_session`` exactly: ``email``,
    ``name``, ``tenant``, ``tenant_id``, ``role``, ``exp``. ``tenant_id`` is the
    join key into ``apex_client_registry`` that selects the per-tenant SP.
    """
    exp = expires_at or (int(time.time()) + CONFIG.app_session_ttl)
    payload = {
        "email": user.username,
        "name": user.display_name,
        "tenant": user.tenant,
        "tenant_id": user.tenant_id,
        "role": user.role,
        "exp": int(exp),
    }
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    return f"{payload_b64}.{_sign(payload_b64)}"


def mint_from_session(session: dict) -> str | None:
    """Mint an app session from a verified *edge* session payload.

    Returns None when the handoff is unconfigured, so the proxy can degrade to
    the app-SP fallback rather than failing the request.
    """
    if not enabled():
        return None
    user = DemoUser(
        username=str(session.get("u", "")),
        display_name=str(session.get("name", "")),
        tenant=str(session.get("tenant", "")),
        tenant_id=str(session.get("tenant_id", "")),
        role=str(session.get("role", "user")),
    )
    # Inherit the edge session's expiry so the two cannot drift apart.
    return mint(user, expires_at=int(session.get("exp", 0)) or None)
