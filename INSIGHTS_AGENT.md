# MongoDB Insights Agent

A production-ready **Planner → Executor → Insight Synthesizer** agent that transforms PM/Engineering Manager queries into actionable insights.

## Architecture

```
Query → Planner → Executor → Synthesizer → Insights
         ↓          ↓           ↓
      [Tasks]   [Results]   [Citations]
```

- **Planner**: Breaks queries into atomic database tasks
- **Executor**: Runs read-only MCP tools to gather data  
- **Synthesizer**: Creates concise insights with citations [T1], [T2]

## Setup

1. Set environment variables:
```bash
export MCP_API_KEY=your_smithery_api_key
export MCP_PROFILE=your_smithery_profile
```

2. Start the server:
```bash
python main.py
```

## API Endpoints

### POST /ask
Get insights from the agent:
```json
{
  "message": "What's the average cycle time by team in the last 30 days?",
  "conversation_id": "optional-session-id"
}
```

Response:
```json
{
  "insights": "• Team Alpha: 3.2 days avg cycle time ↓15% WoW [T1]\n• Team Beta: 5.1 days ↑8% [T2]\n• Backend tickets 2x slower than frontend [T3]\nTakeaway: Focus on Backend team's bottlenecks.",
  "conversation_id": "...",
  "timestamp": "..."
}
```

### WebSocket /ws/insights
Stream real-time progress:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/insights');

ws.send(JSON.stringify({
  query: "Top 5 blockers this quarter by frequency",
  conversation_id: "session-123"
}));

// Receive progress events:
// {"type": "plan_start"}
// {"type": "plan_complete", "tasks": [...]}
// {"type": "task_start", "task_id": "T1", "description": "..."}
// {"type": "task_complete", "task_id": "T1", "success": true}
// {"type": "synthesis_start"}
// {"type": "complete", "insights": "..."}
```

## Example Queries

**Sprint Analytics:**
- "What's the sprint velocity trend over the last 4 sprints?"
- "Which epics are at risk of missing the deadline?"
- "Show me burn-down rate by team this sprint"

**Quality Metrics:**
- "Bug escape rate by component in Q3 vs Q2"
- "Average time from bug report to fix by severity"
- "Which features have the most customer-reported issues?"

**Team Performance:**
- "Average PR review time by reviewer last month"
- "Who are the top contributors by story points delivered?"
- "Team utilization rates and capacity planning"

**Bottleneck Analysis:**
- "Top 5 reasons tickets get blocked and average block duration"
- "Which stage in our workflow has the longest wait time?"
- "Dependencies causing the most delays"

**Trend Analysis:**
- "How has our deployment frequency changed month-over-month?"
- "Reopened ticket rate trend by product area"
- "Customer satisfaction score correlation with bug count"

## Read-Only Safety

The agent enforces read-only operations by:
1. Allowlisting only read tools (find, aggregate, count, list, etc.)
2. Rejecting any tool names suggesting writes (insert, update, delete)
3. Double-checking in the executor before running any tool

## Response Format

Insights are:
- **Concise**: 3-4 bullet points max
- **Quantified**: Specific numbers and percentages
- **Cited**: [T1], [T2] references to source tasks
- **Actionable**: One clear takeaway

Example:
```
• Code review backlog ↑34% WoW, 89 PRs pending [T1]
• Median review time: 4.2 hours (target: 2h) [T2]
• 67% of delays from 3 reviewers [T3]
Takeaway: Add review capacity or redistribute PR assignments.
```

## Performance

- Uses lightweight Qwen 0.6B model for fast responses
- Parallel task execution when possible
- Typical response time: 2-5 seconds for complex queries
- Streaming support shows progress in real-time