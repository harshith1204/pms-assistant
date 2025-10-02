#!/usr/bin/env python3
"""
Fix indexed_vectors_count being 0 by updating collection configuration.

This script updates the Qdrant collection to enable HNSW indexing immediately.
"""
import os
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.models import OptimizersConfigDiff

# Load environment variables
load_dotenv()
qdrant_api_key = os.getenv("QDRANT_API_KEY")
qdrant_url = os.getenv("QDRANT_URL")

print("=" * 80)
print("🔧 FIXING INDEXED VECTORS COUNT")
print("=" * 80)

# Connect to Qdrant
print("\n🔗 Connecting to Qdrant...")
qdrant_client = QdrantClient(
    url=qdrant_url,
    api_key=qdrant_api_key,
    timeout=60
)

COLLECTION_NAME = "pms_collection"

print(f"\n📊 Checking collection: {COLLECTION_NAME}")

# 1. Get current status
try:
    info = qdrant_client.get_collection(COLLECTION_NAME)
    print(f"\n✅ Current Status:")
    print(f"   • Vectors count: {info.vectors_count}")
    print(f"   • Indexed vectors count: {info.indexed_vectors_count}")
    
    if hasattr(info.config, 'optimizer_config') and info.config.optimizer_config:
        threshold = info.config.optimizer_config.indexing_threshold
        print(f"   • Indexing threshold: {threshold}")
        
        if threshold > 0:
            print(f"\n⚠️  PROBLEM FOUND:")
            print(f"   The indexing threshold is {threshold}, meaning HNSW index won't build")
            print(f"   until you have {threshold} vectors.")
            print(f"   You currently have {info.vectors_count} vectors.")
            print(f"\n🔧 APPLYING FIX...")
        else:
            print(f"\n✅ Indexing threshold is already 0 - configuration is correct!")
            print(f"   If indexed_vectors_count is still 0, the index might be building...")
            print(f"   This can take a few seconds for large collections.")
            exit(0)
    
except Exception as e:
    print(f"❌ Error getting collection info: {e}")
    exit(1)

# 2. Update the collection configuration
try:
    print(f"\n🔄 Updating collection configuration to enable immediate indexing...")
    
    qdrant_client.update_collection(
        collection_name=COLLECTION_NAME,
        optimizers_config=OptimizersConfigDiff(
            indexing_threshold=0  # Start indexing immediately
        )
    )
    
    print(f"✅ Collection configuration updated!")
    
except Exception as e:
    print(f"❌ Error updating collection: {e}")
    exit(1)

# 3. Check updated status
try:
    import time
    print(f"\n⏳ Waiting 5 seconds for indexing to start...")
    time.sleep(5)
    
    info = qdrant_client.get_collection(COLLECTION_NAME)
    print(f"\n📊 Updated Status:")
    print(f"   • Vectors count: {info.vectors_count}")
    print(f"   • Indexed vectors count: {info.indexed_vectors_count}")
    
    if hasattr(info.config, 'optimizer_config') and info.config.optimizer_config:
        print(f"   • Indexing threshold: {info.config.optimizer_config.indexing_threshold}")
    
    if info.indexed_vectors_count > 0:
        print(f"\n✅ SUCCESS! HNSW indexing is now active!")
        print(f"   {info.indexed_vectors_count} vectors are indexed")
    elif info.vectors_count > 0:
        print(f"\n⏳ Indexing is in progress...")
        print(f"   Give it a few more seconds and check again with:")
        print(f"   python3 check_qdrant_status.py")
    else:
        print(f"\n⚠️  No vectors found in collection")
        print(f"   Run: python3 qdrant/insertdocs.py")
    
except Exception as e:
    print(f"⚠️  Could not verify: {e}")

print("\n" + "=" * 80)
print("✅ Fix applied!")
print("=" * 80)
print(f"\nNext steps:")
print(f"1. Check status: python3 check_qdrant_status.py")
print(f"2. If still 0, indexing might be in progress (wait a minute)")
print(f"3. For new collections, indexing will now start immediately")
print("=" * 80)
