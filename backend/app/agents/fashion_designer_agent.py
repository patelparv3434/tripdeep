from datetime import date, timedelta

from app.agents.base import BaseAgent
from app.agents.registry import AGENTS_BY_ID
from app.core.config import get_settings
from app.integrations.cloudflare_ai import (
    generate_daily_style_notes as generate_cloud_style_notes,
)
from app.integrations.ollama import generate_daily_style_notes


class FashionDesignerAgent(BaseAgent):
    definition = AGENTS_BY_ID["fashion_designer"]

    async def execute(self, input_data: dict) -> dict:
        trip = input_data.get("trip", {})
        forecast = input_data.get("weather_forecast") or {}
        itinerary = input_data.get("itinerary_activities") or []
        forecasts_by_date = {
            item["date"]: item
            for item in forecast.get("daily_forecast", [])
            if item.get("forecast_available")
        }
        itinerary_by_date = {
            item["date"]: item
            for item in itinerary
            if item.get("date")
        }
        try:
            start = date.fromisoformat(str(trip["start_date"]))
            end = date.fromisoformat(str(trip["end_date"]))
        except (KeyError, ValueError):
            return {
                "agent": self.definition.id,
                "status": "needs_input",
                "day_wise_outfits": [],
                "packing_list": {"clothing": []},
                "warnings": ["Valid trip dates are required to prepare outfit suggestions."],
            }
        if end < start:
            return {
                "agent": self.definition.id,
                "status": "needs_input",
                "day_wise_outfits": [],
                "packing_list": {"clothing": []},
                "warnings": ["The trip end date must be on or after its start date."],
            }

        daily_outfits = []
        packing_items: set[str] = {"Comfortable walking shoes"}
        for day_offset in range((end - start).days + 1):
            day = (start + timedelta(days=day_offset)).isoformat()
            weather = forecasts_by_date.get(day)
            scheduled_day = itinerary_by_date.get(day, {})
            activities = scheduled_day.get("activities", [])
            outfit_items = []

            if weather:
                high = weather.get("high_c")
                low = weather.get("low_c")
                rain = weather.get("precipitation_probability_percent")
                if low is not None and low <= 10:
                    outfit_items.append("Warm base layer")
                    packing_items.add("Warm base layers")
                elif low is not None and low <= 17:
                    outfit_items.append("Light sweater or layer for cooler hours")
                    packing_items.add("Light sweater")
                if high is not None and high >= 28:
                    outfit_items.append("Breathable lightweight clothes")
                    packing_items.add("Breathable lightweight clothes")
                if rain is not None and rain >= 40:
                    outfit_items.extend(["Packable rain jacket", "Compact umbrella"])
                    packing_items.update(["Packable rain jacket", "Compact umbrella"])
                if not outfit_items:
                    outfit_items.append("Comfortable clothes suited to the forecast")
                outfit_items.append("Comfortable walking shoes")
            else:
                outfit_items.extend(
                    [
                        "Comfortable daywear",
                        "Weather-flexible layer; check the forecast closer to departure",
                        "Comfortable walking shoes",
                    ]
                )
                packing_items.add("Weather-flexible layer")

            activity_names = [
                str(activity.get("name", "Suggested stop"))
                for activity in activities
            ]
            if activity_names and any(
                word in str(activity.get("type", "")).casefold()
                for activity in activities
                for word in ("hiking", "trail", "nature", "viewpoint")
            ):
                outfit_items.append("Sturdy shoes for outdoor walking")
                packing_items.add("Sturdy outdoor shoes")

            weather_summary = "No forecast available for this date yet"
            if weather:
                low = weather.get("low_c")
                high = weather.get("high_c")
                weather_summary = weather.get("condition", "Conditions unavailable")
                if low is not None and high is not None:
                    weather_summary += f"; {low}–{high}°C"

            daily_outfits.append(
                {
                    "date": day,
                    "weather_available": weather is not None,
                    "weather_summary": weather_summary,
                    "activities": activity_names,
                    "outfit_items": list(dict.fromkeys(outfit_items)),
                }
            )

        forecast_days = len(forecasts_by_date)
        settings = get_settings()
        llm_warning = None
        llm_status = "not_configured"
        style_notes: dict[str, str] = {}
        cloud_model_days = [
            {
                "date": f"day-{index + 1}",
                "weather_summary": (
                    "forecast available"
                    if outfit["weather_available"]
                    else "forecast unavailable"
                ),
                "outfit_items": outfit["outfit_items"],
                "activity_types": [
                    str(activity.get("type", "activity"))
                    for activity in itinerary_by_date.get(outfit["date"], {}).get(
                        "activities", []
                    )
                ],
            }
            for index, outfit in enumerate(daily_outfits)
        ]
        if settings.llm_provider == "ollama":
            style_notes, llm_warning = await generate_daily_style_notes(
                daily_outfits,
                settings.ollama_base_url,
                settings.ollama_model,
                settings.ollama_timeout_seconds,
            )
        elif settings.llm_provider == "cloudflare_workers_ai" and trip.get(
            "cloud_ai_style_notes"
        ) is True:
            cloud_notes, llm_warning = await generate_cloud_style_notes(
                cloud_model_days,
                settings.cloudflare_account_id,
                settings.cloudflare_api_token,
                settings.cloudflare_ai_model,
                settings.ollama_timeout_seconds,
            )
            style_notes = {
                daily_outfits[index]["date"]: cloud_notes[f"day-{index + 1}"]
                for index in range(len(daily_outfits))
                if f"day-{index + 1}" in cloud_notes
            }
        elif settings.llm_provider == "cloudflare_workers_ai":
            llm_warning = (
                "Optional cloud style notes are off. Turn them on for this trip to generate notes from coarse weather and activity types only."
            )
        model_enabled = (
            settings.llm_provider == "ollama"
            or (
                settings.llm_provider == "cloudflare_workers_ai"
                and trip.get("cloud_ai_style_notes") is True
            )
        )
        if model_enabled:
            for outfit in daily_outfits:
                if outfit["date"] in style_notes:
                    outfit["style_note"] = style_notes[outfit["date"]]
            llm_status = (
                "generated"
                if len(style_notes) == len(daily_outfits)
                else "partial"
                if style_notes
                else "unavailable"
            )
            if style_notes and len(style_notes) != len(daily_outfits):
                llm_warning = (
                    "The AI model returned style notes for only some dates; "
                    "the other dates retain deterministic suggestions."
                )
        elif settings.llm_provider == "none":
            llm_warning = (
                "LLM_PROVIDER=none; rule-based clothing suggestions are shown."
            )

        warnings = []
        if forecast_days != len(daily_outfits):
            warnings.append(
                "Outfits for dates without a live forecast are general guidance; refresh the plan closer to departure."
            )
        if llm_warning:
            warnings.append(llm_warning)
        return {
            "agent": self.definition.id,
            "status": (
                "available"
                if forecast_days == len(daily_outfits)
                else "partial"
                if forecast_days
                else "general_guidance"
            ),
            "llm_status": llm_status,
            "day_wise_outfits": daily_outfits,
            "packing_list": {"clothing": sorted(packing_items)},
            "warnings": warnings,
            "sources": forecast.get("sources", []),
        }