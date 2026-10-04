import asyncio
import json
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock

from app.agents.fashion_designer_agent import FashionDesignerAgent
from app.agents.hotel_agent import HotelAgent
from app.agents.weather_agent import WeatherAgent
from app.integrations.cloudflare_ai import (
    generate_daily_style_notes as generate_cloud_style_notes,
)
from app.integrations.ollama import generate_daily_style_notes


def test_weather_marks_every_selected_date_and_limits_live_request(monkeypatch) -> None:
    today = datetime.now(timezone.utc).date()
    start = today + timedelta(days=14)
    end = today + timedelta(days=16)
    mock_weather = AsyncMock(
        return_value=(
            {
                "daily": {
                    "time": [start.isoformat(), (start + timedelta(days=1)).isoformat()],
                    "weather_code": [1, 2],
                    "temperature_2m_max": [24, 25],
                    "temperature_2m_min": [14, 15],
                    "precipitation_probability_max": [10, 20],
                    "wind_speed_10m_max": [8, 9],
                }
            },
            None,
        )
    )
    monkeypatch.setattr("app.agents.weather_agent.get_destination_weather", mock_weather)

    result = asyncio.run(
        WeatherAgent().execute(
            {
                "destination": "Munnar",
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "location": {
                    "name": "Munnar",
                    "latitude": 10.08,
                    "longitude": 77.06,
                    "timezone": "Asia/Kolkata",
                },
            }
        )
    )

    assert mock_weather.await_args.args[1:] == (
        start.isoformat(),
        (today + timedelta(days=15)).isoformat(),
    )
    assert [day["date"] for day in result["daily_forecast"]] == [
        (start + timedelta(days=offset)).isoformat() for offset in range(3)
    ]
    assert result["forecast_status"] == "PARTIAL"
    assert result["daily_forecast"][-1]["forecast_available"] is False


def test_fashion_recommendations_use_each_days_weather_and_itinerary() -> None:
    first_day = date(2026, 11, 8)
    second_day = first_day + timedelta(days=1)

    result = asyncio.run(
        FashionDesignerAgent().execute(
            {
                "trip": {
                    "start_date": first_day.isoformat(),
                    "end_date": second_day.isoformat(),
                },
                "weather_forecast": {
                    "daily_forecast": [
                        {
                            "date": first_day.isoformat(),
                            "forecast_available": True,
                            "condition": "Rain",
                            "low_c": 8,
                            "high_c": 19,
                            "precipitation_probability_percent": 80,
                        },
                        {
                            "date": second_day.isoformat(),
                            "forecast_available": False,
                        },
                    ]
                },
                "itinerary_activities": [
                    {
                        "date": first_day.isoformat(),
                        "activities": [{"name": "Munnar Museum", "type": "museum"}],
                    },
                    {"date": second_day.isoformat(), "activities": []},
                ],
            }
        )
    )

    assert len(result["day_wise_outfits"]) == 2
    first_outfit, second_outfit = result["day_wise_outfits"]
    assert first_outfit["activities"] == ["Munnar Museum"]
    assert "Warm base layer" in first_outfit["outfit_items"]
    assert "Packable rain jacket" in first_outfit["outfit_items"]
    assert second_outfit["weather_available"] is False
    assert "Weather-flexible layer; check the forecast closer to departure" in second_outfit["outfit_items"]


def test_hotel_rating_preference_excludes_unrated_listings(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.agents.hotel_agent.find_nearby_places",
        AsyncMock(
            return_value=(
                [
                    {"name": "Tagged four star", "type": "hotel", "star_rating": "4"},
                    {"name": "Tagged three star", "type": "hotel", "star_rating": "3"},
                    {"name": "Unrated guest house", "type": "guest_house", "star_rating": None},
                ],
                None,
            )
        ),
    )

    result = asyncio.run(
        HotelAgent().execute(
            {
                "destination": "Munnar",
                "check_in": "2026-11-08",
                "check_out": "2026-11-10",
                "adults": 2,
                "category": "4 Star",
                "location": {
                    "name": "Munnar",
                    "latitude": 10.08,
                    "longitude": 77.06,
                    "timezone": "Asia/Kolkata",
                },
            }
        )
    )

    assert [hotel["name"] for hotel in result["hotels"]] == ["Tagged four star"]


