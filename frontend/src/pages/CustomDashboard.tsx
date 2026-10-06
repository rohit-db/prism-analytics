import { useEffect, useRef, useState } from "react";
import { Loader2, AlertCircle } from "lucide-react";
import { DatabricksDashboard } from "@databricks/aibi-client";
import { WORKSPACE, ORG, buildTokenEmbedUrl, fetchEmbedToken, shouldPassEmbedFilters } from "@/config";
import type { DashboardSpec, FilterState } from "@/config";
import type { AssetPage } from "@/registry/types";

// Default global-filter behavior when a dashboard spec doesn't override it. The
// host FilterBar is the only filter UI (filters are driven via the embed URL),
// so we hide the dashboard's own global-filter panel + toggle entirely.
const DEFAULT_GLOBAL_FILTER_VISIBILITY = "disabled" as const;

// The embedded dashboard renders its own page header/title bar at the top. We
// crop it by shifting the iframe up and over-sizing its height (the SDK renders
// the iframe at a flat 100%, so we re-apply this after it builds the iframe).
const HEADER_OFFSET = 48;

function cropIframeHeader(iframe: HTMLIFrameElement | null | undefined) {
  if (!iframe) return;
  iframe.style.display = "block";
  iframe.style.width = "100%";
  iframe.style.border = "0";
  iframe.style.marginTop = `-${HEADER_OFFSET}px`;
  iframe.style.height = `calc(100% + ${HEADER_OFFSET}px)`;
}

interface CustomDashboardProps {
  spec: DashboardSpec;
  pages: AssetPage[];
  filters: FilterState;
  filtersReady?: boolean;
  activePageId?: string;
}

/**
 * White-label dashboard embed.
 *
 * Uses the official @databricks/aibi-client SDK so we get the supported
 * `config.hideDatabricksLogo` flag (removes the "Powered by Databricks" footer)
 * plus token mint/refresh. The SDK has no filter API, so we apply the dashboard
 * `f_…` filter widgets by reloading the embed iframe with the documented URL
 * params — and re-push the hide-logo config after each reload (the SDK only
 * sends it once). Page switches also reload the iframe (the SDK's navigate()
 * only posts a message and silently no-ops in the token-embed context).
 */
