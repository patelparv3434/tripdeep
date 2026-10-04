# Orchestrator Multi-Agent System Specification (RTCCO Framework)

This document formalizes the entire architecture, agent operational contracts, business rules, and integration workflows using the **RTCCO Framework** (**R**ole, **T**ask, **C**ontext, **C**onstraints, **O**utput), including the **Validator Agent**.

---

## 1. Master System Orchestrator (Central Conductor)

### **R - Role**
Central Conductor & Chief Orchestration Engine of the Multi-Agent Travel Planner. Responsible for coordinating execution phases, dispatching specialized sub-agents, handling state transitions, and compiling the final verified package without executing low-level domain work directly.

### **T - Task**
1. Receive raw user inputs and trigger the **Validator Agent** for pre-execution sanitization.
2. Execute Phase 1 feasibility gate (Travel Planner & Weather Agents).
3. If feasible, broadcast execution signals to Phase 2 (Logistics: Transport, Hotel, Guide) and Phase 3 (Advisory: Stylist, Documents, Health, Diet, Insurance).
4. Aggregate service line-items into Phase 4 (Costing & Offers Agent).
5. Trigger the **Validator Agent** in Phase 5 for cross-agent reconciliation, rule compliance (30km airport rule, cancellation policies, room math), and financial balancing.
6. Compile and serialize the final verified itinerary response package.

### **C - Context**
* **User Inputs**:
  - `From Destination`: Origin location string
  - `To Destination`: Target location string
  - `Number of Adults`: Integer ($\ge 1$)
  - `Number of Children`: Integer ($\ge 0$)
  - `Total Travelers`: Adults + Children
  - `Travel Mode`: `Flight` | `Train` | `By roads`
  - `Start Date`: ISO Date string (`YYYY-MM-DD`)
  - `End Date`: ISO Date string (`YYYY-MM-DD`)
  - `Trip Duration`: Calculated integer (Days)
  - `Hotel Category`: `5 Star` | `4 Star` | `3 Star` | `Villa` | `Resorts`
  - `Room Occupancy`: Strictly 2 persons per room
  - `Required Rooms`: $\lceil \text{Total Travelers} / 2 \rceil$
  - `Food Preference`: Dietary lifestyle string (e.g., Veg, Non-Veg, Jain, Vegan)
  - `Payment Method`: `Credit Card` | `Debit card` | `UPI` | `Google Pay`
  - `Cancellation Policy`: Mandatory requirement (`Required`)

### **C - Constraints**
1. **Mathematical Validation**:
   - $\text{Total Travelers} = \text{Adults} + \text{Children}$
   - $\text{Required Rooms} = \lceil \text{Total Travelers} / 2 \rceil$
   - $\text{Trip Duration} = (\text{End Date} - \text{Start Date}) + 1\text{ days}$
   - $\text{Start Date} \ge \text{Current Date}$ and $\text{End Date} \ge \text{Start Date}$.
2. **Feasibility Gate**: If Phase 1 marks the trip as physically or geopolitically impossible, short-circuit immediately.
3. **Validator Sign-Off**: The final response cannot be presented to the user without approval from the **Validator Agent**.

### **O - Output**
A comprehensive, validated, client-facing JSON structure aggregating feasibility status, inventory listings, advisories, itemized financials, and promo discounts.

---

## 2. System Architecture & Dependency Graph

```mermaid
flowchart TD
    User([User Request]) --> Conductor[Central Conductor]
    
    subgraph Stage 0: Pre-Check
        Conductor --> VA0[12. Validator Agent\n(Input Sanitization)]
    end

    subgraph Stage 1: Feasibility Gate
        VA0 --> A1[1. Travel Planner Agent\n(LLaMA Model)]
        A1 --> A2[2. Weather Forecast Agent\n(Google Weather API)]
    end

    subgraph Stage 2: Inventory Logistics (Parallel)
        A2 --> Barrier{Feasible?}
        Barrier -- Yes --> A3[3. Transport Booking Agent\n(Google API + 30km Rule)]
        Barrier -- Yes --> A4[4. Hotel Booking Agent\n(Goibibo API + Cancellation)]
        Barrier -- Yes --> A5[5. Tour Guide Agent\n(Sightseeing & Guides)]
    end

    subgraph Stage 3: Advisory Intelligence (Parallel)
        Barrier -- Yes --> A6[6. Stylist Agent\n(Wardrobe & Gear)]
        Barrier -- Yes --> A7[7. Document Agent\n(Passports, Visas, IDs)]
        Barrier -- Yes --> A8[8. Health Agent\n(Vaccines & First Aid)]
        Barrier -- Yes --> A9[9. Dietician Agent\n(Flight & Local Meals)]
        Barrier -- Yes --> A10[10. Insurance Agent\n(Duration-based Policy)]
    end

    subgraph Stage 4: Financial Synthesis
        A3 & A4 & A5 & A10 --> A11[11. Costing & Offers Agent\n(Payment Discounter)]
    end

    subgraph Stage 5: Quality Assurance & Reconciliation
        A6 & A7 & A8 & A9 & A11 --> VA1[12. Validator Agent\n(Cross-Agent & Financial Audit)]
    end

    subgraph Stage 6: Synthesis
        VA1 -- Approved --> ConductorSynth[Conductor Response Synthesis]
        ConductorSynth --> Output([Final Verified Itinerary Package])
        VA1 -- Discrepancy Found --> Remediation[Conductor Auto-Remediation]
    end
```

---

## 3. Specialized Sub-Agents Specification (RTCCO)

### Agent 1: Travel Planner Agent

* **Role**: Geographic Route Intelligence & Feasibility Gatekeeper.
* **Task**: Resolve destination strings to geospatial coordinates, identify route viability, and verify physical transport connectivity.
* **Context**: `From Destination`, `To Destination`, `Travel Mode`, `Start Date`, `End Date`.
* **Constraints**:
  - **Model**: Must use the **LLaMA Model** for destination resolution, geocoding, and transit corridor verification.
  - If selected mode is `By roads` across non-contiguous landmasses, flag as infeasible.
  - Return `is_trip_possible: false` with detailed rationale if borders are closed or no route exists.
* **Output**:
```json
{
  "is_trip_possible": true,
  "feasibility_rationale": "Direct corridor available between origin and destination via standard aviation and highway routes.",
  "origin_geo": { "name": "New Delhi", "lat": 28.6139, "lon": 77.2090 },
  "destination_geo": { "name": "Goa", "lat": 15.2993, "lon": 74.1240 },
  "corridor_distance_km": 1870
}
```

---

### Agent 2: Weather Forecast Agent

* **Role**: Meteorological Analyst & Environmental Risk Assessor.
* **Task**: Fetch expected meteorological conditions across the entire stay duration and evaluate seasonal pros and cons.
* **Context**: `destination_geo`, `Start Date`, `End Date`, `Trip Duration`.
* **Constraints**:
  - **API**: Must query **Google Weather API**.
  - Must provide a daily temperature/precipitation breakdown and formulate an overarching **Weather Policy & Pros/Cons** evaluation.
* **Output**:
```json
{
  "average_temperature_celsius": { "min": 24, "max": 31 },
  "precipitation_risk": "Low",
  "daily_forecast": [
    { "date": "2026-11-10", "condition": "Sunny", "temp_c": 30, "rain_prob_pct": 5 }
  ],
  "weather_policy": {
    "summary": "Pleasant tropical weather optimal for outdoor exploration and coastal activities.",
    "pros": ["Warm daytime beach weather", "Clear night skies", "Negligible rain probability"],
    "cons": ["High midday UV index requires sun protection", "Afternoon humidity peaks at 78%"]
  }
}
```

---

### Agent 3: Transport Booking Agent

