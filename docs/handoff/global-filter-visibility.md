# Hiding the embedded dashboard's global-filter chrome (`globalFilterVisibility`)

> **Status:** ✅ Verified working in Prism on the FEVM workspace (`fevm-serverless-stable-71zsua`), 2026-10-05.
> Replaces the pixel-crop hack as the *proper* way to hide the AI/BI dashboard's native
> global-filter button/panel while the host app's own FilterBar keeps driving filters.

---

## 📣 Slack message (paste-ready)

> **Yes**

---

## How it works (implementation detail)

The embedded AI/BI dashboard's **global-filter panel** (and its toggle button) is now
controllable through the `@databricks/aibi-client` embed config:

```ts
new DatabricksDashboard({
  // …token, dashboardId, container…
  config: {
    version: 1,
    hideDatabricksLogo: true,
    globalFilterVisibility: "disabled", // ← new field, SDK ≥ 1.2.0
  },
});
```

### The three states


| Value               | Behavior                                                                                                                                                              |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `"shownByDefault"`  | Panel starts **expanded**; viewer can collapse it.                                                                                                                    |
| `"hiddenByDefault"` | Panel starts **collapsed**; viewer can open it.                                                                                                                       |
| `"disabled"`        | Panel **and** its toggle button are **hidden entirely**; the viewer can't open or change them. **Filter values from the embed URL (or author defaults) still apply.** |
| *(omitted)*         | Dashboard's own default behavior.                                                                                                                                     |


For a white-label app where the host FilterBar is the only filter UI, use **`disabled`**.

### Delivery — there is no URL param

`globalFilterVisibility` reaches the embed **only** through the `DATABRICKS_SET_CONFIG`
postMessage (the SDK's embed URL carries just `o` + the `#token` hash — no config params).
The SDK sends the config once, right after *its own* iframe finishes loading. If your app
reloads the iframe itself (e.g. to apply filter URL params), you must **re-send the config**
after each reload — otherwise only the SDK's first load is configured. `CURRENT_CONFIG_VERSION`
is `1`, so `version: 1` is correct.

### Where it lives in Prism


| Concern                                                                                                    | File                                     |
| ---------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| `DashboardSpec.globalFilterVisibility` (config-driven, default `"disabled"`)                               | `frontend/src/config.ts`                 |
| `embedConfig` — pushed at SDK construction **and** re-pushed via `DATABRICKS_SET_CONFIG` after each reload | `frontend/src/pages/CustomDashboard.tsx` |
| SDK dependency bump `^1.0.3-alpha.0` → `^1.2.0`                                                            | `frontend/package.json`                  |


## Gotchas

1. **`hideRefreshButton` is deprecated.** The SDK marks it `@deprecated` / "not currently
 available," so it no longer hides the refresh button. The pixel-crop (`HEADER_OFFSET`) is
 still the only way to hide the refresh button.
2. **The header crop hides the global-filters button during testing.** Prism crops the top
 ~48px of the iframe (`HEADER_OFFSET = 48` in `CustomDashboard.tsx`) to hide the dashboard's
 page header — and the global-filters button lives in that strip. With the crop on, all three
 `globalFilterVisibility` states *look identical* because the button is cropped out of frame.
 Set `HEADER_OFFSET = 0` to verify the field is actually working.
3. **Availability.** Embed-side support landed in the 2026-10-01 AI/BI release notes and is
 rolling out to workspaces. The npm SDK forwards the field as of **1.2.0** (older versions
 drop it). Confirm your target workspace has the embed feature before relying on it.

