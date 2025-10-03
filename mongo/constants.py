# Database configuration
DATABASE_NAME = "ProjectManagement"
MONGODB_CONNECTION_STRING = "mongodb://backendInterns:mUXe57JwdugphnEn@4.213.88.219:27017/?authSource=admin"

# Qdrant configuration
QDRANT_API_KEY="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.pWxytfubjbSDBCTZaH321Eya7qis_tP6sHMAZ3Gki6Y"
QDRANT_URL = "https://dc88ad91-1e1e-48b4-bf73-0e5c1db1cffd.europe-west3-0.gcp.cloud.qdrant.io"  # Default Qdrant URL
QDRANT_COLLECTION_NAME = "pms_collection"  # Collection for page and work item content
EMBEDDING_MODEL = "google/embeddinggemma-300m"  # Sentence transformer model for embeddings


# MCP Server Configuration for ProjectManagement
mongodb_server_config = {
    "mcpServers": {
        "mongodb": {
            "command": "docker",
            "args": [
                "run",
                "-i",
                "--rm",
                "-e",
                "MDB_MCP_CONNECTION_STRING",
                "mcp/mongodb"
            ],
            "env": {
                "MDB_MCP_CONNECTION_STRING": MONGODB_CONNECTION_STRING
            },
            "transport": "stdio"
        }
    }
}

# HTTP-based configuration for Smithery with ProjectManagement focus
smithery_config = {
    "mongodb": {
        "url": "https://server.smithery.ai/@mongodb-js/mongodb-mcp-server/mcp?api_key=4fd11c6a-4c6f-45ce-ab0d-24cb4c051779&profile=furious-lemming-rvSkqO",
        "transport": "streamable_http"
    }
}

# Import the direct MongoDB client (replaces MongoDB MCP + Smithery)
from mongo.client import direct_mongo_client

# Alias for backward compatibility with existing code
mongodb_tools = direct_mongo_client
