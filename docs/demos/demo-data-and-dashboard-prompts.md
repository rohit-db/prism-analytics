# Prism Demo — Data-Generation & Dashboard-Build Prompts

Copy-paste-ready prompts for standing up a new Prism demo vertical: synthetic data → metric view → AI/BI dashboard → Genie space. Each vertical mirrors the same **KPI-tiles + dashboard + Genie-chat** shape so it drops into Prism with only the documented config/code seams changed (see the README "Spin up a new demo" table).

**Target workspace (FEVM):** `https://fevm-serverless-stable-71zsua.cloud.databricks.com` (AWS us-east-2, serverless).

**Conventions for every vertical**
- One **raw fact table** per vertical (`<catalog>.<schema>.<fact>`), one row per transaction/booking/movement.
- A **`client_id` / `client_name`** column on every fact table — this is Prism's tenant key (row-level isolation joins on it). Generate 3–5 fictional clients per vertical.
- A UC **metric view** (`WITH METRICS LANGUAGE YAML`) on top of the fact table — this is what the dashboard + Genie both read.
- Date ranges: **Jan 2024 → present**, so YoY and trailing-12-month comparisons work.
- Realistic skew (Pareto vendors/SKUs, seasonal curves, weekday/weekend patterns) — flat uniform data reads as fake in a demo.

---

## 1. Travel Intelligence — REFERENCE (grounded in the real BCD schema)

> This mirrors the production `bcd_adv_workspace_poc.apex.travel_metrics` metric view, which sits on raw table `…test.summarydataset`. Reproduce that schema so the existing metric-view YAML and dashboard port with zero changes.

### 1a. Data-generation prompt

```
Generate a synthetic corporate-travel fact table `<catalog>.<schema>.summarydataset`
for a Prism "Travel Intelligence" demo. One row per travel component (booking).
~250,000 rows spanning 2024-01-01 to today.

CATEGORIES (column `category`): Air, Hotel, Rail, Car, Taxi/Rideshare — weight
roughly Air 45%, Hotel 30%, Car 10%, Rail 8%, Taxi/Rideshare 7%.

CLIENTS (tenant key): 4 fictional clients — client_id/client_name pairs:
  acme-travel/"Acme Travel", globex/"Globex", initech/"Initech", umbrella/"Umbrella Corp".
Distribute rows ~40/30/20/10.

COLUMNS (match these names/types exactly — the metric view depends on them):
- invoice_date DATE, travel_start_date DATE, travel_end_date DATE
- report_travel_year INT, report_invoice_year INT  (year of the respective date)
- origin_city, destination_city STRING; origin_country_name, destination_country STRING
- destination_country_region STRING (continent/sub-region: North America, Europe, Asia Pacific, LATAM, Middle East & Africa)
- traveler_country STRING (point-of-sale country)
- hotel_property_city STRING (null for non-hotel), travel_sector STRING
  (one of: Intra-Country, Intra-Continental, Inter-Continental — derive from origin/destination)
- travel_class STRING (Air: Economy/Premium Economy/Business/First; Hotel: Budget/Midscale/Upscale/Luxury; Car: Economy/Compact/Standard/Premium)
- vendor STRING (airline/hotel-chain/rental-co/rail-operator — use a Pareto set: ~8 airlines carry 70% of air rows, e.g. United, Delta, American, Lufthansa, BA, Emirates, Air France, ANA)
- travel_details STRING (Air/Rail: "JFK-LHR" city-pair; Hotel: property name; Car/Taxi: expense detail)
- air_carrier_code STRING (2-letter IATA for Air rows, else null)
- hotel_eco_certified BOOLEAN (null for non-hotel; ~35% of hotel rows true)
- booking_source STRING (Online / Offline — ~65% Online)
- employee_id STRING (pool of ~4,000 travelers across clients; repeat so traveler_count is meaningful)
- budget_field STRING, budget_field_value STRING (carbon-budget dimension, e.g. "Business Unit" / "Sales")
- total_amount_gross DECIMAL(12,2) (in local currency)
- currency_rate_usd, currency_rate_eur, currency_rate_gbp DECIMAL(10,6) (conversion rates)
- co2_emissions_advito, co2_emissions_defra, co2_emissions_advito_wo_rf, co2_emissions_defra_wo_rf DECIMAL(12,3) (kgCO2e; advito ~10-15% higher than defra due to radiative forcing)
- co2_emission_budget DECIMAL(12,3) (allocated kgCO2e for the row's budget scope; sum should exceed actuals ~15%)
- component_count INT (1 per row), air_net_segment_count, air_od_segment_count INT (Air only), hotel_nights INT (Hotel only), car_rental_days INT (Car only), rail_segment_count INT (Rail only)
- distance_km DECIMAL(10,1) (great-circle for Air/Rail; 0/null for Hotel)
- adv_booking_days INT (days between invoice_date and travel_start_date; skew: leisure-ish long lead for some, last-minute for business)

REALISM:
- Emissions must correlate with distance & class (Business ≈ 2-3× Economy per km; long-haul Air dominates total CO2).
- Spend correlates with class + distance + category (Air Business long-haul highest ticket; Taxi lowest).
- Seasonal curve: summer + Q4 peaks, January trough.
- Air distance_km: short-haul 300-1500, long-haul 4000-12000.
Write it as a Spark/SQL generation notebook; create the table managed in UC.
```

