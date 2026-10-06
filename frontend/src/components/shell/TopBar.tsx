import { PanelLeftClose, PanelLeft } from "lucide-react";
import { BrandLogo } from "@/components/BrandLogo";
import Breadcrumb from "./Breadcrumb";
import ClientBadge from "./ClientBadge";
import UserMenu from "./UserMenu";
import ThemeToggle from "@/theme/ThemeToggle";
import { useLocation } from "react-router-dom";
import { useRoutes } from "@/registry/useRegistry";
import { useUser } from "@/hooks/useUser";
import { useBrand } from "@/appconfig/useAppConfig";

const SECTION_LABELS: Record<string, string> = {
  insights: "Insights & Analytics",
  exploration: "Exploration",
};

export default function TopBar({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  const location = useLocation();
  const routes = useRoutes();
  const { user } = useUser();
  // Runtime brand, so a config-only re-skin renames the app in the top bar too.
  const brand = useBrand();

  const currentRoute = routes.find((r) => r.path === location.pathname);
  const pageTitle = currentRoute?.label ?? brand.identity.appName;
  const sectionLabel = currentRoute ? SECTION_LABELS[currentRoute.section] : undefined;
  const clientName = user?.tenant || "All clients";

  return (
    <header className="flex h-12 shrink-0 items-center gap-2 bg-secondary px-3">
      {/* Left: collapse toggle + brand */}
      <button
        onClick={onToggle}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        className="grid h-8 w-8 shrink-0 place-items-center rounded text-muted-foreground transition-colors hover:bg-[var(--action-default-bg-hover)] hover:text-foreground"
      >
        {collapsed ? <PanelLeft size={16} /> : <PanelLeftClose size={16} />}
      </button>
      <div className="flex items-center gap-2 shrink-0">
        <BrandLogo variant="mark" className="h-7 w-7 text-base shrink-0" />
        <div className="min-w-0 leading-none">
          <div className="text-[15px] font-semibold tracking-tight text-foreground">
            {brand.identity.appName}
          </div>
          {brand.identity.tagline && (
            <div className="mt-0.5 truncate text-[8.5px] uppercase tracking-[0.16em] text-muted-foreground">
              {brand.identity.tagline}
            </div>
          )}
        </div>
      </div>

      {/* Center: breadcrumb */}
      <div className="flex-1 min-w-0 px-4">
        <Breadcrumb section={sectionLabel} page={pageTitle} />
      </div>

      {/* Right: client + theme + user */}
      <div className="flex items-center gap-2 shrink-0">
        <ClientBadge tenant={clientName} />
        <ThemeToggle />
        <UserMenu user={user} />
      </div>
    </header>
  );
}
