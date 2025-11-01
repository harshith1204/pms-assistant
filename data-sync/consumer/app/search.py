import argparse
import os
from typing import Dict

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sentence_transformers import SentenceTransformer

from qdrant.encoder import get_splade_encoder


def _load_embedder() -> SentenceTransformer:
    model_name = os.getenv("EMBEDDING_MODEL", "google/embeddinggemma-300m")
    fallback_name = os.getenv("FALLBACK_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    try:
        return SentenceTransformer(model_name)
    except Exception:
        return SentenceTransformer(fallback_name)


EMBEDDER = _load_embedder()
SPLADE_ENCODER = get_splade_encoder()


def build_query_vector(text: str) -> Dict[str, qmodels.NamedVectorStruct]:
    dense_vector = EMBEDDER.encode(text).tolist()
    sparse_raw = SPLADE_ENCODER.encode_text(text)
    query: Dict[str, qmodels.NamedVectorStruct] = {
        "dense": qmodels.NamedVectorStruct(name="dense", vector=dense_vector)
    }
    if sparse_raw.get("indices"):
        query["sparse"] = qmodels.NamedSparseVectorStruct(
            name="sparse",
            vector=qmodels.SparseVector(indices=sparse_raw["indices"], values=sparse_raw["values"]),
        )
    return query


def main() -> None:
    parser = argparse.ArgumentParser(description="Hybrid search against Qdrant")
    parser.add_argument("--query", required=True, help="Query text")
    parser.add_argument("--limit", type=int, default=5, help="Number of results")
    args = parser.parse_args()

    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
    collection = os.getenv("QDRANT_COLLECTION", "ProjectManagement")

    client = QdrantClient(url=qdrant_url)

    query_vectors = build_query_vector(args.query)
    named_vectors = list(query_vectors.values())

    result = client.search(
        collection_name=collection,
        query_vector=named_vectors,
        limit=args.limit,
        with_payload=True,
    )

    for idx, point in enumerate(result, start=1):
        payload = point.payload or {}
        title = payload.get("title")
        content_type = payload.get("content_type")
        score = point.score
        print(f"{idx}. score={score:.4f} type={content_type} title={title}")


if __name__ == "__main__":
    main()
