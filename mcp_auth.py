from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

# Construct server URL with authentication
from urllib.parse import urlencode
base_url = "https://server.smithery.ai/@mongodb-js/mongodb-mcp-server/mcp"
params = {"api_key": "4fd11c6a-4c6f-45ce-ab0d-24cb4c051779", "profile": "furious-lemming-rvSkqO"}
url = f"{base_url}?{urlencode(params)}"

async def main():
    # Connect to the server using HTTP client
    async with streamablehttp_client(url) as (read, write, _):
        async with ClientSession(read, write) as session:
            # Initialize the connection
            await session.initialize()
            
            # List available tools
            tools_result = await session.list_tools()
            print(f"Available tools: {', '.join([t.name for t in tools_result.tools])}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())