### 1b. Metric view

Reuse the committed YAML verbatim: `src/sql/create_travel_metrics.sql` (just repoint the `source:` and view name to your FEVM catalog/schema). Key measures already defined there: `gross_spend_usd`, `total_emissions_advito`, `component_count`, `traveler_count`, `hotel_nights`, `flight_count`, `emissions_per_km`, `co2_budget`, `budget_remaining`, `avg_advance_booking_days`. Key dimensions: `category`, `travel_class`, `vendor`, `destination_region`, `travel_sector`, `travel_month`, `client_name`.

### 1c. Dashboard prompt

```
Build an AI/BI dashboard "Travel Intelligence" on metric view <catalog>.<schema>.travel_metrics.
Two pages:
PAGE "Spend": KPI row (Gross Spend USD, Component Count, Traveler Count, Avg Advance Booking Days);
  line chart Gross Spend USD by travel_month; bar Spend by category; bar Top 10 vendor by spend;
  map/bar Spend by destination_region; table by travel_class.
PAGE "Sustainability": KPI row (Total Emissions Advito tCO2e, Emissions per KM, CO2 Budget, Budget Remaining);
  line Emissions by travel_month vs CO2 Budget; bar Emissions by category; bar Emissions by destination_region;
  scatter Emissions per KM by travel_class; % eco-certified hotel nights.
All widgets filterable by client_name, category, travel_month, destination_region, travel_sector.
Publish with embed_credentials=false for external embedding.
```

### 1d. Genie space prompt

```
Create a Genie space "Prism Travel Intelligence" over metric view <catalog>.<schema>.travel_metrics.
Instructions: "You answer questions about corporate travel spend, CO2 emissions, volume, and
carbon budgets across Air, Hotel, Rail, Car, and Taxi/Rideshare. Always use the metric view
measures; report emissions in tCO2e and spend in USD unless asked otherwise."
Sample questions: "Total travel spend by category this year"; "Top 5 destination countries by CO2 emissions";
"How is spend trending vs last year?"; "Air vs hotel vs rail spend by month"; "Which vendors have the
highest emissions per km?"; "Carbon budget remaining by client".
```

---

## 2. Retail Merchandising Intelligence

Fact grain: one row per **line item of a sales transaction**.

### 2a. Data-generation prompt

