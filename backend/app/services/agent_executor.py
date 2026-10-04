import asyncio
import logging
import re
import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pymongo.asynchronous.database import AsyncDatabase

from app.agents.factory import create_agent
from app.agents.validator_agent import ValidatorAgent
from app.core.config import get_settings
from app.services.retry import CircuitBreaker, TransientProviderError, retry_transient

logger = logging.getLogger(__name__)
settings = get_settings()
output_validator = ValidatorAgent()
provider_breakers: dict[str, CircuitBreaker] = {}
SECRET_KEY = re.compile(r"(password|secret|token|authorization|api[_-]?key|cvv|card[_-]?number|otp)", re.I)


def sanitize_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if SECRET_KEY.search(key) else sanitize_payload(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [sanitize_payload(item) for item in value]
    return value


async def execute_agent(
    database: AsyncDatabase,
    agent_id: str,
    input_data: dict[str, Any],
    request_id: str,
    trip_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    agent = create_agent(agent_id)

    execution_id = str(uuid4())
    execution = {
        "_id": execution_id,
        "request_id": request_id,
        "trip_id": trip_id,
        "user_id": user_id,
        "agent_id": agent_id,
        "status": "running",
        "validation_status": None,
        "validation": None,
        "input_data": sanitize_payload(input_data),
        "output_data": None,
        "error_summary": None,
        "retry_count": 0,
        "started_at": datetime.now(timezone.utc),
        "completed_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    await database.agent_executions.insert_one(execution)
    logger.info("Agent execution started", extra={"request_id": request_id, "agent_id": agent_id, "execution_id": execution_id})
    attempt_count = 0
    breaker = provider_breakers.setdefault(agent_id, CircuitBreaker())

    try:
        validated_input = await agent.validate_input(input_data)

        async def invoke() -> dict[str, Any]:
            nonlocal attempt_count
            attempt_count += 1
            try:
                return await asyncio.wait_for(
                    agent.execute(validated_input),
                    timeout=settings.agent_timeout_seconds,
                )
            except TimeoutError as error:
                raise TransientProviderError("Agent execution timed out") from error

        output, retry_count = await retry_transient(
            lambda: breaker.call(invoke),
            max_attempts=settings.max_agent_retries + 1,
        )
        output = await agent.validate_output(output)
        if agent_id == "validator":
            validation = output
        else:
            validation = await output_validator.execute(
                {
                    "data": {"agent": agent_id, "output": output},
                    "required_fields": ["agent", "output"],
                    "agent_outputs": {agent_id: output},
                    "applicable_rules": [],
                }
            )
        validation_status = validation["status"]
        now = datetime.now(timezone.utc)
        await database.agent_executions.update_one(
            {"_id": execution_id},
            {"$set": {"output_data": output, "status": "completed", "validation_status": validation_status, "validation": validation, "retry_count": retry_count, "completed_at": now, "updated_at": now}},
        )
        await database.audit_logs.insert_one({
            "_id": str(uuid4()),
            "request_id": request_id,
            "trip_id": trip_id,
            "action": "agent_execution_completed",
            "entity_type": "agent_execution",
            "entity_id": execution_id,
            "details": {"agent_id": agent_id, "validation_status": validation["status"]},
            "created_at": now,
        })
        return {
            "execution_id": execution_id,
            "request_id": request_id,
            "agent_id": agent_id,
            "status": "completed",
            "validation_status": validation_status,
            "output": output,
            "validation": validation,
        }
    except Exception as error:
        error_id = str(uuid4())
        now = datetime.now(timezone.utc)
        try:
            await database.agent_executions.update_one(
                {"_id": execution_id},
                {"$set": {"status": "failed", "error_summary": f"{type(error).__name__}: {error}", "retry_count": max(0, attempt_count - 1), "completed_at": now, "updated_at": now}},
            )
            await database.reproduction_cases.insert_one({
                "_id": error_id,
                "execution_id": execution_id,
                "request_id": request_id,
                "agent_id": agent_id,
                "user_id": user_id,
                "trip_id": trip_id,
                "status": "new",
                "error_type": type(error).__name__,
                "error_message": str(error),
                "stack_trace": traceback.format_exc(),
                "sanitized_input": sanitize_payload(input_data),
                "output_data": None,
                "reproduction_steps": [f"POST /api/agents/{agent_id}/execute with the recorded sanitized input"],
                "retry_history": [
                    *[{"attempt": attempt, "status": "transient_failure"} for attempt in range(1, attempt_count)],
                    *([{"attempt": attempt_count, "status": "failed"}] if attempt_count else []),
                ],
                "environment": settings.environment,
                "app_version": settings.app_version,
                "created_at": now,
                "updated_at": now,
            })
            await database.audit_logs.insert_one({
                "_id": str(uuid4()), "request_id": request_id, "trip_id": trip_id,
                "action": "agent_execution_failed", "entity_type": "agent_execution",
                "entity_id": execution_id, "details": {"agent_id": agent_id, "reproduction_case_id": error_id},
                "created_at": now,
            })
        except Exception:
            logger.exception("Could not persist agent failure or reproduction case", extra={"request_id": request_id, "agent_id": agent_id, "execution_id": execution_id})
            raise error
        logger.exception(
            "Agent execution failed; reproduction case created",
            extra={"request_id": request_id, "agent_id": agent_id, "execution_id": execution_id},
        )
        return {
            "execution_id": execution_id,
            "request_id": request_id,
            "agent_id": agent_id,
            "status": "failed",
            "reproduction_case_id": error_id,
            "error": "Agent execution failed; a reproduction case was recorded.",
        }