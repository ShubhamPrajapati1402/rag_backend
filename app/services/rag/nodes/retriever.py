from typing import List, Dict, Any
from loguru import logger
from sqlalchemy import select, and_, func, text
from app.db.session import SessionLocal
from app.models.document import Document, DocumentChunk, DocumentStatus
from app.schemas.rag_state import RAGState
from app.services.embeddings import get_embeddings_model

async def retriever_node(state: RAGState) -> dict:
    """
    Hybrid Retriever Node:
    Performs dual-engine parallel retrieval combining:
    1. Dense Semantic Vector Search (pgvector cosine similarity)
    2. Sparse Lexical Search (PostgreSQL Full-Text Search / BM25 ts_rank_cd)
    Merges both candidate sets using Reciprocal Rank Fusion (RRF).
    """
    query = state.get("rewritten_query") or state.get("question", "")
    document_ids = state.get("document_ids")
    user_id = state.get("user_id")
    top_k = 20
    rrf_k = 60  # Standard RRF smoothing constant

    from app.services.rag.cache import RAGCacheService
    query_vector = RAGCacheService.get_cached_embedding(query)

    if not query_vector:
        logger.info(f"[RetrieverNode] Embedding query via Hugging Face: '{query[:60]}...'")
        try:
            embeddings_model = get_embeddings_model()
            import asyncio
            query_vector = await asyncio.wait_for(
                asyncio.to_thread(embeddings_model.embed_query, query),
                timeout=2.5
            )
            RAGCacheService.set_cached_embedding(query, query_vector)
        except Exception as e:
            logger.warning(f"[RetrieverNode] Hugging Face embedding timed out/failed ({e}). Utilizing fast Postgres Full-Text Search (FTS).")
            query_vector = None
    else:
        logger.info(f"[RetrieverNode] Redis embedding cache hit for query: '{query[:60]}...'")

    db = SessionLocal()
    try:
        # Common filters
        base_filters = [Document.status == DocumentStatus.COMPLETED]
        if document_ids:
            base_filters.append(Document.id.in_(document_ids))
        if user_id:
            base_filters.append((Document.user_id == user_id) | (Document.user_id.is_(None)))

        vector_results = []
        # --- 1. DENSE VECTOR RETRIEVAL ---
        if query_vector:
            cosine_dist = DocumentChunk.embedding.cosine_distance(query_vector)
            vector_stmt = (
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
                .where(and_(*base_filters))
                .order_by(cosine_dist)
                .limit(top_k)
            )
            vector_results = db.execute(vector_stmt).all()

        # --- 2. SPARSE FULL-TEXT / BM25 KEYWORD RETRIEVAL ---
        fts_results = []
        try:
            import re
            raw_tokens = [re.sub(r'[^a-zA-Z0-9]', '', w.lower()) for w in query.split()]
            stopwords = {"what", "which", "when", "where", "how", "why", "who", "whom", "this", "that", "these", "those", "have", "has", "had", "does", "done", "will", "would", "could", "should", "tell", "give", "from", "with", "about", "was", "were", "the", "for", "and", "are"}
            keywords = [w for w in raw_tokens if len(w) >= 3 and w not in stopwords]

            if keywords:
                or_query_str = " | ".join(keywords)
                fts_query = func.to_tsquery('english', or_query_str)
                fts_match = func.to_tsvector('english', DocumentChunk.text_content).op('@@')(fts_query)
                # Normalization flag 32 divides the rank by (length of document + 1) to prevent long PDFs from biasing over compact documents
                fts_rank = func.ts_rank_cd(
                    func.to_tsvector('english', DocumentChunk.text_content),
                    fts_query,
                    32
                )
                fts_stmt = (
                    select(
                        DocumentChunk.id,
                        DocumentChunk.document_id,
                        DocumentChunk.chunk_index,
                        DocumentChunk.page_number,
                        DocumentChunk.text_content,
                        DocumentChunk.metadata_json,
                        Document.filename,
                        Document.user_id,
                        fts_rank.label("rank")
                    )
                    .join(Document, DocumentChunk.document_id == Document.id)
                    .where(and_(*base_filters, fts_match))
                    .order_by(fts_rank.desc())
                    .limit(top_k)
                )
                fts_results = db.execute(fts_stmt).all()
        except Exception as fts_err:
            logger.warning(f"[RetrieverNode] FTS keyword search warning: {fts_err}")
            fts_results = []

        # --- 3. RECIPROCAL RANK FUSION (RRF) ---
        chunk_map: Dict[int, Dict[str, Any]] = {}
        rrf_scores: Dict[int, float] = {}

        # Score vector results
        for rank, r in enumerate(vector_results):
            cid = r.id
            if cid not in chunk_map:
                chunk_map[cid] = {
                    "raw": r,
                    "sim_score": max(0.0, 1.0 - float(r.distance)),
                    "found_in_vector": True,
                    "found_in_fts": False
                }
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))

        # Score FTS keyword results
        for rank, r in enumerate(fts_results):
            cid = r.id
            if cid not in chunk_map:
                chunk_map[cid] = {
                    "raw": r,
                    "sim_score": 0.5, # default baseline for pure keyword hits
                    "found_in_vector": False,
                    "found_in_fts": True
                }
            else:
                chunk_map[cid]["found_in_fts"] = True
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (rrf_k + rank + 1))

        # Sort all chunks by fused RRF score
        sorted_chunk_ids = sorted(rrf_scores.keys(), key=lambda cid: rrf_scores[cid], reverse=True)[:top_k]
        top_fused_chunks = [chunk_map[cid] for cid in sorted_chunk_ids]

        # Log fusion telemetry
        both_count = sum(1 for c in top_fused_chunks if c["found_in_vector"] and c["found_in_fts"])
        logger.info(
            f"[RetrieverNode] Hybrid Search: {len(vector_results)} Vector + {len(fts_results)} FTS -> "
            f"{len(top_fused_chunks)} Fused Chunks (Dual Matches: {both_count})"
        )

        # --- 4. CONTEXT STITCHING ---
        next_chunk_keys = [(c["raw"].document_id, c["raw"].chunk_index + 1) for c in top_fused_chunks]
        adjacent_chunks = {}
        if next_chunk_keys:
            from sqlalchemy import tuple_
            adj_results = db.query(DocumentChunk).filter(
                tuple_(DocumentChunk.document_id, DocumentChunk.chunk_index).in_(next_chunk_keys)
            ).all()
            for ac in adj_results:
                adjacent_chunks[(ac.document_id, ac.chunk_index)] = ac

        retrieved_docs: List[Dict[str, Any]] = []
        for item in top_fused_chunks:
            r = item["raw"]
            meta = r.metadata_json or {}
            sheet_name = meta.get("sheet_name")

            text_content = r.text_content
            next_chunk = adjacent_chunks.get((r.document_id, r.chunk_index + 1))
            if next_chunk and (next_chunk.page_number == r.page_number or not r.page_number):
                text_content = f"{text_content}\n\n{next_chunk.text_content}"

            retrieved_docs.append({
                "chunk_id": r.id,
                "document_id": r.document_id,
                "filename": r.filename,
                "chunk_index": r.chunk_index,
                "page_number": r.page_number or meta.get("page_number"),
                "sheet_name": sheet_name,
                "text_content": text_content,
                "metadata_json": meta,
                "similarity_score": round(item["sim_score"], 4),
                "rrf_score": round(rrf_scores[r.id], 5)
            })

        logger.info(f"[RetrieverNode] Hybrid context-stitched {len(retrieved_docs)} candidate chunks ready for reranking.")
        return {"documents": retrieved_docs}
    except Exception as e:
        logger.error(f"[RetrieverNode] Hybrid database retrieval query failed: {e}")
        return {"documents": []}
    finally:
        db.close()
