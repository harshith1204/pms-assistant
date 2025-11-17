"""
Mem0 Configuration and Setup

Centralized configuration for Mem0 open source with Groq LLM.
Supports all required functionalities with open source deployment.
"""

import logging
import os
from typing import Dict, Any, Optional
from mem0 import MemoryClient

logger = logging.getLogger(__name__)


def get_mem0_config() -> Dict[str, Any]:
    """Get Mem0 configuration dictionary for reference/documentation.
    
    Note: Mem0 open source uses environment variables for configuration.
    This function returns a dict for reference and sets up env vars.
    
    Configures Mem0 to use (via environment variables):
    - Groq LLM for entity extraction, consolidation, and other operations
    - Qdrant for vector storage (separate collection)
    - MongoDB for metadata storage (separate collections)
    - Graph Memory for knowledge graph building
    """
    
    # Vector store configuration
    # IMPORTANT: Using separate collections to avoid conflicts with existing content collections
    # Existing Qdrant collection: "ProjectManagement" (for pages, workItems, etc.)
    # Mem0 Qdrant collection: "knowledgeGraph" (separate, isolated)
    vector_store_provider = os.getenv("MEM0_VECTOR_STORE_PROVIDER", "qdrant")
    vector_store_config = {}
    
    if vector_store_provider == "qdrant":
        # Use separate Qdrant collection for Mem0 (different from "ProjectManagement")
        mem0_qdrant_collection = os.getenv("MEM0_QDRANT_COLLECTION", "knowledgeGraph")
        vector_store_config = {
            "provider": "qdrant",
            "config": {
                "url": os.getenv("QDRANT_URL", "http://localhost:6333"),
                "collection_name": mem0_qdrant_collection,  # Separate from content collection
            }
        }
    elif vector_store_provider == "mongodb":
        # Use separate MongoDB collection for Mem0 vectors
        mem0_mongo_vector_collection = os.getenv("MEM0_MONGODB_VECTOR_COLLECTION", "knowledgeGraph")
        vector_store_config = {
            "provider": "mongodb",
            "config": {
                "connection_string": os.getenv("MONGODB_URI"),
                "database_name": os.getenv("DATABASE_NAME", "ProjectManagement"),
                "collection_name": mem0_mongo_vector_collection,  # Separate from content collections
            }
        }
    else:
        # Default: use Mem0's default vector store
        vector_store_config = None
    
    # Metadata store configuration
    # IMPORTANT: Using separate MongoDB collections to avoid conflicts
    # Existing MongoDB collections: page, workItem, cycle, module, project, epic, userStory, features
    # Mem0 MongoDB collections: knowledgeGraph (separate, isolated)
    metadata_store_provider = os.getenv("MEM0_METADATA_STORE_PROVIDER", "mongodb")
    metadata_store_config = {}
    
    if metadata_store_provider == "mongodb":
        # Use separate MongoDB collection for Mem0 metadata
        mem0_metadata_collection = os.getenv("MEM0_MONGODB_METADATA_COLLECTION", "knowledgeGraph")
        metadata_store_config = {
            "provider": "mongodb",
            "config": {
                "connection_string": os.getenv("MONGODB_URI"),
                "database_name": os.getenv("DATABASE_NAME", "ProjectManagement"),
                "collection_name": mem0_metadata_collection,  # Separate from content collections
            }
        }
    else:
        # Default: use Mem0's default metadata store
        metadata_store_config = None
    
    # LLM Configuration - Use Groq for Mem0's internal operations
    # Mem0 open source uses environment variables for LLM configuration
    # Set these environment variables to use Groq:
    # - GROQ_API_KEY: Your Groq API key
    # - MEM0_LLM_PROVIDER=groq (or set via MEM0_LLM_PROVIDER env var)
    # - MEM0_LLM_MODEL: Groq model name (defaults to GROQ_MODEL, which uses kimi-k2 same as agent)
    groq_api_key = os.getenv("GROQ_API_KEY")
    groq_model = os.getenv("MEM0_GROQ_MODEL", os.getenv("GROQ_MODEL", "moonshotai/kimi-k2-instruct-0905"))
    
    if not groq_api_key:
        logger.warning("GROQ_API_KEY not set. Mem0 will use default LLM provider.")
    else:
        # Set environment variables for Mem0 to use Groq
        # Mem0 open source reads these env vars automatically
        os.environ.setdefault("MEM0_LLM_PROVIDER", "groq")
        os.environ.setdefault("MEM0_LLM_MODEL", groq_model)
        os.environ.setdefault("MEM0_LLM_TEMPERATURE", os.getenv("MEM0_GROQ_TEMPERATURE", "0.1"))
        os.environ.setdefault("MEM0_LLM_MAX_TOKENS", os.getenv("MEM0_GROQ_MAX_TOKENS", "2000"))
        logger.info(f"Configured Mem0 to use Groq LLM: {groq_model}")
    
    # Embedder configuration - Use all-mpnet-base-v2 (768 dimensions)
    # No OpenAI embeddings - using HuggingFace only
    embedder_provider = os.getenv("MEM0_EMBEDDER_PROVIDER", "huggingface")
    embedder_model = os.getenv("MEM0_EMBEDDER_MODEL", "sentence-transformers/all-mpnet-base-v2")
    
    # Always use HuggingFace embedder (all-mpnet-base-v2 produces 768-dimensional vectors)
    huggingface_api_key = os.getenv("HuggingFace_API_KEY") or os.getenv("HUGGINGFACE_API_KEY")
    embedder_config = {
        "provider": "huggingface",
        "config": {
            "model": embedder_model,
        }
    }
    if huggingface_api_key:
        embedder_config["config"]["api_key"] = huggingface_api_key
    
    logger.info(f"Configured Mem0 to use HuggingFace embedder: {embedder_model} (768 dimensions)")
    
    # Build configuration dictionary for reference/documentation
    config_dict = {
        "version": "v1.1",
        "llm": {
            "provider": "groq",
            "config": {
                "api_key": groq_api_key,
                "model": groq_model,
                "temperature": float(os.getenv("MEM0_GROQ_TEMPERATURE", "0.1")),
                "max_tokens": int(os.getenv("MEM0_GROQ_MAX_TOKENS", "2000")),
            }
        },
        "embedder": embedder_config,
    }
    
    if vector_store_config:
        config_dict["vector_store"] = vector_store_config
        # Set environment variables for Mem0
        os.environ.setdefault("MEM0_VECTOR_STORE_PROVIDER", vector_store_provider)
        if vector_store_provider == "qdrant":
            os.environ.setdefault("MEM0_QDRANT_URL", os.getenv("QDRANT_URL", "http://localhost:6333"))
            os.environ.setdefault("MEM0_QDRANT_COLLECTION", mem0_qdrant_collection)
    
    if metadata_store_config:
        config_dict["metadata_store"] = metadata_store_config
        # Set environment variables for Mem0
        os.environ.setdefault("MEM0_METADATA_STORE_PROVIDER", metadata_store_provider)
        if metadata_store_provider == "mongodb":
            os.environ.setdefault("MEM0_MONGODB_URI", os.getenv("MONGODB_URI", ""))
            os.environ.setdefault("MEM0_MONGODB_DATABASE", os.getenv("DATABASE_NAME", "ProjectManagement"))
            os.environ.setdefault("MEM0_MONGODB_METADATA_COLLECTION", mem0_metadata_collection)
    
    # Memory extraction configuration
    # Mem0 automatically extracts entities, relationships, and patterns using Groq LLM
    extraction_enabled = os.getenv("MEM0_EXTRACTION_ENABLED", "true").lower() == "true"
    if extraction_enabled:
        config_dict["extraction"] = {"enabled": True}
        os.environ.setdefault("MEM0_EXTRACTION_ENABLED", "true")
    
    # Consolidation configuration
    # Mem0 automatically consolidates similar/duplicate memories using Groq LLM
    consolidation_enabled = os.getenv("MEM0_CONSOLIDATION_ENABLED", "true").lower() == "true"
    if consolidation_enabled:
        merge_threshold = float(os.getenv("MEM0_MERGE_THRESHOLD", "0.8"))
        config_dict["consolidation"] = {
            "enabled": True,
            "merge_threshold": merge_threshold,
        }
        os.environ.setdefault("MEM0_CONSOLIDATION_ENABLED", "true")
        os.environ.setdefault("MEM0_MERGE_THRESHOLD", str(merge_threshold))
    
    # Conflict resolution configuration
    # Mem0 automatically resolves conflicting memories using Groq LLM
    conflict_resolution_enabled = os.getenv("MEM0_CONFLICT_RESOLUTION_ENABLED", "true").lower() == "true"
    if conflict_resolution_enabled:
        config_dict["conflict_resolution"] = {"enabled": True}
        os.environ.setdefault("MEM0_CONFLICT_RESOLUTION_ENABLED", "true")
    
    # Graph Memory configuration (Knowledge Graph)
    # Mem0 automatically builds a knowledge graph from memories using Groq LLM
    graph_memory_enabled = os.getenv("MEM0_GRAPH_MEMORY_ENABLED", "true").lower() == "true"
    if graph_memory_enabled:
        graph_provider = os.getenv("MEM0_GRAPH_PROVIDER", "default")
        config_dict["graph_memory"] = {"enabled": True, "provider": graph_provider}
        os.environ.setdefault("MEM0_GRAPH_MEMORY_ENABLED", "true")
        os.environ.setdefault("MEM0_GRAPH_PROVIDER", graph_provider)
        
        if graph_provider == "neo4j":
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://172.17.0.2:7687")
            config_dict["graph_memory"]["config"] = {
                "uri": neo4j_uri,
                "user": os.getenv("NEO4J_USER", "neo4j"),
                "password": os.getenv("NEO4J_PASSWORD", ""),
            }
            os.environ.setdefault("NEO4J_URI", neo4j_uri)
        elif graph_provider == "memgraph":
            config_dict["graph_memory"]["config"] = {
                "host": os.getenv("MEMGRAPH_HOST", "localhost"),
                "port": int(os.getenv("MEMGRAPH_PORT", "7687")),
            }
    
    # Return config dict for reference (Mem0 reads from environment variables)
    return config_dict


