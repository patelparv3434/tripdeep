from fastapi import APIRouter, HTTPException

from app.agents.registry import AGENTS, AGENTS_BY_ID
from app.schemas.agents import AgentCatalog, AgentDefinition

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("", response_model=AgentCatalog)
def list_agents() -> AgentCatalog:
    return AgentCatalog(agents=AGENTS, total=len(AGENTS))


@router.get("/{agent_id}", response_model=AgentDefinition)
def get_agent(agent_id: str) -> AgentDefinition:
    agent = AGENTS_BY_ID.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent