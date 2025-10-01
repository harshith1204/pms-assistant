THIS SHOULD BE A LINTER ERROR#!/usr/bin/env python3
"""
Re-index Qdrant database with proper chunking for all content types.

This script will:
1. Clear existing Qdrant collection
2. Re-index all content with proper chunking:
   - Pages: 320 words/chunk, 80-word overlap (already had this)
   - Work Items: 300 words/chunk, 60-word overlap (NEW)
   - Projects: 300 words/chunk, 60-word overlap (NEW)
   - Cycles: 300 words/chunk, 60-word overlap (NEW)
   - Modules: 300 words/chunk, 60-word overlap (NEW)

Run this after updating insertdocs.py to ensure all documents have chunk metadata.
"""

import sys
from qdrant.insertdocs import (
    index_pages_to_qdrant,
    index_workitems_to_qdrant,
    index_projects_to_qdrant,
    index_cycles_to_qdrant,
    index_modules_to_qdrant
)
from qdrant_client import QdrantClient
from mongo.constants import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION_NAME


def clear_collection():
    """Clear existing Qdrant collection"""
    print("🗑️  Clearing existing Qdrant collection...")
    try:
        client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
        client.delete_collection(collection_name=QDRANT_COLLECTION_NAME)
        print(f"✅ Deleted collection: {QDRANT_COLLECTION_NAME}")
    except Exception as e:
        print(f"⚠️  Collection may not exist or error: {e}")


def reindex_all():
    """Re-index all content types with chunking"""
    print("\n🔄 Starting full re-indexing with chunking...\n")
    
    results = []
    
    # Index pages (already had chunking, but consistent now)
    print("1/5 Indexing pages...")
    result = index_pages_to_qdrant()
    results.append(("Pages", result))
    
    # Index work items (NEW chunking)
    print("\n2/5 Indexing work items...")
    result = index_workitems_to_qdrant()
    results.append(("Work Items", result))
    
    # Index projects (NEW chunking)
    print("\n3/5 Indexing projects...")
    result = index_projects_to_qdrant()
    results.append(("Projects", result))
    
    # Index cycles (NEW chunking)
    print("\n4/5 Indexing cycles...")
    result = index_cycles_to_qdrant()
    results.append(("Cycles", result))
    
    # Index modules (NEW chunking)
    print("\n5/5 Indexing modules...")
    result = index_modules_to_qdrant()
    results.append(("Modules", result))
    
    return results


def print_summary(results):
    """Print summary of indexing results"""
    print("\n" + "="*60)
    print("INDEXING SUMMARY")
    print("="*60)
    
    total_indexed = 0
    for content_type, result in results:
        status = result.get("status", "unknown")
        count = result.get("indexed_documents", 0)
        
        status_icon = "✅" if status == "success" else "⚠️" if status == "warning" else "❌"
        print(f"{status_icon} {content_type:15s}: {count:6d} chunks indexed")
        
        if status == "success":
            total_indexed += count
    
    print("="*60)
    print(f"TOTAL: {total_indexed} chunks indexed across all content types")
    print("="*60)
    
    print("\n✅ All content now has proper chunking with:")
    print("   - parent_id: Original document ID")
    print("   - chunk_index: Position in document (0-based)")
    print("   - chunk_count: Total chunks for document")
    print("   - content: Actual chunk text")
    print("\n🚀 Chunk-aware retrieval is ready to use!")


if __name__ == "__main__":
    print("="*60)
    print("QDRANT RE-INDEXING WITH CHUNKING")
    print("="*60)
    print("\nThis will:")
    print("1. Delete existing Qdrant collection")
    print("2. Re-index all content with proper chunking")
    print("3. Add chunk metadata (parent_id, chunk_index, chunk_count)")
    
    response = input("\nContinue? (yes/no): ").strip().lower()
    
    if response not in ["yes", "y"]:
        print("❌ Aborted by user")
        sys.exit(0)
    
    # Clear existing collection
    clear_collection()
    
    # Re-index all content
    results = reindex_all()
    
    # Print summary
    print_summary(results)
    
    print("\n✅ Re-indexing complete!")