def initialize_mem0_client() -> MemoryClient:
    """Initialize Mem0 client with proper configuration for open source deployment.
    
    Note: Mem0 open source uses environment variables for configuration.
    This function:
    1. Calls get_mem0_config() to set up environment variables (Groq LLM, Qdrant, MongoDB)
    2. Initializes MemoryClient with config dict (open source mode)
    
    For open source Mem0, pass config dict directly instead of API key.
    """
    try:
        # Set up environment variables for Mem0 (Groq LLM, Qdrant, MongoDB, etc.)
        config_dict = get_mem0_config()  # This sets env vars and returns dict for reference
        
        # Initialize Mem0 client for open source or cloud
        # Check if MEM0_HOST is set (for self-hosted) or use cloud API
        mem0_host = os.getenv("MEM0_HOST", "https://api.mem0.ai")
        mem0_api_key = os.getenv("MEM0_API_KEY")
        
        # For self-hosted Mem0 Docker server, use Memory class directly
        # MemoryClient expects /v1/ping/ endpoint which Docker server doesn't have
        if mem0_host != "https://api.mem0.ai" or not mem0_api_key or mem0_api_key == "local":
            # Docker server mode - use Memory class directly
            try:
                from mem0 import Memory
                memory_instance = Memory.from_config(config_dict)
                logger.info(f"Mem0 Memory initialized for Docker server at {mem0_host}")
                return _MemoryWrapper(memory_instance)
            except Exception as e:
                logger.warning(f"Failed to initialize Docker Mem0 Memory: {e}")
                # Continue to try MemoryClient as fallback
                try:
                    client = MemoryClient(api_key="local" if not mem0_api_key else mem0_api_key, host=mem0_host)
                    logger.info(f"Mem0 client initialized for self-hosted instance at {mem0_host}")
                    return client
                except Exception as client_e:
                    logger.warning(f"MemoryClient fallback also failed: {client_e}")
                    raise e
        
        # Cloud mode - requires API key
        if mem0_api_key:
            try:
                client = MemoryClient(api_key=mem0_api_key, host=mem0_host)
                logger.info("Mem0 client initialized with cloud API")
                return client
            except Exception as e:
                logger.error(f"Failed to initialize Mem0 cloud client: {e}")
                raise
        
        # No API key and not self-hosted - raise error
        raise ValueError(
            "MEM0_API_KEY not provided. "
            "Either set MEM0_API_KEY for cloud usage or set MEM0_HOST for self-hosted Mem0."
        )
        
    except Exception as e:
        logger.error(f"Failed to initialize Mem0 client: {e}")
        # For Docker-based Mem0, use Memory class directly instead of MemoryClient
        # MemoryClient expects /v1/ping/ endpoint which Docker server doesn't have
        if mem0_host != "https://api.mem0.ai" or not mem0_api_key or mem0_api_key == "local":
            try:
                from mem0 import Memory
                memory_instance = Memory.from_config(config_dict)
                logger.info(f"Mem0 Memory initialized directly for Docker server at {mem0_host}")
                return _MemoryWrapper(memory_instance)
            except Exception as memory_error:
                logger.error(f"Failed to initialize Memory directly: {memory_error}")
                raise
        raise


