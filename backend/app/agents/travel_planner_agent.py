from app.agents.base import BaseAgent
from app.agents.registry import AGENTS_BY_ID


class TravelPlannerAgent(BaseAgent):
    definition = AGENTS_BY_ID["travel_planner"]

    async def execute(self, input_data: dict) -> dict:
        selected_agents = [
            "weather",
            "transportation",
            "hotel",
            "tour_guide",
            "health",
            "fashion_designer",
            "document",
            "insurance",
            "finance",
        ]
        if str(input_data.get("food_preference", "")).casefold() == "jain":
            selected_agents.insert(-2, "dietitian")

        return {
            "agent": self.definition.id,
            "status": "planned",
            "origin": input_data.get("origin"),
            "destination": input_data.get("destination"),
            "execution_plan": [
                {
                    "specialist": agent_id,
                    "reason": (
                        "Prepare Jain meal guidance for the selected food preference."
                        if agent_id == "dietitian"
                        else "Find trip information relevant to the supplied travel details."
                    ),
                }
                for agent_id in selected_agents
            ],
            "selected_specialists": selected_agents,
            "warnings": [],
        }