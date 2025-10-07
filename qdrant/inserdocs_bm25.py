import os
import sys
import json
import uuid
from itertools import islice
from bson.binary import Binary
from bson.objectid import ObjectId
from qdrant_client.http import models
from sentence_transformers import SentenceTransformer
from fastembed import SparseTextEmbedding
from collections import defaultdict

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
import re
import html as html_lib

# ------------------ Setup (Corrected) ------------------
load_dotenv()
hf_token = os.getenv("HuggingFace_API_KEY")
# ... (HuggingFace login logic) ...

print("Loading embedding models...")
try:
    dense_embedder = SentenceTransformer("google/embeddinggemma-300m")
except Exception as e:
    print(f"⚠️ Failed to load 'google/embeddinggemma-300m': {e}\nFalling back to 'all-MiniLM-L6-v2'")
    dense_embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2") # ✅ FIX: Assign fallback

try:
    sparse_embedder = SparseTextEmbedding("Qdrant/bm25")
except Exception as e:
    print(f"⚠️ Failed to load 'Qdrant/bm25': {e}\nFalling back to default sparse model.")
    sparse_embedder = SparseTextEmbedding() # ✅ FIX: Assign fallback

print("✅ Embedding models loaded.")


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

# ... (ChunkingStats, normalize_mongo_id, html_to_text, etc. are unchanged) ...
# ... (CHUNKING_CONFIG, chunk_text, get_chunks_for_content are unchanged) ...
# ... (batch_iterable, upload_in_batches are unchanged) ...
def normalize_mongo_id(mongo_id) -> str:
    """Convert Mongo _id (ObjectId or Binary UUID) into a safe string."""
    if isinstance(mongo_id, ObjectId):
        return str(mongo_id)
    elif isinstance(mongo_id, Binary) and mongo_id.subtype == 3:
        return str(uuid.UUID(bytes=mongo_id))
    return str(mongo_id)