export default function CustomDashboard({
  spec,
  pages,
  filters,
  filtersReady = true,
  activePageId,
}: CustomDashboardProps) {
  const dashboardId = spec.id;
  const instanceUrl = spec.workspace ?? WORKSPACE;
  const orgId = spec.org ?? ORG;
  const currentPageId = activePageId || pages[0]?.pageId || "";

  // Embed config pushed to the dashboard. We re-send it ourselves after every
  // iframe reload because the SDK only pushes it once (after the first
  // DATABRICKS_EMBED_READY). `hideDatabricksLogo` drops the footer logo;
  // `globalFilterVisibility` controls the dashboard's native global-filter panel.
  const embedConfig = {
    version: 1,
    hideDatabricksLogo: true,
    globalFilterVisibility: spec.globalFilterVisibility ?? DEFAULT_GLOBAL_FILTER_VISIBILITY,
  };

  const containerRef = useRef<HTMLDivElement>(null);
  const dashRef = useRef<DatabricksDashboard | null>(null);
  const tokenRef = useRef<string>("");
  const pageRef = useRef(currentPageId);
  pageRef.current = currentPageId;

  const [embedReady, setEmbedReady] = useState(false);

  const [phase, setPhase] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState<string | null>(null);

  const fromEmbed = (e: MessageEvent): boolean => {
    try {
      return new URL(e.origin).origin === new URL(instanceUrl).origin;
    } catch {
      return false;
    }
  };

  // Re-send the hide-logo config the next time the embed reports READY (needed
  // after every reload, since the SDK only auto-sends it once).
  const reapplyConfigOnNextReady = () => {
    const onReady = (e: MessageEvent) => {
      if (!fromEmbed(e)) return;
      if (e.data?.type === "DATABRICKS_EMBED_READY") {
        const iframe = containerRef.current?.querySelector("iframe");
        iframe?.contentWindow?.postMessage(
          { type: "DATABRICKS_SET_CONFIG", config: embedConfig },
          instanceUrl
        );
        window.removeEventListener("message", onReady);
      }
    };
    window.addEventListener("message", onReady);
    setTimeout(() => window.removeEventListener("message", onReady), 20000);
  };

  // Reload the embed iframe on `pageId`. When `f` is omitted we load the plain
  // page URL (no f_ params) — this keeps the dashboard's filter panel collapsed
  // for the default browsing case. Pass filters to apply them.
  const reloadWithFilters = (pageId: string, f?: FilterState) => {
    const iframe = containerRef.current?.querySelector("iframe");
    if (!iframe || !tokenRef.current) return;
    reapplyConfigOnNextReady();
    iframe.src = buildTokenEmbedUrl(spec, pageId, tokenRef.current, f);
  };

  // Create the SDK dashboard once per dashboard.
  useEffect(() => {
    let cancelled = false;
    setEmbedReady(false);
    setPhase("loading");
    setError(null);

    const onFirstReady = (e: MessageEvent) => {
      if (!fromEmbed(e)) return;
      if (e.data?.type === "DATABRICKS_EMBED_READY") {
        setEmbedReady(true);
        setPhase("ready");
        window.removeEventListener("message", onFirstReady);
      }
    };
    window.addEventListener("message", onFirstReady);

    (async () => {
      const res = await fetchEmbedToken(dashboardId);
      if (cancelled) return;
      if (!res.ok || !res.token) {
        setError(res.error || "Could not mint embed token");
        setPhase("error");
        return;
      }
      tokenRef.current = res.token;
      if (!containerRef.current) return;
      const dash = new DatabricksDashboard({
        instanceUrl,
        workspaceId: orgId,
        dashboardId,
        pageId: currentPageId || undefined,
        token: res.token,
        container: containerRef.current,
        config: embedConfig,
        getNewToken: async () => {
          const r = await fetchEmbedToken(dashboardId);
          if (r.ok && r.token) tokenRef.current = r.token;
          return r.token || "";
        },
      });
      dash.initialize();
      dashRef.current = dash;
      // The SDK appends its iframe synchronously during initialize(); crop the
      // embedded dashboard's page header (rAF guards against append timing).
      requestAnimationFrame(() => cropIframeHeader(containerRef.current?.querySelector("iframe")));
    })();

    return () => {
      cancelled = true;
      window.removeEventListener("message", onFirstReady);
      try {
        dashRef.current?.destroy();
      } catch {
        /* ignore */
      }
      dashRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dashboardId]);

  // Apply filters / page changes once the embed is ready. Restored prefs often
  // arrive after the iframe mounts (async Lakebase fetch in App), so we key off
  // `embedReady` + `filtersReady` + `filters` rather than only the first READY.
  useEffect(() => {
    if (!embedReady || !filtersReady) return;
    const embedFilters = shouldPassEmbedFilters(spec, filters) ? filters : undefined;
    reloadWithFilters(currentPageId, embedFilters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [embedReady, filtersReady, currentPageId, filters]);

  if (pages.length === 0) {
    return (
      <div className="h-full flex items-center justify-center text-sm text-muted-foreground">
        No pages configured for this dashboard.
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="h-full flex items-center justify-center p-6">
        <div className="max-w-md rounded-md border border-[color:var(--border-danger)] bg-[var(--background-danger)] p-5 text-sm text-[var(--destructive)]">
          <div className="mb-1 flex items-center gap-2 font-semibold">
            <AlertCircle size={16} />
            Could not load the dashboard
          </div>
          <p className="text-[var(--destructive)]">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 relative overflow-hidden bg-background">
        {phase === "loading" && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-background">
            <div className="flex flex-col items-center gap-3 text-muted-foreground">
              <Loader2 size={28} className="animate-spin text-primary" />
              <span className="text-xs font-medium">Preparing secure dashboard…</span>
            </div>
          </div>
        )}
        <div ref={containerRef} className="absolute inset-0" />
      </div>
    </div>
  );
}
