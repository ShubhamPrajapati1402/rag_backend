from typing import List, Dict, Any
from loguru import logger
from sqlalchemy import select, and_
from app.db.session import SessionLocal
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.schemas.rag_state import RAGState
from app.services.embeddings import get_embeddings_model

def retriever_node(state: RAGState) -> dict:
    """
    Embeds the search query and retrieves top-K similar chunks from PostgreSQL (pgvector).
    """
    query = state.get("rewritten_query") or state.get("question", "")
    document_ids = state.get("document_ids")
    user_id = state.get("user_id")
    top_k = 20

    from app.services.rag.cache import RAGCacheService
    query_vector = RAGCacheService.get_cached_embedding(query)

    if not query_vector:
        logger.info(f"[RetrieverNode] Embedding query via Hugging Face: '{query[:60]}...'")
        try:
            embeddings_model = get_embeddings_model()
            query_vector = embeddings_model.embed_query(query)
            RAGCacheService.set_cached_embedding(query, query_vector)
        except Exception as e:
            logger.error(f"[RetrieverNode] Failed to generate query embedding: {e}")
            return {"documents": []}
    else:
        logger.info(f"[RetrieverNode] Redis embedding cache hit for query: '{query[:60]}...'")

    db = SessionLocal()
    try:
        # Construct cosine distance similarity query
        # pgvector cosine_distance operator: <=>
        cosine_dist = DocumentChunk.embedding.cosine_distance(query_vector)

        query_stmt = (
            select(
                DocumentChunk.id,
                DocumentChunk.document_id,
                DocumentChunk.chunk_index,
                DocumentChunk.page_number,
                DocumentChunk.text_content,
                DocumentChunk.metadata_json,
                Document.filename,
                Document.user_id,
                cosine_dist.label("distance")
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(Document.status == DocumentStatus.COMPLETED)
        )

        filters = []
        if document_ids:
            filters.append(Document.id.in_(document_ids))
        if user_id:
            # Allow document if owned by user or globally accessible (user_id is None)
            filters.append((Document.user_id == user_id) | (Document.user_id.is_(None)))

        if filters:
            query_stmt = query_stmt.where(and_(*filters))

        query_stmt = query_stmt.order_by(cosine_dist).limit(top_k)
        results = db.execute(query_stmt).all()

        # Context Stitching: Fetch immediate next chunk on the same page so table titles and table rows are never split
        next_chunk_keys = [(r.document_id, r.chunk_index + 1) for r in results]
        adjacent_chunks = {}
        if next_chunk_keys:
            from sqlalchemy import tuple_
            adj_results = db.query(DocumentChunk).filter(
                tuple_(DocumentChunk.document_id, DocumentChunk.chunk_index).in_(next_chunk_keys)
            ).all()
            for ac in adj_results:
                adjacent_chunks[(ac.document_id, ac.chunk_index)] = ac

        retrieved_docs: List[Dict[str, Any]] = []
        for r in results:
            meta = r.metadata_json or {}
            sheet_name = meta.get("sheet_name")
            
            # Cosine similarity = 1 - cosine_distance
            sim_score = max(0.0, 1.0 - float(r.distance))

            text = r.text_content
            # If there's an immediate next chunk on the same page, stitch them for full table and paragraph completeness
            next_chunk = adjacent_chunks.get((r.document_id, r.chunk_index + 1))
            if next_chunk and (next_chunk.page_number == r.page_number or not r.page_number):
                text = f"{text}\n\n{next_chunk.text_content}"

            retrieved_docs.append({
                "chunk_id": r.id,
                "document_id": r.document_id,
                "filename": r.filename,
                "chunk_index": r.chunk_index,
                "page_number": r.page_number or meta.get("page_number"),
                "sheet_name": sheet_name,
                "text_content": text,
                "metadata_json": meta,
                "similarity_score": round(sim_score, 4)
            })

        logger.info(f"[RetrieverNode] Retrieved {len(retrieved_docs)} candidate chunks with context stitching from database.")
        return {"documents": retrieved_docs}
    except Exception as e:
        logger.error(f"[RetrieverNode] Database retrieval query failed: {e}")
        return {"documents": []}
    finally:
        db.close()
