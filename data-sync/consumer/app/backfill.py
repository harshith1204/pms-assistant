"""Offline backfill utility for Qdrant.

This script reuses the same document preparation and chunking logic as
the streaming Kafka consumer so we can migrate (or re-migrate) the legacy
data set in bulk. It intentionally mirrors behaviour from
`legacy-code/insertdocs.py`, but relies on the new shared helpers to keep
parity with the real-time pipeline.

Usage examples:

    # Index every supported collection (default behaviour)
    python -m consumer.app.backfill

    # Index only pages and work items with smaller Mongo fetch batches
    python -m consumer.app.backfill --collections page workitem --mongo-batch 100

    # Dry-run to inspect preparation stats without hitting Qdrant
    python -m consumer.app.backfill --dry-run --limit 50

    # Verify existing payloads without indexing
    python -m consumer.app.backfill --verify-only --verify-samples 3
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Tuple

from dotenv import load_dotenv
from huggingface_hub import login
from pymongo import MongoClient
from pymongo.collection import Collection
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sentence_transformers import SentenceTransformer

if not any("qdrant" in p for p in sys.path):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if project_root not in sys.path:
        sys.path.append(project_root)

from qdrant.encoder import get_splade_encoder  # noqa: E402
from qdrant.indexing_shared import (  # noqa: E402
    PROJECT_COLLECTIONS,
    canonicalize_collection_name,
    chunk_prepared_document,
    ensure_collection_with_hybrid,
    generate_points,
    prepare_document,
)


MONGO_COLLECTION_BY_CANONICAL: Dict[str, str] = {
    "page": "page",
    "workitem": "workitem",
    "project": "project",
    "cycle": "cycle",
    "module": "module",
    "epic": "epic",
    "feature": "features",
    "userstory": "userStory",
}


COLLECTION_PROJECTIONS: Dict[str, Dict[str, int]] = {
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
    "workitem": {
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
        "createdAt": 1,
        "updatedAt": 1,
    },
    "cycle": {
        "_id": 1,
        "name": 1,
        "title": 1,
        "description": 1,
        "business": 1,
        "createdAt": 1,
        "updatedAt": 1,
    },
    "module": {
        "_id": 1,
        "name": 1,
        "title": 1,
        "description": 1,
        "business": 1,
        "createdAt": 1,
        "updatedAt": 1,
    },
    "epic": {
        "_id": 1,
        "title": 1,
        "description": 1,
        "bugNo": 1,
        "priority": 1,
        "state": 1,
        "stateMaster": 1,
        "assignee": 1,
        "project": 1,
        "business": 1,
        "createdAt": 1,
        "updatedAt": 1,
        "createdTimeStamp": 1,
        "updatedTimeStamp": 1,
        "createdBy": 1,
    },
    "feature": {
        "_id": 1,
        "displayBugNo": 1,
        "priority": 1,
        "basicInfo": 1,
        "problemInfo": 1,
        "requirements": 1,
        "riskAndDependencies": 1,
        "scope": 1,
        "goals": 1,
        "painPoints": 1,
        "description": 1,
        "workItems": 1,
        "userStories": 1,
        "addLink": 1,
        "label": 1,
        "project": 1,
        "business": 1,
        "state": 1,
        "stateMaster": 1,
        "cycle": 1,
        "modules": 1,
        "assignee": 1,
        "createdBy": 1,
        "createdAt": 1,
        "updatedAt": 1,
        "startDate": 1,
        "endDate": 1,
        "releaseDate": 1,
    },
    "userstory": {
        "_id": 1,
        "displayBugNo": 1,
        "title": 1,
        "demographics": 1,
        "description": 1,
        "summary": 1,
        "acceptanceCriteria": 1,
        "notes": 1,
        "project": 1,
        "business": 1,
        "state": 1,
        "stateMaster": 1,
        "label": 1,
        "createdBy": 1,
        "assignee": 1,
        "priority": 1,
        "createdAt": 1,
        "updatedAt": 1,
    },
}


@dataclass
class CollectionStats:
    name: str
    indexed_docs: int = 0
    planned_points: int = 0
    indexed_points: int = 0
    skipped_docs: int = 0
    errors: int = 0
    elapsed_seconds: float = 0.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill MongoDB documents into Qdrant using the new pipeline")
    parser.add_argument(
        "--collections",
        nargs="*",
        help="Subset of collections to index (accepts any alias e.g. workItem, userStories)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional limit per collection (0 = no limit)",
    )
    parser.add_argument(
        "--mongo-batch",
        type=int,
        default=200,
        help="MongoDB batch size for cursor iteration",
    )
    parser.add_argument(
        "--qdrant-batch",
        type=int,
        default=64,
        help="Number of Qdrant points to buffer before upserting",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare documents but skip Qdrant writes (no embeddings required)",
    )
    parser.add_argument(
        "--skip-delete",
        action="store_true",
        help="Do not delete existing Qdrant points before reindexing",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="After indexing, fetch sample payloads from Qdrant for spot checks",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only fetch existing Qdrant payload samples; skip indexing entirely",
    )
    parser.add_argument(
        "--verify-samples",
        type=int,
        default=5,
        help="Number of payloads to sample per collection when verify is enabled",
    )
    return parser.parse_args()


def load_env_and_login() -> None:
    load_dotenv()
    token = os.getenv("HuggingFace_API_KEY")
    if token:
        try:
            login(token)
        except Exception as exc:  # noqa: BLE001 - best effort
            print(f"??  Failed to authenticate with Hugging Face: {exc}")


def connect_mongo() -> Tuple[MongoClient, str]:
    uri = os.getenv("MONGODB_URI") or os.getenv("MONGODB_CONNECTION_STRING")
    if not uri:
        raise RuntimeError("MONGODB_URI (or MONGODB_CONNECTION_STRING) must be set")
    db_name = os.getenv("MONGODB_DB", "ProjectManagement")
    client = MongoClient(uri)
    return client, db_name


def connect_qdrant() -> QdrantClient:
    url = os.getenv("QDRANT_URL", "http://localhost:6333")
    api_key = os.getenv("QDRANT_API_KEY")
    return QdrantClient(url=url, api_key=api_key)


def iterate_documents(
    collection: Collection,
    *,
    batch_size: int,
    limit: int,
) -> Iterator[Dict[str, object]]:
    processed = 0
    cursor = collection.find({}, projection=COLLECTION_PROJECTIONS.get(collection.name, {}), batch_size=batch_size)
    for document in cursor:
        yield document
        processed += 1
        if limit and processed >= limit:
            break


def delete_points_for_parent(client: QdrantClient, collection_name: str, parent_id: str) -> None:
    if not parent_id:
        return
    try:
        client.delete(
            collection_name=collection_name,
            points_selector=qmodels.FilterSelector(
                filter=qmodels.Filter(
                    must=[
                        qmodels.FieldCondition(
                            key="parent_id",
                            match=qmodels.MatchValue(value=parent_id),
                        )
                    ]
                )
            ),
            wait=True,
        )
    except Exception as exc:  # noqa: BLE001 - we want to continue indexing
        print(f"??  Failed to delete existing points for {parent_id}: {exc}")


def index_collection(
    *,
    canonical_collection: str,
    mongo_collection: Collection,
    qdrant_client: Optional[QdrantClient],
    qdrant_collection_name: str,
    embedder: Optional[SentenceTransformer],
    splade_encoder,
    limit: int,
    mongo_batch: int,
    qdrant_batch: int,
    dry_run: bool,
    skip_delete: bool,
) -> CollectionStats:
    stats = CollectionStats(name=canonical_collection)
    t0 = time.perf_counter()

    if not dry_run and embedder is None:
        raise RuntimeError("Embedder must be initialised when dry_run is False")

    point_buffer: List[qmodels.PointStruct] = []

    for doc in iterate_documents(mongo_collection, batch_size=mongo_batch, limit=limit):
        prepared, messages = prepare_document(canonical_collection, doc)
        for message in messages:
            print(message)

        if not prepared:
            stats.skipped_docs += 1
            continue

        chunks = chunk_prepared_document(prepared)
        if not chunks:
            stats.skipped_docs += 1
            continue

        stats.indexed_docs += 1
        stats.planned_points += len(chunks)

        if dry_run:
            continue

        try:
            if not skip_delete and qdrant_client is not None:
                delete_points_for_parent(qdrant_client, qdrant_collection_name, prepared.mongo_id)

            points = generate_points(prepared, chunks, embedder, splade_encoder)
        except Exception as exc:  # noqa: BLE001 - log but keep going
            stats.errors += 1
            print(f"?  Failed to generate points for document {prepared.mongo_id}: {exc}")
            continue

        point_buffer.extend(points)

        if len(point_buffer) >= qdrant_batch and qdrant_client is not None:
            flush_points(qdrant_client, qdrant_collection_name, point_buffer, stats)

    if not dry_run and point_buffer and qdrant_client is not None:
        flush_points(qdrant_client, qdrant_collection_name, point_buffer, stats)

    stats.elapsed_seconds = time.perf_counter() - t0
    return stats


def flush_points(
    client: QdrantClient,
    collection_name: str,
    buffer: List[qmodels.PointStruct],
    stats: CollectionStats,
) -> None:
    try:
        client.upsert(collection_name=collection_name, points=list(buffer), wait=True)
        stats.indexed_points += len(buffer)
    except Exception as exc:  # noqa: BLE001
        stats.errors += len(buffer)
        print(f"?  Failed to upsert {len(buffer)} points: {exc}")
    finally:
        buffer.clear()


def sample_payloads(
    client: QdrantClient,
    collection_name: str,
    canonical_collection: str,
    *,
    samples: int,
) -> None:
    if samples <= 0:
        return

    content_type = PROJECT_COLLECTIONS.get(canonical_collection)
    if not content_type:
        print(f"??  Skipping verification for unsupported collection '{canonical_collection}'")
        return

    try:
        scroll_result = client.scroll(
            collection_name=collection_name,
            scroll_filter=qmodels.Filter(
                must=[
                    qmodels.FieldCondition(
                        key="content_type",
                        match=qmodels.MatchValue(value=content_type),
                    )
                ]
            ),
            limit=samples,
            with_payload=True,
            with_vectors=False,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"??  Failed to fetch verification samples for '{canonical_collection}': {exc}")
        return

    points, _ = scroll_result
    if not points:
        print(f"??  No points found in Qdrant for '{canonical_collection}'")
        return

    print(f"??  Verification samples for '{canonical_collection}' ({len(points)} result(s)):")
    for point in points:
        payload = point.payload or {}
        print(
            f"  ? id={payload.get('mongo_id')} title={payload.get('title')} "
            f"chunk={payload.get('chunk_index')} of {payload.get('chunk_count')} "
            f"type={payload.get('content_type')}"
        )


def resolve_collections(user_supplied: Optional[Iterable[str]]) -> List[str]:
    if user_supplied:
        resolved: List[str] = []
        for raw in user_supplied:
            canonical = canonicalize_collection_name(raw)
            if not canonical:
                print(f"??  Ignoring unsupported collection alias '{raw}'")
                continue
            resolved.append(canonical)
        if not resolved:
            raise RuntimeError("No supported collections resolved from user input")
        return sorted(set(resolved))
    return sorted(PROJECT_COLLECTIONS.keys())


def main() -> None:
    args = parse_args()
    load_env_and_login()

    if args.verify_only:
        args.verify = True

    canonical_collections = resolve_collections(args.collections)

    qdrant_client: Optional[QdrantClient] = None
    embedder: Optional[SentenceTransformer] = None
    splade_encoder = None

    if not args.dry_run or args.verify:
        try:
            qdrant_client = connect_qdrant()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(f"Failed to initialise Qdrant client: {exc}") from exc

    if not args.dry_run and not args.verify_only:
        try:
            embedder = SentenceTransformer(os.getenv("EMBEDDING_MODEL", "google/embeddinggemma-300m"))
        except Exception as exc:  # noqa: BLE001
            fallback_model = os.getenv("FALLBACK_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
            print(f"??  Failed to load primary embedding model: {exc}\n   Falling back to '{fallback_model}'")
            embedder = SentenceTransformer(fallback_model)
        splade_encoder = get_splade_encoder()

    if args.verify_only and not qdrant_client:
        raise RuntimeError("verify-only mode requires access to Qdrant")

    if args.verify_only:
        for canonical in canonical_collections:
            sample_payloads(
                qdrant_client,
                os.getenv("QDRANT_COLLECTION", "ProjectManagement"),
                canonical,
                samples=args.verify_samples,
            )
        return

    mongo_client: Optional[MongoClient] = None
    try:
        mongo_client, db_name = connect_mongo()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Failed to connect to MongoDB: {exc}") from exc

    qdrant_collection_name = os.getenv("QDRANT_COLLECTION", "ProjectManagement")

    if not args.dry_run and qdrant_client is not None:
        vector_dim = embedder.get_sentence_embedding_dimension() if embedder else 768
        ensure_collection_with_hybrid(qdrant_client, qdrant_collection_name, vector_size=vector_dim)

    overall_stats: List[CollectionStats] = []

    try:
        database = mongo_client[db_name]
        for canonical in canonical_collections:
            mongo_collection_name = MONGO_COLLECTION_BY_CANONICAL.get(canonical)
            if not mongo_collection_name:
                print(f"??  No MongoDB collection mapping for canonical name '{canonical}'")
                continue

            if mongo_collection_name not in database.list_collection_names():
                print(f"??  MongoDB collection '{mongo_collection_name}' not found in '{db_name}'")
                continue

            collection = database[mongo_collection_name]
            print(f"??  Indexing collection '{mongo_collection_name}' as '{canonical}'")

            stats = index_collection(
                canonical_collection=canonical,
                mongo_collection=collection,
                qdrant_client=qdrant_client,
                qdrant_collection_name=qdrant_collection_name,
                embedder=embedder,
                splade_encoder=splade_encoder,
                limit=args.limit,
                mongo_batch=args.mongo_batch,
                qdrant_batch=args.qdrant_batch,
                dry_run=args.dry_run,
                skip_delete=args.skip_delete,
            )
            overall_stats.append(stats)

            print(
                f"?  Done '{canonical}': docs={stats.indexed_docs} "
                f"planned_points={stats.planned_points} "
                f"indexed_points={stats.indexed_points} "
                f"skipped={stats.skipped_docs} errors={stats.errors} "
                f"time={stats.elapsed_seconds:.1f}s"
            )

            if args.verify and qdrant_client is not None:
                sample_payloads(
                    qdrant_client,
                    qdrant_collection_name,
                    canonical,
                    samples=args.verify_samples,
                )

    finally:
        if mongo_client is not None:
            mongo_client.close()


if __name__ == "__main__":
    main()

