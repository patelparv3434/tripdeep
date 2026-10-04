from app.agents.base import BaseAgent
from app.agents.registry import AGENTS_BY_ID
from app.integrations.public_travel_data import find_nearby_places, resolve_destination


class TourGuideAgent(BaseAgent):
    definition = AGENTS_BY_ID["tour_guide"]

    async def execute(self, input_data: dict) -> dict:
        location = input_data.get("location")
        location_error = None
        if not location:
            location, location_error = await resolve_destination(
                str(input_data.get("destination", ""))
            )
        if location is None:
            return {
                "agent": self.definition.id,
                "status": "not_available",
                "guided_activities": [],
                "missing_information": ["Destination could not be located"],
                "warnings": [location_error or "Destination lookup failed."],
                "sources": ["https://www.openstreetmap.org/"],
            }

        activities, search_error = await find_nearby_places(location, "attraction")
        return {
            "agent": self.definition.id,
            "status": "available" if activities else "not_available",
            "guided_activities": activities[:20],
            "tour_guides": [],
            "group_validation": {"required_travelers": input_data.get("travelers"), "guide_capacity": None, "can_accommodate": None},
            "missing_information": [] if activities else ["No named attractions were listed in OpenStreetMap for this area."],
            "warnings": [
                message for message in (
                    search_error,
                    "These are map-listed places, not confirmed tour bookings, opening hours or admission prices."
                    if activities else None,
                ) if message
            ],
            "sources": ["https://www.openstreetmap.org/"],
        }