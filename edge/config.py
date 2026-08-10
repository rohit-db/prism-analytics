"""Edge gateway configuration.

All values come from the environment (loaded from ``edge/.env`` in local dev —
see ``edge/.env.example``). The edge needs three things to do its job:

  1. Where the Databricks App lives           (EDGE_UPSTREAM_URL)
  2. The workspace OIDC endpoint to mint at    (EDGE_WORKSPACE_HOST)
  3. The edge SP credentials                   (EDGE_SP_CLIENT_ID / _SECRET)

Optionally, to also front the AI/BI dashboard origin so basic-embedding
iframes route through the edge instead of hitting the workspace directly:

  4. The workspace embed origin                (EDGE_EMBED_ORIGIN, default =
                                                 EDGE_WORKSPACE_HOST)

Everything else has a sensible default tuned for local http testing.

This module is intentionally self-contained — it does NOT import the app's
``server`` package — so the edge can be deployed anywhere as its own process.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_env_file(filepath: str) -> None:
    """Minimal .env loader — no extra deps."""
    p = Path(filepath)
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


_REPO_ROOT = Path(__file__).resolve().parent.parent
load_env_file(str(_REPO_ROOT / "edge" / ".env"))


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class EdgeConfig:
    # Upstream Databricks App (the thing behind the Apps OAuth proxy).
    upstream_url: str
    # Workspace host that issues OAuth tokens at /oidc/v1/token. The edge SP's
    # token is minted here, not at the app URL.
    workspace_host: str
    # Edge Service Principal — must have CAN_USE on the Databricks App.
    sp_client_id: str
    sp_client_secret: str
    # Optional: the AI/BI dashboard origin to also reverse-proxy, so basic
    # embedding iframes can be routed through the edge. Defaults to the
    # workspace host. (Whether the workspace embed accepts the injected token
    # is exactly what the showcase tests.)
    embed_origin: str
    # Where the edge itself listens.
    host: str
    port: int
    # Strip the `Secure` attribute from upstream Set-Cookie headers so cookies
    # survive over plain http://localhost during local tests. MUST be False for
    # any real https deployment of the edge.
    rewrite_secure_cookies: bool
    oauth_scope: str
    # Secret used to sign the edge's own session cookie (custom auth). Override
    # in production via EDGE_SESSION_SECRET.
    session_secret: str
    # --- Lakebase (custom user directory) ---
    # When enabled, the edge reads its login users from a Lakebase Postgres
    # instance instead of the in-code fallback list. The edge mints a Postgres
    # OAuth credential via the Databricks SDK at connect time.
    lakebase_enabled: bool
    pg_host: str
    pg_database: str
    pg_user: str
    # Lakebase Autoscaling project id (display/reference only).
    pg_instance: str
    # Lakebase endpoint resource path — used to mint the database credential:
    #   projects/<project>/branches/<branch>/endpoints/<endpoint>
    pg_endpoint: str
    # Local-dev: Databricks CLI profile used to mint the Postgres credential.
    # Leave blank in production so the default (edge SP) auth chain is used.
    pg_profile: str

    @property
    def upstream(self) -> str:
        return self.upstream_url.rstrip("/")

    @property
    def embed(self) -> str:
        return (self.embed_origin or self.workspace_host).rstrip("/")

    def missing(self) -> list[str]:
        required = {
            "EDGE_UPSTREAM_URL": self.upstream_url,
            "EDGE_WORKSPACE_HOST": self.workspace_host,
            "EDGE_SP_CLIENT_ID": self.sp_client_id,
            "EDGE_SP_CLIENT_SECRET": self.sp_client_secret,
        }
        return [k for k, v in required.items() if not v]


CONFIG = EdgeConfig(
    upstream_url=_env("EDGE_UPSTREAM_URL"),
    workspace_host=_env("EDGE_WORKSPACE_HOST"),
    sp_client_id=_env("EDGE_SP_CLIENT_ID"),
    sp_client_secret=_env("EDGE_SP_CLIENT_SECRET"),
    embed_origin=_env("EDGE_EMBED_ORIGIN"),
    host=_env("EDGE_HOST", "127.0.0.1"),
    port=int(_env("EDGE_PORT", "9000")),
    rewrite_secure_cookies=_bool("EDGE_REWRITE_SECURE_COOKIES", True),
    oauth_scope=_env("EDGE_OAUTH_SCOPE", "all-apis"),
    session_secret=_env("EDGE_SESSION_SECRET", "apex-edge-dev-secret-change-me"),
    lakebase_enabled=_bool("EDGE_LAKEBASE_ENABLED", False),
    pg_host=_env("EDGE_PG_HOST"),
    pg_database=_env("EDGE_PG_DATABASE", "databricks_postgres"),
    pg_user=_env("EDGE_PG_USER"),
    pg_instance=_env("EDGE_PG_INSTANCE"),
    pg_endpoint=_env("EDGE_PG_ENDPOINT",
                     "projects/apex-edge/branches/production/endpoints/primary"),
    pg_profile=_env("EDGE_PG_PROFILE"),
)
