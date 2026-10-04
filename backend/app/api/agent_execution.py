from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo.asynchronous.database import AsyncDatabase

from app.agents.registry import AGENTS_BY_ID
from app.api.dependencies import get_current_user, get_db
from app.schemas.execution import AgentExecutionRequest, AgentExecutionResponse
from app.services.agent_executor import execute_agent

router = APIRouter(prefix="/agents", tags=["agent-executions"])


@router.post("/{agent_id}/execute", response_model=AgentExecutionResponse)
async def run_agent(
    agent_id: str,
    body: AgentExecutionRequest,
    request: Request,
    database: AsyncDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> AgentExecutionResponse:
    if agent_id not in AGENTS_BY_ID:
        raise HTTPException(status_code=404, detail="Agent not found")
    if body.trip_id and await database.trips.find_one(
        {"_id": body.trip_id, "user_id": user["_id"]}
    ) is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    request_id = getattr(request.state, "request_id", str(uuid4()))
    try:
        UUID(request_id)
    except ValueError:
        request_id = str(uuid4())

    result = await execute_agent(
        database=database,
        agent_id=agent_id,
        input_data=body.input_data,
        request_id=request_id,
        trip_id=body.trip_id,
        user_id=user["_id"],
    )
    return AgentExecutionResponse(**result)