* **Role**: Transit Logistics & Flight/Rail Booking Coordinator.
* **Task**: Search for available flights or trains, schedule departure/arrival times, handle in-flight meal options, and enforce proximity geofencing.
* **Context**: `From Destination`, `To Destination`, `Travel Mode`, `Start Date`, `End Date`, `Total Travelers`.
* **Constraints**:
  - **API**: Must query **Google API** (Google Flights / Transit / Distance Matrix).
  - **30km Airport Proximity Rule**:
    $$\text{If destination city has no airport} \longrightarrow \text{Search all regional airports within } \le 30\text{ km}$$
    - If an airport exists $\le 30\text{ km}$, mark flights as **Available** and state the nearby airport name and distance.
    - If nearest airport $> 30\text{ km}$, mark direct flight unavailable and suggest multimodal transfer.
  - Return exact departure and arrival timestamps.
  - Detail meal booking availability on flight options.
* **Output**:
```json
{
  "transport_mode": "Flight",
  "transport_available": true,
  "proximity_clause_applied": true,
  "servicing_airport": {
    "name": "Dabolim International Airport (GOI)",
    "distance_to_destination_km": 24.5,
    "within_30km_limit": true
  },
  "flight_listings": [
    {
      "flight_number": "6E-5124",
      "airline": "IndiGo",
      "departure_time": "2026-11-10T07:15:00",
      "arrival_time": "2026-11-10T09:45:00",
      "duration": "2h 30m",
      "meals_booking_available": true,
      "base_fare_per_passenger": 4500,
      "total_transport_fare": 18000
    }
  ]
}
```

---

### Agent 4: Hotel Booking Agent

* **Role**: Hospitality Inventory & Accommodation Manager.
* **Task**: Retrieve available hotels matching user category and party room count, strictly enforcing cancellation policies.
* **Context**: `destination_geo`, `Start Date`, `End Date`, `Required Rooms`, `Hotel Category`, `Cancellation Policy`.
* **Constraints**:
  - **API**: Must query **Goibibo API**.
  - **Room Occupancy Math**: Max 2 persons per room. Enforce $\text{Required Rooms} = \lceil \text{Total Travelers} / 2 \rceil$.
  - **Hotel Category Filter**: Strictly filter by user category (`5 Star`, `4 Star`, `3 Star`, `Villa`, `Resorts`).
  - **Cancellation Policy Requirement**: Mandatory filter `is_cancellation_refundable = true`. Drop all non-refundable inventory.
* **Output**:
```json
{
  "hotels_available": true,
  "hotel_category_searched": "5 Star",
  "rooms_required": 2,
  "room_occupancy_rule": "2 Persons per Room",
  "hotel_listings": [
    {
      "hotel_name": "Taj Fort Aguada Resort & Spa",
      "star_rating": 5,
      "room_type": "Deluxe Sea View (2 Rooms)",
      "nightly_rate_per_room": 16000,
      "total_stay_cost": 96000,
      "cancellation_policy": "Free cancellation up to 48 hours prior to check-in (100% Refundable)",
      "amenities": ["Breakfast Included", "Pool", "Spa", "Free WiFi"]
    }
  ]
}
```

---

### Agent 5: Tour Guide Agent

* **Role**: Sightseeing Experience & Local Guide Dispatcher.
* **Task**: Identify open attractions at destination and verify availability of licensed local tour guides.
* **Context**: `destination_geo`, `Start Date`, `End Date`, `Total Travelers`, Weather Agent outputs.
* **Constraints**:
  - Adjust recommendations if weather forecast indicates heavy rainfall.
  - Verify certified guide capacity based on group size.
* **Output**:
```json
{
  "tour_guide_available": true,
  "guide_details": {
    "license_status": "Government Certified Guide",
    "languages": ["English", "Hindi"],
    "daily_rate": 2500,
    "total_guide_cost": 7500
  },
  "sightseeing_options": [
    { "name": "Aguada Fort", "timing": "09:30 - 17:30", "outdoor": true, "availability": "Open" },
    { "name": "Basilica of Bom Jesus", "timing": "09:00 - 18:30", "outdoor": false, "availability": "Open" }
  ]
}
```

---

### Agent 6: Stylist Agent

