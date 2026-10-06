# Prism Shared Filter Catalog — Design

**Date:** 2026-08-03
**Status:** Approved (design). PARKED — not yet planned/implemented; branch to be created when work resumes.
**Relates to:** `docs/superpowers/specs/2026-08-02-prism-rename-merge-readme-design.md` (the "filter vocabulary = code-edit seam" this eliminates), `docs/demos/demo-data-and-dashboard-prompts.md`.

## Problem

"My Filters" (`frontend/src/pages/PreferencesPage.tsx`) lets a user set *values* for filters, but the filter **set** is frozen in code: the catalog is a hardcoded TypeScript union `FilterKey = "currentPeriod" | "previousPeriod" | "travelSector" | "destinationRegion"` plus a `FILTERS` record in `frontend/src/config.ts`. So:
- You cannot add a new filter (e.g. Category, Client) without editing code + rebuilding.
- The filters are travel-specific — every new demo vertical (Retail, Hospitality, FBO) needs a code edit. This is the "filter vocabulary" code-edit seam flagged in the README "Spin up a new demo" table.

**Goal:** make the app-level push-filters a **shared, reusable, operator-managed catalog** — defined once, opted into per dashboard, with user defaults keyed by filter so a default set in My Filters applies across every dashboard that uses that filter.

## Decisions (locked during brainstorming)

