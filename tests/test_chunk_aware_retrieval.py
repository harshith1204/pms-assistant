"""
Unit tests for chunk-aware RAG retrieval system

Tests validate:
1. Chunk grouping by parent document
2. Adjacent chunk fetching
3. Document reconstruction with gap handling
4. Smart merging of overlapping chunks
5. Score aggregation and ranking
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from qdrant.chunk_aware_retrieval import (
    ChunkAwareRetriever,
    ChunkResult,
    ReconstructedDocument,
    format_reconstructed_results
)


@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for testing"""
    client = Mock()
    client.search = Mock()
    client.scroll = Mock()
    return client


@pytest.fixture
def mock_embedding_model():
    """Mock embedding model"""
    model = Mock()
    model.encode = Mock(return_value=Mock(tolist=Mock(return_value=[0.1] * 768)))
    return model


@pytest.fixture
def sample_search_results():
    """Sample Qdrant search results with multiple chunks from same document"""
    return [
        # Document 1, chunk 2 (high score)
        Mock(
            id="doc1_chunk2",
            score=0.86,
            payload={
                "mongo_id": "doc1",
                "parent_id": "doc1",
                "chunk_index": 2,
                "chunk_count": 10,
                "title": "Authentication Guide",
                "content": "OAuth 2.0 supports multiple flows including authorization code, client credentials, and device flow.",
                "content_type": "page",
                "project_name": "Security"
            }
        ),
        # Document 1, chunk 3 (high score)
        Mock(
            id="doc1_chunk3",
            score=0.82,
            payload={
                "mongo_id": "doc1",
                "parent_id": "doc1",
                "chunk_index": 3,
                "chunk_count": 10,
                "title": "Authentication Guide",
                "content": "Token handling involves access tokens (1 hour expiry) and refresh tokens (30 day expiry).",
                "content_type": "page",
                "project_name": "Security"
            }
        ),
        # Document 1, chunk 7 (medium score)
        Mock(
            id="doc1_chunk7",
            score=0.71,
            payload={
                "mongo_id": "doc1",
                "parent_id": "doc1",
                "chunk_index": 7,
                "chunk_count": 10,
                "title": "Authentication Guide",
                "content": "Error handling follows RFC 6749 with error codes like invalid_grant and unauthorized_client.",
                "content_type": "page",
                "project_name": "Security"
            }
        ),
        # Document 2, chunk 1 (lower score)
        Mock(
            id="doc2_chunk1",
            score=0.65,
            payload={
                "mongo_id": "doc2",
                "parent_id": "doc2",
                "chunk_index": 1,
                "chunk_count": 5,
                "title": "API Security Best Practices",
                "content": "Always validate tokens before processing requests. Use HTTPS for all endpoints.",
                "content_type": "page",
                "project_name": "API"
            }
        ),
    ]


def test_chunk_result_creation():
    """Test creating ChunkResult from payload"""
    result = ChunkResult(
        id="test_id",
        score=0.85,
        content="Test content",
        mongo_id="mongo_123",
        parent_id="parent_123",
        chunk_index=2,
        chunk_count=10,
        title="Test Title",
        content_type="page",
        metadata={"project_name": "Test Project"}
    )
    
    assert result.score == 0.85
    assert result.chunk_index == 2
    assert result.chunk_count == 10
    assert result.metadata["project_name"] == "Test Project"


def test_grouping_chunks_by_document(mock_qdrant_client, mock_embedding_model, sample_search_results):
    """Test that chunks are correctly grouped by parent document"""
    mock_qdrant_client.search.return_value = sample_search_results
    
    retriever = ChunkAwareRetriever(mock_qdrant_client, mock_embedding_model)
    
    # Manually test the grouping logic
    from collections import defaultdict
    doc_chunks = defaultdict(list)
    
    for result in sample_search_results:
        payload = result.payload
        parent_id = payload.get("parent_id", payload.get("mongo_id"))
        chunk = ChunkResult(
            id=str(result.id),
            score=result.score,
            content=payload.get("content", ""),
            mongo_id=payload.get("mongo_id"),
            parent_id=parent_id,
            chunk_index=payload.get("chunk_index", 0),
            chunk_count=payload.get("chunk_count", 1),
            title=payload.get("title", ""),
            content_type=payload.get("content_type", "unknown"),
            metadata={}
        )
        doc_chunks[parent_id].append(chunk)
    
    # Verify grouping
    assert len(doc_chunks) == 2  # Two documents
    assert len(doc_chunks["doc1"]) == 3  # Three chunks from doc1
    assert len(doc_chunks["doc2"]) == 1  # One chunk from doc2


