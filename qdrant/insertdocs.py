import os
import sys
from collections import defaultdict
from itertools import islice
from typing import Any, Dict, Iterable, List, Optional

from dotenv import load_dotenv
from huggingface_hub import login
from sentence_transformers import SentenceTransformer

# Ensure qdrant package imports resolve
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from qdrant.dbconnection import (  # noqa: E402
    QDRANT_COLLECTION,
    cycle_collection,
    epic_collection,
    feature_collection,
    module_collection,
    page_collection,
    project_collection,
    qdrant_client,
    userstory_collection,
    workitem_collection,
)
from qdrant.encoder import get_splade_encoder  # noqa: E402
from qdrant.indexing_shared import (  # noqa: E402
    CHUNKING_CONFIG,
    chunk_prepared_document,
    ensure_collection_with_hybrid,
    generate_points,
    prepare_document,
)


# ---------------------------------------------------------------------------
# Environment & model setup
# ---------------------------------------------------------------------------


def init_huggingface_login() -> None:
    load_dotenv()
    token = os.getenv("HuggingFace_API_KEY")
    if not token:
        print("WARN: no HuggingFace token found; proceeding without login")
        return
    try:
        login(token)
        print("INFO: HuggingFace login succeeded")
    except Exception as exc:
        print(f"WARN: HuggingFace login failed: {exc}")


def load_embedder() -> SentenceTransformer:
    primary_model = os.getenv("PRIMARY_EMBEDDING_MODEL", "google/embeddinggemma-300m")
    fallback_model = os.getenv(
        "FALLBACK_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    try:
        print(f"INFO: loading embedding model '{primary_model}'")
        return SentenceTransformer(primary_model)
    except Exception as exc:
        print(f"WARN: failed to load '{primary_model}': {exc}")
        print(f"INFO: falling back to '{fallback_model}'")
        return SentenceTransformer(fallback_model)


init_huggingface_login()
embedder = load_embedder()
splade_encoder = get_splade_encoder()


# ---------------------------------------------------------------------------
# Chunking statistics (for visibility when running the script manually)
# ---------------------------------------------------------------------------


class ChunkingStats:
    def __init__(self) -> None:
        self.by_type: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_docs": 0,
                "single_chunk": 0,
                "multi_chunk": 0,
                "total_chunks": 0,
                "chunk_distribution": defaultdict(int),
                "total_words": 0,
                "max_chunks": 0,
                "max_chunks_doc": None,
            }
        )

    def record(
        self,
        content_type: str,
        doc_id: str,
        title: str,
        chunk_count: int,
        word_count: int,
    ) -> None:
        stats = self.by_type[content_type]
        stats["total_docs"] += 1
        stats["total_chunks"] += chunk_count
        stats["total_words"] += word_count
        stats["chunk_distribution"][chunk_count] += 1

        if chunk_count == 1:
            stats["single_chunk"] += 1
        else:
            stats["multi_chunk"] += 1

        if chunk_count > stats["max_chunks"]:
            stats["max_chunks"] = chunk_count
            stats["max_chunks_doc"] = (doc_id, title[:50])

    def print_summary(self) -> None:
        print("\n" + "=" * 80)
        print("CHUNKING STATISTICS SUMMARY")
        print("=" * 80)

        total_docs = 0
        total_chunks = 0

        for content_type, stats in sorted(self.by_type.items()):
            total_docs += stats["total_docs"]
            total_chunks += stats["total_chunks"]

            if stats["total_docs"] == 0:
                continue

            print(f"\n> {content_type.upper()}")
            print(f"  Documents: {stats['total_docs']}")
            print(f"  Total chunks: {stats['total_chunks']}")
            print(
                f"  Avg chunks/document: {stats['total_chunks'] / stats['total_docs']:.2f}"
            )
            print(
                f"  Avg words/document: {stats['total_words'] / stats['total_docs']:.0f}"
            )
            single_pct = stats['single_chunk'] / stats['total_docs'] * 100
            multi_pct = stats['multi_chunk'] / stats['total_docs'] * 100
            print(f"  Single chunk: {stats['single_chunk']} ({single_pct:.1f}%)")
            print(f"  Multi chunk: {stats['multi_chunk']} ({multi_pct:.1f}%)")

            if stats["max_chunks"] > 1:
                doc_id, title = stats["max_chunks_doc"]
                print(f"  Max chunks: {stats['max_chunks']} (doc '{title}...')")

            if stats["multi_chunk"] > 0:
                print("  Chunk distribution (top 5 multi-chunk counts):")
                multi_keys = [k for k in stats["chunk_distribution"] if k > 1]
                for chunk_count in sorted(multi_keys)[:5]:
                    count = stats["chunk_distribution"][chunk_count]
                    print(f"    - {chunk_count}: {count} docs")

        if total_docs > 0:
            print("\n" + "-" * 80)
            print("OVERALL TOTALS")
            print(f"  Total documents: {total_docs}")
            print(f"  Total chunks (points): {total_chunks}")
            print(f"  Average chunks/document: {total_chunks / total_docs:.2f}")
            expansion = (total_chunks / total_docs - 1) * 100
            print(f"  Chunking expansion: {expansion:.1f}%")
        print("=" * 80 + "\n")


