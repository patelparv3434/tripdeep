import logging
from uuid import uuid4

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import agents, agent_execution, documents, errors, health, trips, validation
from app.core.config import get_settings
from app.db.session import close_database, start_database

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_production()
    await start_database()
    try:
        yield
    finally:
        await close_database()


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
)
for handler in logging.getLogger().handlers:
    handler.addFilter(RequestContextFilter())
logger = logging.getLogger("tripdeep.request")
app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception(
        "Unhandled API exception",
        extra={"request_id": request_id},
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred", "request_id": request_id},
        headers={"X-Request-ID": request_id},
    )


app.include_router(health.router, prefix="/api")
app.include_router(agents.router, prefix="/api")
app.include_router(agent_execution.router, prefix="/api")
app.include_router(errors.router, prefix="/api")
app.include_router(validation.router, prefix="/api")
app.include_router(trips.router, prefix="/api")
app.include_router(documents.router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs"}