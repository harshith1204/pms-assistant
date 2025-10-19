import os
import uuid
from bson.binary import Binary
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database configuration
DATABASE_NAME = "ProjectManagement"
MONGODB_CONNECTION_STRING = "mongodb://backendInterns:mUXe57JwdugphnEn@4.213.88.219:27017/?authSource=admin"

# Qdrant configuration (prefer environment; fall back to safe placeholders)
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_URL = os.getenv("QDRANT_URL", "https://dc88ad91-1e1e-48b4-bf73-0e5c1db1cffd.europe-west3-0.gcp.cloud.qdrant.io")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "pms_collection")
MEMORY_QDRANT_COLLECTION_NAME = os.getenv("MEMORY_QDRANT_COLLECTION_NAME", "conversation_memory")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "google/embeddinggemma-300m")
 
# Retrieval packing configuration
# Max tokens to allocate for retrieved context before sending to the LLM
# You can override via env: RAG_CONTEXT_TOKEN_BUDGET
RAG_CONTEXT_TOKEN_BUDGET: int = int(os.getenv("RAG_CONTEXT_TOKEN_BUDGET", "2200"))
class _LazyMongoDBTools:
    """Lazy wrapper to avoid circular imports"""
    def __init__(self):
        self._client = None

    def __getattr__(self, name):
        if self._client is None:
            from mongo.client import direct_mongo_client
            self._client = direct_mongo_client
        return getattr(self._client, name)

# Alias for backward compatibility with existing code
mongodb_tools = _LazyMongoDBTools()

# --- Global business scoping ---
# Business UUID to scope all queries/searches. Set via env BUSINESS_UUID.
# Example: BUSINESS_UUID=3f2504e0-4f89-11d3-9a0c-0305e82c3301
BUSINESS_UUID: str | None = os.getenv("BUSINESS_UUID")

# Whether to enforce business scoping globally (default: True when BUSINESS_UUID is set)
ENFORCE_BUSINESS_FILTER: bool = os.getenv("ENFORCE_BUSINESS_FILTER", "").lower() in ("1", "true", "yes") or bool(BUSINESS_UUID)

# Collections that carry a direct business reference at path 'business._id'
COLLECTIONS_WITH_DIRECT_BUSINESS = {"project", "workItem", "cycle", "module", "page"}

def uuid_str_to_mongo_binary(uuid_str: str) -> Binary:
    """Convert canonical UUID string to Mongo Binary subtype 3 (legacy UUID).

    Many documents store UUIDs as Binary subtype 3. This returns a Binary value
    suitable for equality matching in queries (e.g., {'business._id': value}).
    """
    if not isinstance(uuid_str, str) or not uuid_str:
        raise ValueError("uuid_str must be a non-empty string")
    u = uuid.UUID(uuid_str)
    # Subtype 3 = OLD_UUID_SUBTYPE in BSON; PyMongo accepts literal 3
    return Binary(u.bytes, subtype=3)

