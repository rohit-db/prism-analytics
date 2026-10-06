"""Edge token broker — mints and caches the edge Service Principal's OAuth M2M
token.

This is the single token the edge injects on every request it forwards
upstream, so the Databricks Apps OAuth proxy admits the call without showing
the end user Databricks SSO.

Self-contained (no ``server`` import): a small thread-safe client-credentials
minter against ``<workspace_host>/oidc/v1/token``, cached until ~5 minutes
before expiry.
"""
from __future__ import annotations

import logging
import threading
import time

import requests

from edge.config import CONFIG

logger = logging.getLogger("edge.broker")


class EdgeTokenBroker:
    def __init__(self) -> None:
        self._host = CONFIG.workspace_host.rstrip("/")
        self._token: str | None = None
        self._expires_at: float = 0.0
        self._lock = threading.Lock()

    def bearer(self) -> str:
        """Current edge SP access token (minted on first use, then cached)."""
        now = time.time()
        with self._lock:
            if self._token and self._expires_at - 300 > now:
                return self._token
            token, expires_in = self._fetch()
            self._token = token
            self._expires_at = now + expires_in
            return token

    def invalidate(self) -> None:
        with self._lock:
            self._token = None
            self._expires_at = 0.0

    def _fetch(self) -> tuple[str, int]:
        logger.info("Minting edge SP token at %s/oidc/v1/token", self._host)
        resp = requests.post(
            f"{self._host}/oidc/v1/token",
            data={"grant_type": "client_credentials", "scope": CONFIG.oauth_scope},
            auth=(CONFIG.sp_client_id, CONFIG.sp_client_secret),
            timeout=30,
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Edge SP token exchange failed ({resp.status_code}): {resp.text[:300]}"
            )
        body = resp.json()
        return body["access_token"], int(body.get("expires_in", 3600))


broker = EdgeTokenBroker()
