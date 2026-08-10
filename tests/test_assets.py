from fastapi.testclient import TestClient

from server.assets import registry as assets

# The seed carries deployment config: its dashboard id and page ids change every
# time the app is pointed at a new workspace. Read the expected id from the seed
# rather than freezing a literal, so these tests keep asserting the wiring
# (dedup, defaulting, catalog shape) instead of failing on a retarget.
_SEED_ASSETS = assets.load_registry()["assets"]
SEED_DASHBOARD_ID = _SEED_ASSETS["spend"]["dashboardId"]


def test_load_registry_has_seed_assets():
    reg = assets.load_registry()
    a = reg["assets"]
    assert "spend" in a and "sustainability" in a
    assert a["spend"]["label"] == "Spend"
    assert a["spend"]["dashboardId"]
    # per-page Genie prompts moved off ROUTES into the seed
    for page in a["spend"]["pages"]:
        assert page["summaryPrompt"].strip()
        assert len(page["suggestions"]) == 3
    assert "SPEND" in a["spend"]["pages"][0]["summaryPrompt"].upper()


def test_dashboard_ids_are_deduped():
    # spend + sustainability share one physical dashboard id -> one entry
    assert _SEED_ASSETS["sustainability"]["dashboardId"] == SEED_DASHBOARD_ID
    assert assets.dashboard_ids() == [SEED_DASHBOARD_ID]


def test_default_dashboard_id():
    assert assets.default_dashboard_id() == SEED_DASHBOARD_ID


def test_catalog_dashboards_shape():
    cat = assets.catalog_dashboards()
    assert cat == [{"id": SEED_DASHBOARD_ID, "name": "Spend"}]


def test_load_registry_failsoft_on_missing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(assets, "_SEED_PATH", str(tmp_path / "nope.json"))
    monkeypatch.setattr(assets, "_cache", None)  # bypass any cached parse
    reg = assets.load_registry()
    assert reg == {"assets": {}}
    assert assets.dashboard_ids() == []
    assert assets.default_dashboard_id() is None


