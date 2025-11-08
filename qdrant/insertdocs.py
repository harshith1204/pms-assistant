import os
import sys
import json
import uuid
import logging
from itertools import islice
from bson.binary import Binary
from bson.objectid import ObjectId
from qdrant_client.http.models import (
    PointStruct,
    PayloadSchemaType,
    Distance,
    VectorParams,
    OptimizersConfigDiff,
    SparseVectorParams,
    SparseVector,
)
from embedding.service_client import EmbeddingServiceClient, EmbeddingServiceError
from collections import defaultdict

# Add the parent directory to sys.path so we can import from qdrant
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from qdrant.dbconnection import (
    page_collection,
    workitem_collection,
    cycle_collection,
    module_collection,
    project_collection,
    epic_collection,
    qdrant_client,
    QDRANT_COLLECTION
)
from dotenv import load_dotenv
from huggingface_hub import login
import re
import html as html_lib
from qdrant.encoder import get_splade_encoder

# ------------------ Setup ------------------

# Load .env file and authenticate HuggingFace
load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)

hf_token = os.getenv("HuggingFace_API_KEY")
try:
    if hf_token:
        login(hf_token)
except Exception as e:
    logger.warning(f"HuggingFace login failed: {e}")

# Load embedding model once, with fallback to a public model
try:
    embedder = EmbeddingServiceClient(os.getenv("EMBEDDING_SERVICE_URL"))
    EMBEDDING_DIMENSION = embedder.get_dimension()
except (EmbeddingServiceError, ValueError) as exc:
    raise RuntimeError(f"Failed to initialize embedding service: {exc}") from exc

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
    

# Global stats instance
_stats = ChunkingStats()

# ------------------ Helpers ------------------

