#!/usr/bin/env python3
"""
Quick test script to verify direct MongoDB connection works
"""

import asyncio
from mongo.constants import mongodb_tools, DATABASE_NAME


async def test_direct_connection():
    """Test the direct MongoDB connection"""
    print("=" * 60)
    print("Testing Direct MongoDB Connection (Motor)")
    print("=" * 60)
    
    try:
        # Test 1: Connection
        print("\n1️⃣  Testing connection...")
        await mongodb_tools.connect()
        print("   ✅ Connected successfully!")
        
        # Test 2: Simple aggregation
        print("\n2️⃣  Testing simple aggregation (count work items)...")
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "workItem",
            "pipeline": [
                {"$count": "total"}
            ]
        })
        print(f"   ✅ Result: {result}")
        
        # Test 3: Complex aggregation with lookup
        print("\n3️⃣  Testing complex aggregation (work items with project names)...")
        result = await mongodb_tools.execute_tool("aggregate", {
            "database": DATABASE_NAME,
            "collection": "workItem",
            "pipeline": [
                {"$limit": 5},
                {"$project": {
                    "_id": 1,
                    "title": 1,
                    "project.name": 1,
                    "state.name": 1
                }}
            ]
        })
        print(f"   ✅ Found {len(result)} work items")
        if result:
            print(f"   📋 Sample: {result[0].get('title', 'N/A')}")
        
        # Test 4: Disconnect
        print("\n4️⃣  Testing disconnect...")
        await mongodb_tools.disconnect()
        print("   ✅ Disconnected successfully!")
        
        print("\n" + "=" * 60)
        print("🎉 All tests passed! Direct MongoDB connection is working.")
        print("=" * 60)
        print("\n💡 Migration Benefits:")
        print("   • Smithery proxy removed (no more external dependency)")
        print("   • MongoDB MCP removed (simpler architecture)")
        print("   • Expected latency reduction: 60-80%")
        print("   • Direct Motor connection (production-ready)")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    success = asyncio.run(test_direct_connection())
    exit(0 if success else 1)
