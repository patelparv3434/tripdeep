from app.agents.registry import AGENTS_BY_ID
from app.integrations.public_travel_data import (
    get_destination_weather,
    resolve_destination,
)
from app.agents.base import BaseAgent
from datetime import date, datetime, timedelta, timezone


class WeatherAgent(BaseAgent):
    definition = AGENTS_BY_ID["weather"]

    async def execute(self, input_data: dict) -> dict:
        destination = str(input_data.get("destination", ""))
        location = input_data.get("location")
        if not location:
            location, location_error = await resolve_destination(destination)
            if location is None:
                return self._unavailable(location_error or "Destination lookup failed.")

        start_date = str(input_data.get("start_date", ""))
        end_date = str(input_data.get("end_date", ""))
        try:
            start = date.fromisoformat(start_date)
            end = date.fromisoformat(end_date)
        except ValueError:
            return self._unavailable("Valid start and end dates are required for the forecast.")

        if end < start:
            return self._unavailable("End date must be on or after the start date.", location)

        today = datetime.now(timezone.utc).date()
        forecast_limit = today + timedelta(days=15)
        requested_dates = [
            start + timedelta(days=offset)
            for offset in range((end - start).days + 1)
        ]
        forecast_start = max(start, today)
        forecast_end = min(end, forecast_limit)
        forecast_error = None
        daily: dict = {}
        if forecast_start <= forecast_end:
            forecast, forecast_error = await get_destination_weather(
                location,
                forecast_start.isoformat(),
                forecast_end.isoformat(),
            )
            if forecast is not None:
                daily = forecast.get("daily", {}) or {}

        forecasts_by_date = {
            forecast_date: {
                "date": forecast_date,
                "forecast_available": True,
                "condition": self._condition(
                    self._value_at(daily, "weather_code", index)
                ),
                "high_c": self._value_at(daily, "temperature_2m_max", index),
                "low_c": self._value_at(daily, "temperature_2m_min", index),
                "precipitation_probability_percent": self._value_at(
                    daily, "precipitation_probability_max", index
                ),
                "wind_speed_kmh": self._value_at(
                    daily, "wind_speed_10m_max", index
                ),
            }
            for index, forecast_date in enumerate(daily.get("time", []))
            if forecast_start.isoformat() <= forecast_date <= forecast_end.isoformat()
        }
        forecasts = [
            forecasts_by_date.get(
                requested_date.isoformat(),
                {
                    "date": requested_date.isoformat(),
                    "forecast_available": False,
                    "condition": "Forecast not available yet",
                    "high_c": None,
                    "low_c": None,
                    "precipitation_probability_percent": None,
                    "wind_speed_kmh": None,
                },
            )
            for requested_date in requested_dates
        ]
        available_count = sum(day["forecast_available"] for day in forecasts)
        if available_count == len(forecasts):
            status = "available"
            forecast_status = "AVAILABLE"
            data_status = "LIVE"
        elif available_count:
            status = "partial"
            forecast_status = "PARTIAL"
            data_status = "PARTIAL"
        else:
            status = "partial"
            forecast_status = "NOT_AVAILABLE"
            data_status = "UNAVAILABLE"

        warnings = []
        if start < today:
            warnings.append("Past dates are not forecast by the live forecast service.")
        if end > forecast_limit:
            warnings.append(
                "Dates more than 16 days ahead are listed without invented weather; forecasts may become available closer to departure."
            )
        if forecast_error:
            warnings.append(forecast_error)
        missing_provider_dates = [
            day["date"]
            for day in forecasts
            if not day["forecast_available"]
            and today <= date.fromisoformat(day["date"]) <= forecast_limit
        ]
        if missing_provider_dates and not forecast_error:
            warnings.append(
                "The weather provider did not return data for: "
                + ", ".join(missing_provider_dates)
                + "."
            )

        return {
            "agent": self.definition.id,
            "status": status,
            "forecast_status": forecast_status,
            "daily_forecast": forecasts,
            "location": location,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "data_status": data_status,
            "warnings": warnings,
            "sources": ["https://open-meteo.com/"],
        }

    @staticmethod
    def _value_at(daily: dict, key: str, index: int):
        values = daily.get(key, [])
        return values[index] if index < len(values) else None

    @staticmethod
    def _condition(code: int | None) -> str:
        if code is None:
            return "Condition unavailable"
        if code == 0:
            return "Clear"
        if code in {1, 2, 3}:
            return "Mainly clear" if code == 1 else "Partly cloudy" if code == 2 else "Overcast"
        if code in {45, 48}:
            return "Fog"
        if code in {51, 53, 55, 56, 57}:
            return "Drizzle"
        if code in {61, 63, 65, 66, 67, 80, 81, 82}:
            return "Rain"
        if code in {71, 73, 75, 77, 85, 86}:
            return "Snow"
        if code in {95, 96, 99}:
            return "Thunderstorm"
        return "Variable conditions"

    @staticmethod
    def _unavailable(message: str, location: dict | None = None) -> dict:
        return {
            "agent": "weather",
            "status": "partial",
            "forecast_status": "NOT_AVAILABLE",
            "daily_forecast": [],
            "location": location,
            "retrieved_at": datetime.now(timezone.utc).isoformat(),
            "data_status": "UNAVAILABLE",
            "warnings": [message],
            "sources": ["https://open-meteo.com/"],
        }