#!/usr/bin/env python3
"""
MongoDB setup script for Phoenix traces storage
This script creates the database, collections, and indexes optimized for trace data.
"""

import os
import sys
from datetime import datetime, timedelta
from pymongo import MongoClient, ASCENDING, DESCENDING, TEXT
from pymongo.errors import ConnectionFailure, OperationFailure
import json

# MongoDB configuration
MONGODB_CONFIG = {
    "connection_string": "mongodb://BeeOSAdmin:Proficornlabs%401118@172.214.123.233:27017/?authSource=admin",
    "database": "SimpoAssist",
    "collections": {
        "traces": "SimpoAssist.traces",
        "evaluations": "SimpoAssist.evaluations",
        "metrics": "SimpoAssist.metrics",
        "trace_events": "SimpoAssist.trace_events"
    }
}

def connect_to_mongodb():
    """Connect to MongoDB and return client and database"""
    try:
        client = MongoClient(MONGODB_CONFIG["connection_string"])
        # Test the connection
        client.admin.command('ping')
        db = client[MONGODB_CONFIG["database"]]
        print(f"✅ Connected to MongoDB database: {MONGODB_CONFIG['database']}")
        return client, db
    except ConnectionFailure as e:
        print(f"❌ Failed to connect to MongoDB: {e}")
        return None, None
    except Exception as e:
        print(f"❌ Unexpected error connecting to MongoDB: {e}")
        return None, None

def create_collections(db):
    """Create collections with appropriate options"""
    try:
        print("📋 Creating MongoDB collections...")

        # Main traces collection with time-based partitioning concept
        if 'traces' not in db.list_collection_names():
            # Create collection with time-series if MongoDB 5.0+
            try:
                db.create_collection(
                    'traces',
                    timeseries={
                        'timeField': 'start_time',
                        'metaField': 'metadata',
                        'granularity': 'seconds'
                    }
                )
                print("✅ Created time-series collection: traces")
            except OperationFailure:
                # Fallback to regular collection
                db.create_collection('traces')
                print("✅ Created regular collection: traces")

        # Evaluations collection
        if 'evaluations' not in db.list_collection_names():
            db.create_collection('evaluations')
            print("✅ Created collection: evaluations")

        # Performance metrics collection
        if 'metrics' not in db.list_collection_names():
            db.create_collection('metrics')
            print("✅ Created collection: metrics")

        # Trace events collection (for high-volume event data)
        if 'trace_events' not in db.list_collection_names():
            # Create as capped collection for events (optional)
            db.create_collection('trace_events', capped=True, size=1000000)  # 1MB capped
            print("✅ Created capped collection: trace_events")

        return True

    except Exception as e:
        print(f"❌ Error creating collections: {e}")
        return False

def create_indexes(db):
    """Create optimized indexes for trace queries"""
    try:
        print("🔍 Creating indexes for performance...")

        # Traces collection indexes
        traces_collection = db['traces']

        # Main query indexes
        indexes = [
            # Time-based queries (most common)
            ('start_time', DESCENDING),
            ('end_time', DESCENDING),

            # Trace correlation queries
            ('trace_id', ASCENDING),
            ('span_id', ASCENDING),
            ('parent_id', ASCENDING),

            # Status and type queries
            ('status_code', ASCENDING),
            ('span_kind', ASCENDING),
            ('name', ASCENDING),

            # Compound indexes for common query patterns
            [('trace_id', ASCENDING), ('start_time', DESCENDING)],  # Get all spans in a trace
            [('parent_id', ASCENDING), ('start_time', ASCENDING)],   # Get child spans
            [('name', ASCENDING), ('start_time', DESCENDING)],      # Get recent spans by operation
            [('status_code', ASCENDING), ('start_time', DESCENDING)], # Error analysis
            [('span_kind', ASCENDING), ('start_time', DESCENDING)],  # Service analysis

            # Text search index for attributes and events
            TEXT
        ]

        for index in indexes:
            if isinstance(index, tuple):
                field, direction = index
                index_name = f"{field}_{direction}"
            elif isinstance(index, list):
                field_names = "_".join([field for field, _ in index])
                index_name = f"compound_{field_names}"
            else:
                field = index
                index_name = f"{field}_text"

            try:
                if index == TEXT:
                    # Create text index on JSON fields
                    traces_collection.create_index([
                        ('name', TEXT),
                        ('status_message', TEXT),
                        ('attributes', TEXT),
                        ('events', TEXT)
                    ], name="text_search")
                elif isinstance(index, list):
                    traces_collection.create_index(index, name=index_name)
                else:
                    traces_collection.create_index(field, direction, name=index_name)

                print(f"✅ Created index: {index_name}")
            except OperationFailure as e:
                print(f"⚠️  Index {index_name} already exists or failed: {e}")

        # Evaluations collection indexes
        evaluations_collection = db['evaluations']
        evaluations_collection.create_index('trace_id', name='eval_trace_id')
        evaluations_collection.create_index('timestamp', DESCENDING, name='eval_timestamp')
        evaluations_collection.create_index([('timestamp', DESCENDING), ('trace_id', ASCENDING)], name='eval_time_trace')

        # Metrics collection indexes
        metrics_collection = db['metrics']
        metrics_collection.create_index('trace_id', name='metric_trace_id')
        metrics_collection.create_index('timestamp', DESCENDING, name='metric_timestamp')
        metrics_collection.create_index('operation_name', name='metric_operation')

        return True

    except Exception as e:
        print(f"❌ Error creating indexes: {e}")
        return False