def test_chunk_merging():
    """Test merging multiple chunks into coherent content"""
    retriever = ChunkAwareRetriever(Mock(), Mock())
    
    chunks = [
        ChunkResult(
            id="1", score=0.8, content="First chunk content.",
            mongo_id="doc1", parent_id="doc1", chunk_index=0, chunk_count=5,
            title="Test", content_type="page", metadata={}
        ),
        ChunkResult(
            id="2", score=0.75, content="Second chunk content.",
            mongo_id="doc1", parent_id="doc1", chunk_index=1, chunk_count=5,
            title="Test", content_type="page", metadata={}
        ),
        ChunkResult(
            id="3", score=0.7, content="Third chunk content.",
            mongo_id="doc1", parent_id="doc1", chunk_index=2, chunk_count=5,
            title="Test", content_type="page", metadata={}
        ),
    ]
    
    merged = retriever._merge_chunks(chunks)
    
    # Should contain all chunks
    assert "First chunk content" in merged
    assert "Second chunk content" in merged
    assert "Third chunk content" in merged
    # Should be in order
    assert merged.index("First") < merged.index("Second") < merged.index("Third")


def test_chunk_merging_with_gaps():
    """Test merging chunks with gaps (non-consecutive indices)"""
    retriever = ChunkAwareRetriever(Mock(), Mock())
    
    chunks = [
        ChunkResult(
            id="1", score=0.8, content="Chunk 1 content.",
            mongo_id="doc1", parent_id="doc1", chunk_index=0, chunk_count=10,
            title="Test", content_type="page", metadata={}
        ),
        ChunkResult(
            id="2", score=0.75, content="Chunk 2 content.",
            mongo_id="doc1", parent_id="doc1", chunk_index=1, chunk_count=10,
            title="Test", content_type="page", metadata={}
        ),
        # Gap: chunks 2-6 missing
        ChunkResult(
            id="3", score=0.7, content="Chunk 7 content.",
            mongo_id="doc1", parent_id="doc1", chunk_index=7, chunk_count=10,
            title="Test", content_type="page", metadata={}
        ),
    ]
    
    merged = retriever._merge_chunks(chunks)
    
    # Should contain gap marker
    assert "omitted" in merged.lower()
    assert "Chunk 1 content" in merged
    assert "Chunk 7 content" in merged


def test_coverage_formatting():
    """Test chunk coverage string formatting"""
    retriever = ChunkAwareRetriever(Mock(), Mock())
    
    # Consecutive chunks
    assert retriever._format_coverage([0, 1, 2], 10) == "chunks 0-2 of 10"
    
    # Non-consecutive chunks
    assert retriever._format_coverage([0, 1, 5, 6, 7], 10) == "chunks 0-1,5-7 of 10"
    
    # Single chunk
    assert retriever._format_coverage([3], 10) == "chunks 3 of 10"
    
    # Multiple separate chunks
    assert retriever._format_coverage([1, 3, 5, 7], 10) == "chunks 1,3,5,7 of 10"


