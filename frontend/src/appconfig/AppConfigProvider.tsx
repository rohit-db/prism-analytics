import { useEffect, useLayoutEffect, useState } from "react";
import type { ReactNode } from "react";
import { Loader2 } from "lucide-react";
import { accentStyleSheet } from "@/theme/brand";
import type { AppConfig } from "./appConfig";
import { bundledAppConfig } from "./appConfig";
import { AppConfigContext } from "./useAppConfig";

/**
 * Boot-time app-config loader (sibling of RegistryProvider). Fetches GET /api/config
 * ONCE, gating the shell behind a spinner until it settles, then provides
 * ``{brand, content}`` so every downstream consumer reads it synchronously.
 *
 * This is what makes branding CONFIG-DRIVEN rather than baked into the bundle: the
 * server reads brand.config.json / content.config.json per request, so editing a file
 * (or pointing BRAND_CONFIG_FILE at another one) re-skins the app on refresh — no
 * rebuild, no restart. One build can therefore serve many branded instances.
 *
 * Fails soft: on any error the bundled Travel config is used so the app always renders.
 */
export function AppConfigProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<AppConfig | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch("/api/config");
        if (!res.ok) throw new Error(`config ${res.status}`);
        const data = (await res.json()) as AppConfig;
        if (cancelled) return;
        // Server is authoritative, but a body missing either half is malformed —
        // fall back rather than render a half-branded app.
        setConfig(data?.brand?.identity && data?.content ? data : bundledAppConfig);
      } catch {
        if (!cancelled) setConfig(bundledAppConfig);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Re-apply identity + accent once the runtime brand lands. ThemeProvider already did
  // this from the BUNDLED brand for a branded first paint; this overrides it with the
  // runtime values (the seam docs/customizing.md anticipated for per-tenant payloads).
  useLayoutEffect(() => {
    if (!config) return;
    const { brand } = config;
    // Reuse ThemeProvider's node (id "prism-accent") so the runtime accent REPLACES the
    // bundled one rather than adding a competing rule of equal specificity.
    let styleEl = document.getElementById("prism-accent") as HTMLStyleElement | null;
    if (!styleEl) {
      styleEl = document.createElement("style");
      styleEl.id = "prism-accent";
      document.head.appendChild(styleEl);
    }
    styleEl.textContent = accentStyleSheet(brand);

    document.title = brand.identity.appName;

    const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
    if (favicon && brand.identity.favicon) favicon.href = brand.identity.favicon;
  }, [config]);

  if (!config) {
    return (
      <div className="h-full flex items-center justify-center bg-secondary">
        <Loader2 size={28} className="animate-spin text-primary" />
      </div>
    );
  }

  return <AppConfigContext.Provider value={config}>{children}</AppConfigContext.Provider>;
}
