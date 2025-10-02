# Scenario-Based Response Generation

## Overview

The PMS Assistant now features an **intelligent query classification system** that automatically detects the type of query and generates responses with appropriate structure and formatting. This ensures more meaningful, properly structured responses tailored to each query type.

## How It Works

### 1. Query Classification

When a user submits a query, the system analyzes it and classifies it into one of 8 scenarios:

| Scenario | Description | Example Queries |
|----------|-------------|-----------------|
| **count** | Numeric/summary queries asking for totals | "How many bugs are there?", "Count active projects" |
| **breakdown** | Distribution/grouping queries | "Show bugs by priority", "Breakdown work items by state" |
| **list** | Queries requesting multiple items | "List all projects", "Show recent work items" |
| **detail** | Queries about specific items | "Tell me about Project X", "Details on bug #123" |
| **comparison** | Comparing two or more entities | "Compare Project A and B", "Difference between X and Y" |
| **analysis** | Insight and trend queries | "Analyze bug patterns", "What are the trends?" |
| **search** | Finding content by keywords/meaning | "Find documentation about auth", "Search for API notes" |
| **export** | Data export operations | "Export to Excel", "Save as CSV" |

### 2. Scenario Detection Logic

The classification is pattern-based and uses keyword matching:

```python
# Count queries
count_patterns = ["how many", "count", "total", "number of"]

# Breakdown queries  
breakdown_patterns = ["breakdown", "distribution", "group by", "by project", "by priority"]

# Comparison queries
comparison_patterns = ["compare", "versus", "vs", "difference between"]

# Analysis queries
analysis_patterns = ["analyze", "trend", "pattern", "insight", "why"]

# ... and so on
```

### 3. Tailored Response Generation

Each scenario has a **specialized finalization prompt** that instructs the LLM how to structure the response:

#### Count Response Structure
```
1. Direct answer with the count/total
2. One-sentence context if relevant
3. Offer to provide more details if helpful
```

Example:
> "There are 47 high-priority bugs across 8 projects. Would you like to see the breakdown by project?"

#### Breakdown Response Structure
```
1. Brief summary of total items and grouping
2. Top 5-7 categories with counts:
   • Category: X items (with key details)
3. Mention remaining categories
4. One insight about distribution
```

Example:
> "Found 120 work items grouped by priority:
> • High: 45 items (mostly in Development state)
> • Medium: 52 items
> • Low: 23 items
> 
> Most items are concentrated in High and Medium priorities."

#### List Response Structure
```
1. Brief intro stating count
2. List items (max 10-15) with essential fields
3. Mention if truncated
4. Offer to show more details
```

Example:
> "Found 8 active projects:
> • Project Alpha: Active, Lead: John Doe, 45 work items
> • Project Beta: Active, Lead: Jane Smith, 32 work items
> ...
> 
> Would you like details on any specific project?"

## Benefits

### 1. **Consistent Structure**
Each query type gets a predictable, well-organized response format.

### 2. **Better User Experience**
- Count queries get concise numeric answers, not walls of data
- List queries get scannable bullet points, not raw JSON
- Analysis queries get insights, not just data dumps

### 3. **Reduced Token Usage**
Structured prompts guide the LLM to be concise and focused, reducing unnecessary verbosity.

### 4. **Easier Parsing**
Frontend can better understand and display responses when structure is predictable.

### 5. **Improved Reasoning**
The LLM reasons about the query intent and applies appropriate formatting logic.

## Customization

### Adding New Scenarios

To add a new scenario type:

1. **Update the classifier** in `agent.py`:
```python
def _classify_query_scenario(user_query: str) -> str:
    # ... existing code ...
    
    # New scenario
    new_pattern = ["keyword1", "keyword2"]
    if any(p in q for p in new_pattern):
        return "new_scenario"
```

