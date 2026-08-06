import brandJson from "@brand";

export type Theme = "light" | "dark";

export interface Brand {
  identity: {
    appName: string;
    shortName: string;
    tagline: string;
    logo: string;
    logoMark: string;
    favicon: string;
  };
  colors: {
    /** Drives --primary and its derivations. */
    accent: string;
    /** Second stop of the brand gradient (logo mark, gradient borders). Defaults to accent. */
    accentAlt?: string;
    /** Optional third gradient stop for a richer mark. */
    accentAlt2?: string;
    /** Sidebar surface + its foreground. Set both, or neither, to flip a shell dark. */
    sidebar?: string;
    sidebarForeground?: string;
  };
  /** Per-brand shape + type. These are what make instances read as different PRODUCTS. */
  design?: {
    /** Base corner radius, e.g. "0.25rem" (sharp) … "0.75rem" (soft). */
    radius?: string;
    /** CSS font-family stack for body text. */
    fontSans?: string;
    /** CSS font-family stack for headings; falls back to fontSans. */
    fontDisplay?: string;
    /** Extra Google Fonts css2 URL to load at runtime for the two families above. */
    fontUrl?: string;
    /** Heading letter-spacing, e.g. "-0.02em". */
    headingTracking?: string;
  };
  defaults?: { theme: Theme };
}

export const brand = brandJson as Brand;

export const DEFAULT_THEME: Theme = brand.defaults?.theme ?? "light";

/**
 * The config-driven CSS: accent + its derivations, the brand gradient, shape (radius) and
 * type (font stacks), emitted as real cascade rules so the `.dark` block can still brighten
 * --primary (inline styles would override the class rule and break dark-mode contrast).
 * Everything not set here stays canonical DuBois from index.css.
 *
 * This is deliberately broader than just color: radius + typeface + gradient are what make
 * two instances read as different PRODUCTS rather than one product in two colors.
 */
export function accentStyleSheet(b: Brand): string {
  const a = b.colors.accent;
  const alt = b.colors.accentAlt ?? a;
  const alt2 = b.colors.accentAlt2;
  const aDark = `color-mix(in srgb, ${a} 65%, white)`;
  const d = b.design ?? {};

  const gradient = alt2
    ? `linear-gradient(135deg, ${a} 8%, ${alt} 52%, ${alt2} 96%)`
    : `linear-gradient(135deg, ${a} 0%, ${alt} 100%)`;

  const root: string[] = [
    `--primary:${a}`,
    `--primary-foreground:#ffffff`,
    `--ring:${a}`,
    `--sidebar-primary:${a}`,
    `--sidebar-ring:${a}`,
    `--accent-gradient:${gradient}`,
  ];
  if (d.radius) root.push(`--radius:${d.radius}`);
  if (d.fontSans) root.push(`--font-sans:${d.fontSans}`);
  if (d.fontDisplay || d.fontSans) {
    root.push(`--font-display:${d.fontDisplay ?? d.fontSans}`);
  }
  if (d.headingTracking) root.push(`--heading-tracking:${d.headingTracking}`);
  if (b.colors.sidebar) root.push(`--sidebar:${b.colors.sidebar}`);
  if (b.colors.sidebarForeground) {
    root.push(
      `--sidebar-foreground:${b.colors.sidebarForeground}`,
      // Keep hover/active surfaces legible on a dark sidebar.
      `--sidebar-accent:color-mix(in srgb, ${b.colors.sidebarForeground} 12%, transparent)`,
      `--sidebar-accent-foreground:${b.colors.sidebarForeground}`,
      `--sidebar-border:color-mix(in srgb, ${b.colors.sidebarForeground} 16%, transparent)`
    );
  }

  return (
    `:root{${root.join(";")};}` +
    `.dark{` +
    `--primary:${aDark};--primary-foreground:#11171c;` +
    `--ring:${aDark};--sidebar-primary:${aDark};--sidebar-ring:${aDark};` +
    `}` +
    // Headings pick up the display face + tracking wherever they're rendered.
    `h1,h2,h3,h4{font-family:var(--font-display,var(--font-sans));` +
    `letter-spacing:var(--heading-tracking,normal);}`
  );
}
