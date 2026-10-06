-- Prism Travel Intelligence — synthetic fact table generator (pure SQL, serverless-safe).
-- Target: serverless_stable_71zsua_catalog.prism_travel.summarydataset  (~250k rows)
-- One row per travel component. Realism via deterministic hashing off a row id `r`.
-- Re-runnable: CREATE OR REPLACE.

CREATE OR REPLACE TABLE serverless_stable_71zsua_catalog.prism_travel.summarydataset AS
WITH base AS (
  SELECT
    id AS r,
    -- uniform helpers in [0,1)
    (pmod(hash(id, 11), 100000) / 100000.0) AS u1,
    (pmod(hash(id, 22), 100000) / 100000.0) AS u2,
    (pmod(hash(id, 33), 100000) / 100000.0) AS u3,
    (pmod(hash(id, 44), 100000) / 100000.0) AS u4,
    (pmod(hash(id, 55), 100000) / 100000.0) AS u5,
    (pmod(hash(id, 66), 100000) / 100000.0) AS u6,
    (pmod(hash(id, 77), 100000) / 100000.0) AS u7,
    (pmod(hash(id, 88), 100000) / 100000.0) AS u8
  FROM range(0, 250000)
),
cat AS (
  SELECT b.*,
    -- category by weight: Air 45, Hotel 30, Car 10, Rail 8, Taxi 7
    CASE
      WHEN u1 < 0.45 THEN 'Air'
      WHEN u1 < 0.75 THEN 'Hotel'
      WHEN u1 < 0.85 THEN 'Car'
      WHEN u1 < 0.93 THEN 'Rail'
      ELSE 'Taxi/Rideshare'
    END AS category,
    -- client by weight 40/30/20/10
    CASE
      WHEN u2 < 0.40 THEN 'acme-travel'
      WHEN u2 < 0.70 THEN 'globex'
      WHEN u2 < 0.90 THEN 'initech'
      ELSE 'umbrella'
    END AS client_id
  FROM base b
),
dated AS (
  SELECT c.*,
    -- travel_start_date: spread over 2024-01-01..today with a seasonal bias.
    -- Base uniform day, then nudge toward summer (Jun-Aug) & Q4 via u3.
    CAST(
      date_add('2024-01-01',
        CAST( least(datediff(current_date(), '2024-01-01'),
               greatest(0,
                 CAST(datediff(current_date(),'2024-01-01') * u4 AS INT)
                 + CASE WHEN u3 < 0.25 THEN 30 WHEN u3 > 0.80 THEN 15 ELSE 0 END
               )) AS INT)
      ) AS DATE) AS travel_start_date
  FROM cat c
)
SELECT
  -- ── dates ────────────────────────────────────────────────────────────────
  date_sub(travel_start_date, CAST(1 + u5*40 AS INT))              AS invoice_date,
  travel_start_date,
  CASE category
    WHEN 'Hotel' THEN date_add(travel_start_date, CAST(1 + u6*4 AS INT))
    WHEN 'Air'   THEN date_add(travel_start_date, CASE WHEN u7 < 0.5 THEN 0 ELSE CAST(1+u6*10 AS INT) END)
    WHEN 'Rail'  THEN travel_start_date
    WHEN 'Car'   THEN date_add(travel_start_date, CAST(1 + u6*5 AS INT))
    ELSE travel_start_date
  END                                                              AS travel_end_date,
  YEAR(travel_start_date)                                          AS report_travel_year,
  YEAR(date_sub(travel_start_date, CAST(1 + u5*40 AS INT)))        AS report_invoice_year,

  -- ── geography ────────────────────────────────────────────────────────────
  elt(1 + CAST(u5*8 AS INT), 'New York','London','San Francisco','Frankfurt','Singapore','Tokyo','Chicago','Paris') AS origin_city,
  elt(1 + CAST(u6*8 AS INT), 'London','New York','Tokyo','Dubai','Sydney','Paris','Los Angeles','Frankfurt')        AS destination_city,
  elt(1 + CAST(u5*6 AS INT), 'United States','United Kingdom','Germany','Singapore','Japan','France')               AS origin_country_name,
  elt(1 + CAST(u6*6 AS INT), 'United Kingdom','United States','Japan','United Arab Emirates','Australia','France')   AS destination_country,
  -- destination region
  CASE 1 + CAST(u6*6 AS INT)
    WHEN 1 THEN 'Europe' WHEN 2 THEN 'North America' WHEN 3 THEN 'Asia Pacific'
    WHEN 4 THEN 'Middle East & Africa' WHEN 5 THEN 'Asia Pacific' WHEN 6 THEN 'Europe' ELSE 'Europe' END AS destination_country_region,
  elt(1 + CAST(u5*6 AS INT), 'United States','United Kingdom','Germany','Singapore','Japan','France')               AS traveler_country,
  CASE WHEN category='Hotel' THEN elt(1 + CAST(u6*8 AS INT),'London','New York','Tokyo','Dubai','Sydney','Paris','Los Angeles','Frankfurt') ELSE NULL END AS hotel_property_city,
  -- travel_sector: crude derivation from origin/dest region-ish indices
  CASE
    WHEN CAST(u5*6 AS INT) = CAST(u6*6 AS INT) THEN 'Intra-Country'
    WHEN u6 < 0.55 THEN 'Intra-Continental'
    ELSE 'Inter-Continental'
  END                                                              AS travel_sector,

  category,

  -- ── class ────────────────────────────────────────────────────────────────
  CASE category
    WHEN 'Air'  THEN elt(1 + CAST(u7*4 AS INT), 'Economy','Premium Economy','Business','First')
    WHEN 'Hotel'THEN elt(1 + CAST(u7*4 AS INT), 'Budget','Midscale','Upscale','Luxury')
    WHEN 'Car'  THEN elt(1 + CAST(u7*4 AS INT), 'Economy','Compact','Standard','Premium')
    ELSE NULL
  END                                                              AS travel_class,

  -- ── vendor (Pareto for Air) ──────────────────────────────────────────────
  CASE category
    WHEN 'Air' THEN CASE WHEN u8 < 0.70
        THEN elt(1 + CAST(u3*8 AS INT), 'United','Delta','American','Lufthansa','British Airways','Emirates','Air France','ANA')
        ELSE elt(1 + CAST(u3*6 AS INT), 'KLM','Qatar Airways','Singapore Airlines','Cathay Pacific','Turkish Airlines','Iberia') END
    WHEN 'Hotel' THEN elt(1 + CAST(u3*6 AS INT), 'Marriott','Hilton','IHG','Accor','Hyatt','Wyndham')
    WHEN 'Car'   THEN elt(1 + CAST(u3*5 AS INT), 'Enterprise','Hertz','Avis','Sixt','Europcar')
    WHEN 'Rail'  THEN elt(1 + CAST(u3*4 AS INT), 'Amtrak','Eurostar','Deutsche Bahn','SNCF')
    ELSE elt(1 + CAST(u3*3 AS INT), 'Uber','Lyft','Local Taxi')
  END                                                              AS vendor,

  -- travel_details
  CASE category
    WHEN 'Air'  THEN concat(elt(1 + CAST(u5*8 AS INT),'JFK','LHR','SFO','FRA','SIN','HND','ORD','CDG'),'-',elt(1 + CAST(u6*8 AS INT),'LHR','JFK','HND','DXB','SYD','CDG','LAX','FRA'))
    WHEN 'Rail' THEN concat(elt(1 + CAST(u5*4 AS INT),'NYP','LDN','PAR','BER'),'-',elt(1 + CAST(u6*4 AS INT),'BOS','PAR','LON','MUC'))
    WHEN 'Hotel'THEN concat(elt(1 + CAST(u3*6 AS INT),'Marriott','Hilton','IHG','Accor','Hyatt','Wyndham'),' ',elt(1 + CAST(u6*8 AS INT),'London','New York','Tokyo','Dubai','Sydney','Paris','Los Angeles','Frankfurt'))
    ELSE 'Ground transport'
  END                                                              AS travel_details,
  CASE category WHEN 'Air' THEN elt(1 + CAST(u3*8 AS INT),'UA','DL','AA','LH','BA','EK','AF','NH') ELSE NULL END AS air_carrier_code,
  CASE WHEN category='Hotel' THEN (u4 < 0.35) ELSE NULL END        AS hotel_eco_certified,
  CASE WHEN u5 < 0.65 THEN 'Online' ELSE 'Offline' END             AS booking_source,
  concat('EMP', lpad(CAST(pmod(hash(r, 7), 4000) AS STRING), 5, '0')) AS employee_id,
  'Business Unit'                                                  AS budget_field,
  elt(1 + CAST(u7*4 AS INT), 'Sales','Engineering','Operations','Marketing') AS budget_field_value,

  CASE client_id WHEN 'acme-travel' THEN 'Acme Travel' WHEN 'globex' THEN 'Globex' WHEN 'initech' THEN 'Initech' ELSE 'Umbrella Corp' END AS client_name,
  client_id,

  -- ── spend (local currency) ───────────────────────────────────────────────
  -- distance/class/category drive the amount; store as gross local amount.
  CAST(
    CASE category
      WHEN 'Air'   THEN (200 + u4*400) * CASE travel_class_calc.tc WHEN 'Business' THEN 4 WHEN 'First' THEN 7 WHEN 'Premium Economy' THEN 1.8 ELSE 1 END * (1 + dist.km/4000)
      WHEN 'Hotel' THEN (120 + u4*250) * CASE travel_class_calc.tc WHEN 'Luxury' THEN 3 WHEN 'Upscale' THEN 1.8 WHEN 'Midscale' THEN 1.2 ELSE 1 END * (1 + u6*3)
      WHEN 'Car'   THEN (45 + u4*60) * (1 + u6*4)
      WHEN 'Rail'  THEN (60 + u4*150)
      ELSE (15 + u4*45)
    END AS DECIMAL(12,2))                                          AS total_amount_gross,
  1.0                                                              AS currency_rate_usd,
  0.92                                                             AS currency_rate_eur,
  0.79                                                             AS currency_rate_gbp,

  -- ── emissions (kgCO2e) — correlate with distance & class ──────────────────
  CAST(emis.adv AS DECIMAL(12,3))                                  AS co2_emissions_advito,
  CAST(emis.adv / 1.12 AS DECIMAL(12,3))                           AS co2_emissions_defra,
  CAST(emis.adv * 0.82 AS DECIMAL(12,3))                           AS co2_emissions_advito_wo_rf,
  CAST(emis.adv / 1.12 * 0.82 AS DECIMAL(12,3))                    AS co2_emissions_defra_wo_rf,
  CAST(emis.adv * 1.15 AS DECIMAL(12,3))                           AS co2_emission_budget,

  -- ── volume ───────────────────────────────────────────────────────────────
  1                                                                AS component_count,
  CASE WHEN category='Air' THEN 1 + CAST(u6*2 AS INT) ELSE NULL END AS air_net_segment_count,
  CASE WHEN category='Air' THEN 1 + CAST(u6*2 AS INT) ELSE NULL END AS air_od_segment_count,
  CASE WHEN category='Hotel' THEN 1 + CAST(u6*4 AS INT) ELSE NULL END AS hotel_nights,
  CASE WHEN category='Car' THEN 1 + CAST(u6*5 AS INT) ELSE NULL END AS car_rental_days,
  CASE WHEN category='Rail' THEN 1 + CAST(u6*2 AS INT) ELSE NULL END AS rail_segment_count,
  CAST(dist.km AS DECIMAL(10,1))                                   AS distance_km,
  datediff(travel_start_date, date_sub(travel_start_date, CAST(1 + u5*40 AS INT))) AS adv_booking_days
