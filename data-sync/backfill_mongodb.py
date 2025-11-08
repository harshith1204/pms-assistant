#!/usr/bin/env python3
"""
Backfill script to import existing MongoDB data into the Kafka pipeline.

This script reads documents from MongoDB collections and sends them as change events
to Kafka topics, mimicking the MongoDB Kafka connector's behavior for existing data.
"""

import json
import os
import sys
import time
import logging
from typing import Dict, Any, List, Optional

import pymongo
from confluent_kafka import Producer
from confluent_kafka import KafkaError, KafkaException

# Import document normalization function from consumer
from qdrant.indexing_shared import normalize_document_ids

# Configure logging
logger = logging.getLogger(__name__)

# Configuration - match the connector setup
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://mongo:27017/ProjectManagement?authSource=admin"
)
DATABASE_NAME = os.getenv("MONGODB_DATABASE", "ProjectManagement")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC_PREFIX = os.getenv("KAFKA_TOPIC_PREFIX", "ProjectManagement.")

# Collections to backfill - configurable via environment
BACKFILL_COLLECTIONS_STR = os.getenv("BACKFILL_COLLECTIONS", "epic,features,cycle,module,members,workItem,userStory,page")
COLLECTIONS_TO_BACKFILL = [col.strip() for col in BACKFILL_COLLECTIONS_STR.split(",") if col.strip()]

# Batch size for processing
BATCH_SIZE = int(os.getenv("BACKFILL_BATCH_SIZE", "1000"))
SLEEP_BETWEEN_BATCHES = float(os.getenv("BACKFILL_SLEEP", "1.0"))

# Default to production mode (not dry run)
DEFAULT_DRY_RUN = os.getenv("BACKFILL_DRY_RUN", "false").lower() == "true"


