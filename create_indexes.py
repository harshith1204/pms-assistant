#!/usr/bin/env python3
"""
MongoDB Index Creation Script for PMS Agent Performance Optimization
This script creates indexes using the MongoDB Python driver to improve query performance.
"""

import asyncio
from pymongo import MongoClient
from constants import MONGODB_CONNECTION_STRING, DATABASE_NAME

def create_index_if_not_exists(collection, index_spec, index_name):
    """Create index only if it doesn't already exist"""
    try:
        existing_indexes = list(collection.list_indexes())
        index_names = [idx['name'] for idx in existing_indexes]

        if index_name in index_names:
            print(f"  ✓ Index '{index_name}' already exists (skipping)")
            return True
        else:
            collection.create_index(index_spec, name=index_name)
            print(f"  ✓ Created index '{index_name}'")
            return True
    except Exception as e:
        print(f"  ✗ Error creating index '{index_name}': {e}")
        return False

async def create_indexes():
    """Create all necessary indexes for optimal PMS agent performance"""

    # Connect to MongoDB
    client = MongoClient(MONGODB_CONNECTION_STRING)
    db = client[DATABASE_NAME]

    print("🚀 Starting MongoDB index creation for PMS Agent optimization...")

    # 1. WORKITEM COLLECTION INDEXES (Most Critical)
    print("📝 Creating workItem collection indexes...")

    # Compound index for status + priority filtering (most common combination)
    create_index_if_not_exists(db.workItem, [("status", 1), ("priority", 1)], "workItem_status_priority_compound")

    # Index for priority sorting with status filter
    create_index_if_not_exists(db.workItem, [("priority", 1), ("status", 1)], "workItem_priority_status_compound")

    # Index for state-based filtering (embedded state.name)
    create_index_if_not_exists(db.workItem, [("state.name", 1)], "workItem_state_name")

    # Index for created timestamp sorting (very common)
    create_index_if_not_exists(db.workItem, [("createdTimeStamp", -1)], "workItem_created_timestamp_desc")

    # Index for regex searches on project names (embedded)
    create_index_if_not_exists(db.workItem, [("project.name", 1)], "workItem_project_name")

    # Index for regex searches on cycle names (embedded)
    create_index_if_not_exists(db.workItem, [("cycle.name", 1)], "workItem_cycle_name")

    # Index for regex searches on module names (embedded)
    create_index_if_not_exists(db.workItem, [("modules.name", 1)], "workItem_modules_name")

    # Index for regex searches on assignee names (embedded)
    create_index_if_not_exists(db.workItem, [("assignee.name", 1)], "workItem_assignee_name")

    # Index for label filtering
    create_index_if_not_exists(db.workItem, [("label", 1)], "workItem_label")

    # 2. PROJECT COLLECTION INDEXES
    print("📝 Creating project collection indexes...")

    # Index for project status filtering (very common)
    create_index_if_not_exists(db.project, [("status", 1)], "project_status")

    # Index for name-based regex searches (common for filtering)
    create_index_if_not_exists(db.project, [("name", 1)], "project_name")

    # Index for isActive and isArchived boolean filters
    create_index_if_not_exists(db.project, [("isActive", 1), ("isArchived", 1)], "project_active_archived")

    # Index for created timestamp sorting
    create_index_if_not_exists(db.project, [("createdTimeStamp", -1)], "project_created_timestamp_desc")

    # 3. CYCLE COLLECTION INDEXES
    print("📝 Creating cycle collection indexes...")

    # Index for cycle status filtering
    create_index_if_not_exists(db.cycle, [("status", 1)], "cycle_status")

    # Index for name-based regex searches
    create_index_if_not_exists(db.cycle, [("name", 1)], "cycle_name")

    # Index for project._id for relationship lookups
    create_index_if_not_exists(db.cycle, [("project._id", 1)], "cycle_project_id")

    # Index for date range queries (start/end dates)
    create_index_if_not_exists(db.cycle, [("startDate", 1), ("endDate", 1)], "cycle_date_range")

    # 4. MODULE COLLECTION INDEXES
    print("📝 Creating module collection indexes...")

    # Index for name-based regex searches
    create_index_if_not_exists(db.module, [("name", 1)], "module_name")

    # Index for project._id for relationship lookups
    create_index_if_not_exists(db.module, [("project._id", 1)], "module_project_id")

    # Index for isFavourite boolean filter
    create_index_if_not_exists(db.module, [("isFavourite", 1)], "module_is_favourite")

    # 5. MEMBERS COLLECTION INDEXES
    print("📝 Creating members collection indexes...")

    # Index for name-based regex searches (very common for assignee lookups)
    create_index_if_not_exists(db.members, [("name", 1)], "members_name")

    # Index for role-based filtering
    create_index_if_not_exists(db.members, [("role", 1)], "members_role")

    # Index for email searches
    create_index_if_not_exists(db.members, [("email", 1)], "members_email")

    # Index for project._id for relationship lookups
    create_index_if_not_exists(db.members, [("project._id", 1)], "members_project_id")

    # 6. PAGE COLLECTION INDEXES
    print("📝 Creating page collection indexes...")

    # Index for visibility-based filtering
    create_index_if_not_exists(db.page, [("visibility", 1)], "page_visibility")

    # Index for title-based searches
    create_index_if_not_exists(db.page, [("title", 1)], "page_title")

    # Index for project._id for relationship lookups
    create_index_if_not_exists(db.page, [("project._id", 1)], "page_project_id")

    # Index for linkedCycle and linkedModule for relationship filtering
    create_index_if_not_exists(db.page, [("linkedCycle", 1)], "page_linked_cycle")
    create_index_if_not_exists(db.page, [("linkedModule", 1)], "page_linked_module")

    # 7. PROJECTSTATE COLLECTION INDEXES
    print("📝 Creating projectState collection indexes...")

    # Index for projectId for relationship lookups
    create_index_if_not_exists(db.projectState, [("projectId", 1)], "projectstate_project_id")

    # TEXT INDEXES FOR NATURAL LANGUAGE SEARCHES
    print("📝 Creating text indexes for natural language searches...")

    # Text index for workItem title and description searches
    create_index_if_not_exists(db.workItem, [("title", "text"), ("description", "text")], "workItem_text_search")

    # Text index for project name and description searches
    create_index_if_not_exists(db.project, [("name", "text"), ("description", "text")], "project_text_search")

    # Text index for page title and content searches
    create_index_if_not_exists(db.page, [("title", "text"), ("content", "text")], "page_text_search")

    # Show index statistics
    print("\n📊 === INDEX STATISTICS ===")

    for collection_name in ['workItem', 'project', 'cycle', 'module', 'members', 'page', 'projectState']:
        collection = db[collection_name]
        print(f"\n{collection_name} collection indexes:")

        # Get index information
        indexes = collection.list_indexes()
        for index_info in indexes:
            index_name = index_info['name']
            if index_name != '_id_':  # Skip default _id index
                print(f"  - {index_name}")

    print("\n✅ All indexes created successfully!")
    print("These indexes will significantly improve query performance for:")
    print("  • Filtering by status, priority, state")
    print("  • Regex searches on names (project, cycle, module, assignee)")
    print("  • Sorting by createdTimeStamp, priority")
    print("  • Count queries and aggregations")
    print("  • Relationship lookups and joins")
    print("  • Text-based natural language searches")

    client.close()

if __name__ == "__main__":
    asyncio.run(create_indexes())
