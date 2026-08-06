# Prism — Internal Demo Run of Show (2026-08-06)

**Arc:** Tell → Show → Tell → Show. Slides carry the Tells; the app carries the Shows.

## Before you start

```bash
cd ~/Documents/github/advito-ai-bi
./demo/run-all.sh          # starts all three; refuses to start if a port is busy
./demo/run-all.sh stop     # when you're done
```

Open three tabs, logged in ahead of time so nothing loads cold on stage:

| Tab | URL | Login |
|-----|-----|-------|
| 1 | http://localhost:8000 | `dana@prism.example` / `apex` (Operator toggle) |
| 2 | http://localhost:8001 | `dana@prism.example` / `apex` |
| 3 | http://localhost:8002 | `dana@prism.example` / `apex` |

**Warm every dashboard page once** (click Sales & Margin, Performance, etc.) — the FEVM
warehouse is serverless and the first query per dashboard takes ~10-20s. After warming,
they render in about a second.

Also open a 4th tab on `localhost:8000` logged in as `alice@acmetravel.com` / `apex` for
the isolation beat, so you don't have to log out mid-demo.

---

## TELL 1 — The primitives are best-in-class, and they're embeddable (~3 min)

The three points, in order:

1. **Genie / Genie One** is best-in-class natural-language analytics.
2. **AI/BI Dashboards** are best-in-class dashboarding.
3. The part people miss: **all of it is available for embedding, over MCP, and to AI
   agents.** These aren't console features, they're building blocks.

Then set up the contrast that carries the whole demo:

> "You *can* build analytics inside a custom app. But then every new chart is a code
> change, a PR, a deploy. Change management eats you alive. Embedding AI/BI inverts that:
> your analysts publish dashboards, and the app just picks them up."

---

## SHOW 1 — Travel Intelligence, the BCD story (~8 min) · **Tab 1, :8000**

Frame it first: *BCD Travel / Advito want to give **their** customers a white-label travel
analytics platform, replacing QuickSight.*

Beats, in order:

1. **Home** — real numbers off Databricks: $216M spend, 75K tCO₂e, 4K travelers, 97K
   trips, with trends. Note this is a metric view, so the numbers are governed and
   consistent everywhere.
2. **Ask Prism** (sidebar) — natural language, streaming, grounded in live SQL. Genie over
   MCP. *"Natural-language analytics is a first-class citizen here, not a bolt-on."*
3. **A dashboard page** (Spend or Network) — the money shot. Point out what's **absent**:
   no Databricks logo, no console links, no page headers, no "Powered by Databricks". It
   looks like BCD's product because it is BCD's product.
4. **Filter passthrough** — change a filter in the app's own UI, watch it drive the
   embedded dashboard widgets. This was the #1 gap vs QuickSight.
5. **Saved / managed filters** (My Filters) — user-level state the app owns, not Databricks.
6. **Row-level security** — switch to **Tab 4 (Alice)**. Same app, same dashboard, same
   code path: **$85.5M instead of $216M.** Enforced by a Unity Catalog row filter against
   a per-tenant Service Principal — not app-side WHERE clauses that a bug could leak past.
   *"Isolation is enforced by the platform, below the app."*
7. **Admin** (bottom of sidebar) — Service Principal management and asset management. Show
   the tenant registry and the asset editor: dashboards, Genie spaces, pages and prompts
   are all editable **from the UI, with no redeploy.**

**Land the impact:** BCD plans to serve this to **10,000+ of their customers.**

---

## TELL 2 — "But wait. This isn't a BCD project. It's a platform." (~2 min)

The pivot, and the most important slide of the deck:

- What you just saw isn't a one-off build for one customer.
- **Look and feel is a config file.** No redeploy.
- **Dashboards, Genie spaces, pages, prompts are managed in the admin UI.** No redeploy.
- Therefore: *any* company that needs to share analytics with **its** customers or
  partners can be stood up on this.

---

## SHOW 2 — The same platform, two more industries (~5 min)

**Tab 2, :8001 — Meridian Retail · Vendor Portal.** A retailer sharing performance data
externally with its vendors. Different brand, different color, different nav (Sales &
Margin, Inventory & Promo), different KPIs ($35.7M Net Sales, $12.6M Gross Margin, 444.9K
Units, 81.8K Transactions), different suggested questions, its own embedded dashboard with
its own filters.

**Tab 3, :8002 — Cascade Hotels · Owner Portal.** A hotel group sharing performance with
its property owners. $148M revenue, $365 ADR, 302K rooms sold, 87K reservations.

Then the line that ties it together:

> "Same build. Same server. Same container. The only difference between these three is
> configuration."

### The live re-skin (your closer — do this one, it lands)

```bash
# In a terminal, edit either file and just refresh the browser. No restart. No rebuild.
code demo/brands/retail.json      # change appName / accent
code demo/content/retail.json     # change hero title / KPI labels
```

Change `appName` to something in the room — a colleague's account name works well — save,
refresh tab 2. The app is now that company's product. **No build step. No deploy.**

*This is the proof of the whole thesis. Don't skip it.*

---

## CLOSE — the teaser (~1 min)

> "One more thing: you can also deploy this publicly and hand a customer a URL to a demo
> you built on Databricks. Come talk to me after the session."

**Do not click into anything public.** The Render deploy is still blocked by FEVM's
workspace IP ACL — the shell loads but embeds and Genie fail. Slide only.

---

## Honesty notes — where NOT to click

Read these once; they're the difference between a clean demo and an awkward pause.

- **Isolation: use Alice, not Ben.** Only `acme-travel` has a dedicated Service Principal.
  `ben@globex.com` has no SP, so he falls back to the app SP and would see **all** clients
  — which looks like a privacy bug on stage. Alice ($85.5M vs $216M) is the correct
  contrast. Initech and Umbrella also have data but no SPs.
- **Isolation is Travel-only.** Retail and Hospitality have `client_id` columns but no row
  filter attached. If asked, say: "same mechanism, wired per vertical" — that's accurate.
- **Ask on :8001 / :8002 answers Travel questions.** Neither Retail nor Hospitality has a
  Genie space yet, so both fall back to the Travel space from `.env`. **Demo Ask on Tab 1
  only.** If you want it on the others, create the two spaces and set `GENIE_SPACE_ID` in
  `demo/envs/{retail,hotel}.env`.
- **Warehouse cold starts.** First hit on any dashboard is ~10-20s. Warm all pages before
  you present.
- **Free-tier dashboard data recency.** The Retail dashboard's KPI tiles show a single
  recent day (e.g. "$306K") rather than the annual total — the dashboard's own date
  defaults, not an app bug. The app's Home KPIs show the full year.

## What I changed in the workspace (so you're not surprised)

- Granted the app SPs `CAN_RUN` on the **Retail** and **Hospitality** dashboards. They had
  no SP grant at all, so embed token exchange failed with `RESOURCE_DOES_NOT_EXIST`.
- Attached the row filter to `prism_travel.summarydataset`
  (`ALTER TABLE … SET ROW FILTER tenant_row_filter ON (client_id)`). It had been created
  but never attached, so RLS was a no-op.
- Extended `tenant_row_filter` to honor a `*` wildcard tenant, and registered the app SP
  with `tenant_id='*'`. Without this the operator view returned all nulls once the filter
  was attached.
