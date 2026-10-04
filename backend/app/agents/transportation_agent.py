from app.agents.provider_unavailable import ProviderUnavailableAgent
from app.agents.registry import AGENTS_BY_ID


class TransportationAgent(ProviderUnavailableAgent):
    definition = AGENTS_BY_ID["transportation"]
    provider_label = "authorized transportation provider"

    async def execute(self, input_data: dict) -> dict:
        return {
            "agent": self.definition.id,
            "status": "partial",
            "provider_summary": {
                "make_my_trip": {"api_status": "NOT_CONFIGURED", "search_status": "UNAVAILABLE"},
                "goibibo": {"api_status": "NOT_CONFIGURED", "search_status": "UNAVAILABLE"},
                "other_providers": [],
            },
            "transportation_feasibility": "Requires an authorized provider search.",
            "options": [],
            "multi_modal_segments": [],
            "booking": {"status": "NOT_BOOKED", "pnr": None},
            "missing_information": [],
            "warnings": ["No authorized booking API is configured. Website search results and bookings are not simulated."],
            "sources": [],
        }