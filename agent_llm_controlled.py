"""
Alternative approach: Let the LLM control execution strategy explicitly
"""

# Alternative System Prompt that asks LLM to specify dependencies
ALTERNATIVE_SYSTEM_PROMPT = (
    "You are a precise, non-speculative Project Management assistant.\n\n"
    "GENERAL RULES:\n"
    "- Never guess facts about the database or content. Prefer invoking a tool.\n"
    "- If a tool is appropriate, always call it before answering.\n"
    "- Keep answers concise and structured.\n\n"
    
    "TOOL EXECUTION PLANNING:\n"
    "When calling multiple tools, you MUST indicate execution order:\n"
    "1. If tools can run independently (parallel), call them in any order\n"
    "2. If one tool needs another's output (sequential), call them in dependency order\n\n"
    
    "EXAMPLES:\n"
    "- Independent tools: 'Find all bugs' + 'Find all features' → Can run in parallel\n"
    "- Dependent tools: 'Find bugs by John' then 'Search docs about those bugs' → Must run sequentially\n\n"
    
    "IMPORTANT: When a tool needs another tool's output, you must:\n"
    "1. Call the first tool\n"
    "2. Wait for its result\n"
    "3. Use that result to call the second tool\n"
    "This ensures proper sequential execution.\n\n"
    
    "TOOL GUIDE:\n"
    "- mongo_query: Database queries (counts, filters, etc.)\n"
    "- rag_search: Content/semantic searches\n"
    "- rag_mongo: Semantic search + full MongoDB records\n"
)

# Alternative approach: Use a custom tool schema that includes dependencies
from typing import List, Optional, Dict, Any

class ToolCallWithDependencies:
    """Enhanced tool call that can specify dependencies"""
    def __init__(self, tool_name: str, args: Dict[str, Any], depends_on: Optional[List[str]] = None):
        self.tool_name = tool_name
        self.args = args
        self.depends_on = depends_on or []  # List of tool call IDs this depends on
        self.id = f"{tool_name}_{id(self)}"  # Unique ID for this call

# Example of how the LLM could indicate dependencies in its response:
"""
For the query: "First find bugs assigned to John, then search documentation about those bugs"

The LLM could return tool calls with metadata:
[
    {
        "tool": "mongo_query",
        "args": {"query": "find work items where type is bug and assignee is John"},
        "id": "query_1",
        "depends_on": []
    },
    {
        "tool": "rag_search", 
        "args": {"query": "documentation about {results_from: query_1}"},
        "id": "search_1",
        "depends_on": ["query_1"]
    }
]
"""

# Or we could parse the LLM's natural language planning:
def extract_execution_plan(llm_response: str) -> Dict[str, Any]:
    """
    Parse LLM's execution plan from its response.
    
    Example LLM response:
    "I'll help you with this in two steps:
    STEP 1: First, I'll query for bugs assigned to John
    STEP 2: Then, I'll search documentation using the bug titles from step 1
    
    Tool calls:
    1. mongo_query(...)
    2. rag_search(...) [depends on step 1]
    "
    """
    # This would parse the response to understand dependencies
    pass