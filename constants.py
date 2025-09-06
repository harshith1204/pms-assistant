# Database configuration
DATABASE_NAME = "ProjectManagement"
MONGODB_CONNECTION_STRING = "mongodb://BeeOSAdmin:Proficornlabs%401118@172.214.123.233:27017/?authSource=admin"

# MCP Server Configuration for ProjectManagement
mongodb_server_config = {
    "mongodb": {
        "command": "npx",
        "args": ["-y", "@mongodb-js/mongodb-mcp-server"],
        "env": {
            "MONGODB_CONNECTION_STRING": MONGODB_CONNECTION_STRING,
            "MONGODB_DATABASE_NAME": DATABASE_NAME
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
from redis_utils import get_cached_json, set_cached_json, tool_cache_key, TOOL_CACHE_TTL_SECONDS

class MongoDBTools:
    """MongoDB MCP Tools wrapper using langchain-mcp-adapters"""

    def __init__(self):
        self.client = MultiServerMCPClient(smithery_config)
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
        """Execute a MongoDB MCP tool with Redis caching."""
        if not self.connected:
            raise ValueError("Not connected to MCP server")

        # Find the tool
        tool = next((t for t in self.tools if t.name == tool_name), None)
        if not tool:
            raise ValueError(f"Tool {tool_name} not available")

        # Try cache first
        cache_key = tool_cache_key(tool_name, arguments)
        cached = await get_cached_json(cache_key)
        if cached is not None:
            return cached

        # Execute the tool directly (it handles MCP communication internally)
        result = await tool.ainvoke(arguments)

        # Set cache with short TTL to reduce latency across identical requests
        try:
            await set_cached_json(cache_key, result, ttl_seconds=TOOL_CACHE_TTL_SECONDS)
        except Exception:
            pass
        return result

# Global MongoDB tools instance
mongodb_tools = MongoDBTools()