```
Generate a synthetic retail-sales fact table `<catalog>.<schema>.retail_sales` for a Prism
"Retail Merchandising Intelligence" demo. One row per sales line item. ~500,000 rows,
2024-01-01 to today.

CLIENTS (tenant key): 3 fictional retailers — northwind/"Northwind Retail",
  summit-goods/"Summit Goods", harbor-mart/"Harbor Mart". Split ~45/35/20.

COLUMNS:
- transaction_date DATE, transaction_id STRING, line_id STRING
- client_id, client_name STRING
- channel STRING (Store / Online / Marketplace — ~55/35/10)
- store_id STRING, store_region STRING (Northeast, Southeast, Midwest, West, International),
  store_country STRING
- department STRING (Apparel, Footwear, Home, Electronics, Grocery, Beauty, Toys)
- category STRING (2-3 per department, e.g. Apparel→Mens/Womens/Kids)
- sku STRING (Pareto: ~20% of SKUs drive ~80% of units), product_name STRING, brand STRING
- units_sold INT (1-6, skewed low)
- unit_price DECIMAL(10,2), unit_cost DECIMAL(10,2) (cost 55-75% of price → realistic margin)
- gross_sales DECIMAL(12,2) (= units_sold*unit_price), discount_amount DECIMAL(12,2)
  (~0-30% of gross; promo periods heavier), net_sales DECIMAL(12,2) (gross - discount),
  cogs DECIMAL(12,2) (= units_sold*unit_cost), gross_margin DECIMAL(12,2) (= net_sales - cogs)
- on_hand_units INT (inventory snapshot for the sku/store at sale time), reorder_point INT
- promo_flag BOOLEAN, return_flag BOOLEAN (~8% returns), loyalty_member BOOLEAN
- customer_segment STRING (New / Returning / VIP)

REALISM:
- Seasonal: Q4 holiday spike (esp. Toys, Electronics, Apparel), back-to-school Aug bump.
- Margin varies by department (Grocery low ~20%, Beauty/Apparel high ~55%).
- Discounts cluster in promo windows; promo_flag rows have higher units, lower margin.
- Weekend > weekday for Store; steady for Online.
Write as a Spark/SQL generation notebook; managed UC table.
```

### 2b. Metric view (measures/dimensions to define)

- **Measures:** `net_sales` (SUM), `gross_margin` (SUM), `gross_margin_pct` (margin/net_sales), `units_sold` (SUM), `transactions` (COUNT DISTINCT transaction_id), `avg_basket` (net_sales/transactions), `discount_rate` (discount/gross_sales), `return_rate` (returns/transactions), `sell_through` (units_sold / (units_sold + on_hand_units)), `inventory_turns` (COGS / avg on-hand value).
- **Dimensions:** `department`, `category`, `brand`, `channel`, `store_region`, `customer_segment`, `sales_month`, `client_name`, `promo_flag`, `loyalty_member`.

### 2c. Dashboard prompt

```
Build an AI/BI dashboard "Retail Merchandising" on metric view <catalog>.<schema>.retail_metrics.
PAGE "Sales & Margin": KPI row (Net Sales, Gross Margin %, Units Sold, Avg Basket);
  line Net Sales by sales_month (this year vs last); bar Margin % by department;
  bar Top 10 brands by net sales; donut sales by channel; table by store_region.
PAGE "Inventory & Promo": KPI row (Sell-Through %, Inventory Turns, Discount Rate, Return Rate);
  bar Sell-through by department; scatter Margin % vs Discount Rate by category;
  line Promo vs Non-promo net sales by month; table slow-movers (low sell-through, high on-hand).
Filters: client_name, department, channel, store_region, sales_month, customer_segment.
Publish embed_credentials=false.
```

### 2d. Genie space prompt

```
Create Genie space "Prism Retail Merchandising" over the retail metric view.
Instructions: "Answer merchandising questions about sales, margin, units, inventory sell-through,
turns, discounts, and returns by department, category, brand, channel, region, and customer segment.
Report currency in USD and margin as a percentage."
Sample questions: "Net sales by department this year"; "Which brands have the highest gross margin %?";
"Sell-through by category"; "How did promo periods affect margin?"; "Top 10 slow-moving SKUs";
"Online vs store sales trend"; "Return rate by department".
```

---

## 3. Hospitality / Hotel Performance

Fact grain: one row per **reservation night** (or per stay — pick nightly for RevPAR math).

