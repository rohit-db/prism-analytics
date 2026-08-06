import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar, { type SidebarNavSection } from "./Sidebar";

const sections: SidebarNavSection[] = [
  { label: "Insights & Analytics", items: [{ path: "/", label: "Home", icon: "LayoutDashboard" }] },
  { label: "Exploration", items: [{ path: "/genie-mcp", label: "Ask Prism", icon: "Sparkles" }] },
];

function renderAt(path: string, props?: Partial<React.ComponentProps<typeof Sidebar>>) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar collapsed={false} sections={sections} {...props} />
    </MemoryRouter>
  );
}

describe("Sidebar", () => {
  it("renders section labels and nav items from props", () => {
    renderAt("/");
    expect(screen.getByText("Insights & Analytics")).toBeInTheDocument();
    expect(screen.getByText("Home")).toBeInTheDocument();
    expect(screen.getByText("Ask Prism")).toBeInTheDocument();
  });

  it("marks the active route with the sidebar-scoped active classes", () => {
    // Sidebar-scoped tokens (not bg-primary/text-primary) so nav stays legible when a
    // brand flips the shell dark via colors.sidebar in its brand config.
    renderAt("/");
    const active = screen.getByText("Home").closest("button")!;
    expect(active.className).toMatch(/bg-sidebar-primary\/15/);
    expect(active.className).toMatch(/text-sidebar-primary/);
    expect(active.className).toMatch(/font-semibold/);
  });

  it("renders a footer when provided", () => {
    renderAt("/", { footer: <button>Admin</button> });
    expect(screen.getByRole("button", { name: "Admin" })).toBeInTheDocument();
  });

  it("collapses to icon-only width", () => {
    const { container } = render(
      <MemoryRouter><Sidebar collapsed sections={sections} /></MemoryRouter>
    );
    expect((container.firstChild as HTMLElement).className).toMatch(/w-\[60px\]/);
  });
});
