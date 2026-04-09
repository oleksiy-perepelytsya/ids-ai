"""SearchOrchestrator — the single entry point for all search operations.

Replaces direct ``ChromaStore`` usage.  Callers hold a reference to this
class and never import backend-specific types.
"""

from __future__ import annotations

import uuid
from typing import Optional

from ids.search.backend import SearchBackend, SearchHit, VectorDoc
from ids.search.data_source import DataSource
from ids.search.embeddings import resolve_embedding_key
from ids.utils import get_logger

logger = get_logger(__name__)


class SearchOrchestrator:
    """What callers hold instead of ChromaStore."""

    def __init__(
        self,
        backends: dict[str, SearchBackend],
        mongo_db=None,
    ):
        self.backends = backends  # {"qdrant": QdrantBackend, "graph": GraphBackend, …}
        self.db = mongo_db  # for corpus_docs hydration

    # -- high-level search (project-aware) ----------------------------------

    async def search(
        self,
        project,  # ids.models.Project
        query: str,
        n: int = 5,
    ) -> list[SearchHit]:
        """Fan out to all project data sources, merge by priority then score."""
        data_sources = getattr(project, "data_sources", None) or []
        if not data_sources:
            # Backwards compat: project without data_sources — use learning collection
            emb_key = resolve_embedding_key(project.embedding_model)
            data_sources = [
                DataSource(
                    name="feedback",
                    kind="learning",
                    backend="qdrant",
                    namespace=f"learning_{project.project_id}",
                    embedding_model=emb_key,
                    priority=100,
                ),
            ]

        all_hits: list[SearchHit] = []
        for ds in data_sources:
            backend = self.backends.get(ds.backend)
            if not backend:
                logger.warning("backend_not_found", backend=ds.backend, source=ds.name)
                continue
            try:
                hits = await backend.search(
                    namespace=ds.namespace,
                    query=query,
                    n=n,
                    filters=ds.filters or None,
                    embedding_model=ds.embedding_model,
                )
                for h in hits:
                    h.source = ds.kind
                    h.score = h.score + ds.priority / 100.0
                all_hits.extend(hits)
            except Exception as e:
                logger.error("search_backend_failed", source=ds.name, error=str(e))

        all_hits.sort(key=lambda h: h.score, reverse=True)
        return _dedupe(all_hits)[:n]

    # -- backwards-compatible wrappers (drop-in for ChromaStore methods) -----

    async def search_learning_patterns(
        self,
        project_id: str,
        query: str,
        n_results: int = 5,
        embedding_model: str = "minilm",
    ) -> list[dict]:
        """Drop-in replacement for ``ChromaStore.search_learning_patterns``.

        Returns the same ``list[dict]`` shape that ``base_agent.py`` and
        ``round_executor.py`` expect: ``{"content": ..., "metadata": ..., "distance": ...}``.
        """
        emb_key = resolve_embedding_key(embedding_model)
        backend = self.backends.get("qdrant")
        if not backend:
            return []

        hits = await backend.search(
            namespace=f"learning_{project_id}",
            query=query,
            n=n_results,
            embedding_model=emb_key,
        )
        return [
            {
                "content": h.content,
                "metadata": h.payload,
                "distance": 1.0 - h.score if h.score else None,
            }
            for h in hits
        ]

    async def add_learning_pattern(
        self,
        project_id: str,
        content: str,
        metadata: Optional[dict] = None,
        embedding_model: str = "minilm",
    ) -> None:
        """Drop-in replacement for ``ChromaStore.add_learning_pattern``."""
        emb_key = resolve_embedding_key(embedding_model)
        backend = self.backends.get("qdrant")
        if not backend:
            return

        doc = VectorDoc(
            id=f"pattern_{uuid.uuid4().hex[:8]}",
            text=content,
            payload=metadata or {"project_id": project_id, "source": "learning"},
        )
        try:
            await backend.upsert(
                namespace=f"learning_{project_id}",
                docs=[doc],
                embedding_model=emb_key,
            )
            logger.info("learning_pattern_added", project_id=project_id)
        except Exception as e:
            logger.error("add_learning_pattern_failed", project_id=project_id, error=str(e))

    async def delete_project_data(self, project_id: str) -> None:
        """Delete all vector data for a project (learning + codebase)."""
        backend = self.backends.get("qdrant")
        if not backend:
            return
        for prefix in ("learning_", "codebase_"):
            await backend.delete_namespace(f"{prefix}{project_id}")

    # -- corpus doc hydration -----------------------------------------------

    async def hydrate_corpus_docs(self, hits: list[SearchHit]) -> list[dict]:
        """Fetch full documents from ``corpus_docs`` for hits with mongo_ref."""
        if not self.db:
            return []
        from bson import ObjectId

        refs = [h.mongo_ref for h in hits if h.mongo_ref]
        if not refs:
            return []
        cursor = self.db["corpus_docs"].find(
            {"_id": {"$in": [ObjectId(r) for r in refs]}}
        )
        docs = await cursor.to_list(length=len(refs))
        for d in docs:
            d["_id"] = str(d["_id"])
        return docs


def _dedupe(hits: list[SearchHit]) -> list[SearchHit]:
    """Remove duplicate hits (same id), keeping highest score."""
    seen: set[str] = set()
    out: list[SearchHit] = []
    for h in hits:
        if h.id not in seen:
            seen.add(h.id)
            out.append(h)
    return out
