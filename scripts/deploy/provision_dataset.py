#!/usr/bin/env python3
"""Recreate the Prism travel demo dataset in a *different* workspace.

The SQL in ``scripts/fevm/`` was written against the FEVM workspace and hardcodes
``serverless_stable_71zsua_catalog.prism_travel``. Standing the demo up somewhere
else (a public workspace, a customer's, a fresh FEVM) otherwise means hand-editing
those files, which is how the two copies drift. This retargets them at run time
instead, so the checked-in SQL stays the single source of truth.

It (idempotently):

  1. creates the target schema,
  2. builds ``summarydataset`` (~250k rows) from ``gen_travel_summarydataset.sql``,
  3. builds the ``travel_metrics`` metric view from ``create_travel_metrics_fevm.sql``,
  4. reports the row count so you know the load actually landed.

Each file is executed as a **single statement**: the metric view carries its YAML
body inside ``$$ ... $$`` and that YAML contains semicolons, so splitting on ``;``
would corrupt it.

Usage:
    python scripts/deploy/provision_dataset.py --profile personal \\
        --catalog workspace --schema prism_travel
    python scripts/deploy/provision_dataset.py --profile personal \\
        --catalog workspace --schema prism_travel --dry-run
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_SQL_DIR = _REPO / "scripts" / "fevm"

# The fully-qualified prefix baked into the checked-in SQL. Identifiers cannot be
# bound as query parameters, so retargeting is textual by necessity.
_SOURCE_FQN = "serverless_stable_71zsua_catalog.prism_travel"

_STEPS = (
    ("summarydataset (~250k rows)", "gen_travel_summarydataset.sql"),
    ("travel_metrics metric view", "create_travel_metrics_fevm.sql"),
)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Recreate the Prism travel demo dataset in another workspace.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--profile", required=True, help="Databricks CLI profile")
    p.add_argument("--catalog", required=True, help="target UC catalog")
    p.add_argument("--schema", default="prism_travel", help="target UC schema")
    p.add_argument(
        "--warehouse-id",
        default=None,
        help="SQL warehouse to run the DDL on (default: first available)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would run without touching the workspace",
    )
    return p.parse_args(argv)


def _retarget(path: Path, catalog: str, schema: str) -> str:
    sql = path.read_text()
    if _SOURCE_FQN not in sql:
        raise RuntimeError(
            f"{path.name} no longer references {_SOURCE_FQN} — the SQL was edited; "
            "update _SOURCE_FQN so retargeting keeps working."
        )
    return sql.replace(_SOURCE_FQN, f"{catalog}.{schema}").strip().rstrip(";")


def _resolve_warehouse(w, warehouse_id: str | None) -> str:
    if warehouse_id:
        return warehouse_id
    for wh in w.warehouses.list():
        if wh.id:
            return wh.id
    raise RuntimeError("no SQL warehouse available in this workspace")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    target = f"{args.catalog}.{args.schema}"

    statements = [(label, _retarget(_SQL_DIR / fname, args.catalog, args.schema))
                  for label, fname in _STEPS]

    if args.dry_run:
        print(f"# would provision {target} using profile {args.profile}")
        for label, stmt in statements:
            print(f"-> {label}: {len(stmt)} chars, first line: {stmt.splitlines()[0][:80]}")
        return 0

    from databricks.sdk import WorkspaceClient
    from databricks.sdk.service.sql import StatementState

    w = WorkspaceClient(profile=args.profile)
    warehouse_id = _resolve_warehouse(w, args.warehouse_id)
    print(f"# workspace: {args.profile} | warehouse: {warehouse_id} | target: {target}\n")

    def run(stmt: str, *, catalog: str | None = None, schema: str | None = None):
        r = w.statement_execution.execute_statement(
            warehouse_id=warehouse_id,
            catalog=catalog,
            schema=schema,
            statement=stmt,
            wait_timeout="30s",
        )
        # A 250k-row CTAS on a 2X-Small comfortably outlives the 30s wait ceiling,
        # so poll rather than treating the first non-terminal reply as a failure.
        waited = 0.0
        while r.status and r.status.state in (StatementState.PENDING, StatementState.RUNNING):
            time.sleep(2.0)
            waited += 2.0
            if waited > 900:
                raise RuntimeError("statement still running after 15 minutes")
            r = w.statement_execution.get_statement(r.statement_id)
        if not r.status or r.status.state != StatementState.SUCCEEDED:
            raise RuntimeError(f"statement failed: {r.status.error if r.status else 'unknown'}")
        return r

    print(f"-> creating schema {target} ...")
    run(f"CREATE SCHEMA IF NOT EXISTS {target}")
    print("   ok")

    for label, stmt in statements:
        print(f"-> {label} ...")
        started = time.time()
        run(stmt, catalog=args.catalog, schema=args.schema)
        print(f"   ok ({time.time() - started:.0f}s)")

    res = run(f"SELECT COUNT(*) FROM {target}.summarydataset")
    rows = res.result.data_array[0][0] if res.result and res.result.data_array else "?"
    print(f"\ndone. {target}.summarydataset has {rows} rows.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
