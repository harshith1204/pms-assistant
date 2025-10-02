#!/usr/bin/env python3
"""
Re-index Qdrant with detailed chunking statistics.

This script provides visibility into:
1. How many documents are being chunked
2. Average chunks per document
3. Distribution of chunk counts
4. Which documents produce the most chunks
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from collections import defaultdict
from qdrant.dbconnection import (
    page_collection, workitem_collection, project_collection,
    cycle_collection, module_collection, qdrant_client, QDRANT_COLLECTION
)
from qdrant.insertdocs import (
    ensure_collection_with_hybrid, normalize_mongo_id, parse_editorjs_blocks,
    point_id_from_seed, upload_in_batches, embedder
)
from qdrant_client.http.models import PointStruct

# Import chunking functions
try:
    from qdrant.chunking_config import chunk_text_configurable, ACTIVE_CONFIG
    USE_CONFIGURABLE = True
    print("✅ Using configurable chunking from chunking_config.py")
except ImportError:
    from qdrant.insertdocs import chunk_text
    USE_CONFIGURABLE = False
    print("ℹ️  Using default chunking from insertdocs.py")

class ChunkingStats:
    """Track chunking statistics during indexing."""
    
    def __init__(self):
        self.by_type = defaultdict(lambda: {
            "total_docs": 0,
            "single_chunk": 0,
            "multi_chunk": 0,
            "total_chunks": 0,
            "chunk_distribution": defaultdict(int),  # chunk_count -> count
            "total_words": 0,
            "max_chunks": 0,
            "max_chunks_doc": None,
        })
    
    def record(self, content_type: str, doc_id: str, title: str, chunk_count: int, word_count: int):
        """Record chunking info for a document."""
        stats = self.by_type[content_type]
        stats["total_docs"] += 1
        stats["total_chunks"] += chunk_count
        stats["total_words"] += word_count
        stats["chunk_distribution"][chunk_count] += 1
        
        if chunk_count == 1:
            stats["single_chunk"] += 1
        else:
            stats["multi_chunk"] += 1
        
        if chunk_count > stats["max_chunks"]:
            stats["max_chunks"] = chunk_count
            stats["max_chunks_doc"] = (doc_id, title)
    
    def print_summary(self):
        """Print comprehensive chunking statistics."""
        print("\n" + "=" * 80)
        print("📊 CHUNKING STATISTICS SUMMARY")
        print("=" * 80)
        
        total_docs = 0
        total_chunks = 0
        
        for content_type, stats in sorted(self.by_type.items()):
            total_docs += stats["total_docs"]
            total_chunks += stats["total_chunks"]
            
            print(f"\n▸ {content_type.upper()}")
            print(f"  Documents: {stats['total_docs']}")
            print(f"  Total chunks: {stats['total_chunks']}")
            print(f"  Avg chunks/doc: {stats['total_chunks'] / stats['total_docs']:.2f}")
            print(f"  Avg words/doc: {stats['total_words'] / stats['total_docs']:.0f}")
            print(f"  Single-chunk: {stats['single_chunk']} ({stats['single_chunk']/stats['total_docs']*100:.1f}%)")
            print(f"  Multi-chunk: {stats['multi_chunk']} ({stats['multi_chunk']/stats['total_docs']*100:.1f}%)")
            
            if stats["max_chunks"] > 1:
                doc_id, title = stats["max_chunks_doc"]
                print(f"  Max chunks: {stats['max_chunks']} (in '{title[:50]}...')")
            
            # Show distribution for multi-chunk documents
            if stats["multi_chunk"] > 0:
                print(f"  Chunk distribution:")
                for chunk_count in sorted([k for k in stats["chunk_distribution"].keys() if k > 1]):
                    count = stats["chunk_distribution"][chunk_count]
                    print(f"    - {chunk_count} chunks: {count} docs")
        
        print(f"\n{'─' * 80}")
        print(f"📈 OVERALL TOTALS:")
        print(f"  Total documents: {total_docs}")
        print(f"  Total chunks (points): {total_chunks}")
        print(f"  Average chunks per document: {total_chunks / total_docs:.2f}")
        print(f"  Chunking ratio: {(total_chunks / total_docs - 1) * 100:.1f}% expansion")
        print("=" * 80 + "\n")


def index_with_stats():
    """Re-index all collections with detailed statistics."""
    
    stats = ChunkingStats()
    
    print("🚀 Starting Qdrant re-indexing with statistics...")
    
    if USE_CONFIGURABLE:
        print("\n📋 Active Chunking Configuration:")
        for content_type, config in ACTIVE_CONFIG.items():
            print(f"  • {content_type}: {config['max_words']} words/chunk, "
                  f"{config['overlap_words']} overlap, "
                  f"min {config.get('min_words_to_chunk', config['max_words'])} to chunk")
    
    # Ensure collection exists
    ensure_collection_with_hybrid(QDRANT_COLLECTION, vector_size=768)
    
    # 1. Index Work Items
    print("\n" + "─" * 80)
    print("🔄 Indexing WORK ITEMS...")
    print("─" * 80)
    
    documents = workitem_collection.find({}, {
        "_id": 1, "title": 1, "description": 1, "displayBugNo": 1,
        "priority": 1, "status": 1, "state": 1, "assignee": 1,
        "createdAt": 1, "updatedAt": 1, "createdTimeStamp": 1, "updatedTimeStamp": 1,
        "project": 1, "cycle": 1, "modules": 1, "business": 1, "createdBy": 1
    })
    
    points = []
    for doc in documents:
        mongo_id = normalize_mongo_id(doc["_id"])
        combined_text = " ".join(filter(None, [doc.get("title", ""), doc.get("description", "")])).strip()
        if not combined_text:
            continue
        
        # Extract metadata
        metadata = {
            "displayBugNo": doc.get("displayBugNo"),
            "priority": doc.get("priority"),
            "status": doc.get("status"),
            "createdAt": doc.get("createdAt") or doc.get("createdTimeStamp"),
            "updatedAt": doc.get("updatedAt") or doc.get("updatedTimeStamp"),
        }
        
        if doc.get("state") and isinstance(doc["state"], dict):
            metadata["state_name"] = doc["state"].get("name")
        if doc.get("project") and isinstance(doc["project"], dict):
            metadata["project_name"] = doc["project"].get("name")
            metadata["project_id"] = normalize_mongo_id(doc["project"].get("_id")) if doc["project"].get("_id") else None
        if doc.get("cycle") and isinstance(doc["cycle"], dict):
            metadata["cycle_name"] = doc["cycle"].get("name")
        if doc.get("modules") and isinstance(doc["modules"], dict):
            metadata["module_name"] = doc["modules"].get("name")
        if doc.get("business") and isinstance(doc["business"], dict):
            metadata["business_name"] = doc["business"].get("name")
        
        # Handle assignee
        if doc.get("assignee"):
            assignee = doc["assignee"]
            if isinstance(assignee, list) and assignee and isinstance(assignee[0], dict):
                metadata["assignee_name"] = assignee[0].get("name")
            elif isinstance(assignee, dict):
                metadata["assignee_name"] = assignee.get("name")
        
        if doc.get("createdBy") and isinstance(doc["createdBy"], dict):
            metadata["created_by_name"] = doc["createdBy"].get("name")
        
        # Chunk text
        if USE_CONFIGURABLE:
            chunks = chunk_text_configurable(combined_text, "work_item")
        else:
            chunks = chunk_text(combined_text, max_words=300, overlap_words=60)
        
        if not chunks:
            chunks = [combined_text]
        
        # Record stats
        word_count = len(combined_text.split())
        stats.record("work_item", mongo_id, doc.get("title", ""), len(chunks), word_count)
        
        # Create points
        for idx, chunk in enumerate(chunks):
            vector = embedder.encode(chunk).tolist()
            payload = {
                "mongo_id": mongo_id,
                "parent_id": mongo_id,
                "chunk_index": idx,
                "chunk_count": len(chunks),
                "title": doc.get("title", ""),
                "content": chunk,
                "full_text": f"{doc.get('title', '')} {chunk}".strip(),
                "content_type": "work_item"
            }
            payload.update({k: v for k, v in metadata.items() if v is not None})
            
            point = PointStruct(
                id=point_id_from_seed(f"{mongo_id}/work_item/{idx}"),
                vector=vector,
                payload=payload
            )
            points.append(point)
    
    if points:
        total = upload_in_batches(points, QDRANT_COLLECTION)
        print(f"✅ Indexed {total} work item chunks from {stats.by_type['work_item']['total_docs']} documents")
    
    # 2. Index Pages (simplified for brevity - full implementation similar to above)
    print("\n" + "─" * 80)
    print("🔄 Indexing PAGES...")
    print("─" * 80)
    
    documents = page_collection.find({}, {
        "_id": 1, "content": 1, "title": 1, "visibility": 1, "isFavourite": 1,
        "createdAt": 1, "updatedAt": 1, "createdTimeStamp": 1, "updatedTimeStamp": 1,
        "project": 1, "business": 1, "createdBy": 1
    })
    
    points = []
    for doc in documents:
        mongo_id = normalize_mongo_id(doc["_id"])
        title = doc.get("title", "")
        blocks, combined_text = parse_editorjs_blocks(doc.get("content", ""))
        if not blocks and not combined_text:
            continue
        
        # Metadata
        metadata = {
            "visibility": doc.get("visibility"),
            "isFavourite": doc.get("isFavourite", False),
            "createdAt": doc.get("createdAt") or doc.get("createdTimeStamp"),
            "updatedAt": doc.get("updatedAt") or doc.get("updatedTimeStamp"),
        }
        
        if doc.get("project") and isinstance(doc["project"], dict):
            metadata["project_name"] = doc["project"].get("name")
            metadata["project_id"] = normalize_mongo_id(doc["project"].get("_id")) if doc["project"].get("_id") else None
        if doc.get("business") and isinstance(doc["business"], dict):
            metadata["business_name"] = doc["business"].get("name")
        if doc.get("createdBy") and isinstance(doc["createdBy"], dict):
            metadata["created_by_name"] = doc["createdBy"].get("name")
        
        # Chunk
        if USE_CONFIGURABLE:
            chunks = chunk_text_configurable(combined_text, "page")
        else:
            chunks = chunk_text(combined_text, max_words=320, overlap_words=80)
        
        if not chunks:
            chunks = [combined_text]
        
        # Record stats
        word_count = len(combined_text.split())
        stats.record("page", mongo_id, title, len(chunks), word_count)
        
        # Create points
        for idx, chunk in enumerate(chunks):
            vector = embedder.encode(chunk).tolist()
            payload = {
                "mongo_id": mongo_id,
                "parent_id": mongo_id,
                "chunk_index": idx,
                "chunk_count": len(chunks),
                "title": title,
                "content": chunk,
                "full_text": f"{title} {chunk}".strip(),
                "content_type": "page"
            }
            payload.update({k: v for k, v in metadata.items() if v is not None})
            
            point = PointStruct(
                id=point_id_from_seed(f"{mongo_id}/page/{idx}"),
                vector=vector,
                payload=payload
            )
            points.append(point)
    
    if points:
        total = upload_in_batches(points, QDRANT_COLLECTION)
        print(f"✅ Indexed {total} page chunks from {stats.by_type['page']['total_docs']} documents")
    
    # Note: Projects, cycles, modules indexing omitted for brevity
    # Add them similarly if needed
    
    # Print final statistics
    stats.print_summary()
    
    print("\n✅ Re-indexing complete with statistics!")


if __name__ == "__main__":
    index_with_stats()
