"""
Test script for Mem0 integration

This script validates that Mem0 is properly configured and working.
Run this after setting up your .env file to verify the integration.

Usage:
    python test_mem0_integration.py
"""

import asyncio
import os
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, AIMessage

# Load environment variables
load_dotenv()

async def test_mem0_basic():
    """Test basic Mem0 functionality"""
    print("\n" + "="*60)
    print("Testing Mem0 Integration")
    print("="*60 + "\n")
    
    try:
        from mem0_integration import Mem0Manager
        print("✅ Successfully imported Mem0Manager")
    except ImportError as e:
        print(f"❌ Failed to import Mem0Manager: {e}")
        print("   Make sure to install: pip install mem0ai")
        return False
    
    # Test 1: Initialize Mem0Manager
    print("\n[Test 1] Initializing Mem0Manager...")
    try:
        manager = Mem0Manager()
        print("✅ Mem0Manager initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Mem0Manager: {e}")
        print("\nTroubleshooting:")
        print("  1. Make sure Qdrant is running:")
        print("     docker run -p 6333:6333 qdrant/qdrant")
        print("  2. Check your .env configuration")
        print("  3. Verify GROQ_API_KEY is set")
        return False
    
    # Test 2: Add messages
    print("\n[Test 2] Adding test messages...")
    try:
        test_conv_id = "test_conversation_001"
        
        # Add some test messages
        manager.add_message(
            test_conv_id,
            HumanMessage(content="What are the main features of our authentication system?"),
            user_id="test_user"
        )
        print("  ✅ Added user message")
        
        manager.add_message(
            test_conv_id,
            AIMessage(content="Our authentication system has OAuth2, JWT tokens, and 2FA support."),
            user_id="test_user"
        )
        print("  ✅ Added AI message")
        
        # Give Mem0 a moment to process
        await asyncio.sleep(2)
        
        print("✅ Messages added successfully")
    except Exception as e:
        print(f"❌ Failed to add messages: {e}")
        return False
    
    # Test 3: Retrieve recent context
    print("\n[Test 3] Retrieving recent context...")
    try:
        context = manager.get_recent_context(
            conversation_id=test_conv_id,
            max_tokens=3000
        )
        print(f"  Retrieved {len(context)} context messages")
        print("✅ Context retrieval successful")
    except Exception as e:
        print(f"❌ Failed to retrieve context: {e}")
        return False
    
    # Test 4: Search memories
    print("\n[Test 4] Searching for relevant memories...")
    try:
        memories = manager.get_relevant_memories(
            conversation_id=test_conv_id,
            query="authentication features",
            user_id="test_user",
            limit=5
        )
        print(f"  Found {len(memories)} relevant memories")
        
        if memories:
            print("\n  Sample memory:")
            memory = memories[0]
            print(f"    Content: {memory.get('memory', 'N/A')}")
            print(f"    ID: {memory.get('id', 'N/A')}")
            print("✅ Memory search successful")
        else:
            print("  ⚠️  No memories found (they may still be processing)")
            print("     Wait a few seconds and try again")
    except Exception as e:
        print(f"❌ Failed to search memories: {e}")
        return False
    
    # Test 5: Get all memories
    print("\n[Test 5] Getting all memories...")
    try:
        all_memories = manager.get_all_memories(
            conversation_id=test_conv_id,
            user_id="test_user"
        )
        print(f"  Total memories stored: {len(all_memories)}")
        print("✅ Memory retrieval successful")
    except Exception as e:
        print(f"❌ Failed to get all memories: {e}")
        return False
    
    # Test 6: Cleanup
    print("\n[Test 6] Cleaning up test data...")
    try:
        manager.delete_memories(
            conversation_id=test_conv_id,
            user_id="test_user"
        )
        print("✅ Cleanup successful")
    except Exception as e:
        print(f"❌ Failed to cleanup: {e}")
        return False
    
    print("\n" + "="*60)
    print("🎉 All tests passed! Mem0 is properly configured.")
    print("="*60 + "\n")
    return True


