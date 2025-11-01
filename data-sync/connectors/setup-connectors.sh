#!/bin/bash

# Wait for Kafka Connect to be ready
echo "Waiting for Kafka Connect to be ready..."
until curl -f http://localhost:8083/connectors > /dev/null 2>&1; do
  echo "Kafka Connect not ready, waiting..."
  sleep 5
done

echo "Installing MongoDB Source Connector..."
# Remove existing connector if present to apply the latest config
curl -s -X DELETE http://localhost:8083/connectors/mongodb-source-connector > /dev/null 2>&1 || true
curl -X POST -H "Content-Type: application/json" \
  --data @/connectors/mongodb-source-connector.json \
  http://localhost:8083/connectors

echo "Connectors installation completed (Qdrant sink disabled; Python consumer handles upserts)."
