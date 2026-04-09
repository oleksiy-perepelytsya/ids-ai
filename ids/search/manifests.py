"""CorpusManifest — dataset-level metadata stored in MongoDB."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from ids.search.embeddings import EMBEDDING_REGISTRY, resolve_embedding_key


class CorpusManifest(BaseModel):
    dataset_id: str
    embedding_model: str  # must exist in EMBEDDING_REGISTRY
    vector_dim: int
    doc_count: int = 0
    chunk_count: int = 0
    schema_version: int = 1
    source_file: str = ""
    field_map: dict[str, str] = Field(default_factory=dict)
    imported_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def _dim_matches_registry(self) -> "CorpusManifest":
        key = resolve_embedding_key(self.embedding_model)
        spec = EMBEDDING_REGISTRY.get(key)
        if spec and spec.dim != self.vector_dim:
            raise ValueError(
                f"Dimension mismatch for {key}: registry says {spec.dim}, "
                f"manifest says {self.vector_dim}"
            )
        return self


class ManifestStore:
    """Thin CRUD wrapper over the ``corpus_manifests`` MongoDB collection."""

    def __init__(self, db):
        self.collection = db["corpus_manifests"]

    async def upsert(self, manifest: CorpusManifest) -> None:
        await self.collection.replace_one(
            {"dataset_id": manifest.dataset_id},
            manifest.model_dump(),
            upsert=True,
        )

    async def get(self, dataset_id: str) -> CorpusManifest | None:
        doc = await self.collection.find_one({"dataset_id": dataset_id})
        if not doc:
            return None
        doc.pop("_id", None)
        return CorpusManifest(**doc)

    async def list_all(self) -> list[CorpusManifest]:
        docs = await self.collection.find().to_list(length=1000)
        return [CorpusManifest(**{k: v for k, v in d.items() if k != "_id"}) for d in docs]