### 3a. Data-generation prompt

```
Generate a synthetic hotel-performance fact table `<catalog>.<schema>.hotel_stays` for a Prism
"Hospitality" demo. One row per reservation. ~200,000 rows, 2024-01-01 to today.

CLIENTS (tenant key = hotel group): 3 fictional groups — coastal-collection/"Coastal Collection",
  metro-suites/"Metro Suites", grand-horizon/"Grand Horizon Hotels". Split ~40/35/25.

COLUMNS:
- reservation_id STRING, booking_date DATE, checkin_date DATE, checkout_date DATE
- client_id, client_name STRING (hotel group)
- property_id STRING, property_name STRING, property_city STRING, property_region STRING
  (Americas, EMEA, APAC), property_country STRING
- property_tier STRING (Economy, Midscale, Upscale, Luxury), rooms_available INT (property capacity, static per property)
- room_type STRING (Standard, Deluxe, Suite, Executive)
- nights INT (1-14, skewed 1-3), rooms INT (1-3)
- room_revenue DECIMAL(12,2), fnb_revenue DECIMAL(12,2) (food & beverage), other_revenue DECIMAL(12,2) (spa/parking/resort fee)
- total_revenue DECIMAL(12,2) (sum of the three)
- adr DECIMAL(10,2) (room_revenue / (nights*rooms) — average daily rate)
- channel STRING (Direct, OTA, Corporate, GDS, Wholesale — OTA carries a commission cost)
- commission_cost DECIMAL(10,2) (OTA ~15-18% of room_revenue, others lower/zero)
- market_segment STRING (Transient, Group, Corporate, Leisure)
- guest_country STRING, loyalty_member BOOLEAN, lead_time_days INT (booking to checkin)
- cancelled_flag BOOLEAN (~10%), length_of_stay INT (= nights)

REALISM:
- Occupancy seasonality: summer + holidays high; shoulder seasons low; APAC/EMEA/Americas offset curves.
- ADR scales with property_tier (Luxury 3-5× Economy) and season (peak uplift).
- Luxury/Upscale have higher F&B + other revenue share.
- OTA channel higher for Economy/Midscale; Direct + Corporate higher for Upscale/Luxury.
- Group segment = longer lead_time, lower ADR; Transient = short lead, higher ADR.
Include enough rows per property/day that occupancy (rooms sold / rooms_available) is computable.
Write as Spark/SQL notebook; managed UC table.
```

### 3b. Metric view (measures/dimensions)

- **Measures:** `total_revenue` (SUM), `room_revenue` (SUM), `rooms_sold` (SUM rooms*nights), `room_nights_available` (property capacity × days in scope), `occupancy` (rooms_sold / available), `adr` (room_revenue / rooms_sold), `revpar` (room_revenue / available), `trevpar` (total_revenue / available), `fnb_revenue` (SUM), `commission_cost` (SUM), `avg_lead_time` (AVG lead_time_days), `cancellation_rate` (cancelled / reservations).
- **Dimensions:** `property_tier`, `property_region`, `room_type`, `channel`, `market_segment`, `stay_month`, `client_name`, `loyalty_member`.

### 3c. Dashboard prompt

```
Build an AI/BI dashboard "Hotel Performance" on metric view <catalog>.<schema>.hotel_metrics.
PAGE "Performance": KPI row (RevPAR, ADR, Occupancy %, Total Revenue);
  line RevPAR by stay_month (this year vs last); bar ADR by property_tier;
  bar Occupancy % by property_region; donut revenue by segment (Room/F&B/Other); table by property.
PAGE "Demand & Channel": KPI row (Avg Lead Time, Cancellation Rate, Commission Cost, TRevPAR);
  bar revenue by channel; line booking pace (reservations by booking_month for future checkins);
  bar occupancy by market_segment; scatter ADR vs Occupancy by property.
Filters: client_name, property_tier, property_region, channel, market_segment, stay_month.
Publish embed_credentials=false.
```

### 3d. Genie space prompt

