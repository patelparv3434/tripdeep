# Tripdeep System Architecture

## Goals and Boundaries

Tripdeep is a local-first multi-agent travel planning application. The supplied agent prompts are the functional source of truth. The system separates deterministic travel/business validation from optional LLM reasoning and external provider access. An unavailable API must reduce data availability, not be replaced by a fabricated success.

The implementation targets a local React + Vite + TypeScript frontend, Python + FastAPI backend, MongoDB persistence through PyMongo's async client and pytest/Vitest coverage. Provider secrets stay server-side in environment variables.

## Components

```text
React SPA (React Router, schema-driven forms)
        | REST/JSON; request ID
FastAPI API layer
        | auth boundary, Pydantic request/response schemas
Application services
        | trip service / agent registry / orchestrator / retry / error capture
Agent modules
        | BaseAgent + independent domain implementations
Validators (deterministic schemas/rules + Validator Agent findings)
        |
MongoDB collections / async PyMongo
        |
MongoDB database + startup-managed indexes

Provider interfaces: weather, maps, hotel, transport, tour, insurance, LLM,
document extraction. Unconfigured providers explicitly report unavailable.
```

## Backend Module Boundaries

Use `backend/app/` with the following ownership (create as implementation progresses):

- `api/`: versioned REST routers, dependency injection and HTTP error mapping.
- `core/`: settings, structured logging, request/execution correlation IDs and security configuration.
- `db/`: reusable async Mongo client, database dependency and collection index setup.
- `models/`: collection/document shape contracts, added only where useful.
- `schemas/`: Pydantic API, agent input/output and dynamic form contracts.
- `repositories/`: persistence queries, no agent business logic.
- `services/`: trip workflow, orchestration, validation, retry, error/reproduction and document processing.
- `agents/`: one module per source-defined specialist plus `base.py`, `registry.py` and shared typed contracts.
- `integrations/`: provider protocols and configured adapters; mock/local adapters are clearly labelled and never presented as live.
- `workers/`: deferred/background work when justified by document processing or long workflows.

The Travel Planner is the orchestration service. Specialist agents do not import frontend code or own database sessions. All executions pass through a common interface and produce structured, schema-validated outputs.

## Agent Execution Contract

Each agent definition returned by `GET /api/agents` contains stable id/name, description, input schema, supported outputs, dependencies, provider requirements and availability. An execution follows:

```text
request + request_id
  -> authenticate/authorize
  -> validate agent id and Pydantic input
  -> persist execution as RUNNING
  -> execute with bounded timeout/retry for transient provider errors
  -> validate output against agent schema
  -> Validator Agent + deterministic policy checks
  -> persist output, validation checks, source metadata and status
  -> return structured result
```

Errors are logged with correlation IDs and sanitized user-facing messages. An execution failure creates a reproduction case containing sanitized input, exception class/message/stack, agent/request/execution IDs, environment/version, retry history, available output and reproduction steps. Reproduction records are diagnostic artifacts, not proof that a bug is fixed; regression status requires a test result.

## Validator Design (Required)

The Validator is both a registered agent and a mandatory orchestration stage for important workflows. It never invents a rule or corrects source information. Its result is a typed object with overall status, checks, evidence/source, missing information, severity and action.

Validation is two-layered:

1. Deterministic rules: Pydantic schema, traveler arithmetic, date arithmetic, required rooms, declared occupancy, provider-confirmed cancellation, airport threshold selected for the trip, known data conflicts, and exact finance arithmetic.
2. Validator Agent review: cross-document and cross-agent consistency, requirements without a deterministic rule, and explicit `NEEDS_REVIEW` for uncertainty.

The final audit itself is checked for valid schema and consistency. A PASS from the LLM alone cannot override deterministic failures. Statuses: `PASS`, `FAIL`, `WARNING`, `MISSING`, `NEEDS_REVIEW`, `NOT_APPLICABLE`.

## Retry and Error-Reproduction Policy

- Retry only transient failures (timeouts, network interruption, rate limit, temporary service/database availability) with exponential backoff, configurable small maximum attempts and per-call timeout.
- Do not retry invalid input, permanent authorization failures, unsupported providers or validation failures as if they were transient.
- Use an in-process circuit breaker per external provider to stop repeated calls after configured failures; expose `TEMPORARILY_UNAVAILABLE` and recovery state.
- Persist each attempt and the final status. On exhausted retries or unexpected exceptions, create a reproduction case automatically.
- Never retry forever or perform irreversible bookings/payments in automated retries.

## MongoDB Data Model

MongoDB indexes are created at application startup. Relationships use string IDs so API/execution records remain easy to inspect and portable. Data accessed together is embedded; independently queried and potentially unbounded records stay in separate collections.

- `users`: identity and auth subject; unique email index and extensible authorization boundary.
- `trips`: owner, bounded trip input, derived date/traveler values and lifecycle status.
- `agent_executions`: trip/user/agent IDs, input/output, embedded bounded validation result, status, error summary, retry count and timestamps.
- `documents`: owner/trip, safe storage key, original filename metadata, media type, size, checksum, extraction status and structured extraction; file bytes remain outside MongoDB and extracted data is not trusted until validation.
- `reproduction_cases`: related execution/request, sanitized reproduction payload, stack/error metadata, environment/version, state, bounded retry history and comparison.
- `audit_logs`: security-sensitive actions and lifecycle changes with correlation identifiers; redact secrets.

