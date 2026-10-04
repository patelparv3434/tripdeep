from fastapi import APIRouter, Depends, HTTPException
from pymongo.asynchronous.database import AsyncDatabase

from app.api.dependencies import get_current_user, get_db
router = APIRouter(prefix="/validation", tags=["validation"])


@router.get("")
async def validation_summary(
    database: AsyncDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, int]:
    owner_filter = {"user_id": user["_id"]}
    total = await database.agent_executions.count_documents(owner_filter)
    successful = await database.agent_executions.count_documents({**owner_filter, "status": "completed", "validation_status": "PASS"})
    failed = await database.agent_executions.count_documents({**owner_filter, "status": "failed"})
    needs_review = await database.agent_executions.count_documents({**owner_filter, "validation_status": {"$in": ["NEEDS_REVIEW", "MISSING", "WARNING"]}})
    validation_errors = await database.agent_executions.count_documents({**owner_filter, "validation_status": {"$in": ["FAIL", "MISSING", "NEEDS_REVIEW"]}})
    reproduced = await database.reproduction_cases.count_documents({**owner_filter, "status": "reproduced"})
    fixed = await database.reproduction_cases.count_documents({**owner_filter, "status": "fixed"})
    return {"total_executions": total, "successful": successful, "failed": failed, "needs_review": needs_review, "validation_errors": validation_errors, "reproduced_errors": reproduced, "fixed_errors": fixed}


@router.get("/{execution_id}")
async def get_validation(
    execution_id: str,
    database: AsyncDatabase = Depends(get_db),
    user: dict = Depends(get_current_user),
) -> dict[str, object]:
    execution = await database.agent_executions.find_one(
        {"_id": execution_id, "user_id": user["_id"]}
    )
    if execution is None or execution.get("validation") is None:
        raise HTTPException(status_code=404, detail="Validation result not found")
    result = execution["validation"]
    return {
        "execution_id": execution["_id"],
        "status": result["status"],
        "checks": result["checks"],
        "missing_information": result["missing_information"],
        "created_at": execution.get("completed_at"),
    }