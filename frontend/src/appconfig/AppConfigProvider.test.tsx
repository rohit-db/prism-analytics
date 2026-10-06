import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AppConfigProvider } from "./AppConfigProvider";
import { useAppConfig } from "./useAppConfig";
import { bundledContent } from "./appConfig";

function Probe() {
  const { brand, content } = useAppConfig();
  return (
    <div>
      <span data-testid="app-name">{brand.identity.appName}</span>
      <span data-testid="hero">{content.hero.title}</span>
    </div>
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("AppConfigProvider", () => {
  it("provides the fetched config when GET /api/config succeeds", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({
          brand: {
            identity: {
              appName: "Meridian Retail",
              shortName: "Meridian",
              tagline: "Vendor Portal",
              logo: "",
              logoMark: "",
              favicon: "",
            },
            colors: { accent: "#b8590a" },
          },
          content: { ...bundledContent, hero: { title: "Vendor Performance", subtitle: "s" } },
        }),
      })
    );

    render(
      <AppConfigProvider>
        <Probe />
      </AppConfigProvider>
    );

    await waitFor(() => expect(screen.getByTestId("app-name")).toHaveTextContent("Meridian Retail"));
    expect(screen.getByTestId("hero")).toHaveTextContent("Vendor Performance");
  });

  it("falls back to the bundled config when the fetch is non-ok", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));

    render(
      <AppConfigProvider>
        <Probe />
      </AppConfigProvider>
    );

    await waitFor(() => expect(screen.getByTestId("hero")).toHaveTextContent(bundledContent.hero.title));
  });

  it("falls back to the bundled config when the fetch rejects", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    render(
      <AppConfigProvider>
        <Probe />
      </AppConfigProvider>
    );

    await waitFor(() => expect(screen.getByTestId("hero")).toHaveTextContent(bundledContent.hero.title));
  });

  it("falls back when the body is malformed (missing content)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ brand: { identity: { appName: "Half" } } }),
      })
    );

    render(
      <AppConfigProvider>
        <Probe />
      </AppConfigProvider>
    );

    // A half-branded app is worse than the known-good bundled default.
    await waitFor(() => expect(screen.getByTestId("hero")).toHaveTextContent(bundledContent.hero.title));
  });
});
