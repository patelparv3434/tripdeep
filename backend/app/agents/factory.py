from app.agents.base import BaseAgent
from app.agents.dietitian_agent import DietitianAgent
from app.agents.document_agent import DocumentAgent
from app.agents.fashion_designer_agent import FashionDesignerAgent
from app.agents.finance_agent import FinanceAgent
from app.agents.health_agent import HealthAgent
from app.agents.hotel_agent import HotelAgent
from app.agents.insurance_agent import InsuranceAgent
from app.agents.registry import AGENTS_BY_ID
from app.agents.tour_guide_agent import TourGuideAgent
from app.agents.transportation_agent import TransportationAgent
from app.agents.travel_planner_agent import TravelPlannerAgent
from app.agents.validator_agent import ValidatorAgent
from app.agents.weather_agent import WeatherAgent

AGENT_FACTORIES: dict[str, type[BaseAgent]] = {
    "travel_planner": TravelPlannerAgent,
    "validator": ValidatorAgent,
    "hotel": HotelAgent,
    "transportation": TransportationAgent,
    "weather": WeatherAgent,
    "tour_guide": TourGuideAgent,
    "insurance": InsuranceAgent,
    "finance": FinanceAgent,
    "fashion_designer": FashionDesignerAgent,
    "document": DocumentAgent,
    "health": HealthAgent,
    "dietitian": DietitianAgent,
}


def create_agent(agent_id: str) -> BaseAgent:
    factory = AGENT_FACTORIES.get(agent_id)
    if factory is None:
        raise LookupError(f"Unknown agent: {agent_id}")
    return factory()


def agent_health() -> list[dict[str, str]]:
    return [
        {"agent_id": definition.id, "status": definition.status}
        for definition in AGENTS_BY_ID.values()
    ]