def html_to_text(html: str) -> str:
    """Convert basic HTML to plain text, preserving simple line breaks and decoding entities."""
    if not html:
        return ""
    # Normalize common breaks to newlines
    text = re.sub(r"<(br|BR)\s*/?>", "\n", html)
    # Remove all other tags
    text = re.sub(r"<[^>]+>", "", text)
    # Decode HTML entities
    text = html_lib.unescape(text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def parse_editorjs_blocks(content_str: str):
    """Extract blocks from EditorJS JSON and produce a rich combined plain-text representation."""
    if not content_str or not content_str.strip():
        return [], ""
    try:
        content_json = json.loads(content_str)
        blocks = content_json.get("blocks", [])
        extracted: list[str] = []
        for block in blocks:
            btype = block.get("type") or ""
            data = block.get("data") or {}
            if btype in ("paragraph", "header", "quote"):
                text = html_to_text(data.get("text", ""))
                caption = html_to_text(data.get("caption", "")) if btype == "quote" else ""
                line = text if not caption else f"{text} — {caption}"
                if line:
                    extracted.append(line)
            elif btype == "list":
                items = data.get("items") or []
                style = (data.get("style") or "").lower()
                lines = []
                for idx, item in enumerate(items, 1):
                    item_text = html_to_text(item if isinstance(item, str) else str(item))
                    if not item_text:
                        continue
                    prefix = f"{idx}. " if style == "ordered" else "- "
                    lines.append(prefix + item_text)
                if lines:
                    extracted.append("\n".join(lines))
            elif btype == "checklist":
                items = data.get("items") or []
                lines = []
                for item in items:
                    text = html_to_text((item or {}).get("text", ""))
                    checked = (item or {}).get("checked", False)
                    if text:
                        lines.append(("[x] " if checked else "[ ] ") + text)
                if lines:
                    extracted.append("\n".join(lines))
            elif btype == "table":
                table = data.get("content") or []
                rows = []
                for row in table:
                    cells = [html_to_text(cell) for cell in (row or [])]
                    rows.append(" | ".join(cells).strip())
                if rows:
                    extracted.append("\n".join(rows))
            elif btype == "code":
                code = data.get("code", "").strip()
                if code:
                    extracted.append(code)
            elif btype in ("image", "embed", "linkTool", "raw", "delimiter"):
                # Prefer human text fields; skip binary/media noise
                parts = []
                if data.get("caption"):
                    parts.append(html_to_text(data.get("caption", "")))
                if btype == "linkTool":
                    link = (data.get("link") or "").strip()
                    meta = data.get("meta") or {}
                    title = html_to_text(meta.get("title", "")) if isinstance(meta, dict) else ""
                    desc = html_to_text(meta.get("description", "")) if isinstance(meta, dict) else ""
                    parts.extend([p for p in [title, desc, link] if p])
                text = " - ".join([p for p in parts if p])
                if text:
                    extracted.append(text)
            else:
                # Fallback: try common 'text' field
                text = html_to_text(data.get("text", ""))
                if text:
                    extracted.append(text)

        # Separate blocks with newlines to retain structure
        combined_text = "\n\n".join([t for t in extracted if t]).strip()
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

# ------------------ Collection Setup ------------------

def ensure_collection_with_hybrid(collection_name: str, dense_vector_size: int):
    """Ensure Qdrant collection exists with named dense and sparse vectors."""
    try:
        qdrant_client.recreate_collection(
            collection_name=collection_name,
            vectors_config={
                "dense": models.VectorParams(size=dense_vector_size, distance=models.Distance.COSINE),
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(),
            },
            optimizers_config=models.OptimizersConfigDiff(indexing_threshold=1000)
        )
        print(f"✅ Collection '{collection_name}' created/recreated with dense and sparse vector support.")
        
        # Create payload indexes for filtering
        for field, schema in [("content_type", models.PayloadSchemaType.KEYWORD), ("business_id", models.PayloadSchemaType.KEYWORD)]:
            qdrant_client.create_payload_index(collection_name, field, schema, wait=True)
        print("✅ Payload indexes ensured.")

    except Exception as e:
        print(f"❌ Error ensuring collection '{collection_name}': {e}")


# ------------------ Indexing Functions (Corrected and Optimized) ------------------

def index_all_documents(mongo_collection, content_type: str):
    """Generic function to index documents from a MongoDB collection."""
    try:
        print(f"🔄 Indexing {content_type} from MongoDB to Qdrant...")
        documents = mongo_collection.find({}, {"_id": 1, "content": 1, "title": 1, "name": 1, "description": 1, "business": 1})
        points = []

        for doc in documents:
            mongo_id = normalize_mongo_id(doc["_id"])
            title = doc.get("title") or doc.get("name") or ""
            
            content_text = doc.get("content") or doc.get("description") or ""
            if isinstance(content_text, str) and "blocks" in content_text:
                 _, combined_text = parse_editorjs_blocks(content_text)
            else:
                 combined_text = html_to_text(str(content_text))

            full_text_to_index = f"{title} {combined_text}".strip()

            if not full_text_to_index:
                print(f"⚠️ Skipping {content_type} {mongo_id} - no text content found")
                continue

            chunks = get_chunks_for_content(full_text_to_index, content_type)
            if not chunks:
                continue

            # ✅ FIX 1: Convert dense vectors to a list of lists immediately
            dense_vectors = dense_embedder.encode(chunks).tolist() 
            sparse_vectors_from_fastembed = list(sparse_embedder.embed(chunks))

            for idx, chunk in enumerate(chunks):
                payload = {
                    "mongo_id": mongo_id,
                    "parent_id": mongo_id,
                    "chunk_index": idx,
                    "chunk_count": len(chunks),
                    "title": title,
                    "content": chunk,
                    "content_type": content_type,
                    "business_id": normalize_mongo_id(doc.get("business", {}).get("_id")) if doc.get("business") else None
                }
                
                payload = {k: v for k, v in payload.items() if v is not None}
                
                # ✅ FIX 2: Convert fastembed's object to Qdrant's SparseVector object
                fastembed_sparse = sparse_vectors_from_fastembed[idx]
                qdrant_sparse_vector = models.SparseVector(
                    indices=fastembed_sparse.indices.tolist(),
                    values=fastembed_sparse.values.tolist()
                )
                
                point = models.PointStruct(
                    id=point_id_from_seed(f"{mongo_id}/{content_type}/{idx}"),
                    vector={
                        "dense": dense_vectors[idx],
                        "sparse": qdrant_sparse_vector # Use the correctly typed object
                    },
                    payload=payload
                )
                points.append(point)

        if not points:
            print(f"⚠️ No valid {content_type} documents to index.")
            return

        upload_in_batches(points, QDRANT_COLLECTION)
        print(f"✅ Indexed {len(points)} {content_type} chunks to Qdrant.")

    except Exception as e:
        import traceback
        print(f"❌ Error during {content_type} indexing: {e}")
        traceback.print_exc()

# ------------------ Usage ------------------
if __name__ == "__main__":
    print("=" * 80)
    print("🚀 STARTING QDRANT INDEXING (DENSE + SPARSE VECTORS)")
    print("=" * 80)

    # ✅ REFACTOR: Get dimension and create collection ONCE
    dense_vector_dimension = dense_embedder.get_sentence_embedding_dimension()
    ensure_collection_with_hybrid(QDRANT_COLLECTION, dense_vector_dimension)
    
    # ✅ REFACTOR: Call a generic function for each collection
    index_all_documents(page_collection, "page")
    index_all_documents(workitem_collection, "work_item")
    index_all_documents(project_collection, "project")
    index_all_documents(cycle_collection, "cycle")
    index_all_documents(module_collection, "module")
    
    print("=" * 80)
    print("✅ Qdrant indexing complete!")
    print("🚀 Collection is now ready for hybrid search using 'dense' and 'sparse' vectors.")
    print("=" * 80)