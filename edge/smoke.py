#!/usr/bin/env python3
"""Prove the edge SP token clears the Databricks Apps OAuth proxy.

This is the one genuinely-unknown hop in the Firefly edge pattern: can a
*Service Principal* OAuth M2M token call a Databricks App and be admitted by
the Apps OAuth proxy (instead of bounced to interactive SSO)?

Run it before standing up the full edge:

    python edge/smoke.py        # reads edge/.env

It (1) mints the edge SP token at <EDGE_WORKSPACE_HOST>/oidc/v1/token, then
(2) hits the upstream app with and without that bearer, and reports whether
the bearer is what flips the result from "redirected to SSO / 401" to "200".
"""
from __future__ import annotations

import sys

import requests

from edge.config import CONFIG


def _classify(resp: requests.Response) -> str:
    loc = resp.headers.get("location", "")
    if resp.status_code in (301, 302, 303, 307, 308):
        if "oidc" in loc or "oauth" in loc or "login" in loc:
            return "redirect-to-sso"
        return f"redirect ({loc[:60]})"
    if resp.status_code == 401:
        return "unauthorized"
    if resp.status_code == 200:
        return "ok"
    return f"http {resp.status_code}"


def main() -> int:
    missing = CONFIG.missing()
    if missing:
        print(f"x missing config in edge/.env: {', '.join(missing)}", file=sys.stderr)
        return 2

    upstream = CONFIG.upstream
    probe = upstream + "/"

    print(f"> Upstream:  {upstream}")
    print(f"> Workspace: {CONFIG.workspace_host}")
    print(f"> Edge SP:   {CONFIG.sp_client_id}\n")

    base = requests.get(probe, allow_redirects=False, timeout=30)
    print(f"  without bearer -> {_classify(base)} (status {base.status_code})")

    print(f"> Minting edge SP token at {CONFIG.workspace_host}/oidc/v1/token "
          f"(scope={CONFIG.oauth_scope})...")
    tok = requests.post(
        f"{CONFIG.workspace_host.rstrip('/')}/oidc/v1/token",
        data={"grant_type": "client_credentials", "scope": CONFIG.oauth_scope},
        auth=(CONFIG.sp_client_id, CONFIG.sp_client_secret),
        timeout=30,
    )
    if tok.status_code != 200:
        print(f"x Token mint failed ({tok.status_code}): {tok.text[:300]}", file=sys.stderr)
        return 1
    token = tok.json()["access_token"]
    print("  ok token minted")

    auth = requests.get(probe, headers={"Authorization": f"Bearer {token}"},
                        allow_redirects=False, timeout=30)
    verdict = _classify(auth)
    print(f"  with bearer    -> {verdict} (status {auth.status_code})\n")

    if verdict == "ok":
        print("OK  The edge SP token CLEARS the Apps OAuth proxy. The edge pattern works.")
        return 0

    print("x  The edge SP token did NOT clear the proxy.")
    print("   Confirm the edge SP has CAN_USE on the app:")
    print("     databricks apps get advito-ai-bi -p bcd-customer | jq .")
    if auth.headers.get("location"):
        print(f"   location: {auth.headers['location'][:120]}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