FROM dated
-- derived helpers
LEFT JOIN LATERAL (
  SELECT CASE dated.category
    WHEN 'Air'  THEN elt(1 + CAST(dated.u7*4 AS INT), 'Economy','Premium Economy','Business','First')
    WHEN 'Hotel'THEN elt(1 + CAST(dated.u7*4 AS INT), 'Budget','Midscale','Upscale','Luxury')
    WHEN 'Car'  THEN elt(1 + CAST(dated.u7*4 AS INT), 'Economy','Compact','Standard','Premium')
    ELSE NULL END AS tc
) AS travel_class_calc
LEFT JOIN LATERAL (
  SELECT CASE dated.category
    WHEN 'Air'  THEN CASE WHEN dated.u7 < 0.5 THEN 300 + dated.u4*1200 ELSE 4000 + dated.u4*8000 END
    WHEN 'Rail' THEN 100 + dated.u4*700
    ELSE 0 END AS km
) AS dist
LEFT JOIN LATERAL (
  SELECT CASE dated.category
    WHEN 'Air'  THEN (CASE WHEN dated.u7 < 0.5 THEN 300 + dated.u4*1200 ELSE 4000 + dated.u4*8000 END)
                     * 0.15 * CASE WHEN dated.u7*4 >= 2 THEN 2.5 ELSE 1 END
    WHEN 'Hotel'THEN (1 + CAST(dated.u6*4 AS INT)) * (10 + dated.u4*20)
    WHEN 'Car'  THEN (1 + CAST(dated.u6*5 AS INT)) * (8 + dated.u4*10)
    WHEN 'Rail' THEN (100 + dated.u4*700) * 0.04
    ELSE (5 + dated.u4*15) END AS adv
) AS emis;