1. **Who defines filters:** the operator/admin (not end users). End users pick *values*.
2. **Which filters:** the app-level push filters (My Filters + the dashboard FilterBar) that get pushed into Lakeview via `f_` params AND drive Genie/KPI queries — NOT the dashboard's own native widgets.
3. **Options populated by:** auto-discovery from the data (distinct values), not hand-typed.
4. **Catalog is REUSABLE / shared** (the crux — user's original correction): one workspace-level catalog; dashboards opt into a subset; user defaults are keyed by filter and shared across dashboards. NOT per-dashboard filter silos.
5. **Catalog home:** alongside the asset registry (a sibling `filters` object in `server/assets/dashboards.seed.json` + a Lakebase table, reusing the existing registry plumbing) — not a brand-new standalone registry.
6. **Dashboard binding:** operator binds catalog filters → that dashboard's `f_` embed-widget ids explicitly, in the Admin dashboard editor.
7. **Unused defaults:** a user default for a filter a dashboard doesn't bind is silently ignored for that dashboard.

## Model

**One workspace-level filter catalog + per-dashboard opt-in + filter-keyed user defaults.**

- **Catalog** (sibling `filters` object in the asset registry seed + Lakebase table):
  ```
  "filters": {
    "category": { "label": "Category", "column": "category", "allLabel": "All Categories" },
    "region":   { "label": "Region",   "column": "destination_country_region", "allLabel": "All Regions" },
    "sector":   { "label": "Sector",   "column": "travel_sector", "allLabel": "All Sectors" }
  }
  ```
  Options are auto-discovered (not stored by hand).
- **Dashboard opt-in:** each asset keeps its `filters` map, meaning `filterKey → f_ widget id` (this dashboard supports catalog filter X, bound to its widget Y). Operator sets this in the Admin dashboard editor (`AssetEditor.tsx`, which already edits `filters`).
- **User defaults are filter-keyed** (unchanged persistence under the per-user `DEFAULT_PREFS_KEY`): saving `{ region: "Europe", category: "Air", currentPeriod…: … }` means `region=Europe` auto-applies to every dashboard that opts into `region`. Set once, reused. Dashboards not binding `region` skip it.
- **`FilterState` refactor:** date ranges stay STRUCTURAL fixed fields (`currentPeriod*`/`previousPeriod*` — they're KPI-special: drive period-over-period + Genie, not `f_` push). Field-filter values move into a keyed map `fieldValues: Record<string,string>`. `FilterBar` renders the active dashboard's bound catalog filters; `PreferencesPage` renders the WHOLE catalog.

**Load-bearing detail:** a filter carries two mappings that make it work — (a) a dashboard `f_` embed-widget id (to push into the Lakeview iframe) and (b) a `FilterState` field / data column (for Genie + KPI queries). The column lives on the catalog entry (shared); the `f_` widget id lives on the per-dashboard binding (varies per dashboard). This split is why the catalog is shared but binding is per-dashboard.

**Current `FilterState` consumers to refactor** (found in exploration): `FilterBar.tsx` references `draft.travelSector`/`.destinationRegion` by name (L60-70, L109-110); `App.tsx` holds `FilterState` state; `PreferencesPage.tsx` iterates `FILTERS`; `config.ts` `getSupportedFilterKeys`/`buildFilterParams`/`serializeFilter`. KPIs (`server/routes/kpis.py`) consume only the date ranges (`travel_start_date BETWEEN …`), so the date-ranges-stay-structural decision keeps KPIs untouched.

## Auto-discovery

Two new server endpoints, options resolved live from the data:

- **`GET /api/filters/options?filter=<key>`** — resolve the filter's `column` from the catalog; run `SELECT DISTINCT <column> FROM <metric view> WHERE <column> IS NOT NULL ORDER BY 1 LIMIT <cap>` **as the tenant SP** (so row-filter isolation applies — a user only sees option values from their own rows). Cap ~200; brief cache (values change rarely).
- **`GET /api/filters/columns`** — return the metric view's dimension columns (via `information_schema`/`DESCRIBE`) so the operator's "define a filter" flow is *pick a column*, not type a name.

**Source of truth for columns** = the configured metric view (`KPI_METRIC_VIEW` / the dashboard's data) — keeps discovery aligned with what Genie + KPIs query.
**High-cardinality guard** — if a column exceeds the cap (e.g. `employee_id`, `sku`), the endpoint returns a flag so the UI warns "4,000+ values — not ideal as a dropdown" and blocks binding it as a select.

## UX

**Admin — new "Filters" management surface** (operator area, beside asset/tenant tables):
- Manage the catalog: list; "Add filter" → pick a column (from `/api/filters/columns`), give label + all-label; edit/remove.
- Per-dashboard binding: in `AssetEditor.tsx`, operator picks which catalog filters this dashboard supports + maps each to its `f_` widget id (enriches the editor that already edits `filters`).

**My Filters (`PreferencesPage`)** — the fix to the original complaint: renders the WHOLE catalog (date ranges + every field filter), values from auto-discovery; whatever the user sets is their default across every dashboard that uses that filter. Set is catalog-driven, so it grows as the operator adds filters — no code edit.

**FilterBar (per-dashboard)** — renders only that dashboard's bound filters, pre-filled from the user's saved defaults.

## Phasing (each phase independently shippable + testable; own spec→plan→implement cycle)

- **Phase 1 — Dynamic filter model (no new UI).** Refactor `FilterState` field-values into a keyed `fieldValues` map; drive the catalog from the registry `filters` object instead of the hardcoded `FILTERS` const; `FilterBar` + `PreferencesPage` render from the registry catalog. Seed the catalog with today's filters (Sector, Region) so behavior is byte-identical. Pure refactor, existing filter tests pass unchanged. **This alone makes filters config-driven (operator adds one by editing the registry) — delivers the core ask.**
- **Phase 2 — Auto-discovery endpoints.** `/api/filters/options` (distinct values as tenant SP) + `/api/filters/columns` (column picker) + cardinality guard; wire dropdowns to live options.
- **Phase 3 — Admin filter-management UI.** Catalog CRUD surface + per-dashboard binding in `AssetEditor`. The "operator defines filters without touching code" endpoint of the whole thing.

## Scope boundaries (YAGNI)

- Date-range filters stay structural — NOT user-definable (KPI-special).
- No per-USER filter creation — operator-only.
- Auto-discovery caps at dropdown-friendly (low-cardinality) columns.
- Not touching the dashboard's own native Lakeview filter widgets — only the app-level push-filter model.

## Verification (per phase)

`cd frontend && npm test` + `npm run build` green. Phase 1 MUST be behavior-identical (existing filter tests pass unchanged). Live check in the FEVM app: My Filters editable across the catalog, filter bar applies, dashboard reloads with `f_` params. `python3 -m pytest tests/` for any server-side (Phase 2/3).

## Open items for when work resumes

- Create a branch (off `rename/prism` or `main` post-merge — decide then).
- Start with Phase 1 (superpowers:writing-plans) — it delivers the core and later phases build on its model.
- The FEVM demo dashboard currently has NO app-level `f_` push filters bound (its filters are native Lakeview widgets); Phase 1's seed should reflect that (empty binding) — consistent with the null-guard fix already shipped (`getSupportedFilterKeys` tolerates a filter-less spec).
