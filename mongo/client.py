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
    BUSINESS_UUID,
    MEMBER_UUID,
)


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

                # Prefer runtime websocket context; fall back to env vars (via helpers)
                biz_uuid: str | None = BUSINESS_UUID()
                member_uuid: str | None = MEMBER_UUID()
                enforce_business: bool = _flag("ENFORCE_BUSINESS_FILTER") or bool(biz_uuid)
                enforce_member: bool = _flag("ENFORCE_MEMBER_FILTER") or bool(member_uuid)
                
                print(f"🔐 RBAC Status for '{collection}':")
                print(f"   biz_uuid: {biz_uuid}")
                print(f"   member_uuid: {member_uuid}")
                print(f"   enforce_business: {enforce_business}")
                print(f"   enforce_member: {enforce_member}")

                # Prepare business and member scoping injections (prepend stages)
                injected_stages: List[Dict[str, Any]] = []

                # 1) Business scoping (ONLY if member filtering is NOT enabled)
                # Member-based access takes precedence over business-based access
                if enforce_business and biz_uuid and not enforce_member:
                    print(f"   Applying business filter (member filter disabled)")
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
                    except ValueError as e:
                        # Invalid UUID format - log and skip business filter
                        print(f"⚠️  Invalid BUSINESS_UUID format '{biz_uuid}': {e}")
                        print(f"   Skipping business filter for {collection}")
                    except Exception as e:
                        # Other errors - log and skip business filter
                        print(f"⚠️  Error applying business filter for {collection}: {e}")
                elif enforce_business and biz_uuid and enforce_member:
                    print(f"   ⚠️  Business filter SKIPPED - member filter takes precedence")

                # 2) Member-level project RBAC scoping
                if enforce_member and member_uuid:
                    print(f"🔍 DEBUG: Applying member filter for collection '{collection}'")
                    print(f"   member_uuid: {member_uuid}")
                    print(f"   enforce_member: {enforce_member}")
                    try:
                        mem_bin = uuid_str_to_mongo_binary(member_uuid)
                        print(f"   mem_bin: {mem_bin}")

                        def _membership_join(local_field: str) -> List[Dict[str, Any]]:
                            """Build a $lookup + $match + $unset pipeline ensuring the document's project belongs to member."""
                            return [
                                {"$lookup": {
                                    "from": "members",
                                    "localField": local_field,
                                    "foreignField": "project._id",
                                    "as": "__mem__",
                                }},
                                # DEBUG: Add field to see member count
                                {"$addFields": {
                                    "__mem_count__": {"$size": "$__mem__"}
                                }},
                                # Ensure at least one membership document for this member
                                # Check any of the three possible ID fields
                                {"$match": {
                                    "$or": [
                                        {"__mem__": {"$elemMatch": {"_id": mem_bin}}},
                                        {"__mem__": {"$elemMatch": {"staff._id": mem_bin}}},
                                        {"__mem__": {"$elemMatch": {"memberId": mem_bin}}}
                                    ]
                                }},
                                {"$unset": ["__mem__", "__mem_count__"]},
                            ]

                        if collection == "members":
                            # Only allow viewing own memberships
                            # Match against both _id and staff._id for compatibility
                            member_filter = {"$match": {
                                "$or": [
                                    {"_id": mem_bin},
                                    {"staff._id": mem_bin},
                                    {"memberId": mem_bin}
                                ]
                            }}
                            print(f"   Adding member filter: {member_filter}")
                            injected_stages.append(member_filter)
                        elif collection == "project":
                            print(f"   Adding membership join for project collection")
                            injected_stages.extend(_membership_join("_id"))
                        elif collection in ("workItem", "cycle", "module", "page"):
                            print(f"   Adding membership join for {collection} collection")
                            injected_stages.extend(_membership_join("project._id"))
                        elif collection == "projectState":
                            print(f"   Adding membership join for projectState collection")
                            injected_stages.extend(_membership_join("projectId"))
                        # Other collections: no-op
                    except ValueError as e:
                        # Invalid UUID format - log and skip member filter
                        print(f"⚠️  Invalid MEMBER_UUID format '{member_uuid}': {e}")
                        print(f"   Skipping member filter for {collection}")
                    except Exception as e:
                        # Other errors - log and skip member filter
                        print(f"⚠️  Error applying member filter for {collection}: {e}")

                # Execute aggregation - Motor uses persistent connection pool
                db = self.client[database]
                coll = db[collection]
                effective_pipeline = (injected_stages + pipeline) if injected_stages else pipeline
                
                if injected_stages:
                    print(f"\n🔧 RBAC Pipeline Injection for '{collection}':")
                    print(f"   Injected stages: {len(injected_stages)}")
                    for i, stage in enumerate(injected_stages):
                        print(f"   Stage {i}: {list(stage.keys())}")
                    print(f"   Original pipeline stages: {len(pipeline)}")
                    print(f"   Total pipeline stages: {len(effective_pipeline)}\n")
                
                # DEBUG: Before filtering, let's see if ANY documents exist
                if injected_stages and collection == "project":
                    print(f"\n🔬 DEBUG: Checking what lookup returns BEFORE filtering...")
                    debug_pipeline = [
                        {"$lookup": {
                            "from": "members",
                            "localField": "_id",
                            "foreignField": "project._id",
                            "as": "__mem__",
                        }},
                        {"$addFields": {
                            "__mem_count__": {"$size": "$__mem__"},
                            "__mem_data__": {
                                "$map": {
                                    "input": {"$slice": ["$__mem__", 3]},
                                    "as": "m",
                                    "in": {
                                        "_id": "$$m._id",
                                        "memberId": "$$m.memberId",
                                        "staff_id": "$$m.staff._id",
                                        "name": "$$m.name"
                                    }
                                }
                            }
                        }},
                        {"$project": {
                            "name": 1,
                            "__mem_count__": 1,
                            "__mem_data__": 1
                        }},
                        {"$limit": 10}
                    ]
                    debug_cursor = coll.aggregate(debug_pipeline)
                    debug_results = await debug_cursor.to_list(length=None)
                    print(f"   Found {len(debug_results)} total projects (showing first 10):")
                    for proj in debug_results:
                        print(f"      - {proj.get('name')}: {proj.get('__mem_count__')} members")
                        if proj.get('__mem_data__'):
                            for m in proj.get('__mem_data__', [])[:2]:
                                print(f"        Member: {m.get('name')}")
                                print(f"          _id: {m.get('_id')}")
                                print(f"          memberId: {m.get('memberId')}")
                                print(f"          staff._id: {m.get('staff_id')}")
                                if m.get('_id') == mem_bin or m.get('memberId') == mem_bin or m.get('staff_id') == mem_bin:
                                    print(f"          ✓✓✓ MATCH FOUND! ✓✓✓")
                    print(f"\n   Target UUID = {mem_bin}\n")
                
                cursor = coll.aggregate(effective_pipeline)
                results = await cursor.to_list(length=None)
                
                print(f"📊 Query Results: {len(results)} documents returned for collection '{collection}'")
                
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
