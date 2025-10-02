#!/usr/bin/env python3
"""
Diagnostic script to check Qdrant collection status and identify chunking issues.
"""
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
import json

# Load environment variables
load_dotenv()
qdrant_api_key = os.getenv("QDRANT_API_KEY")
qdrant_url = os.getenv("QDRANT_URL")

# Connect to Qdrant
print("🔗 Connecting to Qdrant...")
qdrant_client = QdrantClient(
    url=qdrant_url,
    api_key=qdrant_api_key,
    timeout=60
)

COLLECTION_NAME = "pms_collection"

print(f"\n📊 Checking collection: {COLLECTION_NAME}")
print("=" * 60)

# 1. Get collection info
try:
    info = qdrant_client.get_collection(COLLECTION_NAME)
    print(f"\n✅ Collection exists!")
    print(f"   • Vectors count: {info.vectors_count}")
    print(f"   • Points count: {info.points_count}")
    print(f"   • Indexed vectors count: {info.indexed_vectors_count}")
    print(f"   • Vector size: {info.config.params.vectors.size if info.config else 'N/A'}")
    
    # Check HNSW config
    if hasattr(info.config, 'hnsw_config') and info.config.hnsw_config:
        print(f"\n🔧 HNSW Index Configuration:")
        print(f"   • M (edges per node): {info.config.hnsw_config.m}")
        print(f"   • EF construct: {info.config.hnsw_config.ef_construct}")
    
    # Check optimizer config
    if hasattr(info.config, 'optimizer_config') and info.config.optimizer_config:
        print(f"\n⚙️  Optimizer Configuration:")
        print(f"   • Indexing threshold: {info.config.optimizer_config.indexing_threshold}")
        if info.config.optimizer_config.indexing_threshold > 0:
            print(f"   ⚠️  WARNING: Indexing threshold is {info.config.optimizer_config.indexing_threshold}")
            print(f"      HNSW index will only build after {info.config.optimizer_config.indexing_threshold} vectors")
            print(f"      Current vectors: {info.vectors_count}")
            if info.vectors_count < info.config.optimizer_config.indexing_threshold:
                print(f"   ❌ Indexed vectors count is 0 because threshold not reached!")
                print(f"      Need {info.config.optimizer_config.indexing_threshold - info.vectors_count} more vectors")
    
    # Check payload schema (indexes)
    if info.payload_schema:
        print(f"\n📇 Payload Schema (Indexes):")
        for field, schema_type in info.payload_schema.items():
            print(f"   • {field}: {schema_type}")
    else:
        print(f"\n⚠️  No payload indexes found!")
        
except Exception as e:
    print(f"❌ Error getting collection info: {e}")
    exit(1)

# 2. Sample some points to check chunking
print(f"\n🔍 Sampling points to check chunking...")
print("=" * 60)

try:
    # Scroll through points
    results, next_offset = qdrant_client.scroll(
        collection_name=COLLECTION_NAME,
        limit=10,
        with_payload=True,
        with_vectors=False
    )
    
    if not results:
        print("⚠️  No points found in collection!")
    else:
        print(f"\nFound {len(results)} sample points:\n")
        
        chunk_stats = {
            "single_chunk": 0,
            "multi_chunk": 0,
            "by_content_type": {}
        }
        
        for i, point in enumerate(results, 1):
            payload = point.payload or {}
            content_type = payload.get("content_type", "unknown")
            chunk_index = payload.get("chunk_index", 0)
            chunk_count = payload.get("chunk_count", 1)
            title = payload.get("title", "Untitled")
            
            # Update stats
            if chunk_count == 1:
                chunk_stats["single_chunk"] += 1
            else:
                chunk_stats["multi_chunk"] += 1
            
            if content_type not in chunk_stats["by_content_type"]:
                chunk_stats["by_content_type"][content_type] = {
                    "single": 0,
                    "multi": 0,
                    "total_chunks": []
                }
            
            if chunk_count == 1:
                chunk_stats["by_content_type"][content_type]["single"] += 1
            else:
                chunk_stats["by_content_type"][content_type]["multi"] += 1
            
            chunk_stats["by_content_type"][content_type]["total_chunks"].append(chunk_count)
            
            print(f"[{i}] {content_type.upper()}: {title[:50]}...")
            print(f"    Chunk: {chunk_index + 1}/{chunk_count}")
            print(f"    Mongo ID: {payload.get('mongo_id', 'N/A')}")
            
            # Show content length
            content = payload.get("content", "")
            word_count = len(content.split()) if content else 0
            print(f"    Content: {word_count} words, {len(content)} chars")
            print()
        
        # Print statistics
        print("\n📈 CHUNKING STATISTICS (from sample):")
        print("=" * 60)
        print(f"Single-chunk documents: {chunk_stats['single_chunk']}")
        print(f"Multi-chunk documents: {chunk_stats['multi_chunk']}")
        
        print(f"\nBy content type:")
        for ct, stats in chunk_stats["by_content_type"].items():
            avg_chunks = sum(stats["total_chunks"]) / len(stats["total_chunks"]) if stats["total_chunks"] else 0
            print(f"  • {ct}:")
            print(f"      - Single-chunk: {stats['single']}")
            print(f"      - Multi-chunk: {stats['multi']}")
            print(f"      - Avg chunks: {avg_chunks:.1f}")
        
except Exception as e:
    print(f"❌ Error sampling points: {e}")

# 3. Check for specific work item (if you have an ID)
print(f"\n🔎 Searching for work items with SIMPO-2462...")
print("=" * 60)

try:
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    
    search_results = qdrant_client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(
            must=[
                FieldCondition(key="displayBugNo", match=MatchValue(value="SIMPO-2462"))
            ]
        ),
        limit=10,
        with_payload=True,
        with_vectors=False
    )
    
    if search_results and search_results[0]:
        print(f"\n✅ Found {len(search_results[0])} point(s) with SIMPO-2462:")
        for point in search_results[0]:
            payload = point.payload
            print(f"\nPoint ID: {point.id}")
            print(f"  • Title: {payload.get('title', 'N/A')}")
            print(f"  • Content type: {payload.get('content_type', 'N/A')}")
            print(f"  • Chunk: {payload.get('chunk_index', 0) + 1}/{payload.get('chunk_count', 1)}")
            print(f"  • Mongo ID: {payload.get('mongo_id', 'N/A')}")
            print(f"  • Parent ID: {payload.get('parent_id', 'N/A')}")
            
            # Show content
            content = payload.get("content", "")
            print(f"  • Content ({len(content.split())} words):")
            print(f"    {content[:200]}...")
    else:
        print("⚠️  No points found with displayBugNo=SIMPO-2462")
        
except Exception as e:
    print(f"⚠️  Could not search for specific work item: {e}")

# 4. Check total counts by content type
print(f"\n📊 Total counts by content type...")
print("=" * 60)

try:
    for content_type in ["page", "work_item", "project", "cycle", "module"]:
        count_results = qdrant_client.count(
            collection_name=COLLECTION_NAME,
            count_filter=Filter(
                must=[
                    FieldCondition(key="content_type", match=MatchValue(value=content_type))
                ]
            )
        )
        print(f"  • {content_type}: {count_results.count} points")
        
except Exception as e:
    print(f"⚠️  Could not count by content type: {e}")

print("\n" + "=" * 60)
print("✅ Diagnostic complete!")
