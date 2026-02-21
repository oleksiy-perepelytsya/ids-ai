"""ChromaDB storage for codebase and pattern caching"""

import chromadb
import asyncio
from typing import List, Dict, Optional
from ids.config import settings
from ids.utils import get_logger

logger = get_logger(__name__)


class ChromaStore:
    """ChromaDB storage for semantic search and caching"""
    
    def __init__(self):
        """Initialize ChromaDB client - deferred to async initialize()"""
        self.client = None
        self.collections = {}
    
    async def initialize(self):
        """Initialize Chroma connection with proper health checks"""
        try:
            host = settings.chromadb_host
            port = settings.chromadb_port
            
            # Wait for ChromaDB to be ready
            await asyncio.sleep(2)
            
            # Simple HttpClient initialization
            self.client = chromadb.HttpClient(host=host, port=port)
            
            logger.info("chromadb_connected", host=host, port=port)
            
        except Exception as e:
            logger.error("chromadb_initialization_failed", error=str(e), exc_info=True)
            raise
    
    def get_or_create_collection(self, name: str, metadata: Dict = None):
        """Get or create a collection"""
        if not self.client:
            raise Exception("ChromaDB client not initialized. Call initialize() first.")

        collection_metadata = metadata or {"hnsw:space": "cosine"}

        try:
            return self.client.get_or_create_collection(
                name=name,
                metadata=collection_metadata
            )
        except KeyError as e:
            if "_type" in str(e):
                # ChromaDB version mismatch: existing collection lacks '_type' in its
                # embedding function metadata. Delete and recreate it.
                logger.warning("collection_type_mismatch_recreating", name=name)
                try:
                    self.client.delete_collection(name=name)
                except Exception:
                    pass
                return self.client.create_collection(name=name, metadata=collection_metadata)
            logger.error("collection_get_or_create_failed", name=name, error=str(e))
            raise
        except Exception as e:
            logger.error("collection_get_or_create_failed", name=name, error=str(e))
            raise
    
    async def cache_codebase(
        self, 
        project_id: str, 
        files: Dict[str, str]
    ) -> None:
        """
        Cache entire codebase for a project.
        
        Args:
            project_id: Project identifier
            files: Dict of filepath -> file_content
        """
        collection_name = f"codebase_{project_id}"
        collection = self.get_or_create_collection(collection_name)
        
        # Prepare documents for ChromaDB
        documents = []
        metadatas = []
        ids = []
        
        for filepath, content in files.items():
            documents.append(content)
            metadatas.append({
                "filepath": filepath,
                "project_id": project_id
            })
            ids.append(f"{project_id}:{filepath}")
        
        if documents:
            collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids
            )
            logger.info(
                "codebase_cached",
                project_id=project_id,
                file_count=len(documents)
            )
    
    async def search_codebase(
        self,
        project_id: str,
        query: str,
        n_results: int = 5
    ) -> List[Dict]:
        """
        Search codebase for relevant files.
        
        Args:
            project_id: Project identifier
            query: Search query
            n_results: Number of results to return
            
        Returns:
            List of relevant files with content
        """
        collection_name = f"codebase_{project_id}"
        try:
            collection = self.client.get_collection(name=collection_name)
        except Exception:
            logger.warning("codebase_not_found", project_id=project_id)
            return []
        
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        # Format results
        formatted = []
        if results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                formatted.append({
                    "content": doc,
                    "filepath": results["metadatas"][0][i]["filepath"],
                    "distance": results["distances"][0][i] if "distances" in results else None
                })
        
        return formatted
    
    async def get_full_codebase(self, project_id: str) -> Optional[str]:
        """
        Get entire codebase as single string for LLM context.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Complete codebase or None
        """
        collection_name = f"codebase_{project_id}"
        try:
            collection = self.client.get_collection(name=collection_name)
        except Exception:
            logger.warning("codebase_not_found", project_id=project_id)
            return None
        
        # Get all documents
        results = collection.get()
        
        if not results["documents"]:
            return None
        
        # Build complete codebase string
        codebase_parts = []
        for i, content in enumerate(results["documents"]):
            filepath = results["metadatas"][i]["filepath"]
            codebase_parts.append(f"# File: {filepath}\n{content}\n\n")
        
        return "\n".join(codebase_parts)

    async def add_learning_pattern(
        self,
        project_id: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Add a learning pattern (feedback or text insight) to ChromaDB.

        Args:
            project_id: Project identifier
            content: The text to learn
            metadata: Optional additional metadata
        """
        try:
            collection_name = f"learning_{project_id}"
            collection = self.get_or_create_collection(collection_name)

            import uuid
            pattern_id = f"pattern_{uuid.uuid4().hex[:8]}"

            collection.add(
                documents=[content],
                metadatas=[metadata or {"project_id": project_id, "source": "learning"}],
                ids=[pattern_id]
            )
            logger.info("learning_pattern_added", project_id=project_id, pattern_id=pattern_id)
        except Exception as e:
            # Non-fatal: learning failure must not block deliberation or user flows
            logger.error("add_learning_pattern_failed", project_id=project_id, error=str(e))

    async def search_learning_patterns(
        self,
        project_id: str,
        query: str,
        n_results: int = 5
    ) -> List[Dict]:
        """
        Search for relevant learning patterns.
        """
        collection_name = f"learning_{project_id}"
        try:
            collection = self.client.get_collection(name=collection_name)
        except Exception:
            logger.warning("learning_store_not_found", project_id=project_id)
            return []
        
        results = collection.query(
            query_texts=[query],
            n_results=n_results
        )
        
        formatted = []
        if results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                formatted.append({
                    "content": doc,
                    "metadata": results["metadatas"][0][i],
                    "distance": results["distances"][0][i] if "distances" in results else None
                })
        
        return formatted
