import json
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from huggingface_hub import login
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from sentence_transformers import SentenceTransformer


# Ensure repo-root packages (qdrant, etc.) are importable when running locally
REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.append(str(REPO_ROOT))

from qdrant.encoder import get_splade_encoder  # noqa: E402
from qdrant.indexing_shared import (  # noqa: E402
    CHUNKING_CONFIG,
    chunk_prepared_document,
    ensure_collection_with_hybrid,
    generate_points,
    normalize_mongo_id,
    prepare_document,
)


RELEVANT_COLLECTIONS = {
    "page",
    "workItem",
    "project",
    "cycle",
    "module",
    "epic",
}


@dataclass
class ChangeEvent:
    operation: str
    collection: Optional[str]
    full_document: Optional[Dict[str, Any]]
    document_key: Optional[Dict[str, Any]]


def load_env_and_login() -> None:
    load_dotenv()
    token = os.getenv("HuggingFace_API_KEY")
    if not token:
        logger.warning("No HuggingFace token provided; proceeding without login")
        return
    try:
        login(token)
        logger.info("Authenticated with HuggingFace Hub")
    except Exception as exc:
        logger.warning("HuggingFace login failed: {}", exc)


def load_embedder() -> SentenceTransformer:
    primary_model = os.getenv("EMBEDDING_MODEL", "google/embeddinggemma-300m")
    fallback_model = os.getenv(
        "FALLBACK_EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )
    try:
        logger.info("Loading embedding model '{}'", primary_model)
        return SentenceTransformer(primary_model)
    except Exception as exc:
        logger.warning("Failed to load '{}': {}", primary_model, exc)
        logger.info("Falling back to '{}'", fallback_model)
        return SentenceTransformer(fallback_model)


def get_env(name: str, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def flatten_payload(raw: bytes) -> Optional[Any]:
    try:
        decoded = raw.decode("utf-8")
    except Exception as exc:
        logger.warning("Failed to decode Kafka record as UTF-8: {}", exc)
        return None

    try:
        envelope = json.loads(decoded)
    except Exception as exc:
        logger.warning("Invalid JSON payload: {}", exc)
        return None

    if isinstance(envelope, dict) and "payload" in envelope:
        payload = envelope.get("payload")
        if isinstance(payload, str):
            try:
                return json.loads(payload)
            except Exception as exc:
                logger.warning("Failed to parse nested payload JSON: {}", exc)
                return None
        return payload
    return envelope


def parse_change_events(raw: bytes) -> List[ChangeEvent]:
    payload = flatten_payload(raw)
    if payload is None:
        return []

    if isinstance(payload, list):
        events: List[ChangeEvent] = []
        for item in payload:
            if isinstance(item, (dict, list)):
                events.extend(parse_change_events(json.dumps(item).encode("utf-8")))
        return events

    if not isinstance(payload, dict):
        logger.debug("Skipping payload of type {}", type(payload))
        return []

    op = payload.get("operationType") or payload.get("op") or "insert"
    op = str(op).lower()
    if op == "read":
        op = "insert"

    namespace = payload.get("ns") or {}
    collection = namespace.get("coll") or payload.get("collection") or payload.get("collectionName")

    full_document = payload.get("fullDocument")
    if isinstance(full_document, list) and full_document:
        # Some CDC pipelines may wrap documents in a list
        events: List[ChangeEvent] = []
        for doc in full_document:
            if isinstance(doc, dict):
                events.append(
                    ChangeEvent(
                        operation=op,
                        collection=collection,
                        full_document=doc,
                        document_key=payload.get("documentKey"),
                    )
                )
        return events

    if op not in {"insert", "update", "replace", "delete"}:
        logger.debug("Skipping unsupported operation '{}': {}", op, payload)
        return []

    document_key = payload.get("documentKey")
    if not isinstance(document_key, dict):
        document_key = {"_id": payload.get("_id")}

    document = None
    if isinstance(full_document, dict):
        document = full_document
    elif op in {"insert", "replace"}:
        # Some connectors emit the full document at top level when publish.full.document.only=true
        document = payload if payload.get("_id") else None

    return [ChangeEvent(operation=op, collection=collection, full_document=document, document_key=document_key)]


def delete_points_for_parent(client: QdrantClient, collection: str, parent_id: str) -> None:
    if not parent_id:
        return
    try:
        client.delete(
            collection_name=collection,
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
        logger.debug("Deleted existing points for parent_id={}", parent_id)
    except Exception as exc:
        logger.warning("Failed to delete points for parent_id {}: {}", parent_id, exc)


def process_event(
    event: ChangeEvent,
    client: QdrantClient,
    collection_name: str,
    embedder: SentenceTransformer,
    splade_encoder: Any,
) -> None:
    if event.collection not in RELEVANT_COLLECTIONS:
        logger.debug("Ignoring collection '{}'", event.collection)
        return

    if event.operation == "delete":
        raw_id = (event.document_key or {}).get("_id")
        if raw_id is None:
            logger.warning(
                "Delete event missing _id; collection={} payload={}",
                event.collection,
                event.document_key,
            )
            return
        mongo_id = normalize_mongo_id(raw_id)
        if not mongo_id:
            logger.warning("Delete event produced empty mongo_id for collection {}", event.collection)
            return
        delete_points_for_parent(client, collection_name, mongo_id)
        logger.info(
            "Applied delete for mongo_id={} collection={}",
            mongo_id,
            event.collection,
        )
        return

    if not event.full_document:
        logger.warning(
            "Missing fullDocument for operation '{}' on collection '{}'; skipping",
            event.operation,
            event.collection,
        )
        return

    prepared, messages = prepare_document(event.collection, event.full_document)
    for message in messages:
        logger.info(message)
    if not prepared:
        return

    chunks = chunk_prepared_document(prepared)
    mongo_id = prepared.mongo_id
    if not mongo_id:
        logger.warning("Prepared document missing mongo_id for collection {}", event.collection)
        return

    delete_points_for_parent(client, collection_name, mongo_id)

    if not chunks:
        logger.info(
            "Document {} in collection {} has no indexable content; existing points removed",
            mongo_id,
            event.collection,
        )
        return

    points = generate_points(prepared, chunks, embedder, splade_encoder)
    if not points:
        logger.info(
            "Document {} in collection {} produced no points after chunk generation",
            mongo_id,
            event.collection,
        )
        return

    client.upsert(collection_name=collection_name, points=points, wait=True)
    logger.info(
        "Upserted {} points for mongo_id={} collection={} (operation={})",
        len(points),
        mongo_id,
        event.collection,
        event.operation,
    )


def main() -> None:
    load_env_and_login()

    embedder = load_embedder()
    splade_encoder = get_splade_encoder()
    embedding_dim = embedder.get_sentence_embedding_dimension()
    logger.debug("Loaded chunking config for: {}", ", ".join(sorted(CHUNKING_CONFIG.keys())))

    log_level = get_env("LOG_LEVEL", "INFO")
    logger.remove()
    logger.add(lambda msg: print(msg, end=""), level=log_level)

    bootstrap = get_env("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic = get_env("KAFKA_TOPIC", "data-sync.documents")
    group_id = get_env("KAFKA_GROUP_ID", "qdrant-consumer")
    qdrant_url = get_env("QDRANT_URL", "http://qdrant:6333")
    collection = get_env("QDRANT_COLLECTION", "pms_collection")
    batch_max_messages = int(get_env("BATCH_MAX_MESSAGES", "128"))
    batch_max_seconds = float(get_env("BATCH_MAX_SECONDS", "2"))

    logger.info("Using embedding dimension {}", embedding_dim)

    client = None
    while client is None:
        try:
            client = QdrantClient(url=qdrant_url)
        except Exception as exc:
            logger.warning("Waiting for Qdrant availability: {}", exc)
            time.sleep(2)

    ensure_collection_with_hybrid(client, collection, vector_size=embedding_dim)

    consumer: Optional[KafkaConsumer] = None
    while consumer is None:
        try:
            consumer = KafkaConsumer(
                topic,
                bootstrap_servers=[s.strip() for s in bootstrap.split(",") if s.strip()],
                group_id=group_id,
                enable_auto_commit=False,
                auto_offset_reset="earliest",
                value_deserializer=lambda m: m,
                key_deserializer=lambda m: m,
            )
        except Exception as exc:
            logger.warning("Waiting for Kafka consumer: {}", exc)
            time.sleep(2)

    logger.info("Started consumer on topic '{}'", topic)

    batch_events: List[ChangeEvent] = []
    last_flush_ts = time.monotonic()

    while True:
        try:
            now = time.monotonic()
            remaining_capacity = max(0, batch_max_messages - len(batch_events))
            poll_timeout_ms = 500
            max_records = remaining_capacity if remaining_capacity > 0 else None

            records_map = consumer.poll(timeout_ms=poll_timeout_ms, max_records=max_records)
            total_polled = sum(len(records) for records in (records_map or {}).values())

            for records in (records_map or {}).values():
                for msg in records:
                    events = parse_change_events(msg.value)
                    if events:
                        logger.debug("Parsed {} change events from message", len(events))
                        batch_events.extend(events)

            should_flush = False
            if len(batch_events) >= batch_max_messages:
                should_flush = True
            elif (now - last_flush_ts) >= batch_max_seconds and batch_events:
                should_flush = True

            if should_flush:
                try:
                    for event in batch_events:
                        process_event(event, client, collection, embedder, splade_encoder)
                    consumer.commit()
                    batch_events.clear()
                    last_flush_ts = time.monotonic()
                except Exception as exc:
                    logger.exception("Batch processing failed: {}", exc)
                    time.sleep(0.5)

            if total_polled == 0 and not should_flush:
                time.sleep(0.1)

        except Exception as exc:
            logger.exception("Consumer loop error: {}", exc)
            logger.warning("Recreating consumer in 5 seconds")
            time.sleep(5)
            try:
                consumer.close()
            except Exception:
                pass
            consumer = None
            while consumer is None:
                try:
                    consumer = KafkaConsumer(
                        topic,
                        bootstrap_servers=[s.strip() for s in bootstrap.split(",") if s.strip()],
                        group_id=group_id,
                        enable_auto_commit=False,
                        auto_offset_reset="earliest",
                        value_deserializer=lambda m: m,
                        key_deserializer=lambda m: m,
                    )
                except NoBrokersAvailable as broker_exc:
                    logger.warning("Waiting for Kafka broker during recovery: {}", broker_exc)
                    time.sleep(2)


if __name__ == "__main__":
    main()
