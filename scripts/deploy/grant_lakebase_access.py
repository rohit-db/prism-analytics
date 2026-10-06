#!/usr/bin/env python3
"""Grant a Databricks principal read/write access to the app's Lakebase tables.

Declaring the ``lakebase`` resource in ``databricks.yml`` gets the app's Service
Principal a Postgres *role* and ``USAGE`` on the schema — but **not** privileges
on the tables, because those are owned by whoever created them (typically an
operator running locally). The result is an app that connects successfully and
then fails every query, which surfaces as opaque 500s rather than a permission
error at startup.

This script closes that gap. It grants CRUD on all existing tables plus sequence
access (the ``SERIAL`` primary keys), and sets default privileges so tables
created later by the same owner are covered too.

Run it as the table **owner** (the identity that created the schema), not as the
app SP. Idempotent.

Usage:
    # default: whichever SP the deployed app runs as
    python scripts/deploy/grant_lakebase_access.py --profile fevm-stable-71zsua

    # or an explicit principal (e.g. the edge SP)
    python scripts/deploy/grant_lakebase_access.py --principal <client-id>
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

DEFAULT_APP = "prism-analytics"

# psycopg cannot parameterize identifiers, so principals are quoted manually.
# Postgres role names here are Databricks client ids / emails, never free text,
# but validate anyway rather than trusting the caller.
_ALLOWED = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_.@")

GRANTS = (
    'GRANT USAGE ON SCHEMA public TO "{p}"',
    'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "{p}"',
    'GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO "{p}"',
    'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
    'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "{p}"',
    'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
    'GRANT USAGE, SELECT ON SEQUENCES TO "{p}"',
)


def _quote_safe(principal: str) -> str:
    bad = set(principal) - _ALLOWED
    if bad or not principal:
        raise ValueError(f"unsafe principal name {principal!r} (chars: {sorted(bad)})")
    return principal


def _app_service_principal(app_name: str, profile: str) -> str:
    from databricks.sdk import WorkspaceClient

    app = WorkspaceClient(profile=profile).apps.get(name=app_name)
    sp = getattr(app, "service_principal_client_id", None)
    if not sp:
        raise RuntimeError(f"app {app_name!r} has no service_principal_client_id")
    return str(sp)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Grant a principal CRUD on the app's Lakebase tables.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--principal", default=None,
                   help="Postgres role to grant (default: the app's SP client id)")
    p.add_argument("--app", default=DEFAULT_APP, help="Databricks App name")
    p.add_argument("--profile",
                   default=os.environ.get("DATABRICKS_CONFIG_PROFILE", "DEFAULT"),
                   help="CLI profile used to look up the app's SP")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    principal = _quote_safe(
        args.principal or _app_service_principal(args.app, args.profile)
    )
    statements = [s.format(p=principal) for s in GRANTS]

    print(f"Principal: {principal}")
    for s in statements:
        print(f"  {s}")
    if args.dry_run:
        print("\nDry run — nothing executed.")
        return 0

    from server.lakebase import connection

    with connection() as conn:
        for s in statements:
            conn.execute(s)
        conn.commit()

        # Report the resulting state so a silent no-op is visible.
        with conn.cursor() as cur:
            cur.execute(
                "SELECT tablename, has_table_privilege(%s, tablename, 'SELECT'),"
                "       has_table_privilege(%s, tablename, 'INSERT')"
                "  FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename",
                (principal, principal),
            )
            rows = cur.fetchall()

    print("\nResulting privileges:")
    missing = 0
    for table, sel, ins in rows:
        flag = "ok " if (sel and ins) else "GAP"
        missing += 0 if (sel and ins) else 1
        print(f"  {flag} {table:26} SELECT={sel} INSERT={ins}")

    if missing:
        print(f"\n{missing} table(s) still not granted — check table ownership.")
        return 1
    print("\nAll tables granted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
