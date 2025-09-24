import os
import json
import uuid
from itertools import islice
from bson.binary import Binary
from bson.objectid import ObjectId
from qdrant_client.http.models import PointStruct, PayloadSchemaType
from sentence_transformers import SentenceTransformer
from dbconnection import (
    page_collection,
    workitem_collection,
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

# ------------------ Helpers ------------------

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

        documents = page_collection.find({}, {"_id": 1, "content": 1,"title":1})
        points = []

        for doc in documents:
            mongo_id = normalize_mongo_id(doc["_id"])
            title=doc.get("title","")
            blocks, combined_text = parse_editorjs_blocks(doc.get("content", ""))
            if not blocks:
                continue

            vector = embedder.encode(combined_text).tolist()

            point = PointStruct(
                id=mongo_id,
                vector=vector,
                payload={
                    "mongo_id": mongo_id,
                    "title": title,
                    "content": blocks,
                    "content_type": "page"
                }
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

        documents = workitem_collection.find({}, {"_id": 1, "title": 1, "description": 1})
        points = []

        for doc in documents:
            mongo_id = normalize_mongo_id(doc["_id"])
            combined_text = " ".join(filter(None, [doc.get("title", ""), doc.get("description", "")])).strip()
            if not combined_text:
                continue

            vector = embedder.encode(combined_text).tolist()

            point = PointStruct(
                id=mongo_id,
                vector=vector,
                payload={
                    "mongo_id": mongo_id,
                    "title": doc.get("title", ""),
                    "content": doc.get("description", ""),
                    "content_type": "work_item"
                }
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

# ------------------ Usage ------------------
# if __name__ == "__main__":
#     index_pages_to_qdrant()
#     index_workitems_to_qdrant()
