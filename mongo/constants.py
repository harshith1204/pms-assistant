# Database configuration
DATABASE_NAME = "ProjectManagement"
MONGODB_CONNECTION_STRING = "mongodb://BeeOSAdmin:Proficornlabs%401118@172.214.123.233:27017/?authSource=admin"

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

from langchain_mcp_adapters.client import MultiServerMCPClient
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

try:
    from openinference.semconv.trace import SpanAttributes as OI
except Exception:
    class _OI:
        TOOL_INPUT = "tool.input"
        TOOL_OUTPUT = "tool.output"
        ERROR_TYPE = "error.type"
        ERROR_MESSAGE = "error.message"

    OI = _OI()
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
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("mongodb_tools.connect", kind=trace.SpanKind.INTERNAL) as span:
            try:
                async with self._connect_lock:
                    if self.connected and self.tools:
                        return
                    self.tools = await self.client.get_tools()
                    self._tool_map = {tool.name: tool for tool in self.tools}
                    self.connected = True
                    if span:
                        try:
                            span.set_attribute("tools.count", len(self.tools))
                            span.set_attribute(OI.TOOL_OUTPUT, str([t.name for t in self.tools])[:800])
                        except Exception:
                            pass
                    print(f"Connected to MongoDB MCP. Available tools: {[tool.name for tool in self.tools]}")
            except Exception as e:
                if span:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    try:
                        span.set_attribute(OI.ERROR_TYPE, e.__class__.__name__)
                        span.set_attribute(OI.ERROR_MESSAGE, str(e))
                    except Exception:
                        pass
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
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            "mongodb_tools.execute_tool",
            kind=trace.SpanKind.INTERNAL,
            attributes={"tool.name": tool_name},
        ) as span:
            # Set tool input attribute with safe fallback key
            try:
                span.set_attribute(getattr(OI, 'TOOL_INPUT', 'tool.input'), str(arguments)[:1200])
            except Exception:
                pass
            if not self.connected:
                await self.connect()

            tool = self._tool_map.get(tool_name)
            if not tool:
                if span:
                    span.set_status(Status(StatusCode.ERROR, f"Tool {tool_name} not found"))
                raise ValueError(f"Tool {tool_name} not available")

            try:
                result = await tool.ainvoke(arguments)
                if span:
                    try:
                        preview = str(result)
                        span.set_attribute(getattr(OI, 'TOOL_OUTPUT', 'tool.output'), (preview[:1200] if not isinstance(result, list) else f"list[{len(result)}]"))
                    except Exception:
                        pass
                return result
            except Exception as e:
                if span:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    try:
                        span.set_attribute(getattr(OI, 'ERROR_TYPE', 'error.type'), e.__class__.__name__)
                        span.set_attribute(getattr(OI, 'ERROR_MESSAGE', 'error.message'), str(e))
                    except Exception:
                        pass
                raise

# Global MongoDB tools instance
mongodb_tools = MongoDBTools()
