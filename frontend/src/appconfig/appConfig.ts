import { brand as bundledBrand } from "@/theme/brand";
import type { Brand } from "@/theme/brand";

/** How a KPI tile's raw number should be rendered. */
export type KpiFormat = "currency" | "number" | "percent" | "decimal";

export interface KpiSpec {
  /** Matches a key in the /api/kpis response (server owns measure→key). */
  key: string;
  label: string;
  format?: KpiFormat;
  /** Lucide icon name, resolved through the existing ICON_MAP. */
  icon?: string;
  /** Optional short suffix, e.g. "t" for tonnes. */
  unit?: string;
}

export interface Content {
  hero: { title: string; subtitle: string };
  kpis: KpiSpec[];
  trend: { title: string; subtitle: string };
  suggestedQuestions: string[];
  askPlaceholder: string;
}

export interface AppConfig {
  brand: Brand;
  content: Content;
}

/**
 * Bundled fallback — the Travel copy, mirroring server/content.py's DEFAULT_CONTENT.
 * Used when GET /api/config is unreachable so the app always renders (the same
 * fail-soft promise as registry/seed.ts).
 */
export const bundledContent: Content = {
  hero: {
    title: "Travel Intelligence",
    subtitle: "Spend, sustainability and traveler insights across your programme.",
  },
  kpis: [
    { key: "spend", label: "Total Spend", format: "currency", icon: "DollarSign" },
    { key: "emissions", label: "CO₂ Emissions", format: "decimal", icon: "Leaf", unit: "t" },
    { key: "travelers", label: "Travelers", format: "number", icon: "Users" },
    { key: "trips", label: "Trips", format: "number", icon: "Plane" },
  ],
  trend: { title: "Spend Trend", subtitle: "Monthly gross spend" },
  suggestedQuestions: [
    "Total spend by category this year",
    "Top 5 countries by CO₂ emissions",
    "How is spend trending vs last year?",
  ],
  askPlaceholder: "Ask about spend, emissions, bookings…",
};

export const bundledAppConfig: AppConfig = {
  brand: bundledBrand,
  content: bundledContent,
};
