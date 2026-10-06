#!/usr/bin/env python3
"""Apply (or repair) the per-tenant Unity Catalog row-filter isolation.

This is the load-bearing isolation control for the per-tenant Service Principal
feature. It (idempotently):

  1. creates ``sp_tenant_mapping`` (the row-filter join target),
  2. creates/replaces the ``tenant_row_filter`` function (keyed on
     ``session_user()``, which equals a caller's SP application_id over OAuth
     M2M), and
  3. attaches that filter to every table in ISOLATED_TABLES on TENANT_COLUMN.

If a workspace drifts (filter detached, function dropped) tenant SPs start
seeing *all* rows — re-run this to restore the guarantee.

Config resolution (flags override env; env is read from the app's .env too):
    UC_CATALOG        catalog holding the governed tables            (required)
    UC_SCHEMA         schema within that catalog                     (required)
    TENANT_ADMIN_GROUP account group that bypasses the filter        (default 'admins')
    WAREHOUSE_NAME    SQL warehouse used to run the admin DDL
    ISOLATED_TABLES   comma-separated tables to attach the filter to (default = VERIFY_TABLE)
    VERIFY_TABLE      the governed fact table (fallback for ISOLATED_TABLES)
    TENANT_COLUMN     per-row tenant discriminator column            (default 'tenant_id')
    TENANTS_ADMIN_PROFILE  CLI profile (workspace-admin) used for the client

Usage:
    python scripts/tenants/apply_row_filter.py
    python scripts/tenants/apply_row_filter.py --catalog main --schema apex \\
        --tables bookings,invoices --tenant-column tenant_id
    python scripts/tenants/apply_row_filter.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Make the app's ``server`` package importable (repo root is two levels up).
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _resolve_tables(tables_arg: str | None) -> list[str]:
    raw = tables_arg if tables_arg is not None else (
        _env("ISOLATED_TABLES") or _env("VERIFY_TABLE")
    )
    return [t.strip() for t in raw.split(",") if t.strip()]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Apply the per-tenant UC row filter (idempotent).",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--catalog", default=None, help="UC catalog (env UC_CATALOG)")
    p.add_argument("--schema", default=None, help="UC schema (env UC_SCHEMA)")
    p.add_argument(
        "--admin-group",
        default=None,
        help="account group that bypasses the filter (env TENANT_ADMIN_GROUP)",
    )
    p.add_argument(
        "--warehouse-name",
        default=None,
        help="SQL warehouse name to run DDL on (env WAREHOUSE_NAME)",
    )
    p.add_argument(
        "--tables",
        default=None,
        help="comma-separated tables to filter (env ISOLATED_TABLES / VERIFY_TABLE)",
    )
    p.add_argument(
        "--tenant-column",
        default=None,
        help="per-row tenant column (env TENANT_COLUMN)",
    )
    p.add_argument(
        "--profile",
        default=None,
        help="CLI profile for a workspace-admin client (env TENANTS_ADMIN_PROFILE)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print the SQL that would run, without executing it",
    )
    return p.parse_args(argv)


def _build_statements(
    catalog: str, schema: str, admin_group: str, tables: list[str], tenant_column: str
) -> list[tuple[str, str]]:
    """Return an ordered list of (label, sql) steps."""
    steps: list[tuple[str, str]] = []
    steps.append(
        (
            "create sp_tenant_mapping",
            f"""CREATE TABLE IF NOT EXISTS {catalog}.{schema}.sp_tenant_mapping (
    sp_app_id STRING  NOT NULL,
    tenant_id STRING  NOT NULL,
    active    BOOLEAN NOT NULL
) USING DELTA
COMMENT 'Lookup table joined in tenant_row_filter (sp_app_id == session_user()).'""",
        )
    )
    steps.append(
        (
            "create/replace tenant_row_filter",
            f"""CREATE OR REPLACE FUNCTION {catalog}.{schema}.tenant_row_filter(tenant_id STRING)