def test_load_registry_failsoft_on_bad_json(monkeypatch, tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{ not valid json ")
    monkeypatch.setattr(assets, "_SEED_PATH", str(bad))
    monkeypatch.setattr(assets, "_cache", None)
    assert assets.load_registry() == {"assets": {}}


def test_get_api_assets_returns_registry(monkeypatch):
    # Auth gate is a no-op unless AUTH_ENABLED; keep it off for this unit check.
    # Import app FIRST (its load_dotenv() sets AUTH_ENABLED from .env), THEN
    # delenv below — clearing before the import would let load_dotenv re-add it.
    import app as app_module
    monkeypatch.delenv("AUTH_ENABLED", raising=False)

    client = TestClient(app_module.app)
    res = client.get("/api/assets")
    assert res.status_code == 200
    body = res.json()
    assert "spend" in body["assets"]
    assert body["assets"]["spend"]["dashboardId"] == SEED_DASHBOARD_ID


def test_get_api_assets_filters_by_tenant_entitlement(monkeypatch):
    """A tenant sees only assets whose dashboardId its SP can access."""
    import app as app_module
    from server.routes import api as api_module

    # Registry: two assets on two distinct physical dashboards.
    reg = {"assets": {
        "spend": {"label": "Spend", "dashboardId": "DASH-A", "pages": []},
        "sustain": {"label": "Sustainability", "dashboardId": "DASH-B", "pages": []},
    }}
    monkeypatch.setattr(api_module.assets_registry, "load_registry", lambda: reg)
    # A resolved tenant SP whose ACL grants only DASH-A.
    monkeypatch.setattr(api_module, "resolve_tenant_sp",
                        lambda request: ("tok", type("Row", (), {"sp_app_id": "sp-1"})()))
    monkeypatch.setattr(api_module, "tenant_access",
                        lambda sp: {"dashboards": {"DASH-A": True, "DASH-B": False}, "genie_spaces": {}})

    client = TestClient(app_module.app)
    body = client.get("/api/assets").json()
    assert "spend" in body["assets"]
    assert "sustain" not in body["assets"]  # ungranted -> hidden


def test_get_api_assets_operator_sees_all(monkeypatch):
    """resolve_tenant_sp None (operator/*/pre-onboarding) -> unfiltered registry."""
    import app as app_module
    from server.routes import api as api_module

    reg = {"assets": {
        "spend": {"label": "Spend", "dashboardId": "DASH-A", "pages": []},
        "sustain": {"label": "Sustainability", "dashboardId": "DASH-B", "pages": []},
    }}
    monkeypatch.setattr(api_module.assets_registry, "load_registry", lambda: reg)
    monkeypatch.setattr(api_module, "resolve_tenant_sp", lambda request: None)

    client = TestClient(app_module.app)
    body = client.get("/api/assets").json()
    assert set(body["assets"].keys()) == {"spend", "sustain"}


def test_get_api_assets_failsoft_on_acl_error(monkeypatch):
    """If entitlement lookup raises, return the full registry rather than lock out."""
    import app as app_module
    from server.routes import api as api_module

    reg = {"assets": {"spend": {"label": "Spend", "dashboardId": "DASH-A", "pages": []}}}
    monkeypatch.setattr(api_module.assets_registry, "load_registry", lambda: reg)
    monkeypatch.setattr(api_module, "resolve_tenant_sp",
                        lambda request: ("tok", type("Row", (), {"sp_app_id": "sp-1"})()))
    def _boom(sp):
        raise RuntimeError("workspace down")
    monkeypatch.setattr(api_module, "tenant_access", _boom)

    client = TestClient(app_module.app)
    body = client.get("/api/assets").json()
    assert "spend" in body["assets"]  # failed soft -> visible


def test_resources_catalog_uses_registry_dashboards(monkeypatch):
    # SET envs to empty string (NOT delenv): server.lakebase's module-level
    # load_dotenv(override=False) re-adds DELETED vars from .env, but leaves
    # an already-present empty string alone. Point the registry cache at a
    # DISTINCT id so we can prove the registry — not the env — is the source.
    monkeypatch.setenv("RESOURCE_DASHBOARDS", "")
    monkeypatch.setenv("DASHBOARD_IDS", "")
    from server.assets import registry as areg
    monkeypatch.setattr(areg, "_cache", {"assets": {"probe": {"label": "ProbeDash", "dashboardId": "registry-only-id-xyz"}}})
    from server.tenants import resources

    cat = resources.catalog()
    assert cat["dashboards"] == [{"id": "registry-only-id-xyz", "name": "ProbeDash"}]


def test_resources_catalog_env_overrides_registry(monkeypatch):
    monkeypatch.setenv("RESOURCE_DASHBOARDS", "envdash:Env Dashboard")
    from server.tenants import resources

    cat = resources.catalog()
    assert cat["dashboards"] == [{"id": "envdash", "name": "Env Dashboard"}]


def test_grant_dashboard_access_iterates_registry_ids(monkeypatch):
    # Same empty-string-not-delenv pattern; distinct id proves registry is exercised.
    monkeypatch.setenv("DASHBOARD_IDS", "")
    from server.assets import registry as areg
    monkeypatch.setattr(areg, "_cache", {"assets": {"probe": {"label": "ProbeDash", "dashboardId": "registry-only-id-xyz"}}})
    from server.tenants import service

    captured = []
    monkeypatch.setattr(service, "_permissions_patch", lambda path, sp, level: captured.append(path))
    service.grant_dashboard_access("sp-app-id-123")
    assert captured == ["/api/2.0/permissions/dashboards/registry-only-id-xyz"]


def test_embed_default_dashboard_id_prefers_registry(monkeypatch):
    # _DEFAULT_DASHBOARD_ID is set at IMPORT time so we can't patch before it.
    # Instead, test the derivation FUNCTION against a controlled registry cache —
    # this proves registry-primary. The module-level constant separately confirms
    # it resolved to the seed id at import (can't distinguish source there since
    # DASHBOARD_URL also encodes the same id, so the function test carries the proof).
    from server.assets import registry as areg
    monkeypatch.setattr(areg, "_cache", {"assets": {"probe": {"label": "P", "dashboardId": "registry-only-id-xyz"}}})
    from server.routes import embed

    assert embed._default_dashboard_id() == "registry-only-id-xyz"
