#!/usr/bin/env python3
"""Grant the app SP + every registered tenant SP CAN_RUN on dashboards/Genie spaces.

``service.onboard()`` already attempts the tenant grants, but it runs as the
``TENANTS_ADMIN_PROFILE`` identity. Workspace-admin is not sufficient here:
granting on a dashboard or Genie space needs CAN_MANAGE on that *object*, which
normally belongs to whoever authored it. When the app SP didn't author the
assets, onboarding logs a best-effort warning and moves on — the tenant is
registered and row-scoped, but its SP cannot mint an embed token.

The **app SP** needs the same CAN_RUN, and nothing onboards it: it is the
resolver's documented fall-back identity, used whenever
``resolve_tenant_sp()`` returns None (operator ``tenant_id="*"``, no Lakebase,
or pre-onboarding). Without the grant, every operator embed fails with a
misleading ``RESOURCE_DOES_NOT_EXIST`` — Databricks reports an unreadable
dashboard as missing rather than forbidden.

This script closes both gaps by re-running the grants as the **asset owner's**
CLI profile. It is idempotent: a permissions PATCH adds to the ACL, so
re-running is safe.

Usage:
    python scripts/tenants/grant_resource_access.py --profile fevm-stable-71zsua
    python scripts/tenants/grant_resource_access.py --dry-run
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()


_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def _is_real_id(value: str) -> bool:
    """Lakeview ids are 32 hex chars; anything else is a placeholder."""
    return bool(_ID_RE.match((value or "").strip().lower()))


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Grant tenant SPs CAN_RUN on the app's dashboards and Genie spaces.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument(
        "--profile",
        default=os.environ.get("DATABRICKS_CONFIG_PROFILE", "DEFAULT"),
        help="CLI profile of an identity with CAN_MANAGE on the assets",
    )
    p.add_argument(
        "--app-name",
        default=os.environ.get("DATABRICKS_APP_NAME", "prism-analytics"),
        help="Databricks App whose SP is the resolver's fall-back identity",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="print what would be granted without calling the API",
    )
    return p.parse_args(argv)


def _app_sp(w, app_name: str) -> str | None:
    """The app's SP client id, or None when not running as a Databricks App.

    External hosting (EC2/ECS/Docker) has no app resource; the fall-back SP is
    then whatever ``DATABRICKS_CLIENT_ID`` names, which the caller grants itself.
    """
    if not app_name:
        return None
    try:
        return (w.apps.get(name=app_name).service_principal_client_id or "").strip() or None
    except Exception as e:  # noqa: BLE001 — absence is a valid deployment shape
        print(f"  note: could not resolve app {app_name!r} ({str(e)[:80]}); "
              "skipping the app-SP grant")
        return None


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    from databricks.sdk import WorkspaceClient

    from server import assets as assets_registry
    from server.tenants import registry

    w = WorkspaceClient(profile=args.profile)

    tenants = [r for r in registry.list_tenants() if r.status == "active"]
    app_sp = _app_sp(w, args.app_name)
    if not tenants and not app_sp:
        print("No active tenants and no app SP — nothing to grant.")
        return 0

    # Placeholder nav entries carry a stand-in id that is not a real object.
    dashboards = [d for d in assets_registry.dashboard_ids() if _is_real_id(d)]
    targets: list[tuple[str, str]] = [
        (f"/api/2.0/permissions/dashboards/{d}", f"dashboard {d}")
        for d in dashboards
    ]
    genie_space = os.environ.get("GENIE_SPACE_ID", "").strip()
    if genie_space:
        targets.append(
            (f"/api/2.0/permissions/genie/{genie_space}", f"genie space {genie_space}")
        )

    if not targets:
        print("No dashboards or Genie spaces configured — nothing to grant.")
        return 0

    grantees = [(r.tenant_id, r.sp_app_id) for r in tenants]
    if app_sp:
        grantees.append(("app SP (resolver fall-back)", app_sp))

    acl = [
        {"service_principal_name": sp, "permission_level": "CAN_RUN"}
        for _, sp in grantees
    ]
    print(f"Granting CAN_RUN to {len(grantees)} SP(s): "
          f"{', '.join(label for label, _ in grantees)}")

    if args.dry_run:
        for _, label in targets:
            print(f"  would grant on {label}")
        return 0

    failures = 0
    for path, label in targets:
        try:
            w.api_client.do("PATCH", path, body={"access_control_list": acl})
            print(f"  ok   {label}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            print(f"  FAIL {label}: {str(e)[:160]}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
