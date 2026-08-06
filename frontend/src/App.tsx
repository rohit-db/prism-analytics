import { useState, useEffect, useCallback } from "react";
import { Routes, Route, Navigate, useLocation, useNavigate } from "react-router-dom";
import { Sparkles, MessageCircle, Settings } from "lucide-react";
import Sidebar from "@/components/Sidebar";
import type { SidebarNavSection } from "@/components/Sidebar";
import TopBar from "@/components/shell/TopBar";
import { AppShell } from "@/components/shell/AppShell";
import FilterBar from "@/components/FilterBar";
import DashboardWorkspace from "@/components/DashboardWorkspace";
import CustomDashboard from "@/pages/CustomDashboard";
import GenieMcpExperience from "@/pages/GenieMcpExperience";
import AskLive from "@/pages/AskLive";
import HomePage from "@/pages/HomePage";
import PreferencesPage from "@/pages/PreferencesPage";
import Placeholder from "@/pages/Placeholder";
import AdminLayout from "@/pages/admin/AdminLayout";
import AssetsPage from "@/pages/admin/AssetsPage";
import TenantsPage from "@/pages/admin/TenantsPage";
import AccessPage from "@/pages/admin/AccessPage";
import { ADMIN_BASE, ADMIN_ASSETS_PATH, ADMIN_SECTIONS } from "@/components/admin/adminContext";
import { useUser } from "@/hooks/useUser";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  filtersToContext,
  getSupportedFilterKeys,
  DEFAULT_FILTERS,
  loadEffectiveFilterPrefs,
  saveFilterPrefs,
} from "@/config";
import type { FilterState, RouteConfig, DashboardSpec } from "@/config";
import { useRegistry, useDashboardAsset, useRoutes } from "@/registry/useRegistry";
import type { AssetSpec, AssetPage } from "@/registry/types";

/** The embedded-dashboard SDK + URL helpers key off `id`; map the asset onto that shape. */
function toEmbedSpec(asset: AssetSpec): DashboardSpec {
  return {
    id: asset.dashboardId,
    globalFilterPage: asset.globalFilterPage,
    filters: asset.filters,
    workspace: asset.workspace,
    org: asset.org,
  };
}

/**
 * Resolve the Genie config for the active page (falls back to the first page).
 * A registry asset is expected to have >=1 page; if it somehow has none, we
 * degrade to empty prompt/suggestions rather than crash (the Exec Summary /
 * rail just have nothing to send). PR3b's in-UI asset editing should enforce
 * >=1 page at the edit boundary.
 */
function pageGenie(asset: AssetSpec | undefined, pageId?: string): { summaryPrompt: string; suggestions: string[] } {
  const page = asset?.pages.find((p) => p.pageId === pageId) ?? asset?.pages[0];
  return { summaryPrompt: page?.summaryPrompt ?? "", suggestions: page?.suggestions ?? [] };
}

