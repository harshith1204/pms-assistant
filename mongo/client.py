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
    uuid_str_to_mongo_binary,
    COLLECTIONS_WITH_DIRECT_BUSINESS,
)

_MEMBER_CONTEXT_CACHE = None  # type: ignore[var-annotated]
_MEMBER_CONTEXT_CACHE_MEMBER_ID: str | None = None



def _get_current_business_uuid() -> str | None:
    """Determine the active business UUID from env or websocket context."""
    try:
        # Prefer environment-scoped business ID
        from mongo.constants import BUSINESS_UUID as ENV_BUSINESS_UUID  # type: ignore
    except Exception:
        ENV_BUSINESS_UUID = None  # type: ignore

    if ENV_BUSINESS_UUID:
        return ENV_BUSINESS_UUID  # type: ignore[return-value]

    # Fallback to websocket-provided business id when available
    try:
        from websocket_handler import business_id_global  # type: ignore
        return business_id_global
    except Exception:
        return None


async def _resolve_member_context():
    """Resolve a MemberContext for data-level RBAC without relying on WS auth.

    Priority:
    1) Websocket-provided `member_context_global` if present
    2) Build from environment DEFAULT_MEMBER_ID/MEMBER_ID by reading `members` collection
    3) Return None if nothing available (queries will still be business-scoped)
    """
    # Declare global variables at the start of the function
    global _MEMBER_CONTEXT_CACHE, _MEMBER_CONTEXT_CACHE_MEMBER_ID

    # 1) Websocket-provided context
    try:
        from websocket_handler import member_context_global  # type: ignore
        if member_context_global is not None:
            # Cache and return
            _MEMBER_CONTEXT_CACHE = member_context_global
            _MEMBER_CONTEXT_CACHE_MEMBER_ID = getattr(member_context_global, "member_id", None)
            return member_context_global
    except Exception:
        pass

    # 2) Build from env member id
    member_id = os.getenv("DEFAULT_MEMBER_ID") or os.getenv("MEMBER_ID")
    if not member_id:
        return None

    # Serve from cache if up-to-date
    if _MEMBER_CONTEXT_CACHE is not None and _MEMBER_CONTEXT_CACHE_MEMBER_ID == member_id:
        return _MEMBER_CONTEXT_CACHE

    try:
        # Import lazily to avoid circular imports during module load
        from rbac.permissions import MemberContext  # type: ignore
        from rbac.auth import (  # type: ignore
            get_member_by_id,
            get_member_project_memberships,
            get_member_projects,
        )

        # Fetch profile and memberships
        member_doc = await get_member_by_id(member_id)
        project_memberships = await get_member_project_memberships(member_id)
        project_ids = list(project_memberships.keys()) or await get_member_projects(member_id)

        # Build MemberContext (gracefully handle missing profile)
        display_name = (member_doc or {}).get("displayName") or (member_doc or {}).get("name", "")
        email = (member_doc or {}).get("email") or ""
        member_type = (member_doc or {}).get("type")

        ctx = MemberContext(
            member_id=member_id,
            name=display_name,
            email=email,
            project_ids=project_ids,
            project_memberships=project_memberships,
            type=member_type,
            business_id=None,
        )

        # Cache and return
        _MEMBER_CONTEXT_CACHE = ctx
        _MEMBER_CONTEXT_CACHE_MEMBER_ID = member_id
        return ctx
    except Exception as e:
        print(f"⚠️  Failed to resolve member context from env: {e}")
        return None


async def get_member_context():
    """Public async API to obtain the current MemberContext.

    Used by tools (e.g., RAG) to enforce data-level RBAC outside HTTP deps.
    """
    return await _resolve_member_context()

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
                # Prepare business scoping and RBAC injection (prepend stages)
                injected_stages: List[Dict[str, Any]] = []

                # Resolve latest contexts dynamically to avoid stale globals
                member_context = await _resolve_member_context()
                biz_uuid = _get_current_business_uuid()
                enforce_business = os.getenv("ENFORCE_BUSINESS_FILTER", "").lower() in ("1", "true", "yes") or bool(biz_uuid)

                # 1. Apply member-based RBAC filtering first (project-scoped only)
                if member_context is not None:
                    try:
                        from rbac.filters import apply_member_pipeline_filter
                        injected_stages = apply_member_pipeline_filter([], member_context, None, collection)  # type: ignore[arg-type]
                    except Exception as e:
                        print(f"❌ MongoDB Client: RBAC filter construction failed: {e}")
                else:
                    print(f"⚠️  MongoDB Client: No member context available - RBAC filters NOT applied for collection '{collection}'")

                # 2. Apply business scoping on top of RBAC
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

                # Execute aggregation - Motor uses persistent connection pool
                db = self.client[database]
                coll = db[collection]
                effective_pipeline = (injected_stages + pipeline) if injected_stages else pipeline
                
                print(f"📊 MongoDB Query: collection='{collection}', pipeline stages={len(effective_pipeline)} (original: {len(pipeline)}, injected: {len(injected_stages)})")
                if injected_stages:
                    print(f"   First stage (RBAC filter): {injected_stages[0]}")
                
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