class _MemoryWrapper:
    """Wrapper to make Memory instance compatible with MemoryClient interface"""
    def __init__(self, memory_instance):
        self.memory = memory_instance
    
    def add(self, messages, user_id=None, agent_id=None, run_id=None, metadata=None):
        """Add memories - compatible with MemoryClient.add()"""
        params = {}
        if user_id:
            params["user_id"] = user_id
        if agent_id:
            params["agent_id"] = agent_id
        if run_id:
            params["run_id"] = run_id
        if metadata:
            params["metadata"] = metadata
        return self.memory.add(messages=messages, **params)
    
    def search(self, query, user_id=None, agent_id=None, run_id=None, limit=10):
        """Search memories - compatible with MemoryClient.search()"""
        params = {"limit": limit}
        if user_id:
            params["user_id"] = user_id
        if agent_id:
            params["agent_id"] = agent_id
        if run_id:
            params["run_id"] = run_id
        return self.memory.search(query=query, **params)
    
    def get_all(self, user_id=None, agent_id=None, run_id=None):
        """Get all memories - compatible with MemoryClient.get_all()"""
        params = {}
        if user_id:
            params["user_id"] = user_id
        if agent_id:
            params["agent_id"] = agent_id
        if run_id:
            params["run_id"] = run_id
        return self.memory.get_all(**params)
    
    def get(self, memory_id):
        """Get a specific memory - compatible with MemoryClient.get()"""
        return self.memory.get(memory_id)
    
    def update(self, memory_id, data):
        """Update a memory - compatible with MemoryClient.update()"""
        return self.memory.update(memory_id=memory_id, data=data)
    
    def delete(self, memory_id):
        """Delete a memory - compatible with MemoryClient.delete()"""
        return self.memory.delete(memory_id=memory_id)
    
    def delete_all(self, user_id=None, agent_id=None, run_id=None):
        """Delete all memories - compatible with MemoryClient.delete_all()"""
        params = {}
        if user_id:
            params["user_id"] = user_id
        if agent_id:
            params["agent_id"] = agent_id
        if run_id:
            params["run_id"] = run_id
        return self.memory.delete_all(**params)


