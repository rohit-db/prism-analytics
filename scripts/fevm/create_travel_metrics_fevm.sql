CREATE OR REPLACE VIEW serverless_stable_71zsua_catalog.prism_travel.travel_metrics
WITH METRICS LANGUAGE YAML AS $$

version: 1.1
comment: "APEX corporate travel analytics — emissions, spend, volume, and carbon budgets across Air, Hotel, Rail, Car, and Taxi/Rideshare categories."
source: serverless_stable_71zsua_catalog.prism_travel.summarydataset

dimensions:

  # ── Time ──────────────────────────────────────────────────────────────────

  - name: invoice_date
    display_name: Invoice Date
    expr: invoice_date
    comment: "Transaction date; for Taxi/Rideshare this is the date the fare was invoiced."
    synonyms:
      - Transaction Date
    format:
      type: date
      date_format: year_month_day
      leading_zeros: true

  - name: travel_start_date
    display_name: Travel Start Date
    expr: travel_start_date
    comment: "Departure date for Air/Rail, check-in date for Hotel, pickup date for Car/Taxi."
    synonyms:
      - Departure Date
      - Check in Date
      - Pickup Date
      - Trip Date
    format:
      type: date
      date_format: year_month_day
      leading_zeros: true

  - name: travel_end_date
    display_name: Travel End Date
    expr: travel_end_date
    comment: "Arrival date for Air/Rail, checkout date for Hotel, return date for Car/Taxi."
    synonyms:
      - Arrival Date
      - Check out Date
      - Return Date
    format:
      type: date
      date_format: year_month_day
      leading_zeros: true

  - name: travel_month
    display_name: Travel Month
    expr: "DATE_FORMAT(travel_start_date, 'yyyy-MM')"
    synonyms:
      - Trip Month
      - Month

  - name: travel_quarter_label
    display_name: Travel Quarter Label
    expr: "CONCAT('Q', QUARTER(travel_start_date), ' ', YEAR(travel_start_date))"
    comment: "e.g. Q1 2024"
    synonyms:
      - Quarter

  - name: travel_year
    display_name: Travel Year
    expr: report_travel_year
    synonyms:
      - Year

  - name: invoice_month
    display_name: Invoice Month
    expr: "DATE_FORMAT(invoice_date, 'yyyy-MM')"

  - name: invoice_quarter_label
    display_name: Invoice Quarter Label
    expr: "CONCAT('Q', QUARTER(invoice_date), ' ', YEAR(invoice_date))"

  - name: invoice_year
    display_name: Invoice Year
    expr: report_invoice_year

  # ── Geography ─────────────────────────────────────────────────────────────

  - name: origin_city
    display_name: Origin City
    expr: origin_city
    comment: "Departure city for Air/Rail; pickup city for Car/Taxi."
    synonyms:
      - Departure City
      - Pickup City

  - name: destination_city
    display_name: Destination City
    expr: destination_city
    comment: "Arrival city for Air/Rail; return city or major city for Car/Hotel."
    synonyms:
      - Arrival City
      - Major City

  - name: origin_country
    display_name: Origin Country
    expr: origin_country_name

  - name: destination_country
    display_name: Destination Country
    expr: destination_country

  - name: destination_region
    display_name: Destination Region
    expr: destination_country_region
    comment: "Continent or sub-region of the destination country."
    synonyms:
      - Region

  - name: traveler_country
    display_name: Traveler Country
    expr: traveler_country
    comment: "Point-of-sale country for the booking."
    synonyms:
      - Country POS

  - name: hotel_city
    display_name: Hotel City
    expr: hotel_property_city
    synonyms:
      - Property City

  - name: travel_sector
    display_name: Travel Sector
    expr: travel_sector
    comment: "Intra-Country, Intra-Continental, or Inter-Continental."
    synonyms:
      - Sector
      - Geographic Scope

  # ── Travel ────────────────────────────────────────────────────────────────

  - name: category
    display_name: Category
    expr: category
    comment: "Travel category: Air, Hotel, Rail, Car, or Taxi/Rideshare."
    synonyms:
      - Travel Type

  - name: travel_class
    display_name: Travel Class
    expr: travel_class
    comment: "Cabin class for Air/Rail; accommodation tier for Hotel; car type for Car."
    synonyms:
      - Cabin
      - Car Type

  - name: vendor
    display_name: Vendor
    expr: vendor
    comment: "Airline, hotel chain, car rental company, or rail operator."
    synonyms:
      - Supplier
      - Carrier
      - Airline

  - name: travel_details
    display_name: Travel Details
    expr: travel_details
    comment: "Route (city pair) for Air/Rail; property name for Hotel; expense detail for Car/Taxi."
    synonyms:
      - City Pair
      - Route

  - name: air_carrier
    display_name: Air Carrier
    expr: air_carrier_code
    synonyms:
      - Airline
      - Carrier Code

  - name: eco_certified_hotel
    display_name: Eco Certified Hotel
    expr: hotel_eco_certified
    comment: "Indicates whether the hotel property holds a recognized sustainability certification."
    synonyms:
      - Green Hotel

  - name: booking_source
    display_name: Booking Source
    expr: booking_source
    comment: "Channel through which the booking was made (online self-booking tool vs. offline agent)."
    synonyms:
      - Channel

  # ── Client ────────────────────────────────────────────────────────────────

  - name: client_id
    display_name: Client ID
    expr: client_id

  - name: client_name
    display_name: Client Name
    expr: client_name

  - name: budget_field
    display_name: Budget Field
    expr: budget_field
    comment: "Carbon budget dimension name (e.g. business unit, cost center)."

  - name: budget_field_value
    display_name: Budget Field Value
    expr: budget_field_value
    comment: "Value of the carbon budget dimension for this record."

