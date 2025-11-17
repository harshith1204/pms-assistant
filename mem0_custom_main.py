import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

from mem0 import Memory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Load environment variables
load_dotenv()

# Configuration from environment variables - Use Qdrant and MongoDB
QDRANT_URL = os.environ.get("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION = os.environ.get("MEM0_QDRANT_COLLECTION", "knowledgeGraph")

MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DATABASE = os.environ.get("MEM0_MONGODB_DATABASE", "ProjectManagement")
MONGODB_COLLECTION = os.environ.get("MEM0_MONGODB_METADATA_COLLECTION", "knowledgeGraph")

# LLM Configuration - Support Groq
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
LLM_PROVIDER = os.environ.get("MEM0_LLM_PROVIDER", "openai")
LLM_MODEL = os.environ.get("MEM0_LLM_MODEL", os.environ.get("GROQ_MODEL", "gpt-4.1-nano-2025-04-14"))

HISTORY_DB_PATH = os.environ.get("HISTORY_DB_PATH", "/app/history/history.db")

# Embedder configuration - Use all-mpnet-base-v2 (768 dimensions)
# No OpenAI embeddings - using HuggingFace only
EMBEDDER_PROVIDER = os.environ.get("MEM0_EMBEDDER_PROVIDER", "huggingface")
EMBEDDER_MODEL = os.environ.get("MEM0_EMBEDDER_MODEL", "sentence-transformers/all-mpnet-base-v2")
HUGGINGFACE_API_KEY = os.environ.get("HuggingFace_API_KEY") or os.environ.get("HUGGINGFACE_API_KEY")

# Build config based on environment
# Explicitly set embedding dimension to 768 for all-mpnet-base-v2
vector_store_config = {
    "provider": "qdrant",
    "config": {
        "url": QDRANT_URL,
        "collection_name": QDRANT_COLLECTION,
        "embedding_model_dims": 768,  # Explicitly set for all-mpnet-base-v2 (768 dimensions)
    },
}

# LLM config
if LLM_PROVIDER == "groq" and GROQ_API_KEY:
    llm_config = {
        "provider": "groq",
        "config": {
            "api_key": GROQ_API_KEY,
            "model": LLM_MODEL,
            "temperature": 0.1,
        },
    }
else:
    llm_config = {
        "provider": "openai",
        "config": {
            "api_key": OPENAI_API_KEY,
            "temperature": 0.2,
            "model": LLM_MODEL,
        },
    }

# Embedder config - Always use HuggingFace (all-mpnet-base-v2, 768 dimensions)
embedder_config = {
    "provider": "huggingface",
    "config": {
        "model": EMBEDDER_MODEL,
    },
}
if HUGGINGFACE_API_KEY:
    embedder_config["config"]["api_key"] = HUGGINGFACE_API_KEY

DEFAULT_CONFIG = {
    "version": "v1.1",
    "vector_store": vector_store_config,
    "llm": llm_config,
    "embedder": embedder_config,
    "history_db_path": HISTORY_DB_PATH,
}

# Add metadata store if MongoDB is configured
if MONGODB_URI:
    DEFAULT_CONFIG["metadata_store"] = {
        "provider": "mongodb",
        "config": {
            "connection_string": MONGODB_URI,
            "database_name": MONGODB_DATABASE,
            "collection_name": MONGODB_COLLECTION,
        },
    }

try:
    # Delete existing collection if it has wrong dimensions to force recreation
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams
    
    qdrant_client = QdrantClient(url=QDRANT_URL)
    try:
        collection_info = qdrant_client.get_collection(QDRANT_COLLECTION)
        existing_size = collection_info.config.params.vectors.size
        if existing_size != 768:
            logging.warning(f"Existing collection has {existing_size} dimensions, expected 768. Deleting to recreate...")
            qdrant_client.delete_collection(QDRANT_COLLECTION)
            logging.info("Deleted collection with wrong dimensions")
    except Exception as e:
        # Collection doesn't exist or error getting info - that's fine
        logging.debug(f"Collection check: {e}")
    
    MEMORY_INSTANCE = Memory.from_config(DEFAULT_CONFIG)
    logging.info("Mem0 Memory initialized successfully with Qdrant and MongoDB")
except Exception as e:
    logging.error(f"Failed to initialize Mem0 Memory: {e}")
    raise

app = FastAPI(
    title="Mem0 REST APIs",
    description="A REST API for managing and searching memories for your AI Agents and Apps.",
    version="1.0.0",
)


class Message(BaseModel):
    role: str = Field(..., description="Role of the message (user or assistant).")
    content: str = Field(..., description="Message content.")


class MemoryCreate(BaseModel):
    messages: List[Message] = Field(..., description="List of messages to store.")
    user_id: Optional[str] = None
    agent_id: Optional[str] = None
    run_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class SearchRequest(BaseModel):
    query: str = Field(..., description="Search query.")
    user_id: Optional[str] = None
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


@app.post("/configure", summary="Configure Mem0")
def set_config(config: Dict[str, Any]):
    """Set memory configuration."""
    global MEMORY_INSTANCE
    MEMORY_INSTANCE = Memory.from_config(config)
    return {"message": "Configuration set successfully"}


@app.post("/memories", summary="Create memories")
def add_memory(memory_create: MemoryCreate):
    """Store new memories."""
    if not any([memory_create.user_id, memory_create.agent_id, memory_create.run_id]):
        raise HTTPException(status_code=400, detail="At least one identifier (user_id, agent_id, run_id) is required.")

    params = {k: v for k, v in memory_create.model_dump().items() if v is not None and k != "messages"}
    try:
        response = MEMORY_INSTANCE.add(messages=[m.model_dump() for m in memory_create.messages], **params)
        return JSONResponse(content=response)
    except Exception as e:
        logging.exception("Error in add_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories", summary="Get memories")
def get_all_memories(
    user_id: Optional[str] = None,
    run_id: Optional[str] = None,
    agent_id: Optional[str] = None,
):
    """Retrieve stored memories."""
    if not any([user_id, run_id, agent_id]):
        raise HTTPException(status_code=400, detail="At least one identifier is required.")
    try:
        params = {
            k: v for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items() if v is not None
        }
        return MEMORY_INSTANCE.get_all(**params)
    except Exception as e:
        logging.exception("Error in get_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories/{memory_id}", summary="Get a memory")
def get_memory(memory_id: str):
    """Retrieve a specific memory by ID."""
    try:
        return MEMORY_INSTANCE.get(memory_id)
    except Exception as e:
        logging.exception("Error in get_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/search", summary="Search memories")
def search_memories(search_req: SearchRequest):
    """Search for memories based on a query."""
    try:
        params = {k: v for k, v in search_req.model_dump().items() if v is not None and k != "query"}
        return MEMORY_INSTANCE.search(query=search_req.query, **params)
    except Exception as e:
        logging.exception("Error in search_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/memories/{memory_id}", summary="Update a memory")
def update_memory(memory_id: str, updated_memory: Dict[str, Any]):
    """Update an existing memory with new content."""
    try:
        return MEMORY_INSTANCE.update(memory_id=memory_id, data=updated_memory)
    except Exception as e:
        logging.exception("Error in update_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/memories/{memory_id}/history", summary="Get memory history")
def memory_history(memory_id: str):
    """Retrieve memory history."""
    try:
        return MEMORY_INSTANCE.history(memory_id=memory_id)
    except Exception as e:
        logging.exception("Error in memory_history:")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/memories/{memory_id}", summary="Delete a memory")
def delete_memory(memory_id: str):
    """Delete a specific memory by ID."""
    try:
        MEMORY_INSTANCE.delete(memory_id=memory_id)
        return {"message": "Memory deleted successfully"}
    except Exception as e:
        logging.exception("Error in delete_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/memories", summary="Delete all memories")
def delete_all_memories(
    user_id: Optional[str] = None,
    run_id: Optional[str] = None,
    agent_id: Optional[str] = None,
):
    """Delete all memories for a given identifier."""
    if not any([user_id, run_id, agent_id]):
        raise HTTPException(status_code=400, detail="At least one identifier is required.")
    try:
        params = {
            k: v for k, v in {"user_id": user_id, "run_id": run_id, "agent_id": agent_id}.items() if v is not None
        }
        MEMORY_INSTANCE.delete_all(**params)
        return {"message": "All relevant memories deleted"}
    except Exception as e:
        logging.exception("Error in delete_all_memories:")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/reset", summary="Reset all memories")
def reset_memory():
    """Completely reset stored memories."""
    try:
        MEMORY_INSTANCE.reset()
        return {"message": "All memories reset"}
    except Exception as e:
        logging.exception("Error in reset_memory:")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/", summary="Redirect to the OpenAPI documentation", include_in_schema=False)
def home():
    """Redirect to the OpenAPI documentation."""
    return RedirectResponse(url="/docs")

