#!/usr/bin/env python3
"""
Test script to verify business and member filtering is working correctly.

This script helps you test if the BUSINESS_UUID and MEMBER_UUID environment 
variables are set correctly and if the filtering logic is working.
"""

import asyncio
import os
from mongo.client import direct_mongo_client
from mongo.constants import DATABASE_NAME, uuid_str_to_mongo_binary

async def test_filters():
    """Test business and member filtering with current environment variables"""
    
    print("=" * 80)
    print("BUSINESS & MEMBER FILTER TEST")
    print("=" * 80)
    
    # Check environment variables
    business_uuid = os.getenv("BUSINESS_UUID", "")
    member_uuid = os.getenv("MEMBER_UUID", "") or os.getenv("STAFF_ID", "")
    
    print("\n📋 Environment Variables:")
    print(f"   BUSINESS_UUID: {business_uuid or '(not set)'}")
    print(f"   MEMBER_UUID:   {member_uuid or '(not set)'}")
    print(f"   STAFF_ID:      {os.getenv('STAFF_ID', '(not set)')}")
    
    # Validate UUID format
    print("\n🔍 UUID Validation:")
    if business_uuid:
        try:
            uuid_str_to_mongo_binary(business_uuid)
            print(f"   ✅ BUSINESS_UUID is valid UUID format")
        except Exception as e:
            print(f"   ❌ BUSINESS_UUID is INVALID: {e}")
            print(f"      Expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
    else:
        print(f"   ⚠️  BUSINESS_UUID not set - no business filtering will occur")
    
    if member_uuid:
        try:
            uuid_str_to_mongo_binary(member_uuid)
            print(f"   ✅ MEMBER_UUID is valid UUID format")
        except Exception as e:
            print(f"   ❌ MEMBER_UUID is INVALID: {e}")
            print(f"      Expected format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
    else:
        print(f"   ⚠️  MEMBER_UUID not set - no member filtering will occur")
    
    # Connect to MongoDB
    print("\n🔌 Connecting to MongoDB...")
    try:
        await direct_mongo_client.connect()
        print("   ✅ Connected successfully")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        return
    
    # Test queries
    print("\n📊 Testing Queries:")
    
    # Test 1: Query members collection
    print("\n1️⃣  Testing MEMBERS collection:")
    try:
        members = await direct_mongo_client.aggregate(
            database=DATABASE_NAME,
            collection="members",
            pipeline=[{"$limit": 5}]
        )
        print(f"   ✅ Found {len(members)} member(s)")
        if members:
            for i, member in enumerate(members, 1):
                print(f"      {i}. {member.get('name', 'Unknown')} ({member.get('email', 'no email')})")
                if 'project' in member:
                    print(f"         Project: {member['project'].get('name', 'Unknown')}")
        else:
            print("   ⚠️  No members returned - check if:")
            print("      - BUSINESS_UUID matches a business in your database")
            print("      - MEMBER_UUID matches a staff member in your database")
            print("      - The member has access to projects in this business")
    except Exception as e:
        print(f"   ❌ Query failed: {e}")
    
    # Test 2: Query projects with business filter
    print("\n2️⃣  Testing PROJECT collection (with business filter):")
    try:
        projects = await direct_mongo_client.aggregate(
            database=DATABASE_NAME,
            collection="project",
            pipeline=[{"$limit": 5}]
        )
        print(f"   ✅ Found {len(projects)} project(s)")
        if projects:
            for i, proj in enumerate(projects, 1):
                biz_name = proj.get('business', {}).get('name', 'Unknown')
                print(f"      {i}. {proj.get('name', 'Unknown')} (Business: {biz_name})")
        else:
            print("   ⚠️  No projects returned - check if:")
            print("      - BUSINESS_UUID matches a business in your database")
            print("      - MEMBER_UUID has access to projects")
    except Exception as e:
        print(f"   ❌ Query failed: {e}")
    
    # Test 3: Count total without filters (raw query)
    print("\n3️⃣  Testing raw counts (no RBAC filters):")
    try:
        # Temporarily disable filters by not using the client
        from motor.motor_asyncio import AsyncIOMotorClient
        from mongo.constants import MONGODB_CONNECTION_STRING
        
        raw_client = AsyncIOMotorClient(MONGODB_CONNECTION_STRING)
        db = raw_client[DATABASE_NAME]
        
        total_members = await db.members.count_documents({})
        total_projects = await db.project.count_documents({})
        
        print(f"   Total members in DB:  {total_members}")
        print(f"   Total projects in DB: {total_projects}")
        
        raw_client.close()
    except Exception as e:
        print(f"   ❌ Raw count failed: {e}")
    
    print("\n" + "=" * 80)
    print("💡 RECOMMENDATIONS:")
    print("=" * 80)
    
    if not business_uuid:
        print("1. Set BUSINESS_UUID environment variable to a valid UUID from your database")
        print("   Example: export BUSINESS_UUID='4e6064c5-0539-071f-685f-e342651963ac'")
        print("   (Get this from one of your business documents)")
    
    if not member_uuid:
        print("2. Set MEMBER_UUID or STAFF_ID to a valid staff member UUID")
        print("   Example: export MEMBER_UUID='ce64c003-378b-fd1e-db34-e30804c95fda'")
        print("   (Get this from the staff._id field in a members document)")
    
    print("\n✅ Test complete!")
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(test_filters())
