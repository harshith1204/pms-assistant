"""Test WebSocket streaming functionality"""
import asyncio
import websockets
import json
import time

async def test_websocket_chat():
    """Test the WebSocket chat endpoint"""
    uri = "ws://localhost:8000/ws/chat"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket server")
            
            # Wait for connection confirmation
            response = await websocket.recv()
            data = json.loads(response)
            print(f"Connection confirmed: {data}")
            
            # Test queries
            queries = [
                "List all collections in the ProjectManagement database",
                "What databases are available?",
                "Tell me about the project management system"
            ]
            
            for query in queries:
                print(f"\n{'='*50}")
                print(f"Sending query: {query}")
                print(f"{'='*50}")
                
                # Send message
                await websocket.send(json.dumps({
                    "type": "message",
                    "message": query
                }))
                
                # Track timing
                start_time = time.time()
                tokens = []
                
                # Receive streaming response
                while True:
                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                        data = json.loads(response)
                        
                        if data["type"] == "token":
                            # Collect tokens for display
                            tokens.append(data["content"])
                            print(data["content"], end="", flush=True)
                            
                        elif data["type"] == "llm_start":
                            print("\n[LLM Started]")
                            
                        elif data["type"] == "llm_end":
                            elapsed = data.get("elapsed_time", 0)
                            print(f"\n[LLM Completed in {elapsed:.2f}s]")
                            
                        elif data["type"] == "tool_start":
                            print(f"\n[Tool: {data['tool_name']} started]")
                            
                        elif data["type"] == "tool_end":
                            print(f"\n[Tool output: {data['output'][:100]}...]")
                            
                        elif data["type"] == "complete":
                            total_time = time.time() - start_time
                            print(f"\n[Response completed in {total_time:.2f}s]")
                            print(f"[Total tokens: {len(tokens)}]")
                            break
                            
                        elif data["type"] == "error":
                            print(f"\n[Error: {data.get('message', 'Unknown error')}]")
                            break
                            
                    except asyncio.TimeoutError:
                        print("\n[Timeout waiting for response]")
                        break
                
                # Small delay between queries
                await asyncio.sleep(1)
                
    except Exception as e:
        print(f"Error: {e}")

async def main():
    """Main test function"""
    print("Testing WebSocket streaming functionality...")
    print("Make sure the backend server is running on http://localhost:8000")
    print()
    
    await test_websocket_chat()

if __name__ == "__main__":
    asyncio.run(main())