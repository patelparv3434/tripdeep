from app.agents.base import BaseAgent
from app.agents.registry import AGENTS_BY_ID


class DietitianAgent(BaseAgent):
    definition = AGENTS_BY_ID["dietitian"]

    async def execute(self, input_data: dict) -> dict:
        trip = input_data.get("trip", {})
        children = int(trip.get("children", 0) or 0)
        ages = input_data.get("child_ages") or []
        allergies_confirmed = input_data.get("allergies_confirmed") is True
        missing = []
        if children and len(ages) != children:
            missing.append("Child ages for every child")
        if not allergies_confirmed:
            missing.append("Allergy confirmation")
        status = "needs_input" if missing else "degraded"
        confidence = 1.0 - (0.4 if children and len(ages) != children else 0) - (0.15 if not allergies_confirmed else 0) - 0.2
        return {
            "status": status,
            "rtcco": {"requirement": "Jain meals only", "target": trip.get("destination"), "context": trip, "constraints": ["No meat, fish, eggs, honey, onion, garlic or root vegetables", "Never assume a dish is Jain"], "outcome": "No day plan produced until required input and current local food/weather context are available."},
            "days": [],
            "confidence": max(0.0, confidence),
            "confidence_reason": "Child ages and allergy confirmation are required; local menu lookup is not configured.",
            "missing_information": missing + ([] if missing else ["Verified Jain menu and current local food context"]),
            "warnings": ["No dishes or nutrition values were fabricated."],
        }