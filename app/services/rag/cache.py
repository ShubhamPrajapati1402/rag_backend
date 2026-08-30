import json
import hashlib
from typing import Optional, List, Dict, Any
from loguru import logger
from app.core.redis_client import get_redis_client

class RAGCacheService:
    """
    High-performance Redis caching service for RAG embeddings and Q&A responses.
    """

    @staticmethod
    def _hash_key(*args) -> str:
        raw = ":".join(str(a) for a in args)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def get_cached_embedding(cls, text: str) -> Optional[List[float]]:
        """
        Retrieves a cached 1024-dim embedding vector from Redis in <1ms.
        """
        try:
            r = get_redis_client()
            key = f"emb:{cls._hash_key(text.strip().lower())}"
            cached = r.get(key)
            if cached:
                logger.debug(f"[RAGCache] Cache HIT for embedding: '{text[:40]}...'")
                return json.loads(cached)
        except Exception as e:
            logger.debug(f"[RAGCache] Redis get_cached_embedding error: {e}")
        return None

    @classmethod
    def set_cached_embedding(cls, text: str, vector: List[float], ttl: int = 86400):
        """
        Stores an embedding vector in Redis with a 24-hour default TTL.
        """
        try:
            r = get_redis_client()
            key = f"emb:{cls._hash_key(text.strip().lower())}"
            r.setex(key, ttl, json.dumps(vector))
            logger.debug(f"[RAGCache] Cached embedding for: '{text[:40]}...'")
        except Exception as e:
            logger.debug(f"[RAGCache] Redis set_cached_embedding error: {e}")

    @classmethod
    def get_cached_response(
        cls,
        user_id: Optional[int],
        document_ids: Optional[List[int]],
        query: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieves an exact cached RAG response + citations in <5ms.
        """
        try:
            r = get_redis_client()
            sorted_docs = sorted(document_ids) if document_ids else "all"
            key = f"rag_res:{cls._hash_key(user_id or 'global', sorted_docs, query.strip().lower())}"
            cached = r.get(key)
            if cached:
                logger.info(f"[RAGCache] Cache HIT for query: '{query[:50]}...'")
                return json.loads(cached)
        except Exception as e:
            logger.debug(f"[RAGCache] Redis get_cached_response error: {e}")
        return None

    @classmethod
    def set_cached_response(
        cls,
        user_id: Optional[int],
        document_ids: Optional[List[int]],
        query: str,
        response_data: Dict[str, Any],
        ttl: int = 3600
    ):
        """
        Caches a generated RAG answer + citations for 1 hour.
        """
        try:
            r = get_redis_client()
            sorted_docs = sorted(document_ids) if document_ids else "all"
            key = f"rag_res:{cls._hash_key(user_id or 'global', sorted_docs, query.strip().lower())}"
            r.setex(key, ttl, json.dumps(response_data))
            logger.debug(f"[RAGCache] Cached RAG response for: '{query[:50]}...'")
        except Exception as e:
            logger.debug(f"[RAGCache] Redis set_cached_response error: {e}")

    @classmethod
    def invalidate_all_rag_responses(cls):
        """
        Flushes all cached Q&A responses when documents are uploaded or deleted.
        Ensures new documents are immediately discoverable.
        """
        try:
            r = get_redis_client()
            keys = r.keys("rag_res:*")
            if keys:
                r.delete(*keys)
                logger.info(f"[RAGCache] Invalidated {len(keys)} cached RAG responses.")
        except Exception as e:
            logger.debug(f"[RAGCache] Redis invalidate error: {e}")