```
Create Genie space "Prism Hospitality" over the hotel metric view.
Instructions: "Answer hotel-performance questions using RevPAR, ADR, occupancy, TRevPAR, and revenue
by property, tier, region, channel, and market segment. RevPAR = room revenue / available room nights;
ADR = room revenue / rooms sold; occupancy = rooms sold / available. Report currency in USD, occupancy as %."
Sample questions: "RevPAR by region this year"; "ADR by property tier"; "Occupancy trend vs last year";
"Which channels drive the most revenue after commission?"; "Booking pace for next quarter";
"Cancellation rate by market segment"; "Top 10 properties by TRevPAR".
```

---

## 4. FBO / Private Aviation — Signature Aviation flavor

**Domain note:** An FBO (Fixed-Base Operator) is a private-aviation terminal providing fuel, hangarage, ramp/ground handling, de-icing, and concierge for business/private jets. Signature Aviation runs the world's largest FBO network. The revenue engine is **fuel uplift** (gallons × margin), plus hangarage, ramp/handling fees, and de-icing — analyzed by **base (FBO location)**, **aircraft category**, and **customer type**. Fact grain: one row per **aircraft movement / fuel-and-services ticket**.

### 4a. Data-generation prompt

```
Generate a synthetic FBO (fixed-base operator) fact table `<catalog>.<schema>.fbo_movements` for a
Prism private-aviation demo in the style of Signature Aviation. One row per aircraft movement/service
ticket. ~180,000 rows, 2024-01-01 to today.

CLIENTS (tenant key = FBO network/brand): 3 fictional networks — apex-air/"Apex Air Services",
  meridian-fbo/"Meridian FBO Network", summit-jet/"Summit Jet Centers". Split ~45/30/25.

COLUMNS:
- ticket_id STRING, movement_date DATE (service date), arrival_date DATE, departure_date DATE
- client_id, client_name STRING (FBO network)
- base_id STRING, base_name STRING, base_icao STRING (e.g. KTEB, KLAS, EGGW, KPBI),
  base_city STRING, base_region STRING (US-Northeast, US-West, US-Southeast, Europe, Caribbean)
- tail_number STRING (pool ~6,000 aircraft), aircraft_category STRING
  (Light Jet, Midsize Jet, Super-Midsize, Heavy Jet, Turboprop, Ultra-Long-Range),
  aircraft_type STRING (e.g. Citation CJ3, Phenom 300, Challenger 350, Gulfstream G650, King Air 350)
- operator_type STRING (Part 91 owner / Part 135 charter / Fractional / Corporate flight dept)
- movement_type STRING (Arrival, Departure, Turn)
- fuel_type STRING (Jet-A, Jet-A+ / SAF blend), fuel_gallons DECIMAL(10,1)
  (scales with aircraft_category: Turboprop 100-400, Light 300-800, Heavy 1500-4000, ULR 3000-6000)
- fuel_price_per_gal DECIMAL(6,2), fuel_cost_per_gal DECIMAL(6,2) (margin 1.50-3.50/gal, higher at premium bases)
- fuel_revenue DECIMAL(12,2) (= gallons*price), fuel_margin DECIMAL(12,2) (= gallons*(price-cost))
- ramp_fee DECIMAL(10,2), handling_fee DECIMAL(10,2), hangar_fee DECIMAL(10,2) (null if not hangared),
  deice_fee DECIMAL(10,2) (winter + northern bases only), catering_fee DECIMAL(10,2), other_fee DECIMAL(10,2)
- services_revenue DECIMAL(12,2) (sum of the fees), total_revenue DECIMAL(12,2) (fuel_revenue + services_revenue)
- hangar_flag BOOLEAN, based_aircraft_flag BOOLEAN (based vs transient; ~25% based), membership_flag BOOLEAN (loyalty/contract fuel)
- turn_time_minutes INT (ground time; Light ~45, Heavy ~90), passenger_count INT (1-14)

REALISM:
- Fuel is ~65-75% of total revenue; gallons and fuel_revenue scale strongly with aircraft_category.
- Ramp/handling waived or reduced when fuel uplift is large (common FBO practice) — model an inverse relationship.
- De-icing only Nov-Mar and only northern/European bases.
- Seasonality: summer + Dec holidays peak (leisure jet travel to Caribbean/resort bases); Teterboro/NY-metro bases weekday-heavy (business).
- Fractional + Part 135 = high movement frequency, contract fuel (thinner margin); Part 91 owners = higher services attach.
- SAF blend a small but growing share (sustainability angle), premium price.
Write as Spark/SQL notebook; managed UC table.
```