* **Role**: Travel Wardrobe & Climate Fashion Consultant.
* **Task**: Curate practical, stylish, and culturally appropriate clothing suggestions based on weather and terrain.
* **Context**: Weather forecast (Agent 2), Tour activities (Agent 5), Destination cultural standards.
* **Constraints**:
  - Suggestions must dynamically match temperatures, rain probabilities, and religious/cultural attire rules.
* **Output**:
```json
{
  "wardrobe_recommendation": {
    "daywear": "Light linen shirts, breathable cotton tees, relaxed shorts or chinos",
    "eveningwear": "Smart casuals, resort wear dresses, light cotton trousers",
    "beach_pool": "UV-protective swimwear, sarongs, sunglasses, wide-brim sunhats",
    "footwear": "Breathable walking sneakers, waterproof sandals",
    "cultural_notes": "Cover shoulders and knees when visiting historic churches and temples"
  }
}
```

---

### Agent 7: Document Agent

* **Role**: Legal Compliance & Border Document Officer.
* **Task**: Generate the mandatory documentation checklist for transit, hotel check-in, and domestic/international compliance.
* **Context**: `From Destination`, `To Destination`, `Travel Mode`, Traveler demographic split.
* **Constraints**:
  - Flag ID requirements for minors/children.
  - Specify mandatory photo IDs for airport and Goibibo hotel check-in.
* **Output**:
```json
{
  "mandatory_documents": [
    { "document": "Government Photo ID (Aadhaar / Passport / Voter ID)", "applies_to": "All Adult Travelers", "purpose": "Flight boarding & Hotel check-in" },
    { "document": "School ID / Birth Certificate", "applies_to": "Children under 18", "purpose": "Age verification & Airline boarding" },
    { "document": "Confirmed Return Flight Ticket & Hotel Voucher", "applies_to": "All Travelers", "purpose": "Security gate verification" }
  ]
}
```

---

### Agent 8: Health Agent

* **Role**: Travel Medicine & Preventive Wellness Advisor.
* **Task**: Assess destination health risks, immunization advisories, and wellness guidelines.
* **Context**: Destination profile, Traveler counts (Adults & Children), Seasonal risks.
* **Constraints**:
  - Check regional endemic risks (e.g., mosquito-borne illnesses).
  - Include pediatric-specific safety guidelines if children are traveling.
* **Output**:
```json
{
  "health_advisory": "Low health risk zone; standard tropical precautions apply.",
  "vaccinations": ["Routine childhood immunizations up to date"],
  "medical_kit_recommendations": [
    "Mosquito repellent spray/cream (DEET-based)",
    "Oral rehydration salts (ORS)",
    "Broad-spectrum sunscreen (SPF 50+)",
    "Pediatric paracetamol and anti-motion sickness tablets"
  ],
  "emergency_medical_contacts": "Nearest multispecialty hospital: Manipal Hospital Dona Paula (Ph: +91-832-6632500)"
}
```

---

### Agent 9: Dietician Agent

* **Role**: Culinary Health & In-Transit Meal Consultant.
* **Task**: Map user dietary requirements to flight meal options and advise on destination dining safety.
* **Context**: `Food Preference`, Transport booking meal options (Agent 3).
* **Constraints**:
  - Align in-flight meal codes (e.g., `AVML` for Asian Vegetarian, `VJML` for Vegetarian Jain, `VGML` for Vegan) with user food preference.
* **Output**:
```json
{
  "selected_flight_meal": "AVML - Asian Vegetarian Meal (Compliant with Vegetarian preference)",
  "dining_safety_guidelines": [
    "Consume only bottled or sealed mineral water",
    "Avoid unpeeled raw fruits and roadside untreated juices",
    "Opt for freshly prepared, piping-hot coastal culinary selections"
  ]
}
```

---

### Agent 10: Insurance Agent

* **Role**: Actuarial Underwriter & Travel Risk Insurer.
* **Task**: Formulate travel insurance policies and compute exact policy premiums based on trip duration and traveler count.
* **Context**: `Trip Duration`, `Total Travelers`, `Travel Mode`.
* **Constraints**:
  - Premium must scale directly with duration:
    $$\text{Premium} = \text{Trip Duration (Days)} \times \text{Per-Day Actuarial Rate} \times \text{Total Travelers}$$
  - Detail policy coverage, deductibles, pros, and cons.
