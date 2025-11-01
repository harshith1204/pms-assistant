import os
import time
import uuid
import json
from typing import Dict, List

from pymongo import MongoClient
from kafka import KafkaProducer
from fastembed import TextEmbedding
from loguru import logger


def get_env(name: str, default: str) -> str:
    return os.getenv(name, default)



def load_data_json() -> List[Dict]:
    """Load documents from data.json file."""
    try:
        with open('/app/data.json', 'r') as f:
            data = json.load(f)
            logger.info("Loaded {} documents from data.json", len(data))
            return data
    except Exception as e:
        logger.warning("Could not load data.json: {}", e)
        return []


def send_to_kafka(producer: KafkaProducer, topic: str, document: Dict) -> None:
    """Send a document to Kafka."""
    try:
        # Create Kafka message with the same format as MongoDB CDC
        message = {
            "schema": {"type": "string", "optional": False},
            "payload": json.dumps(document)
        }
        producer.send(topic, value=json.dumps(message).encode('utf-8'))
        logger.info("Sent document {} to Kafka topic {}", document.get('id', 'unknown'), topic)
    except Exception as e:
        logger.error("Failed to send document to Kafka: {}", e)


def main() -> None:
    # Connection settings
    mongo_uri = get_env("MONGODB_URI", "mongodb://mongodb:27017/?replicaSet=rs0&directConnection=true")
    database_name = get_env("MONGODB_DATABASE", "data_sync")
    collection_name = get_env("MONGODB_COLLECTION", "documents")
    kafka_bootstrap = get_env("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    kafka_topic = get_env("KAFKA_TOPIC", "data-sync.documents")

    # Wait for MongoDB to be ready
    client = None
    while client is None:
        try:
            client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
            # Test the connection
            client.admin.command('ping')
            logger.info("Connected to MongoDB")
        except Exception as e:
            logger.warning("Waiting for MongoDB: {}", e)
            time.sleep(2)

    # Wait for Kafka to be ready
    producer = None
    while producer is None:
        try:
            producer = KafkaProducer(bootstrap_servers=kafka_bootstrap.split(','))
            logger.info("Connected to Kafka")
        except Exception as e:
            logger.warning("Waiting for Kafka: {}", e)
            time.sleep(2)

    # Get database and collection
    db = client[database_name]
    collection = db[collection_name]

    # Load data.json documents and send them to Kafka
    data_docs = load_data_json()
    if data_docs:
        logger.info("Sending {} documents from data.json to Kafka", len(data_docs))
        try:
            # Insert into MongoDB first
            result = collection.insert_many(data_docs)
            logger.info("Inserted {} documents into MongoDB", len(result.inserted_ids))

            # Fetch the inserted documents from MongoDB and send them to Kafka
            inserted_docs = list(collection.find({"_id": {"$in": result.inserted_ids}}))
            for doc in inserted_docs:
                # Convert ObjectId to string for JSON serialization
                kafka_doc = {k: str(v) if k == '_id' else v for k, v in doc.items()}
                send_to_kafka(producer, kafka_topic, kafka_doc)
            producer.flush()
            logger.info("Successfully sent all documents to Kafka")

        except Exception as e:
            logger.error("Failed to process data.json documents: {}", e)
            import traceback
            logger.error("Traceback: {}", traceback.format_exc())
    else:
        logger.warning("No documents found in data.json")

    logger.info("Producer completed successfully")

    # Close connections
    producer.close()
    client.close()


if __name__ == "__main__":
    main()
