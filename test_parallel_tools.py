#!/usr/bin/env python3
"""
Test script to demonstrate parallel tool execution in the MongoDB Agent.

This script shows the performance difference between parallel and sequential tool execution.
"""

import asyncio
import time
from agent import MongoDBAgent

async def test_parallel_execution():
    """Test parallel tool execution performance"""
    
    # Test queries that should trigger multiple tools
    test_queries = [
        "Count work items by state AND show me recent pages about authentication",
        "List all projects AND search for OAuth documentation",
        "Show me bugs grouped by priority AND find API-related notes",
        "Count total work items AND list members AND search for microservices pages"
    ]
    
    print("=" * 80)
    print("PARALLEL TOOL EXECUTION TEST")
    print("=" * 80)
    
    # Test with parallel execution ENABLED
    print("\n📊 TEST 1: Parallel Execution ENABLED")
    print("-" * 80)
    agent_parallel = MongoDBAgent(enable_parallel_tools=True)
    await agent_parallel.connect()
    
    parallel_times = []
    for i, query in enumerate(test_queries, 1):
        print(f"\n[Query {i}] {query}")
        start = time.time()
        try:
            result = await agent_parallel.run(query, conversation_id=f"parallel_test_{i}")
            elapsed = time.time() - start
            parallel_times.append(elapsed)
            print(f"⏱️  Time: {elapsed:.3f}s")
            print(f"✅ Result preview: {result[:200]}..." if len(result) > 200 else f"✅ Result: {result}")
        except Exception as e:
            elapsed = time.time() - start
            parallel_times.append(elapsed)
            print(f"❌ Error: {e}")
            print(f"⏱️  Time: {elapsed:.3f}s")
    
    await agent_parallel.disconnect()
    
    # Test with parallel execution DISABLED
    print("\n\n📊 TEST 2: Parallel Execution DISABLED (Sequential)")
    print("-" * 80)
    agent_sequential = MongoDBAgent(enable_parallel_tools=False)
    await agent_sequential.connect()
    
    sequential_times = []
    for i, query in enumerate(test_queries, 1):
        print(f"\n[Query {i}] {query}")
        start = time.time()
        try:
            result = await agent_sequential.run(query, conversation_id=f"sequential_test_{i}")
            elapsed = time.time() - start
            sequential_times.append(elapsed)
            print(f"⏱️  Time: {elapsed:.3f}s")
            print(f"✅ Result preview: {result[:200]}..." if len(result) > 200 else f"✅ Result: {result}")
        except Exception as e:
            elapsed = time.time() - start
            sequential_times.append(elapsed)
            print(f"❌ Error: {e}")
            print(f"⏱️  Time: {elapsed:.3f}s")
    
    await agent_sequential.disconnect()
    
    # Performance comparison
    print("\n\n" + "=" * 80)
    print("PERFORMANCE COMPARISON")
    print("=" * 80)
    
    total_parallel = sum(parallel_times)
    total_sequential = sum(sequential_times)
    improvement = ((total_sequential - total_parallel) / total_sequential * 100) if total_sequential > 0 else 0
    
    print(f"\n📈 Total Execution Time:")
    print(f"   Parallel:   {total_parallel:.3f}s")
    print(f"   Sequential: {total_sequential:.3f}s")
    print(f"   Improvement: {improvement:.1f}% faster")
    
    print(f"\n📊 Per-Query Comparison:")
    for i, (p_time, s_time) in enumerate(zip(parallel_times, sequential_times), 1):
        query_improvement = ((s_time - p_time) / s_time * 100) if s_time > 0 else 0
        print(f"   Query {i}: {p_time:.3f}s (parallel) vs {s_time:.3f}s (sequential) → {query_improvement:.1f}% faster")
    
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)

async def test_streaming_parallel():
    """Test parallel execution in streaming mode"""
    
    print("\n\n" + "=" * 80)
    print("STREAMING MODE TEST")
    print("=" * 80)
    
    agent = MongoDBAgent(enable_parallel_tools=True)
    await agent.connect()
    
    query = "Count work items AND search for authentication pages"
    print(f"\n🔄 Query: {query}")
    print("-" * 80)
    
    start = time.time()
    full_response = ""
    
    async for chunk in agent.run_streaming(query, websocket=None, conversation_id="stream_test"):
        print(chunk, end="", flush=True)
        full_response += chunk
    
    elapsed = time.time() - start
    print(f"\n\n⏱️  Streaming completed in {elapsed:.3f}s")
    
    await agent.disconnect()

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════════════════════════╗
    ║                   PARALLEL TOOL EXECUTION TEST SUITE                         ║
    ║                                                                              ║
    ║  This script demonstrates the performance benefits of parallel tool         ║
    ║  execution in the MongoDB Agent.                                            ║
    ║                                                                              ║
    ║  Features tested:                                                           ║
    ║  • Parallel vs Sequential execution comparison                              ║
    ║  • Multi-tool query performance                                             ║
    ║  • Streaming mode with parallel tools                                       ║
    ║  • Error handling in parallel execution                                     ║
    ╚══════════════════════════════════════════════════════════════════════════════╝
    """)
    
    # Run tests
    asyncio.run(test_parallel_execution())
    asyncio.run(test_streaming_parallel())
    
    print("\n✨ All tests completed!")
