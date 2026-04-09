"""Graph search backend — Phase 3 stub.

Implements SearchBackend protocol so SearchOrchestrator can fan out
to it once a graph database is available.
"""

from __future__ import annotations

from ids.search.backend import SearchHit, VectorDoc
from ids.utils import get_logger

logger = get_logger(__name__)


class GraphBackend:
    """Placeholder for future graph DB integration (Neo4j / Memgraph)."""

    async def search(
        self,
        namespace: str,
        query: str | list[float],
        n: int = 5,
        filters: dict | None = None,
        embedding_model: str | None = None,
    ) -> list[SearchHit]:
        logger.warning("graph_backend_not_implemented")
        return []

    async def upsert(
        self,
        namespace: str,
        docs: list[VectorDoc],
        embedding_model: str | None = None,
    ) -> None:
        logger.warning("graph_backend_not_implemented")

    async def delete_namespace(self, namespace: str) -> None:
        logger.warning("graph_backend_not_implemented")