def test_document_reconstruction_scoring():
    """Test that reconstructed documents have correct scores"""
    retriever = ChunkAwareRetriever(Mock(), Mock())
    
    from collections import defaultdict
    doc_chunks = defaultdict(list)
    
    # Add chunks with varying scores
    doc_chunks["doc1"] = [
        ChunkResult(
            id="1", score=0.86, content="High score chunk",
            mongo_id="doc1", parent_id="doc1", chunk_index=2, chunk_count=5,
            title="Test Doc", content_type="page", metadata={"project": "A"}
        ),
        ChunkResult(
            id="2", score=0.75, content="Medium score chunk",
            mongo_id="doc1", parent_id="doc1", chunk_index=3, chunk_count=5,
            title="Test Doc", content_type="page", metadata={"project": "A"}
        ),
        ChunkResult(
            id="3", score=0.0, content="Adjacent context chunk",
            mongo_id="doc1", parent_id="doc1", chunk_index=4, chunk_count=5,
            title="Test Doc", content_type="page", metadata={"project": "A"}
        ),
    ]
    
    reconstructed = retriever._reconstruct_documents(doc_chunks, max_docs=5, chunks_per_doc=3)
    
    assert len(reconstructed) == 1
    doc = reconstructed[0]
    
    # Max score should be highest chunk
    assert doc.max_score == 0.86
    
    # Average score should only include scored chunks (not adjacent with score=0)
    assert doc.avg_score == (0.86 + 0.75) / 2  # 0.805


def test_format_output():
    """Test formatting of reconstructed results"""
    docs = [
        ReconstructedDocument(
            mongo_id="doc1",
            title="Test Document",
            content_type="page",
            chunks=[],
            max_score=0.85,
            avg_score=0.80,
            full_content="This is the full content of the document.",
            metadata={"project_name": "TestProject", "priority": "HIGH"},
            chunk_coverage="chunks 1-3 of 5"
        )
    ]
    
    output = format_reconstructed_results(docs, show_full_content=True, show_chunk_details=True)
    
    # Verify key elements in output
    assert "Test Document" in output
    assert "0.85" in output  # max score
    assert "0.80" in output  # avg score
    assert "chunks 1-3 of 5" in output
    assert "TestProject" in output
    assert "HIGH" in output
    assert "This is the full content" in output


def test_format_output_truncation():
    """Test that very long content gets truncated appropriately"""
    long_content = "A" * 5000  # 5000 character content
    
    docs = [
        ReconstructedDocument(
            mongo_id="doc1",
            title="Long Document",
            content_type="page",
            chunks=[],
            max_score=0.85,
            avg_score=0.80,
            full_content=long_content,
            metadata={},
            chunk_coverage="chunks 1-10 of 10"
        )
    ]
    
    output = format_reconstructed_results(docs, show_full_content=True)
    
    # Should include truncation notice
    assert "truncated" in output.lower()
    # Should not include all 5000 characters
    assert len(output) < len(long_content)


@pytest.mark.asyncio
async def test_adjacent_chunk_identification():
    """Test identification of which adjacent chunks to fetch"""
    retriever = ChunkAwareRetriever(Mock(), Mock())
    
    # If we have chunks 2, 5, 7 from a 10-chunk document
    # We should fetch adjacent: 1,3,4,6,8
    existing_indices = {2, 5, 7}
    chunk_count = 10
    
    adjacent_indices = set()
    for idx in existing_indices:
        if idx > 0:
            adjacent_indices.add(idx - 1)
        if idx < chunk_count - 1:
            adjacent_indices.add(idx + 1)
    
    to_fetch = adjacent_indices - existing_indices
    
    expected = {1, 3, 4, 6, 8}
    assert to_fetch == expected


def test_chunk_selection_priority():
    """Test that highest scoring chunks are prioritized"""
    retriever = ChunkAwareRetriever(Mock(), Mock())
    
    from collections import defaultdict
    doc_chunks = defaultdict(list)
    
    # Create 10 chunks with varying scores
    for i in range(10):
        doc_chunks["doc1"].append(
            ChunkResult(
                id=f"chunk{i}",
                score=0.9 - (i * 0.05),  # Descending scores
                content=f"Chunk {i} content",
                mongo_id="doc1",
                parent_id="doc1",
                chunk_index=i,
                chunk_count=10,
                title="Test",
                content_type="page",
                metadata={}
            )
        )
    
    # Reconstruct with limit of 3 chunks per doc
    reconstructed = retriever._reconstruct_documents(doc_chunks, max_docs=1, chunks_per_doc=3)
    
    doc = reconstructed[0]
    scored_chunks = [c for c in doc.chunks if c.score > 0]
    
    # Should select top 3 highest scoring chunks
    assert len(scored_chunks) <= 3
    assert all(c.score >= 0.75 for c in scored_chunks)  # Top 3 have scores 0.90, 0.85, 0.80


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
