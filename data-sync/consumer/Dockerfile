FROM python:3.11-slim

# Pin model at build-time to avoid first-run download delays
ARG EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
ENV EMBEDDING_MODEL=${EMBEDDING_MODEL}
ENV HF_HUB_DISABLE_TELEMETRY=1

# Minimal runtime deps for onnxruntime (used by fastembed)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 libstdc++6 ca-certificates curl netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --default-timeout=300 --retries=5 -r requirements.txt

# Warm up embedding model so the container starts fast at runtime
RUN python - <<'PY'
import os
from fastembed import TextEmbedding
model_name = os.environ.get('EMBEDDING_MODEL', 'BAAI/bge-small-en-v1.5')
emb = TextEmbedding(model_name=model_name)
# Trigger download and verify a single embed call
list(emb.embed(["warmup"]))
print("Model prefetch complete for:", model_name)
PY

COPY app ./app
COPY wait-for-qdrant.sh /usr/local/bin/wait-for-qdrant.sh
RUN chmod +x /usr/local/bin/wait-for-qdrant.sh
ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["/usr/local/bin/wait-for-qdrant.sh"]
CMD ["python", "-m", "app.main"]
