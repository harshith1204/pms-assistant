import os
from pymongo import MongoClient
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from dotenv import load_dotenv
from tools import rag_content_search

# Load environment variables
load_dotenv()
qdrant_api_key = os.getenv("QDRANT_API_KEY")
qdrant_url = os.getenv("QDRANT_URL")  

# --- Connect to MongoDB ---
try:
    mongo_client = MongoClient(
        "localhost:27017",
        directConnection=True,
        serverSelectionTimeoutMS=5000
    )

    # Try listing databases to confirm connection
    print("MongoDB Databases:", mongo_client.list_database_names())
    print("✅ MongoDB connected successfully!")

    # Access your specific collections
    db = mongo_client["pms"]
    page_collection = db["page"]
    workitem_collection = db["workitem"]

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

    # Check if collection exists, if not, create
    if QDRANT_COLLECTION not in [col.name for col in qdrant_client.get_collections().collections]:
        qdrant_client.recreate_collection(
            collection_name=QDRANT_COLLECTION,
            vectors_config=VectorParams(
                size=768, 
                distance=Distance.COSINE
            )
        )
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
    async def main():
        print("🔍 Testing rag_content_search...")
        result1 = await rag_content_search("Find the work item about cycle UI breaking.", content_type="workitem")
        print(result1)

        # print("\n📖 Testing rag_answer_question...")
        # result2 = await rag_answer_question("What is stored in pages?")
        # print(result2)

    asyncio.run(main())

