import argparse
import os
from typing import List

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels


def main():
    parser = argparse.ArgumentParser(description="Embed a text query and search in Qdrant")
    parser.add_argument("--query", required=True, help="Text to embed and search")
    parser.add_argument("--limit", type=int, default=5, help="Number of results")
    args = parser.parse_args()

    qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
    collection = os.getenv("QDRANT_COLLECTION", "documents")
    embedding_model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")

    embedder = TextEmbedding(model_name=embedding_model)
    vector: List[float] = [float(x) for x in next(embedder.embed([args.query]))]

    client = QdrantClient(url=qdrant_url)
    result = client.search(
        collection_name=collection,
        query_vector=vector,
        limit=args.limit,
        with_payload=True,
    )

    for i, r in enumerate(result, 1):
        text = (r.payload or {}).get("text")
        score = r.score
        print(f"{i}. score={score:.4f} text={text}")


if __name__ == "__main__":
    main()
