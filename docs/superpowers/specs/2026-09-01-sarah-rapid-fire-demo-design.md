# Sarah Rapid-Fire Demo — Design

**Date:** 2026-09-01  
**Status:** Approved design; self-reviewed; awaiting written-spec review  
**Audience:** Databricks YouTube, LinkedIn, resource pages, and databricks.com readers

## Goal

Create a three-to-four-minute, single-browser-tab demonstration of Prism Analytics using
the fictional Acme Travel tenant. The demo will show how a secure white-label embedded
experience unifies fragmented corporate-travel data, helps nontechnical travel managers
understand it, and turns a governed finding into a decision-ready action plan.

The companion blog will use the same problem, evidence, and outcome so the recording and
article reinforce one another.

## Narrative

The video follows Sarah's requested structure: problem, generic solution, and high-level
product demonstration.

1. Corporate-travel data is fragmented across air, hotel, rail, car, rideshare, suppliers,
   spend, and emissions systems.
2. Prism Analytics embeds Databricks AI/BI and Genie inside Acme's own branded experience,
   while a per-tenant Service Principal and Unity Catalog row filter enforce isolation.
3. Acme's governed KPIs reveal rising spend and emissions.
4. The embedded Spend dashboard identifies the main driver.
5. Ask Prism explains that driver in plain language for a nontechnical travel manager.
6. An Opportunity Brief converts the finding into a recommended action and modeled impact.

The security and white-label architecture receives a short introduction rather than a
technical walkthrough. The business problem and user experience remain the focus.

## Anchored Acme Data Story

The synthetic generator will create a deterministic, Acme-only recent-period signal:

- Corporate-travel spend in the latest complete 12-month period increases between 17% and
  19% compared with the preceding 12 complete months.
- The increase is concentrated in intercontinental air bookings to London and Frankfurt.
- Bookings made fewer than 14 days before departure and offline bookings account for a
  disproportionate share of the increase.
- Business-class travel magnifies both cost and carbon emissions.
- Earlier booking and greater online-channel adoption produce a measurable savings
  opportunity. A separate class-policy recommendation addresses emissions without claiming
  that earlier booking alone reduces carbon.

The demo script will use the generated, validated results rather than rounding the target
into a hardcoded claim.

Other fictional tenants remain realistic but do not receive Acme's deliberate trend. The
tenant key remains `acme-travel`; the generator does not change identity mappings or row
isolation.

## Governed Measures

The travel fact table and metric view will expose enough governed evidence for the
dashboard, Genie, and Opportunity Brief to agree. The implementation will add or derive:

- booking lead-time band, including a `<14 days` late-booking segment;
- online versus offline booking channel;
- intercontinental route and destination dimensions;
- late-booked air spend;
- late-booking rate;
- addressable late-booked air spend;
- modeled savings equal to 12% of late-booked intercontinental Air spend, presented as a
  scenario rather than guaranteed savings;
- business-class spend and emissions share.

The savings assumption will be explicit in data-generation and metric documentation. Genie
will use metric-view measures rather than estimating values in prose.

## Dashboard and Genie Experience

The Spend dashboard will preserve the existing white-label embedding and filter behavior.
Its visible charts, suggested questions, and page prompt will support the discovery path:

1. identify Air as the spend-growth driver;
2. narrow to intercontinental travel and Europe;
3. surface London and Frankfurt;
4. connect the increase to short lead times, offline bookings, and business class;
5. quantify the addressable savings opportunity.

The preferred Ask Prism question will ask what is driving Acme's increase and what action
the travel manager should take. The answer must cite governed figures and distinguish cost
actions from emissions actions.

## Opportunity Brief

The existing Executive Summary flow will be evolved into a decision-oriented Opportunity
Brief rather than creating a separate agent or workflow. It will continue to use the managed
Genie MCP path and the current dashboard context.

The response format is fixed:

1. **Headline** — the principal business finding.
2. **Evidence and drivers** — specific governed figures supporting it.
3. **Recommended action** — an operationally credible response.
4. **Modeled impact** — the calculated savings opportunity and any separately supported
   emissions implication.

The modal retains regeneration, SQL/result disclosure, and existing soft error behavior. A
copy-to-clipboard action provides a small but tangible closing interaction. It does not claim
to create campaigns, modify travel policy, or write into an external operational system.

## Demo Script and Blog Alignment

The timed script will include exact clicks, narration, expected evidence, transition lines,
and a recovery note for slow Genie responses. Target timing:

- 0:00–0:25 — fragmented-data problem;
- 0:25–0:45 — Prism white-label, embedded, governed introduction;
- 0:45–1:25 — Acme KPI overview;
- 1:25–2:15 — embedded dashboard discovery;
- 2:15–3:05 — Ask Prism explanation;
- 3:05–3:40 — Opportunity Brief and close.

The blog outline will mirror those six beats while allowing modest additional technical
context about AI/BI embedding, Genie MCP, Service Principals, and Unity Catalog isolation.
The article remains outcome-led and links readers to the reference implementation for the
deep technical details.

## Files and Boundaries

Expected implementation surfaces:

- `scripts/fevm/gen_travel_summarydataset.sql` — deterministic Acme scenario;
- `scripts/fevm/create_travel_metrics_fevm.sql` and the canonical metric-view SQL — new
  governed dimensions and measures;
- `scripts/fevm/travel_dashboard.json` — story-aligned dashboard widgets;
- `scripts/fevm/travel_genie_space.json` — instructions and sample questions;
- `server/assets/dashboards.seed.json` — page prompt and suggestions;
- `frontend/src/components/ExecutiveSummaryModal.tsx` and prompt construction — Opportunity
  Brief presentation and copy action;
- focused frontend/backend validation tests;
- `docs/demos/` — Sarah script, blog outline, and recording checklist.

The implementation will not alter the tenant-resolution seam, Service Principal fallback,
row-filter function, authentication model, secret handling, or Lakebase fail-soft behavior.
It will not add a transactional intervention workflow.

## Error Handling and Demo Resilience

- Dashboard and Genie failures keep their current visible, non-destructive error states.
- Opportunity Brief generation failure does not obscure or invalidate the dashboard.
- Clipboard failure displays a local UI failure state and does not affect the generated brief.
- Missing new measures fail validation before recording rather than silently producing a
  scripted claim.
- The recording checklist requires dashboard and Genie warm-up and confirmation that the
  logged-in Acme identity sees only Acme rows.

## Validation

Validation will cover:

- deterministic regeneration and expected Acme-only trend;
- no equivalent injected spike for other tenants;
- agreement among fact-table queries, metric-view measures, dashboard values, and Genie;
- explicit checks for spend growth, destination concentration, late-booking rate,
  addressable spend, modeled savings, and business-class emissions share;
- existing asset-registry and tenant-isolation tests;
- Opportunity Brief rendering, regeneration, copy success/failure, streaming, and Genie
  error states;
- frontend unit tests and production build;
- a timed dry run of the final script in one browser tab.

## Success Criteria

The work is complete when a viewer can follow one consistent Acme story from KPI to
dashboard to natural-language explanation to Opportunity Brief in under four minutes; every
spoken number is reproducible from governed synthetic data; Prism is clearly presented as a
secure white-label embedded experience; and the blog outline tells the same story without
depending on unsupported product claims.
