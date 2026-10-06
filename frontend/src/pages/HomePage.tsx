import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Sparkles,
  ArrowUp,
  ArrowRight,
  TrendingUp,
  TrendingDown,
  MessageCircle,
  type LucideIcon,
} from "lucide-react";
import {
  fetchKpis,
  fetchKpiTrend,
  ICON_MAP,
  type KpiValues,
  type KpiResponse,
  type TrendPoint,
} from "@/config";
import { useUser } from "@/hooks/useUser";
import { useRoutes } from "@/registry/useRegistry";
import { useContent, useBrand } from "@/appconfig/useAppConfig";
import type { KpiSpec } from "@/appconfig/appConfig";
import GradientMark from "@/theme/GradientMark";

// ─── KPI presentation config ──────────────────────────────────────────────────

type KpiKey = keyof KpiValues;

interface KpiMeta {
  key: KpiKey;
  label: string;
  icon: LucideIcon;
  format: (n: number) => string;
  // Whether an increase is "good" (green), "bad" (rose), or neutral (slate).
  goodDirection: "up" | "down" | "neutral";
}

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});
const compact = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
});

const decimal = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
});
const percent = new Intl.NumberFormat("en-US", {
  style: "percent",
  maximumFractionDigits: 1,
});

/** Fallback icon for a KPI whose configured `icon` name isn't in ICON_MAP. */
const KPI_ICON_FALLBACK: LucideIcon = TrendingUp;

/**
 * Build the KPI tile metadata from the runtime content config, so a vertical's tiles
 * (labels, icons, number formats) come from content.config.json rather than code.
 * The `key` must match a key in the /api/kpis response — the server's KPI_MEASURES
 * owns measure→key, this owns key→label.
 */
