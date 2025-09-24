# Database configuration
DATABASE_NAME = "ProjectManagement"
MONGODB_CONNECTION_STRING = "mongodb://BeeOSAdmin:Proficornlabs%401118@172.214.123.233:27017/?authSource=admin"

# Qdrant configuration (hybrid search)
# Prefer environment variables; fall back to defaults/placeholders
import os
QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "pms_collection")
DEFAULT_EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "768"))

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

from langchain_mcp_adapters.client import MultiServerMCPClient
from typing import Dict, Any

class MongoDBTools:
    """MongoDB MCP Tools wrapper using langchain-mcp-adapters"""

    def __init__(self):
        self.client = MultiServerMCPClient(mongodb_server_config)
        self.tools = []
        self.connected = False

    async def connect(self):
        """Initialize connection to MongoDB MCP server using langchain-mcp-adapters"""
        try:
            # Get tools from the MCP server (this will establish connections as needed)
            self.tools = await self.client.get_tools()
            self.connected = True
            print(f"Connected to MongoDB MCP. Available tools: {[tool.name for tool in self.tools]}")

        except Exception as e:
            print(f"Failed to connect to MongoDB MCP server: {e}")
            raise

    async def disconnect(self):
        """Disconnect from MongoDB MCP server"""
        # MultiServerMCPClient handles connection cleanup automatically
        self.connected = False
        self.tools = []

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a MongoDB MCP tool"""
        if not self.connected:
            raise ValueError("Not connected to MCP server")

        # Find the tool
        tool = next((t for t in self.tools if t.name == tool_name), None)
        if not tool:
            raise ValueError(f"Tool {tool_name} not available")

        # Execute the tool directly (it handles MCP communication internally)
        result = await tool.ainvoke(arguments)
        return result

# Global MongoDB tools instance
mongodb_tools = MongoDBTools()