2. **Add the finalization prompt**:
```python
FINALIZATION_PROMPTS = {
    # ... existing prompts ...
    
    "new_scenario": """FINALIZATION (New Scenario Response):
Based on the tool outputs above, provide [SPECIFIC GUIDANCE].

Structure your response as:
1. [Step 1]
2. [Step 2]
3. [Step 3]

Keep it [QUALITY GUIDELINES].
Do NOT paste tool outputs verbatim. Do NOT include emojis or banners.""",
}
```

### Modifying Existing Prompts

Edit the `FINALIZATION_PROMPTS` dictionary in `agent.py` to change how responses are structured.

For example, to make list responses more detailed:

```python
"list": """FINALIZATION (List Response):
Based on the tool outputs above, present the items as a DETAILED list.

Structure your response as:
1. Brief intro with count and filters applied
2. List items (max 20) with FULL fields:
   • Item identifier: All relevant details
3. Show metadata (updated dates, created by, etc.)
4. Offer to export or filter further

Keep it COMPREHENSIVE but ORGANIZED.
Do NOT paste tool outputs verbatim. Do NOT include emojis or banners.""",
```

## Monitoring

When a query is processed, you'll see logs like:

```
🔧 Executing 1 tool(s) (SINGLE): ['mongo_query']
🎯 Query scenario detected: COUNT
```

This helps you verify the classification is working correctly.

## Best Practices

### For Users

1. **Be specific**: Use keywords that match the scenario you want
   - ❌ "bugs" → might get generic search
   - ✅ "how many bugs" → gets count response
   
2. **Use natural language**: The patterns are designed for human queries
   - ✅ "Show me work items by priority"
   - ✅ "Compare Project A and Project B"

### For Developers

1. **Test edge cases**: Some queries may match multiple patterns
2. **Adjust pattern order**: Earlier patterns take precedence
3. **Monitor logs**: Watch scenario detection to fine-tune patterns
4. **Keep prompts focused**: Each prompt should have clear structural guidelines

## Examples

### Count Query
**Input**: "How many high priority bugs are there?"

**Scenario**: COUNT

**Response**:
> "There are 12 high-priority bugs across 5 projects. Would you like to see them broken down by project or assignee?"

### Breakdown Query  
**Input**: "Show me work items by state"

**Scenario**: BREAKDOWN

**Response**:
> "Found 89 work items grouped by state:
> • In Progress: 34 items (38%)
> • Todo: 28 items (31%)
> • Done: 18 items (20%)
> • Blocked: 9 items (10%)
> 
> Most items are actively being worked on (In Progress) or awaiting start (Todo)."

### Analysis Query
**Input**: "Analyze the bug trends for this month"

**Scenario**: ANALYSIS

**Response**:
> "Based on this month's data:
> 
> **Key Findings:**
> • 45 new bugs reported (15% increase from last month)
> • Average resolution time: 3.2 days (improved from 4.1 days)
> • High-priority bugs concentrated in Authentication module (67%)
> • 3 recurring issues related to login validation
> 
> **Recommendation**: Focus QA resources on Authentication module and implement regression tests for login validation.
> 
> Would you like to see specific bugs or dive deeper into any area?"

## Troubleshooting

### Wrong Scenario Detected?

If a query is classified incorrectly:

1. Check the pattern order in `_classify_query_scenario`
2. Add more specific patterns for your use case
3. Adjust pattern matching logic

### Response Not Following Structure?

The finalization prompts are **guidelines**, not strict templates. The LLM may:
- Adapt structure based on available data
- Skip sections if data is missing
- Combine sections for brevity

To enforce stricter structure, make prompts more explicit with numbered steps and examples.

## Future Enhancements

Potential improvements to consider:

1. **Machine Learning Classification**: Replace pattern matching with ML model
2. **Multi-Scenario Detection**: Handle queries that fit multiple scenarios
3. **User Preferences**: Let users specify preferred response format
4. **A/B Testing**: Track which scenarios produce best user satisfaction
5. **Dynamic Prompts**: Adjust prompts based on data volume or complexity

---

**Note**: This system is designed to be iterative. Monitor usage, collect feedback, and refine scenarios and prompts over time.
