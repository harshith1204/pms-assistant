import json
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, Union

from loguru import logger
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels
from fastembed import TextEmbedding
from dotenv import load_dotenv
load_dotenv()


def get_env(name: str, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def normalize_point_id(doc_id: Any) -> Union[int, str]:
    """
    Convert document ID to a valid Qdrant point ID.
    Qdrant accepts either integers or UUIDs (as strings).
    """
    if doc_id is None:
        return str(uuid.uuid4())
    
    # If it's already an int, return as-is
    if isinstance(doc_id, int):
        return doc_id
    
    # If it's a string that looks like an integer, convert it
    if isinstance(doc_id, str):
        # Try to parse as integer
        try:
            return int(doc_id)
        except ValueError:
            pass
        
        # Check if it's already a valid UUID
        try:
            uuid.UUID(doc_id)
            return doc_id
        except ValueError:
            pass
        
        # Not an integer or UUID, generate a UUID
        return str(uuid.uuid4())
    
    # For any other type, generate a UUID
    return str(uuid.uuid4())


def ensure_qdrant_collection(client: QdrantClient, collection: str, embedder: TextEmbedding) -> int:
    """Ensure the Qdrant collection exists with the expected vector size.

    Handles both single-vector and named-vector configurations returned by Qdrant.
    """
    # Determine vector dimension by embedding a single token
    dim = len(next(embedder.embed(["dim-probe"])))
    try:
        info = client.get_collection(collection_name=collection)

        # qdrant-client returns CollectionInfo with config.params.vectors that can be either:
        # - VectorParams (single vector)
        # - Dict[str, VectorParams] (named vectors)
        existing_dim: Optional[int] = None
        try:
            vectors_cfg = info.config.params.vectors  # type: ignore[attr-defined]
        except AttributeError:
            # Fallback for older client shapes
            vectors_cfg = getattr(info, "vectors_config", None)

        if isinstance(vectors_cfg, qmodels.VectorParams):
            existing_dim = vectors_cfg.size
        elif isinstance(vectors_cfg, dict):
            for _, vp in vectors_cfg.items():
                if isinstance(vp, qmodels.VectorParams):
                    existing_dim = vp.size
                    break

        if existing_dim is None:
            logger.warning(
                "Could not determine existing vector size for collection '{}' — proceeding without check",
                collection,
            )
        elif existing_dim != dim:
            logger.warning(
                "Collection exists with dim={}, but embedder dim={} — consider recreating",
                existing_dim,
                dim,
            )
        else:
            logger.info("Qdrant collection '{}' exists with dim {}", collection, existing_dim)
    except Exception:
        logger.info("Creating Qdrant collection '{}' with dim {}", collection, dim)
        client.create_collection(
            collection_name=collection,
            vectors_config=qmodels.VectorParams(size=dim, distance=qmodels.Distance.COSINE),
        )
    return dim


def parse_message_value(raw: bytes) -> List[Dict[str, Any]]:
    text: Optional[str] = None
    try:
        decoded = raw.decode("utf-8")
    except Exception:
        # Fallback: keep as-is
        decoded = ''
    try:
        data = json.loads(decoded)
    except Exception:
        text = decoded
        data = None

    docs: List[Dict[str, Any]] = []

    # Handle Kafka Connect message format: { "schema": {...}, "payload": "json_string" }
    if isinstance(data, dict) and "payload" in data:
        payload_data = data.get("payload")
        if isinstance(payload_data, str):
            try:
                data = json.loads(payload_data)
                logger.info(f"Parsed Kafka payload: has _id={data.get('_id') is not None}, has text={data.get('text') is not None}, has vector={data.get('vector') is not None}")
            except Exception:
                data = payload_data

    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                docs.append(item)
            elif isinstance(item, str):
                docs.append({"text": item})
    elif isinstance(data, dict):
        # Handle MongoDB CDC messages
        if "fullDocument" in data and "operationType" in data:
            # This is a MongoDB CDC message
            operation_type = data.get("operationType")
            if operation_type in ["insert", "update", "replace"]:
                full_doc = data["fullDocument"]
                if isinstance(full_doc, dict):
                    docs.append(full_doc)
            # Skip delete operations or operations without fullDocument
        # Support Qdrant points batch envelope: { "points": [ ... ] }
        elif "points" in data and isinstance(data["points"], list):
            for p in data["points"]:
                if isinstance(p, dict):
                    docs.append(p)
        elif "_id" in data:
            # This is a MongoDB document (CDC with publish.full.document.only=true)
            docs.append(data)
        else:
            # Regular document (backward compatibility)
            docs.append(data)
    else:
        if text:
            docs.append({"text": text})
    return docs


def build_points(
    docs: List[Dict[str, Any]],
    embedder: TextEmbedding,
) -> Tuple[List[qmodels.PointStruct], int]:
    texts_to_embed: List[str] = []
    text_indices: List[int] = []
    payloads: List[Dict[str, Any]] = []
    ids: List[Union[int, str]] = []
    vectors: List[Optional[List[float]]] = []

    for d in docs:
        # Normalize the ID to be valid for Qdrant
        raw_id: Any = d.get("id")
        if raw_id is None:
            # Fall back to Mongo's _id which may be a nested Extended JSON object
            mongo_id = d.get("_id")
            if isinstance(mongo_id, dict):
                # Handle common shapes like {"$oid": "..."} or {"oid": "..."}
                raw_id = mongo_id.get("$oid") or mongo_id.get("oid") or json.dumps(mongo_id, sort_keys=True)
            else:
                raw_id = mongo_id
        doc_id = normalize_point_id(raw_id)
        
        vector = d.get("vector")
        # Accept both 'metadata' and 'payload' like Qdrant docs
        metadata = d.get("metadata") or d.get("payload") or {}
        if not isinstance(metadata, dict):
            metadata = {"metadata": metadata}
        # Prefer top-level text, else try common payload keys
        text = d.get("text")
        if text is None and isinstance(metadata, dict):
            text = metadata.get("text") or metadata.get("content")

        if vector is not None:
            # Accept provided vector and optional text
            if text is None:
                text = ""
            if isinstance(vector, list):
                ids.append(doc_id)
                payloads.append({"text": text, **metadata})
                vectors.append([float(x) for x in vector])
            else:
                logger.warning("Skipping doc due to invalid vector type for id={}.", doc_id)
        else:
            if not text:
                logger.warning("Skipping doc without 'text' or 'vector', id={}", doc_id)
                continue
            ids.append(doc_id)
            payloads.append({"text": text, **metadata})
            vectors.append(None)
            text_indices.append(len(vectors) - 1)
            texts_to_embed.append(text)

    # Embed texts and place vectors back into the original positions
    if texts_to_embed:
        for idx, emb in zip(text_indices, embedder.embed(texts_to_embed)):
            vectors[idx] = [float(x) for x in emb]

    # Build points preserving original order and skipping any unresolved vectors
    points: List[qmodels.PointStruct] = []
    embedded_count = 0
    for i in range(len(ids)):
        vec = vectors[i]
        if vec is None:
            # Should not happen, but be defensive
            logger.warning("Vector missing for id={}, skipping", ids[i])
            continue
        if i in text_indices:
            embedded_count += 1
        points.append(qmodels.PointStruct(id=ids[i], vector=vec, payload=payloads[i]))

    return points, embedded_count


def main() -> None:
    log_level = get_env("LOG_LEVEL", "INFO")
    logger.remove()
    logger.add(lambda msg: print(msg, end=""), level=log_level)

    bootstrap = get_env("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic = get_env("KAFKA_TOPIC", "documents")
    group_id = get_env("KAFKA_GROUP_ID", "qdrant-consumer")
    qdrant_url = get_env("QDRANT_URL", "http://qdrant:6333")
    collection = get_env("QDRANT_COLLECTION", "documents")
    embedding_model = get_env("EMBEDDING_MODEL", "BAAI/bge-small-en-v1.5")
    batch_max_messages = int(get_env("BATCH_MAX_MESSAGES", "256"))
    batch_max_seconds = float(get_env("BATCH_MAX_SECONDS", "2"))

    # Initialize dependencies with retries
    embedder = None
    max_retries = 30  # Allow up to 30 retries (about 5 minutes with 10s sleep)
    retry_count = 0
    while embedder is None and retry_count < max_retries:
        try:
            embedder = TextEmbedding(model_name=embedding_model)
        except Exception as e:
            retry_count += 1
            if retry_count >= max_retries:
                raise
            # Exponential backoff with jitter
            sleep_time = min(10, 2 ** min(retry_count // 5, 3)) + (retry_count % 3)
            time.sleep(sleep_time)

    client = None
    while client is None:
        try:
            client = QdrantClient(url=qdrant_url)
        except Exception as e:
            logger.warning("Waiting for Qdrant: {}", e)
            time.sleep(2)

    ensure_qdrant_collection(client, collection, embedder)

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
            print("DEBUG: Kafka consumer created successfully")
        except Exception as e:
            print(f"DEBUG: Waiting for Kafka consumer creation: {e}")
            time.sleep(2)

    logger.info("Started consumer on topic '{}'", topic)

    # Poll in batches and upsert
    batch_docs: List[Dict[str, Any]] = []
    last_flush_ts = time.monotonic()

    while True:
        try:
            now = time.monotonic()
            remaining_capacity = max(0, batch_max_messages - len(batch_docs))
            poll_timeout_ms = 500
            max_records = remaining_capacity if remaining_capacity > 0 else None

            records_map = consumer.poll(timeout_ms=poll_timeout_ms, max_records=max_records)
            logger.info(f"Polled {len(records_map) if records_map else 0} partitions with messages")
            total_polled = 0
            for tp, records in (records_map or {}).items():
                total_polled += len(records)
                for msg in records:
                    docs = parse_message_value(msg.value)
                    logger.info("Parsed {} docs from message", len(docs) if docs else 0)
                    if docs:
                        for doc in docs:
                            logger.info("Parsed doc ID: {}, has text: {}, has vector: {}",
                                       doc.get('id', 'unknown'), 'text' in doc, 'vector' in doc)
                        batch_docs.extend(docs)

            should_flush = False
            if len(batch_docs) >= batch_max_messages:
                should_flush = True
            elif (now - last_flush_ts) >= batch_max_seconds and batch_docs:
                should_flush = True

            if should_flush:
                try:
                    points, embedded_count = build_points(batch_docs, embedder)
                    logger.info("Built {} points from {} docs ({} embedded)", len(points), len(batch_docs), embedded_count)
                    if points:
                        client.upsert(collection_name=collection, points=points, wait=True)
                        logger.info("Upserted {} points to collection '{}'", len(points), collection)
                    else:
                        logger.info("No points to upsert this batch; committing offsets")
                    consumer.commit()
                    batch_docs.clear()
                    last_flush_ts = time.monotonic()
                except Exception as e:
                    logger.exception("Batch processing failed: {}", e)
                    # Do not commit; retry on next loop
                    time.sleep(0.5)

            # If no records and no flush, small sleep to avoid tight loop
            if total_polled == 0 and not should_flush:
                time.sleep(0.1)
        except Exception as e:
            logger.exception("Consumer loop error: {}", e)
            logger.warning("Recreating consumer in 5 seconds...")
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
                except NoBrokersAvailable as e:
                    logger.warning("Waiting for Kafka broker during recovery: {}", e)
                    time.sleep(2)


if __name__ == "__main__":
    main()