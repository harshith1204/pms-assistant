#!/usr/bin/env python3
"""
Test script to demonstrate context-aware tool execution in the MongoDB Agent.
"""

import asyncio
from agent import MongoDBAgent

async def test_queries():
    """Test various queries to show parallel vs sequential execution."""
    agent = MongoDBAgent()
    await agent.connect()
    
    test_cases = [
        # Should execute sequentially (dependency markers)
        {
            "query": "First find all work items assigned to John, then search for documentation about those items",
            "expected": "SEQUENTIAL"
        },
        # Should execute sequentially (ordered operations)
        {
            "query": "List work items step by step: first get open bugs, then find their assignees",
            "expected": "SEQUENTIAL"
        },
        # Should execute in parallel (comparison)
        {
            "query": "Compare work items vs documentation pages for the auth project",
            "expected": "PARALLEL"
        },
        # Should execute in parallel (multiple independent searches)
        {
            "query": "Show me both bug counts and feature counts in parallel",
            "expected": "PARALLEL"
        },
        # Should execute in parallel (explicit marker)
        {
            "query": "Simultaneously search for API documentation and database schema pages",
            "expected": "PARALLEL"
        },
        # Should execute sequentially (result dependency)
        {
            "query": "Find high priority bugs and use the results to search for related documentation",
            "expected": "SEQUENTIAL"
        },
        # Should execute in parallel (independent RAG searches)
        {
            "query": "Find all OAuth documentation and all authentication work items",
            "expected": "PARALLEL"
        }
    ]
    
    print("🧪 Testing Context-Aware Tool Execution\n")
    print("=" * 80)
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n📝 Test Case {i}: {test['expected']} execution expected")
        print(f"Query: {test['query']}")
        print("-" * 80)
        
        try:
            # Run the query - the agent will print the execution strategy
            result = await agent.run(test['query'])
            print(f"\n✅ Result preview: {result[:200]}...")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        
        print("\n" + "=" * 80)
        
        # Small delay between tests
        await asyncio.sleep(1)
    
    await agent.disconnect()
    print("\n✨ Test completed!")

if __name__ == "__main__":
    asyncio.run(test_queries())