#!/usr/bin/env python3
"""Push the app's shared secrets from ``.env`` into a Databricks secret scope.

Two values must be identical everywhere the app runs, and neither can live in
``app.yaml`` (which is committed):

``AUTH_SESSION_SECRET``
    Signs the white-label session cookie. The edge gateway mints cookies the
    app must accept, so both processes have to agree on this key — if they
    diverge, every edge login is rejected and users silently fall back to the
    app Service Principal.

``AES_KEY_BASE64``
    Encrypts tenant SP client secrets at rest in Lakebase. Changing it does not
    just break new writes: **existing tenant credentials become undecryptable**,
    so every tenant must be re-onboarded. Treat it as write-once.

The deployed app reads both via ``valueFrom`` against the scope written here.
Values are never printed.

Usage:
    python scripts/deploy/sync_app_secrets.py --profile fevm-stable-71zsua
    python scripts/deploy/sync_app_secrets.py --scope prism --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from dotenv import dotenv_values  # noqa: E402

# Read `.env` *without* exporting it. It also holds DATABRICKS_HOST and the app
# SP's credentials, and the SDK ranks ambient environment above an explicit
# `profile=` — so `load_dotenv()` here made `--profile` a lie, quietly writing
# secrets into whatever workspace `.env` happened to point at.
_DOTENV = dotenv_values(_REPO / ".env")

DEFAULT_SCOPE = "prism"

# env var -> secret key within the scope
SECRETS = {
    "AUTH_SESSION_SECRET": "auth-session-secret",
    "AES_KEY_BASE64": "aes-key-base64",
}


def _fingerprint(value: str) -> str:
    """A short, non-reversible tag so operators can compare without disclosing."""
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Sync AUTH_SESSION_SECRET / AES_KEY_BASE64 into a secret scope.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--scope", default=DEFAULT_SCOPE, help="secret scope name")
    p.add_argument(
        "--profile",
        default=os.environ.get("DATABRICKS_CONFIG_PROFILE", "DEFAULT"),
        help="CLI profile with permission to manage the scope",
    )
    p.add_argument("--dry-run", action="store_true",
                   help="report what would be written, without writing")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    values = {}
    for env_name, key in SECRETS.items():
        raw = (os.environ.get(env_name) or _DOTENV.get(env_name) or "").strip()
        if not raw:
            print(f"ERROR: {env_name} is not set in the environment or .env")
            return 2
        values[key] = raw

    print(f"Scope '{args.scope}' on profile '{args.profile}':")
    for key, raw in values.items():
        print(f"  {key:22} (sha256:{_fingerprint(raw)})")

    if args.dry_run:
        print("\nDry run — nothing written.")
        return 0

    from databricks.sdk import WorkspaceClient
    from databricks.sdk.errors import ResourceAlreadyExists

    w = WorkspaceClient(profile=args.profile)
    try:
        w.secrets.create_scope(scope=args.scope)
        print(f"\nCreated scope '{args.scope}'.")
    except ResourceAlreadyExists:
        print(f"\nScope '{args.scope}' already exists — reusing.")

    for key, raw in values.items():
        w.secrets.put_secret(scope=args.scope, key=key, string_value=raw)
        print(f"  wrote {key}")

    print("\nDone. Reference these from app.yaml with `valueFrom:` and redeploy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
