# Sarah Rapid-Fire Prism Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a validated Acme Travel data story, Genie ontology, Opportunity Brief, and synchronized three-to-four-minute demo script/blog outline that present Prism as a multi-tenant white-label experience built with Databricks Apps.

**Architecture:** Keep tenant identity and isolation unchanged. Encode the Acme narrative deterministically in the synthetic fact generator, expose its evidence through Unity Catalog metric-view measures, and configure the AI/BI dashboard plus Genie ontology to consume those same governed semantics. Reuse the existing Executive Summary/Genie MCP path for a decision-oriented Opportunity Brief, then document one timed story across the app and blog.

**Tech Stack:** Databricks SQL, Unity Catalog metric views (YAML), AI/BI dashboard JSON, Genie space/ontology JSON, FastAPI, React 19, TypeScript, Vitest, pytest.

## Global Constraints

- Keep `tenant_id="acme-travel"` as the Acme join key; do not add a user-to-tenant mapping.
- Do not change `server/tenants/resolver.resolve_tenant_sp(request)` or its app-SP fallback.
- Do not change the Unity Catalog row-filter function, authentication model, secret handling, or Lakebase fail-soft behavior.
- Present the 12% savings value as a modeled scenario, never guaranteed savings.
- Do not imply that earlier booking reduces carbon; connect emissions action to cabin-class policy.
- Use Databricks as the governed data/AI solution, Databricks Apps as Prism's interface, and the Genie ontology as its business-semantic layer.
- Keep the recording to one browser tab and three to four minutes.
- Do not add a transactional intervention workflow.
- Preserve unrelated worktree changes and commit only files named by each task.

## File Map

- `scripts/fevm/gen_travel_summarydataset.sql`: deterministic synthetic rows and Acme scenario.
- `scripts/fevm/validate_sarah_demo_story.sql`: executable acceptance queries for the narrative.
- `scripts/fevm/create_travel_metrics_fevm.sql`: FEVM metric-view dimensions and measures.
- `src/sql/create_travel_metrics.sql`: canonical metric-view definition kept semantically aligned.
- `src/sql/validate_travel_metrics.sql`: canonical measure cross-checks.
- `scripts/fevm/travel_genie_space.json`: Genie instructions, ontology terms, and sample questions.
- `scripts/fevm/travel_dashboard.json`: visual discovery path.
- `server/assets/dashboards.seed.json`: runtime Opportunity Brief prompt and Ask Prism suggestions.
- `tests/test_assets.py`: registry prompt/suggestion contract.
- `frontend/src/config.ts`: Opportunity Brief prompt formatter.
- `frontend/src/config.test.ts`: formatter contract.
- `frontend/src/components/ExecutiveSummaryModal.tsx`: Opportunity Brief presentation and copy interaction.
- `frontend/src/components/ExecutiveSummaryModal.test.tsx`: modal behavior.
- `frontend/src/App.tsx`: dashboard action label.
- `docs/demos/sarah-rapid-fire-demo-script.md`: timed narration and exact clicks.
- `docs/demos/sarah-companion-blog-outline.md`: synchronized article outline.
- `docs/demos/sarah-recording-checklist.md`: validation, warm-up, identity, and recording checks.

---

### Task 1: Deterministic Acme Data Story

**Files:**
- Modify: `scripts/fevm/gen_travel_summarydataset.sql`
- Create: `scripts/fevm/validate_sarah_demo_story.sql`

**Interfaces:**
- Consumes: existing `summarydataset` schema and `client_id='acme-travel'` isolation key.
- Produces: `booking_lead_band STRING`, deterministic Acme recent-period weighting, and raw columns usable by metric-view expressions; acceptance queries returning one row per assertion.

- [ ] **Step 1: Add a validation query that fails against the current uniform generator**

Create `scripts/fevm/validate_sarah_demo_story.sql` with a `periodized` CTE based on complete months:

```sql
WITH bounds AS (
  SELECT
    add_months(trunc(current_date(), 'MONTH'), -12) AS recent_start,
    trunc(current_date(), 'MONTH') AS recent_end,
    add_months(trunc(current_date(), 'MONTH'), -24) AS prior_start
), periodized AS (
  SELECT
    s.*,
    CASE
      WHEN travel_start_date >= recent_start AND travel_start_date < recent_end THEN 'recent'
      WHEN travel_start_date >= prior_start AND travel_start_date < recent_start THEN 'prior'
    END AS period
  FROM serverless_stable_71zsua_catalog.prism_travel.summarydataset s
  CROSS JOIN bounds
  WHERE travel_start_date >= prior_start AND travel_start_date < recent_end
)
SELECT
  client_id,
  SUM(CASE WHEN period = 'recent' THEN total_amount_gross END)
    / NULLIF(SUM(CASE WHEN period = 'prior' THEN total_amount_gross END), 0) - 1 AS spend_growth
FROM periodized
GROUP BY client_id
ORDER BY client_id;
```

Append queries for Acme recent-period Air share, London/Frankfurt share of intercontinental Air growth, `<14 days` late-booking spend share, offline spend share, business-class spend/emissions share, and 12% modeled savings. Add comment assertions: Acme growth `BETWEEN 0.17 AND 0.19`; every non-Acme tenant `< 0.10`; London plus Frankfurt is the largest destination driver.

- [ ] **Step 2: Run the baseline validation and capture the mismatch**

Run the file through the configured Databricks SQL warehouse.

Expected: current Acme growth and driver shares do not satisfy all acceptance bands. Save no generated output in the repository.

- [ ] **Step 3: Refactor generator CTEs to expose complete-period and scenario flags**

In `scripts/fevm/gen_travel_summarydataset.sql`, add derived values before the final `SELECT`:

```sql
CASE
  WHEN travel_start_date >= add_months(trunc(current_date(), 'MONTH'), -12)
   AND travel_start_date < trunc(current_date(), 'MONTH') THEN 'recent'
  WHEN travel_start_date >= add_months(trunc(current_date(), 'MONTH'), -24)
   AND travel_start_date < add_months(trunc(current_date(), 'MONTH'), -12) THEN 'prior'
  ELSE 'outside'
END AS comparison_period
```

Derive `is_acme_story_row` only when `client_id='acme-travel'`, `comparison_period='recent'`, `category='Air'`, and a deterministic hash bucket is selected. For selected rows, consistently set destination to London or Frankfurt, sector to `Inter-Continental`, lead time below 14 days, booking source to `Offline`, and increase the Air fare multiplier. Do not mutate rows for other tenants.

- [ ] **Step 4: Add the lead-time semantic column and documented savings assumption**

Project this expression as `booking_lead_band`:

```sql
CASE
  WHEN adv_booking_days < 7 THEN '0-6 days'
  WHEN adv_booking_days < 14 THEN '7-13 days'
  WHEN adv_booking_days < 30 THEN '14-29 days'
  ELSE '30+ days'
END AS booking_lead_band
```

Add a top-of-file comment defining modeled savings as `12% * late-booked intercontinental Air spend`; do not store a mutable savings number per row.

- [ ] **Step 5: Regenerate the FEVM table and rerun acceptance queries**

Run `scripts/fevm/gen_travel_summarydataset.sql`, then `scripts/fevm/validate_sarah_demo_story.sql`.

Expected: Acme recent complete-12-month growth is 17–19%; no other tenant receives the injected pattern; London/Frankfurt, short lead time, offline source, and business class visibly explain the Acme increase.

- [ ] **Step 6: Commit the data story**

```bash
git add scripts/fevm/gen_travel_summarydataset.sql scripts/fevm/validate_sarah_demo_story.sql
git commit -m "feat(data): anchor Acme travel demo narrative"
```

---

### Task 2: Governed Metric Semantics and Genie Ontology

**Files:**
- Modify: `scripts/fevm/create_travel_metrics_fevm.sql`
- Modify: `src/sql/create_travel_metrics.sql`
- Modify: `src/sql/validate_travel_metrics.sql`
- Modify: `scripts/fevm/travel_genie_space.json`

**Interfaces:**
- Consumes: `booking_lead_band`, `adv_booking_days`, category, sector, destination, source, class, amount, and emissions from Task 1.
- Produces: stable metric names `late_booking_rate`, `late_intercontinental_air_spend_usd`, `modeled_advance_purchase_savings_usd`, `business_class_spend_share`, and `business_class_emissions_share`; Genie ontology mapping business language to them.

