from typing import Iterable, Dict, Any, List

from qdrant_client.http.models import PointStruct
from qdrant_client.conversions import common_types as types

from constants import QDRANT_COLLECTION_NAME, DEFAULT_EMBEDDING_DIM
from registry import VECTOR_REGISTRY
from .dbconnection import ensure_collection, get_qdrant_client


def ensure_default_collection():
    # Use the default embedding size; allow override per registry if present
    vector_size = DEFAULT_EMBEDDING_DIM
    ensure_collection(QDRANT_COLLECTION_NAME, vector_size=vector_size, enable_sparse=True)


def _build_point(doc_id: str, dense_vector: List[float], payload: Dict[str, Any], sparse_vector: Dict[int, float] | None = None) -> PointStruct:
    point = PointStruct(id=doc_id, vector={"text": dense_vector}, payload=payload)
    if sparse_vector:
        # Qdrant client accepts separate arg for sparse vectors via upsert method, but PointStruct allows embedding sparse under dedicated param in new versions.
        # We'll pass sparse via upsert's sparse_vectors kw.
        pass
    return point


def upsert_documents(
    items: Iterable[Dict[str, Any]],
    collection: str | None = None,
    vector_size: int | None = None,
) -> None:
    """
    Upsert documents into Qdrant. Auto-creates collection with hybrid search if missing.
    Expects each item to contain:
      - id: unique id
      - vector: dense embedding as List[float]
      - payload: arbitrary payload dict
      - optional sparse: mapping of index->weight for hybrid retrieval
    """
    target_collection = collection or QDRANT_COLLECTION_NAME
    eff_vector_size = vector_size or DEFAULT_EMBEDDING_DIM

    ensure_collection(target_collection, vector_size=eff_vector_size, enable_sparse=True)

    client = get_qdrant_client()

    points: List[PointStruct] = []
    sparse_list: List[types.SparseVector] = []

    for item in items:
        doc_id = item["id"]
        vector = item["vector"]
        payload = item.get("payload", {})
        sparse = item.get("sparse")

        points.append(PointStruct(id=doc_id, vector={"text": vector}, payload=payload))
        if sparse:
            # Convert dict to qdrant SparseVector format
            indices = list(sparse.keys())
            values = [sparse[i] for i in indices]
            sparse_list.append(types.SparseVector(indices=indices, values=values))
        else:
            sparse_list.append(None)  # keep alignment

    # Upsert with optional sparse vectors
    client.upload_points(
        collection_name=target_collection,
        points=points,
        sparse_vectors={"text_sparse": sparse_list} if any(s is not None for s in sparse_list) else None,
        wait=True,
    )

