"""``/api/me`` must report the logged-in user, never the Service Principal.

Every request into this app arrives as a Service Principal — the app's own, or
the tenant's after the resolver swap. So "who is the Databricks caller?" is
always the wrong answer to "who is the user?". These tests pin that: when a
white-label session exists it wins, and the workspace identity is only a
last-resort fallback for the auth-disabled path.

This is a regression guard. The symptom it prevents is subtle and demo-visible:
sign in as a tenant user, and the avatar greets you as the app SP.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from server.auth.sessions import SESSION_COOKIE, create_session

SECRET = "test-me-endpoint-secret"

BEN = {
    "email": "ben@globex.com",
    "display_name": "Ben Ortiz",
    "tenant": "Globex",
    "tenant_id": "globex",
    "role": "user",
}
DANA = {
    "email": "dana@prism.example",
    "display_name": "Dana Lee",
    "tenant": "All Clients",
    "tenant_id": "*",
    "role": "operator",
}


@pytest.fixture(autouse=True)
def _auth_on(monkeypatch):
    monkeypatch.setenv("AUTH_SESSION_SECRET", SECRET)
    monkeypatch.setenv("AUTH_ENABLED", "true")


@pytest.fixture()
def client():
    from app import app

    return TestClient(app, raise_server_exceptions=True)


def _me(client, identity: dict) -> dict:
    client.cookies.set(SESSION_COOKIE, create_session(identity))
    r = client.get("/api/me")
    assert r.status_code == 200, r.text
    return r.json()


def test_me_reports_the_session_user(client):
    body = _me(client, BEN)

    assert body["displayName"] == "Ben Ortiz"
    assert body["email"] == "ben@globex.com"
    assert body["initials"] == "BO"


def test_me_does_not_leak_the_service_principal(client):
    """The bug this file exists for: the SP identity shown as the user."""
    body = _me(client, BEN)

    blob = " ".join(str(v) for v in body.values()).lower()
    for sp_marker in ("service principal", "prism-analytics", "app-"):
        assert sp_marker not in blob, f"SP identity leaked into /api/me: {body}"


def test_me_carries_tenant_and_role(client):
    """The shell uses these to scope the UI (operator nav, tenant label)."""
    body = _me(client, DANA)

    assert body["role"] == "operator"
    assert body["tenant"] == "All Clients"
    assert body["tenantId"] == "*"


def test_me_defaults_role_to_user(client):
    body = _me(client, {"email": "carol@initech.com", "display_name": "Carol Diaz",
                        "tenant": "Initech", "tenant_id": "initech"})

    assert body["role"] == "user"


def test_two_sessions_get_two_identities(client):
    """Distinct logins must not collapse onto one identity."""
    ben = _me(client, BEN)
    dana = _me(client, DANA)

    assert ben["email"] != dana["email"]
    assert ben["displayName"] != dana["displayName"]


def test_me_falls_back_to_email_when_display_name_is_missing(client):
    body = _me(client, {"email": "erin@umbrella.com", "tenant_id": "umbrella"})

    assert body["displayName"] == "erin@umbrella.com"


def test_a_forged_session_is_not_trusted(client, monkeypatch):
    """A cookie signed with the wrong key must not become an identity."""
    forged = create_session(BEN)
    monkeypatch.setenv("AUTH_SESSION_SECRET", "a-different-secret")

    client.cookies.set(SESSION_COOKIE, forged)
    r = client.get("/api/me")

    assert r.status_code == 401, (
        f"forged session was accepted: {r.status_code} {r.text}"
    )