Validation is embedded in its execution because the two are read together and have a one-to-one bounded relationship. Trip outputs and execution history remain separate because execution history can grow without bound. Keep binary files out of Mongo documents to avoid the 16 MB BSON document limit. Do not create speculative bookings, notifications, API integration credential collections or itinerary collections before a concrete use case needs them. Store no provider secrets or payment credentials in MongoDB.

## API Surface

- `GET /api/health`: app, database and registry health; provider health reported separately and accurately.
- `GET /api/agents`, `GET /api/agents/{agent_id}`: dynamic agent metadata and form schemas.
- `POST /api/agents/{agent_id}/execute`: independent execution with trip/context and structured inputs.
- `GET/POST /api/trips`, `GET /api/trips/{trip_id}`: trip lifecycle and workflow entry point.
- `GET /api/executions/{execution_id}` and trip execution listing.
- `GET /api/validation/{execution_id}`: persisted validation result.
- `GET /api/errors`, `GET /api/errors/{error_id}`: execution failures and detail.
- `GET /api/reproduction`, `GET /api/reproduction/{case_id}`, `POST /api/reproduction/{case_id}/replay`: replay sanitized input through normal validation and capture comparison.
- `POST /api/documents`, `GET /api/documents`, `GET /api/documents/{document_id}`: size/type-limited safe upload and document metadata/results.

Every request receives or propagates a request ID. Authorization must be checked at trip/document/execution ownership boundaries; initial local development can use a clearly documented development auth adapter, not an unauthenticated production claim.

## Frontend Structure and Dynamic UI

The frontend fetches agent metadata and input schemas from the backend. A small set of generic field renderers supports text/number/date/select/multiselect/checkbox/file/array/object fields. Agent-specific UI is driven by schema and outputs, not a single hard-coded form. Pages include Dashboard, Trips, Create Trip, Agents, Documents, Validation Center, Activity and Settings as backed API capability becomes available.

Every async action has loading, empty, success, validation-warning and visible-error states. Validation checks and data source/status labels render from backend response fields. Responsive navigation and accessible labels/keyboard operation are required.

## External Providers and LLM

Define protocols for `WeatherProvider`, `MapsProvider`, `HotelProvider`, `TransportProvider`, `TourGuideProvider`, `InsuranceKnowledgeProvider`, `DocumentExtractor` and `LLMProvider`. Configure credentials only through environment variables and document each optional integration in `.env.example` and README. If no provider is configured, return a typed unavailable result. Do not substitute sample prices, current inventory, policy terms or forecasts. Local fixtures may be used in tests and must be explicitly marked fixture/test data.

LLM calls are optional and replaceable (local Ollama/open models first where installed; optional external trial/free tiers only when configured). Pydantic validates every structured LLM response. Core trip validation, arithmetic, orchestration and error capture must work without an LLM.

## Security and Document Handling

- Validate input with Pydantic and PyMongo query documents; never build raw query strings from user input.
- Restrict CORS to configured frontend origins.
- Keep secrets out of frontend bundles, logs, audit payloads and database records.
- Enforce upload extension, MIME/signature, size and safe generated storage names; do not execute uploaded content.
- Sanitize exception responses while retaining protected diagnostics in logs/reproduction records.
- Apply per-user ownership checks before reading trips, documents, executions or reproduction cases.
- Redact tokens, credentials and unnecessary personal/medical data from reproduction snapshots.

## Testing Strategy

- Unit: input/date/room rules, every agent schema, validator cases, finance arithmetic, retry classification/backoff and reproduction capture.
- API: agent metadata, execution, validation/error/reproduction persistence, upload rejection and health status.
- Integration: create trip -> execute agent -> validate -> persist -> retrieve; injected transient/permanent agent failures -> retry policy -> reproduction case.
- Frontend: dynamic schema form, required-field errors, execution/loading/error states and validation/error center.
- Provider tests use deterministic fixtures marked as test data. Live API tests are opt-in and never gate offline local setup.

## Decisions Needed Before Live Integration

- Resolve system airport radius (20 km user example, 30 km system orchestrator, 150 km Travel Planner example); retain trip-level configuration until then.
- Confirm whether max two travelers per room is universal or only a user constraint, versus hotel/provider-specific occupancy.
- Supply authorized provider credentials/terms for Google Weather/Maps, hotel, transport, tours and insurer sources if live results are required.
- Supply or confirm local LLM runtime/model; core operation must not depend on it.

## Implementation Order

1. Agent inventory and this architecture record.
2. Backend settings, MongoDB client/collection indexes and typed Pydantic contracts.
3. Deterministic Validator and tests before relying on agent-generated results.
4. Base agent, dynamic registry and orchestration with persisted execution audit.
5. Retry/circuit breaker and automatic reproduction capture.
6. Implement each prompt-defined agent and provider abstraction, preserving unavailable states.
7. Dynamic React UI, trip workflow, validation/error views and document upload.
8. End-to-end tests, local Docker Compose and setup documentation.