class MongoDBBackfill:
    """Handles backfilling MongoDB data to Kafka."""

    def __init__(self):
        self.mongo_client = None
        self.kafka_producer = None
        self.database = None

    def connect_mongodb(self) -> bool:
        """Connect to MongoDB."""
        try:
            self.mongo_client = pymongo.MongoClient(MONGODB_URI)
            self.database = self.mongo_client[DATABASE_NAME]

            # Test connection
            self.mongo_client.admin.command('ping')
            return True
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            return False

    def connect_kafka(self) -> bool:
        """Connect to Kafka."""
        try:
            conf = {
                'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
                'acks': 'all',
                'retries': 3,
                'max.in.flight.requests.per.connection': 1,
                'delivery.timeout.ms': 30000,
                'request.timeout.ms': 10000
            }
            self.kafka_producer = Producer(conf)
            return True
        except Exception as e:
            logger.error(f"Kafka connection failed: {e}")
            return False

    def create_change_event(self, collection_name: str, document: Dict[str, Any]) -> Dict[str, Any]:
        """Create a change event message in the format expected by the consumer."""
        # Normalize document IDs to handle Binary objects and other MongoDB types
        normalized_document = normalize_document_ids(document)
        return {
            "operationType": "insert",
            "ns": {
                "db": DATABASE_NAME,
                "coll": collection_name
            },
            "fullDocument": normalized_document,
            "documentKey": {"_id": normalized_document["_id"]}
        }

    def get_collection_count(self, collection_name: str) -> int:
        """Get the total count of documents in a collection."""
        try:
            collection = self.database[collection_name]
            return collection.count_documents({})
        except Exception as e:
            logger.error(f"Error getting count for {collection_name}: {e}")
            return 0

    def backfill_collection(self, collection_name: str, dry_run: bool = False) -> int:
        """Backfill a single collection."""
        collection = self.database[collection_name]
        topic_name = f"{KAFKA_TOPIC_PREFIX}{collection_name}"

        total_count = self.get_collection_count(collection_name)

        if total_count == 0:
            logger.error(f"No documents to process for collection {collection_name}")
            return 0

        processed = 0
        errors = 0

        try:
            cursor = collection.find({}, batch_size=BATCH_SIZE)

            for i, document in enumerate(cursor):
                try:
                    # Create change event
                    change_event = self.create_change_event(collection_name, document)

                    if not dry_run:
                        # Send to Kafka using confluent-kafka
                        try:
                            self.kafka_producer.produce(
                                topic=topic_name,
                                value=json.dumps(change_event),
                                key=str(document["_id"])
                            )
                            # Trigger delivery callback
                            self.kafka_producer.poll(0)
                        except KafkaException as e:
                            logger.error(f"Kafka error sending to {topic_name}: {e}")
                            errors += 1
                            continue
                    processed += 1

                    # Progress reporting
                    if (i + 1) % BATCH_SIZE == 0:
                        time.sleep(SLEEP_BETWEEN_BATCHES)

                except Exception as e:
                    errors += 1
                    logger.error(f"Error processing document {document.get('_id', 'unknown')}: {e}")
                    if errors > 10:  # Stop if too many errors
                        logger.error("Too many errors, stopping collection processing")
                        break

        except Exception as e:
            logger.error(f"Error processing collection {collection_name}: {e}")
            return processed

        return processed

    def backfill_all_collections(self, collections: Optional[List[str]] = None, dry_run: bool = False) -> Dict[str, int]:
        """Backfill all specified collections."""
        if collections is None:
            collections = COLLECTIONS_TO_BACKFILL

        results = {}

        for collection_name in collections:
            try:
                processed = self.backfill_collection(collection_name, dry_run=dry_run)
                results[collection_name] = processed
            except Exception as e:
                logger.error(f"Failed to process collection {collection_name}: {e}")
                results[collection_name] = 0

        # Flush producer to ensure all messages are sent
        if not dry_run and self.kafka_producer:
            # Wait for all messages to be delivered (timeout: 30 seconds)
            remaining = self.kafka_producer.flush(30)
            if remaining > 0:
                logger.error(f"{remaining} messages may not have been delivered")

        return results

    def close(self):
        """Close connections."""
        # Note: confluent-kafka Producer doesn't have a close() method
        # Messages are flushed in backfill_all_collections()
        if self.mongo_client:
            self.mongo_client.close()


def main():
    """Main function."""
    import argparse

    global BATCH_SIZE, SLEEP_BETWEEN_BATCHES  # Declare globals first

    parser = argparse.ArgumentParser(description="Backfill MongoDB data to Kafka")
    parser.add_argument("--dry-run", action="store_true", help="Run without actually sending to Kafka")
    parser.add_argument("--collections", nargs="*", help="Specific collections to backfill")
    parser.add_argument("--batch-size", type=int, help="Batch size for processing")
    parser.add_argument("--sleep", type=float, help="Sleep between batches")

    args = parser.parse_args()

    # Override globals with args (for manual runs) or use environment defaults
    if args.batch_size is not None:
        BATCH_SIZE = args.batch_size
    if args.sleep is not None:
        SLEEP_BETWEEN_BATCHES = args.sleep

    # Determine dry run mode
    dry_run = args.dry_run or DEFAULT_DRY_RUN

    # Determine collections to process
    collections = args.collections if args.collections else COLLECTIONS_TO_BACKFILL

    backfill = MongoDBBackfill()

    try:
        # Connect to services
        if not backfill.connect_mongodb():
            sys.exit(1)

        if not dry_run and not backfill.connect_kafka():
            sys.exit(1)

        # Perform backfill
        results = backfill.backfill_all_collections(collections, dry_run=dry_run)

        # Summary
        total_processed = sum(results.values())
        if total_processed == 0:
            logger.error("No documents were processed.")
            sys.exit(1)
        sys.exit(0)

    except KeyboardInterrupt:
        logger.error("Backfill interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        backfill.close()


if __name__ == "__main__":
    main()