def test_ollama_style_notes_are_limited_to_requested_trip_dates(monkeypatch) -> None:
    requested_day = "2026-11-08"

    class MockResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "message": {
                    "content": json.dumps(
                        {
                            "days": [
                                {"date": requested_day, "style_note": "Use a light rain layer."},
                                {"date": "2099-01-01", "style_note": "Invented date."},
                            ]
                        }
                    )
                }
            }

    class MockClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def post(self, _url: str, json: dict) -> MockResponse:
            assert json["model"] == "qwen2.5:3b"
            assert json["format"] == "json"
            return MockResponse()

    monkeypatch.setattr("app.integrations.ollama.httpx.AsyncClient", MockClient)

    notes, warning = asyncio.run(
        generate_daily_style_notes(
            [{"date": requested_day, "outfit_items": ["Packable rain jacket"]}],
            "http://127.0.0.1:11434",
            "qwen2.5:3b",
            25,
        )
    )

    assert notes == {requested_day: "Use a light rain layer."}
    assert warning is None


def test_cloud_ai_receives_coarse_trip_context_only_when_user_opted_in(monkeypatch) -> None:
    travel_day = (date.today() + timedelta(days=7)).isoformat()
    captured_days: list[dict] = []

    async def mock_generate(days, *_args):
        captured_days.extend(days)
        return {"day-1": "Choose layers suitable for a museum visit."}, None

    monkeypatch.setattr(
        "app.agents.fashion_designer_agent.get_settings",
        lambda: type(
            "Settings",
            (),
            {
                "llm_provider": "cloudflare_workers_ai",
                "cloudflare_account_id": "test-account",
                "cloudflare_api_token": "test-token",
                "cloudflare_ai_model": "@cf/meta/llama-3.1-8b-instruct",
                "ollama_timeout_seconds": 25,
            },
        )(),
    )
    monkeypatch.setattr(
        "app.agents.fashion_designer_agent.generate_cloud_style_notes",
        mock_generate,
    )

    result = asyncio.run(
        FashionDesignerAgent().execute(
            {
                "trip": {
                    "origin": "Ahmedabad",
                    "destination": "Munnar",
                    "start_date": travel_day,
                    "end_date": travel_day,
                    "cloud_ai_style_notes": True,
                },
                "weather_forecast": {
                    "daily_forecast": [
                        {
                            "date": travel_day,
                            "forecast_available": True,
                            "condition": "Rain",
                            "low_c": 12,
                            "high_c": 20,
                            "precipitation_probability_percent": 80,
                        }
                    ]
                },
                "itinerary_activities": [
                    {
                        "date": travel_day,
                        "activities": [
                            {"name": "Private itinerary place", "type": "museum"}
                        ],
                    }
                ],
            }
        )
    )

    assert captured_days == [
        {
            "date": "day-1",
            "weather_summary": "forecast available",
            "outfit_items": [
                "Light sweater or layer for cooler hours",
                "Packable rain jacket",
                "Compact umbrella",
                "Comfortable walking shoes",
            ],
            "activity_types": ["museum"],
        }
    ]
    assert "Private itinerary place" not in str(captured_days)
    assert travel_day not in str(captured_days)
    assert "Munnar" not in str(captured_days)
    assert result["day_wise_outfits"][0]["style_note"] == "Choose layers suitable for a museum visit."


def test_cloudflare_style_response_is_limited_to_supplied_day_labels(monkeypatch) -> None:
    class MockResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "result": {
                    "response": json.dumps(
                        {
                            "days": [
                                {"date": "day-1", "style_note": "Use comfortable layers."},
                                {"date": "day-99", "style_note": "Unrequested day."},
                            ]
                        }
                    )
                }
            }

    class MockClient:
        def __init__(self, timeout: float) -> None:
            assert timeout == 25

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args) -> None:
            return None

        async def post(self, url: str, headers: dict, json: dict) -> MockResponse:
            assert url.endswith("/accounts/account-id/ai/run/@cf/meta/llama-3.1-8b-instruct")
            assert headers == {"Authorization": "Bearer server-only-test-token"}
            assert json["messages"][1]["content"].find("day-1") >= 0
            return MockResponse()

    monkeypatch.setattr(
        "app.integrations.cloudflare_ai.httpx.AsyncClient", MockClient
    )
    notes, warning = asyncio.run(
        generate_cloud_style_notes(
            [{"date": "day-1", "weather_summary": "forecast available"}],
            "account-id",
            "server-only-test-token",
            "@cf/meta/llama-3.1-8b-instruct",
            25,
        )
    )
    assert notes == {"day-1": "Use comfortable layers."}
    assert warning is None
