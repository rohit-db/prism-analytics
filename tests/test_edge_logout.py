"""Signing out must actually sign you out.

Behind the edge there are two session cookies and only one of them is the
credential: ``apex_edge_session`` is what the gate checks, and the proxy re-mints
the app's ``prism_session`` from it on every request. So the app's own ``/logout``
is a no-op here — it clears a cookie the proxy immediately overwrites, leaving
the user signed in with no way back to the login screen.

The edge therefore owns the auth surface and intercepts both ``/logout`` and
``/login`` instead of proxying them. These tests pin that, because the failure is
silent: logout returns a perfectly good 303 and the user stays logged in.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from edge.app import app
from edge.auth import SESSION_COOKIE, DemoUser, issue_session
from edge.config import CONFIG

BEN = DemoUser("ben@globex.com", "Ben Ortiz", "Globex", "globex")

APP_COOKIE = CONFIG.app_session_cookie


@pytest.fixture()
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture()
def signed_in(client):
    """A client carrying a valid edge session."""
    client.cookies.set(SESSION_COOKIE, issue_session(BEN))
    return client


def _cleared(response, name: str) -> bool:
    """True when the response tells the browser to drop ``name``."""
    return any(
        name in h and ('=""' in h or "=;" in h or "Max-Age=0" in h)
        for h in response.headers.get_list("set-cookie")
    )


# ------------------------------------------------------------------- /logout
@pytest.mark.parametrize("method", ["get", "post"])
def test_logout_clears_the_edge_session(signed_in, method):
    """The cookie that actually authenticates the user."""
    r = getattr(signed_in, method)("/logout")

    assert _cleared(r, SESSION_COOKIE), (
        f"edge session not cleared: {r.headers.get_list('set-cookie')}"
    )


def test_logout_clears_the_app_session(signed_in):
    r = signed_in.get("/logout")

    assert _cleared(r, APP_COOKIE), (
        f"app session not cleared: {r.headers.get_list('set-cookie')}"
    )


def test_logout_sends_the_user_to_the_edge_login(signed_in):
    r = signed_in.get("/logout")

    assert r.status_code == 303
    assert r.headers["location"] == "/__edge/login"


def test_logout_is_not_proxied_upstream(signed_in):
    """If this proxied, the app would answer and the edge session would survive.

    The upstream host is unreachable from the test environment, so a proxied
    request would error rather than return a clean redirect — but assert on the
    redirect target too, so the test states the intent rather than the accident.
    """
    r = signed_in.get("/logout")

    assert r.status_code == 303
    assert r.headers["location"].startswith("/__edge/")


def test_user_is_unauthenticated_after_logout(client):
    """The whole point: no session afterwards, so the gate stops the next call."""
    client.cookies.set(SESSION_COOKIE, issue_session(BEN))
    client.get("/logout")
    client.cookies.clear()  # the browser honours the Set-Cookie deletions

    r = client.get("/api/me", headers={"accept": "application/json"})

    assert r.status_code == 401


def test_logout_works_without_a_session(client):
    """Double-clicking sign out must not 500."""
    r = client.get("/logout")

    assert r.status_code == 303
    assert r.headers["location"] == "/__edge/login"


# -------------------------------------------------------------------- /login
def test_app_login_redirects_to_the_edge_login(client):
    """Otherwise the user meets a second, different sign-in form (double login)."""
    r = client.get("/login", headers={"accept": "text/html"})

    assert r.status_code == 303
    assert r.headers["location"].startswith("/__edge/login")


def test_app_login_preserves_the_next_target(client):
    r = client.get("/login?next=/ask", headers={"accept": "text/html"})

    assert r.headers["location"] == "/__edge/login?next=/ask"


# --------------------------------------------------------------------- gate
def test_html_navigation_without_a_session_goes_to_the_login_screen(client):
    r = client.get("/", headers={"accept": "text/html"})

    assert r.status_code == 303
    assert r.headers["location"].startswith("/__edge/login")
