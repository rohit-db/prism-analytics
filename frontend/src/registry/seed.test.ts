import { describe, it, expect } from "vitest";
import { bundledRegistry } from "./seed";

// The seed carries deployment config: its dashboard id and page ids change every
// time the app is pointed at a new workspace. Assert the shape and wiring rather
// than freezing literals, so a retarget doesn't fail these.
describe("bundled registry seed", () => {
  it("carries the spend + sustainability assets on one dashboard", () => {
    const { spend, sustainability } = bundledRegistry.assets;
    expect(spend).toBeDefined();
    expect(sustainability).toBeDefined();
    expect(spend.dashboardId).toBeTruthy();
    // Both surfaces are pages of the same physical dashboard.
    expect(sustainability.dashboardId).toBe(spend.dashboardId);
  });

  it("carries per-page Genie prompts", () => {
    for (const asset of Object.values(bundledRegistry.assets)) {
      for (const page of asset.pages) {
        expect(page.summaryPrompt.trim()).not.toBe("");
        expect(page.suggestions).toHaveLength(3);
      }
    }
    expect(
      bundledRegistry.assets.spend.pages[0].summaryPrompt.toUpperCase()
    ).toContain("SPEND");
  });
});
