"""Fingerprint store — persists daily planetary fingerprints to MongoDB + ChromaDB."""

import sys
import os
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from ids.config import settings
from ids.utils import get_logger

logger = get_logger(__name__)

# Import schema helpers from project root
_schema_dir = os.path.join(os.path.dirname(__file__), "..", "..", "..")
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
    """Stores daily planetary fingerprints in MongoDB and ChromaDB."""

    def __init__(self, chroma_store):
        self.chroma = chroma_store
        self.client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db = self.client[settings.mongodb_db]
        self.collection = self.db[COLLECTION_NAME]

    async def ensure_indexes(self) -> None:
        """Create MongoDB indexes on first use."""
        await self.collection.create_index("date", unique=True)
        await self.collection.create_index([("lunar.phase_name", 1), ("date", 1)])
        await self.collection.create_index([("solar.kp_index", 1), ("date", 1)])
        await self.collection.create_index([("tides.spring_neap_position", 1), ("date", 1)])
        logger.info("fingerprint_indexes_ensured")

    async def upsert(self, doc: dict) -> dict:
        """
        Store a daily fingerprint document.

        1. Builds the 16-dim vector and fingerprint_components from schema helpers.
        2. Upserts into MongoDB (keyed on date).
        3. Upserts into ChromaDB with the custom embedding vector.

        Returns the stored document with fingerprint_components populated.
        """
        date_str = doc["date"]

        # Build fingerprint components
        if build_fingerprint_vector:
            vector = build_fingerprint_vector(doc)
            doc["fingerprint_components"] = dict(zip(
                [
                    "solar_activity", "lunar_tidal_force", "lunar_phase", "lunar_distance",
                    "planetary_perturbation", "geomagnetic_disturbance", "med_wind_strength",
                    "med_sea_state", "med_pressure_anomaly", "nao_state", "enso_state",
                    "tidal_range_composite", "seismic_activity", "solar_cycle_position",
                    "lunar_node_cycle", "season_position",
                ],
                [round(v, 4) for v in vector]
            ))
        else:
            vector = [0.5] * 16
            doc["fingerprint_components"] = {}

        # 1. MongoDB upsert
        await self.collection.replace_one(
            {"date": date_str},
            doc,
            upsert=True
        )
        logger.info("fingerprint_mongo_upserted", date=date_str)

        # 2. ChromaDB upsert with custom embedding
        try:
            chroma_collection = self.chroma.get_or_create_collection(
                COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"}
            )
            chroma_doc = build_chromadb_document(doc) if build_chromadb_document else date_str
            metadata = build_chromadb_metadata(doc) if build_chromadb_metadata else {"date": date_str}

            chroma_collection.upsert(
                ids=[date_str],
                embeddings=[vector],
                documents=[chroma_doc],
                metadatas=[metadata],
            )
            logger.info("fingerprint_chroma_upserted", date=date_str)
        except Exception as e:
            logger.error("fingerprint_chroma_failed", date=date_str, error=str(e))

        return doc

    async def get(self, date_str: str) -> Optional[dict]:
        """Retrieve a fingerprint by date."""
        doc = await self.collection.find_one({"date": date_str})
        if doc:
            doc.pop("_id", None)
        return doc

    async def find_similar(self, date_str: str, n: int = 5) -> list:
        """
        Find historically similar days using ChromaDB vector similarity.
        Returns list of (date, distance, summary) tuples.
        """
        source = await self.get(date_str)
        if not source or not build_fingerprint_vector:
            return []

        vector = build_fingerprint_vector(source)
        try:
            chroma_collection = self.chroma.get_or_create_collection(COLLECTION_NAME)
            results = chroma_collection.query(
                query_embeddings=[vector],
                n_results=n + 1,  # +1 to exclude self
                include=["documents", "metadatas", "distances"],
            )
            similar = []
            for i, doc_id in enumerate(results["ids"][0]):
                if doc_id == date_str:
                    continue
                similar.append({
                    "date": doc_id,
                    "distance": round(results["distances"][0][i], 4),
                    "summary": results["documents"][0][i],
                })
            return similar[:n]
        except Exception as e:
            logger.error("fingerprint_similarity_search_failed", error=str(e))
            return []
