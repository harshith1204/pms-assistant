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
# Business UUID to scope all queries/searches. Set via env BUSINESS_UUID.
# Example: BUSINESS_UUID=3f2504e0-4f89-11d3-9a0c-0305e82c3301


# Collections that carry a direct business reference at path 'business._id'
# Collections that directly embed business reference and can be filtered via 'business._id'
# Include timeline since it carries 'business._id' on each event
COLLECTIONS_WITH_DIRECT_BUSINESS = {"project", "workItem", "cycle", "module", "page", "timeline"}

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

