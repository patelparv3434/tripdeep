from uuid import uuid4
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pymongo import DESCENDING
from pymongo.asynchronous.database import AsyncDatabase

from app.api.dependencies import get_current_user, get_db
from app.services.agent_executor import execute_agent

router = APIRouter(tags=["errors"])


@router.get("/errors")
async def list_errors(
    database: AsyncDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, object]:
    cases = await database.reproduction_cases.find(
        {"user_id": user["_id"]}
    ).sort("created_at", DESCENDING).to_list(length=500)
    return {
        "errors": [
            {
                "id": case["_id"],
                "execution_id": case.get("execution_id"),
                "agent_id": case["agent_id"],
                "error": case["error_message"],
                "status": case["status"],
                "created_at": case.get("created_at"),
                "retry_count": len(case.get("retry_history", [])),
            }
            for case in cases
        ],
        "total": len(cases),
    }


@router.get("/errors/{error_id}")
async def get_error(
    error_id: str,
    database: AsyncDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, object]:
    case = await database.reproduction_cases.find_one(
        {"_id": error_id, "user_id": user["_id"]}
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Error record not found")
    execution = (
        await database.agent_executions.find_one(
            {"_id": case["execution_id"], "user_id": user["_id"]}
        )
        if case.get("execution_id")
        else None
    )
    return {
        "id": case["_id"],
        "execution_id": case.get("execution_id"),
        "request_id": case["request_id"],
        "agent_id": case["agent_id"],
        "status": case["status"],
        "error_type": case["error_type"],
        "error_message": case["error_message"],
        "stack_trace": case.get("stack_trace"),
        "input": case["sanitized_input"],
        "output": case.get("output_data"),
        "validation_status": execution.get("validation_status") if execution else None,
        "reproduction_steps": case.get("reproduction_steps", []),
        "retry_history": case.get("retry_history", []),
        "environment": case["environment"],
        "app_version": case["app_version"],
        "created_at": case.get("created_at"),
    }


@router.get("/reproduction")
async def list_reproduction_cases(
    database: AsyncDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, object]:
    cases = await database.reproduction_cases.find(
        {"user_id": user["_id"]}
    ).sort("created_at", DESCENDING).to_list(length=500)
    return {"cases": [{"id": case["_id"], "agent_id": case["agent_id"], "status": case["status"], "created_at": case.get("created_at")} for case in cases], "total": len(cases)}


@router.get("/reproduction/{case_id}")
async def get_reproduction_case(
    case_id: str,
    database: AsyncDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, object]:
    result = await get_error(case_id, database, user)
    return {"case": result}


@router.post("/reproduction/{case_id}/replay")
async def replay_reproduction_case(
    case_id: str,
    request: Request,
    database: AsyncDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, object]:
    case = await database.reproduction_cases.find_one(
        {"_id": case_id, "user_id": user["_id"]}
    )
    if case is None:
        raise HTTPException(status_code=404, detail="Reproduction case not found")
    await database.reproduction_cases.update_one({"_id": case_id}, {"$set": {"status": "reproducing", "updated_at": datetime.now(timezone.utc)}})
    replay_request_id = getattr(request.state, "request_id", str(uuid4()))
    replay = await execute_agent(
        database=database,
        agent_id=case["agent_id"],
        input_data=case["sanitized_input"],
        request_id=replay_request_id,
        trip_id=case.get("trip_id"),
        user_id=user["_id"],
    )
    new_status = "reproduced" if replay["status"] == "failed" else "not_reproduced"
    await database.reproduction_cases.update_one(
        {"_id": case_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc)}, "$push": {"retry_history": {"request_id": replay_request_id, "status": replay["status"], "execution_id": replay["execution_id"]}}},
    )
    return {"case_id": case_id, "status": new_status, "replay": replay}