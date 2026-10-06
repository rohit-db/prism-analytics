"""Custom authentication for the edge front door.

This is the "your own IdP" layer of the OEM pattern: end users sign in against
*the edge*, not Databricks. The edge then proxies into the Databricks App using
the edge Service Principal, so users never see Databricks SSO.

Users live in **Lakebase** (Databricks managed Postgres) — the edge's own user
directory, separate from Databricks workspace identity. If Lakebase is disabled
or unreachable, we fall back to the in-code ``FALLBACK_USERS`` list so the demo
still runs.

Each user maps to a display ``tenant`` name and a ``tenant_id`` — the join key
into ``apex_client_registry`` that selects the tenant's Service Principal. The
app runs the AI/BI embed and Genie MCP as that SP, so the Unity Catalog row
filter scopes the data. ``tenant_id`` must therefore match a ``tenant_id`` in
the registry; ``*`` means operator / all-rows.

Self-contained crypto (stdlib only): PBKDF2-HMAC-SHA256 for passwords,
HMAC-SHA256 for the signed session cookie.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass

from edge.config import CONFIG

logger = logging.getLogger("edge.auth")

SESSION_COOKIE = "apex_edge_session"
SESSION_TTL_SECONDS = 8 * 60 * 60  # 8h demo session
DEMO_PASSWORD = "apex"  # shared demo password for the sample logins
_PBKDF2_ITERATIONS = 200_000


@dataclass(frozen=True)
class DemoUser:
    username: str
    display_name: str
    tenant: str
    tenant_id: str
    role: str = "user"


# In-code fallback directory (used only if Lakebase is off/unreachable). The
# canonical copy lives in Lakebase; this list also drives the one-time seed.
# The ``tenant_id`` values must exist in ``apex_client_registry`` — a tenant
# that is not onboarded resolves to no SP and falls back to the app SP, which
# silently defeats row scoping.
FALLBACK_USERS: tuple[DemoUser, ...] = (
    DemoUser("alice@acmetravel.com", "Alice Chen", "Acme Travel", "acme-travel"),
    DemoUser("ben@globex.com", "Ben Ortiz", "Globex", "globex"),
    DemoUser("dana@prism.example", "Dana Lee", "All Clients", "*", role="operator"),
)
_FALLBACK_BY_EMAIL = {u.username: u for u in FALLBACK_USERS}


# ------------------------------------------------------------------ passwords
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return (
        f"pbkdf2_sha256${_PBKDF2_ITERATIONS}$"
        f"{base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iters))
        return hmac.compare_digest(dk, expected)
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------- directory
def authenticate(username: str, password: str) -> DemoUser | None:
    """Validate credentials against Lakebase; fall back to the in-code list."""
    email = (username or "").strip().lower()
    if CONFIG.lakebase_enabled:
        try:
            from edge import users as users_repo

            row = users_repo.get_by_email(email)
            if row and verify_password(password or "", row.password_hash):
                try:
                    users_repo.touch_login(email)
                except Exception:  # noqa: BLE001
                    pass
                return DemoUser(row.email, row.display_name, row.tenant,
                                row.tenant_id, row.role)
            if row:  # found but wrong password — do not fall through
                return None
        except Exception as e:  # noqa: BLE001
            logger.warning("Lakebase auth failed, using fallback list: %s", e)

    user = _FALLBACK_BY_EMAIL.get(email)
    if user and hmac.compare_digest(DEMO_PASSWORD, password or ""):
        return user
    return None


def list_logins() -> list[dict]:
    """Sample logins for the chips: ``{name, tenant, email, password, role}``.

    Sourced from Lakebase when enabled (password shown is the shared demo
    password); otherwise the in-code fallback list. ``role`` is what the login
    page's user/operator toggle filters on, so omitting it files every operator
    under "Sign in".
    """
    if CONFIG.lakebase_enabled:
        try:
            from edge import users as users_repo

            rows = users_repo.list_all()
            if rows:
                return [
                    {"name": r.display_name, "tenant": r.tenant,
                     "email": r.email, "password": DEMO_PASSWORD, "role": r.role}
                    for r in rows
                ]
        except Exception as e:  # noqa: BLE001
            logger.warning("Lakebase list failed, using fallback list: %s", e)

    return [
        {"name": u.display_name, "tenant": u.tenant,
         "email": u.username, "password": DEMO_PASSWORD, "role": u.role}
        for u in FALLBACK_USERS
    ]


def seed_users() -> int:
    """Create the table (if needed) and upsert the demo users into Lakebase.

    Idempotent. Returns the number of users seeded.
    """
    from edge import users as users_repo

    users_repo.ensure_schema()
    for u in FALLBACK_USERS:
        users_repo.upsert(
            email=u.username,
            password_hash=hash_password(DEMO_PASSWORD),
            display_name=u.display_name,
            tenant=u.tenant,
            tenant_id=u.tenant_id,
            role=u.role,
        )
    return len(FALLBACK_USERS)


# ------------------------------------------------------------------ session
def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _sign(payload_b64: str) -> str:
    mac = hmac.new(CONFIG.session_secret.encode(), payload_b64.encode(), hashlib.sha256)
    return _b64e(mac.digest())


def issue_session(user: DemoUser) -> str:
    payload = {
        "u": user.username,
        "name": user.display_name,
        "tenant": user.tenant,
        "tenant_id": user.tenant_id,
        "role": user.role,
        "exp": int(time.time()) + SESSION_TTL_SECONDS,
    }
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_session(cookie: str | None) -> dict | None:
    if not cookie or "." not in cookie:
        return None
    payload_b64, sig = cookie.rsplit(".", 1)
    if not hmac.compare_digest(sig, _sign(payload_b64)):
        return None
    try:
        data = json.loads(_b64d(payload_b64))
    except Exception:  # noqa: BLE001
        return None
    if int(data.get("exp", 0)) < int(time.time()):
        return None
    return data
