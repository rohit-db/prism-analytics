"""The edge -> app identity handoff.

The edge signs a session that the app verifies, in two different processes that
deliberately share no code. That makes the wire format a contract, and these
tests are what pin it: if either side's payload keys, signing scheme, or cookie
handling drift, the app stops recognizing edge logins and silently serves every
tenant as the app SP — the exact failure this handoff exists to prevent.
"""
from __future__ import annotations

import dataclasses
import time

import pytest

from edge import appsession, proxy
from edge.auth import DemoUser
from server.auth.sessions import verify_session

SECRET = "test-shared-session-secret"

BEN = DemoUser("ben@globex.com", "Ben Ortiz", "Globex", "globex")
DANA = DemoUser("dana@prism.example", "Dana Lee", "All Clients", "*", role="operator")


@pytest.fixture(autouse=True)
def _shared_secret(monkeypatch):
    """Point both sides at the same signing key."""
    monkeypatch.setattr(
        appsession, "CONFIG",
        dataclasses.replace(appsession.CONFIG, app_session_secret=SECRET),
    )
    monkeypatch.setenv("AUTH_SESSION_SECRET", SECRET)


def test_app_accepts_an_edge_minted_session():
    identity = verify_session(appsession.mint(BEN))

    assert identity is not None, "the app rejected a session the edge minted"
    assert identity["email"] == "ben@globex.com"
    assert identity["display_name"] == "Ben Ortiz"
    assert identity["role"] == "user"


def test_tenant_id_survives_the_handoff():
    """The join key into apex_client_registry — the whole point of the handoff."""
    assert verify_session(appsession.mint(BEN))["tenant_id"] == "globex"
    assert verify_session(appsession.mint(DANA))["tenant_id"] == "*"


def test_operator_role_survives_the_handoff():
    assert verify_session(appsession.mint(DANA))["role"] == "operator"


def test_app_rejects_a_session_signed_with_another_key(monkeypatch):
    forged = appsession.mint(BEN)
    monkeypatch.setenv("AUTH_SESSION_SECRET", "a-different-secret")

    assert verify_session(forged) is None


def test_app_rejects_a_tampered_payload():
    payload, sig = appsession.mint(BEN).rsplit(".", 1)
    other_payload = appsession.mint(DANA).rsplit(".", 1)[0]

    assert verify_session(f"{other_payload}.{sig}") is None


def test_app_rejects_an_expired_session():
    stale = appsession.mint(BEN, expires_at=int(time.time()) - 1)

    assert verify_session(stale) is None


def test_minting_is_disabled_without_a_shared_secret(monkeypatch):
    """No secret must mean no identity, never an unsigned or default-signed one."""
    monkeypatch.setattr(
        appsession, "CONFIG",
        dataclasses.replace(appsession.CONFIG, app_session_secret=""),
    )

    assert appsession.enabled() is False
    assert appsession.mint_from_session({"u": "ben@globex.com"}) is None


def test_edge_session_round_trips_into_an_app_session():
    from edge.auth import issue_session, verify_session as verify_edge_session

    edge_session = verify_edge_session(issue_session(BEN))
    identity = verify_session(appsession.mint_from_session(edge_session))

    assert identity["email"] == "ben@globex.com"
    assert identity["tenant_id"] == "globex"


def test_app_session_expires_with_the_edge_session():
    """Otherwise a stale upstream token could outlive the login it came from."""
    edge_exp = int(time.time()) + 60
    identity = verify_session(
        appsession.mint_from_session({"u": "ben@globex.com", "tenant_id": "globex",
                                      "role": "user", "exp": edge_exp})
    )

    assert identity["exp"] == edge_exp


# --------------------------------------------------------------- cookie hygiene
def test_client_supplied_session_cookie_is_replaced():
    """The browser must not be able to nominate its own identity upstream."""
    out = proxy._set_upstream_cookie(
        "prism_session=forged-by-client; theme=dark", "prism_session", "minted-by-edge"
    )

    assert "forged-by-client" not in out
    assert "prism_session=minted-by-edge" in out


def test_client_supplied_session_cookie_is_dropped_when_unauthenticated():
    out = proxy._set_upstream_cookie("prism_session=stale; theme=dark",
                                     "prism_session", None)

    assert "prism_session" not in out
    assert out == "theme=dark"


def test_unrelated_cookies_pass_through_untouched():
    out = proxy._set_upstream_cookie("theme=dark; lang=en", "prism_session", None)

    assert out == "theme=dark; lang=en"