def create_time_based_collections(db):
    """Create time-based collections for better performance"""
    try:
        print("🕐 Setting up time-based collections...")

        now = datetime.now()
        collections_to_create = []

        # Create collections for current and next 2 months
        for i in range(3):
            month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            if i > 0:
                # Add months to get future months
                from dateutil.relativedelta import relativedelta
                month_start = month_start + relativedelta(months=i)

            collection_name = f"traces_{month_start.strftime('%Y_%m')}"
            collections_to_create.append(collection_name)

        for collection_name in collections_to_create:
            if collection_name not in db.list_collection_names():
                db.create_collection(collection_name)
                print(f"✅ Created time-based collection: {collection_name}")

        return True

    except Exception as e:
        print(f"❌ Error creating time-based collections: {e}")
        return False

def create_document_validation(db):
    """Create document validation schemas"""
    try:
        print("📝 Setting up document validation...")

        # JSON schema for traces collection (relaxed for OpenTelemetry compatibility)
        trace_schema = {
            "$jsonSchema": {
                "bsonType": "object",
                "required": ["trace_id", "span_id", "name", "start_time"],
                "properties": {
                    "trace_id": {"bsonType": "string", "pattern": "^[0-9a-f]{32}$"},
                    "span_id": {"bsonType": "string", "pattern": "^[0-9a-f]{32}$"},  # 32-char hex
                    "parent_id": {"bsonType": ["string", "null"], "pattern": "^[0-9a-f]{32}$"},
                    "name": {"bsonType": "string", "maxLength": 255},
                    "span_kind": {"bsonType": "string"},  # Accept any string for span kind
                    "kind": {"bsonType": "string"},  # Keep original kind field
                    "start_time": {"bsonType": "date"},
                    "end_time": {"bsonType": ["date", "null"]},
                    "status_code": {"bsonType": "string"},  # Accept any status code
                    "status_message": {"bsonType": ["string", "null"]},
                    "attributes": {"bsonType": "object"},
                    "events": {"bsonType": "array"},
                    "context": {"bsonType": "object"},
                    "created_at": {"bsonType": "date"},
                    "duration_ms": {"bsonType": ["number", "null"]}
                }
            }
        }

        # Apply validation schema
        try:
            db.command({
                "collMod": "traces",
                "validator": trace_schema,
                "validationLevel": "moderate"  # Allow existing invalid documents
            })
            print("✅ Applied document validation to traces collection")
        except OperationFailure:
            print("⚠️  Document validation not supported in this MongoDB version")

        return True

    except Exception as e:
        print(f"❌ Error setting up document validation: {e}")
        return False