measures:

  # ── Emissions ─────────────────────────────────────────────────────────────

  - name: total_emissions_advito
    display_name: Total Emissions (Advito)
    expr: "SUM(co2_emissions_advito) / 1000"
    comment: "Total CO₂-equivalent emissions (tCO₂e) using Advito methodology, including radiative forcing."
    synonyms:
      - Emissions
      - CO2
      - Carbon
    format:
      type: number
      decimal_places:
        type: exact
        places: 1
      abbreviation: compact

  - name: total_emissions_defra
    display_name: Total Emissions (Defra)
    expr: "SUM(co2_emissions_defra) / 1000"
    comment: "Total CO₂-equivalent emissions (tCO₂e) using UK Defra methodology."
    synonyms:
      - Emissions Defra
    format:
      type: number
      decimal_places:
        type: exact
        places: 1
      abbreviation: compact

  - name: total_emissions_wo_rf_advito
    display_name: Total Emissions W/O RF (Advito)
    expr: "SUM(co2_emissions_advito_wo_rf) / 1000"
    comment: "Total CO₂-equivalent emissions (tCO₂e) using Advito methodology, excluding radiative forcing."
    format:
      type: number
      decimal_places:
        type: exact
        places: 1
      abbreviation: compact

  - name: total_emissions_wo_rf_defra
    display_name: Total Emissions W/O RF (Defra)
    expr: "SUM(co2_emissions_defra_wo_rf) / 1000"
    comment: "Total CO₂-equivalent emissions (tCO₂e) using UK Defra methodology, excluding radiative forcing."
    format:
      type: number
      decimal_places:
        type: exact
        places: 1
      abbreviation: compact

  # ── Spend ─────────────────────────────────────────────────────────────────

  - name: gross_spend_usd
    display_name: Gross Spend (USD)
    expr: "SUM(currency_rate_usd * total_amount_gross)"
    comment: "Total gross spend converted to US Dollars using the stored currency rate."
    synonyms:
      - Spend USD
      - Total Amount USD
    format:
      type: number
      decimal_places:
        type: exact
        places: 1
      abbreviation: compact

  - name: gross_spend_eur
    display_name: Gross Spend (EUR)
    expr: "SUM(currency_rate_eur * total_amount_gross)"
    comment: "Total gross spend converted to Euros using the stored currency rate."
    synonyms:
      - Spend EUR
    format:
      type: number
      decimal_places:
        type: exact
        places: 1
      abbreviation: compact

  - name: gross_spend_gbp
    display_name: Gross Spend (GBP)
    expr: "SUM(currency_rate_gbp * total_amount_gross)"
    comment: "Total gross spend converted to British Pounds using the stored currency rate."
    synonyms:
      - Spend GBP
    format:
      type: number
      decimal_places:
        type: exact
        places: 1
      abbreviation: compact

  # ── Volume ────────────────────────────────────────────────────────────────

  - name: component_count
    display_name: Component Count
    expr: "SUM(component_count)"
    comment: "Total number of travel components (trips/bookings) across all categories."
    synonyms:
      - Volume
      - Trip Components
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact

  - name: flight_count
    display_name: Flight Count
    expr: "SUM(air_net_segment_count)"
    comment: "Total number of individual flight legs (net, excluding cancellations)."
    synonyms:
      - Flights
      - Air Legs
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact

  - name: air_segment_count
    display_name: Air Segment Count
    expr: "SUM(air_od_segment_count)"
    comment: "Total number of origin-destination air segments."
    synonyms:
      - Air Segments
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact

  - name: hotel_nights
    display_name: Hotel Nights
    expr: "SUM(hotel_nights)"
    comment: "Total number of hotel room nights booked."
    synonyms:
      - Room Nights
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact

  - name: car_rental_days
    display_name: Car Rental Days
    expr: "SUM(car_rental_days)"
    comment: "Total number of car rental days."
    synonyms:
      - Rental Days
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact

  - name: rail_segment_count
    display_name: Rail Segment Count
    expr: "SUM(rail_segment_count)"
    comment: "Total number of rail segments booked."
    synonyms:
      - Rail Segments
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact

  - name: total_distance_km
    display_name: Total Distance (KM)
    expr: "SUM(distance_km)"
    comment: "Total distance traveled in kilometers across all categories."
    synonyms:
      - Distance
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact

  - name: traveler_count
    display_name: Traveler Count
    expr: "COUNT(DISTINCT employee_id)"
    comment: "Number of unique travelers (by employee ID)."
    synonyms:
      - Unique Travelers
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact

  - name: record_count
    display_name: Record Count
    expr: "COUNT(*)"
    comment: "Total number of records (rows) in the dataset."
    synonyms:
      - Rows
      - Transactions
    format:
      type: number
      decimal_places:
        type: exact
        places: 0
      abbreviation: compact

  # ── Intensity ─────────────────────────────────────────────────────────────

  - name: emissions_per_km
    display_name: Emissions per KM
    expr: "MEASURE(total_emissions_advito) * 1000 / NULLIF(MEASURE(total_distance_km), 0)"
    comment: "Average CO₂ emissions in kgCO₂e per kilometer traveled."
    synonyms:
      - Carbon Intensity per KM
    format:
      type: number
      decimal_places:
        type: exact
        places: 2

  - name: emissions_per_night
    display_name: Emissions per Night
    expr: "MEASURE(total_emissions_advito) * 1000 / NULLIF(MEASURE(hotel_nights), 0)"
    comment: "Average CO₂ emissions in kgCO₂e per hotel room night."
    synonyms:
      - Carbon Intensity per Night
    format:
      type: number
      decimal_places:
        type: exact
        places: 1

  - name: emissions_per_segment
    display_name: Emissions per Segment
    expr: "MEASURE(total_emissions_advito) * 1000 / NULLIF(MEASURE(air_segment_count), 0)"
    comment: "Average CO₂ emissions in kgCO₂e per air origin-destination segment."
    format:
      type: number
      decimal_places:
        type: exact
        places: 1

  - name: emissions_per_rental_day
    display_name: Emissions per Rental Day
    expr: "MEASURE(total_emissions_advito) * 1000 / NULLIF(MEASURE(car_rental_days), 0)"
    comment: "Average CO₂ emissions in kgCO₂e per car rental day."
    format:
      type: number
      decimal_places:
        type: exact
        places: 1

  # ── Carbon Budget ─────────────────────────────────────────────────────────

  - name: co2_budget
    display_name: CO2 Budget
    expr: "SUM(co2_emission_budget)"
    comment: "Total allocated CO₂ emissions budget (tCO₂e) for the filtered scope."
    format:
      type: number
      decimal_places:
        type: exact
        places: 1
      abbreviation: compact

  - name: budget_remaining
    display_name: Budget Remaining
    expr: "MEASURE(co2_budget) - MEASURE(total_emissions_advito)"
    comment: "Remaining carbon budget (tCO₂e): allocated budget minus actual Advito emissions."
    format:
      type: number
      decimal_places:
        type: exact
        places: 1
      abbreviation: compact

  # ── Booking ───────────────────────────────────────────────────────────────

  - name: avg_advance_booking_days
    display_name: Avg Advance Booking Days
    expr: "AVG(adv_booking_days)"
    comment: "Average number of days between booking date and travel start date."
    format:
      type: number
      decimal_places:
        type: exact
        places: 0

$$