RETURN
  is_account_group_member('{admin_group}')
  OR EXISTS (
    SELECT 1
    FROM {catalog}.{schema}.sp_tenant_mapping m
    WHERE m.sp_app_id = session_user()
      AND m.active = true
      -- A mapping row of tenant_id = '*' is a wildcard: that SP sees ALL rows.
      -- The app's own Service Principal is mapped to '*' so the operator view
      -- (tenant_id = '*', which resolves to the app SP) and the onboard client
      -- picker can read across every tenant, without adding the SP to
      -- {admin_group}. Per-tenant SPs carry an exact tenant_id and see only theirs.
      AND (m.tenant_id = tenant_row_filter.tenant_id OR m.tenant_id = '*')
  )""",
        )
    )
    for tbl in tables:
        steps.append(
            (
                f"attach row filter to {tbl}",
                f"ALTER TABLE {catalog}.{schema}.{tbl} "
                f"SET ROW FILTER {catalog}.{schema}.tenant_row_filter "
                f"ON ({tenant_column})",
            )
        )
    return steps


def _get_client(profile: str):
    """Prefer an explicit admin CLI profile; else the app's SP-first client."""
    if profile:
        from databricks.sdk import WorkspaceClient

        return WorkspaceClient(profile=profile)
    from server.config import get_workspace_client

    return get_workspace_client()


def _resolve_warehouse_id(w, warehouse_name: str) -> str:
    wid = None
    for wh in w.warehouses.list():
        if wh.name == warehouse_name:
            wid = wh.id
            break
    if wid is None:
        for wh in w.warehouses.list():
            wid = wh.id
            break
    if wid is None:
        raise SystemExit("No SQL warehouse available in this workspace.")
    return wid


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    catalog = (args.catalog or _env("UC_CATALOG")).strip()
    schema = (args.schema or _env("UC_SCHEMA")).strip()
    admin_group = (args.admin_group or _env("TENANT_ADMIN_GROUP", "admins")).strip()
    warehouse_name = (
        args.warehouse_name or _env("WAREHOUSE_NAME", "Serverless Starter Warehouse")
    ).strip()
    tenant_column = (args.tenant_column or _env("TENANT_COLUMN", "tenant_id")).strip()
    profile = (args.profile or _env("TENANTS_ADMIN_PROFILE")).strip()
    tables = _resolve_tables(args.tables)

    if not catalog or not schema:
        raise SystemExit(
            "UC_CATALOG and UC_SCHEMA must be set (via env or --catalog/--schema). "
            f"Got catalog={catalog!r} schema={schema!r}."
        )
    if not tables:
        raise SystemExit(
            "No tables to isolate. Set ISOLATED_TABLES or VERIFY_TABLE, or pass "
            "--tables <comma,separated,list>."
        )

    steps = _build_statements(catalog, schema, admin_group, tables, tenant_column)

    print(
        f"# {catalog}.{schema} | admin_group={admin_group!r} | "
        f"tables={tables} | tenant_column={tenant_column!r}"
    )
    if profile:
        print(f"# using workspace client profile: {profile}")

    if args.dry_run:
        print("# --dry-run: printing SQL only, not executing\n")
        for label, stmt in steps:
            print(f"-- {label}")
            print(f"{stmt};\n")
        return 0

    from databricks.sdk.service.sql import StatementState

    w = _get_client(profile)
    warehouse_id = _resolve_warehouse_id(w, warehouse_name)
    print(f"# warehouse: {warehouse_name} ({warehouse_id})\n")

    def run(stmt: str) -> None:
        r = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            catalog=catalog,
            schema=schema,
            statement=stmt,
            wait_timeout="30s",
        )
        while r.status and r.status.state in (
            StatementState.PENDING,
            StatementState.RUNNING,
        ):
            time.sleep(0.5)
            r = w.statement_execution.get_statement(r.statement_id)
        if not r.status or r.status.state != StatementState.SUCCEEDED:
            err = r.status.error if r.status else "unknown error"
            raise RuntimeError(f"statement failed: {err}")

    for label, stmt in steps:
        print(f"-> {label} ...")
        run(stmt)
        print(f"   ok: {label}")

    print("\ndone. Verify with: python scripts/tenants/verify_isolation.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