### 4b. Metric view (measures/dimensions)

- **Measures:** `total_revenue` (SUM), `fuel_revenue` (SUM), `fuel_gallons` (SUM), `fuel_margin` (SUM), `fuel_margin_per_gal` (fuel_margin/fuel_gallons), `services_revenue` (SUM), `movements` (COUNT DISTINCT ticket_id), `revenue_per_movement` (total_revenue/movements), `avg_uplift_gal` (fuel_gallons/movements), `services_attach_rate` (services_revenue/total_revenue), `avg_turn_time` (AVG turn_time_minutes), `saf_gallons_pct` (SAF gallons / total gallons), `based_movement_pct`.
- **Dimensions:** `base_name`, `base_region`, `aircraft_category`, `operator_type`, `movement_type`, `fuel_type`, `movement_month`, `client_name`, `membership_flag`, `based_aircraft_flag`.

### 4c. Dashboard prompt

```
Build an AI/BI dashboard "FBO Network Performance" on metric view <catalog>.<schema>.fbo_metrics.
PAGE "Fuel & Revenue": KPI row (Total Revenue, Fuel Gallons, Fuel Margin per Gal, Revenue per Movement);
  line Total Revenue by movement_month (this year vs last); bar Fuel gallons by aircraft_category;
  bar Top 10 bases by revenue; donut revenue mix (Fuel vs Services); table by operator_type.
PAGE "Operations & Sustainability": KPI row (Movements, Avg Uplift (gal), Services Attach Rate, SAF %);
  bar movements by base_region; scatter Fuel margin/gal vs uplift by base; line SAF % trend;
  bar avg turn time by aircraft_category; based vs transient split.
Filters: client_name, base_region, aircraft_category, operator_type, fuel_type, movement_month.
Publish embed_credentials=false.
```

### 4d. Genie space prompt

```
Create Genie space "Prism Private Aviation (FBO)" over the fbo metric view.
Instructions: "Answer FBO/private-aviation questions using fuel gallons, fuel revenue and margin per
gallon, services revenue, movements, revenue per movement, uplift per movement, and SAF share — by
base, region, aircraft category, and operator type (Part 91 / Part 135 / Fractional / Corporate).
Fuel is the primary revenue driver. Report currency in USD, fuel in gallons."
Sample questions: "Total revenue by base this year"; "Fuel margin per gallon by region";
"Which aircraft categories uplift the most fuel?"; "Revenue per movement by operator type";
"SAF adoption trend"; "Top 10 bases by fuel volume"; "Services attach rate by base"; "Movements by month vs last year".
```

---

## Applying a vertical to Prism (the seams)

Once the data + metric view + dashboard + Genie space exist, wire the vertical into a Prism deployment by changing only:
1. `brand.config.json` — appName/tagline/accent/logo.
2. `server/assets/dashboards.seed.json` — dashboard IDs, Genie space IDs, per-page prompts, suggested questions, nav.
3. `.env` — `GENIE_SPACE_ID`, `DASHBOARD_URL`, `UC_CATALOG`/`UC_SCHEMA`, `WAREHOUSE_NAME`, SP creds.
4. **Code edits** (the honest seams): `frontend/src/config.ts` `FILTERS` (filter vocabulary), `server/routes/kpis.py` (KPI measure/column names + `KPI_METRIC_VIEW`), and hero/page copy in the page components.

See the README "Spin up a new demo" table for the full config-vs-code breakdown.
```
