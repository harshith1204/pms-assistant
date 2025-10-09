#!/usr/bin/env python3
"""Direct MongoDB client using PyMongo - replacing MongoDB MCP"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, Any, List
import os
import contextlib
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
    """Direct MongoDB client using Motor (async PyMongo) - replaces MongoDB MCP

    Supports dynamic connection strings per-call or per-session. When a
    connection string override is provided, the client will (re)connect using
    that URI and reuse the persistent pool for subsequent calls until changed
    again.
    """

    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.connected = False
        self._connect_lock = asyncio.Lock()
        self._connection_string: str | None = None

        
    async def connect(self, connection_string: str | None = None):
        """Initialize or switch MongoDB connection with persistent connection pool

        Args:
            connection_string: Optional MongoDB URI to use for this connection.
                If not provided, falls back to env var MONGODB_CONNECTION_STRING
                when set, otherwise to the codebase default from
                `mongo.constants.MONGODB_CONNECTION_STRING`.
        """
        span_cm = contextlib.nullcontext()
        with span_cm as span:
            try:
                async with self._connect_lock:
                    # Resolve target connection string with sensible fallbacks
                    target_conn_str = (
                        connection_string
                        or os.getenv("MONGODB_CONNECTION_STRING")
                        or MONGODB_CONNECTION_STRING
                    )

                    # If already connected with the same URI, reuse the pool
                    if self.connected and self.client and self._connection_string == target_conn_str:
                        print("✅ MongoDB already connected (reusing persistent connection)")
                        return

                    # If connected to a different URI, close before switching
                    if self.connected and self.client and self._connection_string != target_conn_str:
                        print("🔄 Switching MongoDB connection URI; closing previous client")
                        self.client.close()
                        self.connected = False
                        self.client = None

                    # Create Motor client with optimized connection pool settings
                    # Motor maintains persistent connections automatically
                    self.client = AsyncIOMotorClient(
                        target_conn_str,
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

                    # Mark connected and remember URI in use
                    self.connected = True
                    self._connection_string = target_conn_str

                    pass

                    print("✅ MongoDB connected with persistent connection pool (50 connections)")
                    print("   Direct connection - no MCP/Smithery overhead!")

            except Exception as e:
                pass
                print(f"❌ Failed to connect to MongoDB: {e}")
                raise

    async def disconnect(self):
        """Disconnect from MongoDB"""
        if self.client:
            self.client.close()
        self.connected = False
        self.client = None
        self._connection_string = None

    async def aggregate(self, database: str, collection: str, pipeline: List[Dict[str, Any]], connection_string: str | None = None) -> List[Dict[str, Any]]:
        """Execute MongoDB aggregation pipeline directly
        
        This replaces mongodb_tools.execute_tool("aggregate", {...})
        
        Args:
            database: Database name
            collection: Collection name
            pipeline: MongoDB aggregation pipeline
            connection_string: Optional MongoDB URI to override the current
                connection for this call. When provided and different from the
                active one, a reconnection will occur automatically.
            
        Returns:
            List of result documents
        """
        span_cm = contextlib.nullcontext()
        with span_cm as span:
            pass
            
            # Ensure connection exists and matches requested URI (if provided)
            if (not self.client) or (connection_string is not None and connection_string != self._connection_string):
                await self.connect(connection_string=connection_string)
            
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
                effective_pipeline = (injected_stages + pipeline) if injected_stages else pipeline
                cursor = coll.aggregate(effective_pipeline)
                results = await cursor.to_list(length=None)
                
                pass
                
                return results
                
            except Exception as e:
                pass
                raise

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Compatibility wrapper matching MongoDB MCP interface
        
        This maintains API compatibility with existing code that calls:
        mongodb_tools.execute_tool("aggregate", args)

        Supported tools and arguments:
        - aggregate: {
            database?: str,
            collection: str,
            pipeline: list[dict],
            connection_string?: str  # optional per-call MongoDB URI override
          }
        """
        if tool_name == "aggregate":
            database = arguments.get("database", DATABASE_NAME)
            collection = arguments["collection"]
            pipeline = arguments["pipeline"]
            connection_string = (
                arguments.get("connection_string")
            )
            return await self.aggregate(database, collection, pipeline, connection_string=connection_string)
        else:
            raise ValueError(f"Tool '{tool_name}' not supported by direct client. Only 'aggregate' is implemented.")


# Global instance - drop-in replacement for mongodb_tools
direct_mongo_client = DirectMongoClient()
