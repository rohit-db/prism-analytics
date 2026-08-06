# Per-instance logo assets

Each demo instance serves its own `/brand/*` from the directory named by
`BRAND_ASSETS_DIR` in its env file. One build, three logos.

| Instance | Port | `BRAND_ASSETS_DIR` |
|----------|------|--------------------|
| Prism · Travel Intelligence | 8000 | `demo/logos/travel` |
| Meridian Retail · Vendor Portal | 8001 | `demo/logos/retail` |
| Cascade Hotels · Owner Portal | 8002 | `demo/logos/hotel` |

## Dropping in a custom logo

Replace these three files in the relevant folder, then **just refresh the browser** —
assets are served from disk per request, so no rebuild and no restart:

| File | Used by | Notes |
|------|---------|-------|
| `mark.svg` | sidebar header, login card, favicon source | Square. Design on a **~64×64 viewBox**; rendered as small as 30×30, so keep it simple. |
| `logo.svg` | wherever the full lockup renders | Wide, roughly **220–230 × 48**. Use `fill="currentColor"` for text so it works in light *and* dark mode. |
| `favicon.svg` | browser tab | Usually just a copy of `mark.svg`. |

The files currently in each folder are hand-written placeholders (a prism triangle, a
Meridian "M", Cascade arcs) so every instance looks finished out of the box. Overwrite them.

## If you generate logos with Claude Design

Ask for **SVG**, and mention:

- A square mark on a 64×64 viewBox, legible at 30×30.
- A horizontal lockup around 220×48 with the wordmark in `currentColor`.
- The brand's palette, which lives in `demo/brands/<name>.json` under `colors`:
  - Travel: `#2272b4` → `#4299e0` → `#7c3aed` (cool, crystalline)
  - Retail: `#c2410c` → `#ea580c` → `#f59e0b` (warm, geometric)
  - Hotels: `#0f766e` → `#0d9488` → `#65a30d` (deep teal, editorial/serif)

## Fallbacks (nothing breaks)

- A **missing or broken** `logo.svg` / `mark.svg` → `BrandLogo` renders a monogram badge
  from `identity.shortName`.
- A **missing `BRAND_ASSETS_DIR`** → the mount is skipped and `/brand/*` falls through to
  the built SPA's copy.

So a half-finished logo set degrades to something presentable rather than a broken image.

## Related config

`demo/brands/<name>.json` carries the rest of the identity — `colors.accent` +
`accentAlt`/`accentAlt2` (the gradient), and a `design` block with `radius`, `fontSans`,
`fontDisplay`, `fontUrl` and `headingTracking`. Those are also read per request, so editing
one and refreshing re-skins the running app. See `docs/customizing.md`.
