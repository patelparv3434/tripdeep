# Tripdeep Decisions and Assumptions

## Prompt Conflicts

| Topic | Source requirements | Implementation decision |
| --- | --- | --- |
| Airport distance | User example says 20 km; Orchestrator says 30 km; Travel Planner example uses 150 km. | `AIRPORT_RADIUS_KM` is configurable and defaults to the strict 20 km user example. A per-trip explicit value must be shown in the audit. Product owner confirmation is still needed for a system-wide rule. |
| Room occupancy | Orchestrator says exactly two per room; Hotel prompt says use actual hotel occupancy and supports family rooms/extra beds. | Preserve requested occupancy and actual provider capacity separately. Enforce two per room only where the trip explicitly sets it. |
| Financial discounts | Orchestrator contains sample discount percentages; Finance prohibits unverified offers. | Examples never become financial facts. Only verified and eligible offers reduce totals. |
| Weather requirements | No standalone Weather Agent prompt; Google Weather is required by orchestration. | Use the orchestration output contract and report no forecast when integration is missing/outside its horizon. |
| Provider access | Several prompts name commercial/partner APIs but no keys or authorization are supplied. | Provider adapters report `NOT_CONFIGURED`; no scraping, sample inventory presented as live, or invented fallback. |
| Dietitian inputs | Ages and allergy confirmation gate Jain plans; local lookup is required for current food/weather context. | Missing input returns `needs_input`; unavailable context returns `degraded`; no dishes or nutrition values are made up. |
| Authentication | User asks for local software and gives no auth provider. | Only a local development owner is supported. No production auth claim; deployment requires a real identity provider and ownership enforcement. |

## Provider and Data Gaps

- No API credentials are supplied for Google Weather/Maps, Goibibo, MakeMyTrip, GDS, guide inventory or insurers.
- No insurer policy corpus or provider terms are supplied for retrieval-grounded comparison.
- No local LLM is assumed installed; Ollama is optional and not necessary for deterministic operations.
- Current forecast, bookings, costs, cancellation terms and guide availability therefore remain unavailable until authorized integrations are configured.
- `Document Agent` local parsing currently supports only explicitly supplied text/JSON/CSV; PDF/DOCX/image extraction needs hardened parser/OCR integrations and upload controls.

## Safety Rules

- External facts require a source and status.
- Unknown or conflicting requirements become `NEEDS_REVIEW`.
- Only verified financial values are aggregated; mixed currencies need an exchange-rate source.
- Provider unavailability is not a successful search result.
- Automated retries never perform booking/payment side effects.
- Reproduction inputs are sanitized; a replay passing once does not mark a bug FIXED without a regression test.