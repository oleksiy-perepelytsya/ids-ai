"""Qdrant implementation of SearchBackend."""

from __future__ import annotations

import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient, models

from ids.search.backend import SearchHit, VectorDoc
from ids.search.embeddings import get_spec, resolve_embedding_key
from ids.utils import get_logger

logger = get_logger(__name__)


class QdrantBackend:
    """SearchBackend backed by Qdrant.

    Supports named vectors — each collection can hold multiple embedding
    spaces (e.g. ``{"minilm": 384, "ada": 1536}``).
    """

    def __init__(self, client: AsyncQdrantClient):
        self.client = client

    # -- public API (SearchBackend) -----------------------------------------

    async def search(
        self,
        namespace: str,
        query: str | list[float],
        n: int = 5,
        filters: dict | None = None,
        embedding_model: str | None = None,
    ) -> list[SearchHit]:
        """Search a Qdrant collection by text or raw vector."""
        if not await self._collection_exists(namespace):
            return []

        # Resolve query vector
        if isinstance(query, str):
            if not embedding_model:
                logger.warning("search_no_embedding_model", namespace=namespace)
                return []
            spec = get_spec(embedding_model)
            embed_fn = spec.get_embed_fn()
            if not embed_fn:
                return []
            vectors = embed_fn([query])
            query_vector = vectors[0]
        else:
            query_vector = query

        # Determine which named vector to search
        vector_name = resolve_embedding_key(embedding_model) if embedding_model else None
        if not vector_name:
            vector_name = await self._first_vector_name(namespace)
            if not vector_name:
                return []

        # Build Qdrant filter
        q_filter = _build_filter(filters) if filters else None

        try:
            results = await self.client.query_points(
                collection_name=namespace,
                query=query_vector,
                using=vector_name,
                limit=n,
                query_filter=q_filter,
                with_payload=True,
            )
        except Exception as e:
            logger.error("qdrant_search_failed", namespace=namespace, error=str(e))
            return []

        hits: list[SearchHit] = []
        for point in results.points:
            payload = dict(point.payload) if point.payload else {}
            content = payload.pop("text", "")
            hits.append(SearchHit(
                id=str(point.id),
                score=point.score if point.score is not None else 0.0,
                content=content,
                payload=payload,
                source=payload.get("source", "learning"),
                mongo_ref=payload.get("_mongo_ref"),
            ))
        return hits

    async def upsert(
        self,
        namespace: str,
        docs: list[VectorDoc],
        embedding_model: str | None = None,
    ) -> None:
        """Upsert documents into a Qdrant collection."""
        if not docs:
            return

        # Ensure collection exists with appropriate vector config
        await self._ensure_collection(namespace, docs, embedding_model)

        points: list[models.PointStruct] = []
        # Compute embeddings for docs that have text but no vectors
        text_docs = [d for d in docs if d.text and not d.vectors]
        if text_docs and embedding_model:
            spec = get_spec(embedding_model)
            embed_fn = spec.get_embed_fn()
            if embed_fn:
                texts = [d.text for d in text_docs]
                vecs = embed_fn(texts)
                vec_key = resolve_embedding_key(embedding_model)
                for doc, vec in zip(text_docs, vecs):
                    doc.vectors = {vec_key: vec}

        for doc in docs:
            payload = dict(doc.payload)
            if doc.text:
                payload["text"] = doc.text

            point_id = doc.id
            # Qdrant accepts UUID strings or ints; use UUID if not numeric
            try:
                point_id_parsed: str | int = int(point_id)
            except ValueError:
                # Ensure it's a valid UUID or create one from the string
                try:
                    uuid.UUID(point_id)
                    point_id_parsed = point_id
                except ValueError:
                    point_id_parsed = str(uuid.uuid5(uuid.NAMESPACE_URL, point_id))

            vectors: dict[str, list[float]] = {}
            if doc.vectors:
                vectors = doc.vectors

            if vectors:
                points.append(models.PointStruct(
                    id=point_id_parsed,
                    vector=vectors,
                    payload=payload,
                ))

        if points:
            await self.client.upsert(
                collection_name=namespace,
                points=points,
            )
            logger.info("qdrant_upserted", namespace=namespace, count=len(points))

    async def delete_namespace(self, namespace: str) -> None:
        """Delete a Qdrant collection."""
        try:
            await self.client.delete_collection(namespace)
            logger.info("qdrant_collection_deleted", namespace=namespace)
        except Exception as e:
            logger.info("qdrant_collection_delete_skip", namespace=namespace, error=str(e))

    # -- internals ----------------------------------------------------------

    async def _collection_exists(self, name: str) -> bool:
        try:
            collections = await self.client.get_collections()
            return any(c.name == name for c in collections.collections)
        except Exception:
            return False

    async def _first_vector_name(self, namespace: str) -> str | None:
        """Return the name of the first named vector in a collection."""
        try:
            info = await self.client.get_collection(namespace)
            if isinstance(info.config.params.vectors, dict):
                names = list(info.config.params.vectors.keys())
                return names[0] if names else None
        except Exception:
            pass
        return None

    async def _ensure_collection(
        self,
        namespace: str,
        docs: list[VectorDoc],
        embedding_model: str | None,
    ) -> None:
        """Create collection if it doesn't exist, using vector config from docs/model."""
        if await self._collection_exists(namespace):
            return

        # Determine vector configuration
        vectors_config: dict[str, models.VectorParams] = {}

        if embedding_model:
            spec = get_spec(embedding_model)
            vec_key = resolve_embedding_key(embedding_model)
            vectors_config[vec_key] = models.VectorParams(
                size=spec.dim,
                distance=models.Distance.COSINE,
            )

        # Also check first doc for pre-computed vector names
        for doc in docs:
            if doc.vectors:
                for vec_name, vec_data in doc.vectors.items():
                    if vec_name not in vectors_config:
                        vectors_config[vec_name] = models.VectorParams(
                            size=len(vec_data),
                            distance=models.Distance.COSINE,
                        )
                break

        if not vectors_config:
            logger.error("cannot_create_collection_no_vector_config", namespace=namespace)
            return

        await self.client.create_collection(
            collection_name=namespace,
            vectors_config=vectors_config,
        )
        logger.info("qdrant_collection_created", namespace=namespace, vectors=list(vectors_config))


def _build_filter(filters: dict) -> models.Filter:
    """Convert a simple dict of {field: value} into a Qdrant filter."""
    conditions: list[models.FieldCondition] = []
    for key, value in filters.items():
        if isinstance(value, list):
            conditions.append(models.FieldCondition(
                key=key, match=models.MatchAny(any=value),
            ))
        else:
            conditions.append(models.FieldCondition(
                key=key, match=models.MatchValue(value=value),
            ))
    return models.Filter(must=conditions)
