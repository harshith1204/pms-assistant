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
    USERNAME,
    ENFORCE_AUTHZ_FILTER,
    AUTH_MEMBER_UUID,
    AUTH_ALLOWED_PROJECT_UUIDS,
)
from auth import apply_authorization_filter
MOCK_USER_DATABASE = {
    "harshith": {
        "role": "developer", "member_id": "M789", "business_id": "B123"
    },
    "gaurav": {
        "role": "admin", "member_id": "M001", "business_id": "B123"
    }
}


class DirectMongoClient:
    """Direct MongoDB client using Motor (async PyMongo) - replaces MongoDB MCP"""

    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.connected = False
        self._connect_lock = asyncio.Lock()
        # Authorization awareness: store metadata about the last aggregate call
        self.last_auth_meta: Dict[str, Any] = {
            "auth_applied": False,
            "auth_restricted": False,
            "stages": [],
        }

    async def connect(self):
        """Initialize direct MongoDB connection with persistent connection pool"""
        span_cm = contextlib.nullcontext()
        with span_cm as span:
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
                    
                    pass
                    
                    print(f"✅ MongoDB connected with persistent connection pool (50 connections)")
                    print(f"   Direct connection - no MCP/Smithery overhead!")
                    
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
        span_cm = contextlib.nullcontext()
        with span_cm as span:
            pass
            
            # Motor maintains persistent connection pool automatically
            # No need to check connection status on every query - massive latency savings!
            if not self.client:
                raise RuntimeError("MongoDB client not initialized. Call connect() first.")
            
            try:
                # Prepare business scoping injection (prepend stages)
                injected_stages: List[Dict[str, Any]] = []
                auth_stages: List[Dict[str, Any]] = []
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
                        
                # Inject authorization stages based on authenticated user context
                if ENFORCE_AUTHZ_FILTER:
                    user_context = None
                    # Prefer explicit AUTH_* env config if provided
                    if AUTH_MEMBER_UUID or AUTH_ALLOWED_PROJECT_UUIDS:
                        user_context = {
                            "member_id": AUTH_MEMBER_UUID,
                            "allowed_project_ids": AUTH_ALLOWED_PROJECT_UUIDS,
                        }
                    # Fallback to mock database by USERNAME for local/dev
                    elif USERNAME and USERNAME in MOCK_USER_DATABASE:
                        user_context = MOCK_USER_DATABASE[USERNAME]

                    if user_context:
                        auth_stages = apply_authorization_filter(collection, user_context)
                        if auth_stages:
                            injected_stages.extend(auth_stages)
                            print("Auth stages injected:", auth_stages)
                # Execute aggregation - Motor uses persistent connection pool
                db = self.client[database]
                coll = db[collection]
                effective_pipeline = (injected_stages + pipeline) if injected_stages else pipeline
                cursor = coll.aggregate(effective_pipeline)
                results = await cursor.to_list(length=None)

                # Record authorization metadata for agent awareness
                self.last_auth_meta = {
                    "auth_applied": bool(auth_stages),
                    "auth_restricted": bool(auth_stages) and isinstance(results, list) and len(results) == 0,
                    "stages": auth_stages or [],
                }
                
                pass
                
                return results
                
            except Exception as e:
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

    def get_last_auth_meta(self) -> Dict[str, Any]:
        """Expose metadata about the last authorization filter injection."""
        return dict(self.last_auth_meta)


# Global instance - drop-in replacement for mongodb_tools
direct_mongo_client = DirectMongoClient()
