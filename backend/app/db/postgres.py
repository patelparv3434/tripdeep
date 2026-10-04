import json
from copy import deepcopy
from datetime import date, datetime
from typing import Any
from uuid import uuid4

from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool


def _json_dumps(value: Any) -> str:
    def encode(item: Any) -> str:
        if isinstance(item, (datetime, date)):
            return item.isoformat()
        raise TypeError(f"Cannot serialize {type(item).__name__} to JSON")

    return json.dumps(value, default=encode, separators=(",", ":"))


def _where_clause(query: dict[str, Any]) -> tuple[str, list[Any]]:
    exact_matches = {
        key: expected
        for key, expected in query.items()
        if not (isinstance(expected, dict) and "$in" in expected)
    }
    conditions: list[str] = []
    parameters: list[Any] = []

    if exact_matches:
        conditions.append("document @> %s::jsonb")
        parameters.append(_json_dumps(exact_matches))

    for key, expected in query.items():
        if isinstance(expected, dict) and "$in" in expected:
            conditions.append(
                "(document -> %s) IN (SELECT value FROM jsonb_array_elements(%s::jsonb))"
            )
            parameters.extend((key, _json_dumps(expected["$in"])))

    return (" AND ".join(conditions) or "TRUE", parameters)


class PostgresCursor:
    def __init__(self, collection: "PostgresCollection", query: dict[str, Any]):
        self.collection = collection
        self.query = query
        self.sort_field: str | None = None
        self.sort_direction = 1

    def sort(self, key: str, direction: int = 1) -> "PostgresCursor":
        self.sort_field = key
        self.sort_direction = direction
        return self

    async def to_list(self, length: int | None = None) -> list[dict[str, Any]]:
        where, parameters = _where_clause(self.query)
        statement = f"SELECT document FROM {self.collection.table} WHERE {where}"
        if self.sort_field is not None:
            direction = "DESC" if self.sort_direction < 0 else "ASC"
            statement += f" ORDER BY document ->> %s {direction}"
            parameters.append(self.sort_field)
        if length is not None:
            statement += " LIMIT %s"
            parameters.append(length)

        async with self.collection.pool.connection() as connection:
            cursor = await connection.execute(statement, parameters)
            rows = await cursor.fetchall()
        return [row["document"] for row in rows]


class PostgresCollection:
    def __init__(self, pool: AsyncConnectionPool, table: str):
        self.pool = pool
        self.table = table

    async def find_one(self, query: dict[str, Any]) -> dict[str, Any] | None:
        where, parameters = _where_clause(query)
        async with self.pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT document FROM {self.table} WHERE {where} LIMIT 1",
                parameters,
            )
            row = await cursor.fetchone()
        return row["document"] if row else None

    async def insert_one(self, document: dict[str, Any]) -> None:
        stored = deepcopy(document)
        stored.setdefault("_id", str(uuid4()))
        async with self.pool.connection() as connection:
            await connection.execute(
                f"INSERT INTO {self.table} (document) VALUES (%s)",
                (Jsonb(stored, dumps=_json_dumps),),
            )

    async def update_one(
        self,
        query: dict[str, Any],
        update: dict[str, Any],
        upsert: bool = False,
    ) -> None:
        where, parameters = _where_clause(query)
        async with self.pool.connection() as connection:
            async with connection.transaction():
                cursor = await connection.execute(
                    f"SELECT document FROM {self.table} WHERE {where} LIMIT 1 FOR UPDATE",
                    parameters,
                )
                row = await cursor.fetchone()
                inserted = row is None
                if inserted and not upsert:
                    return

                if inserted:
                    document = {
                        key: deepcopy(value)
                        for key, value in query.items()
                        if not (isinstance(value, dict) and "$in" in value)
                    }
                    document.setdefault("_id", str(uuid4()))
                else:
                    document = row["document"]

                for key, value in update.get("$setOnInsert", {}).items():
                    if inserted:
                        document[key] = deepcopy(value)
                for key, value in update.get("$set", {}).items():
                    document[key] = deepcopy(value)
                for key, value in update.get("$push", {}).items():
                    document.setdefault(key, []).append(deepcopy(value))

                if inserted:
                    await connection.execute(
                        f"INSERT INTO {self.table} (document) VALUES (%s)",
                        (Jsonb(document, dumps=_json_dumps),),
                    )
                else:
                    await connection.execute(
                        f"UPDATE {self.table} SET document = %s WHERE document ->> '_id' = %s",
                        (Jsonb(document, dumps=_json_dumps), document["_id"]),
                    )

    async def count_documents(self, query: dict[str, Any]) -> int:
        where, parameters = _where_clause(query)
        async with self.pool.connection() as connection:
            cursor = await connection.execute(
                f"SELECT count(*) AS count FROM {self.table} WHERE {where}",
                parameters,
            )
            row = await cursor.fetchone()
        return row["count"]

    def find(self, query: dict[str, Any] | None = None) -> PostgresCursor:
        return PostgresCursor(self, query or {})


class PostgresDatabase:
    collection_names = (
        "users",
        "trips",
        "agent_executions",
        "documents",
        "reproduction_cases",
        "audit_logs",
    )

    def __init__(self, pool: AsyncConnectionPool):
        self.pool = pool
        self.collections = {
            name: PostgresCollection(pool, self.table_name(name))
            for name in self.collection_names
        }

    @staticmethod
    def table_name(collection_name: str) -> str:
        if collection_name not in PostgresDatabase.collection_names:
            raise ValueError(f"Unknown database collection: {collection_name}")
        return f"tripdeep_{collection_name}"

    @staticmethod
    def index_name(collection_name: str, suffix: str) -> str:
        return f"tripdeep_{collection_name}_{suffix}_idx"

    def __getattr__(self, name: str) -> PostgresCollection:
        try:
            return self.collections[name]
        except KeyError as error:
            raise AttributeError(name) from error
