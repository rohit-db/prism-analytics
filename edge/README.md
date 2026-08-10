# APEX Edge Gateway (front door)

A localhost **front-door gateway** that lets the APEX app stay hosted on
Databricks while external users reach it **without ever seeing Databricks
SSO**. This is the "Firefly" / OEM-analytics pattern from
[Building a Customer-Facing OEM Analytics App on Databricks](https://medium.com/@rohitbhagwat/building-a-customer-facing-oem-analytics-app-on-databricks-2233f89efc66).

```
 end user ──http──▶ localhost:9000 (edge)  ──https + edge-SP bearer──▶  advito-ai-bi (Databricks App)
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

### Users live in Lakebase

The login directory is stored in **Lakebase** (Databricks managed Postgres) —
the edge's own `apex_app_users` table, separate from Databricks workspace
identity. Passwords are PBKDF2-SHA256 hashes; the edge mints a short-lived
Postgres OAuth credential via the Databricks SDK at connect time (no static DB
password). If Lakebase is disabled (`EDGE_LAKEBASE_ENABLED=0`) or unreachable,
the edge falls back to an in-code list so the demo never hard-breaks.

Demo sample logins (seeded into Lakebase; shown on the login page, click to fill):

| Email | Password | Tenant | `external_value` | Role |
|---|---|---|---|---|
| `alice@cloudventure.com` | `apex` | CloudVenture | `cloudventure` | user |
| `ben@nike.com` | `apex` | Nike | `nike` | user |
| `dana@advito.com` | `apex` | Advito (All) | `*` | operator |

**One-time setup:**

```bash
# 1) create the Lakebase Autoscaling project
databricks postgres create-project apex-edge \
  --json '{"spec": {"display_name": "APEX Edge Auth"}}' -p bcd-customer

# 2) get the endpoint host -> EDGE_PG_HOST in edge/.env
databricks postgres get-endpoint \
  projects/apex-edge/branches/production/endpoints/primary -p bcd-customer

# 3) fill EDGE_PG_* in edge/.env (see edge/.env.example), then seed users
python -m edge.seed_users
```

The authenticated identity is forwarded upstream as `X-Apex-Viewer` /
`X-Apex-Tenant` / `X-Apex-External-Value`, so the app can mint per-tenant embed
tokens (`external_value`) and let Unity Catalog row filters scope each
dashboard. In production, swap `edge/auth.py` for Azure AD B2C / Okta / Entra
(keep the Lakebase table for app-level profile/tenant mapping) — the rest of the
edge is unchanged. Sign out at `/__edge/logout`.

`GET /__edge/health` reports `user_directory` (`lakebase` | `in-code fallback`)
and `lakebase_ok` so you can confirm the directory is live.

## Setup

```bash
cp edge/.env.example edge/.env

# 1) Create the edge SP + secret (writes them into edge/.env)
python edge/create_edge_sp.py --profile bcd-customer \
    --display-name apex-edge --app-name advito-ai-bi

# 2) Grant the edge SP CAN_USE on the app (command printed by step 1)
databricks apps update-permissions advito-ai-bi -p bcd-customer \
    --json '{"access_control_list":[{"service_principal_name":"<edge-sp-id>","permission_level":"CAN_USE"}]}'

# 3) Prove the edge SP token clears the Apps OAuth proxy
python edge/smoke.py        # expect: "with bearer -> ok (status 200)"

# 4) Run the front door, then open http://localhost:9000
./edge/run.sh
```

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