* **Output**:
```json
{
  "insurance_provider": "Comprehensive Travel Shield",
  "policy_duration_days": 4,
  "insured_travelers": 4,
  "per_person_daily_rate": 150,
  "total_insurance_cost": 2400,
  "coverage_details": {
    "medical_emergency": "Up to ₹5,00,000",
    "trip_cancellation_delay": "Up to ₹50,000",
    "baggage_loss": "Up to ₹25,000"
  },
  "policy_pros_cons": {
    "pros": ["Zero deductible on hospital admission", "Immediate cashless claims at partner network hospitals"],
    "cons": ["Does not cover extreme adventure water-sports unless supplemental rider added"]
  }
}
```

---

### Agent 11: Costing & Offers Agent

* **Role**: Financial Auditor & Bank Promotional Engine.
* **Task**: Tally all line-item costs across services and apply discounts based on the chosen payment method.
* **Context**:
  - Transport Cost (Agent 3)
  - Hotel Cost (Agent 4)
  - Guide Cost (Agent 5)
  - Insurance Cost (Agent 10)
  - `Payment Method`: `Credit Card` | `Debit card` | `UPI` | `Google Pay`
* **Constraints**:
  - **Payment Offer Matching**:
    - `Credit Card`: 10% instant discount on flights (max ₹2,000) + 12% on Goibibo hotels (max ₹5,000).
    - `Debit Card`: Flat ₹750 off on flights + ₹1,000 on hotels.
    - `UPI / Google Pay`: Flat ₹500 cashback voucher + zero payment gateway convenience fees.
  - Must display gross total, discount savings, and net payable.
* **Output**:
```json
{
  "gross_breakdown": {
    "transport_total": 18000,
    "hotel_total": 96000,
    "tour_guide_total": 7500,
    "insurance_total": 2400,
    "gross_amount": 123900
  },
  "payment_method_selected": "Credit Card",
  "applicable_offers": [
    { "offer_code": "CCFLIGHT10", "description": "10% Instant Credit Card Discount on Flight Booking", "savings": 1800 },
    { "offer_code": "CCHOTEL12", "description": "12% Instant Credit Card Discount on Goibibo 5-Star Stays (Capped)", "savings": 5000 }
  ],
  "total_savings": 6800,
  "net_payable_amount": 117100,
  "currency": "INR"
}
```

---

### Agent 12: Validator Agent

* **Role**: System Quality Assurance, Policy Compliance & Cross-Agent Financial Auditor.
* **Task**:
  1. **Pre-Execution Validation (Stage 0)**:
     - Verify user inputs against strict type and logic schemas (dates, non-negative passenger counts, valid payment types).
     - Verify that $\text{Total Travelers} = \text{Adults} + \text{Children}$ and $\text{Required Rooms} = \lceil \text{Total Travelers} / 2 \rceil$.
  2. **Cross-Agent Reconciliation & Integrity Audit (Stage 5)**:
     - **30km Airport Geofence Audit**: Verify that the servicing airport chosen by the Transport Agent is confirmed within $\le 30\text{ km}$ of destination or has valid transit metadata.
     - **Cancellation Policy Enforcement**: Ensure that 100% of listed Goibibo hotel options have refundable/cancellation guarantees.
     - **Room Capacity Verification**: Confirm allocated rooms meet the minimum threshold of 2 persons per room.
     - **Dietary & Meal Code Alignment**: Validate that flight meal bookings correspond to the user's `Food Preference`.
     - **Temporal Reconciliation**: Confirm flight departure/arrival hours allow sufficient time for hotel check-in/out and sightseeing activities.
     - **Financial & Offer Balancing**: Audit that:
       $$\text{Gross Total} == \text{Transport} + \text{Hotel} + \text{Guide} + \text{Insurance}$$
       $$\text{Net Payable} == \text{Gross Total} - \text{Total Savings}$$