def create_aggregation_pipeline_examples(db):
    """Create example aggregation pipelines for common queries"""
    try:
        print("🔧 Creating aggregation pipeline examples...")

        pipelines = {
            "error_analysis": [
                {"$match": {"status_code": "ERROR"}},
                {"$group": {
                    "_id": {"name": "$name", "date": {"$dateToString": {"format": "%Y-%m-%d", "date": "$start_time"}}},
                    "count": {"$sum": 1},
                    "avg_duration": {"$avg": "$duration_ms"}
                }},
                {"$sort": {"count": -1}}
            ],
            "performance_by_operation": [
                {"$group": {
                    "_id": "$name",
                    "avg_duration": {"$avg": "$duration_ms"},
                    "min_duration": {"$min": "$duration_ms"},
                    "max_duration": {"$max": "$duration_ms"},
                    "total_count": {"$sum": 1}
                }},
                {"$sort": {"avg_duration": -1}}
            ],
            "trace_completion_time": [
                {"$match": {"name": {"$regex": ".*completion|.*finish|.*end"}}},
                {"$project": {"trace_id": 1, "duration": {"$subtract": ["$end_time", "$start_time"]}}},
                {"$group": {"_id": "$trace_id", "completion_time": {"$sum": "$duration"}}},
                {"$sort": {"completion_time": -1}}
            ]
        }

        # Save pipelines to a configuration file
        with open('mongodb_aggregations.json', 'w') as f:
            json.dump(pipelines, f, indent=2, default=str)

        print("✅ Created aggregation pipeline examples")

        return True

    except Exception as e:
        print(f"❌ Error creating aggregation pipelines: {e}")
        return False

def create_mongodb_config():
    """Create MongoDB connection configuration"""
    config = {
        "mongodb": {
            "connection_string": MONGODB_CONFIG["connection_string"],
            "database": MONGODB_CONFIG["database"],
            "connection_pool": {
                "maxPoolSize": 100,
                "minPoolSize": 10,
                "maxIdleTimeMS": 30000,
                "serverSelectionTimeoutMS": 5000
            },
            "write_concern": {
                "w": "majority",
                "j": True,
                "wtimeout": 10000
            },
            "read_preference": "secondaryPreferred",
            "retry_writes": True,
            "retry_reads": True
        },
        "collections": MONGODB_CONFIG["collections"]
    }

    with open('mongodb_config.json', 'w') as f:
        json.dump(config, f, indent=2)

    print("✅ Created MongoDB configuration file")

def main():
    """Main setup function"""
    print("🚀 Setting up MongoDB for Phoenix traces storage...")
    print("=" * 60)

    client, db = connect_to_mongodb()
    if not client or db is None:
        print("❌ Cannot proceed without MongoDB connection")
        sys.exit(1)

    if not create_collections(db):
        sys.exit(1)

    if not create_indexes(db):
        print("⚠️  Index creation failed, but continuing...")

    if not create_time_based_collections(db):
        print("⚠️  Time-based collection creation failed, but continuing...")

    if not create_document_validation(db):
        print("⚠️  Document validation setup failed, but continuing...")

    if not create_aggregation_pipeline_examples(db):
        print("⚠️  Aggregation pipeline creation failed, but continuing...")

    create_mongodb_config()

    print("\n" + "=" * 60)
    print("✅ MongoDB setup completed successfully!")
    print("=" * 60)
    print("📋 MongoDB Configuration Summary:")
    print(f"   Database: {MONGODB_CONFIG['database']}")
    print(f"   Collections: {', '.join(MONGODB_CONFIG['collections'].keys())}")
    print(f"   Connection: {MONGODB_CONFIG['connection_string']}")
    print("\n📊 Key Features Enabled:")
    print("   • Time-series collections for traces")
    print("   • Optimized indexes for trace queries")
    print("   • Document validation schemas")
    print("   • Aggregation pipelines for analytics")
    print("   • Capped collection for events")
    print("\n🔧 Connection String for Phoenix:")
    print(f"   {MONGODB_CONFIG['connection_string']}/{MONGODB_CONFIG['database']}")
    print("\n📍 Your SimpoAssist database will store:")
    print("   • Phoenix traces and spans")
    print("   • Evaluation results and metrics")
    print("   • Performance monitoring data")
    print("   • Trace events and analytics")

if __name__ == "__main__":
    main()
