"""
Example client for the MongoDB Insights Agent
Demonstrates both HTTP and WebSocket usage
"""

import asyncio
import aiohttp
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000/ws/insights"

# Example queries for PM/Engineering Managers
EXAMPLE_QUERIES = [
    "What's the average cycle time by team in the last 30 days?",
    "Top 5 blockers this quarter by frequency and median time-to-unblock",
    "Show me bug escape rate trends by component",
    "Which tickets have been in 'In Review' status for more than 3 days?",
    "Sprint velocity comparison across teams for the last 4 sprints",
]

async def test_http_endpoint():
    """Test the /ask HTTP endpoint"""
    print("\n=== Testing HTTP Endpoint ===\n")
    
    async with aiohttp.ClientSession() as session:
        for query in EXAMPLE_QUERIES[:2]:  # Test first 2 queries
            print(f"Query: {query}")
            
            async with session.post(
                f"{BASE_URL}/ask",
                json={"message": query}
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    print(f"Insights:\n{result['insights']}\n")
                else:
                    print(f"Error: {response.status} - {await response.text()}\n")
                    
            await asyncio.sleep(1)  # Be nice to the server

async def test_websocket_streaming():
    """Test the WebSocket streaming endpoint"""
    print("\n=== Testing WebSocket Streaming ===\n")
    
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            # Send a query
            query = EXAMPLE_QUERIES[2]  # Bug escape rate query
            print(f"Query: {query}\n")
            
            await ws.send_json({
                "query": query,
                "conversation_id": f"demo-{datetime.now().isoformat()}"
            })
            
            # Receive streaming updates
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    event = json.loads(msg.data)
                    
                    if event["type"] == "plan_start":
                        print("📋 Planning tasks...")
                        
                    elif event["type"] == "plan_complete":
                        print(f"✅ Plan complete: {len(event['tasks'])} tasks")
                        for task in event["tasks"]:
                            print(f"   - [{task['id']}] {task['description']}")
                            
                    elif event["type"] == "task_start":
                        print(f"🔄 Executing {event['task_id']}: {event['description']}")
                        
                    elif event["type"] == "task_complete":
                        status = "✅" if event["success"] else "❌"
                        print(f"{status} {event['task_id']} complete")
                        
                    elif event["type"] == "synthesis_start":
                        print("🧠 Synthesizing insights...")
                        
                    elif event["type"] == "complete":
                        print(f"\n📊 Final Insights:\n{event['insights']}\n")
                        break
                        
                    elif event["type"] == "error":
                        print(f"❌ Error: {event['message']}")
                        break
                        
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(f"WebSocket error: {ws.exception()}")
                    break

async def interactive_mode():
    """Interactive mode - type your own queries"""
    print("\n=== Interactive Mode ===")
    print("Type your queries (or 'quit' to exit):\n")
    
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(WS_URL) as ws:
            while True:
                query = input("\n> ")
                if query.lower() in ["quit", "exit", "q"]:
                    break
                    
                if not query.strip():
                    continue
                    
                # Send query
                await ws.send_json({"query": query})
                
                # Receive response
                print("\nProcessing...\n")
                
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        event = json.loads(msg.data)
                        
                        if event["type"] == "plan_complete":
                            print(f"📋 Created {len(event['tasks'])} tasks")
                            
                        elif event["type"] == "task_complete":
                            print(f"{'✅' if event['success'] else '❌'} Task {event['task_id']}")
                            
                        elif event["type"] == "complete":
                            print(f"\n📊 Insights:\n{event['insights']}")
                            break
                            
                        elif event["type"] == "error":
                            print(f"❌ Error: {event['message']}")
                            break

async def main():
    """Run all tests"""
    print("MongoDB Insights Agent - Example Client")
    print("=" * 50)
    
    try:
        # Test HTTP endpoint
        await test_http_endpoint()
        
        # Test WebSocket streaming
        await test_websocket_streaming()
        
        # Interactive mode
        interactive = input("\nEnter interactive mode? (y/n): ")
        if interactive.lower() == 'y':
            await interactive_mode()
            
    except aiohttp.ClientError as e:
        print(f"\n❌ Connection error: {e}")
        print("Make sure the server is running on http://localhost:8000")
    except KeyboardInterrupt:
        print("\n\nGoodbye!")

if __name__ == "__main__":
    asyncio.run(main())