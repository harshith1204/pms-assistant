#!/bin/bash

# Wait for Kafka Connect to be ready
echo "Waiting for Kafka Connect to be ready..."
until curl -f http://localhost:8083/connectors > /dev/null 2>&1; do
  echo "Kafka Connect not ready, waiting..."
  sleep 5
done

echo "Installing MongoDB Source Connector..."

export CONFIG_PATH=/tmp/mongodb-source-connector.json
python - <<'PY'
import json
import os

config_path = os.environ.get("CONFIG_PATH", "/tmp/mongodb-source-connector.json")

uri = os.environ.get("MONGODB_URI", "mongodb://mongodb:27017/?replicaSet=rs0")
database = os.environ.get("MONGODB_DATABASE", "ProjectManagement")
topic = os.environ.get("KAFKA_TOPIC", "data-sync.documents")
collections = ["page", "workItem", "project", "cycle", "module", "epic", "features", "userStory"]

pipeline = [
    {
        "$match": {
            "operationType": {"$in": ["insert", "update", "replace", "delete"]},
            "ns.coll": {"$in": collections},
        }
    }
]

config = {
    "name": "mongodb-source-connector",
    "config": {
        "connector.class": "com.mongodb.kafka.connect.MongoSourceConnector",
        "connection.uri": uri,
        "database": database,
        "change.stream.full.document": "updateLookup",
        "publish.full.document.only": "false",
        "pipeline": json.dumps(pipeline),
        "topic.namespace.map": json.dumps({"*": topic}),
        "copy.existing": "true",
        "copy.existing.namespace.regex": f"{database}\\\.(" + "|".join(collections) + ")",
        "key.converter": "org.apache.kafka.connect.storage.StringConverter",
        "key.converter.schemas.enable": "false",
        "value.converter": "org.apache.kafka.connect.json.JsonConverter",
        "value.converter.schemas.enable": "false",
    },
}

with open(config_path, "w", encoding="utf-8") as f:
    json.dump(config, f)
PY

# Remove existing connector if present to apply the latest config
curl -s -X DELETE http://localhost:8083/connectors/mongodb-source-connector > /dev/null 2>&1 || true
curl -X POST -H "Content-Type: application/json" \
  --data @${CONFIG_PATH} \
  http://localhost:8083/connectors

echo "Connectors installation completed (Qdrant sink disabled; Python consumer handles upserts)."
