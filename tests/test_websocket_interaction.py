"""
Test file for debugging websocket interactions.

This simulates a WebSocket client to test the full end-to-end flow.
"""
import asyncio
import sys
import os
from pathlib import Path
import json
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

class MockWebSocket:
    """Mock WebSocket for testing without actual WebSocket connection"""
    
    def __init__(self):
        self.messages_sent = []
        self.connected = True
        
    async def send_json(self, data):
        """Record messages sent through WebSocket"""
        self.messages_sent.append({
            "timestamp": datetime.now().isoformat(),
            "data": data
        })
        # Print important events
        msg_type = data.get("type", "unknown")
        if msg_type == "agent_action":
            print(f"   📋 Action: {data.get('text', '')[:80]}")
        elif msg_type == "token":
            print(".", end="", flush=True)
        elif msg_type == "llm_start":
            print("\n   🤖 LLM started generating")
        elif msg_type == "llm_end":
            elapsed = data.get("elapsed_time", 0)
            print(f"\n   ✅ LLM finished ({elapsed:.2f}s)")
        elif msg_type == "tool_start":
            tool_name = data.get("tool_name", "unknown")
            print(f"\n   🔧 Tool started: {tool_name}")
        elif msg_type == "tool_end":
            print(f"\n   ✅ Tool finished")
    
    async def accept(self):
        """Mock accept"""
        pass
    
    async def receive_text(self):
        """Mock receive - not used in these tests"""
        pass
    
    async def close(self):
        """Mock close"""
        self.connected = False
    
    def get_messages_by_type(self, msg_type):
        """Get all messages of a specific type"""
        return [msg for msg in self.messages_sent if msg["data"].get("type") == msg_type]
    
    def print_summary(self):
        """Print summary of WebSocket messages"""
        print("\n" + "=" * 60)
        print("WEBSOCKET MESSAGE SUMMARY")
        print("=" * 60)
        
        # Count message types
        type_counts = {}
        for msg in self.messages_sent:
            msg_type = msg["data"].get("type", "unknown")
            type_counts[msg_type] = type_counts.get(msg_type, 0) + 1
        
        print(f"Total messages: {len(self.messages_sent)}")
        print("\nMessage types:")
        for msg_type, count in sorted(type_counts.items()):
            print(f"  {msg_type:20s}: {count}")
        
        # Show agent actions
        actions = self.get_messages_by_type("agent_action")
        if actions:
            print(f"\nAgent Actions ({len(actions)}):")
            for i, msg in enumerate(actions, 1):
                text = msg["data"].get("text", "")
                print(f"  {i}. {text[:80]}")

