from app.agents.base import BaseAgent
from app.agents.registry import AGENTS_BY_ID


class HealthAgent(BaseAgent):
    definition = AGENTS_BY_ID["health"]

    async def execute(self, input_data: dict) -> dict:
        travelers = input_data.get("trip", {})
        return {
            "agent_name": "HealthAgent",
            "status": "GENERAL_GUIDANCE",
            "traveler_considerations": {
                "adults": {"traveler_count": travelers.get("adults"), "considerations": ["Keep personal prescribed medicines in original packaging and accessible.", "Plan hydration, rest breaks and emergency contact access."]},
                "children": {"traveler_count": travelers.get("children"), "considerations": ["Plan rest breaks and keep guardian contact information accessible.", "Age-specific planning requires the children's ages."]},
            },
            "weather_based_preparation": {"forecast_status": "FORECAST_NOT_AVAILABLE", "recommended_preparation": []},
            "medical_kit": [{"category": "First aid", "item": "Basic wound-care supplies", "purpose": "General preparedness", "priority": "RECOMMENDED", "notes": "Consult a qualified professional for personal medical needs."}],
            "identified_risks": [],
            "warnings": ["General non-diagnostic guidance only. Destination-specific advisories require verified health sources."],
            "sources": [],
        }