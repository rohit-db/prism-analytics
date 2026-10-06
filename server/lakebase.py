"""Shared Lakebase (Databricks managed Postgres) connection layer.

One place that knows how to talk to Lakebase, reused by every persistence
concern in the app:
  * the white-label user directory (``server.auth.users``),
  * conversation history + user filter preferences (``server.persistence``).

Lakebase auth is OAuth — the Postgres "password" is a short-lived database
credential minted from a Databricks identity. We mint it through the same
Service-Principal-first client the rest of the app uses
(``server.config.get_workspace_client()``), so it works host-agnostically with
no Databricks login. For local development you can instead point
``LAKEBASE_PROFILE`` at a Databricks CLI profile and mint the credential as that
user (handy before the SP has been granted a Postgres role on the instance).

Env contract (see ``.env.example``)::

    LAKEBASE_ENABLED=true
    LAKEBASE_INSTANCE_NAME=apex-edge
    LAKEBASE_ENDPOINT_PATH=projects/apex-edge/branches/production/endpoints/primary
    LAKEBASE_PROFILE=                 # optional: CLI profile for local-dev minting
    PGHOST=ep-xxxx.database.<region>.cloud.databricks.com
    PGPORT=5432
    PGDATABASE=databricks_postgres
    PGUSER=<sp-client-id or user email>   # defaults to DATABRICKS_CLIENT_ID
    PGSSLMODE=require
"""
from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import contextmanager
from typing import Iterator

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("server.lakebase")


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


LAKEBASE_ENABLED = _bool("LAKEBASE_ENABLED", False)
LAKEBASE_INSTANCE_NAME = os.environ.get("LAKEBASE_INSTANCE_NAME", "").strip()
# Resource path used to mint the database credential for Lakebase Autoscaling
# projects, e.g. projects/<id>/branches/production/endpoints/primary.
LAKEBASE_ENDPOINT_PATH = os.environ.get("LAKEBASE_ENDPOINT_PATH", "").strip()
# Optional CLI profile for local-dev credential minting. Leave blank in
# production so the app's SP auth chain mints the credential.
LAKEBASE_PROFILE = os.environ.get("LAKEBASE_PROFILE", "").strip()

PGHOST = os.environ.get("PGHOST", "").strip()
PGPORT = os.environ.get("PGPORT", "5432").strip() or "5432"
PGDATABASE = os.environ.get("PGDATABASE", "databricks_postgres").strip() or "databricks_postgres"
# The Postgres role is the Databricks identity the credential was minted for.
# On Databricks Apps that is the app's own Service Principal, whose client id the
# platform injects — so deployments don't have to hardcode (and keep in sync) an
# SP id that the platform already knows.
PGUSER = (
    os.environ.get("PGUSER", "").strip()
    or os.environ.get("DATABRICKS_CLIENT_ID", "").strip()
)
PGSSLMODE = os.environ.get("PGSSLMODE", "require").strip() or "require"


def enabled() -> bool:
    """True when Lakebase is configured enough to attempt a connection."""
    return LAKEBASE_ENABLED and bool(PGHOST and PGUSER)


# --- credential minting (cached until shortly before expiry) -----------------
_token: str | None = None
_token_exp: float = 0.0
_lock = threading.Lock()


def _workspace_client():
    if LAKEBASE_PROFILE:
        from databricks.sdk import WorkspaceClient

        return WorkspaceClient(profile=LAKEBASE_PROFILE)
    from server.config import get_workspace_client

    return get_workspace_client()


def _mint_token() -> str:
    global _token, _token_exp
    with _lock:
        if _token and time.time() < _token_exp - 120:
            return _token
        w = _workspace_client()
        cred = None
        # Lakebase Autoscaling projects mint via the postgres service using the
        # endpoint resource path. This is the path proven against apex-edge.
        if LAKEBASE_ENDPOINT_PATH:
            try:
                cred = w.postgres.generate_database_credential(  # type: ignore[attr-defined]
                    endpoint=LAKEBASE_ENDPOINT_PATH
                )
            except Exception as e:  # noqa: BLE001
                logger.debug("postgres.generate_database_credential failed: %s", e)
        # Newer "Database Instances" API mints via instance_names.
        if cred is None:
            import uuid

            cred = w.database.generate_database_credential(  # type: ignore[attr-defined]
                request_id=str(uuid.uuid4()),
                instance_names=[LAKEBASE_INSTANCE_NAME],
            )
        _token = cred.token
        _token_exp = time.time() + 3000  # credentials last ~1h; refresh early
        logger.info("Minted Lakebase credential for %s", LAKEBASE_INSTANCE_NAME or PGHOST)
        return _token  # type: ignore[return-value]


def _conninfo() -> str:
    token = _mint_token()
    return (
        f"host={PGHOST} port={PGPORT} dbname={PGDATABASE} "
        f"user={PGUSER} password={token} sslmode={PGSSLMODE}"
    )


@contextmanager
def connection() -> Iterator["object"]:
    """Yield a psycopg connection minted with a fresh Lakebase credential."""
    import psycopg

    conn = psycopg.connect(_conninfo())
    try:
        yield conn
    finally:
        conn.close()


def healthcheck() -> tuple[bool, str]:
    """Return (ok, detail) — used by the health endpoint."""
    if not enabled():
        return False, "disabled"
    try:
        with connection() as conn:
            conn.execute("SELECT 1")
        return True, "ok"
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:200]
