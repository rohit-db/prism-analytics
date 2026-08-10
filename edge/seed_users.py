"""Create the apex_app_users table in Lakebase and seed the demo logins.

Run once after creating the Lakebase project and filling EDGE_PG_* in .env:

    python -m edge.seed_users
"""
from __future__ import annotations

from edge import auth, users
from edge.config import CONFIG


def main() -> None:
    if not CONFIG.lakebase_enabled:
        raise SystemExit("EDGE_LAKEBASE_ENABLED is not set — nothing to seed.")
    print(f"Seeding Lakebase instance '{CONFIG.pg_instance}' "
          f"({CONFIG.pg_host}) as {CONFIG.pg_user} ...")
    n = auth.seed_users()
    rows = users.list_all()
    print(f"Seeded {n} users; directory now has {len(rows)}:")
    for r in rows:
        print(f"  - {r.email:28} {r.tenant:16} external_value={r.external_value} role={r.role}")


if __name__ == "__main__":
    main()
