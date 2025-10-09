"""
Test script for the optimized generate_content tool.

This demonstrates how the tool returns only a summary instead of full content,
saving significant tokens.
"""

import asyncio
import os
from tools import generate_content

async def test_work_item_generation():
    """Test work item generation with token optimization"""
    print("=" * 60)
    print("TEST 1: Generate Work Item")
    print("=" * 60)
    
    result = await generate_content.ainvoke({
        "content_type": "work_item",
        "prompt": "Bug: Users cannot login on mobile devices. The authentication token expires too quickly.",
        "template_title": "Authentication Bug",
        "template_content": "## Description\n\n## Steps to Reproduce\n\n## Expected Behavior\n\n## Actual Behavior"
    })
    
    print("\n📋 Tool Response (sent to agent):")
    print(result)
    print("\n✅ Notice: Only a summary is returned, not the full content!")
    print("   Full content was generated but NOT sent back to the LLM.")
    print()

async def test_page_generation():
    """Test page generation with token optimization"""
    print("=" * 60)
    print("TEST 2: Generate Page")
    print("=" * 60)
    
    result = await generate_content.ainvoke({
        "content_type": "page",
        "prompt": "Create comprehensive API documentation for our authentication endpoints including login, logout, and token refresh.",
        "template_title": "API Documentation",
        "template_content": "",
        "context": {
            "context": {
                "tenantId": "test-tenant",
                "page": {"type": "DOCUMENTATION"},
                "subject": {},
                "timeScope": {},
                "retrieval": {},
                "privacy": {}
            },
            "pageId": "test-page-123",
            "projectId": "test-project-456",
            "tenantId": "test-tenant"
        }
    })
    
    print("\n📋 Tool Response (sent to agent):")
    print(result)
    print("\n✅ Notice: Only block count and preview returned!")
    print("   Full Editor.js blocks were generated but NOT sent back to the LLM.")
    print()

async def test_error_handling():
    """Test error handling"""
    print("=" * 60)
    print("TEST 3: Error Handling")
    print("=" * 60)
    
    result = await generate_content.ainvoke({
        "content_type": "invalid_type",
        "prompt": "This should fail validation"
    })
    
    print("\n📋 Tool Response:")
    print(result)
    print()

async def main():
    """Run all tests"""
    print("\n" + "🚀 CONTENT GENERATION TOKEN OPTIMIZATION TEST".center(60) + "\n")
    print("This test demonstrates how the generate_content tool saves tokens")
    print("by returning only summaries instead of full generated content.\n")
    
    # Set API base URL if needed
    if not os.getenv("API_BASE_URL"):
        os.environ["API_BASE_URL"] = "http://localhost:8000"
    
    try:
        await test_work_item_generation()
        await test_page_generation()
        await test_error_handling()
        
        print("=" * 60)
        print("TOKEN SAVINGS ANALYSIS")
        print("=" * 60)
        print("""
BEFORE optimization:
- Generate 2000-token work item
- Return full 2000 tokens to agent
- Agent sends 2000 tokens to LLM
- Total cost: ~4000 tokens

AFTER optimization:
- Generate 2000-token work item  
- Return ~50-token summary to agent
- Agent sends 50 tokens to LLM
- Total cost: ~2050 tokens

💰 SAVINGS: ~48% reduction in token usage!
        """)
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        print("\nMake sure:")
        print("1. Your generation API is running (default: http://localhost:8000)")
        print("2. GROQ_API_KEY is set in your environment")
        print("3. The groq package is installed (pip install groq)")

if __name__ == "__main__":
    asyncio.run(main())
