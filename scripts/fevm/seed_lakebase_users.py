"""Seed the demo user directory into a fresh Lakebase instance.

When LAKEBASE_ENABLED=true the app reads users from the `apex_app_users` table,
not the JSON seed — and `ensure_schema()` creates that table empty. A brand-new
Lakebase (e.g. a fresh FEVM deployment) therefore has no users to authenticate
against. This one-shot loads `server/auth/users.seed.json` into Lakebase via the
app's own `ensure_schema()` + `_lakebase_upsert()`, so `verify_login` works.

Run once after pointing .env at a new Lakebase:
    python scripts/fevm/seed_lakebase_users.py
Idempotent (ON CONFLICT DO UPDATE).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Load .env exactly like the app does, then import the users repo so it picks up
# the same LAKEBASE_* config.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:  # noqa: BLE001
    pass

from server.auth import users as users_repo  # noqa: E402


def main() -> int:
    if not users_repo.LAKEBASE_ENABLED:
        print("LAKEBASE_ENABLED is false — nothing to seed (app uses JSON directly).")
        return 0
    users_repo.ensure_schema()
    seed = users_repo._load_json_users()  # noqa: SLF001 - deliberate reuse of the loader
    if not seed:
        print("No JSON seed users found — check AUTH_USERS_FILE.")
        return 1
    n = 0
    for u in seed:
        users_repo._lakebase_upsert(u)  # noqa: SLF001
        n += 1
    print(f"Seeded {n} users into Lakebase table '{users_repo.USERS_TABLE}':")
    for r in users_repo._lakebase_list():  # noqa: SLF001
        print(f"  - {r.email}  ({r.role}, tenant={r.tenant})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
