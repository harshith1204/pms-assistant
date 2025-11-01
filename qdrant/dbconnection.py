import os
from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams, OptimizersConfigDiff, SparseVectorParams
from dotenv import load_dotenv
# from tools import rag_content_search

# Load environment variables
load_dotenv()
qdrant_api_key = os.getenv("QDRANT_API_KEY")
qdrant_url = os.getenv("QDRANT_URL")  

# --- Connect to MongoDB ---
try:
    mongo_client = MongoClient(
        "mongodb://BeeOSAdmin:Proficornlabs%401118@172.214.123.233:27017/?authSource=admin",
        directConnection=True,
        serverSelectionTimeoutMS=5000
    )

    # Try listing databases to confirm connection
    print("MongoDB Databases:", mongo_client.list_database_names())
    print("✅ MongoDB connected successfully!")

    # Access your specific collections
    db = mongo_client["ProjectManagement"]
    page_collection = db["page"]
    workitem_collection = db["workItem"]
    cycle_collection = db["cycle"]
    module_collection = db["module"]
    project_collection = db["project"]
    epic_collection = db["epic"]
    feature_collection = db["features"]
    userstory_collection = db["userStory"]

except Exception as e:
    print("❌ MongoDB connection failed:", e)

# --- Connect to Qdrant ---
try:
    qdrant_client = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key,
        timeout=60 
    )

    QDRANT_COLLECTION= "pms_collection"

    # Check if collection exists, if not, create with named vectors + sparse for hybrid search
    if QDRANT_COLLECTION not in [col.name for col in qdrant_client.get_collections().collections]:
        qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config={
                "dense": VectorParams(size=768, distance=Distance.COSINE),
            },
            sparse_vectors_config={
                "sparse": SparseVectorParams(),
            },
        )
    
    # Force immediate indexing on this collection
    try:
        qdrant_client.update_collection(
            collection_name=QDRANT_COLLECTION,
            optimizer_config=OptimizersConfigDiff(indexing_threshold=1)
        )
        print("✅ Qdrant optimizer indexing_threshold set to 1")
    except Exception as e:
        print(f"⚠️ Failed to set optimizer config: {e}")
    # if QDRANT_COLLECTION_WORKITEM not in [col.name for col in qdrant_client.get_collections().collections]:
    #     qdrant_client.recreate_collection(
    #         collection_name=QDRANT_COLLECTION_WORKITEM,
    #         vectors_config=VectorParams(
    #             size=768, 
    #             distance=Distance.COSINE
    #         )
    #     )

    # Try listing collections to confirm connection
    print("Qdrant Collections:", qdrant_client.get_collections())
    print("✅ Qdrant connected successfully!")

except Exception as e:
    print("❌ Qdrant connection failed:", e)

import asyncio

if __name__ == "__main__":
    # Test basic connection
    try:
        collections = qdrant_client.get_collections()
        print(f"✅ Qdrant connected successfully! Collections: {[col.name for col in collections.collections]}")
    except Exception as e:
        print(f"❌ Qdrant connection failed: {e}")

