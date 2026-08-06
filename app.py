from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from server.brand import load_brand
app = FastAPI(title=f"{load_brand()['identity']['appName']} API")

# White-label session gate. No-op when AUTH_ENABLED is unset/false, so the
# default Databricks-Apps behavior is unchanged.
from server.auth import SessionGateMiddleware, router as auth_router
app.add_middleware(SessionGateMiddleware)

from server.routes.api import router as api_router
app.include_router(api_router, prefix="/api")

# Runtime brand + copy (GET /api/config). Read per request so a config edit needs no
# rebuild or restart — the seam that lets one build serve several branded instances.
from server.routes.app_config import router as app_config_router
app.include_router(app_config_router, prefix="/api")

from server.routes.genie_mcp import router as genie_mcp_router
app.include_router(genie_mcp_router, prefix="/api")

from server.routes.embed import router as embed_router
app.include_router(embed_router, prefix="/api")

# Live headline KPIs for the landing page (per-tenant, row-scoped; fails soft).
from server.routes.kpis import router as kpis_router
app.include_router(kpis_router, prefix="/api")

# Per-tenant Service Principal isolation: operator API to manage tenant SPs.
from server.routes.tenants import router as tenants_router
app.include_router(tenants_router, prefix="/api")

# White-label login user directory (operator API).
from server.routes.users import router as users_router
app.include_router(users_router, prefix="/api")

# Dashboard asset registry (operator CRUD API).
from server.routes.assets_admin import router as assets_admin_router
app.include_router(assets_admin_router, prefix="/api")

# Conversation history + user filter preferences, persisted in Lakebase.
from server.routes.prism import router as prism_router
app.include_router(prism_router, prefix="/api/prism")


@app.on_event("startup")
def _ensure_lakebase_schema() -> None:
    """Best-effort creation of the persistence tables. Never blocks startup —
    if Lakebase is off or unreachable the app falls back to in-memory behavior."""
    try:
        from server import persistence

        persistence.ensure_schema()
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger("app").warning("Lakebase schema init skipped: %s", exc)

    # Per-tenant SP registry + audit tables (best-effort; no-op without Lakebase).
    try:
        from server.tenants import registry as _tenant_registry
        from server.tenants import audit as _tenant_audit

        _tenant_registry.ensure_schema()
        _tenant_audit.ensure_schema()
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger("app").warning("Tenant schema init skipped: %s", exc)

    # White-label user directory (migrate external_value → tenant_id, etc.).
    try:
        from server.auth import users as _auth_users

        _auth_users.ensure_schema()
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger("app").warning("Auth users schema init skipped: %s", exc)

    # Asset registry (dashboard specs); best-effort, no-op without Lakebase.
    try:
        from server.assets import registry as _asset_registry

        _asset_registry.ensure_schema()
    except Exception as exc:  # noqa: BLE001
        import logging

        logging.getLogger("app").warning("Asset registry schema init skipped: %s", exc)

# Login/logout/identity routes. Mounted WITHOUT an /api prefix (so /login and
# /logout are top-level), and BEFORE the SPA catch-all so they aren't swallowed
# by the index.html fallback. The /api/auth/* routes are declared inside it too.
app.include_router(auth_router)

frontend_dir = os.path.join(os.path.dirname(__file__), "frontend", "dist")

# Per-instance logo assets. BRAND_ASSETS_DIR overrides the built-in /brand/* files so each
# branded instance can serve its own logo.svg / mark.svg / favicon.svg off ONE build.
# Mounted BEFORE the SPA catch-all; missing files fall back to BrandLogo's monogram.
_brand_assets_dir = os.environ.get("BRAND_ASSETS_DIR", "").strip()
if _brand_assets_dir and os.path.isdir(_brand_assets_dir):
    app.mount("/brand", StaticFiles(directory=_brand_assets_dir), name="brand-assets")

if os.path.exists(frontend_dir):
    assets_dir = os.path.join(frontend_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Never swallow API routes — an old or missing handler should 404 as JSON,
        # not return index.html (which breaks admin fetch clients).
        if full_path.startswith("api/"):
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Not Found")
        file_path = os.path.join(frontend_dir, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(frontend_dir, "index.html"))