def ensure_collection_with_hybrid(
    collection_name: str,
    vector_size: int = 768,
    force_recreate: bool = False,
):
    """Ensure Qdrant collection supports dense + sparse (SPLADE) hybrid search without data loss.

    Behavior:
    - If the collection does not exist → create it with named dense and sparse vectors.
    - If the collection exists → do NOT drop it (unless force_recreate=True).
    - Always ensure optimizer and payload indexes idempotently.
    """
    try:
        should_create = False
        try:
            # Determine existence via list to avoid 404 exceptions
            existing_names = [c.name for c in qdrant_client.get_collections().collections]
            should_create = collection_name not in existing_names
        except Exception as e:
            # If listing fails, fallback to creation attempt path
            logger.warning(f"Could not list collections: {e}")
            should_create = True

        if force_recreate:
            qdrant_client.recreate_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": VectorParams(size=vector_size, distance=Distance.COSINE),
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(),
                },
            )
        elif should_create:
            qdrant_client.create_collection(
                collection_name=collection_name,
                vectors_config={
                    "dense": VectorParams(size=vector_size, distance=Distance.COSINE),
                },
                sparse_vectors_config={
                    "sparse": SparseVectorParams(),
                },
            )

        # Ensure optimizer is set for immediate indexing (idempotent)
        try:
            qdrant_client.update_collection(
                collection_name=collection_name,
                optimizer_config=OptimizersConfigDiff(indexing_threshold=1),
            )
        except Exception as e:
            logger.warning(f"Failed to update optimizer config: {e}")

        # Ensure keyword and text payload indexes exist (idempotent)
        try:
            qdrant_client.create_payload_index(
                collection_name=collection_name,
                field_name="content_type",
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception as e:
            if "already exists" not in str(e):
                logger.warning(f"Failed to ensure index on 'content_type': {e}")

        # Business scoping index
        try:
            qdrant_client.create_payload_index(
                collection_name=collection_name,
                field_name="business_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception as e:
            if "already exists" not in str(e):
                logger.warning(f"Failed to ensure index on 'business_id': {e}")

        try:
            qdrant_client.create_payload_index(
                collection_name=collection_name,
                field_name="project_name",
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception as e:
            if "already exists" not in str(e):
                logger.warning(f"Failed to ensure index on 'project_name': {e}")

        for text_field in ["title", "full_text"]:
            try:
                qdrant_client.create_payload_index(
                    collection_name=collection_name,
                    field_name=text_field,
                    field_schema=PayloadSchemaType.TEXT,
                )
            except Exception as e:
                if "already exists" not in str(e):
                    logger.warning(f"Failed to ensure text index on '{text_field}': {e}")

        # Chunk index for efficient adjacent chunk retrieval
        try:
            qdrant_client.create_payload_index(
                collection_name=collection_name,
                field_name="chunk_index",
                field_schema=PayloadSchemaType.INTEGER,
            )
        except Exception as e:
            if "already exists" not in str(e):
                logger.warning(f"Failed to ensure index on 'chunk_index': {e}")

        # Additional indexes for filtering operations
        for field_name in ["parent_id", "project_id", "mongo_id"]:
            try:
                qdrant_client.create_payload_index(
                    collection_name=collection_name,
                    field_name=field_name,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
            except Exception as e:
                if "already exists" not in str(e):
                    logger.warning(f"Failed to ensure index on '{field_name}': {e}")
    except Exception as e:
        logger.error(f"Error ensuring collection '{collection_name}': {e}")

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
        logger.warning(f"Failed to parse content: {e}")
        return [], ""

def point_id_from_seed(seed: str) -> str:
    """Create a deterministic UUID from a seed string for Qdrant point IDs."""
    return str(uuid.uuid5(uuid.NAMESPACE_URL, seed))

# ------------------ Chunking Configuration ------------------

# Chunking settings per content type
# Adjust these values to control chunking behavior
CHUNKING_CONFIG = {
    "page": {
        "max_words": 220,
        "overlap_words": 40,
        "min_words_to_chunk": 220,  # Only chunk if text is longer than this
    },
    "work_item": {
        "max_words": 220,
        "overlap_words": 40,
        "min_words_to_chunk": 220,
    },
    "project": {
        "max_words": 220,
        "overlap_words": 40,
        "min_words_to_chunk": 220,
    },
    "cycle": {
        "max_words": 220,
        "overlap_words": 40,
        "min_words_to_chunk": 220,
    },
    "module": {
        "max_words": 220,
        "overlap_words": 40,
        "min_words_to_chunk": 220,
    },
    # timeline intentionally excluded from RAG indexing to avoid bulky data
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
            logger.error(f"Failed to upload batch: {e}")
    return total_indexed

# ------------------ Indexing Functions ------------------

def index_pages_to_qdrant():
    try:
        print("🔄 Indexing pages from MongoDB to Qdrant...")

        # Ensure collection and indexes for hybrid search
        ensure_collection_with_hybrid(QDRANT_COLLECTION, vector_size=EMBEDDING_DIMENSION)

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
                logger.warning(f"Failed to ensure index: {e}")

        # Fetch pages with rich metadata
        documents = page_collection.find({}, {
            "_id": 1, "content": 1, "title": 1, "visibility": 1, "isFavourite": 1,
            "createdAt": 1, "updatedAt": 1, "createdTimeStamp": 1, "updatedTimeStamp": 1,
            "project": 1, "business": 1, "createdBy": 1
        })
        points = []

        splade = get_splade_encoder()
        for doc in documents:
            mongo_id = normalize_mongo_id(doc["_id"])
            title = doc.get("title", "")
            blocks, combined_text = parse_editorjs_blocks(doc.get("content", ""))

            # Extract additional text content from other fields in the page
            if combined_text:
                # Look for other substantial text fields in the page document
                for field_name, field_value in doc.items():
                    if (field_name not in ["_id", "title", "content", "visibility", "isFavourite", "createdAt", "updatedAt", "createdTimeStamp", "updatedTimeStamp", "project", "createdBy", "business"]
                        and isinstance(field_value, str)
                        and len(field_value.strip()) > 20):  # Only substantial text
                        combined_text += " " + field_value.strip()

            # Use title as fallback content if no content is available
            # This ensures pages are searchable even if they have minimal content
            if not combined_text and title:
                combined_text = title
                print(f"⚠️ Page '{title}' has no content, using title as fallback")

            # Skip only if both content AND title are empty
            if not combined_text:
                print(f"⚠️ Skipping page {mongo_id} - no title or content")
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
                    if doc["business"].get("_id") is not None:
                        try:
                            metadata["business_id"] = normalize_mongo_id(doc["business"].get("_id"))
                        except Exception:
                            pass
            
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

            vectors = embedder.encode(chunks)
            if len(vectors) != len(chunks):
                raise EmbeddingServiceError("Embedding service returned unexpected vector count")

            for idx, chunk in enumerate(chunks):
                vector = vectors[idx]
                full_text = f"{title} {chunk}".strip()
                splade_vec = splade.encode_text(full_text)
                payload = {
                    "mongo_id": mongo_id,
                    "parent_id": mongo_id,
                    "chunk_index": idx,
                    "chunk_count": len(chunks),
                    "title": title,
                    "content": chunk,
                    # Provide a concatenated text field for full-text search
                    "full_text": full_text,
                    "content_type": "page"
                }
                # Add metadata, filtering out None values
                payload.update({k: v for k, v in metadata.items() if v is not None})
                
                point_kwargs = {
                    "id": point_id_from_seed(f"{mongo_id}/page/{idx}"),
                    "vector": {
                        "dense": vector,
                    },
                    "payload": payload,
                }
                if splade_vec.get("indices"):
                    point_kwargs["vector"]["sparse"] = SparseVector(
                        indices=splade_vec["indices"], values=splade_vec["values"]
                    )
                point = PointStruct(**point_kwargs)
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
        ensure_collection_with_hybrid(QDRANT_COLLECTION, vector_size=EMBEDDING_DIMENSION)

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
                logger.warning(f"Failed to ensure index: {e}")

        # Fetch work items with rich metadata
        documents = workitem_collection.find({}, {
            "_id": 1, "title": 1, "description": 1, "displayBugNo": 1,
            "priority": 1, "status": 1, "state": 1, "assignee": 1,
            "createdAt": 1, "updatedAt": 1, "createdTimeStamp": 1, "updatedTimeStamp": 1,
            "project": 1, "cycle": 1, "modules": 1, "business": 1, "createdBy": 1,"workLogs":1
        })
        points = []

        splade = get_splade_encoder()
        for doc in documents:
            mongo_id = normalize_mongo_id(doc["_id"])
            # Clean HTML/entities before chunking for better retrieval quality
            title_clean = html_to_text(doc.get("title", ""))
            desc_clean = html_to_text(doc.get("description", ""))
            # Extract work log descriptions (workLogs is an array)
            worklogs_descriptions = []
            if doc.get("workLogs") and isinstance(doc["workLogs"], list):
                worklogs_descriptions = [
                    log.get("description", "") for log in doc["workLogs"]
                    if isinstance(log, dict) and log.get("description")
                ]
            worklogs_description = " ".join(worklogs_descriptions)
            combined_text = " ".join(filter(None, [title_clean, desc_clean, worklogs_description])).strip()
            if not combined_text:
                print(f"⚠️ Skipping work item {mongo_id} - no substantial text content found")
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
                    if doc["business"].get("_id") is not None:
                        try:
                            metadata["business_id"] = normalize_mongo_id(doc["business"].get("_id"))
                        except Exception:
                            pass
            
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
            
            vectors = embedder.encode(chunks)
            if len(vectors) != len(chunks):
                raise EmbeddingServiceError("Embedding service returned unexpected vector count")

            for idx, chunk in enumerate(chunks):
                vector = vectors[idx]
                full_text = f"{doc.get('title', '')} {chunk}".strip()
                splade_vec = splade.encode_text(full_text)
                
                payload = {
                    "mongo_id": mongo_id,
                    "parent_id": mongo_id,
                    "chunk_index": idx,
                    "chunk_count": len(chunks),
                    "title": doc.get("title", ""),
                    "content": chunk,
                    "full_text": full_text,
                    "content_type": "work_item"
                }
                # Add metadata, filtering out None values
                payload.update({k: v for k, v in metadata.items() if v is not None})

                point_kwargs = {
                    "id": point_id_from_seed(f"{mongo_id}/work_item/{idx}"),
                    "vector": {
                        "dense": vector,
                    },
                    "payload": payload,
                }
                if splade_vec.get("indices"):
                    point_kwargs["vector"]["sparse"] = SparseVector(
                        indices=splade_vec["indices"], values=splade_vec["values"]
                    )
                point = PointStruct(**point_kwargs)
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

        ensure_collection_with_hybrid(QDRANT_COLLECTION, vector_size=EMBEDDING_DIMENSION)

        documents = project_collection.find({}, {"_id": 1, "name": 1, "description": 1, "business": 1})
        points = []

        splade = get_splade_encoder()
        for doc in documents:
            mongo_id = normalize_mongo_id(doc["_id"])
            name = doc.get("name", "")
            description = (doc.get("description") or "").strip()

            # Extract ALL substantial text content from the project document
            text_parts = []

            # Include name if present
            if name:
                text_parts.append(name)

            # Include description if present and substantial
            if description and len(description) > 10:
                text_parts.append(description)

            # Include any other substantial text fields
            for field_name, field_value in doc.items():
                if (field_name not in ["_id", "name", "description", "createdAt", "updatedAt", "createdTimeStamp", "updatedTimeStamp"]
                    and isinstance(field_value, str)
                    and len(field_value.strip()) > 20):  # Only substantial text
                    text_parts.append(field_value.strip())

            combined_text = " ".join(text_parts).strip()
            if not combined_text:
                print(f"⚠️ Skipping project {mongo_id} - no substantial text content found")
                continue

            # Build metadata
            metadata = {}
            if doc.get("business") and isinstance(doc["business"], dict):
                metadata["business_name"] = doc["business"].get("name")
                if doc["business"].get("_id") is not None:
                    try:
                        metadata["business_id"] = normalize_mongo_id(doc["business"].get("_id"))
                    except Exception:
                        pass

            # Chunk projects with long descriptions
            chunks = get_chunks_for_content(combined_text, "project")
            if not chunks:
                chunks = [combined_text]
            
            # Record statistics
            word_count = len(combined_text.split()) if combined_text else 0
            _stats.record("project", mongo_id, name, len(chunks), word_count)
            
            vectors = embedder.encode(chunks)
            if len(vectors) != len(chunks):
                raise EmbeddingServiceError("Embedding service returned unexpected vector count")

            for idx, chunk in enumerate(chunks):
                vector = vectors[idx]
                full_text = f"{name} {chunk}".strip()
                splade_vec = splade.encode_text(full_text)
                payload = {
                    "mongo_id": mongo_id,
                    "parent_id": mongo_id,
                    "chunk_index": idx,
                    "chunk_count": len(chunks),
                    "title": name,
                    "content": chunk,
                    "full_text": full_text,
                    "content_type": "project"
                }
                payload.update({k: v for k, v in metadata.items() if v is not None})
                point_kwargs = {
                    "id": point_id_from_seed(f"{mongo_id}/project/{idx}"),
                    "vector": {
                        "dense": vector,
                    },
                    "payload": payload,
                }
                if splade_vec.get("indices"):
                    point_kwargs["vector"]["sparse"] = SparseVector(
                        indices=splade_vec["indices"], values=splade_vec["values"]
                    )
                point = PointStruct(**point_kwargs)
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

        ensure_collection_with_hybrid(QDRANT_COLLECTION, vector_size=EMBEDDING_DIMENSION)

        documents = cycle_collection.find({}, {"_id": 1, "name": 1, "title": 1, "description": 1, "business": 1})
        points = []

        splade = get_splade_encoder()
        for doc in documents:
            mongo_id = normalize_mongo_id(doc["_id"])
            name = doc.get("name") or doc.get("title") or ""
            description = (doc.get("description") or "").strip()

            # Extract ALL substantial text content from the cycle document
            text_parts = []

            # Include name if present
            if name:
                text_parts.append(name)

            # Include description if present and substantial
            if description and len(description) > 10:
                text_parts.append(description)

            # Include any other substantial text fields
            for field_name, field_value in doc.items():
                if (field_name not in ["_id", "name", "title", "description", "createdAt", "updatedAt", "createdTimeStamp", "updatedTimeStamp"]
                    and isinstance(field_value, str)
                    and len(field_value.strip()) > 20):  # Only substantial text
                    text_parts.append(field_value.strip())

            combined_text = " ".join(text_parts).strip()
            if not combined_text:
                print(f"⚠️ Skipping cycle {mongo_id} - no substantial text content found")
                continue

            # Build metadata
            metadata = {}
            if doc.get("business") and isinstance(doc["business"], dict):
                metadata["business_name"] = doc["business"].get("name")
                if doc["business"].get("_id") is not None:
                    try:
                        metadata["business_id"] = normalize_mongo_id(doc["business"].get("_id"))
                    except Exception:
                        pass

            # Chunk cycles with long descriptions
            chunks = get_chunks_for_content(combined_text, "cycle")
            if not chunks:
                chunks = [combined_text]
            
            # Record statistics
            word_count = len(combined_text.split()) if combined_text else 0
            _stats.record("cycle", mongo_id, name, len(chunks), word_count)
            
            vectors = embedder.encode(chunks)
            if len(vectors) != len(chunks):
                raise EmbeddingServiceError("Embedding service returned unexpected vector count")

            for idx, chunk in enumerate(chunks):
                vector = vectors[idx]
                full_text = f"{name} {chunk}".strip()
                splade_vec = splade.encode_text(full_text)
                payload = {
                    "mongo_id": mongo_id,
                    "parent_id": mongo_id,
                    "chunk_index": idx,
                    "chunk_count": len(chunks),
                    "title": name,
                    "content": chunk,
                    "full_text": full_text,
                    "content_type": "cycle"
                }
                payload.update({k: v for k, v in metadata.items() if v is not None})
                point_kwargs = {
                    "id": point_id_from_seed(f"{mongo_id}/cycle/{idx}"),
                    "vector": {
                        "dense": vector,
                    },
                    "payload": payload,
                }
                if splade_vec.get("indices"):
                    point_kwargs["vector"]["sparse"] = SparseVector(
                        indices=splade_vec["indices"], values=splade_vec["values"]
                    )
                point = PointStruct(**point_kwargs)
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

        ensure_collection_with_hybrid(QDRANT_COLLECTION, vector_size=EMBEDDING_DIMENSION)

        documents = module_collection.find({}, {"_id": 1, "name": 1, "title": 1, "description": 1, "business": 1})
        points = []

        splade = get_splade_encoder()
        for doc in documents:
            mongo_id = normalize_mongo_id(doc["_id"])
            name = doc.get("name") or doc.get("title") or ""
            description = (doc.get("description") or "").strip()

            # Extract ALL substantial text content from the module document
            text_parts = []

            # Include name if present
            if name:
                text_parts.append(name)

            # Include description if present and substantial
            if description and len(description) > 10:
                text_parts.append(description)

            # Include any other substantial text fields
            for field_name, field_value in doc.items():
                if (field_name not in ["_id", "name", "title", "description", "createdAt", "updatedAt", "createdTimeStamp", "updatedTimeStamp"]
                    and isinstance(field_value, str)
                    and len(field_value.strip()) > 20):  # Only substantial text
                    text_parts.append(field_value.strip())

            combined_text = " ".join(text_parts).strip()
            if not combined_text:
                print(f"⚠️ Skipping module {mongo_id} - no substantial text content found")
                continue

            # Build metadata
            metadata = {}
            if doc.get("business") and isinstance(doc["business"], dict):
                metadata["business_name"] = doc["business"].get("name")
                if doc["business"].get("_id") is not None:
                    try:
                        metadata["business_id"] = normalize_mongo_id(doc["business"].get("_id"))
                    except Exception:
                        pass

            # Chunk modules with long descriptions
            chunks = get_chunks_for_content(combined_text, "module")
            if not chunks:
                chunks = [combined_text]
            
            # Record statistics
            word_count = len(combined_text.split()) if combined_text else 0
            _stats.record("module", mongo_id, name, len(chunks), word_count)
            
            vectors = embedder.encode(chunks)
            if len(vectors) != len(chunks):
                raise EmbeddingServiceError("Embedding service returned unexpected vector count")

            for idx, chunk in enumerate(chunks):
                vector = vectors[idx]
                full_text = f"{name} {chunk}".strip()
                splade_vec = splade.encode_text(full_text)
                payload = {
                    "mongo_id": mongo_id,
                    "parent_id": mongo_id,
                    "chunk_index": idx,
                    "chunk_count": len(chunks),
                    "title": name,
                    "content": chunk,
                    "full_text": full_text,
                    "content_type": "module"
                }
                payload.update({k: v for k, v in metadata.items() if v is not None})
                point_kwargs = {
                    "id": point_id_from_seed(f"{mongo_id}/module/{idx}"),
                    "vector": {
                        "dense": vector,
                    },
                    "payload": payload,
                }
                if splade_vec.get("indices"):
                    point_kwargs["vector"]["sparse"] = SparseVector(
                        indices=splade_vec["indices"], values=splade_vec["values"]
                    )
                point = PointStruct(**point_kwargs)
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

# New function to index epic
def index_epic_to_qdrant():
    try:
        print("🔄 Indexing epic from MongoDB to Qdrant...")

        ensure_collection_with_hybrid(QDRANT_COLLECTION, vector_size=EMBEDDING_DIMENSION)

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
                logger.warning(f"Failed to ensure index: {e}")

        documents = epic_collection.find({}, {
            "_id": 1,
            "title": 1,
            "description": 1,
            "bugNo": 1,
            "priority": 1,
            "assignee": 1,
            "createdAt": 1,
            "updatedAt": 1,
            "createdTimeStamp": 1,
            "updatedTimeStamp": 1,
            "project": 1,
            "business": 1,
            "state": 1,
            "stateMaster": 1,
            "createdBy": 1
        })
        points = []

        splade = get_splade_encoder()
        for doc in documents:
            mongo_id = normalize_mongo_id(doc["_id"])
            title_clean = html_to_text(doc.get("title", ""))
            desc_clean = html_to_text(doc.get("description", ""))
            combined_text = " ".join(filter(None, [title_clean, desc_clean])).strip()
            if not combined_text:
                print(f"⚠️ Skipping epic {mongo_id} - no substantial text content found")
                continue

            metadata = {
                "bugNo": doc.get("bugNo"),
                "priority": doc.get("priority"),
                "createdAt": doc.get("createdAt") or doc.get("createdTimeStamp"),
                "updatedAt": doc.get("updatedAt") or doc.get("updatedTimeStamp"),
            }
            
            if doc.get("state"):
                if isinstance(doc["state"], dict):
                    metadata["state_name"] = doc["state"].get("name")

            if doc.get("stateMaster"):
                if isinstance(doc["stateMaster"], dict):
                    metadata["stateMaster_name"] = doc["stateMaster"].get("name")

            if doc.get("project"):
                if isinstance(doc["project"], dict):
                    metadata["project_name"] = doc["project"].get("name")
                    metadata["project_id"] = normalize_mongo_id(doc["project"].get("_id")) if doc["project"].get("_id") else None

            if doc.get("business"):
                if isinstance(doc["business"], dict):
                    metadata["business_name"] = doc["business"].get("name")
                    if doc["business"].get("_id") is not None:
                        try:
                            metadata["business_id"] = normalize_mongo_id(doc["business"].get("_id"))
                        except Exception:
                            pass

            if doc.get("assignee"):
                assignee = doc["assignee"]
                if isinstance(assignee, list) and assignee and isinstance(assignee[0], dict):
                    metadata["assignee_name"] = assignee[0].get("name")
                elif isinstance(assignee, dict):
                    metadata["assignee_name"] = assignee.get("name")

            if doc.get("createdBy"):
                if isinstance(doc["createdBy"], dict):
                    metadata["created_by_name"] = doc["createdBy"].get("name")

            chunks = get_chunks_for_content(combined_text, "epic")
            if not chunks:
                chunks = [combined_text]

            word_count = len(combined_text.split()) if combined_text else 0
            _stats.record("epic", mongo_id, doc.get("title", ""), len(chunks), word_count)

            vectors = embedder.encode(chunks)
            if len(vectors) != len(chunks):
                raise EmbeddingServiceError("Embedding service returned unexpected vector count")

            for idx, chunk in enumerate(chunks):
                vector = vectors[idx]
                full_text = f"{doc.get('title', '')} {chunk}".strip()
                splade_vec = splade.encode_text(full_text)
                payload = {
                    "mongo_id": mongo_id,
                    "parent_id": mongo_id,
                    "chunk_index": idx,
                    "chunk_count": len(chunks),
                    "title": doc.get("title", ""),
                    "content": chunk,
                    "full_text": full_text,
                    "content_type": "epic"
                }

                payload.update({k: v for k, v in metadata.items() if v is not None})

                point_kwargs = {
                    "id": point_id_from_seed(f"{mongo_id}/epic/{idx}"),
                    "vector": {
                        "dense": vector,
                    },
                    "payload": dict(payload),
                }
                if splade_vec.get("indices"):
                    point_kwargs["vector"]["sparse"] = SparseVector(
                        indices=splade_vec["indices"], values=splade_vec["values"]
                    )
                point = PointStruct(**point_kwargs)
                points.append(point)

        if not points:
            print("⚠️ No valid epics to index.")
            return {"status": "warning", "message": "No valid epics found to index."}

        total_indexed = upload_in_batches(points, QDRANT_COLLECTION)
        print(f"✅ Indexed {total_indexed} epics to Qdrant.")
        return {"status": "success", "indexed_documents": total_indexed}

    except Exception as e:
        print(f"❌ Error during epic indexing: {e}")
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
