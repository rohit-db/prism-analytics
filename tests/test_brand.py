import json
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
