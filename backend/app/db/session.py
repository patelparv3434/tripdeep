from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool
from pymongo import ASCENDING, DESCENDING, AsyncMongoClient

from app.core.config import get_settings
from app.db.memory import MemoryDatabase
from app.db.postgres import PostgresDatabase

settings = get_settings()
client = (
    AsyncMongoClient(settings.mongodb_url)
    if settings.database_backend == "mongo"
    else None
)
pool = (
    AsyncConnectionPool(
        settings.postgres_dsn,
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    if settings.database_backend == "postgres"
    else None
)
if settings.database_backend == "postgres":
    database = PostgresDatabase(pool)
elif settings.database_backend == "mongo":
    database = client[settings.mongodb_database]
else:
    database = MemoryDatabase()


async def start_database() -> None:
    if pool is not None:
        await pool.open(wait=True)
        await ensure_indexes()
    elif client is not None:
        await ensure_indexes()


async def close_database() -> None:
    if pool is not None:
        await pool.close()
    if client is not None:
        await client.close()


async def ping_database() -> None:
    if pool is not None:
        async with pool.connection() as connection:
            await connection.execute("SELECT 1")
    elif client is not None:
        await client.admin.command("ping")


async def ensure_indexes() -> None:
    if pool is not None:
        async with pool.connection() as connection:
            for collection_name in PostgresDatabase.collection_names:
                table = PostgresDatabase.table_name(collection_name)
                await connection.execute(
                    f"CREATE TABLE IF NOT EXISTS {table} "
                    "(id BIGSERIAL PRIMARY KEY, document JSONB NOT NULL)"
                )
                await connection.execute(
                    f"CREATE UNIQUE INDEX IF NOT EXISTS "
                    f"{PostgresDatabase.index_name(collection_name, 'id')} "
                    f"ON {table} ((document ->> '_id'))"
                )
                await connection.execute(
                    f"CREATE INDEX IF NOT EXISTS "
                    f"{PostgresDatabase.index_name(collection_name, 'document_gin')} "
                    f"ON {table} USING GIN (document)"
                )
        return

    if client is None:
        return
    await database.users.create_index("email", unique=True)
    await database.trips.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await database.agent_executions.create_index([("trip_id", ASCENDING), ("created_at", DESCENDING)])
    await database.agent_executions.create_index("request_id")
    await database.agent_executions.create_index("agent_id")
    await database.documents.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await database.documents.create_index("trip_id")
    await database.documents.create_index("sha256")
    await database.reproduction_cases.create_index([("status", ASCENDING), ("created_at", DESCENDING)])
    await database.reproduction_cases.create_index("execution_id")
    await database.reproduction_cases.create_index("request_id")
    await database.audit_logs.create_index("request_id")
    await database.audit_logs.create_index([("trip_id", ASCENDING), ("created_at", DESCENDING)])