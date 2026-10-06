# Prism Multi-Vertical Demo — Design

**Date:** 2026-08-06
**Branch:** `demo/multi-vertical` (off `rename/prism`)
**Status:** Approved (design), implementing.
**Driver:** Internal Databricks demo TODAY. Narrative is Tell → Show → Tell → Show:
Databricks primitives are embeddable → BCD Travel white-label story → "but wait, it's a
platform" → the same platform as two other industries.

## Goal

Run **three branded instances of Prism on three localhost ports**, each pointed at its
own Databricks vertical, from **one build**, so the "config-driven, no redeploy"
platform claim is demonstrated rather than asserted.

```
:8000  Prism · Travel Intelligence      prism_travel              (BCD anchor)
:8001  Meridian Retail · Vendor Portal  retail_merchandising_demo
:8002  Cascade Hotels · Owner Portal    hospitality_demo
```

Retail and Hospitality are framed as **external-partner portals** (a retailer sharing
performance with vendors; a hotel group sharing with property owners) — the same
white-label-external-analytics thesis as BCD, not a recolor.

## Verified starting state (2026-08-06)

Baseline app on `rename/prism` is **healthy**: `/api/kpis` returns real FEVM numbers,
Lakebase is connected, `/api/admin/assets` reports `writable: true` with 3 assets.

Workspace `fevm-serverless-stable-71zsua`, catalog `serverless_stable_71zsua_catalog`:

| Vertical | Metric view | Dashboard | Genie space |
|---|---|---|---|
| Travel | `prism_travel.travel_metrics` | ✅ published | ✅ |
| Retail | `retail_merchandising_demo.retail_metrics` | ✅ published (5pp/38w) | ❌ being built |
| Hospitality | `hospitality_demo.hotel_metrics` | ⚠️ empty shell, unpublished | ❌ being built |
| FBO | `prism_fbo.fbo_metrics` | ✅ published | ✅ (unused here) |

Dashboards/Genie/look-and-feel are owned by **Rohit + parallel agents**, not this work.
This spec covers **app code only** and consumes their output as config values.

## Problem 1 — branding is build-time

`frontend/vite.config.ts:12` aliases `@brand` → `brand.config.json`, and
`frontend/src/theme/brand.ts:1` does `import brandJson from "@brand"`. Brand is frozen
into the bundle at `vite build`, so three ports serving one `dist` would render three
*identically branded* apps. This is also precisely the claim the narrative rests on.

**Fix:** `GET /api/config` serves `{brand, content}` from env-pointed files
(`BRAND_CONFIG_FILE`, `CONTENT_CONFIG_FILE`), read **per request** (not cached at
import) so a file edit shows up on refresh. Frontend gains `ConfigProvider`, a direct
sibling of the existing `frontend/src/registry/RegistryProvider.tsx` — that file already
proves the pattern: boot-time fetch, gate the shell behind a branded spinner, fall back
to a bundled seed on failure. `brand.ts` keeps its static import purely as that
fallback, so nothing regresses when the endpoint is unavailable.

**Payoff:** edit a JSON, refresh, the app is a different company's product — live, no
build, no restart.

## Problem 2 — KPIs are travel-hardcoded

`server/routes/kpis.py:34-39` hardcodes `gross_spend_usd` / `total_emissions_advito` /
`traveler_count` / `component_count`, and `_monthly_trend` hardcodes
`travel_start_date`. Pointed at `retail_metrics` every tile returns null — a broken home
page on two of three tabs.

**Fix:** two env vars, `KPI_MEASURES` (comma-separated `measure:key` pairs) and
`KPI_DATE_COLUMN`, parsed with the current travel values as defaults.

| Vertical | `KPI_MEASURES` | `KPI_DATE_COLUMN` |
|---|---|---|
| Travel | `gross_spend_usd:spend, total_emissions_advito:emissions, traveler_count:travelers, component_count:trips` | `travel_start_date` |
| Retail | `net_sales:spend, gross_margin:margin, units_sold:units, transactions:trips` | `transaction_date` |
| Hospitality | `total_revenue:spend, avg_adr:adr, rooms_sold:rooms, reservation_count:trips` | `checkin_date` |

Server owns measure→key; `content.config.json` owns key→label. Each side owns what it
should.

## Problem 3 — copy is hardcoded

Travel strings live in `frontend/src/pages/HomePage.tsx:52-84,163,220`,
`AskLive.tsx:11-13,313,345`, `GenieMcpExperience.tsx:208`. `content.config.json`
(already anticipated in `docs/customizing.md` as "planned, PR7") covers them:

```json
{
  "hero": { "title": "...", "subtitle": "..." },
  "kpis": [{ "key": "spend", "label": "Net Sales", "format": "currency", "icon": "DollarSign" }],
  "trend": { "title": "Sales Trend", "subtitle": "Monthly net sales" },
  "suggestedQuestions": ["..."],
  "askPlaceholder": "Ask about sales, margin, inventory…"
}
```

