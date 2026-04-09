"""DataSource model — one searchable thing attached to a project."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DataSource(BaseModel):
    """Declarative description of a search source bound to a project."""
    name: str
    kind: str  # "learning", "corpus", "graph", …
    backend: Literal["qdrant", "graph"] = "qdrant"
    namespace: str  # Qdrant collection name / graph name
    embedding_model: str | None = None  # registry key (None = precomputed)
    priority: int = 0  # higher wins in merge
    filters: dict = Field(default_factory=dict)