# Memory type constants for consistent usage
MEMORY_TYPES = {
    "USER_PREFERENCE": "user_preference",
    "USER_TRAIT": "user_trait",
    "USER_CONTEXT": "user_context",
    "AWARENESS_ENTITY": "awareness_entity",
    "CONVERSATION_PATTERN": "conversation_pattern",
    "RELATIONSHIP": "relationship",
}


def create_preference_memory(pref_type: str, pref_value: Any) -> Dict[str, Any]:
    """Create a properly formatted preference memory"""
    return {
        "role": "user",
        "content": f"User preference: {pref_type} = {pref_value}",
        "metadata": {
            "type": MEMORY_TYPES["USER_PREFERENCE"],
            "preference_type": pref_type,
            "value": pref_value,
            "source": "explicit",
        }
    }


def create_trait_memory(trait_name: str, trait_value: Any) -> Dict[str, Any]:
    """Create a properly formatted trait memory"""
    return {
        "role": "user",
        "content": f"User trait: {trait_name} = {trait_value}",
        "metadata": {
            "type": MEMORY_TYPES["USER_TRAIT"],
            "trait_name": trait_name,
            "value": trait_value,
            "source": "explicit",
        }
    }


def create_context_memory(content: str, document_id: Optional[str] = None, source: str = "explicit") -> Dict[str, Any]:
    """Create a properly formatted context memory"""
    metadata = {
        "type": MEMORY_TYPES["USER_CONTEXT"],
        "source": source,
    }
    if document_id:
        metadata["document_id"] = document_id
    
    return {
        "role": "user",
        "content": content,
        "metadata": metadata,
    }


def create_awareness_memory(entity_type: str, entity_id: str, entity_name: str, business_id: str) -> Dict[str, Any]:
    """Create a properly formatted awareness entity memory"""
    return {
        "role": "user",
        "content": f"User is aware of {entity_type}: {entity_name} (ID: {entity_id})",
        "metadata": {
            "type": MEMORY_TYPES["AWARENESS_ENTITY"],
            "entity_type": entity_type,
            "entity_id": entity_id,
            "entity_name": entity_name,
            "business_id": business_id,
            "access_level": "awareness_only",
        }
    }


def create_relationship_memory(relationship_type: str, source_entity: str, target_entity: str) -> Dict[str, Any]:
    """Create a properly formatted relationship memory"""
    return {
        "role": "user",
        "content": f"Relationship: {source_entity} {relationship_type} {target_entity}",
        "metadata": {
            "type": MEMORY_TYPES["RELATIONSHIP"],
            "relationship_type": relationship_type,
            "source_entity": source_entity,
            "target_entity": target_entity,
        }
    }

