"""The edge's login page must look like the app's.

It is the first screen a customer sees, and for a while it was a *copy* of the
app's page — so when the app was rebranded, the edge kept serving the old brand.
These tests pin the two together: the edge renders the shared template, and the
only intended differences are the form's POST target and the user directory the
sample logins come from.
"""
from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from edge.app import app
from edge.login_page import ACTION, render_login_page
from server.auth.login import render_login_page as app_render
from server.brand import load_brand


@pytest.fixture()
def client():
    return TestClient(app, follow_redirects=False)


@pytest.fixture()
def page():
    return render_login_page()


def _tag(html: str, pattern: str) -> str:
    m = re.search(pattern, html, re.S)
    return m.group(1) if m else ""


# --------------------------------------------------------------- brand parity
def test_page_uses_the_brand_name(page):
    app_name = load_brand()["identity"]["appName"]

    assert _tag(page, r"<h1>(.*?)</h1>") == app_name
    assert app_name in _tag(page, r"<title>(.*?)</title>")


def test_page_does_not_carry_the_previous_brand(page):
    """The exact drift that prompted this: a stale hardcoded brand and palette."""
    stale = ["APEX", "#4f46e5", "#7c3aed", "--indigo", "--purple"]

    for token in stale:
        assert token not in page, f"stale branding {token!r} still in the login page"


def test_page_uses_the_brand_primary_colour(page):
    assert load_brand()["colors"]["primary"] in page


def test_styling_is_identical_to_the_app_login(page):
    """Shared template, so the CSS cannot drift between the two front doors."""
    assert _tag(page, r"<style>(.*?)</style>") == _tag(app_render(), r"<style>(.*?)</style>")


# ------------------------------------------------------- intended differences
def test_form_posts_to_the_edge(page):
    assert _tag(page, r'<form class="card" method="post" action="(.*?)"') == ACTION


def test_app_page_still_posts_to_the_app():
    assert _tag(app_render(), r'<form class="card" method="post" action="(.*?)"') == "/login"


def test_chips_come_from_the_edge_directory(page):
    """The edge has its own Lakebase connection; chips must reflect its users."""
    from edge.auth import list_logins

    for row in list_logins():
        assert row["email"] in page


def test_chips_are_tagged_with_their_role(page):
    """The user/operator toggle filters on this, so every chip needs a role."""
    roles = set(re.findall(r'data-role="(.*?)"', page))

    assert "operator" in roles, "no operator chip — the Operator tab would be empty"
    assert "user" in roles


# ---------------------------------------------------------------- mode toggle
def test_operator_mode_is_honoured(client):
    r = client.get("/__edge/login?mode=operator")

    assert r.status_code == 200
    assert 'data-active-mode="operator"' in r.text


def test_user_mode_is_the_default(client):
    r = client.get("/__edge/login")

    assert 'data-active-mode="user"' in r.text


# ------------------------------------------------------------- open redirect
@pytest.mark.parametrize("hostile", ["//evil.com", "https://evil.com", "javascript:alert(1)"])
def test_next_cannot_leave_the_site(client, hostile):
    """``//evil.com`` passes a naive startswith('/') check but is off-site."""
    r = client.get("/__edge/login", params={"next": hostile})

    assert f'value="{hostile}"' not in r.text
    assert 'name="next" value="/"' in r.text


@pytest.mark.parametrize("hostile", ["//evil.com", "https://evil.com"])
def test_login_does_not_redirect_off_site(client, hostile):
    r = client.post(
        "/__edge/login",
        data={"username": "ben@globex.com", "password": "apex", "next": hostile},
    )

    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_a_relative_next_is_preserved(client):
    r = client.post(
        "/__edge/login",
        data={"username": "ben@globex.com", "password": "apex", "next": "/ask"},
    )

    assert r.headers["location"] == "/ask"


# ------------------------------------------------------------------- errors
def test_a_failed_login_renders_the_branded_page(client):
    r = client.post(
        "/__edge/login",
        data={"username": "ben@globex.com", "password": "wrong", "next": "/"},
    )

    assert r.status_code == 401
    assert "Invalid email or password." in r.text
    assert load_brand()["identity"]["appName"] in r.text