`format` is one of `currency | number | percent | decimal`; unknown values fall back to
`number`. Missing keys fall back to today's travel copy.

## Problem 4 — the cookie trap

Browsers scope cookies by **host, ignoring port**, so three instances on `localhost`
would evict each other's sessions mid-demo.

Compounding gotcha (verified today): `server/auth/sessions.py:29` reads `os.environ` at
**import time** and is deliberately stdlib-only — it never imports `server/config.py`,
where `load_dotenv()` runs. So `AUTH_SESSION_COOKIE` set **only in `.env` is ignored**
(observed: `.env` said `apex_session`, app served the `prism_session` code default). A
real exported env var *does* work (verified `AUTH_SESSION_COOKIE=zzz_test` → `zzz_test`).

**Fix:** the launch script **exports** per-instance cookie names
(`prism_travel_session`, `prism_retail_session`, `prism_hotel_session`) rather than
relying on `.env`. No code change.

## Components

| Unit | Responsibility |
|---|---|
| `server/routes/app_config.py` | `GET /api/config` → `{brand, content}`, fail-soft, per-request read |
| `server/content.py` | Load + validate `content.config.json` (mirrors `server/brand.py`) |
| `frontend/src/config/ConfigProvider.tsx` | Boot fetch, spinner gate, fallback to bundled |
| `frontend/src/config/useAppConfig.ts` | Hook exposing `{brand, content}` |
| `server/routes/kpis.py` | Parse `KPI_MEASURES` / `KPI_DATE_COLUMN` |
| `demo/envs/{travel,retail,hotel}.env` | Per-instance config |
| `demo/brands/*.json`, `demo/content/*.json` | Per-instance brand + copy |
| `demo/run-all.sh` | Launch three uvicorns with exported env |

## Data flow

```
demo/envs/retail.env ──exported──> uvicorn :8001
                                     ├─ GET /api/config  → demo/brands/retail.json + demo/content/retail.json
                                     ├─ GET /api/assets   → Lakebase registry (dashboard + Genie ids)
                                     └─ GET /api/kpis     → retail_metrics via KPI_MEASURES
```

## Error handling

Every layer fails soft, preserving the existing invariant:
- `/api/config` unreachable or file malformed → SPA uses bundled `@brand` + default copy.
- Missing `content.config.json` → travel defaults (app never blank).
- Unparseable `KPI_MEASURES` → log a warning, fall back to travel measures.
- Lakebase down → existing in-memory/JSON fallback, unchanged.
- A KPI tile whose measure doesn't exist renders `—`, not a crash.

## Testing

- Unit: `KPI_MEASURES` parser (valid, malformed, empty, whitespace); `server/content.py`
  loader (present, absent, malformed).
- Component: `ConfigProvider` fetch-success, fetch-fail-fallback, malformed-body —
  mirroring the existing `RegistryProvider.test.tsx`.
- Manual per port: login → KPIs non-null → dashboard embeds without a login prompt →
  Ask streams a real answer.
- Cross-port: log into all three in one browser, confirm no session eviction.
- Live re-skin: edit `demo/content/retail.json`, refresh, copy changes without restart.

## Sequencing — demoable at every checkpoint

| # | Work | Est | Demoable after |
|---|---|---|---|
| 1 | Cookies + 3 env files + launch script | 20m | three ports serving |
| 2 | Runtime brand (`/api/config` + ConfigProvider) | 1h | **3 distinct apps + live re-skin** |
| 3 | Config-driven KPIs | 1.25h | real numbers on all three |
| 4 | `content.config.json` wiring | 45m | per-vertical copy |
| 5 | Run-of-show script | 30m | the talk track |

**Hard rule:** if we fall behind, stop after step 3 and write the script. Steps 1–3 give
three credible working apps; step 4 is polish.

## Narrative honesty constraints

- **RLS demo stays on Travel.** `sp_tenant_mapping` + `tenant_row_filter` exist only for
  `prism_travel`. Retail/Hospitality have `client_id` columns but no row filter wired.
  Show isolation on Travel, then say "same mechanism, per vertical."
- **Render stays a slide.** Still 403'd by FEVM's IP ACL (see [[prism-render-deploy]]);
  the shell loads but embeds and Genie fail. Tease it; don't click it.
- **Hospitality is the likeliest casualty.** Its dashboard is being built from scratch in
  parallel. If it slips, demo Travel + Retail live and make Hospitality a slide — two
  polished verticals beat three shaky ones, and the platform point survives with two.

## Scope boundaries

App code only. **Not** in scope: new data, dashboard building or beautification, Genie
space creation, the FBO vertical, fixing Render, custom logo assets (the `BrandLogo`
monogram fallback is sufficient), RLS for the new verticals, and any change to `main` or
`rename/prism`.
