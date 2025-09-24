from typing import Optional
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.http.models import Distance, VectorParams, SparseVectorParams, OptimizersConfig

from constants import QDRANT_URL, QDRANT_API_KEY


_client: Optional[QdrantClient] = None


def get_qdrant_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None, timeout=30.0)
    return _client


def ensure_collection(collection: str, vector_size: int, enable_sparse: bool = True) -> None:
    """
    Ensure a Qdrant collection exists. If not, create it with hybrid search support:
    - Dense vector space using cosine distance
    - Sparse vectors (BM25/TF-IDF) enabled when enable_sparse=True
    """
    client = get_qdrant_client()

    try:
        exists = client.collection_exists(collection)
    except UnexpectedResponse:
        exists = False

    if exists:
        return

    vectors_config = {
        "text": VectorParams(size=vector_size, distance=Distance.COSINE),
    }

    # Hybrid: add sparse vectors namespace as "text_sparse"
    sparse_config = {"text_sparse": SparseVectorParams(index=True)} if enable_sparse else None

    client.recreate_collection(
        collection_name=collection,
        vectors_config=vectors_config,
        sparse_vectors_config=sparse_config,
        optimizers_config=OptimizersConfig(
            default_segment_number=2
        ),
    )

