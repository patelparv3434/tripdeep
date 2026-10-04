from copy import deepcopy
from uuid import uuid4


def _matches(document: dict, query: dict) -> bool:
    for key, expected in query.items():
        actual = document.get(key)
        if isinstance(expected, dict) and "$in" in expected:
            if actual not in expected["$in"]:
                return False
        elif actual != expected:
            return False
    return True


class MemoryCursor:
    def __init__(self, documents: list[dict]):
        self.documents = documents

    def sort(self, key: str, direction: int = 1):
        self.documents.sort(key=lambda document: document.get(key), reverse=direction < 0)
        return self

    async def to_list(self, length: int | None = None) -> list[dict]:
        documents = self.documents if length is None else self.documents[:length]
        return deepcopy(documents)


class MemoryCollection:
    def __init__(self):
        self.documents: dict[str, dict] = {}

    async def find_one(self, query: dict) -> dict | None:
        for document in self.documents.values():
            if _matches(document, query):
                return deepcopy(document)
        return None

    async def insert_one(self, document: dict) -> None:
        stored = deepcopy(document)
        identifier = stored.setdefault("_id", str(uuid4()))
        if identifier in self.documents:
            raise ValueError(f"Duplicate in-memory document id: {identifier}")
        self.documents[identifier] = stored

    async def update_one(self, query: dict, update: dict, upsert: bool = False) -> None:
        document = next((item for item in self.documents.values() if _matches(item, query)), None)
        inserted = document is None
        if inserted:
            if not upsert:
                return
            document = {key: value for key, value in query.items() if not isinstance(value, dict)}
            document.setdefault("_id", str(uuid4()))
        for key, value in update.get("$setOnInsert", {}).items():
            if inserted:
                document[key] = deepcopy(value)
        for key, value in update.get("$set", {}).items():
            document[key] = deepcopy(value)
        for key, value in update.get("$push", {}).items():
            document.setdefault(key, []).append(deepcopy(value))
        self.documents[document["_id"]] = document

    async def count_documents(self, query: dict) -> int:
        return sum(_matches(document, query) for document in self.documents.values())

    def find(self, query: dict | None = None) -> MemoryCursor:
        return MemoryCursor([deepcopy(document) for document in self.documents.values() if _matches(document, query or {})])

    async def create_index(self, *_args, **_kwargs) -> None:
        return None


class MemoryDatabase:
    """Process-local Mongo-shaped store for development without a MongoDB server."""

    def __init__(self):
        self.collections: dict[str, MemoryCollection] = {}

    def __getattr__(self, name: str) -> MemoryCollection:
        if name.startswith("_"):
            raise AttributeError(name)
        return self.collections.setdefault(name, MemoryCollection())