function RouteRenderer({
  route,
  filters,
  filtersReady,
  activePageId,
  railOpen,
  onRailOpenChange,
  summaryOpen,
  onSummaryOpenChange,
}: {
  route: RouteConfig;
  filters: FilterState;
  filtersReady: boolean;
  activePageId?: string;
  railOpen: boolean;
  onRailOpenChange: (open: boolean) => void;
  summaryOpen: boolean;
  onSummaryOpenChange: (open: boolean) => void;
}) {
  const asset = useDashboardAsset(route.dashboard);
  switch (route.mode) {
    case "custom": {
      if (!asset) return <Placeholder />;
      const pages = asset.pages;
      const spec = toEmbedSpec(asset);
      const genie = pageGenie(asset, activePageId);
      const pageLabel = `${route.label} · ${pages.find((p) => p.pageId === activePageId)?.label ?? ""}`.replace(/ · $/, "");
      const pageContext = [`Dashboard: ${pageLabel}`, filtersToContext(filters, spec)].filter(Boolean).join(". ");
      const content = (
        <CustomDashboard spec={spec} pages={pages} filters={filters} filtersReady={filtersReady} activePageId={activePageId} />
      );
      return (
        <DashboardWorkspace
          pageKey={`${route.path}:${activePageId ?? ""}`}
          pageLabel={pageLabel}
          pageContext={pageContext}
          summaryPrompt={genie.summaryPrompt}
          suggestions={genie.suggestions}
          railOpen={railOpen}
          onRailOpenChange={onRailOpenChange}
          summaryOpen={summaryOpen}
          onSummaryOpenChange={onSummaryOpenChange}
        >
          {content}
        </DashboardWorkspace>
      );
    }
    case "react":
      if (route.path === "/") return <HomePage />;
      if (route.path === "/genie-mcp") return <GenieMcpExperience />;
      if (route.path === "/ask-live") return <AskLive />;
      if (route.path === "/preferences") return <PreferencesPage />;
      return <Placeholder />;
    case "placeholder":
    default:
      return <Placeholder />;
  }
}

