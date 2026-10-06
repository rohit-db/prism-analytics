#!/usr/bin/env python3
"""Seed the Lakebase login directory with one demo user per onboarded tenant.

Keeps ``apex_app_users`` in step with ``apex_client_registry``: every active
tenant gets a login whose ``tenant_id`` is that tenant's registry key, plus the
operator account that sees all rows. A login whose ``tenant_id`` has no
registered tenant resolves to no Service Principal and falls back to the app SP,
which looks indistinguishable from broken isolation — so this script reports any
such drift in both directions.

All seeded users share the demo password from ``server/auth/users.seed.json``.
Existing rows are updated in place (upsert by email); passwords are re-hashed,
so this also serves as a password reset.

Usage:
    python scripts/deploy/seed_demo_users.py
    python scripts/deploy/seed_demo_users.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

# Email local-part per tenant; anything not listed falls back to "user".
_CONTACT = {
    "acme-travel": ("alice", "Alice Chen"),
    "globex": ("ben", "Ben Ortiz"),
    "initech": ("carol", "Carol Nguyen"),
    "umbrella": ("erin", "Erin Walsh"),
    "meridian-health": ("maria", "Maria Alvarez"),
    "northwind-logistics": ("nathan", "Nathan Brooks"),
    "vantage-pharma": ("vivian", "Vivian Shah"),
    "atlas-energy": ("aaron", "Aaron Klein"),
    "blue-harbor": ("bianca", "Bianca Moreau"),
    "summit-mfg": ("sam", "Sam Whitfield"),
}

OPERATOR = ("dana@prism.example", "Dana Lee", "All Clients", "*", "operator")


def _contact_for(tenant_id: str, display_name: str) -> tuple[str, str]:
    local, name = _CONTACT.get(tenant_id, ("user", f"{display_name} User"))
    domain = tenant_id.replace("-", "") + ".com"
    return f"{local}@{domain}", name


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    from server.auth.sessions import hash_password
    from server.auth.users import USERS_FILE, UserRow, list_users, save_user
    from server.tenants import registry

    password = json.loads(Path(USERS_FILE).read_text()).get("demo_password") or "apex"

    tenants = [r for r in registry.list_tenants() if r.status == "active"]
    if not tenants:
        print("No active tenants in the registry — onboard tenants first.")
        return 1

    planned: list[UserRow] = []
    for t in tenants:
        email, name = _contact_for(t.tenant_id, t.display_name)
        planned.append(UserRow(email=email, password_hash="", display_name=name,
                               tenant=t.display_name, tenant_id=t.tenant_id))
    planned.append(UserRow(email=OPERATOR[0], password_hash="", display_name=OPERATOR[1],
                           tenant=OPERATOR[2], tenant_id=OPERATOR[3], role=OPERATOR[4]))

    print(f"Seeding {len(planned)} logins (shared password: {password!r}):")
    for u in planned:
        print(f"  {u.email:28} tenant_id={u.tenant_id:14} role={u.role}")

    if args.dry_run:
        print("\nDry run — nothing written.")
        return 0

    for u in planned:
        save_user(UserRow(email=u.email, password_hash=hash_password(password),
                          display_name=u.display_name, tenant=u.tenant,
                          tenant_id=u.tenant_id, role=u.role))

    # Report drift: logins pointing at tenants that are not onboarded.
    registered = {t.tenant_id for t in tenants} | {"*"}
    orphans = [u for u in list_users() if u.tenant_id not in registered]
    if orphans:
        print("\nWARNING — these logins have no registered tenant and will fall "
              "back to the app SP (no row scoping):")
        for u in orphans:
            print(f"  {u.email:28} tenant_id={u.tenant_id!r}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
