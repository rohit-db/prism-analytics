# Customizing / rebranding Prism

This app is a white-label reference. Rebrand it in **3 steps**:

1. **Edit `brand.config.json`** (repo root) — app name, tagline, colors, font.
   Colors are semantic (`primary`, `accent`, `sidebarFrom`…), applied at runtime
   as CSS variables and mapped to Tailwind `brand-*` utilities.
2. **Swap logo assets** in `frontend/public/brand/` (`logo.svg`, `mark.svg`,
   `favicon.svg`). Absent files fall back to a monogram derived from `shortName`.
3. **Rebuild** — `cd frontend && npm run build`. Both login screens
   (server-rendered) read the same `brand.config.json`, so they rebrand too — the
   app's `/login` and the edge gateway's `/__edge/login` share one template.

## `brand.config.json` schema

```json
{
  "identity": {
    "appName": "Prism",       // full display name, sets document.title
    "shortName": "Prism",     // used for the monogram fallback in BrandLogo
    "tagline": "Travel Intelligence",
    "logo": "/brand/logo.svg",
    "logoMark": "/brand/mark.svg",
    "favicon": "/brand/favicon.svg"
  },
  "colors": {
    "primary":      "#4f46e5",   // buttons, active nav, key accents
    "primaryDark":  "#3730a3",   // hover-darken on primary surfaces
    "primaryLight": "#e0e7ff",   // tinted backgrounds (e.g. badge fill)
    "accent":       "#6366f1",   // gradient endpoint, secondary accents
    "accentDark":   "#4f46e5",   // hover-darken on accent surfaces
    "sidebarFrom":  "#211d52",   // sidebar gradient start
    "sidebarVia":   "#2d2a6e",   // sidebar gradient mid
    "sidebarTo":    "#16142e",   // sidebar gradient end
    "bg":           "#f8fafc",   // page canvas background
    "border":       "#e2e8f0"    // dividers, card outlines
  },
  "typography": {
    "fontSans": "Inter, system-ui, -apple-system, sans-serif"
  }
}
```

## Change X → edit Y

| To change… | Edit… |
|------------|-------|
| Colors, app name, tagline, font | `brand.config.json` |
| Logo / favicon | files in `frontend/public/brand/` |
| Login demo chips on/off | `AUTH_SHOW_DEMO_LOGINS` env |
| User-facing copy (hero, cards) | *(planned: `content.config.json`, PR7)* |
| Dashboards & Genie spaces (specs, filter wiring, per-page prompts) | `server/assets/dashboards.seed.json` |
| Which filters exist / how they render | `frontend/src/config.ts` (`FILTERS`) |
| Nav order, labels, icons, pages | `frontend/src/config.ts` (`ROUTES`) |
| Server data assets / SP / Lakebase / RLS | `.env` |

**Dashboard registry vs. filters vs. nav.** `server/assets/dashboards.seed.json`
owns dashboard **assets** (physical dashboard id, filter→widget wiring, pages,
per-page Genie prompts), resolved by `server/assets/registry.py` and served at
`GET /api/assets` (the frontend fetches it at boot and bundles a fallback copy).
**Filter render vocabulary** (which filters exist, how they render) stays in
`frontend/src/config.ts` `FILTERS`; the seed's `filters` map only *references*
those keys. **Nav** (order, icons, sections, non-dashboard pages) stays in
`config.ts` `ROUTES`; a dashboard route points at an asset via its `dashboard`
key. `DASHBOARD_IDS` / `RESOURCE_DASHBOARDS` / `DASHBOARD_URL` remain env
fallbacks used only when the registry is empty.

## How theming works (for agents)

- **Single source:** `brand.config.json`. Never hardcode a hex or brand string
  in a component — add/emit a semantic token instead.
- **Frontend pipeline:**
  1. `frontend/src/theme/brand.ts` — types the config as `Brand` and exports
     `brandToCssVars(b)` which flattens `colors.*` + `typography.fontSans` into
     `--brand-*` CSS custom properties.
  2. `frontend/src/theme/ThemeProvider.tsx` — calls `brandToCssVars` in a
     `useLayoutEffect` and sets each property on `:root`. Also sets
     `document.title = brand.identity.appName`. This is the seam a future
     per-tenant payload will overwrite.
  3. `frontend/src/index.css` — seeds the same `--brand-*` vars with default
     values on `:root` (branded first paint, no FOUC), then maps them into
     Tailwind's color namespace via `@theme inline`:
     `--color-brand-primary: var(--brand-primary, …)` etc.
- **Server:** `server/brand.py` exports `load_brand()` — fail-soft JSON read
  of the same `brand.config.json` (falls back to `DEFAULT_BRAND`, never raises).
  Used by the login page template and to set the FastAPI `app.title`.
  `brand_asset_exists()` decides logo-vs-monogram: `identity.logoMark` is always
  *named*, so only the file's presence can tell the template whether to emit an
  `<img>` or fall back to the monogram.
- **Tailwind utilities in use:** `brand-primary`, `brand-primary-dark`,
  `brand-primary-light`, `brand-accent`, `brand-accent-dark`,
  `brand-sidebar-from`, `brand-sidebar-via`, `brand-sidebar-to`,
  `brand-bg`, `brand-border`.

## Design conventions

- **Two-tone brand gradient** is always `from-brand-primary to-brand-accent`
  (sidebar gradient uses the three `brand-sidebar-*` stops instead).
- **Hover-darken** uses the `-dark` token pair: `hover:bg-brand-primary-dark`
  and `hover:bg-brand-accent-dark`.
- **Structural grays** (`slate-*`, `white`) and **data/status colors**
  (`emerald`, `rose`, `amber`, `sky`, `fuchsia`) are intentionally NOT brand
  tokens — they communicate meaning independent of the brand palette and must
  stay stable across rebrands.

## Logo fallback

If `logo.svg` or `mark.svg` are absent from `frontend/public/brand/`, the
`BrandLogo` component renders a monogram badge — the first letter(s) of
`brand.identity.shortName` — so the app is presentable without any logo assets.
Replace the SVG files to get the real logo.
