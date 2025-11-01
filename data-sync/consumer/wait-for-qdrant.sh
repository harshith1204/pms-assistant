#!/usr/bin/env sh
set -e

# Use QDRANT_URL if provided, otherwise use the docker service name 'qdrant'
QDRANT_URL="${QDRANT_URL:-http://qdrant:6333}"

# Remove trailing slash for safety
QDRANT_URL=$(echo "$QDRANT_URL" | sed 's:/*$::')

echo "Waiting for Qdrant at ${QDRANT_URL} ..."

attempt=0
max_attempts=12
sleep_secs=2

while [ $attempt -lt $max_attempts ]; do
  attempt=$((attempt+1))
  if command -v curl >/dev/null 2>&1; then
    if curl -fsS "${QDRANT_URL}/collections" >/dev/null 2>&1; then
      echo "Qdrant ready at ${QDRANT_URL}"
      exec "$@"
    fi
  else
    # fallback to nc if curl not present
    host=$(echo "$QDRANT_URL" | sed -n 's|^[a-z]*://\([^:/]*\).*|\1|p')
    port=$(echo "$QDRANT_URL" | sed -n 's|^[a-z]*://[^:/]*:\?\([0-9]*\).*|\1|p')
    if [ -z "$port" ]; then port=6333; fi
    if nc -z "$host" "$port" >/dev/null 2>&1; then
      echo "Qdrant ready (tcp) at ${host}:${port}"
      exec "$@"
    fi
  fi

  # Simple exponential backoff: cap at 32 seconds
  if [ $attempt -gt 5 ]; then
    wait_secs=32
  else
    wait_secs=$((sleep_secs * (1 << attempt)))
  fi
  echo "Attempt ${attempt}: Qdrant not ready yet, waiting ${wait_secs}s..."
  sleep "$wait_secs"
done

echo "Timed out waiting for Qdrant at ${QDRANT_URL}" >&2
exit 1
