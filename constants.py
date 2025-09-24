# Database configuration
DATABASE_NAME = "ProjectManagement"
MONGODB_CONNECTION_STRING = "mongodb://BeeOSAdmin:Proficornlabs%401118@172.214.123.233:27017/?authSource=admin"

# Qdrant configuration
QDRANT_URL = "http://localhost:6333"  # Default Qdrant URL
QDRANT_COLLECTION_NAME = "pms_content"  # Collection for page and work item content
EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Sentence transformer model for embeddings

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
import asyncio

class MongoDBTools:
    """MongoDB MCP Tools wrapper using langchain-mcp-adapters"""

    def __init__(self):
        self.client = MultiServerMCPClient(smithery_config)
        self.tools = []
        self.connected = False
        self._connect_lock = asyncio.Lock()
        self._tool_map: Dict[str, Any] = {}

    async def connect(self):
        """Initialize connection to MongoDB MCP server using langchain-mcp-adapters"""
        try:
            async with self._connect_lock:
                # If already connected and tools are loaded, avoid reconnecting
                if self.connected and self.tools:
                    return
                # Get tools from the MCP server (this will establish connections as needed)
                self.tools = await self.client.get_tools()
                self._tool_map = {tool.name: tool for tool in self.tools}
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
        self._tool_map = {}

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a MongoDB MCP tool"""
        if not self.connected:
            # Attempt to lazily (re)connect for resilience
            await self.connect()

        # Find the tool
        tool = self._tool_map.get(tool_name)
        if not tool:
            raise ValueError(f"Tool {tool_name} not available")

        # Execute the tool directly (it handles MCP communication internally)
        result = await tool.ainvoke(arguments)
        return result

# Global MongoDB tools instance
mongodb_tools = MongoDBTools()
