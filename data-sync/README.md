## MongoDB CDC → Kafka → Qdrant (Real‑Time, No Manual Producer)

This stack streams MongoDB changes to Kafka via the MongoDB Kafka Source Connector and ingests them into Qdrant through a Python consumer that embeds text with SentenceTransformers + SPLADE. No manual producer is required.

### What’s included
- **MongoDB** (replica set enabled) for CDC
- **Kafka** single-node KRaft broker
- **Kafka Connect** with MongoDB source connector auto-configured
- **Qdrant** (pinned version) vector DB
- **Consumer** Python app: consumes CDC, embeds text, upserts to Qdrant
- **Kafka UI** for inspection

### Key design choices
- **Event-driven**: Mongo writes automatically flow to Qdrant via Kafka.
- **No Qdrant sink connector**: Python consumer manages embeddings and upserts (single source of truth, consistent schema).
- **Pinned versions & warmups**: Qdrant pinned for stability; consumer pre-downloads the embedding model at build time for fast startups.

---

## Quick start

1) Build and start the stack:
```bash
docker compose up -d --build
```

2) Verify services are up:
- Kafka UI: `http://localhost:8080`
- Qdrant: `curl http://localhost:6333/collections`
- Kafka Connect: `curl http://localhost:8083/connectors`

3) Confirm connectors (MongoDB source should be present):
```bash
curl -s http://localhost:8083/connectors | jq
```

4) Insert a document into MongoDB (triggers CDC → Kafka → Consumer → Qdrant):
```bash
docker compose exec mongodb mongosh --eval '
  db.getSiblingDB("data_sync").documents.insertOne({
    text: "hello world from cdc",
    payload: { source: "manual-test", ts: Date.now() }
  })'
```

5) Search in Qdrant:
```bash
docker compose exec consumer python -m app.search --query "hello world"
```

You should see the inserted text appear in search results within a few seconds.

---

## Configuration
Most defaults are production-sane for local dev. Useful envs (see docker-compose.yml):
- **Kafka**: `KAFKA_BOOTSTRAP_SERVERS` (internal: `kafka:9092`)
- **MongoDB**: `MONGODB_URI`, `MONGODB_DATABASE`, `MONGODB_COLLECTION`
- **Consumer**:
  - `KAFKA_TOPIC` (default: `data-sync.documents`)
  - `QDRANT_URL` (default: `http://qdrant:6333`)
  - `QDRANT_COLLECTION` (default: `pms_collection`)
  - `EMBEDDING_MODEL` (default: `google/embeddinggemma-300m`)
  - Batch: `BATCH_MAX_MESSAGES`, `BATCH_MAX_SECONDS`
- **Connect**: MongoDB source installs automatically; sink to Qdrant is intentionally disabled.

---

## How it works
- MongoDB runs as a replica set and emits change streams.
- Kafka Connect (MongoDB Source Connector) publishes full documents for inserts/updates/replaces to topic `data-sync.documents`.
- The Python consumer:
  - Parses CDC payloads
  - Builds embeddings (or uses provided `vector` if present)
  - Upserts to Qdrant using a stable point id (prefers `id`, falls back to Mongo `_id`)

---

## Troubleshooting

- **Qdrant/consumer take long to start**
  - The consumer image prefetches the embedding model at build time to avoid first-run delays. Ensure the image was rebuilt after pulling changes: `docker compose build consumer`.
  - Qdrant is pinned (`v1.11.0`) and healthcheck start period is extended to accommodate cold starts.

- **Kafka Connect slow on first run**
  - It installs the MongoDB connector at first boot. This is cached afterwards; restarts will be fast.

- **Consumer crash / model download issues**
  - Check network, increase timeouts: set `HF_HUB_DOWNLOAD_TIMEOUT=600` and `HF_HUB_ETAG_TIMEOUT=600` in `consumer` env if you change models.

- **End-to-end doesn’t ingest**
  - Validate connector:
    ```bash
    curl -s http://localhost:8083/connectors/mongodb-source-connector/status | jq
    ```
  - Watch logs:
    ```bash
    docker compose logs -f kafka-connect consumer qdrant
    ```

- **Reset local state** (removes all data):
  ```bash
  docker compose down -v
  docker compose up -d --build
  ```

---

## Production hardening (directional)
- Kafka: multi-broker, proper replication/retention, DLQs for consumer failures
- MongoDB: replica set with adequate Oplog size for CDC
- Consumer: metrics, retries with backoff, idempotent upserts by key, structured logs
- Qdrant: snapshots/backups, sharding/replication (clustered deployment)
- Security: credentials via secret manager, TLS/SASL for Kafka, Mongo auth enabled
- CI/CD: pin images and connector versions, health checks, automated rollouts

---

## Common commands
```bash
# Bring the stack up
docker compose up -d --build

# Tail logs
docker compose logs -f consumer

# Recreate Mongo source connector (if needed)
curl -X DELETE http://localhost:8083/connectors/mongodb-source-connector || true
curl -X POST -H 'Content-Type: application/json' \
  --data @connectors/mongodb-source-connector.json \
  http://localhost:8083/connectors
```
