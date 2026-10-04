from app.schemas.agents import AgentDefinition, InputField, InputSchema


def field(
    name: str,
    label: str,
    field_type: str = "text",
    required: bool = False,
    options: list[str] | None = None,
    description: str | None = None,
    minimum: float | None = None,
) -> InputField:
    return InputField(
        name=name,
        label=label,
        type=field_type,
        required=required,
        options=options or [],
        description=description,
        minimum=minimum,
    )


def definition(
    agent_id: str,
    name: str,
    description: str,
    fields: list[InputField],
    outputs: list[str],
    dependencies: list[str] | None = None,
    providers: list[str] | None = None,
        configured: bool = True,
) -> AgentDefinition:
    return AgentDefinition(
        id=agent_id,
        name=name,
        description=description,
        input_schema=InputSchema(fields=fields),
        supported_outputs=outputs,
        dependencies=dependencies or [],
        provider_requirements=providers or [],
        status="partially_available" if configured else "not_configured",
    )


AGENTS: list[AgentDefinition] = [
    definition("travel_planner", "Travel Planner Agent", "Coordinates specialist agents and consolidates a validated travel plan.", [field("origin", "Origin", required=True), field("destination", "Destination", required=True), field("start_date", "Start date", "date", True), field("end_date", "End date", "date", True), field("adults", "Adults", "number", True, minimum=1), field("children", "Children", "number", minimum=0), field("travel_mode", "Travel mode", "select", options=["Flight", "Train", "Bus", "By roads"])], ["feasibility", "execution_plan", "travel_plan"], ["validator", "weather"]),
    definition("validator", "Validator Agent", "Independently checks completeness, evidence, document status and cross-agent consistency.", [field("data", "Trip or document data", "object", True), field("required_fields", "Required field paths", "array"), field("agent_outputs", "Related agent outputs", "object"), field("applicable_rules", "Applicable rule identifiers", "array")], ["status", "checks", "missing_information", "evidence"], configured=True),
    definition("hotel", "Hotel Agent", "Finds and compares accommodation while preserving provider-confirmed availability and cancellation terms.", [field("destination", "Destination", required=True), field("check_in", "Check-in", "date", True), field("check_out", "Check-out", "date", True), field("adults", "Adults", "number", True, minimum=1), field("children", "Children", "array"), field("category", "Hotel category", "select", True, ["5 Star", "4 Star", "3 Star", "Villa", "Resorts"]), field("free_cancellation_required", "Cancellation required", "checkbox")], ["hotel_options", "room_requirement", "pricing", "cancellation"], ["finance", "validator"], ["authorized hotel API"]),
    definition("transportation", "Transportation Provider Agent", "Coordinates authorized flight, train, bus and multimodal provider searches.", [field("origin", "Origin", required=True), field("destination", "Destination", required=True), field("departure_date", "Departure date", "date", True), field("return_date", "Return date", "date"), field("travel_mode", "Travel mode", "select", True, ["Flight", "Train", "Bus", "Multi-modal"]), field("travelers", "Traveler details", "object", True)], ["provider_status", "options", "connections", "pricing", "policies"], ["finance", "validator"], ["authorized booking/GDS APIs"]),
    definition("weather", "Weather Agent", "Returns sourced forecast data and explicit limits for the requested dates.", [field("destination", "Destination", required=True), field("start_date", "Start date", "date", True), field("end_date", "End date", "date", True), field("coordinates", "Coordinates", "object")], ["forecast_status", "daily_forecast", "weather_policy"], ["stylist", "health", "tour_guide"], ["Open-Meteo public weather API"], configured=True),
    definition("tour_guide", "Tour Guide Agent", "Plans activities and validates guide/provider capacity, terms and source reliability.", [field("destination", "Destination", required=True), field("start_date", "Start date", "date", True), field("end_date", "End date", "date", True), field("travelers", "Traveler details", "object", True), field("preferences", "Activity preferences", "array")], ["guided_activities", "guide_options", "group_validation", "confidence"], ["finance", "stylist", "health"], ["authorized tour provider APIs"]),
    definition("insurance", "Travel Insurance Agent", "Compares policy information grounded in supplied policy documents or verified insurer sources.", [field("destination", "Destination", required=True), field("start_date", "Start date", "date", True), field("end_date", "End date", "date", True), field("travelers", "Traveler details", "object", True), field("coverage_requirements", "Coverage requirements", "array")], ["insurance_options", "coverage", "exclusions", "sources"], ["finance"], ["policy knowledge base / insurer source"]),
    definition("finance", "Finance Agent", "Calculates costs, budget position and cancellation exposure from verified specialist data.", [field("trip", "Trip summary", "object", True), field("verified_agent_data", "Verified agent outputs", "object", True), field("budget", "Budget", "object"), field("payment_method", "Payment method", "select", options=["Credit Card", "Debit Card", "UPI", "Cash", "Bank Transfer", "Other"])], ["cost_breakdown", "totals", "budget_check", "payment_plan", "risks"], ["travel_planner", "hotel", "transportation", "tour_guide", "insurance"]),
    definition("fashion_designer", "Fashion Designer / Stylist Agent", "Creates weather- and activity-aware clothing and packing recommendations.", [field("trip", "Trip details", "object", True), field("weather_forecast", "Weather output", "object"), field("itinerary_activities", "Activities", "array"), field("health_flags", "Health flags", "array"), field("traveler_profiles", "Traveler profiles", "array")], ["day_wise_outfits", "packing_list"], ["weather", "tour_guide", "health", "dietitian", "finance"]),
    definition("document", "Document Agent", "Extracts, organizes, summarizes and tracks travel documents without inventing their contents.", [field("operation", "Operation", "select", True, ["upload", "summarize", "extract", "checklist", "lookup"]), field("document", "Document", "file"), field("trip_id", "Trip ID")], ["summary", "extracted_fields", "checklist", "document_status"], ["validator"], ["local parser/OCR"]),
    definition("health", "Health Agent", "Provides general travel-health preparation and separates sourced facts from general guidance.", [field("trip", "Trip details", "object", True), field("weather", "Weather output", "object"), field("activities", "Activities", "array"), field("food_preference", "Food preference")], ["health_summary", "medical_kit", "risks", "handoff"], ["weather", "tour_guide", "dietitian", "insurance"]),
    definition("dietitian", "Dietitian Agent", "Plans Jain meals only and gates plans on child ages, allergy confirmation and menu checks.", [field("trip", "Trip details", "object", True), field("child_ages", "Child ages", "array", True), field("allergies_confirmed", "Allergies confirmed", "checkbox", True), field("weather_context", "Weather context", "object"), field("local_food_context", "Local food context", "object")], ["status", "rtcco", "days", "confidence"], ["weather", "hotel", "finance"], ["local food lookup"]),
]

AGENTS_BY_ID = {agent.id: agent for agent in AGENTS}