_stats = ChunkingStats()


# ---------------------------------------------------------------------------
# Qdrant upload helpers
# ---------------------------------------------------------------------------


def batch_iterable(iterable: Iterable, batch_size: int) -> Iterable[List]:
    iterator = iter(iterable)
    while True:
        batch = list(islice(iterator, batch_size))
        if not batch:
            break
        yield batch


def upload_in_batches(points: List[Any], collection_name: str, batch_size: int = 20) -> int:
    total_indexed = 0
    for batch in batch_iterable(points, batch_size):
        print(f"INFO: uploading batch of {len(batch)} points to {collection_name}")
        try:
            qdrant_client.upsert(collection_name=collection_name, points=batch)
            total_indexed += len(batch)
        except Exception as exc:
            print(f"ERROR: failed to upload batch: {exc}")
    return total_indexed


# ---------------------------------------------------------------------------
# Collection indexing logic
# ---------------------------------------------------------------------------


COLLECTION_PROJECTIONS: Dict[str, Optional[Dict[str, int]]] = {
    "page": {
        "_id": 1,
        "content": 1,
        "title": 1,
        "visibility": 1,
        "isFavourite": 1,
        "createdAt": 1,
        "updatedAt": 1,
        "createdTimeStamp": 1,
        "updatedTimeStamp": 1,
        "project": 1,
        "business": 1,
        "createdBy": 1,
    },
    "workItem": {
        "_id": 1,
        "title": 1,
        "description": 1,
        "displayBugNo": 1,
        "priority": 1,
        "status": 1,
        "state": 1,
        "assignee": 1,
        "createdAt": 1,
        "updatedAt": 1,
        "createdTimeStamp": 1,
        "updatedTimeStamp": 1,
        "project": 1,
        "cycle": 1,
        "modules": 1,
        "business": 1,
        "createdBy": 1,
        "workLogs": 1,
    },
    "project": {
        "_id": 1,
        "name": 1,
        "description": 1,
        "business": 1,
    },
    "cycle": {
        "_id": 1,
        "name": 1,
        "title": 1,
        "description": 1,
        "business": 1,
    },
    "module": {
        "_id": 1,
        "name": 1,
        "title": 1,
        "description": 1,
        "business": 1,
    },
    "epic": {
        "_id": 1,
        "title": 1,
        "description": 1,
        "bugNo": 1,
        "priority": 1,
        "assignee": 1,
        "createdAt": 1,
        "updatedAt": 1,
        "createdTimeStamp": 1,
        "updatedTimeStamp": 1,
        "project": 1,
        "business": 1,
        "state": 1,
        "stateMaster": 1,
        "createdBy": 1,
    },
    "features": {
        "_id": 1,
        "basicInfo": 1,
        "problemInfo": 1,
        "displayBugNo": 1,
        "requirements": 1,
        "riskAndDependencies": 1,
        "project": 1,
        "business": 1,
        "state": 1,
        "stateMaster": 1,
        "createdAt": 1,
        "updatedAt": 1,
        "createdBy": 1,
        "priority": 1,
        "assignee": 1,
        "label": 1,
        "modules": 1,
        "cycle": 1,
        "startDate": 1,
        "endDate": 1,
        "releaseDate": 1,
        "scope": 1,
        "goals": 1,
        "painPoints": 1,
        "workItems": 1,
        "userStories": 1,
        "addLink": 1,
    },
    "userStory": {
        "_id": 1,
        "displayBugNo": 1,
        "title": 1,
        "description": 1,
        "demographics": 1,
        "project": 1,
        "business": 1,
        "state": 1,
        "stateMaster": 1,
        "createdAt": 1,
        "updatedAt": 1,
        "createdBy": 1,
        "priority": 1,
        "assignee": 1,
        "label": 1,
    },
}


