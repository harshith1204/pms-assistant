from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END, MessagesState
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

# Database configuration
DATABASE_NAME = "ProjectManagement"

# MCP Server Configuration
mongodb_server_config = {
    "mongodb": {
        "command": "npx",
        "args": ["-y", "@mongodb-js/mongodb-mcp-server"],
        "env": {
            "MONGODB_CONNECTION_STRING": "mongodb://localhost:27017",
            "MONGODB_DATABASE_NAME": DATABASE_NAME
        }
    }
}

# HTTP-based configuration for Smithery
smithery_config = {
    "mongodb": {
        "url": "https://server.smithery.ai/@mongodb-js/mongodb-mcp-server/mcp?api_key=4fd11c6a-4c6f-45ce-ab0d-24cb4c051779&profile=furious-lemming-rvSkqO",
        "transport": "streamable_http"
    }
}

class MongoDBTools:
    """MongoDB MCP Tools wrapper using langchain-mcp-adapters"""

    def __init__(self):
        self.client = MultiServerMCPClient(smithery_config)
        self.tools = []
        self.connected = False

    async def connect(self):
        """Initialize connection to MongoDB MCP server using langchain-mcp-adapters"""
        try:
            # Get tools from the MCP server (this will establish connections as needed)
            self.tools = await self.client.get_tools()
            self.connected = True
            print(f"Connected to MongoDB MCP. Available tools: {[tool.name for tool in self.tools]}")

        except Exception as e:
            print(f"Failed to connect to MongoDB MCP server: {e}")
            raise

    async def disconnect(self):
        """Disconnect from MongoDB MCP server"""
        # MultiServerMCPClient handles connection cleanup automatically
        self.connected = False
        self.tools = []

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Execute a MongoDB MCP tool"""
        if not self.connected:
            raise ValueError("Not connected to MCP server")

        # Find the tool
        tool = next((t for t in self.tools if t.name == tool_name), None)
        if not tool:
            raise ValueError(f"Tool {tool_name} not available")

        # Execute the tool directly (it handles MCP communication internally)
        result = await tool.ainvoke(arguments)
        return result

# Global MongoDB tools instance
mongodb_tools = MongoDBTools()

# ---------- Helpers (read-only) ----------
async def _find_tasks(filter_: Dict[str, Any], limit: int = 2000, sort: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    args: Dict[str, Any] = {
        "database": DATABASE_NAME,
        "collection": "tasks",
        "filter": filter_,
        "limit": limit,
    }
    if sort:
        args["sort"] = sort
    res = await mongodb_tools.execute_tool("find", args)
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except Exception:
            pass
    return res or []

async def _find_one_sprint(project: str, sprint_name: str) -> Optional[Dict[str, Any]]:
    # Try preferred tool name, fall back to common alias
    try:
        res = await mongodb_tools.execute_tool("find-one", {
            "database": DATABASE_NAME,
            "collection": "sprints",
            "filter": {"project": project, "name": sprint_name}
        })
    except Exception:
        res = await mongodb_tools.execute_tool("findOne", {
            "database": DATABASE_NAME,
            "collection": "sprints",
            "filter": {"project": project, "name": sprint_name}
        })
    if isinstance(res, str):
        try:
            res = json.loads(res)
        except Exception:
            pass
    return res or None

def _iso_now() -> str:
    return datetime.utcnow().isoformat()

def _to_date(s: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(s.replace("Z", ""))
    except Exception:
        return None

# ---------- Insight Tools (read-only) ----------
@tool
async def list_overdue_tasks(project: Optional[str] = None, limit: int = 50) -> str:
    """List open tasks past due_date. Open= status not in ['done','completed','cancelled']."""
    now = _iso_now()
    flt: Dict[str, Any] = {
        "due_date": {"$lt": now},
        "status": {"$nin": ["done", "completed", "cancelled"]},
    }
    if project:
        flt["project"] = project
    tasks = await _find_tasks(flt, limit=limit, sort=[{"due_date": 1}])

    summary: Dict[str, Any] = {
        "count": len(tasks),
        "oldest_due": tasks[0]["due_date"] if tasks else None,
        "by_assignee": {},
        "examples": [{"_id": str(t.get("_id")), "title": t.get("title"), "assignee": t.get("assignee"), "due_date": t.get("due_date")} for t in tasks[:10]],
    }
    for t in tasks:
        owner = t.get("assignee") or "unassigned"
        summary["by_assignee"][owner] = summary["by_assignee"].get(owner, 0) + 1

    return json.dumps(summary)

@tool
async def workload(project: Optional[str] = None) -> str:
    """Active WIP distribution by assignee. Active = status in ['todo','in_progress','blocked']."""
    flt: Dict[str, Any] = {"status": {"$in": ["todo", "in_progress", "blocked"]}}
    if project:
        flt["project"] = project
    tasks = await _find_tasks(flt, limit=5000)

    buckets: Dict[str, int] = {}
    blocked = 0
    for t in tasks:
        owner = t.get("assignee") or "unassigned"
        buckets[owner] = buckets.get(owner, 0) + 1
        if t.get("status") == "blocked":
            blocked += 1

    out = {
        "active_tasks": sum(buckets.values()),
        "blocked_tasks": blocked,
        "by_assignee": [{"assignee": k, "active_tasks": v} for k, v in sorted(buckets.items(), key=lambda x: (-x[1], x[0]))]
    }
    return json.dumps(out)

@tool
async def throughput(project: Optional[str] = None, period_days: int = 14) -> str:
    """Tasks completed per day over the last period_days."""
    since = (datetime.utcnow() - timedelta(days=period_days)).isoformat()
    flt: Dict[str, Any] = {
        "status": {"$in": ["done", "completed"]},
        "completed_at": {"$gte": since}
    }
    if project:
        flt["project"] = project
    tasks = await _find_tasks(flt, limit=5000)

    buckets: Dict[str, int] = {}
    for t in tasks:
        d = _to_date(t.get("completed_at") or "")
        if not d:
            continue
        key = d.date().isoformat()
        buckets[key] = buckets.get(key, 0) + 1

    series = [{"date": k, "completed": v} for k, v in sorted(buckets.items())]
    return json.dumps({
        "period_days": period_days,
        "total_completed": sum(buckets.values()),
        "daily_series": series,
        "avg_per_day": round(sum(buckets.values()) / max(1, len(series)), 2) if series else 0.0
    })

@tool
async def sprint_burndown(project: str, sprint_name: str) -> str:
    """
    Remaining points by day across sprint window.
    Requires: tasks with fields {project, sprint, points:int, status, completed_at?}; sprints with {start_date, end_date}.
    """
    sprint = await _find_one_sprint(project, sprint_name)
    if not sprint:
        return json.dumps({"error": f"No sprint '{sprint_name}' for project '{project}'"})

    start = _to_date(sprint.get("start_date") or "")
    end = _to_date(sprint.get("end_date") or "")
    if not start or not end:
        return json.dumps({"error": "Sprint dates missing or invalid"})

    tasks = await _find_tasks({"project": project, "sprint": sprint_name}, limit=5000)
    total = sum(int(t.get("points") or 0) for t in tasks)

    days = (end - start).days + 1
    remaining = total
    series: List[Dict[str, Any]] = []
    for i in range(days):
        day = (start + timedelta(days=i)).date().isoformat()
        completed_today = 0
        for t in tasks:
            if t.get("status") in ["done", "completed"]:
                ct = _to_date(t.get("completed_at") or "")
                if ct and ct.date().isoformat() == day:
                    completed_today += int(t.get("points") or 0)
        remaining = max(remaining - completed_today, 0)
        series.append({"date": day, "remaining_points": remaining})

    ideal: List[Dict[str, Any]] = []
    step = total / max(1, (days - 1))
    for i in range(days):
        ideal.append({"date": (start + timedelta(days=i)).date().isoformat(), "ideal_remaining": max(total - step * i, 0)})

    return json.dumps({
        "project": project,
        "sprint": sprint_name,
        "total_points": total,
        "series": series,
        "ideal": ideal
    })

@tool
async def aging_wip(project: Optional[str] = None) -> str:
    """
    Age (days) of active tasks since created_at. Helps find stale items.
    Active statuses: todo, in_progress, blocked.
    """
    flt: Dict[str, Any] = {"status": {"$in": ["todo", "in_progress", "blocked"]}}
    if project:
        flt["project"] = project
    tasks = await _find_tasks(flt, limit=5000)
    now = datetime.utcnow()

    rows: List[Dict[str, Any]] = []
    for t in tasks:
        created = _to_date(t.get("created_at") or "")
        age_days = (now - created).days if created else None
        rows.append({
            "_id": str(t.get("_id")),
            "title": t.get("title"),
            "assignee": t.get("assignee") or "unassigned",
            "status": t.get("status"),
            "age_days": age_days
        })
    rows.sort(key=lambda r: (-(r["age_days"] or -1), r["assignee"]))
    return json.dumps({"count": len(rows), "top_stale": rows[:20]})

# Register only read-only insight tools
tools = [
    list_overdue_tasks,
    workload,
    throughput,
    sprint_burndown,
    aging_wip,
]

# Read-only insights-first system prompt
READONLY_SYSTEM_PROMPT = SystemMessage(content="""
You are a Project Management Insights Agent with read-only access.
- You CANNOT create/update/delete tasks.
- You CAN call tools to READ data (overdue, workload, throughput, burndown, aging WIP).
- Decide which tool to call based on the user's ask.
- After a tool returns JSON, parse it and produce a short, structured summary with bullet points, concrete dates, and numbers.
- If a user requests creation/update, politely say write access is disabled and offer an insight alternative.
- Keep answers concise; include 3–5 bullets and (if helpful) next steps.
""")

# Initialize the LLM with optimized settings for faster performance
llm = ChatOllama(
    model="qwen3:0.6b-fp16",
    temperature=0.3,
    num_ctx=2048,  # Smaller context window for faster responses
    num_predict=256,  # Limit token generation
    num_thread=8,  # Use multiple threads
    streaming=True,  # Enable streaming
    verbose=False
)
llm_with_tools = llm.bind_tools(tools)

# Define the agent state
class AgentState(MessagesState):
    pass

# Define the agent workflow
def call_agent(state: AgentState):
    """Main agent logic"""
    messages = [READONLY_SYSTEM_PROMPT] + state["messages"]
    response = llm_with_tools.invoke(messages)

    return {"messages": [response]}

async def call_agent_streaming(state: AgentState, callback_handler=None):
    """Main agent logic with streaming support"""
    messages = [READONLY_SYSTEM_PROMPT] + state["messages"]
    
    # Create a new LLM instance with the callback handler if provided
    if callback_handler:
        streaming_llm = ChatOllama(
            model="qwen3:0.6b-fp16",
            temperature=0.3,
            num_ctx=2048,
            num_predict=256,
            num_thread=8,
            streaming=True,
            callbacks=[callback_handler]
        )
        streaming_llm_with_tools = streaming_llm.bind_tools(tools)
        response = await streaming_llm_with_tools.ainvoke(messages)
    else:
        response = await llm_with_tools.ainvoke(messages)
    
    return {"messages": [response]}

async def call_tools_async(state: AgentState, callback_handler=None):
    """Execute tools based on agent response (async version)"""
    messages = state["messages"]
    last_message = messages[-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}

    tool_results = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        # Find the corresponding tool
        tool = next((t for t in tools if t.name == tool_name), None)
        if tool:
            try:
                # Notify callback about tool execution
                if callback_handler:
                    await callback_handler.on_tool_start(
                        {"name": tool_name}, 
                        str(tool_args)
                    )
                
                # Run the async tool
                result = await tool.ainvoke(tool_args)
                
                if callback_handler:
                    await callback_handler.on_tool_end(str(result))
                    
                tool_results.append(ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"]
                ))
            except Exception as e:
                error_msg = f"Error executing tool {tool_name}: {str(e)}"
                if callback_handler:
                    await callback_handler.on_tool_end(error_msg)
                    
                tool_results.append(ToolMessage(
                    content=error_msg,
                    tool_call_id=tool_call["id"]
                ))

    return {"messages": tool_results}

def call_tools(state: AgentState):
    """Execute tools based on agent response (sync version)"""
    messages = state["messages"]
    last_message = messages[-1]

    if not hasattr(last_message, "tool_calls") or not last_message.tool_calls:
        return {"messages": []}

    tool_results = []
    for tool_call in last_message.tool_calls:
        tool_name = tool_call["name"]
        tool_args = tool_call["args"]

        # Find the corresponding tool
        tool = next((t for t in tools if t.name == tool_name), None)
        if tool:
            try:
                # Run the async tool
                result = asyncio.run(tool.ainvoke(tool_args))
                tool_results.append(ToolMessage(
                    content=str(result),
                    tool_call_id=tool_call["id"]
                ))
            except Exception as e:
                tool_results.append(ToolMessage(
                    content=f"Error executing tool {tool_name}: {str(e)}",
                    tool_call_id=tool_call["id"]
                ))

    return {"messages": tool_results}

def should_continue(state: AgentState) -> str:
    """Determine if we should continue or end"""
    messages = state["messages"]
    last_message = messages[-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END

# Create the graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_agent)
workflow.add_node("tools", call_tools)

workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", should_continue)
workflow.add_edge("tools", "agent")

# Compile the graph
graph = workflow.compile()

class MongoDBAgent:
    """MongoDB Agent using LangGraph and MCP"""

    def __init__(self):
        self.graph = graph
        self.connected = False

    async def connect(self):
        """Connect to MongoDB MCP server"""
        await mongodb_tools.connect()
        self.connected = True
        print("MongoDB Agent connected successfully!")

    async def disconnect(self):
        """Disconnect from MongoDB MCP server"""
        await mongodb_tools.disconnect()
        self.connected = False

    async def run(self, query: str) -> str:
        """Run the agent with a query"""
        if not self.connected:
            await self.connect()

        messages = [HumanMessage(content=query)]
        result = await graph.ainvoke({"messages": messages})

        # Get the final response
        final_message = result["messages"][-1]
        return final_message.content
    
    async def run_streaming(self, query: str, callback_handler=None, websocket=None):
        """Run the agent with streaming support"""
        if not self.connected:
            await self.connect()
            
        messages = [HumanMessage(content=query)]
        state = {"messages": messages}
        
        # Create a custom graph for streaming
        while True:
            # Call agent with streaming
            agent_result = await call_agent_streaming(state, callback_handler)
            state["messages"].extend(agent_result["messages"])
            
            last_message = state["messages"][-1]
            
            # Check if we need to call tools
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                # Execute tools
                tool_result = await call_tools_async(state, callback_handler)
                state["messages"].extend(tool_result["messages"])
            else:
                # No more tools to call, we're done
                break
                
        # Return the final response
        return state["messages"][-1].content

# Example usage
async def main():
    """Example usage of the MongoDB Agent"""
    agent = MongoDBAgent()

    try:
        # Connect to MongoDB
        await agent.connect()

        # Example read-only queries
        queries = [
            "Show overdue tasks for WebApp",
            "What's our throughput in the last 21 days for WebApp?",
            "Who is overloaded right now in WebApp?",
            "Sprint 34 burndown for WebApp, include risks",
            "Which WIP is getting stale in WebApp?",
        ]

        for query in queries:
            print(f"\nQuery: {query}")
            response = await agent.run(query)
            print(f"Response: {response}")

    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        await agent.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