function buildKpis(specs: KpiSpec[]): KpiMeta[] {
  return specs.map((s) => {
    const unit = s.unit ? ` ${s.unit}` : "";
    const format = (n: number): string => {
      switch (s.format) {
        case "currency":
          return currency.format(n);
        case "percent":
          return percent.format(n);
        case "decimal":
          return `${decimal.format(n)}${unit}`;
        default:
          return `${compact.format(n)}${unit}`;
      }
    };
    return {
      key: s.key as KpiKey,
      label: s.label,
      icon: (s.icon && ICON_MAP[s.icon]) || KPI_ICON_FALLBACK,
      format,
      // Emissions-style measures are better when they fall; everything else is neutral.
      goodDirection: /emission|co2|cancel|return|discount/i.test(s.key) ? "down" : "neutral",
    } satisfies KpiMeta;
  });
}

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HomePage() {
  const navigate = useNavigate();
  const { user } = useUser();
  const content = useContent();
  const brand = useBrand();
  const routes = useRoutes();
  const kpiMetas = useMemo(() => buildKpis(content.kpis), [content.kpis]);
  // The dashboard routes this instance actually serves, capped at two so the row stays
  // three-up alongside the Ask card.
  const quickCards = useMemo(
    () => routes.filter((r) => r.dashboard).slice(0, 2),
    [routes]
  );
  const [input, setInput] = useState("");
  const [kpis, setKpis] = useState<KpiResponse | null>(null);
  const [kpiLoading, setKpiLoading] = useState(true);
  const [trend, setTrend] = useState<TrendPoint[] | null>(null);
  const [trendLoading, setTrendLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    fetchKpis().then((res) => {
      if (cancelled) return;
      setKpis(res);
      setKpiLoading(false);
    });
    fetchKpiTrend().then((res) => {
      if (cancelled) return;
      setTrend(res.ok && res.series ? res.series : []);
      setTrendLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const ask = (q: string) => {
    const text = q.trim();
    if (!text) return;
    navigate(`/genie-mcp?q=${encodeURIComponent(text)}`);
  };

  const firstName = (user?.displayName || "").split(/\s+/)[0] || "there";
  const showKpis = kpiLoading || (kpis?.ok && kpis.current);

  return (
    <div className="flex-1 overflow-y-auto bg-background">
      <div className="mx-auto w-full max-w-5xl px-6 py-8 md:py-10">
        {/* ── Hero ─────────────────────────────────────────────────────── */}
        <section className="rounded-md border border-border bg-secondary px-7 py-8 md:px-10 md:py-10">
          <div className="relative z-10">
            <div className="flex items-center gap-2 text-[12px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
              <GradientMark size={20} />
              {user?.tenant || content.hero.title}
            </div>
            <h1 className="mt-2 text-2xl md:text-[28px] font-semibold tracking-tight text-foreground">
              {greeting()}, {firstName}.
            </h1>
            <p className="mt-1.5 max-w-lg text-[14px] leading-relaxed text-muted-foreground">
              {content.hero.subtitle}
            </p>

            {/* Ask Prism composer */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                ask(input);
              }}
              className="gradient-border group relative mt-6 flex items-center rounded-md bg-background px-4 py-2.5 transition-all focus-within:ring-2 focus-within:ring-ring"
            >
              <Sparkles className="mr-2.5 h-4 w-4 shrink-0 text-muted-foreground" />
              {/* eslint-disable-next-line jsx-a11y/no-autofocus */}
              <input
                autoFocus
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={content.askPlaceholder}
                className="flex-1 bg-transparent py-1 text-[15px] text-foreground placeholder:text-muted-foreground focus:outline-none"
              />
              <button
                type="submit"
                disabled={!input.trim()}
                className="ml-2 flex h-8 w-8 shrink-0 items-center justify-center rounded bg-primary text-primary-foreground transition-colors hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-30"
              >
                <ArrowUp size={16} strokeWidth={2.5} />
              </button>
            </form>

            <div className="mt-3 flex flex-wrap gap-2">
              {content.suggestedQuestions.map((q) => (
                <button
                  key={q}
                  onClick={() => ask(q)}
                  className="rounded border border-border bg-background px-3.5 py-1.5 text-[12.5px] text-foreground transition-colors hover:bg-[var(--action-default-bg-hover)] hover:text-blue-700"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </section>

        {/* ── KPI strip ────────────────────────────────────────────────── */}
        {showKpis && (
          <section className="mt-6">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-[13px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                This year at a glance
              </h2>
              <span className="text-[11px] text-muted-foreground">vs. prior year</span>
            </div>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {kpiMetas.map((meta) =>
                kpiLoading ? (
                  <KpiSkeleton key={meta.key} />
                ) : (
                  <KpiCard
                    key={meta.key}
                    meta={meta}
                    current={kpis?.current?.[meta.key] ?? null}
                    previous={kpis?.previous?.[meta.key] ?? null}
                  />
                )
              )}
            </div>
          </section>
        )}

        {/* ── Trends ───────────────────────────────────────────────────── */}
        {(trendLoading || (trend && trend.length > 0)) && (
          <section className="mt-6 grid grid-cols-1 gap-3 lg:grid-cols-2">
            {/* The server charts the FIRST TWO configured measures and exposes them under
                the legacy `spend`/`emissions` aliases, so these two cards work for every
                vertical while taking their titles and formatting from the config. */}
            <TrendCard
              title={content.trend.title}
              subtitle={content.trend.subtitle}
              accent="var(--primary)"
              points={trend}
              loading={trendLoading}
              variant="area"
              format={kpiMetas[0]?.format ?? ((n) => currency.format(n))}
              pick={(p) => p.spend}
            />
            {kpiMetas[1] && (
              <TrendCard
                title={`${kpiMetas[1].label} trend`}
                subtitle={`Monthly ${kpiMetas[1].label.toLowerCase()}`}
                accent="var(--chart-2)"
                points={trend}
                loading={trendLoading}
                variant="bar"
                format={kpiMetas[1].format}
                pick={(p) => p.emissions}
              />
            )}
          </section>
        )}

        {/* ── Quick access ─────────────────────────────────────────────── */}
        <section className="mt-8">
          <h2 className="mb-3 text-[13px] font-semibold uppercase tracking-[0.14em] text-muted-foreground">
            Jump back in
          </h2>
          {/* Derived from the registry (not hardcoded) so these always match the actual
              dashboards this instance serves, whatever the vertical. */}
          <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
            {quickCards.map((r) => (
              <QuickCard
                key={r.path}
                icon={(r.icon && ICON_MAP[r.icon]) || ICON_MAP.BarChart3}
                title={r.label}
                desc={`Explore ${r.label.toLowerCase()}.`}
                onClick={() => navigate(r.path)}
              />
            ))}
            <QuickCard
              icon={MessageCircle}
              title={`Ask ${brand.identity.shortName}`}
              desc="Full conversational analytics with history."
              onClick={() => navigate("/genie-mcp")}
            />
          </div>
        </section>
      </div>
    </div>
  );
}

// ─── KPI card ─────────────────────────────────────────────────────────────────

function KpiCard({
  meta,
  current,
  previous,
}: {
  meta: KpiMeta;
  current: number | null;
  previous: number | null;
}) {
  const Icon = meta.icon;
  const value = current != null ? meta.format(current) : "—";

  let deltaPct: number | null = null;
  if (current != null && previous != null && previous !== 0) {
    deltaPct = ((current - previous) / Math.abs(previous)) * 100;
  }

  return (
    <div className="group rounded-md border border-border bg-background p-4 transition-colors hover:border-neutral-200">
      <div className="flex items-center justify-between">
        <div
          className="flex h-9 w-9 items-center justify-center rounded bg-primary/10 text-primary"
        >
          <Icon size={17} />
        </div>
        <DeltaChip pct={deltaPct} goodDirection={meta.goodDirection} />
      </div>
      <div className="mt-3 text-2xl font-semibold tracking-tight text-foreground">{value}</div>
      <div className="mt-0.5 text-[12.5px] font-medium text-muted-foreground">{meta.label}</div>
    </div>
  );
}

function DeltaChip({
  pct,
  goodDirection,
}: {
  pct: number | null;
  goodDirection: "up" | "down" | "neutral";
}) {
  if (pct == null || !isFinite(pct)) return null;
  const up = pct >= 0;
  const rounded = Math.abs(pct) < 0.1 ? "0" : Math.abs(pct).toFixed(0);

  let tone = "bg-secondary text-muted-foreground"; // neutral
  if (goodDirection !== "neutral") {
    const good = goodDirection === "up" ? up : !up;
    tone = good
      ? "bg-[var(--background-success)] text-[var(--success)]"
      : "bg-[var(--background-danger)] text-[var(--destructive)]";
  }

  const Arrow = up ? TrendingUp : TrendingDown;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-[11px] font-semibold ${tone}`}
    >
      <Arrow size={12} />
      {rounded}%
    </span>
  );
}

function KpiSkeleton() {
  return (
    <div className="rounded-md border border-border bg-background p-4">
      <div className="h-9 w-9 animate-pulse rounded bg-muted" />
      <div className="mt-3 h-7 w-24 animate-pulse rounded bg-muted" />
      <div className="mt-2 h-3.5 w-16 animate-pulse rounded bg-muted" />
    </div>
  );
}

// ─── Trend card (inline SVG, no deps) ─────────────────────────────────────────

function monthLabel(m: string): string {
  // "2025-03" -> "Mar"
  const idx = Number(m.slice(5, 7)) - 1;
  const names = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  return names[idx] ?? m;
}

function TrendCard({
  title,
  subtitle,
  accent,
  points,
  loading,
  variant,
  format,
  pick,
}: {
  title: string;
  subtitle: string;
  accent: string;
  points: TrendPoint[] | null;
  loading: boolean;
  variant: "area" | "bar";
  format: (n: number) => string;
  pick: (p: TrendPoint) => number | null;
}) {
  const data = (points ?? [])
    .map((p) => ({ label: monthLabel(p.month), value: pick(p) }))
    .filter((d) => d.value != null && isFinite(d.value as number)) as {
    label: string;
    value: number;
  }[];

  const latest = data.length ? data[data.length - 1].value : null;

  return (
    <div className="rounded-md border border-border bg-background p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-[14px] font-semibold text-foreground">{title}</div>
          <div className="text-[12px] text-muted-foreground">{subtitle}</div>
        </div>
        {latest != null && (
          <div className="text-right">
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground">Latest</div>
            <div className="text-[15px] font-semibold text-foreground">{format(latest)}</div>
          </div>
        )}
      </div>

      <div className="mt-3 h-28">
        {loading ? (
          <div className="h-full w-full animate-pulse rounded bg-muted" />
        ) : data.length < 2 ? (
          <div className="flex h-full items-center justify-center text-[12px] text-muted-foreground">
            Not enough data
          </div>
        ) : variant === "area" ? (
          <AreaChart data={data} accent={accent} />
        ) : (
          <BarChart data={data} accent={accent} />
        )}
      </div>

      {data.length >= 2 && (
        <div className="mt-1.5 flex justify-between text-[10px] text-muted-foreground">
          <span>{data[0].label}</span>
          <span>{data[data.length - 1].label}</span>
        </div>
      )}
    </div>
  );
}

const CHART_W = 320;
const CHART_H = 96;

function AreaChart({
  data,
  accent,
}: {
  data: { label: string; value: number }[];
  accent: string;
}) {
  const max = Math.max(...data.map((d) => d.value));
  const min = Math.min(...data.map((d) => d.value), 0);
  const range = max - min || 1;
  const x = (i: number) => (i / (data.length - 1)) * CHART_W;
  const y = (v: number) => CHART_H - ((v - min) / range) * (CHART_H - 8) - 4;

  const line = data.map((d, i) => `${x(i)},${y(d.value)}`).join(" ");
  const area = `0,${CHART_H} ${line} ${CHART_W},${CHART_H}`;
  const gid = "prism-spend-grad";

  return (
    <svg
      viewBox={`0 0 ${CHART_W} ${CHART_H}`}
      preserveAspectRatio="none"
      className="h-full w-full"
    >
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={accent} stopOpacity="0.28" />
          <stop offset="100%" stopColor={accent} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polygon points={area} fill={`url(#${gid})`} />
      <polyline
        points={line}
        fill="none"
        stroke={accent}
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
      />
      {data.map((d, i) => (
        <circle key={i} cx={x(i)} cy={y(d.value)} r={2} fill={accent} />
      ))}
    </svg>
  );
}

function BarChart({
  data,
  accent,
}: {
  data: { label: string; value: number }[];
  accent: string;
}) {
  const max = Math.max(...data.map((d) => d.value)) || 1;
  const gap = 3;
  const bw = (CHART_W - gap * (data.length - 1)) / data.length;

  return (
    <svg viewBox={`0 0 ${CHART_W} ${CHART_H}`} className="h-full w-full">
      {data.map((d, i) => {
        const h = Math.max(2, (d.value / max) * (CHART_H - 6));
        return (
          <rect
            key={i}
            x={i * (bw + gap)}
            y={CHART_H - h}
            width={bw}
            height={h}
            rx={2}
            fill={accent}
            opacity={0.85}
          />
        );
      })}
    </svg>
  );
}

// ─── Quick-access card ────────────────────────────────────────────────────────

function QuickCard({
  icon: Icon,
  title,
  desc,
  onClick,
}: {
  icon: LucideIcon;
  title: string;
  desc: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group flex items-start gap-3.5 rounded-md border border-border bg-background p-4 text-left transition-colors hover:border-neutral-200"
    >
      <div
        className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-primary/10 text-primary"
      >
        <Icon size={19} />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <span className="text-[14px] font-semibold text-foreground">{title}</span>
          <ArrowRight
            size={14}
            className="text-muted-foreground transition-all group-hover:translate-x-0.5 group-hover:text-primary"
          />
        </div>
        <p className="mt-0.5 text-[12.5px] leading-relaxed text-muted-foreground">{desc}</p>
      </div>
    </button>
  );
}