- [ ] **Step 1: Add raw-versus-metric validation queries first**

Append to `src/sql/validate_travel_metrics.sql` a query for Acme's recent complete period:

```sql
SELECT
  MEASURE(`Late Booking Rate`) AS late_booking_rate,
  MEASURE(`Late Intercontinental Air Spend USD`) AS addressable_spend,
  MEASURE(`Modeled Advance Purchase Savings USD`) AS modeled_savings,
  MEASURE(`Business Class Spend Share`) AS business_class_spend_share,
  MEASURE(`Business Class Emissions Share`) AS business_class_emissions_share
FROM bcd_adv_workspace_poc.apex.travel_metrics
WHERE `Client ID` = 'acme-travel'
  AND `Travel Start Date` >= add_months(trunc(current_date(), 'MONTH'), -12)
  AND `Travel Start Date` < trunc(current_date(), 'MONTH');
```

Add a raw-table cross-check using `SUM(CASE WHEN ...)`, `COUNT_IF`, and `0.12 * SUM(...)` with the same filters.

- [ ] **Step 2: Run validation to verify the measures are absent**

Expected: metric query fails because the five measures do not exist; raw query succeeds after Task 1 deployment.

- [ ] **Step 3: Add identical semantic dimensions to both metric-view definitions**

Add `booking_lead_band` with synonyms `Lead Time Band`, `Advance Purchase Window`, and `Booking Window`. Extend `booking_source` synonyms with `Online Adoption` and `Offline Channel`. Extend `travel_details` synonyms with `City Pair` and `Route` while preserving existing entries.

- [ ] **Step 4: Add governed measures to both metric-view definitions**

Use these exact expressions and document their scopes:

```yaml
- name: late_booking_rate
  display_name: Late Booking Rate
  expr: "COUNT_IF(category = 'Air' AND adv_booking_days < 14) / NULLIF(COUNT_IF(category = 'Air'), 0)"
  comment: "Share of Air components booked fewer than 14 days before travel."

- name: late_intercontinental_air_spend_usd
  display_name: Late Intercontinental Air Spend USD
  expr: "SUM(CASE WHEN category = 'Air' AND travel_sector = 'Inter-Continental' AND adv_booking_days < 14 THEN currency_rate_usd * total_amount_gross ELSE 0 END)"
  comment: "Addressable Air spend booked fewer than 14 days before intercontinental travel."

- name: modeled_advance_purchase_savings_usd
  display_name: Modeled Advance Purchase Savings USD
  expr: "0.12 * MEASURE(late_intercontinental_air_spend_usd)"
  comment: "Scenario equal to 12% of late intercontinental Air spend; not guaranteed savings."
```

Add share measures as conditional spend/emissions divided by total Air spend/emissions with `NULLIF` protection. Apply percent formats to rates/shares and compact USD formatting to spend/savings.

- [ ] **Step 5: Deploy the FEVM metric view and run both validation suites**

Run `scripts/fevm/create_travel_metrics_fevm.sql`, `scripts/fevm/validate_sarah_demo_story.sql`, and the FEVM-adjusted metric validation queries.

Expected: raw and metric outputs agree within normal decimal precision; modeled savings equals addressable spend multiplied by `0.12`.

- [ ] **Step 6: Encode the Genie ontology in the space configuration**

Update `scripts/fevm/travel_genie_space.json` description/instructions and serialized config so it explicitly defines:

```text
Late booking means an Air component booked fewer than 14 days before travel.
Advance-purchase opportunity means 12% of late intercontinental Air spend and is a modeled scenario, not guaranteed savings.
Offline adoption refers to Booking Source = Offline; online adoption refers to Booking Source = Online.
For emissions recommendations, discuss cabin-class mix; do not claim that earlier booking directly reduces CO2.
Use complete-month comparisons and metric-view measures whenever available.
```

Add synonyms/examples for `late booking`, `short lead time`, `advance purchase`, `offline channel`, `city pair`, and `carbon impact`. Make the lead sample question: `What is driving Acme Travel's spend increase, and what action should its travel manager take?`

- [ ] **Step 7: Provision the updated Genie space and verify representative questions**

Use `scripts/deploy/provision_genie.py` with the configured FEVM profile. Verify the lead question plus: `How much late intercontinental Air spend is addressable under the 12% scenario?` and `What is the business-class carbon impact?`

