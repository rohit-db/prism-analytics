#!/usr/bin/env python3
"""End-to-end per-tenant isolation test — proves the UC row filter holds.

For each *active* tenant in the Lakebase registry
(``server.tenants.registry.list_tenants()``):

  1. mint an OAuth (M2M) token AS that tenant's SP,
  2. run ``SELECT session_user()`` (should equal the SP application_id), and
  3. run ``SELECT DISTINCT <tenant_column> FROM <VERIFY_TABLE>``,

then assert the SP sees ONLY its own tenant's rows. A tenant PASSes iff the
distinct tenant_ids it can see equal exactly ``[tenant_id]``. Exits non-zero if
any tenant fails, so this is CI-friendly.

Statements run over the raw REST Statement Execution API
(POST {WORKSPACE_URL}/api/2.0/sql/statements) with the tenant SP's Bearer token,
because we deliberately want session_user() to resolve to the tenant SP — not to
the app/admin identity a WorkspaceClient would use.

Config (env or flags):
    UC_CATALOG / UC_SCHEMA   locate VERIFY_TABLE when it is not fully qualified
    VERIFY_TABLE             governed fact table (bare, schema.table, or
                             catalog.schema.table)                     (required)
    TENANT_COLUMN            per-row tenant column                     (default 'tenant_id')

Secret source:
    Default   — decrypted from the registry via registry.get_secret(sp_app_id).
    Fallback  — pass --secrets-env to read secrets from env vars instead
                (MT-style), named ``<PREFIX><TENANT_ID_UPPER>`` where PREFIX is
                --secret-prefix (default 'TENANT_SECRET_'). Useful when Lakebase
                isn't reachable from where this runs.

Usage:
    python scripts/tenants/verify_isolation.py
    python scripts/tenants/verify_isolation.py --verify-table main.apex.bookings
    python scripts/tenants/verify_isolation.py --secrets-env \\
        --secret-prefix TENANT_SECRET_
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

import requests

# Make the app's ``server`` package importable (repo root is two levels up).
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

# Load .env before reading any config below. Without it this script runs on a
# partial environment and reports an isolation FAILURE when isolation is
# actually intact — the most misleading result it could give.
from dotenv import load_dotenv  # noqa: E402

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Verify per-tenant UC row-filter isolation across all tenants.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--catalog", default=None, help="UC catalog (env UC_CATALOG)")
    p.add_argument("--schema", default=None, help="UC schema (env UC_SCHEMA)")
    p.add_argument(
        "--verify-table",
        default=None,
        help="fact table: bare, schema.table, or catalog.schema.table "
        "(env VERIFY_TABLE)",
    )
    p.add_argument(
        "--tenant-column",
        default=None,
        help="per-row tenant column (env TENANT_COLUMN)",
    )
    p.add_argument(
        "--secrets-env",
        action="store_true",
        help="read SP secrets from env vars instead of the Lakebase registry",
    )
    p.add_argument(
        "--secret-prefix",
        default="TENANT_SECRET_",
        help="env var prefix for --secrets-env (name = PREFIX + TENANT_ID_UPPER)",
    )
    return p.parse_args(argv)


def _qualify_table(verify_table: str, catalog: str, schema: str) -> str:
    """Return a fully-qualified name, honoring already-qualified inputs."""
    parts = verify_table.split(".")
    if len(parts) >= 3:
        return verify_table
    if len(parts) == 2:
        if not catalog:
            raise SystemExit(
                "VERIFY_TABLE is schema-qualified but UC_CATALOG is unset."
            )
        return f"{catalog}.{verify_table}"
    if not catalog or not schema:
        raise SystemExit(
            "VERIFY_TABLE is a bare name; set UC_CATALOG and UC_SCHEMA "
            "(or pass a fully-qualified --verify-table)."
        )
    return f"{catalog}.{schema}.{verify_table}"


def _run_sql_as(host: str, token: str, warehouse_id: str, statement: str) -> list[list]:
    """Execute one SQL statement over REST as the given bearer token."""
    host = host.rstrip("/")
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.post(
        f"{host}/api/2.0/sql/statements",
        headers=headers,
        json={
            "warehouse_id": warehouse_id,
            "statement": statement,
            "wait_timeout": "30s",
        },
        timeout=60,
    )
    r.raise_for_status()
    body = r.json()
    statement_id = body.get("statement_id")
    while body.get("status", {}).get("state") in ("PENDING", "RUNNING"):
        time.sleep(0.5)
        r = requests.get(
            f"{host}/api/2.0/sql/statements/{statement_id}",
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
    state = body.get("status", {}).get("state")
    if state != "SUCCEEDED":
        raise RuntimeError(f"SQL failed ({state}): {body.get('status')}")
    return (body.get("result") or {}).get("data_array") or []


def _secret_for(tenant, use_env: bool, prefix: str):
    if use_env:
        return os.environ.get(f"{prefix}{tenant.tenant_id.upper()}")
    from server.tenants import registry

    return registry.get_secret(tenant.sp_app_id)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    catalog = (args.catalog or _env("UC_CATALOG")).strip()
    schema = (args.schema or _env("UC_SCHEMA")).strip()
    tenant_column = (args.tenant_column or _env("TENANT_COLUMN", "tenant_id")).strip()
    verify_table = (args.verify_table or _env("VERIFY_TABLE")).strip()
    if not verify_table:
        raise SystemExit(
            "VERIFY_TABLE must be set (env or --verify-table): the governed "
            "fact table to probe."
        )
    fq_table = _qualify_table(verify_table, catalog, schema)

    from server.config import WORKSPACE_URL
    from server.tenants import registry, runtime

    host = WORKSPACE_URL
    warehouse_id = runtime.warehouse_id()
    minter = runtime.minter()

    tenants = [t for t in registry.list_tenants() if t.status == "active"]
    if not tenants:
        print(
            "No active tenants found in the registry. Onboard at least one "
            "tenant before verifying (or check Lakebase connectivity)."
        )
        return 1

    print(f"# host={host}")
    print(f"# warehouse_id={warehouse_id}")
    print(f"# table={fq_table} | tenant_column={tenant_column}\n")

    header = f"{'tenant_id':<22} {'session_user':<40} {'distinct_tenant_ids':<32} result"
    print(header)
    print("-" * len(header))

    all_pass = True
    for tenant in tenants:
        secret = _secret_for(tenant, args.secrets_env, args.secret_prefix)
        if not secret:
            print(f"{tenant.tenant_id:<22} {'<no secret>':<40} {'-':<32} FAIL")
            all_pass = False
            continue

        try:
            token = minter.get_token(tenant.sp_app_id, secret)
            s_user_rows = _run_sql_as(
                host, token, warehouse_id, "SELECT session_user()"
            )
            distinct_rows = _run_sql_as(
                host,
                token,
                warehouse_id,
                f"SELECT DISTINCT {tenant_column} FROM {fq_table}",
            )
        except Exception as e:  # noqa: BLE001 - report and keep going
            print(f"{tenant.tenant_id:<22} {'<error>':<40} {str(e)[:32]:<32} FAIL")
            all_pass = False
            continue

        session_user = s_user_rows[0][0] if s_user_rows and s_user_rows[0] else ""
        distinct_ids = sorted(
            {row[0] for row in distinct_rows if row and row[0] is not None}
        )
        passed = distinct_ids == [tenant.tenant_id]
        all_pass = all_pass and passed
        print(
            f"{tenant.tenant_id:<22} {str(session_user):<40} "
            f"{str(distinct_ids):<32} {'PASS' if passed else 'FAIL'}"
        )

    print()
    if all_pass:
        print("ALL TENANTS PASS — row-filter isolation holds.")
        return 0
    print("ISOLATION FAILURE — at least one tenant saw the wrong rows.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
