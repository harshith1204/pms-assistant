import os
import sys
import json
import uuid
from itertools import islice
from bson.binary import Binary
from bson.objectid import ObjectId
from qdrant_client.http.models import PointStruct, PayloadSchemaType, Distance, VectorParams
from sentence_transformers import SentenceTransformer
from collections import defaultdict

# Add the parent directory to sys.path so we can import from qdrant
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qdrant.dbconnection import (
    page_collection,
    workitem_collection,
    cycle_collection,
    module_collection,
    project_collection,
    qdrant_client,
    QDRANT_COLLECTION
)
from dotenv import load_dotenv
from huggingface_hub import login

# ------------------ Setup ------------------

# Load .env file and authenticate HuggingFace
load_dotenv()
hf_token = os.getenv("HuggingFace_API_KEY")
login(hf_token)

# Load embedding model once
embedder = SentenceTransformer("google/embeddinggemma-300m")

# ------------------ Chunking Statistics ------------------

class ChunkingStats:
    """Track and display chunking statistics during indexing."""
    
    def __init__(self):
        self.by_type = defaultdict(lambda: {
            "total_docs": 0,
            "single_chunk": 0,
            "multi_chunk": 0,
            "total_chunks": 0,
            "chunk_distribution": defaultdict(int),
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
            stats["max_chunks_doc"] = (doc_id, title[:50])
    
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
            
            if stats["total_docs"] == 0:
                continue
            
            print(f"\n▸ {content_type.upper()}")
            print(f"  Documents: {stats['total_docs']}")
            print(f"  Total chunks: {stats['total_chunks']}")
            print(f"  Avg chunks/doc: {stats['total_chunks'] / stats['total_docs']:.2f}")
            print(f"  Avg words/doc: {stats['total_words'] / stats['total_docs']:.0f}")
            print(f"  Single-chunk: {stats['single_chunk']} ({stats['single_chunk']/stats['total_docs']*100:.1f}%)")
            print(f"  Multi-chunk: {stats['multi_chunk']} ({stats['multi_chunk']/stats['total_docs']*100:.1f}%)")
            
            if stats["max_chunks"] > 1:
                doc_id, title = stats["max_chunks_doc"]
                print(f"  Max chunks: {stats['max_chunks']} (in '{title}...')")
            
            # Show distribution for multi-chunk documents
            if stats["multi_chunk"] > 0:
                print(f"  Chunk distribution:")
                multi_chunks = [k for k in stats["chunk_distribution"].keys() if k > 1]
                for chunk_count in sorted(multi_chunks)[:5]:  # Show top 5
                    count = stats["chunk_distribution"][chunk_count]
                    print(f"    - {chunk_count} chunks: {count} docs")
        
        if total_docs > 0:
            print(f"\n{'─' * 80}")
            print(f"📈 OVERALL TOTALS:")
            print(f"  Total documents: {total_docs}")
            print(f"  Total chunks (points): {total_chunks}")
            print(f"  Average chunks per document: {total_chunks / total_docs:.2f}")
            print(f"  Chunking expansion: {(total_chunks / total_docs - 1) * 100:.1f}%")
        print("=" * 80 + "\n")

# Global stats instance
_stats = ChunkingStats()

# ------------------ Helpers ------------------

def ensure_collection_with_hybrid(collection_name: str, vector_size: int = 768):
    """Ensure Qdrant collection exists with dense vectors and text indexes for hybrid search.

    - Creates collection if missing with cosine distance and specified vector size
    - Ensures payload indexes for keyword and text fields used by our tools
    """
    try:
        existing = [col.name for col in qdrant_client.get_collections().collections]
        if collection_name not in existing:
            print(f"ℹ️ Creating Qdrant collection '{collection_name}' with vector_size={vector_size}...")
            # Create basic dense vector collection; sparse/text search uses payload text indexes
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            print(f"✅ Collection '{collection_name}' created")

        # Ensure keyword and text payload indexes exist (idempotent)
        try:
            qdrant_client.create_payload_index(
                collection_name=collection_name,
                field_name="content_type",
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception as e:
            if "already exists" not in str(e):
                print(f"⚠️ Failed to ensure index on 'content_type': {e}")

        for text_field in ["title", "full_text"]:
            try:
                qdrant_client.create_payload_index(
                    collection_name=collection_name,
                    field_name=text_field,
                    field_schema=PayloadSchemaType.TEXT,
                )
            except Exception as e:
                if "already exists" not in str(e):
                    print(f"⚠️ Failed to ensure text index on '{text_field}': {e}")
    except Exception as e:
        print(f"❌ Error ensuring collection '{collection_name}': {e}")

def normalize_mongo_id(mongo_id) -> str:
    """Convert Mongo _id (ObjectId or Binary UUID) into a safe string."""
    if isinstance(mongo_id, ObjectId):
        return str(mongo_id)
    elif isinstance(mongo_id, Binary) and mongo_id.subtype == 3:
        return str(uuid.UUID(bytes=mongo_id))
    return str(mongo_id)

def parse_editorjs_blocks(content_str: str):
    """Extract all blocks and combined text for embedding."""
    if not content_str or not content_str.strip():
        return [], ""
    try:
        content_json = json.loads(content_str)
        blocks = content_json.get("blocks", [])
        block_texts = [
            (block.get("data") or {}).get("text", "").strip()
            for block in blocks
            if (block.get("data") or {}).get("text", "").strip()
        ]
        combined_text = " ".join(block_texts).strip()
        return blocks, combined_text
    except Exception as e:
        print(f"⚠️ Failed to parse content: {e}")
        return [], ""

def point_id_from_seed(seed: str) -> str:
    """Create a deterministic UUID from a seed string for Qdrant point IDs."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))

# ------------------ Chunking Configuration ------------------

# Chunking settings per content type
# Adjust these values to control chunking behavior
CHUNKING_CONFIG = {
    "page": {
        "max_words": 320,
        "overlap_words": 80,
        "min_words_to_chunk": 320,  # Only chunk if text is longer than this
    },
    "work_item": {
        "max_words": 300,
        "overlap_words": 60,
        "min_words_to_chunk": 300,
    },
    "project": {
        "max_words": 300,
        "overlap_words": 60,
        "min_words_to_chunk": 300,
    },
    "cycle": {
        "max_words": 300,
        "overlap_words": 60,
        "min_words_to_chunk": 300,
    },
    "module": {
        "max_words": 300,
        "overlap_words": 60,
        "min_words_to_chunk": 300,
    },
}

# For more aggressive chunking (more multi-chunk documents), use:
# CHUNKING_CONFIG = {
#     "page": {"max_words": 200, "overlap_words": 40, "min_words_to_chunk": 100},
#     "work_item": {"max_words": 150, "overlap_words": 30, "min_words_to_chunk": 80},
#     "project": {"max_words": 150, "overlap_words": 30, "min_words_to_chunk": 80},
#     "cycle": {"max_words": 150, "overlap_words": 30, "min_words_to_chunk": 80},
#     "module": {"max_words": 150, "overlap_words": 30, "min_words_to_chunk": 80},
# }

def chunk_text(text: str, max_words: int = 300, overlap_words: int = 60, min_words_to_chunk: int = None):
    """Split long text into overlapping word chunks suitable for embeddings.

    Args:
        text: Input text to chunk.
        max_words: Target words per chunk.
        overlap_words: Overlap words between consecutive chunks.
        min_words_to_chunk: Minimum words needed to trigger chunking (default: max_words).

    Returns:
        List of chunk strings.
    """
    if not text:
        return []
    
    words = text.split()
    min_threshold = min_words_to_chunk if min_words_to_chunk is not None else max_words
    
    # Don't chunk if below minimum threshold
    if len(words) <= min_threshold:
        return [text]
    
    chunks = []
    step = max(1, max_words - overlap_words)
    for start in range(0, len(words), step):
        end = min(start + max_words, len(words))
        chunk = " ".join(words[start:end]).strip()
        if chunk:
            chunks.append(chunk)
        if end == len(words):
            break
    return chunks

def get_chunks_for_content(text: str, content_type: str):
    """Get chunks for a specific content type using its configuration.
    
    Args:
        text: Text to chunk
        content_type: Type of content (page, work_item, etc.)
        
    Returns:
        List of chunk strings
    """
    config = CHUNKING_CONFIG.get(content_type, CHUNKING_CONFIG["work_item"])
    return chunk_text(
        text,
        max_words=config["max_words"],
        overlap_words=config["overlap_words"],
        min_words_to_chunk=config.get("min_words_to_chunk", config["max_words"])
    )

def batch_iterable(iterable, batch_size):
    """Yield successive batches from a list or iterable."""
    it = iter(iterable)
    while batch := list(islice(it, batch_size)):
        yield batch

def upload_in_batches(points, collection_name, batch_size=20):
    """Upload list of points to Qdrant in smaller batches with debug prints."""
    total_indexed = 0
    for batch in batch_iterable(points, batch_size):
        print(f"🔹 Uploading batch of {len(batch)} points to {collection_name}...")
        try:
            qdrant_client.upsert(collection_name=collection_name, points=batch)
            total_indexed += len(batch)
        except Exception as e:
            print(f"❌ Failed to upload batch: {e}")
    return total_indexed

# ------------------ Indexing Functions ------------------

def index_pages_to_qdrant():
    try:
        print("🔄 Indexing pages from MongoDB to Qdrant...")

        # Ensure collection and indexes for hybrid search
        ensure_collection_with_hybrid(QDRANT_COLLECTION, vector_size=768)

        # Ensure payload index exists
        try:
            qdrant_client.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name="content_type",
                field_schema=PayloadSchemaType.KEYWORD
            )
            print("✅ Ensured payload index on 'content_type'")
        except Exception as e:
            if "already exists" in str(e):
                print("ℹ️ Index on 'content_type' already exists, skipping.")
            else:
                print(f"⚠️ Failed to ensure index: {e}")

        # Fetch pages with rich metadata
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

            # Extract metadata for filtering/grouping
            metadata = {
                "visibility": doc.get("visibility"),
                "isFavourite": doc.get("isFavourite", False),
                "createdAt": doc.get("createdAt") or doc.get("createdTimeStamp"),
                "updatedAt": doc.get("updatedAt") or doc.get("updatedTimeStamp"),
            }
            
            # Extract nested references
            if doc.get("project"):
                if isinstance(doc["project"], dict):
                    metadata["project_name"] = doc["project"].get("name")
                    metadata["project_id"] = normalize_mongo_id(doc["project"].get("_id")) if doc["project"].get("_id") else None
            
            if doc.get("business"):
                if isinstance(doc["business"], dict):
                    metadata["business_name"] = doc["business"].get("name")
            
            if doc.get("createdBy"):
                if isinstance(doc["createdBy"], dict):
                    metadata["created_by_name"] = doc["createdBy"].get("name")

            # Chunk combined text for better retrieval
            chunks = get_chunks_for_content(combined_text, "page")
            if not chunks:
                chunks = [combined_text]
            
            # Record statistics
            word_count = len(combined_text.split()) if combined_text else 0
            _stats.record("page", mongo_id, title, len(chunks), word_count)

            for idx, chunk in enumerate(chunks):
                vector = embedder.encode(chunk).tolist()
                payload = {
                    "mongo_id": mongo_id,
                    "parent_id": mongo_id,
                    "chunk_index": idx,
                    "chunk_count": len(chunks),
                    "title": title,
                    "content": chunk,
                    # Provide a concatenated text field for full-text search
                    "full_text": f"{title} {chunk}".strip(),
                    "content_type": "page"
                }
                # Add metadata, filtering out None values
                payload.update({k: v for k, v in metadata.items() if v is not None})
                
                point = PointStruct(
                    id=point_id_from_seed(f"{mongo_id}/page/{idx}"),
                    vector=vector,
                    payload=payload
                )
                points.append(point)

        if not points:
            print("⚠️ No valid pages to index.")
            return {"status": "warning", "message": "No valid pages found to index."}

        total_indexed = upload_in_batches(points, QDRANT_COLLECTION)
        print(f"✅ Indexed {total_indexed} pages to Qdrant.")
        return {"status": "success", "indexed_documents": total_indexed}

    except Exception as e:
        print(f"❌ Error during page indexing: {e}")
        return {"status": "error", "message": str(e)}

def index_workitems_to_qdrant():
    try:
        print("🔄 Indexing work items from MongoDB to Qdrant...")

        # Ensure collection and indexes for hybrid search
        ensure_collection_with_hybrid(QDRANT_COLLECTION, vector_size=768)

        # Ensure payload index exists
        try:
            qdrant_client.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name="content_type",
                field_schema=PayloadSchemaType.KEYWORD
            )
            print("✅ Ensured payload index on 'content_type'")
        except Exception as e:
            if "already exists" in str(e):
                print("ℹ️ Index on 'content_type' already exists, skipping.")
            else:
                print(f"⚠️ Failed to ensure index: {e}")

        # Fetch work items with rich metadata
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

            # Extract metadata for filtering/grouping
            metadata = {
                "displayBugNo": doc.get("displayBugNo"),
                "priority": doc.get("priority"),
                "status": doc.get("status"),
                "createdAt": doc.get("createdAt") or doc.get("createdTimeStamp"),
                "updatedAt": doc.get("updatedAt") or doc.get("updatedTimeStamp"),
            }
            
            # Extract nested references
            if doc.get("state"):
                if isinstance(doc["state"], dict):
                    metadata["state_name"] = doc["state"].get("name")
            
            if doc.get("project"):
                if isinstance(doc["project"], dict):
                    metadata["project_name"] = doc["project"].get("name")
                    metadata["project_id"] = normalize_mongo_id(doc["project"].get("_id")) if doc["project"].get("_id") else None
            
            if doc.get("cycle"):
                if isinstance(doc["cycle"], dict):
                    metadata["cycle_name"] = doc["cycle"].get("name")
            
            if doc.get("modules"):
                if isinstance(doc["modules"], dict):
                    metadata["module_name"] = doc["modules"].get("name")
            
            if doc.get("business"):
                if isinstance(doc["business"], dict):
                    metadata["business_name"] = doc["business"].get("name")
            
            # Handle assignee (can be array or single object)
            if doc.get("assignee"):
                assignee = doc["assignee"]
                if isinstance(assignee, list) and assignee and isinstance(assignee[0], dict):
                    metadata["assignee_name"] = assignee[0].get("name")
                elif isinstance(assignee, dict):
                    metadata["assignee_name"] = assignee.get("name")
            
            if doc.get("createdBy"):
                if isinstance(doc["createdBy"], dict):
                    metadata["created_by_name"] = doc["createdBy"].get("name")

            # Chunk work items with long descriptions (similar to pages)
            chunks = get_chunks_for_content(combined_text, "work_item")
            if not chunks:
                chunks = [combined_text]
            
            # Record statistics
            word_count = len(combined_text.split()) if combined_text else 0
            _stats.record("work_item", mongo_id, doc.get("title", ""), len(chunks), word_count)
            
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
                # Add metadata, filtering out None values
                payload.update({k: v for k, v in metadata.items() if v is not None})

                point = PointStruct(
                    id=point_id_from_seed(f"{mongo_id}/work_item/{idx}"),
                    vector=vector,
                    payload=payload
                )
                points.append(point)

        if not points:
            print("⚠️ No valid work items to index.")
            return {"status": "warning", "message": "No valid work items found to index."}

        total_indexed = upload_in_batches(points, QDRANT_COLLECTION)
        print(f"✅ Indexed {total_indexed} work items to Qdrant.")
        return {"status": "success", "indexed_documents": total_indexed}

    except Exception as e:
        print(f"❌ Error during work item indexing: {e}")
        return {"status": "error", "message": str(e)}

def index_projects_to_qdrant():
    try:
        print("🔄 Indexing projects to Qdrant...")

        ensure_collection_with_hybrid(QDRANT_COLLECTION, vector_size=768)

        documents = project_collection.find({}, {"_id": 1, "name": 1, "description": 1})
        points = []

        for doc in documents:
            mongo_id = normalize_mongo_id(doc["_id"])
            name = doc.get("name", "")
            description = (doc.get("description") or "").strip()
            combined_text = " ".join(filter(None, [name, description])).strip()
            if not combined_text:
                continue

            # Chunk projects with long descriptions
            chunks = get_chunks_for_content(combined_text, "project")
            if not chunks:
                chunks = [combined_text]
            
            # Record statistics
            word_count = len(combined_text.split()) if combined_text else 0
            _stats.record("project", mongo_id, name, len(chunks), word_count)
            
            for idx, chunk in enumerate(chunks):
                vector = embedder.encode(chunk).tolist()
                point = PointStruct(
                    id=point_id_from_seed(f"{mongo_id}/project/{idx}"),
                    vector=vector,
                    payload={
                        "mongo_id": mongo_id,
                        "parent_id": mongo_id,
                        "chunk_index": idx,
                        "chunk_count": len(chunks),
                        "title": name,
                        "content": chunk,
                        "full_text": f"{name} {chunk}".strip(),
                        "content_type": "project"
                    }
                )
                points.append(point)

        if not points:
            print("ℹ️ No projects with descriptions to index.")
            return {"status": "warning", "message": "No projects to index."}

        total_indexed = upload_in_batches(points, QDRANT_COLLECTION)
        print(f"✅ Indexed {total_indexed} projects to Qdrant.")
        return {"status": "success", "indexed_documents": total_indexed}
    except Exception as e:
        print(f"❌ Error during project indexing: {e}")
        return {"status": "error", "message": str(e)}

def index_cycles_to_qdrant():
    try:
        print("🔄 Indexing cycles to Qdrant...")

        ensure_collection_with_hybrid(QDRANT_COLLECTION, vector_size=768)

        documents = cycle_collection.find({}, {"_id": 1, "name": 1, "title": 1, "description": 1})
        points = []

        for doc in documents:
            mongo_id = normalize_mongo_id(doc["_id"])
            name = doc.get("name") or doc.get("title") or ""
            description = (doc.get("description") or "").strip()
            combined_text = " ".join(filter(None, [name, description])).strip()
            if not combined_text:
                continue

            # Chunk cycles with long descriptions
            chunks = get_chunks_for_content(combined_text, "cycle")
            if not chunks:
                chunks = [combined_text]
            
            # Record statistics
            word_count = len(combined_text.split()) if combined_text else 0
            _stats.record("cycle", mongo_id, name, len(chunks), word_count)
            
            for idx, chunk in enumerate(chunks):
                vector = embedder.encode(chunk).tolist()
                point = PointStruct(
                    id=point_id_from_seed(f"{mongo_id}/cycle/{idx}"),
                    vector=vector,
                    payload={
                        "mongo_id": mongo_id,
                        "parent_id": mongo_id,
                        "chunk_index": idx,
                        "chunk_count": len(chunks),
                        "title": name,
                        "content": chunk,
                        "full_text": f"{name} {chunk}".strip(),
                        "content_type": "cycle"
                    }
                )
                points.append(point)

        if not points:
            print("ℹ️ No cycles with descriptions to index.")
            return {"status": "warning", "message": "No cycles to index."}

        total_indexed = upload_in_batches(points, QDRANT_COLLECTION)
        print(f"✅ Indexed {total_indexed} cycles to Qdrant.")
        return {"status": "success", "indexed_documents": total_indexed}
    except Exception as e:
        print(f"❌ Error during cycle indexing: {e}")
        return {"status": "error", "message": str(e)}

def index_modules_to_qdrant():
    try:
        print("🔄 Indexing modules to Qdrant...")

        ensure_collection_with_hybrid(QDRANT_COLLECTION, vector_size=768)

        documents = module_collection.find({}, {"_id": 1, "name": 1, "title": 1, "description": 1})
        points = []

        for doc in documents:
            mongo_id = normalize_mongo_id(doc["_id"])
            name = doc.get("name") or doc.get("title") or ""
            description = (doc.get("description") or "").strip()
            combined_text = " ".join(filter(None, [name, description])).strip()
            if not combined_text:
                continue

            # Chunk modules with long descriptions
            chunks = get_chunks_for_content(combined_text, "module")
            if not chunks:
                chunks = [combined_text]
            
            # Record statistics
            word_count = len(combined_text.split()) if combined_text else 0
            _stats.record("module", mongo_id, name, len(chunks), word_count)
            
            for idx, chunk in enumerate(chunks):
                vector = embedder.encode(chunk).tolist()
                point = PointStruct(
                    id=point_id_from_seed(f"{mongo_id}/module/{idx}"),
                    vector=vector,
                    payload={
                        "mongo_id": mongo_id,
                        "parent_id": mongo_id,
                        "chunk_index": idx,
                        "chunk_count": len(chunks),
                        "title": name,
                        "content": chunk,
                        "full_text": f"{name} {chunk}".strip(),
                        "content_type": "module"
                    }
                )
                points.append(point)

        if not points:
            print("ℹ️ No modules with descriptions to index.")
            return {"status": "warning", "message": "No modules to index."}

        total_indexed = upload_in_batches(points, QDRANT_COLLECTION)
        print(f"✅ Indexed {total_indexed} modules to Qdrant.")
        return {"status": "success", "indexed_documents": total_indexed}
    except Exception as e:
        print(f"❌ Error during module indexing: {e}")
        return {"status": "error", "message": str(e)}

# ------------------ Usage ------------------
if __name__ == "__main__":
    print("=" * 80)
    print("🚀 STARTING QDRANT INDEXING WITH CONFIGURABLE CHUNKING")
    print("=" * 80)
    
    print("\n📋 Active Chunking Configuration:")
    for content_type, config in CHUNKING_CONFIG.items():
        print(f"  • {content_type.upper()}:")
        print(f"      - Chunk size: {config['max_words']} words")
        print(f"      - Overlap: {config['overlap_words']} words")
        print(f"      - Min to chunk: {config.get('min_words_to_chunk', config['max_words'])} words")
    
    print(f"\n💡 TIP: To change chunking behavior, edit CHUNKING_CONFIG in {__file__}")
    print("    Uncomment the aggressive config for more granular chunks.\n")
    
    print("─" * 80)
    index_pages_to_qdrant()
    index_workitems_to_qdrant()
    index_projects_to_qdrant()
    index_cycles_to_qdrant()
    index_modules_to_qdrant()
    
    # Print comprehensive statistics
    _stats.print_summary()
    
    print("✅ Qdrant indexing complete!")
    print("🚀 All documents have chunk metadata (parent_id, chunk_index, chunk_count)")
    print("🚀 Chunk-aware retrieval is ready to use!")
    print("=" * 80)
