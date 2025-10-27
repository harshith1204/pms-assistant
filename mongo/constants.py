import os
import uuid
from bson.binary import Binary
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
COLLECTIONS_WITH_DIRECT_BUSINESS = {"project", "workItem", "cycle", "module", "page"}

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
    return os.getenv("BUSINESS_UUID") or os.getenv("BUSINESS_ID") or ""

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
    return os.getenv("MEMBER_UUID") or os.getenv("STAFF_ID") or os.getenv("USER_ID") or ""

def _get_current_context():
    """Get current business and member context."""
    return {
        "business_uuid": _get_business_uuid(),
        "member_uuid": _get_member_uuid()
    }

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

def _uuid_to_java_legacy_bytes(u: uuid.UUID) -> bytes:
    """Encode a UUID to Java legacy (MSB+LSB) byte order (subtype 3)."""
    msb = ((u.time_low << 32) | (u.time_mid << 16) | u.time_hi_version)
    lsb = ((u.clock_seq_hi_variant << 56) | (u.clock_seq_low << 48) | u.node)
    return msb.to_bytes(8, byteorder="big") + lsb.to_bytes(8, byteorder="big")


def _java_legacy_bytes_to_uuid(b: bytes) -> uuid.UUID:
    """Decode Java legacy UUID bytes (16 bytes) into a Python uuid.UUID."""
    if not isinstance(b, (bytes, bytearray)) or len(b) != 16:
        raise ValueError("Java legacy UUID must be 16 bytes")
    msb = int.from_bytes(b[:8], byteorder="big")
    lsb = int.from_bytes(b[8:], byteorder="big")
    fields = (
        (msb >> 32) & 0xFFFFFFFF,  # time_low
        (msb >> 16) & 0xFFFF,      # time_mid
        (msb >> 0) & 0xFFFF,       # time_hi_version
        (lsb >> 56) & 0xFF,        # clock_seq_hi_variant
        (lsb >> 48) & 0xFF,        # clock_seq_low
        lsb & 0xFFFFFFFFFFFF,      # node (48 bits)
    )
    return uuid.UUID(fields=fields)


def uuid_str_to_mongo_binary(uuid_str: str) -> Binary:
    """Convert UUID string to Java-legacy Binary (subtype 3) for MongoDB queries."""
    if not isinstance(uuid_str, str) or not uuid_str:
        raise ValueError("uuid_str must be a non-empty string")

    cleaned_uuid = uuid_str.strip('"\'')
    try:
        u = uuid.UUID(cleaned_uuid)
        return Binary(_uuid_to_java_legacy_bytes(u), subtype=3)
    except ValueError as e:
        raise ValueError(f"Invalid UUID format '{uuid_str}': {e}") from e


def mongo_binary_to_uuid_str(b: Binary) -> str:
    """Convert Binary(subtype=3, Java-legacy) to canonical UUID string.

    Falls back to str(b) when not a Binary subtype 3 value.
    """
    try:
        if isinstance(b, Binary) and getattr(b, "subtype", None) == 3:
            return str(_java_legacy_bytes_to_uuid(bytes(b)))
        return str(b)
    except Exception:
        return str(b)

