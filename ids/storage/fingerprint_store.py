"""Fingerprint store — persists daily planetary fingerprints to MongoDB + Qdrant."""

import os
import sys
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from ids.config import settings
from ids.search.backend import VectorDoc
from ids.utils import get_logger

logger = get_logger(__name__)

# 22-dimensional vector component order (must match agent prompt normalization rules)
FINGERPRINT_DIMS = [
    "solar_activity", "lunar_tidal_force", "lunar_phase", "lunar_distance",
    "planetary_perturbation", "geomagnetic_disturbance", "med_wind_strength",
    "med_sea_state", "med_pressure_anomaly", "nao_state", "enso_state",
    "tidal_range_composite", "seismic_activity", "solar_cycle_position",
    "lunar_node_cycle", "season_position",
    # Cosmic ray dimensions (v1.1+)
    "gcr_intensity", "phi_modulation", "solar_wind_dynamic_pressure",
    "imf_magnitude", "forbush_decrease", "loss_cone_state",
]

# Import schema helpers from project root (fallback if not present)
_schema_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _schema_dir not in sys.path:
    sys.path.insert(0, _schema_dir)

try:
    from planetary_fingerprint_schema import (
        build_fingerprint_vector,
        build_chromadb_metadata,
        build_chromadb_document,
    )
except ImportError:
    logger.warning("planetary_fingerprint_schema_not_found")
    build_fingerprint_vector = None
    build_chromadb_metadata = None
    build_chromadb_document = None

COLLECTION_NAME = "planetary_fingerprints"


class FingerprintStore:
    """Stores daily planetary fingerprints in MongoDB and Qdrant."""

    def __init__(self, vectors):
        """Accept a QdrantBackend (or any SearchBackend) for vector ops."""
        self.vectors = vectors
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db = self.client[settings.mongodb_db]
        self.collection = self.db[COLLECTION_NAME]

    async def ensure_indexes(self) -> None:
        """Create MongoDB indexes on first use."""
        await self.collection.create_index("date", unique=True)
        await self.collection.create_index([("lunar.phase_name", 1), ("date", 1)])
        await self.collection.create_index([("solar.kp_index", 1), ("date", 1)])
        await self.collection.create_index([("tides.spring_neap_position", 1), ("date", 1)])
        await self.collection.create_index([("cosmic_rays.gcr_intensity_normalized", 1), ("date", 1)])
        logger.info("fingerprint_indexes_ensured")

    async def upsert(self, doc: dict) -> dict:
        """
        Store a daily fingerprint document.

        Priority for vector embedding:
        1. Use chromadb_ready.embedding returned by the agent (22-dim, pre-computed)
        2. Fall back to building vector from fingerprint_components dict
        3. Fall back to build_fingerprint_vector() from schema helpers
        4. Use zero vector of default dimension

        The chromadb_ready section is stripped before MongoDB storage.
        Returns the stored document with fingerprint_components populated.
        """
        date_str = doc["date"]

        # --- Extract chromadb_ready before MongoDB storage ---
        chroma_ready = doc.pop("chromadb_ready", None)

        # --- Resolve vector, chroma document string, and metadata ---
        if chroma_ready and chroma_ready.get("embedding"):
            vector = chroma_ready["embedding"]
            chroma_doc = chroma_ready.get("document", date_str)
            metadata = chroma_ready.get("metadata", {"date": date_str})
            logger.info("fingerprint_using_agent_embedding", date=date_str, dims=len(vector))
        elif doc.get("fingerprint_components"):
            # Build vector from components dict in canonical dimension order
            fc = doc["fingerprint_components"]
            vector = [round(float(fc.get(dim, 0.5)), 4) for dim in FINGERPRINT_DIMS]
            chroma_doc = build_chromadb_document(doc) if build_chromadb_document else date_str
            metadata = build_chromadb_metadata(doc) if build_chromadb_metadata else {"date": date_str}
        elif build_fingerprint_vector:
            vector = build_fingerprint_vector(doc)
            chroma_doc = build_chromadb_document(doc) if build_chromadb_document else date_str
            metadata = build_chromadb_metadata(doc) if build_chromadb_metadata else {"date": date_str}
        else:
            vector = [0.5] * len(FINGERPRINT_DIMS)
            chroma_doc = date_str
            metadata = {"date": date_str}

        # --- Populate fingerprint_components from vector if not present ---
        if "fingerprint_components" not in doc:
            doc["fingerprint_components"] = {
                dim: round(vector[i], 4)
                for i, dim in enumerate(FINGERPRINT_DIMS)
                if i < len(vector)
            }

        # --- MongoDB upsert (chromadb_ready already removed) ---
        await self.collection.replace_one(
            {"date": date_str},
            doc,
            upsert=True
        )
        logger.info("fingerprint_mongo_upserted", date=date_str)

        # --- Qdrant upsert with embedding vector ---
        try:
            fp_doc = VectorDoc(
                id=date_str,
                text=chroma_doc,
                vectors={"fp22": vector},
                payload=metadata,
            )
            await self.vectors.upsert(
                namespace=COLLECTION_NAME,
                docs=[fp_doc],
                embedding_model="fp22",
            )
            logger.info("fingerprint_qdrant_upserted", date=date_str, dims=len(vector))
        except Exception as e:
            logger.error("fingerprint_qdrant_failed", date=date_str, error=str(e))

        return doc

    async def get(self, date_str: str) -> Optional[dict]:
        """Retrieve a fingerprint by date."""
        doc = await self.collection.find_one({"date": date_str})
        if doc:
            doc.pop("_id", None)
        return doc

    async def find_similar(self, date_str: str, n: int = 5) -> list:
        """
        Find historically similar days using vector similarity search.
        Builds query vector from fingerprint_components in canonical dimension order.
        Returns list of dicts with date, distance, summary.
        """
        source = await self.get(date_str)
        if not source:
            return []

        # Build vector from stored fingerprint_components
        fc = source.get("fingerprint_components", {})
        if fc:
            vector = [float(fc.get(dim, 0.5)) for dim in FINGERPRINT_DIMS]
        elif build_fingerprint_vector:
            vector = build_fingerprint_vector(source)
        else:
            return []

        try:
            hits = await self.vectors.search(
                namespace=COLLECTION_NAME,
                query=vector,
                n=n + 1,  # +1 to exclude self
                embedding_model="fp22",
            )
            similar = []
            for h in hits:
                if h.id == date_str:
                    continue
                similar.append({
                    "date": h.id,
                    "distance": round(1.0 - h.score, 4) if h.score else 0.0,
                    "summary": h.content,
                })
            return similar[:n]
        except Exception as e:
            logger.error("fingerprint_similarity_search_failed", error=str(e))
            return []
