#!/usr/bin/env python3
"""Direct MongoDB client using PyMongo - replacing MongoDB MCP"""

from motor.motor_asyncio import AsyncIOMotorClient
from typing import Dict, Any, List
import os
import contextlib
import asyncio
from dotenv import load_dotenv

load_dotenv()

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
    uuid_str_to_mongo_binary,
    COLLECTIONS_WITH_DIRECT_BUSINESS,
)

import websocket_handler as _ws_ctx

# NOTE: Do NOT capture RBAC context at import time.
# Read business/member IDs at query time to reflect the active websocket user.

class DirectMongoClient:
    """Direct MongoDB client using Motor (async PyMongo) - replaces MongoDB MCP"""

    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.connected = False
        self._connect_lock = asyncio.Lock()

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
                # --- Resolve RBAC context at query time ---
                def _flag(name: str) -> bool:
                    return os.getenv(name, "").lower() in ("1", "true", "yes")

                # Prefer runtime websocket context; fall back to env vars
                biz_uuid: str | None = getattr(_ws_ctx, "business_id_global", None) or os.getenv("BUSINESS_ID")
                member_uuid: str | None = (
                    os.getenv("MEMBER_ID")
                    or os.getenv("STAFF_ID")
                    or getattr(_ws_ctx, "user_id_global", None)
                )

                enforce_business: bool = _flag("ENFORCE_BUSINESS_FILTER") or bool(biz_uuid)
                enforce_member: bool = _flag("ENFORCE_MEMBER_FILTER") or bool(member_uuid)

                # Prepare business and member scoping injections (prepend stages)
                injected_stages: List[Dict[str, Any]] = []

                # 1) Business scoping
                if enforce_business and biz_uuid:
                    try:
                        biz_bin = uuid_str_to_mongo_binary(biz_uuid)
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
                        pass

                # 2) Member-level project RBAC scoping
                if enforce_member and member_uuid:
                    try:
                        mem_bin = uuid_str_to_mongo_binary(member_uuid)

                        def _membership_join(local_field: str) -> List[Dict[str, Any]]:
                            """Build a $lookup + $match + $unset pipeline ensuring the document's project belongs to member."""
                            return [
                                {"$lookup": {
                                    "from": "members",
                                    "localField": local_field,
                                    "foreignField": "project._id",
                                    "as": "__mem__",
                                }},
                                # Ensure at least one membership document for this member
                                {"$match": {"__mem__": {"$elemMatch": {"staff._id": mem_bin}}}},
                                {"$unset": "__mem__"},
                            ]

                        if collection == "members":
                            # Only allow viewing own memberships
                            injected_stages.append({"$match": {"staff._id": mem_bin}})
                        elif collection == "project":
                            injected_stages.extend(_membership_join("_id"))
                        elif collection in ("workItem", "cycle", "module", "page"):
                            injected_stages.extend(_membership_join("project._id"))
                        elif collection == "projectState":
                            injected_stages.extend(_membership_join("projectId"))
                        # Other collections: no-op
                    except Exception:
                        # Do not fail query if member filter construction fails
                        pass

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