COLLECTION_SOURCES = {
    "page": page_collection,
    "workItem": workitem_collection,
    "project": project_collection,
    "cycle": cycle_collection,
    "module": module_collection,
    "epic": epic_collection,
    "features": feature_collection,
    "userStory": userstory_collection,
}


def index_collection(collection_name: str) -> Dict[str, Any]:
    mongo_collection = COLLECTION_SOURCES[collection_name]
    projection = COLLECTION_PROJECTIONS.get(collection_name)

    print("-" * 80)
    print(f"INFO: indexing '{collection_name}' documents into Qdrant")

    ensure_collection_with_hybrid(qdrant_client, QDRANT_COLLECTION, vector_size=768)

    cursor = mongo_collection.find({}, projection or None)
    processed_docs = 0
    indexed_docs = 0
    points: List[Any] = []

    for doc in cursor:
        processed_docs += 1
        prepared, messages = prepare_document(collection_name, doc)
        for message in messages:
            print(message)
        if not prepared:
            continue

        chunks = chunk_prepared_document(prepared)
        if not chunks:
            print(
                f"WARN: document {prepared.mongo_id} produced no chunks for {collection_name}"
            )
            continue

        word_count = len(prepared.combined_text.split()) if prepared.combined_text else 0
        _stats.record(
            prepared.content_type,
            prepared.mongo_id,
            prepared.title,
            len(chunks),
            word_count,
        )

        points.extend(generate_points(prepared, chunks, embedder, splade_encoder))
        indexed_docs += 1

    if not points:
        print(f"WARN: no valid {collection_name} documents to index")
        return {
            "status": "warning",
            "processed_documents": processed_docs,
            "indexed_points": 0,
        }

    total_indexed = upload_in_batches(points, QDRANT_COLLECTION)
    print(
        f"INFO: indexed {total_indexed} points derived from {indexed_docs} {collection_name} documents"
    )

    return {
        "status": "success",
        "processed_documents": processed_docs,
        "indexed_points": total_indexed,
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------


def main() -> None:
    print("=" * 80)
    print("STARTING QDRANT INDEXING WITH CONFIGURABLE CHUNKING")
    print("=" * 80)

    print("\nActive chunking configuration:")
    for content_type, cfg in sorted(CHUNKING_CONFIG.items()):
        print(
            f"  - {content_type.upper()}: size {cfg['max_words']} words, overlap {cfg['overlap_words']}"
        )
    print("  - FEATURE & USER_STORY reuse WORK_ITEM defaults")

    results = {}
    for collection_name in COLLECTION_SOURCES:
        results[collection_name] = index_collection(collection_name)

    _stats.print_summary()

    print("INDEXING SUMMARY")
    for collection_name, result in results.items():
        print(
            f"  {collection_name}: status={result['status']}, "
            f"processed={result['processed_documents']}, indexed_points={result['indexed_points']}"
        )

    print("INFO: Qdrant indexing complete")
    print("=" * 80)


if __name__ == "__main__":
    main()
