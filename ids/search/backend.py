"""SearchBackend protocol and universal data types.

Every search backend (Qdrant, future graph DB, etc.) implements
``SearchBackend`` so the rest of the app never imports transport-specific
types.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class VectorDoc(BaseModel):
    """One point going into a vector store.  Text OR vectors must be set."""
    id: str
    text: str | None = None
    vectors: dict[str, list[float]] | None = None  # named-vector map
    payload: dict = Field(default_factory=dict)


class SearchHit(BaseModel):
    """Universal search result — every backend returns these."""
    id: str
    score: float
    content: str
    payload: dict = Field(default_factory=dict)
    source: str = "learning"  # "learning", "corpus", "graph", …
    mongo_ref: str | None = None


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class SearchBackend(Protocol):
    """Anything that takes a query and returns scored hits."""

    async def search(
        self,
        namespace: str,
        query: str | list[float],
        n: int = 5,
        filters: dict | None = None,
        embedding_model: str | None = None,
    ) -> list[SearchHit]: ...

    async def upsert(
        self,
        namespace: str,
        docs: list[VectorDoc],
        embedding_model: str | None = None,
    ) -> None: ...

    async def delete_namespace(self, namespace: str) -> None: ...
