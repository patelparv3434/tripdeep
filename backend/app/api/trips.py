from uuid import uuid4
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo import DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.agents.factory import AGENT_FACTORIES
from app.api.dependencies import get_current_user, get_db
from app.integrations.public_travel_data import resolve_destination
from app.schemas.trips import (
    TripCreateRequest,
    TripResponse,
    TripWorkflowRequest,
)
from app.services.agent_executor import execute_agent
from app.services.trip_service import create_trip

router = APIRouter(prefix="/trips", tags=["trips"])


def agent_context(trip_request: dict, agent_id: str) -> dict:
    travelers = {
        "adults": trip_request.get("adults", 0),
        "children": trip_request.get("children", 0),
        "child_ages": trip_request.get("child_ages", []),
        "total": trip_request.get("total_travelers", 0),
    }
    contexts = {
        "hotel": {"destination": trip_request.get("destination"), "check_in": trip_request.get("start_date"), "check_out": trip_request.get("end_date"), "adults": travelers["adults"], "children": travelers["child_ages"], "category": trip_request.get("hotel_category"), "location": trip_request.get("location")},
        "transportation": {"origin": trip_request.get("origin"), "destination": trip_request.get("destination"), "departure_date": trip_request.get("start_date"), "return_date": trip_request.get("end_date"), "travel_mode": trip_request.get("travel_mode"), "travelers": travelers},
        "weather": {"destination": trip_request.get("destination"), "start_date": trip_request.get("start_date"), "end_date": trip_request.get("end_date"), "location": trip_request.get("location")},
        "tour_guide": {"destination": trip_request.get("destination"), "start_date": trip_request.get("start_date"), "end_date": trip_request.get("end_date"), "travelers": travelers, "location": trip_request.get("location")},
        "insurance": {"destination": trip_request.get("destination"), "start_date": trip_request.get("start_date"), "end_date": trip_request.get("end_date"), "travelers": travelers},
        "finance": {"trip": trip_request, "verified_agent_data": {}, "budget": trip_request.get("budget")},
        "fashion_designer": {"trip": trip_request, "weather_forecast": trip_request.get("weather_forecast"), "itinerary_activities": trip_request.get("itinerary_activities", [])},
        "health": {"trip": trip_request, "weather": trip_request.get("weather_forecast"), "activities": trip_request.get("itinerary_activities", []), "food_preference": trip_request.get("food_preference")},
        "dietitian": {"trip": trip_request, "child_ages": trip_request.get("child_ages", []), "allergies_confirmed": False},
        "document": {"operation": "checklist", "trip": trip_request},
        "travel_planner": {"origin": trip_request.get("origin"), "destination": trip_request.get("destination"), "start_date": trip_request.get("start_date"), "end_date": trip_request.get("end_date"), "travel_mode": trip_request.get("travel_mode"), "food_preference": trip_request.get("food_preference")},
    }
    return contexts.get(agent_id, {})


def trip_response(document: dict) -> TripResponse:
    return TripResponse(
        id=document["_id"],
        title=document["title"],
        origin=document["origin"],
        destination=document["destination"],
        start_date=document.get("start_date"),
        end_date=document.get("end_date"),
        status=document["status"],
        request_data=document["request_data"],
    )


def _build_itinerary(
    trip: dict,
    places: list[dict],
    daily_forecast: list[dict],
) -> list[dict]:
    start = date.fromisoformat(str(trip["start_date"]))
    end = date.fromisoformat(str(trip["end_date"]))
    days = [
        start + timedelta(days=offset)
        for offset in range((end - start).days + 1)
    ]
    if not days:
        return []

    places_by_day: list[list[dict]] = [[] for _ in days]
    for index, place in enumerate(places[: len(days) * 2]):
        day_index = index % len(days)
        places_by_day[day_index].append(place)

    forecast_by_date = {item["date"]: item for item in daily_forecast}
    itinerary = []
    for day_index, travel_date in enumerate(days):
        forecast = forecast_by_date.get(travel_date.isoformat(), {})
        activities = places_by_day[day_index]
        rain_probability = forecast.get("precipitation_probability_percent")
        if rain_probability is not None and rain_probability >= 50:
            activities.sort(
                key=lambda place: str(place.get("type", "")).casefold()
                not in {"museum", "gallery", "aquarium"}
            )
        scheduled = [
            {
                "name": place.get("name", "Suggested place"),
                "type": place.get("type"),
                "source": place.get("source"),
                "time_of_day": "Morning" if activity_index == 0 else "Afternoon",
                "notes": "Suggested stop; check opening hours, admission and travel time before visiting.",
            }
            for activity_index, place in enumerate(activities)
        ]
        itinerary.append(
            {
                "date": travel_date.isoformat(),
                "day_number": day_index + 1,
                "title": f"Day {day_index + 1} in {trip.get('destination', 'your destination')}",
                "activities": scheduled,
                "weather_summary": (
                    forecast.get("condition")
                    if forecast.get("forecast_available")
                    else "Forecast not available yet"
                ),
                "rain_probability_percent": forecast.get(
                    "precipitation_probability_percent"
                ),
                "notes": (
                    "Keep this day flexible; no named place listing was available."
                    if not scheduled
                    else "Suggested order only; opening hours and travel times are not verified."
                ),
            }
        )
    return itinerary


