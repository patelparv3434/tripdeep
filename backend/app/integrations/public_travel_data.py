from datetime import datetime, timezone
from typing import Any

import httpx


OPEN_METEO_GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "TripdeepTravelPlanner/1.0 (non-commercial travel planning)"


async def resolve_destination(destination: str) -> tuple[dict[str, Any] | None, str | None]:
    try:
        async with httpx.AsyncClient(
            timeout=10,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(
                OPEN_METEO_GEOCODING_URL,
                params={"name": destination, "count": 1, "language": "en", "format": "json"},
            )
            response.raise_for_status()
            results = response.json().get("results", [])
    except (httpx.HTTPError, ValueError) as error:
        return None, f"Destination lookup failed: {error}"

    if not results:
        return None, f"No matching destination was found for {destination}."

    result = results[0]
    return {
        "name": result.get("name", destination),
        "country": result.get("country"),
        "latitude": result["latitude"],
        "longitude": result["longitude"],
        "timezone": result.get("timezone", "auto"),
    }, None


async def get_destination_weather(
    location: dict[str, Any],
    start_date: str,
    end_date: str,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        async with httpx.AsyncClient(
            timeout=12,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(
                OPEN_METEO_FORECAST_URL,
                params={
                    "latitude": location["latitude"],
                    "longitude": location["longitude"],
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
                    "start_date": start_date,
                    "end_date": end_date,
                    "timezone": location.get("timezone", "auto"),
                },
            )
            response.raise_for_status()
            return response.json(), None
    except (httpx.HTTPError, KeyError, ValueError) as error:
        return None, f"Forecast lookup failed: {error}"


async def find_nearby_places(
    location: dict[str, Any],
    place_type: str,
    radius_meters: int = 8000,
) -> tuple[list[dict[str, Any]], str | None]:
    if place_type == "accommodation":
        tag_filter = '["tourism"~"hotel|guest_house|hostel|motel|resort|apartment"]'
    elif place_type == "attraction":
        tag_filter = '["tourism"~"attraction|museum|viewpoint|theme_park|zoo|gallery|aquarium"]'
    else:
        raise ValueError(f"Unsupported place type: {place_type}")

    latitude = float(location["latitude"])
    longitude = float(location["longitude"])
    query = (
        "[out:json][timeout:12];("
        f'node{tag_filter}["name"](around:{radius_meters},{latitude},{longitude});'
        f'way{tag_filter}["name"](around:{radius_meters},{latitude},{longitude});'
        ");out center tags 40;"
    )

    try:
        async with httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.post(OVERPASS_URL, data={"data": query})
            response.raise_for_status()
            elements = response.json().get("elements", [])
    except (httpx.HTTPError, ValueError) as error:
        fallback_places, fallback_error = await _search_named_places(
            location,
            place_type,
        )
        if fallback_places:
            return fallback_places, None
        return [], (
            f"OpenStreetMap place lookup failed: {error}. "
            f"{fallback_error or ''}"
        ).strip()

    places: list[dict[str, Any]] = []
    for element in elements:
        tags = element.get("tags", {})
        name = tags.get("name")
        if not name:
            continue

        coordinates = element.get("center", element)
        places.append(
            {
                "name": name,
                "type": tags.get("tourism", place_type),
                "star_rating": tags.get("stars"),
                "address": ", ".join(
                    part
                    for part in (
                        tags.get("addr:street"),
                        tags.get("addr:city"),
                    )
                    if part
                )
                or None,
                "latitude": coordinates.get("lat"),
                "longitude": coordinates.get("lon"),
                "source": f"https://www.openstreetmap.org/{element.get('type')}/{element.get('id')}",
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    if not places:
        fallback_places, _ = await _search_named_places(location, place_type)
        if fallback_places:
            return fallback_places, None
    return places, None


async def _search_named_places(
    location: dict[str, Any],
    place_type: str,
) -> tuple[list[dict[str, Any]], str | None]:
    place_query = "hotel" if place_type == "accommodation" else "museum"
    query = f"{place_query} near {location['name']}"
    if location.get("country"):
        query += f", {location['country']}"

    try:
        async with httpx.AsyncClient(
            timeout=12,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            response = await client.get(
                NOMINATIM_SEARCH_URL,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 20,
                    "addressdetails": 1,
                },
            )
            response.raise_for_status()
            results = response.json()
    except (httpx.HTTPError, ValueError) as error:
        return [], f"OpenStreetMap search fallback failed: {error}"

    places: list[dict[str, Any]] = []
    for result in results:
        address = result.get("address", {})
        city = (
            address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("suburb")
        )
        places.append(
            {
                "name": result.get("name")
                or result.get("namedetails", {}).get("name")
                or result.get("display_name", "").split(",")[0],
                "type": result.get("type", place_type),
                "star_rating": None,
                "address": ", ".join(
                    value
                    for value in (
                        result.get("display_name", "").split(",")[1].strip()
                        if "," in result.get("display_name", "")
                        else None,
                        city,
                    )
                    if value
                ),
                "latitude": float(result["lat"]),
                "longitude": float(result["lon"]),
                "source": (
                    f"https://www.openstreetmap.org/{result['osm_type']}/{result['osm_id']}"
                    if result.get("osm_type") and result.get("osm_id")
                    else "https://www.openstreetmap.org/"
                ),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
    return places, None
