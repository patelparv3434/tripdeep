from app.agents.base import BaseAgent
from app.agents.registry import AGENTS_BY_ID
from app.integrations.public_travel_data import find_nearby_places, resolve_destination


class HotelAgent(BaseAgent):
    definition = AGENTS_BY_ID["hotel"]

    async def validate_input(self, input_data: dict) -> dict:
        missing = [key for key in ("destination", "check_in", "check_out", "adults", "category") if input_data.get(key) in (None, "")]
        if missing:
            raise ValueError(f"Required hotel inputs are missing: {', '.join(missing)}")
        return input_data

    async def execute(self, input_data: dict) -> dict:
        location = input_data.get("location")
        warning = None
        if not location:
            location, warning = await resolve_destination(input_data["destination"])
        if location is None:
            return self._unavailable(warning or "Destination could not be resolved.")

        hotels, search_error = await find_nearby_places(location, "accommodation")
        category = str(input_data.get("category", ""))
        if category.endswith(" Star"):
            requested_stars = category.removesuffix(" Star")
            hotels = [
                hotel for hotel in hotels
                if str(hotel.get("star_rating", "")) == requested_stars
            ]
        elif category == "Resorts":
            hotels = [hotel for hotel in hotels if hotel.get("type") == "resort"]
        elif category == "Hotel / Guest house":
            hotels = [
                hotel for hotel in hotels
                if hotel.get("type") in {"hotel", "guest_house", "hostel", "motel"}
            ]

        status = "available" if hotels else "not_available"
        if category.endswith(" Star"):
            summary_warning = (
                f"Only listings tagged {category} are included. OpenStreetMap ratings are not independently verified; booking availability, rates and cancellation terms require a provider."
            )
        else:
            summary_warning = (
                "Map listings are discovery suggestions only. Live room availability, prices, star ratings and cancellation terms require a booking provider."
                if hotels else
                "No map listings matched this destination and preference. Live rates and availability require a booking provider."
            )
        return {
            "agent": self.definition.id,
            "status": status,
            "data_status": "LIVE_LISTINGS" if hotels else "NOT_AVAILABLE",
            "search_criteria": input_data,
            "hotels": hotels[:20],
            "retrieved_at": hotels[0].get("retrieved_at") if hotels else None,
            "warnings": [
                message for message in (search_error, summary_warning) if message
            ],
            "sources": ["https://www.openstreetmap.org/"],
        }

    @staticmethod
    def _unavailable(message: str) -> dict:
        return {
            "agent": "hotel",
            "status": "not_available",
            "data_status": "NOT_AVAILABLE",
            "hotels": [],
            "warnings": [message],
            "sources": ["https://www.openstreetmap.org/"],
        }