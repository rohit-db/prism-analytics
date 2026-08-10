import type { FilterKey } from "@/config";

/** One page within a dashboard asset (its id, label, and Genie wiring). */
export interface AssetPage {
  pageId: string;
  label: string;
  summaryPrompt: string;
  suggestions: string[];
}

/**
 * A dashboard asset: the full spec the app renders + wires. Structural superset
 * of config.ts DashboardSpec (adds `label`, `pages`; the physical Lakeview id is
 * `dashboardId`). Filter render vocabulary (FilterKey) lives in config.ts FILTERS;
 * `filters` only references those keys.
 */
/**
 * Optional nav metadata that lets an asset generate its own sidebar entry +
 * route (PR3c). When absent, the asset is still embeddable but does not appear
 * in the nav on its own — the fixed react routes in config.ts are separate.
 */
export interface AssetNav {
  path: string;                          // route path, must start with "/"
  icon: string;                          // key into config.ts ICON_MAP
  section: "insights" | "exploration";   // which sidebar group
  order: number;                         // sort within the section
  /**
   * Render a "coming soon" stub instead of an embedded dashboard. Lets a deployment
   * show its full intended nav (icons + labels) before every dashboard exists —
   * per-instance, since the registry is per-instance.
   */
  placeholder?: boolean;
}

export interface AssetSpec {
  label: string;
  dashboardId: string;
  globalFilterPage: string;
  filters: Partial<Record<FilterKey, string>>;
  workspace?: string;
  org?: string;
  pages: AssetPage[];
  nav?: AssetNav;
}

export interface Registry {
  assets: Record<string, AssetSpec>;
}
