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
    top_k = 8

    logger.info(f"[RetrieverNode] Embedding query for vector search: '{query[:60]}...'")

    try:
        embeddings_model = get_embeddings_model()
        query_vector = embeddings_model.embed_query(query)
    except Exception as e:
        logger.error(f"[RetrieverNode] Failed to generate query embedding: {e}")
        return {"documents": []}

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

        retrieved_docs: List[Dict[str, Any]] = []
        for r in results:
            meta = r.metadata_json or {}
            sheet_name = meta.get("sheet_name")
            
            # Cosine similarity = 1 - cosine_distance
            sim_score = max(0.0, 1.0 - float(r.distance))

            retrieved_docs.append({
                "chunk_id": r.id,
                "document_id": r.document_id,
                "filename": r.filename,
                "chunk_index": r.chunk_index,
                "page_number": r.page_number or meta.get("page_number"),
                "sheet_name": sheet_name,
                "text_content": r.text_content,
                "metadata_json": meta,
                "similarity_score": round(sim_score, 4)
            })

        logger.info(f"[RetrieverNode] Retrieved {len(retrieved_docs)} candidate chunks from database.")
        return {"documents": retrieved_docs}
    except Exception as e:
        logger.error(f"[RetrieverNode] Database retrieval query failed: {e}")
        return {"documents": []}
    finally:
        db.close()
