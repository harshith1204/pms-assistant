"""
Test file for debugging tool calling in the agent system.

This tests the fundamental tool execution without full agent orchestration.
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

async def test_tool_imports():
    """Test if tools can be imported correctly"""
    print("\n=== Testing Tool Imports ===")
    try:
        from agent.tools import tools, mongo_query, rag_search, generate_content
        print("✅ Successfully imported tools from agent.tools")
        print(f"   - Found {len(tools)} tools: {[t.name for t in tools]}")
        return True
    except ImportError as e:
        print(f"❌ Failed to import from agent.tools: {e}")
        try:
            # Try legacy import path
            import tools as legacy_tools
            print("✅ Successfully imported from legacy tools module")
            print(f"   - Found {len(legacy_tools.tools)} tools: {[t.name for t in legacy_tools.tools]}")
            return True
        except ImportError as e2:
            print(f"❌ Also failed legacy import: {e2}")
            return False

async def test_mongo_query_tool():
    """Test mongo_query tool directly"""
    print("\n=== Testing mongo_query Tool ===")
    try:
        from agent.tools import mongo_query
        from mongo.constants import mongodb_tools
        
        # Connect to MongoDB first
        print("Connecting to MongoDB...")
        await mongodb_tools.connect()
        print("✅ Connected to MongoDB")
        
        # Test a simple query
        query = "Count all work items"
        print(f"Testing query: '{query}'")
        result = await mongo_query.ainvoke({"query": query, "show_all": False})
        
        print("✅ Tool executed successfully")
        print(f"Result preview: {result[:200]}...")
        
        await mongodb_tools.disconnect()
        return True
    except Exception as e:
        print(f"❌ mongo_query test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_rag_search_tool():
    """Test rag_search tool directly"""
    print("\n=== Testing rag_search Tool ===")
    try:
        from agent.tools import rag_search
        from qdrant.initializer import RAGTool
        
        # Initialize RAG
        print("Initializing RAG Tool...")
        await RAGTool.initialize()
        print("✅ RAG Tool initialized")
        
        # Test a simple search
        query = "authentication"
        print(f"Testing search: '{query}'")
        result = await rag_search.ainvoke({
            "query": query,
            "content_type": None,
            "limit": 5
        })
        
        print("✅ Tool executed successfully")
        print(f"Result preview: {result[:200]}...")
        return True
    except Exception as e:
        print(f"❌ rag_search test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_tool_binding_to_llm():
    """Test binding tools to the LLM"""
    print("\n=== Testing Tool Binding to LLM ===")
    try:
        from langchain_groq import ChatGroq
        from agent.tools import tools
        from dotenv import load_dotenv
        
        load_dotenv()
        
        llm = ChatGroq(
            model=os.getenv("GROQ_MODEL", "moonshotai/kimi-k2-instruct-0905"),
            temperature=0.1,
        )
        
        print(f"Binding {len(tools)} tools to LLM...")
        llm_with_tools = llm.bind_tools(tools)
        print("✅ Tools bound successfully to LLM")
        
        # Test a simple invocation to see if tools are recognized
        from langchain_core.messages import HumanMessage
        response = await llm_with_tools.ainvoke([
            HumanMessage(content="Count all work items in the database")
        ])
        
        print(f"✅ LLM responded with type: {type(response)}")
        print(f"   Has tool_calls: {hasattr(response, 'tool_calls')}")
        if hasattr(response, 'tool_calls') and response.tool_calls:
            print(f"   Tool calls: {len(response.tool_calls)}")
            for tc in response.tool_calls:
                print(f"     - {tc.get('name', 'unknown')}: {tc.get('args', {})}")
        else:
            print(f"   Content: {response.content[:200]}")
        
        return True
    except Exception as e:
        print(f"❌ Tool binding test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_tool_execution_from_llm_response():
    """Test executing tools based on LLM's tool call response"""
    print("\n=== Testing Tool Execution from LLM Response ===")
    try:
        from langchain_groq import ChatGroq
        from agent.tools import tools
        from langchain_core.messages import HumanMessage, SystemMessage
        from mongo.constants import mongodb_tools
        from qdrant.initializer import RAGTool
        from dotenv import load_dotenv
        
        load_dotenv()
        
        # Initialize dependencies
        print("Initializing dependencies...")
        await mongodb_tools.connect()
        await RAGTool.initialize()
        
        llm = ChatGroq(
            model=os.getenv("GROQ_MODEL", "moonshotai/kimi-k2-instruct-0905"),
            temperature=0.1,
        )
        llm_with_tools = llm.bind_tools(tools)
        
        # Create a test query that should trigger mongo_query
        messages = [
            SystemMessage(content="You are a helpful assistant. Use tools when needed."),
            HumanMessage(content="How many work items are in the database?")
        ]
        
        print("Sending query to LLM...")
        response = await llm_with_tools.ainvoke(messages)
        
        print(f"✅ LLM Response received")
        
        if hasattr(response, 'tool_calls') and response.tool_calls:
            print(f"   Found {len(response.tool_calls)} tool call(s)")
            
            for tool_call in response.tool_calls:
                tool_name = tool_call.get('name', 'unknown')
                tool_args = tool_call.get('args', {})
                print(f"\n   Executing tool: {tool_name}")
                print(f"   Arguments: {tool_args}")
                
                # Find the tool
                tool_obj = next((t for t in tools if t.name == tool_name), None)
                if tool_obj:
                    try:
                        result = await tool_obj.ainvoke(tool_args)
                        print(f"   ✅ Tool executed successfully")
                        print(f"   Result preview: {result[:200]}...")
                    except Exception as e:
                        print(f"   ❌ Tool execution failed: {e}")
                else:
                    print(f"   ❌ Tool '{tool_name}' not found")
        else:
            print("   ⚠️ No tool calls in response")
            print(f"   Content: {response.content}")
        
        await mongodb_tools.disconnect()
        return True
        
    except Exception as e:
        print(f"❌ Tool execution test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all tool tests"""
    print("=" * 60)
    print("AGENT TOOL CALLING DEBUG TEST SUITE")
    print("=" * 60)
    
    results = {}
    
    # Test 1: Import checks
    results['imports'] = await test_tool_imports()
    
    # Test 2: Direct tool execution
    if results['imports']:
        results['mongo_query'] = await test_mongo_query_tool()
        results['rag_search'] = await test_rag_search_tool()
        
        # Test 3: LLM integration
        results['tool_binding'] = await test_tool_binding_to_llm()
        results['tool_execution'] = await test_tool_execution_from_llm_response()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:20s}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    print(f"\nTotal: {passed}/{total} tests passed")
    
    return passed == total

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
