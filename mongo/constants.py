import os
import uuid
from bson.binary import Binary
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database configuration
DATABASE_NAME = "ProjectManagement"
MONGODB_CONNECTION_STRING = "mongodb://backendInterns:mUXe57JwdugphnEn@4.213.88.219:27017/?authSource=admin"

# Qdrant configuration
QDRANT_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.pWxytfubjbSDBCTZaH321Eya7qis_tP6sHMAZ3Gki6Y"
QDRANT_URL = "https://dc88ad91-1e1e-48b4-bf73-0e5c1db1cffd.europe-west3-0.gcp.cloud.qdrant.io"  # Default Qdrant URL
QDRANT_COLLECTION_NAME = "pms_collection"  # Collection for page and work item content
EMBEDDING_MODEL = "google/embeddinggemma-300m"  # Sentence transformer model for embeddings
 
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
# Business UUID to scope all queries/searches. Set via env.
# Some modules import this; define it here to avoid import errors
BUSINESS_UUID: str = os.getenv("BUSINESS_UUID", "")

COLLECTIONS_WITH_DIRECT_BUSINESS = {"project", "workItem", "cycle", "module", "page"}

def uuid_str_to_mongo_binary(uuid_str: str) -> Binary:
    """Convert canonical UUID string to Binary subtype 3 using Java legacy layout.

    The data in the collections was written by a Java driver using the
    "JAVA_LEGACY" representation (Binary subtype 3) where the first three
    UUID components (time_low, time_mid, time_hi_and_version) are stored in
    little-endian byte order. To match these values correctly from Python,
    we must reverse the byte order of those fields when constructing the
    Binary value.
    """
    if not isinstance(uuid_str, str) or not uuid_str:
        raise ValueError("uuid_str must be a non-empty string")
    u = uuid.UUID(uuid_str)
    b = u.bytes  # standard big-endian layout

    # Convert to Java legacy (subtype 3) by reversing the first 3 components:
    # - time_low (4 bytes)
    # - time_mid (2 bytes)
    # - time_hi_and_version (2 bytes)
    # The remaining 8 bytes stay in their original order
    java_legacy_bytes = b[3::-1] + b[5:3:-1] + b[7:5:-1] + b[8:]

    # Subtype 3 = OLD_UUID_SUBTYPE in BSON
    return Binary(java_legacy_bytes, subtype=3)