export default function App() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [filters, setFilters] = useState<FilterState>(DEFAULT_FILTERS);
  const [filtersReady, setFiltersReady] = useState(false);
  const [activePageId, setActivePageId] = useState<string | undefined>();
  const [railOpen, setRailOpen] = useState(false);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const location = useLocation();
  const navigate = useNavigate();

  const registry = useRegistry();
  const routes = useRoutes();
  const currentRoute = routes.find((r) => r.path === location.pathname);

  const { user } = useUser();
  const isOperator = user?.role === "operator";
  const inAdmin = location.pathname.startsWith(ADMIN_BASE);

  const sidebarSections: SidebarNavSection[] = inAdmin && isOperator
    ? [
        { items: [{ path: "/", label: "Back to Prism", icon: "ArrowLeftNav" }] },
        {
          label: "Administration",
          items: ADMIN_SECTIONS.map((s) => ({ path: s.path, label: s.label, icon: s.icon })),
        },
      ]
    : [
        {
          label: "Insights & Analytics",
          items: routes
            .filter((r) => r.section === "insights")
            .map((r) => ({ path: r.path, label: r.label, icon: r.icon, placeholder: r.mode === "placeholder" })),
        },
        {
          label: "Exploration",
          items: routes
            .filter((r) => r.section === "exploration")
            .map((r) => ({ path: r.path, label: r.label, icon: r.icon, placeholder: r.mode === "placeholder" })),
        },
      ];

  const sidebarFooter = isOperator && !inAdmin ? (
    <button
      onClick={() => navigate(ADMIN_ASSETS_PATH)}
      title={sidebarCollapsed ? "Admin" : undefined}
      className={`group flex h-7 w-full items-center gap-2 rounded text-[13px] font-medium text-sidebar-foreground/85 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground ${sidebarCollapsed ? "justify-center px-0" : "px-3 text-left"}`}
    >
      <Settings size={16} className="shrink-0 text-sidebar-foreground/60 group-hover:text-sidebar-foreground" />
      {!sidebarCollapsed && <span>Admin</span>}
    </button>
  ) : undefined;
  const isCustom = currentRoute?.mode === "custom";
  const currentAsset: AssetSpec | undefined = currentRoute?.dashboard ? registry.assets[currentRoute.dashboard] : undefined;
  const pages: AssetPage[] = currentAsset?.pages ?? [];
  const currentDashboardId = currentAsset?.dashboardId;
  const filterKeys = getSupportedFilterKeys(currentAsset ? toEmbedSpec(currentAsset) : undefined);

  // Restore filters: My Filters defaults, with per-dashboard FilterBar overrides on top.
  const loadFilterPrefs = useCallback(async (): Promise<FilterState | null> => {
    if (!currentDashboardId) return null;
    return loadEffectiveFilterPrefs(currentDashboardId);
  }, [currentDashboardId]);

  useEffect(() => {
    let cancelled = false;
    setFiltersReady(false);
    loadFilterPrefs().then((next) => {
      if (cancelled) return;
      if (next) setFilters(next);
      setFiltersReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, [currentDashboardId, location.pathname, loadFilterPrefs]);

  // Re-apply when global defaults are saved on the Preferences page.
  useEffect(() => {
    const onPrefsSaved = () => {
      void loadFilterPrefs().then((next) => {
        if (next) setFilters(next);
      });
    };
    window.addEventListener("prism:filter-prefs-saved", onPrefsSaved);
    return () => window.removeEventListener("prism:filter-prefs-saved", onPrefsSaved);
  }, [loadFilterPrefs]);

  // Apply + persist the user's filter selection.
  const handleFilterChange = useCallback(
    (next: FilterState) => {
      setFilters(next);
      if (currentDashboardId) saveFilterPrefs(currentDashboardId, next);
    },
    [currentDashboardId]
  );

  // Reset active page when route changes
  const effectivePageId = activePageId && pages.some(p => p.pageId === activePageId)
    ? activePageId
    : pages[0]?.pageId;

  // Close the assistant rail / summary modal when navigating to a new page.
  useEffect(() => {
    setRailOpen(false);
    setSummaryOpen(false);
  }, [location.pathname, effectivePageId]);

  return (
    <AppShell
      topBar={<TopBar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} />}
      sidebar={<Sidebar collapsed={sidebarCollapsed} sections={sidebarSections} footer={sidebarFooter} />}
    >
      {/* Unified dashboard toolbar: page tabs (left) + page actions (right) */}
      {isCustom && (
        <div className="shrink-0 bg-background px-5 pt-3 pb-1 flex items-center justify-between gap-3">
          {isCustom && pages.length > 0 ? (
            <Tabs value={effectivePageId} onValueChange={setActivePageId}>
              <TabsList>
                {pages.map((page) => (
                  <TabsTrigger key={page.pageId} value={page.pageId}>
                    {page.label}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          ) : (
            <div />
          )}
          <div className="flex items-center gap-2 shrink-0">
            <Button
              size="sm"
              variant="default"
              onClick={() => setSummaryOpen(true)}
              className="gap-1.5 text-primary border-primary/30 hover:bg-primary/10 hover:text-blue-700"
            >
              <Sparkles size={14} />
              <span>Executive Summary</span>
            </Button>
            <Button
              size="sm"
              variant={railOpen ? "primary" : "default"}
              onClick={() => setRailOpen((o) => !o)}
              className="gap-1.5"
            >
              <MessageCircle size={14} />
              <span>Ask Prism</span>
            </Button>
          </div>
        </div>
      )}

      {isCustom && filterKeys.length > 0 && (
        <FilterBar filters={filters} onChange={handleFilterChange} filterKeys={filterKeys} />
      )}

      <div className="flex-1 flex min-h-0">
        <main className="flex-1 flex flex-col min-w-0 bg-background border border-border rounded-md mr-2 mb-2 overflow-y-auto">
          <Routes>
            <Route path={ADMIN_BASE} element={<AdminLayout />}>
              <Route index element={<Navigate to={ADMIN_ASSETS_PATH} replace />} />
              <Route path="assets" element={<AssetsPage />} />
              <Route path="access" element={<AccessPage />} />
              <Route path="tenants" element={<TenantsPage />} />
            </Route>
            {routes.map((route) => (
              <Route
                key={route.path}
                path={route.path}
                element={
                  <RouteRenderer
                    route={route}
                    filters={filters}
                    filtersReady={filtersReady}
                    activePageId={effectivePageId}
                    railOpen={railOpen}
                    onRailOpenChange={setRailOpen}
                    summaryOpen={summaryOpen}
                    onSummaryOpenChange={setSummaryOpen}
                  />
                }
              />
            ))}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </AppShell>
  );
}