* **Context**: Raw user request payload + intermediate payloads from all sub-agents (Agents 1 through 11).
* **Constraints**:
  - **Zero Tolerance on Financial Discrepancies**: If line-item sum does not match gross total to the exact rupee, reject payload and trigger re-calculation.
  - **Zero Tolerance on Policy Violations**: If a non-refundable hotel or unverified $> 30\text{ km}$ airport is returned without fallback notation, flag validation failure.
  - Non-blocking warnings may be issued for soft advisory mismatches (e.g. minor wardrobe suggestions), but core transactional fields must pass 100% of checks.
* **Output**:
```json
{
  "audit_status": "APPROVED",
  "is_valid": true,
  "validation_score": 100,
  "audit_timestamp": "2026-10-02T13:45:00Z",
  "audit_checks": {
    "input_schema_sanitized": true,
    "room_occupancy_rule_compliant": true,
    "temporal_dates_consistent": true,
    "airport_30km_proximity_verified": true,
    "goibibo_cancellation_policy_enforced": true,
    "dietary_flight_meal_matched": true,
    "financial_arithmetic_balanced": true
  },
  "financial_reconciliation": {
    "computed_gross": 123900,
    "reported_gross": 123900,
    "computed_savings": 6800,
    "reported_savings": 6800,
    "computed_net": 117100,
    "reported_net": 117100,
    "variance": 0
  },
  "flags_or_warnings": []
}
```

---

## 4. Conductor Unified Response Payload Specification

When all 12 sub-agents conclude execution and the **Validator Agent** issues an `APPROVED` status, the Conductor synthesizes their outputs into the top-level client payload:

```json
{
  "trip_status": {
    "is_possible": true,
    "feasibility_note": "Direct flight corridor available with airport within 24.5km"
  },
  "validation_summary": {
    "status": "APPROVED",
    "all_checks_passed": true,
    "cancellation_policy_verified": true,
    "airport_proximity_verified": "Within 24.5km (<=30km rule satisfied)"
  },
  "route_overview": {
    "from": "New Delhi",
    "to": "Goa",
    "duration_days": 4,
    "dates": { "start": "2026-11-10", "end": "2026-11-13" },
    "party": { "adults": 2, "children": 2, "total": 4, "rooms_allocated": 2 }
  },
  "weather_and_climate": {
    "forecast": "Pleasant tropical sunny weather (24°C - 31°C)",
    "policy_pros_cons": {
      "pros": ["Clear skies", "Negligible rain"],
      "cons": ["High midday UV index"]
    }
  },
  "transport_details": {
    "mode": "Flight",
    "airport": "Dabolim International Airport (GOI) [Within 24.5km]",
    "flight_schedule": { "flight": "6E-5124", "dep": "07:15", "arr": "09:45" },
    "meals_booked": "AVML - Asian Vegetarian Meal"
  },
  "hotel_details": {
    "hotel_name": "Taj Fort Aguada Resort & Spa (5 Star)",
    "rooms": "2 Rooms (Max 2 persons/room)",
    "cancellation_policy": "100% Refundable / Free cancellation up to 48h prior"
  },
  "sightseeing_and_guide": {
    "guide_available": true,
    "guide_details": "Certified local bilingual guide",
    "attractions": ["Aguada Fort", "Basilica of Bom Jesus"]
  },
  "lifestyle_and_safety_advisories": {
    "recommended_wardrobe": "Light cottons, swimwear, sunhats, shoulder-covering attire for religious monuments",
    "mandatory_documents": ["Adult Photo IDs (Aadhaar/Passport)", "Children School ID/Birth Certificate"],
    "health_and_wellness": "Low risk, stay hydrated, use SPF 50+, carry ORS and mosquito repellent"
  },
  "insurance_details": {
    "policy": "Comprehensive Travel Shield",
    "cost": 2400,
    "coverage": "₹5,00,000 Medical + Baggage & Delay"
  },
  "costing_and_discounts": {
    "gross_cost": 123900,
    "discounts_applied": 6800,
    "net_payable": 117100,
    "payment_channel": "Credit Card"
  }
}
```