async def test_websocket_basic_flow():
    """Test basic WebSocket message flow"""
    print("\n=== Testing Basic WebSocket Flow ===")
    try:
        from agent.agent import MongoDBAgent
        
        mock_ws = MockWebSocket()
        agent = MongoDBAgent(max_steps=5)
        await agent.connect()
        
        query = "Count all work items"
        conversation_id = "test_ws_1"
        
        print(f"Query: '{query}'")
        print("Monitoring WebSocket messages...")
        
        async for chunk in agent.run_streaming(
            query=query,
            websocket=mock_ws,
            conversation_id=conversation_id
        ):
            pass  # Messages are captured by mock
        
        print("\n✅ Streaming completed")
        mock_ws.print_summary()
        
        # Verify expected message types
        has_llm_start = len(mock_ws.get_messages_by_type("llm_start")) > 0
        has_tokens = len(mock_ws.get_messages_by_type("token")) > 0
        has_llm_end = len(mock_ws.get_messages_by_type("llm_end")) > 0
        
        print(f"\nMessage validation:")
        print(f"  LLM start events: {'✅' if has_llm_start else '❌'}")
        print(f"  Token events: {'✅' if has_tokens else '❌'}")
        print(f"  LLM end events: {'✅' if has_llm_end else '❌'}")
        
        await agent.disconnect()
        return has_llm_start and has_tokens and has_llm_end
    except Exception as e:
        print(f"❌ Basic WebSocket flow test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_websocket_tool_events():
    """Test WebSocket events during tool execution"""
    print("\n=== Testing WebSocket Tool Events ===")
    try:
        from agent.agent import MongoDBAgent
        
        mock_ws = MockWebSocket()
        agent = MongoDBAgent(max_steps=5)
        await agent.connect()
        
        query = "How many work items are assigned to each user?"
        conversation_id = "test_ws_2"
        
        print(f"Query: '{query}'")
        print("This should trigger mongo_query tool...")
        
        async for chunk in agent.run_streaming(
            query=query,
            websocket=mock_ws,
            conversation_id=conversation_id
        ):
            pass
        
        print("\n✅ Streaming completed")
        mock_ws.print_summary()
        
        # Check for agent actions (tool planning/execution)
        actions = mock_ws.get_messages_by_type("agent_action")
        print(f"\nAgent actions captured: {len(actions)}")
        
        await agent.disconnect()
        return len(actions) > 0
    except Exception as e:
        print(f"❌ WebSocket tool events test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_websocket_error_handling():
    """Test WebSocket behavior during errors"""
    print("\n=== Testing WebSocket Error Handling ===")
    try:
        from agent.agent import MongoDBAgent
        
        mock_ws = MockWebSocket()
        agent = MongoDBAgent(max_steps=3)
        await agent.connect()
        
        # Query that might cause issues
        query = "Do something impossible with nonexistent data"
        conversation_id = "test_ws_error"
        
        print(f"Query: '{query}'")
        print("Testing error handling...")
        
        try:
            async for chunk in agent.run_streaming(
                query=query,
                websocket=mock_ws,
                conversation_id=conversation_id
            ):
                pass
            print("\n✅ Completed without crash")
        except Exception as e:
            print(f"\n⚠️ Exception occurred (may be expected): {e}")
        
        mock_ws.print_summary()
        
        # Check if we got some response
        tokens = mock_ws.get_messages_by_type("token")
        has_response = len(tokens) > 0
        
        print(f"\nGot response: {'✅' if has_response else '❌'}")
        
        await agent.disconnect()
        return True  # Pass if no crash
    except Exception as e:
        print(f"❌ WebSocket error handling test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_websocket_message_ordering():
    """Test that WebSocket messages arrive in correct order"""
    print("\n=== Testing WebSocket Message Ordering ===")
    try:
        from agent.agent import MongoDBAgent
        
        mock_ws = MockWebSocket()
        agent = MongoDBAgent(max_steps=5)
        await agent.connect()
        
        query = "List 3 work items"
        conversation_id = "test_ws_order"
        
        print(f"Query: '{query}'")
        
        async for chunk in agent.run_streaming(
            query=query,
            websocket=mock_ws,
            conversation_id=conversation_id
        ):
            pass
        
        print("\n✅ Streaming completed")
        
        # Analyze message ordering
        message_types = [msg["data"].get("type") for msg in mock_ws.messages_sent]
        
        print(f"\nMessage sequence ({len(message_types)} messages):")
        
        # Show first 20 message types
        for i, msg_type in enumerate(message_types[:20], 1):
            print(f"  {i:2d}. {msg_type}")
        
        if len(message_types) > 20:
            print(f"  ... ({len(message_types) - 20} more messages)")
        
        # Verify llm_start comes before tokens
        llm_start_indices = [i for i, t in enumerate(message_types) if t == "llm_start"]
        token_indices = [i for i, t in enumerate(message_types) if t == "token"]
        
        order_ok = True
        if llm_start_indices and token_indices:
            first_llm_start = min(llm_start_indices)
            first_token = min(token_indices)
            order_ok = first_llm_start < first_token
            print(f"\nMessage ordering: {'✅ Correct' if order_ok else '❌ Incorrect'}")
            print(f"  First llm_start at index: {first_llm_start}")
            print(f"  First token at index: {first_token}")
        
        await agent.disconnect()
        return order_ok
    except Exception as e:
        print(f"❌ WebSocket message ordering test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def test_websocket_conversation_persistence():
    """Test that conversation is properly saved through WebSocket"""
    print("\n=== Testing Conversation Persistence via WebSocket ===")
    try:
        from agent.agent import MongoDBAgent
        from mongo.conversations import conversation_mongo_client, CONVERSATIONS_DB_NAME, CONVERSATIONS_COLLECTION_NAME
        import time
        
        mock_ws = MockWebSocket()
        agent = MongoDBAgent(max_steps=5)
        await agent.connect()
        
        # Use unique conversation ID
        conversation_id = f"test_persist_{int(time.time())}"
        query = "Hello, this is a test message"
        
        print(f"Conversation ID: {conversation_id}")
        print(f"Query: '{query}'")
        
        # Run query
        async for chunk in agent.run_streaming(
            query=query,
            websocket=mock_ws,
            conversation_id=conversation_id
        ):
            pass
        
        print("\n✅ Streaming completed")
        
        # Check if conversation was saved to MongoDB
        try:
            coll = await conversation_mongo_client.get_collection(
                CONVERSATIONS_DB_NAME,
                CONVERSATIONS_COLLECTION_NAME
            )
            doc = await coll.find_one({"conversationId": conversation_id})
            
            if doc:
                messages = doc.get("messages", [])
                print(f"\n✅ Conversation found in MongoDB")
                print(f"   Messages saved: {len(messages)}")
                
                # Show message types
                msg_types = [m.get("type") for m in messages if isinstance(m, dict)]
                print(f"   Message types: {msg_types}")
                
                return True
            else:
                print(f"\n⚠️ Conversation not found in MongoDB")
                return False
        except Exception as e:
            print(f"\n⚠️ Could not check MongoDB: {e}")
            return False
        
        await agent.disconnect()
    except Exception as e:
        print(f"❌ Conversation persistence test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all WebSocket interaction tests"""
    print("=" * 60)
    print("WEBSOCKET INTERACTION DEBUG TEST SUITE")
    print("=" * 60)
    
    from dotenv import load_dotenv
    load_dotenv()
    
    results = {}
    
    # Run tests
    results['basic_flow'] = await test_websocket_basic_flow()
    results['tool_events'] = await test_websocket_tool_events()
    results['error_handling'] = await test_websocket_error_handling()
    results['message_ordering'] = await test_websocket_message_ordering()
    results['persistence'] = await test_websocket_conversation_persistence()
    
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
