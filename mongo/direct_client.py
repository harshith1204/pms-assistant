#!/usr/bin/env python3
"""Direct MongoDB client using PyMongo - replacing MongoDB MCP"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, Any, List
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
import asyncio

try:
    from openinference.semconv.trace import SpanAttributes as OI
except Exception:
    class _OI:
        TOOL_INPUT = "tool.input"
        TOOL_OUTPUT = "tool.output"
        ERROR_TYPE = "error.type"
        ERROR_MESSAGE = "error.message"
    OI = _OI()

from mongo.constants import DATABASE_NAME, MONGODB_CONNECTION_STRING


class DirectMongoClient:
    """Direct MongoDB client using Motor (async PyMongo) - replaces MongoDB MCP"""

    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.connected = False
        self._connect_lock = asyncio.Lock()

    async def connect(self):
        """Initialize direct MongoDB connection"""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("direct_mongo.connect", kind=trace.SpanKind.INTERNAL) as span:
            try:
                async with self._connect_lock:
                    if self.connected and self.client:
                        return
                    
                    # Create Motor client (async PyMongo)
                    self.client = AsyncIOMotorClient(MONGODB_CONNECTION_STRING)
                    
                    # Test connection
                    await self.client.admin.command('ping')
                    
                    self.connected = True
                    
                    if span:
                        try:
                            span.set_attribute("connection.type", "direct_pymongo")
                            span.set_attribute("database.name", DATABASE_NAME)
                        except Exception:
                            pass
                    
                    print(f"✅ Connected to MongoDB directly (bypassing MCP/Smithery)")
                    
            except Exception as e:
                if span:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    try:
                        span.set_attribute(OI.ERROR_TYPE, e.__class__.__name__)
                        span.set_attribute(OI.ERROR_MESSAGE, str(e))
                    except Exception:
                        pass
                print(f"❌ Failed to connect to MongoDB: {e}")
                raise

    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
        self.connected = False
        self.client = None

    async def aggregate(self, database: str, collection: str, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Execute MongoDB aggregation pipeline directly
        
        This replaces mongodb_tools.execute_tool("aggregate", {...})
        
        Args:
            database: Database name
            collection: Collection name
            pipeline: MongoDB aggregation pipeline
            
        Returns:
            List of result documents
        """
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span(
            "direct_mongo.aggregate",
            kind=trace.SpanKind.INTERNAL,
            attributes={
                "db.system": "mongodb",
                "db.name": database,
                "db.mongodb.collection": collection,
                "db.operation": "aggregate"
            },
        ) as span:
            try:
                span.set_attribute(getattr(OI, 'TOOL_INPUT', 'tool.input'), str(pipeline)[:1200])
            except Exception:
                pass
            
            if not self.connected:
                await self.connect()
            
            if not self.client:
                raise RuntimeError("MongoDB client not initialized")
            
            try:
                # Execute aggregation
                db = self.client[database]
                coll = db[collection]
                cursor = coll.aggregate(pipeline)
                results = await cursor.to_list(length=None)
                
                if span:
                    try:
                        span.set_attribute(getattr(OI, 'TOOL_OUTPUT', 'tool.output'), f"list[{len(results)}]")
                        span.set_attribute("db.result_count", len(results))
                    except Exception:
                        pass
                
                return results
                
            except Exception as e:
                if span:
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    try:
                        span.set_attribute(getattr(OI, 'ERROR_TYPE', 'error.type'), e.__class__.__name__)
                        span.set_attribute(getattr(OI, 'ERROR_MESSAGE', 'error.message'), str(e))
                    except Exception:
                        pass
                raise

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Compatibility wrapper matching MongoDB MCP interface
        
        This maintains API compatibility with existing code that calls:
        mongodb_tools.execute_tool("aggregate", args)
        """
        if tool_name == "aggregate":
            database = arguments.get("database", DATABASE_NAME)
            collection = arguments["collection"]
            pipeline = arguments["pipeline"]
            return await self.aggregate(database, collection, pipeline)
        else:
            raise ValueError(f"Tool '{tool_name}' not supported by direct client. Only 'aggregate' is implemented.")


# Global instance - drop-in replacement for mongodb_tools
direct_mongo_client = DirectMongoClient()
