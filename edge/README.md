# Prism Edge Gateway (front door)

A localhost **front-door gateway** that lets the Prism app stay hosted on
Databricks while external users reach it **without ever seeing Databricks
SSO**. This is the "Firefly" / OEM-analytics pattern from
[Building a Customer-Facing OEM Analytics App on Databricks](https://medium.com/@rohitbhagwat/building-a-customer-facing-oem-analytics-app-on-databricks-2233f89efc66).

```
 end user ──http──▶ localhost:9000 (edge)  ──https + edge-SP bearer──▶  prism-analytics (Databricks App)
                       front door                                        behind Apps OAuth proxy
```

The edge is a thin, transparent reverse proxy. For every request it injects an
**edge Service Principal** OAuth token as `Authorization: Bearer …`, which is
what clears the Databricks Apps OAuth proxy — so the browser never gets bounced
to interactive login. The app's own session cookie rides through unchanged.

## Custom authentication (the edge IdP)

The edge hosts its **own branded login** at `/__edge/login` — this is the "your
own IdP" layer of the OEM pattern. End users sign in against the edge (not
Databricks); only then does the edge proxy them into the Databricks App. Until
authenticated, any page navigation is redirected to the login screen.

The page itself is the **app's** login template
(`server.auth.login.render_login_page`), rendered with the edge's user directory
and posting to `/__edge/login`. It is shared rather than copied on purpose: the
edge used to carry its own copy, and it silently kept serving the previous brand
after the app was rebranded. So the login screen picks up `brand.config.json`
automatically, and `tests/test_edge_login_page.py` asserts the two pages' CSS is
identical so they cannot drift again.

Brand assets (`/brand/*`) and the favicon pass the edge gate unauthenticated,
since the login page itself references them.

### Users live in Lakebase

The login directory is stored in **Lakebase** (Databricks managed Postgres) — the
`apex_app_users` table, **shared with the app** so both sides resolve a user to
the same `tenant_id`. That column is the join key into `apex_client_registry`;
it is what selects the per-tenant Service Principal. Passwords are PBKDF2-SHA256
hashes; the edge mints a short-lived Postgres OAuth credential via the Databricks
SDK at connect time (no static DB password). If Lakebase is disabled
(`EDGE_LAKEBASE_ENABLED=0`) or unreachable, the edge falls back to an in-code
list so the demo never hard-breaks.

Demo sample logins (seeded into Lakebase; shown on the login page, click to fill):

| Email | Password | Tenant | `tenant_id` | Role |
|---|---|---|---|---|
| `alice@acmetravel.com` | `apex` | Acme Travel | `acme-travel` | user |
| `ben@globex.com` | `apex` | Globex | `globex` | user |
| `carol@initech.com` | `apex` | Initech | `initech` | user |
| `erin@umbrella.com` | `apex` | Umbrella Corp | `umbrella` | user |
| `dana@prism.example` | `apex` | All Clients | `*` | operator |

**One-time setup:**

```bash
# 1) create the Lakebase Autoscaling project
databricks postgres create-project prism-edge \
  --json '{"spec": {"display_name": "Prism Edge Auth"}}' -p fevm-stable-71zsua

# 2) get the endpoint host -> EDGE_PG_HOST in edge/.env
databricks postgres get-endpoint \
  projects/prism-edge/branches/production/endpoints/primary -p fevm-stable-71zsua

# 3) fill EDGE_PG_* in edge/.env (see edge/.env.example), then seed users
python -m edge.seed_users
```

### Handing the identity to the app

A bearer token clears the OAuth proxy but says nothing about *which user* is
asking — to the app, every request would look like the edge SP. So after
authenticating, the edge **mints the app's own signed session cookie** and
injects it on the upstream request (`edge/appsession.py` → `edge/proxy.py`). The
app verifies it with `server/auth/sessions.verify_session`, and from there
`resolve_tenant_sp()` swaps in that tenant's Service Principal — which is what
makes the Unity Catalog row filter bite.

Two properties make this safe, both pinned by `tests/test_edge_identity.py`:

- **The browser cannot nominate its own identity.** Any client-supplied
  `prism_session` cookie is stripped before the upstream call and replaced with
  the edge-minted one (or dropped entirely when unauthenticated).
- **Both sides share one signing secret** (`AUTH_SESSION_SECRET`) and one cookie
  name (`AUTH_SESSION_COOKIE`). The edge reads them from the repo-root `.env`;
  the app reads them from the `prism` secret scope. A mismatch fails closed —
  the app rejects the session rather than trusting it.

### The edge owns the auth surface

Because the edge holds the session, `/login` and `/logout` are **handled by the
edge, not proxied** (`edge/app.py`, declared before the catch-all):

| Route | Behind the edge |
|---|---|
| `/logout` | Clears `apex_edge_session` **and** `prism_session`, redirects to `/__edge/login` |
| `/login` | Redirects to `/__edge/login` (preserving `?next=`) |

Without this, the app's own `/logout` clears only `prism_session` — which the
proxy re-mints from the edge session on the very next request — so the user
appears to sign out but stays logged in with no way back to the login screen.
Its `/login` would likewise be a second, different sign-in form. Pinned by
`tests/test_edge_logout.py`. The in-app "Sign out" button therefore works
unchanged in both hosting models; `/__edge/logout` also still works directly.

In production, swap `edge/auth.py` for Azure AD B2C / Okta / Entra (keep the
Lakebase table for app-level profile/tenant mapping) — the rest of the edge is
unchanged.

`GET /__edge/health` reports `user_directory` (`lakebase` | `in-code fallback`)
and `lakebase_ok` so you can confirm the directory is live.

## Setup

```bash
cp edge/.env.example edge/.env

# 1) Create the edge SP + secret (writes them into edge/.env)
python edge/create_edge_sp.py --profile fevm-stable-71zsua \
    --display-name prism-edge --app-name prism-analytics

# 2) Grant the edge SP CAN_USE on the app (command printed by step 1)
databricks apps update-permissions prism-analytics -p fevm-stable-71zsua \
    --json '{"access_control_list":[{"service_principal_name":"<edge-sp-id>","permission_level":"CAN_USE"}]}'

# 3) Prove the edge SP token clears the Apps OAuth proxy.
#    Run as a module — as a script the repo root is not on sys.path.
python -m edge.smoke        # expect: "with bearer -> ok (status 200)"

# 4) Run the front door, then open http://localhost:9000
./edge/run.sh
```

Sign in with any of the fallback logins (`alice@cloudventure.com`,
`ben@nike.com`, `dana@advito.com`), password `apex`.

`GET http://localhost:9000/__edge/health` reports config + whether the edge SP
token is mintable, without touching upstream.

## What this proves — and the dashboard boundary

The front door reliably carries the **app shell** (React UI, Genie MCP chat,
APIs) with no SSO. AI/BI dashboards are a separate question:

- **Basic embedding** loads its iframe **directly from the workspace origin**,
  not through the edge, and authenticates with a **Databricks browser
  session**. A no-login external user has no such session, so basic-embed
  dashboards behind the front door render "unavailable" / bounce to login.
  Basic embedding *does* support URL-parameter filters (`f_{page}~{widget}=…`).
- **External embedding** (a per-tenant SP-scoped token in the iframe `#token=`
  hash) renders with **no login**, which is what pairs with this gateway. The
  `@databricks/aibi-client` SDK exposes no filter method, but the embed SPA it
  loads honors the same `f_{page}~{widget}=value` URL params — **validated
  live**: a scoped-token embed with `f_…~tsector=Air` appended rendered with no
  login *and* applied the filter (`travel_sector: Air`). So we get no-login
  white-label **and** app-driven filters by appending `f_` params to the embed
  URL (a ~15-line extension of, or replacement for, the SDK shim). Per-tenant
  data isolation still uses Unity Catalog row filters / `external_value`.

So: **front door (edge SP) + app shell → works today. No-login dashboards →
use SP-scoped token embedding (with `f_` filters appended), not basic
embedding.** See `docs/architecture/poc-status-and-path-forward.md`.
