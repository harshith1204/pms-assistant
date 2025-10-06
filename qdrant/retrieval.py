"""
Chunk-Aware RAG Retrieval System

Improves context quality by:
1. Retrieving multiple relevant chunks from the same document
2. Fetching adjacent chunks for better context continuity
3. Reconstructing documents from related chunks
4. Deduplicating and merging overlapping chunks intelligently
"""

from typing import List, Dict, Any, Optional, Set, Tuple
from mongo.constants import BUSINESS_UUID
from collections import defaultdict
from dataclasses import dataclass
import asyncio


@dataclass
class ChunkResult:
    """Represents a single chunk with metadata"""
    id: str
    score: float
    content: str
    mongo_id: str
    parent_id: str
    chunk_index: int
    chunk_count: int
    title: str
    content_type: str
    metadata: Dict[str, Any]


@dataclass
class ReconstructedDocument:
    """Represents a document reconstructed from multiple chunks"""
    mongo_id: str
    title: str
    content_type: str
    chunks: List[ChunkResult]
    max_score: float
    avg_score: float
    full_content: str
    metadata: Dict[str, Any]
    chunk_coverage: str  # e.g., "chunks 1,2,5 of 10"


class ChunkAwareRetriever:
    """Enhanced RAG retrieval with chunk awareness and context reconstruction"""
    
    def __init__(self, qdrant_client, embedding_model):
        self.qdrant_client = qdrant_client
        self.embedding_model = embedding_model
    
    async def search_with_context(
        self,
        query: str,
        collection_name: str,
        content_type: Optional[str] = None,
        limit: int = 5,
        chunks_per_doc: int = 2,
        include_adjacent: bool = True,
        min_score: float = 0.6
    ) -> List[ReconstructedDocument]:
        """
        Perform chunk-aware search with context reconstruction.
        
        Args:
            query: Search query
            collection_name: Qdrant collection name
            content_type: Filter by content type
            limit: Max number of DOCUMENTS to return (not chunks)
            chunks_per_doc: Max chunks to retrieve per document
            include_adjacent: Whether to fetch adjacent chunks for context
            min_score: Minimum relevance score threshold
            
        Returns:
            List of reconstructed documents with full context
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        # Step 1: Initial vector search (retrieve more chunks to cover more docs)
        query_embedding = self.embedding_model.encode(query).tolist()
        
        # Build filter with optional content_type and global business scoping
        must_conditions = []
        if content_type:
            must_conditions.append(FieldCondition(key="content_type", match=MatchValue(value=content_type)))
        if BUSINESS_UUID:
            must_conditions.append(FieldCondition(key="business_id", match=MatchValue(value=BUSINESS_UUID)))
        # Prefer chunked points only (exclude legacy unchunked points)
        try:
            # Try importing Range dynamically for compatibility across client versions
            from qdrant_client.models import Range as _QRange  # type: ignore
        except Exception:
            try:
                from qdrant_client.http.models import Range as _QRange  # type: ignore
            except Exception:
                _QRange = None  # type: ignore

        try:
            if _QRange is not None:
                must_conditions.append(
                    FieldCondition(key="chunk_count", range=_QRange(gte=1))
                )
        except Exception:
            # If Range or field is unsupported, proceed without this preference
            pass
        search_filter = Filter(must=must_conditions) if must_conditions else None
        
        # Fetch more chunks initially to ensure we have multiple per document
        initial_limit = max(10, limit * chunks_per_doc * 2)
        
        search_results = self.qdrant_client.search(
            collection_name=collection_name,
            query_vector=query_embedding,
            query_filter=search_filter,
            limit=initial_limit,
            with_payload=True,
            score_threshold=min_score
        )
        
        if not search_results:
            return []
        
        # Step 2: Group chunks by parent document
        doc_chunks: Dict[str, List[ChunkResult]] = defaultdict(list)
        
        for result in search_results:
            payload = result.payload or {}
            
            # Prefer 'content'; fallback to 'full_text' or title if missing
            content_text = payload.get("content") or payload.get("full_text") or payload.get("title", "")

            chunk = ChunkResult(
                id=str(result.id),
                score=result.score,
                content=content_text,
                mongo_id=payload.get("mongo_id", ""),
                parent_id=payload.get("parent_id", payload.get("mongo_id", "")),
                chunk_index=payload.get("chunk_index", 0),
                chunk_count=payload.get("chunk_count", 1),
                title=payload.get("title", "Untitled"),
                content_type=payload.get("content_type", "unknown"),
                metadata={k: v for k, v in payload.items() 
                         if k not in ["content", "full_text", "mongo_id", "parent_id", 
                                     "chunk_index", "chunk_count", "title", "content_type"]}
            )
            
            parent_id = chunk.parent_id or chunk.mongo_id
            doc_chunks[parent_id].append(chunk)
        
        # Step 3: Fetch adjacent chunks for better context (if enabled)
        if include_adjacent:
            await self._fetch_adjacent_chunks(doc_chunks, collection_name, content_type)
        
        # Step 4: Reconstruct documents from chunks
        reconstructed_docs = self._reconstruct_documents(
            doc_chunks, 
            max_docs=limit,
            chunks_per_doc=chunks_per_doc
        )
        
        return reconstructed_docs
    
    async def _fetch_adjacent_chunks(
        self,
        doc_chunks: Dict[str, List[ChunkResult]],
        collection_name: str,
        content_type: Optional[str]
    ):
        """
        Fetch adjacent chunks to fill gaps and provide better context.
        Modifies doc_chunks in place.
        """
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        for parent_id, chunks in doc_chunks.items():
            if not chunks:
                continue
            
            # Find the chunk with highest score
            best_chunk = max(chunks, key=lambda c: c.score)
            chunk_count = best_chunk.chunk_count
            
            # Determine which chunks we have
            existing_indices = {c.chunk_index for c in chunks}
            
            # Identify adjacent chunks to fetch (±1 from each existing chunk)
            adjacent_indices: Set[int] = set()
            for idx in existing_indices:
                if idx > 0:
                    adjacent_indices.add(idx - 1)
                if idx < chunk_count - 1:
                    adjacent_indices.add(idx + 1)
            
            # Remove indices we already have
            to_fetch = adjacent_indices - existing_indices
            
            if not to_fetch:
                continue
            
            # Fetch missing adjacent chunks using scroll/search by parent_id and chunk_index
            # Note: This requires a compound filter which Qdrant supports
            for chunk_idx in to_fetch:
                try:
                    filter_conditions = [
                        FieldCondition(key="parent_id", match=MatchValue(value=parent_id)),
                        FieldCondition(key="chunk_index", match=MatchValue(value=chunk_idx))
                    ]
                    
                    if content_type:
                        filter_conditions.append(
                            FieldCondition(key="content_type", match=MatchValue(value=content_type))
                        )
                    if BUSINESS_UUID:
                        filter_conditions.append(
                            FieldCondition(key="business_id", match=MatchValue(value=BUSINESS_UUID))
                        )
                    
                    # Use scroll to find specific chunk (more efficient than search for exact match)
                    scroll_result = self.qdrant_client.scroll(
                        collection_name=collection_name,
                        scroll_filter=Filter(must=filter_conditions),
                        limit=1,
                        with_payload=True,
                        with_vectors=False
                    )
                    
                    if scroll_result and scroll_result[0]:
                        for point in scroll_result[0]:
                            payload = point.payload or {}
                            # Prefer 'content'; fallback to 'full_text' or title if missing
                            adj_content_text = payload.get("content") or payload.get("full_text") or payload.get("title", "")

                            adjacent_chunk = ChunkResult(
                                id=str(point.id),
                                score=0.0,  # Adjacent chunks get 0 score (context only)
                                content=adj_content_text,
                                mongo_id=payload.get("mongo_id", ""),
                                parent_id=payload.get("parent_id", payload.get("mongo_id", "")),
                                chunk_index=payload.get("chunk_index", 0),
                                chunk_count=payload.get("chunk_count", 1),
                                title=payload.get("title", "Untitled"),
                                content_type=payload.get("content_type", "unknown"),
                                metadata={k: v for k, v in payload.items() 
                                         if k not in ["content", "full_text", "mongo_id", "parent_id",
                                                     "chunk_index", "chunk_count", "title", "content_type"]}
                            )
                            chunks.append(adjacent_chunk)
                
                except Exception as e:
                    print(f"Warning: Could not fetch adjacent chunk {chunk_idx} for {parent_id}: {e}")
                    continue
    
    def _reconstruct_documents(
        self,
        doc_chunks: Dict[str, List[ChunkResult]],
        max_docs: int,
        chunks_per_doc: int
    ) -> List[ReconstructedDocument]:
        """
        Reconstruct full documents from chunks with smart ordering and deduplication.
        """
        reconstructed = []
        
        # Sort documents by best chunk score
        sorted_docs = sorted(
            doc_chunks.items(),
            key=lambda x: max(c.score for c in x[1]),
            reverse=True
        )
        
        for parent_id, chunks in sorted_docs[:max_docs]:
            if not chunks:
                continue
            
            # Sort chunks by index for proper document reconstruction
            chunks.sort(key=lambda c: c.chunk_index)
            
            # Limit chunks per document (keep highest scoring + adjacent for context)
            scored_chunks = [c for c in chunks if c.score > 0]
            context_chunks = [c for c in chunks if c.score == 0]
            
            # Keep top scoring chunks plus their adjacent context
            top_scored = sorted(scored_chunks, key=lambda c: c.score, reverse=True)[:chunks_per_doc]
            top_indices = {c.chunk_index for c in top_scored}
            
            # Include adjacent context chunks
            relevant_context = [
                c for c in context_chunks 
                if any(abs(c.chunk_index - idx) <= 1 for idx in top_indices)
            ]
            
            selected_chunks = sorted(top_scored + relevant_context, key=lambda c: c.chunk_index)
            
            # Calculate statistics
            scored = [c for c in selected_chunks if c.score > 0]
            max_score = max(c.score for c in scored) if scored else 0.0
            avg_score = sum(c.score for c in scored) / len(scored) if scored else 0.0
            
            # Reconstruct full content with smart merging
            full_content = self._merge_chunks(selected_chunks)
            
            # Build chunk coverage info
            # Convert to 1-based indices for display
            chunk_indices = sorted([c.chunk_index + 1 for c in selected_chunks])
            total_chunks = chunks[0].chunk_count if chunks else 1
            coverage = self._format_coverage(chunk_indices, total_chunks)
            
            # Use metadata from best scoring chunk
            best_chunk = max(chunks, key=lambda c: c.score)
            
            doc = ReconstructedDocument(
                mongo_id=parent_id,
                title=best_chunk.title,
                content_type=best_chunk.content_type,
                chunks=selected_chunks,
                max_score=max_score,
                avg_score=avg_score,
                full_content=full_content,
                metadata=best_chunk.metadata,
                chunk_coverage=coverage
            )
            
            reconstructed.append(doc)
        
        return reconstructed
    
    def _merge_chunks(self, chunks: List[ChunkResult]) -> str:
        """
        Intelligently merge chunks, handling overlaps and maintaining readability.
        """
        if not chunks:
            return ""
        
        if len(chunks) == 1:
            return chunks[0].content
        
        # For now, use simple concatenation with markers
        # TODO: Implement overlap detection and smart merging
        merged_parts = []
        
        for i, chunk in enumerate(chunks):
            if i > 0:
                prev_chunk = chunks[i - 1]
                # Check if chunks are adjacent
                if chunk.chunk_index == prev_chunk.chunk_index + 1:
                    # Adjacent chunks - they overlap, try to merge smoothly
                    # For now, just add separator
                    merged_parts.append("\n")
                else:
                    # Gap in chunks - add clear separator
                    merged_parts.append(f"\n\n[... chunk {prev_chunk.chunk_index + 1} to {chunk.chunk_index - 1} omitted ...]\n\n")
            
            merged_parts.append(chunk.content)
        
        return "".join(merged_parts)
    
    def _format_coverage(self, indices: List[int], total: int) -> str:
        """
        Format chunk coverage info (e.g., 'chunks 1-3,5,7-9 of 12')
        """
        if not indices:
            return "no chunks"
        
        # Group consecutive indices into ranges
        ranges = []
        start = indices[0]
        end = indices[0]
        
        for idx in indices[1:]:
            if idx == end + 1:
                end = idx
            else:
                ranges.append(f"{start}-{end}" if start != end else f"{start}")
                start = end = idx
        
        ranges.append(f"{start}-{end}" if start != end else f"{start}")
        
        return f"chunks {','.join(ranges)} of {total}"


def format_reconstructed_results(
    docs: List[ReconstructedDocument],
    show_full_content: bool = True,
    show_chunk_details: bool = True
) -> str:
    """
    Format reconstructed documents for display to LLM.
    
    Args:
        docs: List of reconstructed documents
        show_full_content: Whether to show full merged content
        show_chunk_details: Whether to show individual chunk scores
        
    Returns:
        Formatted string representation
    """
    if not docs:
        return "No results found."
    
    response_parts = []
    response_parts.append(f"🔍 CHUNK-AWARE RETRIEVAL: {len(docs)} document(s) reconstructed\n")
    
    for i, doc in enumerate(docs, 1):
        response_parts.append(f"\n[{i}] {doc.content_type.upper()}: {doc.title}")
        response_parts.append(f"    Relevance: {doc.max_score:.3f} (avg: {doc.avg_score:.3f})")
        response_parts.append(f"    Coverage: {doc.chunk_coverage}")
        
        # Show metadata compactly
        meta = []
        if doc.metadata.get('project_name'):
            meta.append(f"Project: {doc.metadata['project_name']}")
        if doc.metadata.get('priority'):
            meta.append(f"Priority: {doc.metadata['priority']}")
        if doc.metadata.get('state_name'):
            meta.append(f"State: {doc.metadata['state_name']}")
        if doc.metadata.get('assignee_name'):
            meta.append(f"Assignee: {doc.metadata['assignee_name']}")
        if doc.metadata.get('visibility'):
            meta.append(f"Visibility: {doc.metadata['visibility']}")
        
        if meta:
            response_parts.append(f"    {' | '.join(meta)}")
        
        # Show chunk details if requested
        if show_chunk_details and len(doc.chunks) > 1:
            scored_chunks = [c for c in doc.chunks if c.score > 0]
            if scored_chunks:
                chunk_info = ", ".join([f"#{c.chunk_index}({c.score:.2f})" for c in scored_chunks])
                response_parts.append(f"    Matched chunks: {chunk_info}")
        
        # Show full content without truncation so the LLM has complete context for synthesis
        # This enables the LLM to generate properly formatted, accurate responses based on actual content
        if show_full_content:
            content = doc.full_content
            response_parts.append(f"\n    === CONTENT START ===")
            response_parts.append(content)
            response_parts.append(f"    === CONTENT END ===")
        
        response_parts.append("")  # Empty line between docs
    
    return "\n".join(response_parts)