async def test_agent_integration():
    """Test Mem0 integration with the agent"""
    print("\n" + "="*60)
    print("Testing Agent Integration with Mem0")
    print("="*60 + "\n")
    
    try:
        from agent import conversation_memory, MongoDBAgent, USE_MEM0
        
        if not USE_MEM0:
            print("⚠️  Mem0 is disabled (USE_MEM0=false)")
            print("   Set USE_MEM0=true in .env to enable Mem0")
            return False
        
        print(f"✅ Agent is using Mem0: {USE_MEM0}")
        print(f"   Memory manager type: {type(conversation_memory).__name__}")
        
        # Test adding messages through the agent's memory
        print("\n[Test] Adding messages through agent's conversation_memory...")
        test_conv_id = "agent_test_conv_001"
        
        conversation_memory.add_message(
            test_conv_id,
            HumanMessage(content="Show me critical bugs in the authentication module"),
            user_id="test_agent_user"
        )
        print("  ✅ Added message through agent's memory manager")
        
        # Test context retrieval
        context = conversation_memory.get_recent_context(
            conversation_id=test_conv_id,
            max_tokens=2000
        )
        print(f"  ✅ Retrieved {len(context)} messages from context")
        
        # Cleanup
        conversation_memory.delete_memories(
            conversation_id=test_conv_id,
            user_id="test_agent_user"
        )
        print("  ✅ Cleaned up test data")
        
        print("\n✅ Agent integration test passed!")
        return True
        
    except ImportError as e:
        print(f"❌ Failed to import agent modules: {e}")
        return False
    except Exception as e:
        print(f"❌ Agent integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def print_configuration():
    """Print current configuration"""
    print("\n" + "="*60)
    print("Current Configuration")
    print("="*60 + "\n")
    
    config_vars = [
        ("USE_MEM0", os.getenv("USE_MEM0", "not set")),
        ("GROQ_API_KEY", "***" if os.getenv("GROQ_API_KEY") else "not set"),
        ("GROQ_MODEL", os.getenv("GROQ_MODEL", "not set")),
        ("MEM0_QDRANT_HOST", os.getenv("MEM0_QDRANT_HOST", "not set")),
        ("MEM0_QDRANT_PORT", os.getenv("MEM0_QDRANT_PORT", "not set")),
        ("MEM0_QDRANT_PATH", os.getenv("MEM0_QDRANT_PATH", "not set")),
        ("MEM0_LLM_PROVIDER", os.getenv("MEM0_LLM_PROVIDER", "not set")),
        ("MEM0_EMBEDDING_MODEL", os.getenv("MEM0_EMBEDDING_MODEL", "not set")),
    ]
    
    for var, value in config_vars:
        status = "✅" if value != "not set" else "❌"
        print(f"  {status} {var}: {value}")
    
    print()


async def main():
    """Run all tests"""
    print("\n🚀 Mem0 Integration Test Suite\n")
    
    # Check if .env exists
    if not os.path.exists(".env"):
        print("⚠️  No .env file found!")
        print("   Please create one from .env.example:")
        print("   cp .env.example .env")
        print("\n   Then configure the following variables:")
        print("   - GROQ_API_KEY")
        print("   - USE_MEM0=true")
        print("   - MEM0_QDRANT_HOST and MEM0_QDRANT_PORT")
        return
    
    # Print configuration
    print_configuration()
    
    # Run basic Mem0 tests
    basic_success = await test_mem0_basic()
    
    if not basic_success:
        print("\n❌ Basic tests failed. Fix the issues above before testing agent integration.")
        return
    
    # Run agent integration tests
    await test_agent_integration()
    
    print("\n" + "="*60)
    print("Test Suite Complete!")
    print("="*60 + "\n")
    print("Next steps:")
    print("  1. Start your application: python main.py")
    print("  2. Try having a conversation with the agent")
    print("  3. Check that memories persist across restarts")
    print("  4. Verify semantic search retrieves relevant context")
    print("\n" + "="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
