"""
Read-only MongoDB Insight Agent (Planner-Executor with MCP tools)

This agent implements a three-stage pipeline:
1. Planner: Breaks down queries into specific database tasks
2. Executor: Runs read-only MCP tools to gather data
3. Insight Synthesizer: Creates concise, actionable insights with citations
"""

import asyncio
import json
from typing import Dict, Any, List, Optional, TypedDict
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END
from langchain_mcp_adapters.client import MultiServerMCPClient
import re

# Read-only tool allowlist - only these tools can be executed
READ_ONLY_TOOLS = {
    "find", "aggregate", "count", "list", "describe", 
    "schema", "ping", "sample", "find-databases",
    "list-databases", "list-collections", "describe-collection"
}

def is_read_only_tool(tool_name: str) -> bool:
    """Check if a tool is read-only based on allowlist"""
    return any(tool_name.startswith(prefix) for prefix in READ_ONLY_TOOLS)

# Task structure
class Task(BaseModel):
    id: str = Field(description="Unique task ID like T1, T2, etc")
    description: str = Field(description="What this task accomplishes")
    tool: str = Field(description="MCP tool name to execute")
    args: Dict[str, Any] = Field(description="Arguments for the tool")

class TaskResult(BaseModel):
    task_id: str
    tool: str
    output: Any
    success: bool
    error: Optional[str] = None

# Agent State
class AgentState(TypedDict):
    query: str
    tasks: List[Task]
    results: List[TaskResult]
    insights: str
    conversation_id: Optional[str]

# System prompts
PLANNER_SYSTEM = """You are a data analysis planner for a project management system.

Your job is to break down queries into specific database tasks using ONLY the available MCP tools.
Each task should gather specific data needed to answer the query.

Available collections: tickets, projects, teams, users, sprints, releases

Rules:
1. Output ONLY valid JSON with a "tasks" array
2. Each task must have: id (T1, T2...), description, tool, args
3. Use aggregation pipelines for complex queries
4. Default to last 30 days for time-based queries unless specified
5. Keep tasks focused and atomic - one query per task
6. Maximum 5 tasks per plan

Example output:
{
  "tasks": [
    {
      "id": "T1",
      "description": "Count tickets by status for last 30 days",
      "tool": "aggregate",
      "args": {
        "database": "ProjectManagement",
        "collection": "tickets",
        "pipeline": [
          {"$match": {"createdAt": {"$gte": "2024-01-01"}}},
          {"$group": {"_id": "$status", "count": {"$sum": 1}}}
        ]
      }
    }
  ]
}
"""

EXECUTOR_SYSTEM = """You are a database task executor.
Execute each task using the appropriate MCP tool and record results.
If a tool fails, note the error and continue with remaining tasks."""

SYNTHESIZER_SYSTEM = """You are an insight synthesizer for engineering managers.

Your job is to create CONCISE, ACTIONABLE insights from task results.
Focus on numbers, trends, and recommendations.

Rules:
1. Be extremely concise - max 3-4 bullet points
2. Lead with the most important finding
3. Use ↑↓ arrows for trends
4. Include specific numbers and percentages
5. Add citations [T1], [T2] to show which task provided each insight
6. End with ONE actionable takeaway

Example:
• Sprint velocity ↑15% MoM, now averaging 47 points [T1]
• Bug escape rate dropped to 2.1% (from 3.8%) [T2]  
• 78% of delays traced to "blocked by backend" label [T3]
Takeaway: Backend bottleneck is limiting velocity gains - prioritize API work.
"""

