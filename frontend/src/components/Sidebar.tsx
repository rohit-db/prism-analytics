import { useLocation, useNavigate } from "react-router-dom";
import { cn } from "@/lib/utils";
import { ICON_MAP } from "@/config";

export interface SidebarNavItem {
  path: string;
  label: string;
  icon: string;
  placeholder?: boolean;
}
export interface SidebarNavSection {
  label?: string;
  items: SidebarNavItem[];
}
export interface SidebarProps {
  collapsed: boolean;
  sections: SidebarNavSection[];
  footer?: React.ReactNode;
}

export default function Sidebar({ collapsed, sections, footer }: SidebarProps) {
  return (
    <aside
      className={cn(
        // bg-sidebar (not bg-secondary) so a brand can flip the shell dark via config.
        // --sidebar defaults to the same value as --secondary, so this is a no-op unless
        // the brand sets colors.sidebar.
        "flex h-full shrink-0 flex-col bg-sidebar text-sidebar-foreground",
        "transition-all duration-200 overflow-hidden",
        collapsed ? "w-[60px]" : "w-[224px]"
      )}
    >
      <nav
        className={cn(
          "flex flex-1 flex-col gap-4 overflow-y-auto py-4",
          collapsed ? "px-1.5" : "px-3",
          "[&::-webkit-scrollbar]:w-[5px] [&::-webkit-scrollbar-track]:bg-transparent",
          "[&::-webkit-scrollbar-thumb]:rounded-full [&::-webkit-scrollbar-thumb]:bg-border"
        )}
      >
        {sections.map((section, i) => (
          <div key={i} className="flex flex-col gap-0.5">
            {section.label && !collapsed && (
              <div className="px-2 mb-1 text-[9px] font-semibold uppercase tracking-[0.16em] text-sidebar-foreground/55">
                {section.label}
              </div>
            )}
            {section.items.map((item) => (
              <NavItem key={item.path} item={item} collapsed={collapsed} />
            ))}
          </div>
        ))}
      </nav>
      {footer && (
        <div className="shrink-0 border-t border-sidebar-border px-3 py-3">{footer}</div>
      )}
    </aside>
  );
}

function NavItem({ item, collapsed }: { item: SidebarNavItem; collapsed: boolean }) {
  const location = useLocation();
  const navigate = useNavigate();
  const Icon = ICON_MAP[item.icon];
  const active = location.pathname === item.path;

  return (
    <button
      onClick={() => navigate(item.path)}
      title={collapsed ? item.label : undefined}
      className={cn(
        "group flex h-7 w-full items-center gap-2 rounded px-3 text-left text-[13px] transition-colors",
        collapsed && "justify-center px-0",
        // Sidebar-scoped tokens so nav stays legible when a brand flips the shell dark.
        active
          ? "bg-sidebar-primary/15 text-sidebar-primary font-semibold"
          : "text-sidebar-foreground/85 font-medium hover:bg-sidebar-accent hover:text-sidebar-foreground"
      )}
    >
      {Icon && (
        <Icon
          size={16}
          className={cn(
            "shrink-0 transition-colors",
            active
              ? "text-sidebar-primary"
              : "text-sidebar-foreground/60 group-hover:text-sidebar-foreground"
          )}
        />
      )}
      {!collapsed && (
        <>
          <span className="flex-1 truncate">{item.label}</span>
          {item.placeholder && (
            <span className="rounded bg-[var(--action-default-bg-hover)] px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground">
              soon
            </span>
          )}
        </>
      )}
    </button>
  );
}
