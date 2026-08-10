"""Lakebase (Databricks managed Postgres) connection for the edge directory.

The edge stores its custom-auth users in Lakebase. Lakebase auth is OAuth — the
"password" is a short-lived database credential minted from a Databricks
identity. We mint it via the Databricks SDK and cache it until shortly before
expiry.

Auth identity:
  * **Local dev** — set ``EDGE_PG_PROFILE`` to a Databricks CLI profile; the
    credential is minted as that user (``EDGE_PG_USER`` = their email).
  * **Production** — leave ``EDGE_PG_PROFILE`` blank; the default SDK auth chain
    (the edge SP env creds) is used, with ``EDGE_PG_USER`` = the SP client id
    (the SP must have a Postgres role on the instance).

If Lakebase is disabled or unreachable, callers fall back to the in-code user
list in ``edge.auth`` — the demo never hard-breaks.
"""
from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from typing import Iterator

import psycopg

from edge.config import CONFIG

logger = logging.getLogger("edge.db")

_token: str | None = None
_token_exp: float = 0.0
_lock = threading.Lock()


def _workspace_client():
    from databricks.sdk import WorkspaceClient

    if CONFIG.pg_profile:
        return WorkspaceClient(profile=CONFIG.pg_profile)
    return WorkspaceClient()


def _mint_token() -> str:
    """Mint (and cache) a Lakebase database credential for the instance.

    Two APIs exist depending on SDK version: Lakebase Autoscaling projects mint
    from an endpoint resource path via ``w.postgres``, while the newer Database
    Instances API mints from instance names via ``w.database``. Try the former
    and fall back, mirroring ``server.lakebase`` so both processes work against
    the same instance on whichever SDK is installed.
    """
    global _token, _token_exp
    with _lock:
        if _token and time.time() < _token_exp - 120:
            return _token
        w = _workspace_client()
        cred = None
        if CONFIG.pg_endpoint:
            try:
                cred = w.postgres.generate_database_credential(  # type: ignore[attr-defined]
                    endpoint=CONFIG.pg_endpoint
                )
            except Exception as e:  # noqa: BLE001
                logger.debug("postgres.generate_database_credential failed: %s", e)
        if cred is None:
            import uuid

            cred = w.database.generate_database_credential(  # type: ignore[attr-defined]
                request_id=str(uuid.uuid4()),
                instance_names=[CONFIG.pg_instance],
            )
        _token = cred.token
        # DatabaseCredential.expiration_time may be a datetime; default ~1h.
        _token_exp = time.time() + 3000
        logger.info("Minted Lakebase credential for instance %s", CONFIG.pg_instance)
        return _token  # type: ignore[return-value]


def _conninfo() -> str:
    token = _mint_token()
    return (
        f"host={CONFIG.pg_host} port=5432 dbname={CONFIG.pg_database} "
        f"user={CONFIG.pg_user} password={token} sslmode=require"
    )


@contextmanager
def get_connection() -> Iterator[psycopg.Connection]:
    conn = psycopg.connect(_conninfo())
    try:
        yield conn
    finally:
        conn.close()


def healthcheck() -> tuple[bool, str]:
    """Return (ok, detail) — used by the edge health endpoint."""
    if not CONFIG.lakebase_enabled:
        return False, "disabled"
    try:
        with get_connection() as conn:
            conn.execute("SELECT 1")
        return True, "ok"
    except Exception as e:  # noqa: BLE001
        return False, str(e)[:200]