Expected: answers use the named measures, state units, label savings as modeled, and separate cost from emissions recommendations.

- [ ] **Step 8: Commit governed semantics and ontology**

```bash
git add scripts/fevm/create_travel_metrics_fevm.sql src/sql/create_travel_metrics.sql src/sql/validate_travel_metrics.sql scripts/fevm/travel_genie_space.json
git commit -m "feat(genie): add travel opportunity ontology"
```

---

### Task 3: Story-Aligned Dashboard and Runtime Prompts

**Files:**
- Modify: `scripts/fevm/travel_dashboard.json`
- Modify: `server/assets/dashboards.seed.json`
- Modify: `tests/test_assets.py`

**Interfaces:**
- Consumes: Task 2 metric names and the existing `spend` page ID/dashboard ID.
- Produces: a dashboard discovery sequence and one runtime prompt contract shared by Ask Prism and Opportunity Brief.

- [ ] **Step 1: Strengthen the asset test before changing prompts**

Add this test to `tests/test_assets.py`:

```python
def test_spend_asset_supports_acme_opportunity_story():
    page = assets.load_registry()["assets"]["spend"]["pages"][0]
    prompt = page["summaryPrompt"].lower()
    assert "modeled" in prompt
    assert "12%" in prompt
    assert "late" in prompt
    assert "business class" in prompt
    assert page["suggestions"][0] == (
        "What is driving Acme Travel's spend increase, and what action should its travel manager take?"
    )
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `pytest tests/test_assets.py::test_spend_asset_supports_acme_opportunity_story -v`

Expected: FAIL because current prompt/suggestions cover generic spend.

- [ ] **Step 3: Update the runtime prompt and suggestions**

Set the Spend page summary prompt to request the headline, evidence, recommendation, and modeled impact using governed measures. Require the response to label 12% as a scenario and separate emissions recommendations. Use these suggestions:

```json
[
  "What is driving Acme Travel's spend increase, and what action should its travel manager take?",
  "How much late intercontinental Air spend is addressable under the 12% scenario?",
  "How do business-class bookings affect spend and emissions?"
]
```

- [ ] **Step 4: Add dashboard evidence for the discovery path**

Update `scripts/fevm/travel_dashboard.json` datasets to expose booking lead band, booking source, destination city, travel class, late-booking rate, addressable spend, modeled savings, and business-class shares. Preserve existing page/filter IDs required by embedding. Add or retarget widgets so the Spend page includes:

- spend trend by complete month;
- spend/growth by category;
- intercontinental Air spend by destination city;
- spend split by lead-time band and booking source;
- counters for addressable spend and modeled savings.

- [ ] **Step 5: Run registry tests and validate dashboard JSON**

Run: `pytest tests/test_assets.py -v`

Run: `python -m json.tool scripts/fevm/travel_dashboard.json`

Expected: PASS and valid JSON.

- [ ] **Step 6: Provision, publish, and smoke-test the dashboard**

Use `scripts/deploy/provision_dashboard.py` with the configured FEVM profile. Confirm the published dashboard keeps `embed_credentials=false`, its ID/page IDs still match the runtime registry, Acme filters show the validated figures, and external embedding still loads.

- [ ] **Step 7: Commit dashboard and prompt changes**

```bash
git add scripts/fevm/travel_dashboard.json server/assets/dashboards.seed.json tests/test_assets.py
git commit -m "feat(demo): align dashboard with Acme opportunity story"
```

---

### Task 4: Opportunity Brief Interaction

**Files:**
- Modify: `frontend/src/config.ts`
- Modify: `frontend/src/config.test.ts`
- Modify: `frontend/src/components/ExecutiveSummaryModal.tsx`
- Create: `frontend/src/components/ExecutiveSummaryModal.test.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `summaryPrompt` and existing `useGenieMcpChat("multi")` result.
- Produces: `buildOpportunityBriefPrompt(summaryPrompt: string): string`, an Opportunity Brief modal, and copy-to-clipboard status.

- [ ] **Step 1: Write the failing prompt-format test**

Extend `frontend/src/config.test.ts`:

```ts
import { buildOpportunityBriefPrompt } from "./config";

it("formats a four-part opportunity brief without unsupported execution claims", () => {
  const prompt = buildOpportunityBriefPrompt("Use governed Acme measures.");
  expect(prompt).toContain("## Headline");
  expect(prompt).toContain("## Evidence and drivers");
  expect(prompt).toContain("## Recommended action");
  expect(prompt).toContain("## Modeled impact");
  expect(prompt).toContain("scenario, not guaranteed savings");
  expect(prompt).not.toContain("create a campaign");
});
```

- [ ] **Step 2: Run the focused test and verify failure**

Run: `cd frontend && npm test -- --run src/config.test.ts`

Expected: FAIL because `buildOpportunityBriefPrompt` is not exported.

- [ ] **Step 3: Implement the formatter and retain a compatibility alias**

Replace the three-section formatter with `buildOpportunityBriefPrompt`. Require exactly the four approved headings, specific governed figures, explicit units, and the savings disclaimer. Keep `buildExecSummaryPrompt` as an alias during this change if any existing imports remain, then migrate the modal import.

- [ ] **Step 4: Write failing modal tests for title and copy states**

Mock `useGenieMcpChat` and `navigator.clipboard.writeText`. Assert:

```tsx
expect(screen.getByRole("heading", { name: "Opportunity Brief" })).toBeInTheDocument();
await user.click(screen.getByRole("button", { name: "Copy brief" }));
expect(navigator.clipboard.writeText).toHaveBeenCalledWith("## Headline\nAcme opportunity");
expect(screen.getByText("Copied")).toBeInTheDocument();
```

Add a rejection test that shows `Could not copy` while leaving brief content visible.

- [ ] **Step 5: Run modal tests and verify failure**

Run: `cd frontend && npm test -- --run src/components/ExecutiveSummaryModal.test.tsx`

Expected: FAIL because the existing modal is titled Executive Summary and has no copy action.

- [ ] **Step 6: Implement Opportunity Brief presentation**

In `ExecutiveSummaryModal.tsx`, change user-facing summary strings to Opportunity Brief, call `buildOpportunityBriefPrompt`, import `Copy`/`Check`, and add local state:

```ts
const [copyState, setCopyState] = useState<"idle" | "copied" | "error">("idle");

const copyBrief = async () => {
  if (!assistant?.content) return;
  try {
    await navigator.clipboard.writeText(assistant.content);
    setCopyState("copied");
  } catch {
    setCopyState("error");
  }
};
```

Disable copying until content exists. Render accessible button labels `Copy brief`, `Copied`, and `Could not copy`. Do not remove regenerate, SQL, table, deep-link, streaming, Escape, or soft-error behavior.

- [ ] **Step 7: Change the dashboard toolbar label**

In `frontend/src/App.tsx`, change only the visible action text from `Executive Summary` to `Opportunity Brief`; preserve state wiring and the `Sparkles` icon.

- [ ] **Step 8: Run focused and full frontend verification**

Run: `cd frontend && npm test -- --run src/config.test.ts src/components/ExecutiveSummaryModal.test.tsx`

Run: `cd frontend && npm test`

Run: `cd frontend && npm run build`

Expected: all tests pass and TypeScript/Vite build succeeds.

- [ ] **Step 9: Commit the Opportunity Brief**

```bash
git add frontend/src/config.ts frontend/src/config.test.ts frontend/src/components/ExecutiveSummaryModal.tsx frontend/src/components/ExecutiveSummaryModal.test.tsx frontend/src/App.tsx
git commit -m "feat(ui): turn summaries into opportunity briefs"
```

---

### Task 5: Timed Script, Companion Blog, and Recording Checklist

**Files:**
- Create: `docs/demos/sarah-rapid-fire-demo-script.md`
- Create: `docs/demos/sarah-companion-blog-outline.md`
- Create: `docs/demos/sarah-recording-checklist.md`
- Modify: `docs/demos/run-of-show.md`

**Interfaces:**
- Consumes: validated figures from Tasks 1–3 and final UI labels from Task 4.
- Produces: the recording source of truth and a blog outline with the same claims.

- [ ] **Step 1: Write the script with timed rows and exact interactions**

Use a table with columns `Time`, `Screen/action`, `Narration`, and `Evidence expected`. Begin with:

```text
A travel management company serves many corporate customers, each with travel data spread
across suppliers and systems. It wants to give every customer useful insights without
building and securing a separate analytics product each time.
```

Then identify Databricks as the governed solution, Prism on Databricks Apps as the branded
interface, Acme as the tenant shown, and the Genie ontology as the travel-business vocabulary
behind Ask Prism. Include exact dashboard filters/question, the Opportunity Brief click/copy,
and a closing line that moves from governed data to a decision-ready plan.

- [ ] **Step 2: Insert validated figures only after querying the deployed assets**

Run `scripts/fevm/validate_sarah_demo_story.sql` and the metric-view acceptance query. Replace
script evidence with those exact rounded values. Do not copy the target 18% or savings amount
without validation.

- [ ] **Step 3: Write the companion blog outline**

Use sections: travel-management-company problem; one branded experience per corporate
customer; Databricks foundation; Databricks Apps interface; governed AI/BI discovery; Genie
ontology and natural-language explanation; Opportunity Brief outcome; architecture sidebar;
and reference-app call to action. Label Acme and all data as fictional.

- [ ] **Step 4: Write the recording checklist**

Include: Acme login/tenant identity; app-SP fallback not used; dashboard page and filter IDs;
Acme-only figures; Genie answers warmed and ontology verified; Opportunity Brief copy tested;
single tab; notifications hidden; 1080p capture; MP4 output; three-to-four-minute stopwatch;
and fallback narration if Genie is slow.

- [ ] **Step 5: Link the rapid-fire script from the existing run-of-show**

Add a short `Sarah rapid-fire cut` note near the top of `docs/demos/run-of-show.md` linking to
the new script. Keep the existing longer internal multi-vertical run-of-show unchanged.

- [ ] **Step 6: Run documentation consistency checks**

Run:

```bash
rg -n "Executive Summary|guaranteed savings|earlier booking.*emissions|BCD" docs/demos/sarah-*.md
rg -n "Databricks Apps|Genie ontology|Acme Travel|multi-tenant|white-label|12%" docs/demos/sarah-*.md
```

Expected: no stale Executive Summary label, guarantee claim, earlier-booking carbon claim, or real-customer framing; all required product and tenant concepts appear.

- [ ] **Step 7: Commit the recording package**

```bash
git add docs/demos/sarah-rapid-fire-demo-script.md docs/demos/sarah-companion-blog-outline.md docs/demos/sarah-recording-checklist.md docs/demos/run-of-show.md
git commit -m "docs(demo): add Sarah rapid-fire recording package"
```

---

### Task 6: End-to-End Acceptance

**Files:**
- Modify only if a failing acceptance check requires a scoped correction to files from Tasks 1–5.

**Interfaces:**
- Consumes: all prior task outputs.
- Produces: a release-ready demo state with reproducible evidence.

- [ ] **Step 1: Run the repository test suites**

Run: `pytest -q`

Run: `cd frontend && npm test`

Run: `cd frontend && npm run build`

Expected: all tests pass and the production frontend builds.

- [ ] **Step 2: Re-run Databricks data and ontology acceptance**

Run the synthetic-story and metric-view validation files. Ask the three verified Genie
questions from Task 2. Confirm dashboard, Genie, and Opportunity Brief agree on rounded
figures, units, period, and scenario language.

- [ ] **Step 3: Verify tenant isolation without changing it**

Run the existing tenant verification tooling for Acme and the operator identity. Confirm
Acme sees only `client_id='acme-travel'`; operator/app-SP fallback remains functional.

- [ ] **Step 4: Perform a timed one-tab dry run**

Follow `docs/demos/sarah-rapid-fire-demo-script.md` without improvising navigation.

Expected: 3:00–4:00 total; no second tab; no cold dashboard/Genie wait longer than the
documented recovery line; Opportunity Brief is copied successfully.

- [ ] **Step 5: Record final acceptance evidence**

Add a dated results section to `docs/demos/sarah-recording-checklist.md` containing test
counts, frontend build result, validated demo figures, Genie question status, tenant check,
and dry-run duration.

- [ ] **Step 6: Commit acceptance evidence if the checklist changed**

```bash
git add docs/demos/sarah-recording-checklist.md
git commit -m "test(demo): record rapid-fire acceptance results"
```
