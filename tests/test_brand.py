import json
import re

import pytest

from server import brand


def test_load_brand_returns_config_values():
    b = brand.load_brand()
    assert b["identity"]["appName"] == "Prism"
    assert b["colors"]["primary"].startswith("#")


def test_load_brand_failsoft_on_missing_file(monkeypatch, tmp_path):
    # Point the loader at a nonexistent path -> must return defaults, not raise.
    monkeypatch.setenv("BRAND_CONFIG_FILE", str(tmp_path / "nope.json"))
    b = brand.load_brand()
    assert b == brand.DEFAULT_BRAND


def test_load_brand_failsoft_on_bad_json(monkeypatch, tmp_path):
    bad = tmp_path / "brand.config.json"
    bad.write_text("{ not valid json")
    monkeypatch.setenv("BRAND_CONFIG_FILE", str(bad))
    assert brand.load_brand() == brand.DEFAULT_BRAND


def test_brand_config_file_env_selects_another_brand(monkeypatch, tmp_path):
    """BRAND_CONFIG_FILE is the seam that lets one build serve many brands."""
    other = tmp_path / "retail.json"
    other.write_text('{"identity": {"appName": "Meridian Retail"}, "colors": {"accent": "#b8590a"}}')
    monkeypatch.setenv("BRAND_CONFIG_FILE", str(other))
    b = brand.load_brand()
    assert b["identity"]["appName"] == "Meridian Retail"
    assert b["colors"]["accent"] == "#b8590a"
    # Unspecified keys still fall back to the defaults (shallow merge).
    assert b["identity"]["logo"] == brand.DEFAULT_BRAND["identity"]["logo"]


def test_brand_color_helper():
    assert brand.brand_color("primary").startswith("#")
    assert brand.brand_color("nonexistent") == brand.DEFAULT_BRAND["colors"].get(
        "nonexistent", "#4f46e5"
    )


# ------------------------------------------------------- logo mark resolution
def test_absent_brand_mark_falls_back_to_the_monogram():
    """brand.config.json always *names* a logoMark, but the file is optional.

    frontend/public/brand/README.md promises a monogram fallback when it is
    absent; emitting an <img> for a path that 404s shows a broken image instead.
    """
    from server.auth.login import render_login_page
    from server.brand import brand_asset_exists, load_brand

    mark = load_brand()["identity"]["logoMark"]
    if brand_asset_exists(mark):
        pytest.skip("this instance ships a logo mark, so the <img> is correct")

    html_out = render_login_page()
    logo = re.search(r'class="logo">(.*?)</div>', html_out, re.S).group(1)

    assert "<img" not in logo, "renders an <img> for a brand mark that does not exist"
    assert logo.strip() == load_brand()["identity"]["shortName"][:1].upper()


def test_shipped_brand_mark_is_used(tmp_path, monkeypatch):
    from server.auth.login import render_login_page

    (tmp_path / "mark.svg").write_text("<svg/>")
    monkeypatch.setenv("BRAND_ASSETS_DIR", str(tmp_path))

    html_out = render_login_page()

    assert "<img" in re.search(r'class="logo">(.*?)</div>', html_out, re.S).group(1)


def test_brand_asset_exists_rejects_non_paths():
    from server.brand import brand_asset_exists

    assert brand_asset_exists("") is False
    assert brand_asset_exists("brand/mark.svg") is False
