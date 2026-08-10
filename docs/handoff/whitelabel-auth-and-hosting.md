# White-Label Auth Flow, Hosting Models & Docker

**What & why.** APEX is its own OEM Identity Provider: users sign in against
**APEX's own directory** (Lakebase Postgres, or a JSON file for demos), get an
**HMAC-signed session cookie**, and **never see a Databricks login screen**. This
doc owns the **authentication flow** — login → signed cookie → identity →
tenant resolution — plus the two hosting models and Docker packaging.

> **Companion docs (don't duplicate — read them for their topics):**
> - [`multi-tenant-isolation.md`](./multi-tenant-isolation.md) — what happens
>   *after* identity: `tenant_id` → tenant Service Principal → UC row filter.
>   This doc hands off there.
> - [`../architecture/aibi-embedding-filter-passing-workaround.md`](../architecture/aibi-embedding-filter-passing-workaround.md)
>   — owns the embed-token exchange + `f_` filter-passing details.
> - [`../architecture/external-hosting.md`](../architecture/external-hosting.md)
>   — the authoritative self-hosting deep-dive (SP setup, full env contract).

---

## The auth flow (one screen)

```
Browser  ──POST /login (email + password)──►  server/auth/login.py
   │                                              │ users_repo.verify_login()
   │                                              │   PBKDF2-HMAC-SHA256 verify
   │                                              ▼
   │                                    server/auth/users.py  (Lakebase | JSON)
   │  ◄──Set-Cookie: apex_session=<payload>.<hmac>── create_session()
   ▼                                                  server/auth/sessions.py
Browser sends cookie on every request
   │
   ▼
SessionGateMiddleware  (server/auth/middleware.py)   [no-op if AUTH_ENABLED off]
   │  verify_session() → request.state.identity = {email, tenant, tenant_id, role}
   ▼
Route handlers read the identity:
   ├── embed.py            tenant_id → tenant SP credentials (+ maps to Databricks external_value at token mint)
   └── tenants/resolver.py tenant_id → tenant SP            (see isolation doc)
```

Everything downstream keys on **`tenant_id`** — the join key carried in the signed
cookie. It selects the per-tenant Service Principal for Genie and dashboard embeds.

---

## Password hashing — PBKDF2-HMAC-SHA256

Stdlib-only (`hashlib.pbkdf2_hmac`), SHA-256, **200,000 iterations**, random
16-byte salt, self-describing encoding, constant-time verify:

```45:64:server/auth/sessions.py
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return (
        f"pbkdf2_sha256${_PBKDF2_ITERATIONS}$"
        f"{base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, iters, salt_b64, hash_b64 = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(hash_b64)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iters))
        return hmac.compare_digest(dk, expected)
    except Exception:  # noqa: BLE001
        return False
```

---

## The signed session cookie

The cookie value is `"<payload_b64>.<hmac_sig>"`: a compact JSON identity dict,
base64url-encoded, plus **HMAC-SHA256 over that payload** keyed by
`AUTH_SESSION_SECRET`. On read, the signature is re-computed and compared
constant-time, then `exp` is checked.

```81:97:server/auth/sessions.py
def create_session(identity: dict, ttl_seconds: int | None = None) -> str:
    """Build a signed cookie value from an identity dict.

    ``identity`` should contain at least ``email``; ``tenant``, ``tenant_id``,
    ``display_name`` and ``role`` are carried through when present.
    """
    ttl = SESSION_TTL_SECONDS if ttl_seconds is None else ttl_seconds
    payload = {
        "email": identity.get("email"),
        "name": identity.get("display_name") or identity.get("name"),
        "tenant": identity.get("tenant"),
        "tenant_id": identity.get("tenant_id"),
        "role": identity.get("role", "user"),
        "exp": int(time.time()) + int(ttl),
    }
    payload_b64 = _b64e(json.dumps(payload, separators=(",", ":")).encode())
    return f"{payload_b64}.{_sign(payload_b64)}"
```

- **Signing key:** `AUTH_SESSION_SECRET` (falls back to a clearly-marked dev
  default — set a real one in production).
- **Payload fields:** `email`, `name`, `tenant`, `tenant_id`, `role`, `exp`.
  Legacy cookies used `ext` (normalized to `tenant_id` on read).
- **TTL:** `AUTH_SESSION_TTL_SECONDS` (default **28800s = 8h**).
- **Cookie name:** `AUTH_SESSION_COOKIE` (default `apex_session`).

> The cookie is **signed, not encrypted** — the payload is readable (base64) but
> cannot be tampered with without the secret. It carries only non-sensitive
> routing/scoping fields; never put a secret in it.

On login the cookie is set `HttpOnly`, `SameSite=Lax`, and `Secure` when the
request arrived over TLS (or when `AUTH_COOKIE_SECURE` forces it) — see
`login.py::login_post` (lines 133–163).

---

## Roles — user vs operator

`role` rides in the session. Two values matter:

- **`user`** — a normal tenant viewer. Their `tenant_id` selects their SP.
- **`operator`** — back-office / admin. Gates the Service Principal admin API
  (`role == "operator"` in `server/routes/tenants.py`) and the **Administration →
  Service Principals** nav entry. Operators typically have `tenant_id = "*"`
  (all rows) and are members of `TENANT_ADMIN_GROUP` so the UC row filter lets them
  see every tenant.

---

## The session gate — `AUTH_ENABLED` and `request.state.identity`

`SessionGateMiddleware` enforces the cookie on every non-public request:

```71:94:server/auth/middleware.py
class SessionGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # No-op when disabled — identical behavior to today's Databricks-Apps app.
        if not _auth_enabled():
            return await call_next(request)

        path = request.url.path
        identity = verify_session(request.cookies.get(SESSION_COOKIE))
        if identity:
            request.state.identity = identity
            return await call_next(request)

        # No valid session.
        if _is_public(path):
            return await call_next(request)

        if request.url.path.startswith("/api/"):
            return JSONResponse({"error": "not authenticated"}, status_code=401)

        if _wants_html(request):
            nxt = path + (f"?{request.url.query}" if request.url.query else "")
            return RedirectResponse(f"/login?next={nxt}", status_code=302)

        return JSONResponse({"error": "not authenticated"}, status_code=401)
```

- **`AUTH_ENABLED` code-default is OFF** (`_auth_enabled()` returns `False` when the
  var is unset), so the gate is a no-op unless you opt in. `.env.example` ships
  `AUTH_ENABLED=true`.
- **Public allowlist:** `/login`, `/logout`, `/favicon.ico`, `/api/health`,
  `/api/auth/*`, `/assets/*`, `/static/*`, and static file extensions.
- Valid session → `request.state.identity` set, passes through. No session →
  `401` JSON for `/api/*`, `302` to `/login?next=…` for HTML nav.

`app.py` adds the middleware and mounts the auth router **without** an `/api`
prefix (so `/login`, `/logout` are top-level, before the SPA catch-all).
`current_identity(request)` (in `server/auth/__init__.py`) reads the decoded
identity, falling back to decoding the cookie directly.

---

## From identity → tenant resolution (the hand-off)

Two routes consume `tenant_id` from the session; this is where this doc ends
and [`multi-tenant-isolation.md`](./multi-tenant-isolation.md) begins:

- **Embed token** — `embed.py` derives `tenant_id` and `viewer_id` from
  `request.state.identity`, never from the browser. At the Databricks API boundary
  the value is sent as the embed `external_value` param (defense-in-depth):

```147:159:server/routes/embed.py
    identity = getattr(request.state, "identity", None)
    if identity:
        # Session identity wins over the default viewer; a query-param override
        # (anything other than the default) is still honored.
        if viewer_id == "apex-viewer":
            viewer_id = identity.get("email") or identity.get("tenant") or viewer_id
        if tenant_id is None:
            tenant_id = identity.get("tenant_id")

    try:
        credentials = _resolve_embed_credentials(request)
        result = _mint_embed_token(did, viewer_id, tenant_id, credentials)
```

- **Tenant SP** — `tenants/resolver.resolve_tenant_sp(request)` maps that same
  `tenant_id` to a per-tenant Service Principal so Genie **and** the embed run
  *as* the tenant SP (with the app SP as the safe fallback). See the isolation doc.

---

## The user directory — Lakebase, with JSON fallback

The directory is the app's **own** login store, separate from Databricks identity.
Each user maps to a display `tenant` name and a `tenant_id` join key.

- **Lakebase backend** (managed Postgres) when `LAKEBASE_ENABLED` is true. The
  Postgres credential is a **short-lived OAuth credential minted via the app's
  SP-first workspace client** — no static DB password (see `server/lakebase.py`).
- **JSON fallback** when Lakebase is off — users load from `AUTH_USERS_FILE`
  (default `server/auth/users.seed.json`). Zero setup for demos.

```167:180:server/auth/users.py
def get_user(email: str) -> Optional[UserRow]:
    """Look up a user by email from Lakebase (if enabled) or the JSON fallback."""
    em = (email or "").strip().lower()
    if not em:
        return None
    if LAKEBASE_ENABLED:
        try:
            return _lakebase_get(em)
        except Exception as e:  # noqa: BLE001
            logger.warning("Lakebase lookup failed, using JSON fallback: %s", e)
    for u in _load_json_users():
        if u.email == em:
            return u
    return None
```

Seed the Lakebase users table once from the JSON seed with
`python -m server.auth.seed_users` (a no-op when `LAKEBASE_ENABLED` is false).

### Demo logins

When `LAKEBASE_ENABLED=false` (the default), the store is `users.seed.json` and
**all three sample users share the password `apex`**. The login page renders
clickable chips pre-filled from `demo_password_hint()` (JSON mode only).

| Display name | Email | Password | Tenant | `tenant_id` | Role |
|---|---|---|---|---|---|
| Alice Chen | `alice@acmetravel.com` | `apex` | Acme Travel | `acme-travel` | user |
| Ben Ortiz | `ben@globex.com` | `apex` | Globex | `globex` | user |
| Dana Lee | `dana@advito.com` | `apex` | Advito (All) | `*` (all rows) | operator |

---

## The two hosting models

Both put a branded, no-SSO login in front of Databricks-hosted analytics; they
differ in *where the app runs* and *where the login lives*. **The auth code
(`server/auth/`) is identical either way.**

| | **Edge-gateway (Model A)** | **External-host (Model B)** |
|---|---|---|
| App runtime | Databricks Apps platform | Your container (EC2 / ECS / any Docker) |
| Custom login lives in | Separate `edge/` reverse-proxy service | In-process `server/auth/` |
| Embedding | Basic embedding behind the proxy | SP-minted scoped embed tokens |
| Front door | The edge proxy (injects an SP bearer to clear the Apps OAuth proxy) | The app itself |
| Shipped here? | **Yes** — `edge/`, see [the edge README](../../edge/README.md) | **Yes** |

Both are present. `server/auth/` was originally **ported from the edge gateway**
(its docstrings still reference `edge/auth.py`, `edge/db.py`), and the gateway
itself now lives alongside it again.

> **Which one is running?** They are mutually exclusive in practice, and the
> switch is `AUTH_ENABLED`. Behind the edge, leave it unset so the app has no
> login of its own and the edge is the only place a user signs in; the deployed
> `app.yaml` does exactly that. Self-hosting the whole app instead, set it true
> and skip the edge.
>
> **Known gap in Model A.** The edge forwards its authenticated identity as
> `X-Apex-Viewer` / `X-Apex-Tenant` / `X-Apex-External-Value`, but nothing in
> `server/` reads those headers yet. With the session gate off, every user
> behind the edge is served as the app Service Principal, so per-tenant row
> filtering does not apply. Closing this means teaching
> `SessionGateMiddleware` to trust a signed identity header from the edge.

### How the SP identity powers all Databricks calls off-platform

Running externally, **every** Databricks call is made **as the Service Principal**.
`get_workspace_client()` resolves SP creds first, so one code path works on
Databricks Apps *and* any container:

```102:113:server/config.py
    if HAS_SP_CREDENTIALS:
        return WorkspaceClient(
            host=WORKSPACE_URL,
            client_id=DATABRICKS_CLIENT_ID,
            client_secret=DATABRICKS_CLIENT_SECRET,
        )
    if IS_DATABRICKS_APP:
        return WorkspaceClient()
    return WorkspaceClient(
        host=WORKSPACE_URL,
        token=os.environ.get("token"),
    )
```

This SP client mints embed tokens, opens Genie MCP sessions, and mints the
short-lived Lakebase credential — all without any Databricks login.

---

## Running it with Docker

Packaging lives at the repo root: `Dockerfile`, `docker-compose.yml`,
`.dockerignore`, `.env.example`. The image is a **two-stage build**: stage 1 builds
the Vite/React SPA to `frontend/dist`; stage 2 runs FastAPI via uvicorn and serves
the SPA **and** API from one process. `app.py` mounts `/assets` and adds an
SPA catch-all that returns the requested file if it exists, else `index.html`.

```bash
# 1) Create your env file and fill it in.
cp .env.example .env
#    Set at minimum:
#      DATABRICKS_HOST, DATABRICKS_CLIENT_ID, DATABRICKS_CLIENT_SECRET  (your SP)
#      GENIE_SPACE_ID, DASHBOARD_URL                                    (data assets)
#      AUTH_SESSION_SECRET (long random)   AUTH_ENABLED=true            (branded login)

# 2) Choose a login backend:
#      LAKEBASE_ENABLED=false  -> instant demo (server/auth/users.seed.json)
#      LAKEBASE_ENABLED=true   -> fill PG* + LAKEBASE_*, then: python -m server.auth.seed_users

# 3) Build and run, then sign in with a sample user.
docker compose up --build
open http://localhost:8000        # or your APP_PORT
```

### Environment variables (auth + run)

Authoritative against `.env.example`, `server/config.py`, `server/lakebase.py`,
`server/auth/`. (Full SP-setup + isolation env: see
[`../architecture/external-hosting.md`](../architecture/external-hosting.md) and
[`multi-tenant-isolation.md`](./multi-tenant-isolation.md).)

| Variable | Required | Purpose |
|---|---|---|
| `DATABRICKS_HOST` | **Yes** | Workspace URL for all Databricks API calls. |
| `DATABRICKS_CLIENT_ID` / `DATABRICKS_CLIENT_SECRET` | **Yes** | App Service Principal (M2M). Server-side only; toggles `HAS_SP_CREDENTIALS`. |
| `GENIE_SPACE_ID` | **Yes** | Genie space backing Ask APEX. |
| `DASHBOARD_URL` | **Yes** | Embedded dashboard; the dashboard id + `o=` org are parsed from it. |
| `APP_PORT` | No (default `8000`) | Host + container port. |
| `AUTH_ENABLED` | No (code default `false`; `.env.example` `true`) | Turns on the white-label session gate. |
| `AUTH_SESSION_SECRET` | **Yes** if auth on | HMAC key that signs session cookies. |
| `AUTH_SESSION_COOKIE` / `AUTH_SESSION_TTL_SECONDS` | No | Cookie name (`apex_session`) / lifetime (`28800` = 8h). |
| `AUTH_COOKIE_SECURE` | No | Force the `Secure` flag (else inferred from TLS / `x-forwarded-proto`). |
| `AUTH_USERS_FILE` / `AUTH_USERS_TABLE` | Conditional | JSON directory (Lakebase off) / Lakebase users table. |
| `LAKEBASE_ENABLED` | No (default `false`) | `true` → persist users/history/prefs in Lakebase; `false` → JSON + in-memory. |
| `LAKEBASE_INSTANCE_NAME` / `LAKEBASE_ENDPOINT_PATH` / `LAKEBASE_PROFILE` | If Lakebase on | Instance name / endpoint path used to mint the Postgres credential / local-dev CLI profile (blank → SP mints). |
| `PGHOST` / `PGPORT` / `PGDATABASE` / `PGUSER` / `PGSSLMODE` | If Lakebase on | Postgres endpoint host, port (`5432`), db (`databricks_postgres`), login identity, SSL mode (`require`). |

---

## Security notes

- **SP secret stays server-side.** The browser only ever receives the final
  short-lived, scoped embed token — never SP creds.
- **Session cookie is signed, `HttpOnly`, `SameSite=Lax`, `Secure` on TLS.**
  HMAC-SHA256-signed (tamper-proof) but not encrypted; carries only non-sensitive
  scoping fields. Use a long random secret and rotate it.
- **Passwords are never stored in plaintext** — PBKDF2-HMAC-SHA256, 200k
  iterations, per-user salt, constant-time verify.
- **Terminate TLS in front of the container** (ALB / nginx / API gateway) so
  `Secure` cookies and the embed-token-in-URL are safe.
- **Removing the login does not remove authorization.** Queries run as the SP, so
  the SP still needs warehouse `CAN_USE` + UC `SELECT`, and UC row filters govern
  what each identity can read (see [`multi-tenant-isolation.md`](./multi-tenant-isolation.md)).

---

## File map (real paths only)

| Path | Role |
|---|---|
| `server/auth/__init__.py` | Package exports: `router`, `SessionGateMiddleware`, `current_identity()`. |
| `server/auth/middleware.py` | Session-gate middleware; sets `request.state.identity`; no-op when `AUTH_ENABLED` off. |
| `server/auth/login.py` | `/login`, `/logout`, `/api/auth/me` routes + branded login HTML. |
| `server/auth/sessions.py` | PBKDF2 password hashing + HMAC-signed session cookie crypto. |
| `server/auth/users.py` | User directory: Lakebase backend + JSON fallback + `verify_login()`. |
| `server/auth/seed_users.py` | `python -m server.auth.seed_users` — seed the Lakebase users table. |
| `server/auth/users.seed.json` | Demo user directory (JSON fallback); shared demo password `apex`. |
| `server/config.py` | `get_workspace_client()` / `get_sp_bearer()` — SP-first Databricks auth. |
| `server/lakebase.py` | Shared Lakebase connection + short-lived Postgres credential minting. |
| `server/routes/embed.py` | `/api/embed/token` — SP-minted scoped embed token; consumes session identity. |
| `server/tenants/resolver.py` | `tenant_id` → tenant SP (the isolation hand-off). |
| `app.py` | FastAPI entry: adds middleware, wires routers, serves `frontend/dist`. |
| `Dockerfile` / `docker-compose.yml` / `.dockerignore` / `.env.example` | Container packaging + env contract. |
| `edge/` | The Model A front door: its own login, session and reverse proxy. Runs as a separate process, imports nothing from `server/`. |
