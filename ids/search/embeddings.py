"""Embedding registry — maps string keys to embedding specs.

Each project and corpus manifest references models by registry key
(e.g. ``"minilm"``, ``"ada"``).  The registry provides dimension info
and the callable that produces vectors.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Callable, Literal


@dataclass
class EmbeddingSpec:
    key: str
    dim: int
    provider: Literal["local", "openai", "precomputed"]
    model_name: str | None = None  # provider-specific model identifier
    _embed_fn: Callable[[list[str]], list[list[float]]] | None = field(
        default=None, repr=False,
    )

    def get_embed_fn(self) -> Callable[[list[str]], list[list[float]]] | None:
        """Return (or lazily build) the embedding callable."""
        if self._embed_fn is not None:
            return self._embed_fn
        if self.provider == "precomputed":
            return None
        if self.provider == "local":
            return self._build_local()
        if self.provider == "openai":
            return self._build_openai()
        return None

    # -- lazy builders (avoid import cost at module load) --------------------

    def _build_local(self) -> Callable[[list[str]], list[list[float]]]:
        from sentence_transformers import SentenceTransformer

        model = SentenceTransformer("all-MiniLM-L6-v2")

        def _fn(texts: list[str]) -> list[list[float]]:
            return model.encode(texts).tolist()

        self._embed_fn = _fn
        return _fn

    def _build_openai(self) -> Callable[[list[str]], list[list[float]]]:
        import openai

        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        model = self.model_name or "text-embedding-ada-002"

        def _fn(texts: list[str]) -> list[list[float]]:
            resp = client.embeddings.create(input=texts, model=model)
            return [d.embedding for d in resp.data]

        self._embed_fn = _fn
        return _fn


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

EMBEDDING_REGISTRY: dict[str, EmbeddingSpec] = {
    "minilm": EmbeddingSpec(key="minilm", dim=384, provider="local"),
    "ada": EmbeddingSpec(
        key="ada", dim=1536, provider="openai",
        model_name="text-embedding-ada-002",
    ),
    "te3-large": EmbeddingSpec(
        key="te3-large", dim=3072, provider="openai",
        model_name="text-embedding-3-large",
    ),
    "bge-large": EmbeddingSpec(
        key="bge-large", dim=1024, provider="local",
    ),
    "fp22": EmbeddingSpec(key="fp22", dim=22, provider="precomputed"),
}

# Backwards-compat aliases for values previously stored in Project.embedding_model
_ALIASES: dict[str, str] = {
    "default": "minilm",
    "ada-002": "ada",
}


def resolve_embedding_key(key: str) -> str:
    """Normalise legacy or alias keys to canonical registry keys."""
    return _ALIASES.get(key, key)


def get_spec(key: str) -> EmbeddingSpec:
    """Look up a spec, resolving aliases first."""
    return EMBEDDING_REGISTRY[resolve_embedding_key(key)]
