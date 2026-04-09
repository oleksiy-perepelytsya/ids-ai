"""Search package — replaces ids.storage.chroma_store."""

from .backend import SearchBackend, SearchHit, VectorDoc
from .data_source import DataSource
from .embeddings import EMBEDDING_REGISTRY, EmbeddingSpec, get_spec, resolve_embedding_key
from .manifests import CorpusManifest, ManifestStore
from .orchestrator import SearchOrchestrator

__all__ = [
    "SearchBackend",
    "SearchHit",
    "VectorDoc",
    "DataSource",
    "EMBEDDING_REGISTRY",
    "EmbeddingSpec",
    "get_spec",
    "resolve_embedding_key",
    "CorpusManifest",
    "ManifestStore",
    "SearchOrchestrator",
]
