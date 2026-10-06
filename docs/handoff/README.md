# APEX — Engineering Handoff Guide

**Start here.** This folder is a guided walkthrough of *how* the APEX reference
app solves the specific blockers your team asked about, with links straight to
the code that implements each one. It's written to be followed literally — every
deep dive cites exact files and line ranges you can open and copy.

> New to the app itself? Read the [root `README.md`](../../README.md) first for
> what APEX is, the project layout, and how to run it. This guide assumes that
> context and focuses on the *techniques*.

---

## The three headline blockers (and where each is solved)

| Blocker you raised | Short answer | Deep-dive doc |
|---|---|---|
| **1. Passing filters into an embedded AI/BI dashboard via the SDK** | The `@databricks/aibi-client` SDK has no filter API (yet — [DB-I-14988](https://databrickinternal.ideas.aha.io/ideas/DB-I-14988)). We keep the SDK for auth/token-refresh/logo-hiding and apply filters by rebuilding the embed iframe URL ourselves with the documented `f_…` params. | [`../architecture/aibi-embedding-filter-passing-workaround.md`](../architecture/aibi-embedding-filter-passing-workaround.md) |
| **2. White-label embedding using the SDK** (no Databricks login, no "Powered by Databricks" logo) | Token-based external embedding with a **Service-Principal-scoped token** (removes the login screen) + the SDK's `config.hideDatabricksLogo` (removes the logo), re-pushed after every reload. | [`../architecture/aibi-embedding-filter-passing-workaround.md`](../architecture/aibi-embedding-filter-passing-workaround.md) |
| **3. "Ask APEX" using Genie MCP** | An agentic chat over the **managed Genie MCP server (Genie One MCP)** — streamed reasoning, SQL, result tables, tool calls, and deep links over SSE. Agent mode **out of the box today**. | [`ask-apex-genie-mcp.md`](./ask-apex-genie-mcp.md) |

Two supporting capabilities the team will also want to reuse:

| Capability | Deep-dive doc |
|---|---|
| **Multi-tenant isolation** — each tenant gets its own Service Principal; Genie **and** dashboards run as that SP, with a Unity Catalog row filter enforcing isolation in the data plane; plus an operator **Admin** page to manage SPs and a **"Manage access"** dialog to grant/revoke per-resource `CAN_RUN` | [`multi-tenant-isolation.md`](./multi-tenant-isolation.md) · [`tenant-isolation-runbook.md`](./tenant-isolation-runbook.md) |
| **Own your front door** — white-label custom login (PBKDF2 + HMAC-signed session cookie), the edge-gateway vs external-host hosting models, and Docker packaging | [`whitelabel-auth-and-hosting.md`](./whitelabel-auth-and-hosting.md) |
| **Persistence + reuse** — Lakebase (managed Postgres) for conversation history, per-user filter prefs, and the user-facing **"My Filters"** default-filter page; plus the config-driven dashboard/filter registry that makes adding a dashboard declarative | [`lakebase-persistence-and-config.md`](./lakebase-persistence-and-config.md) |

Also referenced (kept current): [`../architecture/external-hosting.md`](../architecture/external-hosting.md)
— running the app fully outside Databricks via a Service Principal.

---

## Suggested reading order

1. [Root `README.md`](../../README.md) — what the app is, structure, how to run.
2. [**AI/BI embedding + filter passing**](../architecture/aibi-embedding-filter-passing-workaround.md) — the core technique (blockers #1 and #2). Everything else builds on this.
3. [**Ask APEX / Genie One MCP**](./ask-apex-genie-mcp.md) — the agentic chat (blocker #3).
4. [**White-label auth + hosting**](./whitelabel-auth-and-hosting.md) — how end users sign in and where the app runs.
5. [**Lakebase persistence + config**](./lakebase-persistence-and-config.md) — persistence and how to re-point the app at new dashboards.

---

## Mental model (one screen)

```
Browser
  │  (optional) white-label login  →  HMAC-signed session cookie  (server/auth/*)
  ▼
React UI (Vite + Tailwind)
  │   /api/*   (SSE for chat)
  ▼
FastAPI backend  ─────────────────►  Databricks   (auth = app SP / M2M)
  ├── /api/embed/token       3-step OAuth → scoped AI/BI embed token   (server/routes/embed.py)
  ├── /api/genie-mcp/ask     SSE stream from managed Genie MCP server  (server/routes/genie_mcp/*)
  ├── /api/apex/*            conversation history + filter prefs ── Lakebase (server/persistence.py)
  └── /login /logout         white-label IdP + session gate            (server/auth/*)
                                   │
                                   ▼
                AI/BI Dashboard  ·  Genie Space  ·  Unity Catalog data
```

The one non-obvious idea to internalize: **the browser never touches Databricks
credentials.** The server mints a short-lived, dashboard-scoped token with the
Service Principal and hands only that to the iframe. The SP secret stays
server-side.

---

## What you need on the Databricks side (prerequisites)

To stand this up against *your* workspace:

- **A Service Principal with an OAuth client id + secret.** This is the identity
  that mints embed tokens and (when hosted externally) makes *all* API calls.
  *Generating an SP secret requires workspace-admin* — plan for this; it was the
  gating item in our own testing.
- **Each dashboard published for external embedding** (`embed_credentials = false`,
  so queries run *as the SP*), with the SP granted **CAN RUN** on the published
  dashboard, **CAN USE** on the SQL **warehouse**, and **SELECT** on the underlying
  Unity Catalog tables/views. Add your app's origin to the dashboard's embedding
  **approved-domains** allow-list.
- **A Genie space** for Ask APEX, with the identity granted **CAN RUN** on it.
- **(Optional) A Lakebase instance** for persistence — the app runs fully without
  it (see graceful degradation below).

Full permission details live in the embedding and Genie deep-dive docs.

---

## Fastest path to run it locally

Full instructions are in the [root README](../../README.md#local-development).
The minimum to see dashboards + Ask APEX (persistence and login off):

```bash
cp .env.example .env      # set DATABRICKS_HOST, DATABRICKS_CLIENT_ID/SECRET,
                          # GENIE_SPACE_ID, DASHBOARD_URL; leave LAKEBASE_ENABLED
                          # and AUTH_ENABLED = false
python -m uvicorn app:app --host 0.0.0.0 --port 8000
cd frontend && npm install && npm run dev
```

**Demo logins** (only when `AUTH_ENABLED=true`; the shipped JSON directory
`server/auth/users.seed.json`, password `apex` for all). When
`LAKEBASE_ENABLED=true`, a Lakebase-backed directory (`AUTH_USERS_TABLE`)
overrides this file — that's where you'd seed real tenant/operator accounts.

| Email | Tenant | Role | Row scope (`tenant_id`) |
|---|---|---|---|
| `alice@acmetravel.com` | Acme Travel | user | `acme-travel` |
| `ben@globex.com` | Globex | user | `globex` |
| `dana@advito.com` | Advito | **operator** (sees Admin) | `*` (sees all rows) |

The **operator** role is what unlocks the Admin (Service Principal management)
page and the "Manage access" dialog.

---

## Gotchas & known discrepancies (read before you debug)

These are real quirks in the current code that will otherwise cost you an hour:

- **Ask APEX runs in `multi` mode regardless of the API default.** The server's
  `AskRequest.mode` defaults to `"space"` (per-space Genie MCP), but the Ask APEX
  page and the Executive Summary modal both hardcode `"multi"` (workspace-wide
  Genie One MCP). If you point at a single space and see workspace-wide behavior,
  that's why. (See the Genie doc.)
- **`AUTH_ENABLED` code-default is `false`.** The session gate is a no-op unless
  you set it, even though `.env.example` ships `true`. Set it explicitly.
- **`GENIE_SPACE_ID` that matters is the *server* env var.** There's also a
  `GENIE_SPACE_ID` constant in `frontend/src/config.ts`, but it is **not** wired
  into the MCP call — the backend env var drives Genie.
- **The default dashboard id lives in two places** that must stay in sync:
  `DASHBOARDS.apex.id` in `frontend/src/config.ts` and the `DASHBOARD_URL` default
  in `server/config.py`. They currently match; keep them matched when you
  re-point.
- **Changing a host-app filter reloads the embed iframe.** That's expected — it's
  how filters re-apply. The dashboard's own in-frame filter widgets stay
  interactive without a reload.
- **Removing the login screen does not remove authorization.** The SP still needs
  warehouse + UC `SELECT`; Unity Catalog RLS (keyed on the SQL caller identity)
  governs what each viewer can see.
- **A tenant SP without `CAN_RUN` on the dashboard fails the embed-token mint**
  with `invalid_authorization_details`. Onboarding auto-grants the dashboards in
  `DASHBOARD_IDS`; operators can adjust later via the Admin **"Manage access"**
  dialog. Same applies to Genie spaces the tenant should reach.
- **Under workspace IP access lists, minting an SP token still succeeds from a
  blocked IP.** The OIDC endpoint is not IP-governed, so hosting the edge off an
  allowlisted network looks like a credential problem when the token works and
  the *next* call 403s. The Apps front door enforces the ACL too, despite being a
  different hostname. See the IP-ACL section of the white-label hosting doc.

---

## Graceful degradation (why the demo never hard-fails)

Persistence and login are both optional and fail *soft*:

- `LAKEBASE_ENABLED=false` → conversations aren't saved and filter prefs aren't
  remembered, but every screen still works (in-memory + JSON user file). The
  server returns `persisted: false`; the frontend helpers swallow errors and
  return empty/null.
- `AUTH_ENABLED=false` → no login screen; requests run with a default identity.

This is deliberate so you can demo the hard parts (embedding + Genie) with zero
infra beyond a Service Principal and a Genie space.

---

## Doc index (everything in one place)

| Doc | Topic |
|---|---|
| [root `README.md`](../../README.md) | App overview, structure, run/deploy |
| [`../architecture/aibi-embedding-filter-passing-workaround.md`](../architecture/aibi-embedding-filter-passing-workaround.md) | White-label SDK embedding + `f_` filter passing + 3-step token minting |
| [`ask-apex-genie-mcp.md`](./ask-apex-genie-mcp.md) | Ask APEX over the managed Genie MCP server (SSE, auth, tool discovery, parsing, Executive Summary) |
| [`multi-tenant-isolation.md`](./multi-tenant-isolation.md) | Per-tenant Service Principals for Genie + dashboards; UC row-filter isolation; the `server/tenants/` package + admin UI |
| [`tenant-isolation-runbook.md`](./tenant-isolation-runbook.md) | Operator runbook: apply the row filter, onboard tenants, verify isolation |
| [`whitelabel-auth-and-hosting.md`](./whitelabel-auth-and-hosting.md) | Custom login (PBKDF2 + signed cookie), edge-gateway vs external-host, Docker |
| [`lakebase-persistence-and-config.md`](./lakebase-persistence-and-config.md) | Lakebase history + filter prefs, and the config-driven dashboard/filter registry |
| [`../architecture/external-hosting.md`](../architecture/external-hosting.md) | Running fully outside Databricks via a Service Principal |

---

## Glossary

- **Basic embedding** — iframe authenticated by the viewer's **Databricks session
  cookie**. Supports `f_…` URL filters, but shows a login screen to anyone without
  a Databricks session.
- **Token-based external embedding** — iframe authenticated by a short-lived,
  **SP-scoped token** in the URL `#token=` hash. No login screen. What we use.
- **`f_…` filter grammar** — `f_{pageId}~{widgetId}={value}` URL params that drive
  a dashboard's filter widgets. Documented for basic embedding; we confirmed
  empirically they also survive token embedding.
- **Edge gateway** — deployment model where the analytics app stays on **Databricks
  Apps** and a small external "front door" authenticates users and reverse-proxies
  to it (no Databricks SSO shown).
- **External host** — deployment model where the **whole app runs off Databricks**
  (EC2/ECS/Docker) and reaches Databricks purely via the SP. This branch is set up
  for this model.
- **OBO (On-Behalf-Of)** — calling Databricks as the *end user* by forwarding their
  access token; contrast with **M2M / SP** (calling as the app's service principal).
- **Genie One MCP** — the managed, **workspace-wide** Genie MCP server (`/api/2.0/mcp/genie`),
  vs the **per-space** server (`/api/2.0/mcp/genie/{spaceId}`). Genie One MCP gives
  an agent experience across spaces today.