class AgentRuntime:
    """Runtime for the Planner-Executor-Synthesizer agent"""
    
    def __init__(self, mcp_config: Dict[str, Any]):
        self.mcp_config = mcp_config
        self.mcp_client = None
        self.available_tools = {}
        
        # Initialize LLMs with appropriate models
        self.planner_llm = ChatOllama(
            model="qwen3:0.6b-fp16",  # Fast model for planning
            temperature=0.1,
            num_ctx=2048,
            format="json"
        )
        
        self.executor_llm = ChatOllama(
            model="qwen3:0.6b-fp16",  # Fast model for execution
            temperature=0,
            num_ctx=2048
        )
        
        self.synthesizer_llm = ChatOllama(
            model="qwen3:0.6b-fp16",  # Fast model for synthesis
            temperature=0.3,
            num_ctx=2048
        )
        
        # Build the graph
        self.graph = self._build_graph()
        
    async def start(self):
        """Initialize MCP connection and discover tools"""
        self.mcp_client = MultiServerMCPClient(self.mcp_config)
        tools = await self.mcp_client.get_tools()
        
        # Filter to read-only tools
        for tool in tools:
            if is_read_only_tool(tool.name):
                self.available_tools[tool.name] = tool
                
        print(f"Agent started with {len(self.available_tools)} read-only tools")
        
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow"""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("planner", self._plan_node)
        workflow.add_node("executor", self._executor_node)
        workflow.add_node("synthesizer", self._synthesizer_node)
        
        # Define flow
        workflow.set_entry_point("planner")
        workflow.add_edge("planner", "executor")
        workflow.add_edge("executor", "synthesizer")
        workflow.add_edge("synthesizer", END)
        
        return workflow.compile()
        
    async def _plan_node(self, state: AgentState) -> Dict[str, Any]:
        """Planner node - breaks query into tasks"""
        messages = [
            SystemMessage(content=PLANNER_SYSTEM),
            HumanMessage(content=f"Query: {state['query']}\n\nAvailable tools: {list(self.available_tools.keys())}")
        ]
        
        response = await self.planner_llm.ainvoke(messages)
        
        try:
            # Parse JSON response
            plan_data = json.loads(response.content)
            tasks = [Task(**task_dict) for task_dict in plan_data.get("tasks", [])]
            
            # Validate tools exist and are read-only
            validated_tasks = []
            for task in tasks:
                if task.tool in self.available_tools:
                    validated_tasks.append(task)
                else:
                    print(f"Warning: Skipping task {task.id} - tool '{task.tool}' not available or not read-only")
                    
            return {"tasks": validated_tasks}
            
        except Exception as e:
            print(f"Planning error: {e}")
            # Fallback to a simple find query
            return {
                "tasks": [
                    Task(
                        id="T1",
                        description="Find recent tickets",
                        tool="find",
                        args={"database": "ProjectManagement", "collection": "tickets", "limit": 10}
                    )
                ]
            }
            
    async def _executor_node(self, state: AgentState) -> Dict[str, Any]:
        """Executor node - runs tasks with MCP tools"""
        results = []
        
        for task in state["tasks"]:
            try:
                # Double-check read-only
                if not is_read_only_tool(task.tool):
                    results.append(TaskResult(
                        task_id=task.id,
                        tool=task.tool,
                        output=None,
                        success=False,
                        error="Tool not allowed (write operation)"
                    ))
                    continue
                    
                # Execute via MCP
                tool = self.available_tools[task.tool]
                output = await tool.ainvoke(task.args)
                
                results.append(TaskResult(
                    task_id=task.id,
                    tool=task.tool,
                    output=output,
                    success=True
                ))
                
            except Exception as e:
                results.append(TaskResult(
                    task_id=task.id,
                    tool=task.tool,
                    output=None,
                    success=False,
                    error=str(e)
                ))
                
        return {"results": results}
        
    async def _synthesizer_node(self, state: AgentState) -> Dict[str, Any]:
        """Synthesizer node - creates insights from results"""
        # Build context from results
        context_parts = []
        for result in state["results"]:
            if result.success:
                context_parts.append(f"[{result.task_id}] {json.dumps(result.output, indent=2)}")
            else:
                context_parts.append(f"[{result.task_id}] Error: {result.error}")
                
        context = "\n\n".join(context_parts)
        
        messages = [
            SystemMessage(content=SYNTHESIZER_SYSTEM),
            HumanMessage(content=f"Original query: {state['query']}\n\nTask results:\n{context}")
        ]
        
        response = await self.synthesizer_llm.ainvoke(messages)
        
        return {"insights": response.content}
        
    async def ask(self, query: str, conversation_id: Optional[str] = None) -> str:
        """Main entry point - process a query and return insights"""
        if not self.mcp_client:
            raise ValueError("Agent not started. Call start() first.")
            
        # Run the graph
        result = await self.graph.ainvoke({
            "query": query,
            "tasks": [],
            "results": [],
            "insights": "",
            "conversation_id": conversation_id
        })
        
        return result["insights"]
        
    async def ask_with_progress(self, query: str, progress_callback=None, conversation_id: Optional[str] = None) -> str:
        """Process query with progress callbacks for streaming"""
        if not self.mcp_client:
            raise ValueError("Agent not started. Call start() first.")
            
        state = {
            "query": query,
            "tasks": [],
            "results": [],
            "insights": "",
            "conversation_id": conversation_id
        }
        
        # Plan
        if progress_callback:
            await progress_callback({"type": "plan_start"})
        plan_result = await self._plan_node(state)
        state.update(plan_result)
        if progress_callback:
            await progress_callback({"type": "plan_complete", "tasks": [t.dict() for t in state["tasks"]]})
            
        # Execute
        for i, task in enumerate(state["tasks"]):
            if progress_callback:
                await progress_callback({"type": "task_start", "task_id": task.id, "description": task.description})
                
        exec_result = await self._executor_node(state)
        state.update(exec_result)
        
        for result in state["results"]:
            if progress_callback:
                await progress_callback({
                    "type": "task_complete", 
                    "task_id": result.task_id,
                    "success": result.success,
                    "error": result.error
                })
                
        # Synthesize
        if progress_callback:
            await progress_callback({"type": "synthesis_start"})
        synth_result = await self._synthesizer_node(state)
        state.update(synth_result)
        if progress_callback:
            await progress_callback({"type": "synthesis_complete", "insights": state["insights"]})
            
        return state["insights"]


# Helper function to parse time expressions
def parse_time_expression(expr: str) -> Optional[datetime]:
    """Parse expressions like 'last 30 days', 'this week', etc."""
    now = datetime.now()
    expr_lower = expr.lower()
    
    # Last N days
    if match := re.search(r'last (\d+) days?', expr_lower):
        days = int(match.group(1))
        return now - timedelta(days=days)
        
    # This week/month/quarter
    if 'this week' in expr_lower:
        return now - timedelta(days=now.weekday())
    elif 'this month' in expr_lower:
        return now.replace(day=1)
    elif 'this quarter' in expr_lower:
        quarter_start_month = ((now.month - 1) // 3) * 3 + 1
        return now.replace(month=quarter_start_month, day=1)
        
    return None