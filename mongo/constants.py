import os
import uuid
from bson.binary import Binary, UuidRepresentation
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database configuration
DATABASE_NAME = "ProjectManagement"
MONGODB_CONNECTION_STRING = "mongodb://BeeOSAdmin:Proficornlabs%401118@172.214.123.233:27017/?authSource=admin"

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
# Business UUID to scope all queries/searches. Set via env or websocket context
COLLECTIONS_WITH_DIRECT_BUSINESS = {"project", "workItem", "cycle", "module", "page", "epic"}

def _get_business_uuid():
    """Get business UUID from websocket context or environment variables."""
    # Try websocket context first (dynamic)
    try:
        import websocket_handler as _ws_ctx
        ws_business = getattr(_ws_ctx, "business_id_global", None)
        if isinstance(ws_business, str) and ws_business:
            return ws_business
    except Exception:
        pass

    # Fall back to environment variables
    return ""

def _get_member_uuid():
    """Get member UUID from websocket context or environment variables."""
    # Try websocket context first (dynamic)
    try:
        import websocket_handler as _ws_ctx
        ws_member = getattr(_ws_ctx, "user_id_global", None)
        if isinstance(ws_member, str) and ws_member:
            return ws_member
    except Exception:
        pass

    # Fall back to environment variables
    return ""
# BUSINESS_UUID function that returns current value from websocket context or environment
def BUSINESS_UUID():
    """Get current business UUID from websocket context or environment variables.

    Returns:
        str: Current business UUID or empty string if not available
    """
    return _get_business_uuid()

# MEMBER_UUID function that returns current value from websocket context or environment
def MEMBER_UUID():
    """Get current member UUID from websocket context or environment variables.

    Returns:
        str: Current member UUID or empty string if not available
    """
    return _get_member_uuid()

def uuid_str_to_mongo_binary(uuid_str: str) -> Binary:
    """Convert canonical UUID string to Mongo Binary subtype 3 (legacy UUID).

    Many documents store UUIDs as Binary subtype 3. This returns a Binary value
    suitable for equality matching in queries (e.g., {'business._id': value}).
    """
    if not isinstance(uuid_str, str) or not uuid_str:
        raise ValueError("uuid_str must be a non-empty string")

    # Strip surrounding quotes if present (handles JSON-serialized UUIDs)
    cleaned_uuid = uuid_str.strip('"\'')

    try:
        u = uuid.UUID(cleaned_uuid)
        return Binary.from_uuid(u, uuid_representation=UuidRepresentation.JAVA_LEGACY)
    except ValueError as e:
        raise ValueError(f"Invalid UUID format '{uuid_str}': {e}") from e

