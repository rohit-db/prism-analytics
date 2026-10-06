#!/usr/bin/env python3
"""Export a curated Genie space from one workspace and recreate it in another.

Third companion to ``provision_dataset.py`` / ``provision_dashboard.py``. A Genie
space is more than a pointer at a table — the curated sample questions and the
instructions in its description are what make "Ask Prism" answer well on the
first try. Recreating that by hand in each workspace loses the curation, so the
definition is exported to ``scripts/fevm/travel_genie_space.json`` and replayed.

The create API takes ``serialized_space`` (a JSON *string*) and rejects a bare
table list, which is why an export step exists at all rather than building the
space from arguments.

Usage:
    # refresh the checked-in definition from the workspace that owns it
    python scripts/deploy/provision_genie.py --export \\
        --from-profile fevm-stable-71zsua --space-id 01f18f363d9e193495d201f4b836151d

    # recreate it somewhere else, retargeted at that workspace's tables
    python scripts/deploy/provision_genie.py --profile personal \\
        --catalog workspace --schema prism_travel
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

_DEF = _REPO / "scripts" / "fevm" / "travel_genie_space.json"
_SOURCE_FQN = "serverless_stable_71zsua_catalog.prism_travel"


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Export/import the Prism Genie space.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--export", action="store_true", help="refresh the checked-in definition")
    p.add_argument("--from-profile", default=None, help="source profile (with --export)")
    p.add_argument("--space-id", default=None, help="source space id (with --export)")
    p.add_argument("--profile", default=None, help="target profile (import mode)")
    p.add_argument("--catalog", default=None, help="target UC catalog (import mode)")
    p.add_argument("--schema", default="prism_travel", help="target UC schema")
    p.add_argument("--warehouse-id", default=None, help="warehouse (default: first available)")
    return p.parse_args(argv)


def _export(from_profile: str, space_id: str) -> int:
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient(profile=from_profile)
    got = w.api_client.do(
        "GET", f"/api/2.0/genie/spaces/{space_id}", query={"include_serialized_space": "true"}
    )
    _DEF.write_text(json.dumps(
        {
            "title": got.get("title"),
            "description": got.get("description"),
            "serialized_space": json.loads(got["serialized_space"]),
        },
        indent=2,
    ) + "\n")
    print(f"# wrote {_DEF.relative_to(_REPO)} from {from_profile}:{space_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.export:
        if not (args.from_profile and args.space_id):
            raise SystemExit("--export requires --from-profile and --space-id")
        return _export(args.from_profile, args.space_id)

    if not (args.profile and args.catalog):
        raise SystemExit("import mode requires --profile and --catalog")

    from databricks.sdk import WorkspaceClient

    spec = json.loads(_DEF.read_text())
    serialized = json.dumps(spec["serialized_space"]).replace(
        _SOURCE_FQN, f"{args.catalog}.{args.schema}"
    )

    w = WorkspaceClient(profile=args.profile)
    warehouse_id = args.warehouse_id or next(
        (wh.id for wh in w.warehouses.list() if wh.id), None
    )
    if not warehouse_id:
        raise RuntimeError("no SQL warehouse available")

    existing = next(
        (s for s in w.api_client.do("GET", "/api/2.0/genie/spaces").get("spaces", [])
         if s.get("title") == spec["title"]),
        None,
    )
    if existing:
        print(f"# space '{spec['title']}' already exists: {existing['space_id']}")
        space_id = existing["space_id"]
    else:
        created = w.api_client.do(
            "POST",
            "/api/2.0/genie/spaces",
            body={
                "title": spec["title"],
                "description": spec["description"],
                "warehouse_id": warehouse_id,
                "serialized_space": serialized,
            },
        )
        space_id = created["space_id"]
        print(f"# created Genie space {space_id}")

    print(f"\nGENIE_SPACE_ID: {space_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
