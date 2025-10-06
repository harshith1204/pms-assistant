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

from mongo.constants import (
    DATABASE_NAME,
    MONGODB_CONNECTION_STRING,
    BUSINESS_UUID,
    ENFORCE_BUSINESS_FILTER,
    uuid_str_to_mongo_binary,
    COLLECTIONS_WITH_DIRECT_BUSINESS,
)


class DirectMongoClient:
    """Direct MongoDB client using Motor (async PyMongo) - replaces MongoDB MCP"""

    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.connected = False
        self._connect_lock = asyncio.Lock()

    async def connect(self):
        """Initialize direct MongoDB connection with persistent connection pool"""
        tracer = trace.get_tracer(__name__)
        with tracer.start_as_current_span("direct_mongo.connect", kind=trace.SpanKind.INTERNAL) as span:
            try:
                async with self._connect_lock:
                    if self.connected and self.client:
                        print("✅ MongoDB already connected (reusing persistent connection)")
                        return
                    
                    # Create Motor client with optimized connection pool settings
                    # Motor maintains persistent connections automatically
                    self.client = AsyncIOMotorClient(
                        MONGODB_CONNECTION_STRING,
                        maxPoolSize=50,          # Max connections in pool
                        minPoolSize=10,          # Keep minimum connections alive
                        maxIdleTimeMS=45000,     # Keep idle connections for 45s
                        waitQueueTimeoutMS=5000, # Faster timeout for queue
                        serverSelectionTimeoutMS=5000,  # Faster server selection
                        connectTimeoutMS=10000,  # Connection timeout
                        socketTimeoutMS=20000,   # Socket timeout
                    )
                    
                    # Test connection
                    await self.client.admin.command('ping')
                    
                    self.connected = True
                    
                    if span:
                        try:
                            span.set_attribute("connection.type", "direct_motor")
                            span.set_attribute("connection.persistent", True)
                            span.set_attribute("connection.pool_size", 50)
                            span.set_attribute("database.name", DATABASE_NAME)
                        except Exception:
                            pass
                    
                    print(f"✅ MongoDB connected with persistent connection pool (50 connections)")
                    print(f"   Direct connection - no MCP/Smithery overhead!")
                    
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
            
            # Motor maintains persistent connection pool automatically
            # No need to check connection status on every query - massive latency savings!
            if not self.client:
                raise RuntimeError("MongoDB client not initialized. Call connect() first.")
            
            try:
                # Prepare business scoping injection (prepend stages)
                injected_stages: List[Dict[str, Any]] = []
                if ENFORCE_BUSINESS_FILTER and BUSINESS_UUID:
                    try:
                        biz_bin = uuid_str_to_mongo_binary(BUSINESS_UUID)
                        if collection in COLLECTIONS_WITH_DIRECT_BUSINESS:
                            injected_stages.append({"$match": {"business._id": biz_bin}})
                        elif collection == "members":
                            # Join project to filter by its business
                            injected_stages.extend([
                                {"$lookup": {
                                    "from": "project",
                                    "localField": "project._id",
                                    "foreignField": "_id",
                                    "as": "__biz_proj__"
                                }},
                                {"$match": {"__biz_proj__.business._id": biz_bin}},
                                {"$unset": "__biz_proj__"},
                            ])
                        elif collection == "projectState":
                            injected_stages.extend([
                                {"$lookup": {
                                    "from": "project",
                                    "localField": "projectId",
                                    "foreignField": "_id",
                                    "as": "__biz_proj__"
                                }},
                                {"$match": {"__biz_proj__.business._id": biz_bin}},
                                {"$unset": "__biz_proj__"},
                            ])
                    except Exception:
                        # Do not fail query if business filter construction fails
                        injected_stages = []

                # Execute aggregation - Motor uses persistent connection pool
                db = self.client[database]
                coll = db[collection]
                # Ensure $search remains the first stage for Atlas Search pipelines.
                # If we need to inject business scoping stages, place them IMMEDIATELY AFTER $search
                # to satisfy the requirement that $search is the first stage.
                if injected_stages and pipeline and isinstance(pipeline[0], dict) and (
                    "$search" in pipeline[0] or "$vectorSearch" in pipeline[0] or "$searchBeta" in pipeline[0]
                ):
                    effective_pipeline = [pipeline[0], *injected_stages, *pipeline[1:]]
                else:
                    effective_pipeline = (injected_stages + pipeline) if injected_stages else pipeline
                cursor = coll.aggregate(effective_pipeline)
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