@router.get("")
async def list_trips(
    database: AsyncDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, object]:
    trips = await database.trips.find({"user_id": user["_id"]}).sort("created_at", DESCENDING).to_list(length=500)
    return {"trips": [trip_response(trip).model_dump(mode="json") for trip in trips], "total": len(trips)}


@router.post("", response_model=TripResponse, status_code=201)
async def post_trip(
    payload: TripCreateRequest,
    request: Request,
    database: AsyncDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> TripResponse:
    try:
        trip = await create_trip(
            database,
            payload,
            getattr(request.state, "request_id", str(uuid4())),
            user,
        )
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return trip_response(trip)


@router.get("/{trip_id}", response_model=TripResponse)
async def get_trip(
    trip_id: str,
    database: AsyncDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> TripResponse:
    trip = await database.trips.find_one({"_id": trip_id, "user_id": user["_id"]})
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip_response(trip)


@router.get("/{trip_id}/plan")
async def get_trip_plan(
    trip_id: str,
    database: AsyncDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, object]:
    trip = await database.trips.find_one({"_id": trip_id, "user_id": user["_id"]})
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    if not trip.get("plan"):
        raise HTTPException(status_code=404, detail="A plan has not been created for this trip")
    return {"trip_id": trip_id, "plan": trip["plan"]}


@router.post("/{trip_id}/plan")
async def run_trip_workflow(
    trip_id: str,
    request: Request,
    payload: TripWorkflowRequest | None = None,
    database: AsyncDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, object]:
    trip = await database.trips.find_one({"_id": trip_id, "user_id": user["_id"]})
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    trip_request = trip["request_data"]
    executions = []
    outputs: dict[str, dict] = {}
    request_id = getattr(request.state, "request_id", str(uuid4()))
    location, location_error = await resolve_destination(
        str(trip_request.get("destination", ""))
    )
    trip_request = {**trip_request, "location": location}
    planning_result = await execute_agent(
        database,
        "travel_planner",
        agent_context(trip_request, "travel_planner"),
        request_id,
        trip_id,
        user["_id"],
    )
    if planning_result.get("status") != "completed":
        raise HTTPException(
            status_code=503,
            detail="The trip could not be planned. Please retry in a moment.",
        )
    outputs["travel_planner"] = planning_result["output"]
    attached_documents = await database.documents.find(
        {"trip_id": trip_id, "user_id": user["_id"]}
    ).sort("created_at", DESCENDING).to_list(length=100)
    attached_document_summaries = [
        {
            "id": document["_id"],
            "original_name": document["original_name"],
            "media_type": document["media_type"],
            "status": document.get("status", "unknown"),
            "document_type": document.get("document_type"),
        }
        for document in attached_documents
    ]
    if payload is None:
        selected_agents = (
            planning_result.get("output", {}).get("selected_specialists", [])
        )
    else:
        selected_agents = [item.agent_id for item in payload.agents]

    for selected_id in selected_agents:
        if selected_id == "validator":
            raise HTTPException(status_code=400, detail="Validator runs automatically after selected agents")
        if selected_id not in AGENT_FACTORIES:
            raise HTTPException(status_code=404, detail=f"Unknown agent: {selected_id}")
        input_data = agent_context(trip_request, selected_id)
        if selected_id == "weather":
            input_data["location"] = location
        if selected_id in {"hotel", "tour_guide"}:
            input_data["location"] = location
        if selected_id == "fashion_designer":
            input_data["weather_forecast"] = outputs.get("weather")
            input_data["itinerary_activities"] = _build_itinerary(
                trip_request,
                outputs.get("tour_guide", {}).get("guided_activities", []),
                outputs.get("weather", {}).get("daily_forecast", []),
            )
        if selected_id == "health":
            input_data["weather"] = outputs.get("weather")
            input_data["activities"] = outputs.get("tour_guide", {}).get("guided_activities", [])
        if selected_id == "dietitian":
            input_data["weather_context"] = outputs.get("weather")
        if selected_id == "finance":
            input_data["verified_agent_data"] = {
                "specialist_outputs": {
                    key: value
                    for key, value in outputs.items()
                    if key in {"hotel", "transportation", "tour_guide", "insurance"}
                },
                "line_items": [],
            }
        if selected_id == "finance":
            input_data["trip"] = trip_request
        if payload is not None:
            selected_input = next(
                item.input_data for item in payload.agents if item.agent_id == selected_id
            )
            input_data.update(selected_input)
        if selected_id in {"document", "insurance"}:
            input_data["attached_documents"] = attached_document_summaries
        result = await execute_agent(
            database, selected_id, input_data, request_id, trip_id, user["_id"]
        )
        executions.append(result)
        if result.get("output"):
            outputs[selected_id] = result["output"]

    validator_input = {
        "data": trip_request,
        "agent_outputs": outputs,
        "required_fields": ["origin", "destination", "start_date", "end_date", "adults", "children"],
        "applicable_rules": ["cross_agent_consistency"],
    }
    final_validation = await execute_agent(
        database, "validator", validator_input, request_id, trip_id, user["_id"]
    )
    trip_status = "needs_review" if final_validation.get("validation_status") != "PASS" else "validated"
    now = datetime.now(timezone.utc)
    await database.trips.update_one({"_id": trip_id}, {"$set": {"status": trip_status, "updated_at": now}})
    await database.audit_logs.insert_one({
        "_id": str(uuid4()), "request_id": request_id, "trip_id": trip_id,
        "action": "trip_workflow_completed", "entity_type": "trip", "entity_id": trip_id,
        "details": {"validation_status": final_validation.get("validation_status")}, "created_at": now,
    })
    if payload is None:
        await database.trips.update_one(
            {"_id": trip_id},
            {"$set": {"plan": _present_plan(trip_request, outputs, location_error)}},
        )
        return {
            "trip_id": trip_id,
            "status": trip_status,
            "plan": _present_plan(trip_request, outputs, location_error),
        }
    return {"trip_id": trip_id, "status": trip_status, "executions": executions, "final_validation": final_validation}


def _present_plan(
    trip: dict,
    outputs: dict[str, dict],
    location_error: str | None,
) -> dict[str, object]:
    destination = trip.get("destination", "your destination")
    weather = outputs.get("weather", {})
    hotels = outputs.get("hotel", {})
    activities = outputs.get("tour_guide", {})
    transport = outputs.get("transportation", {})
    insurance = outputs.get("insurance", {})
    document_output = outputs.get("document", {})
    finance = outputs.get("finance", {})
    health = outputs.get("health", {})
    stylist = outputs.get("fashion_designer", {})
    itinerary = _build_itinerary(
        trip,
        activities.get("guided_activities", []),
        weather.get("daily_forecast", []),
    )
    forecast_days = weather.get("daily_forecast", [])
    available_forecast_days = sum(
        day.get("forecast_available", True) for day in forecast_days
    )
    weather_summary = (
        f"Destination forecast available for {available_forecast_days} of "
        f"{len(forecast_days)} selected travel days."
        if forecast_days
        else (weather.get("warnings") or ["Weather forecast is unavailable."])[0]
    )

    sections: list[dict[str, object]] = [
        {
            "id": "weather",
            "title": "Weather forecast",
            "status": weather.get("forecast_status", "NOT_AVAILABLE"),
            "summary": weather_summary,
            "items": weather.get("daily_forecast", []),
            "sources": weather.get("sources", []),
            "updated_at": weather.get("retrieved_at"),
        },
        {
            "id": "hotels",
            "title": "Places to stay",
            "status": hotels.get("status", "not_available"),
            "summary": (
                (hotels.get("warnings") or ["Nearby map listings."])[0]
                if hotels.get("hotels")
                else (hotels.get("warnings") or ["No hotel listings were found."])[0]
            ),
            "items": hotels.get("hotels", []),
            "sources": hotels.get("sources", []),
            "updated_at": hotels.get("retrieved_at"),
        },
        {
            "id": "transport",
            "title": "Getting there",
            "status": transport.get("status", "not_configured"),
            "summary": (
                "Live schedules, ticket prices and availability require a connected booking provider."
                if not transport.get("options")
                else "Provider-supplied transport options."
            ),
            "items": transport.get("options", []),
            "sources": transport.get("sources", []),
        },
        {
            "id": "activities",
            "title": "Places to explore",
            "status": activities.get("status", "not_available"),
            "summary": (
                "Map-listed attractions; opening hours, admission prices and tour availability are not confirmed."
                if activities.get("guided_activities")
                else (activities.get("warnings") or ["No attraction listings were found."])[0]
            ),
            "items": activities.get("guided_activities", []),
            "sources": activities.get("sources", []),
        },
        {
            "id": "itinerary",
            "title": "Suggested day-by-day itinerary",
            "status": "available" if activities.get("guided_activities") else "partial",
            "summary": (
                "Map-listed places are distributed across your selected dates. Confirm opening hours, admission and travel time before visiting."
                if activities.get("guided_activities")
                else "Your travel dates are laid out below; no sourced attraction listings were available, so keep the days flexible."
            ),
            "items": itinerary,
            "sources": activities.get("sources", []),
        },
        {
            "id": "packing",
            "title": "Travel essentials",
            "status": health.get("status", stylist.get("status", "general_guidance")),
            "summary": "General preparation advice. This is not medical advice.",
            "items": health.get("medical_kit", []),
            "sources": health.get("sources", []),
        },
        {
            "id": "clothing",
            "title": "Clothing suggestions",
            "status": stylist.get("status", "general_guidance"),
            "summary": (
                "AI-generated supplementary styling notes were added from limited weather and activity data. Forecast values and place listings remain sourced data."
                if stylist.get("llm_status") == "generated"
                else (
                    "The AI model added styling notes for some days; other days use rule-based suggestions. "
                    + " ".join(stylist.get("warnings", []))
                    if stylist.get("llm_status") == "partial"
                    else "Rule-based clothing suggestions follow your forecast and itinerary. "
                    + " ".join(stylist.get("warnings", []))
                )
            ),
            "items": stylist.get("day_wise_outfits", []),
            "details": stylist.get("packing_list", {}),
            "sources": stylist.get("sources", []),
        },
        {
            "id": "budget",
            "title": "Trip budget",
            "status": finance.get("status", "partial"),
            "summary": (
                f"Verified cost total: {finance.get('totals', {}).get('grand_total')} {finance.get('currency', '')}"
                if finance.get("totals", {}).get("grand_total") not in (None, "0")
                else "No verified provider prices are available yet, so a trip total cannot be calculated."
            ),
            "items": finance.get("cost_breakdown", []),
            "sources": finance.get("sources", []),
        },
        {
            "id": "documents",
            "title": "Travel documents",
            "status": document_output.get("status", "needs_input"),
            "summary": (
                "Attached documents are listed below. Check each original file; filenames and extraction status do not verify validity."
                if document_output.get("documents")
                else "No documents are linked to this trip yet. Upload documents and associate them with this trip to see them here."
            ),
            "items": document_output.get("checklist", []),
            "details": {"attached_documents": document_output.get("documents", [])},
            "sources": document_output.get("sources", []),
        },
        {
            "id": "insurance",
            "title": "Travel cover",
            "status": insurance.get("status", "needs_information"),
            "summary": (
                "Possible policy document(s) are attached; coverage and exclusions still need review with the insurer."
                if insurance.get("policy_documents")
                else "No policy details or verified insurer offers are available. Attach a policy or confirm cover directly with an insurer."
            ),
            "items": insurance.get("policy_documents", insurance.get("insurance_options", [])),
            "sources": insurance.get("sources", []),
        },
    ]
    if trip.get("food_preference"):
        food = outputs.get("dietitian", {})
        sections.append(
            {
                "id": "food",
                "title": "Food preferences",
                "status": food.get("status", "guidance_only"),
                "summary": (
                    (food.get("warnings") or food.get("missing_information") or [
                        "Menus and dietary accommodations need to be confirmed with the restaurant."
                    ])[0]
                ),
                "items": food.get("days", []),
                "sources": food.get("sources", []),
            }
        )

    return {
        "title": f"Your trip to {destination}",
        "origin": trip.get("origin"),
        "destination": destination,
        "start_date": trip.get("start_date"),
        "end_date": trip.get("end_date"),
        "traveler_count": trip.get("total_travelers"),
        "location_warning": location_error,
        "sections": sections,
    }


@router.get("/{trip_id}/executions")
async def list_trip_executions(
    trip_id: str,
    database: AsyncDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, object]:
    if await database.trips.find_one({"_id": trip_id, "user_id": user["_id"]}) is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    executions = await database.agent_executions.find({"trip_id": trip_id}).sort("created_at", DESCENDING).to_list(length=500)
    return {"executions": [{"id": item["_id"], "agent_id": item["agent_id"], "status": item["status"], "validation_status": item.get("validation_status"), "retry_count": item.get("retry_count", 0), "created_at": item.get("created_at")} for item in executions], "total": len(executions)}