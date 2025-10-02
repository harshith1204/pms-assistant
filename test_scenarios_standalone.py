#!/usr/bin/env python3
"""
Standalone test script to demonstrate scenario-based query classification.
This version doesn't require any dependencies.
"""

def classify_query_scenario(user_query: str) -> str:
    """Classify the query into a scenario type (standalone version)."""
    q = (user_query or "").lower()
    
    # Count/Summary queries
    count_patterns = ["how many", "count", "total", "number of"]
    if any(p in q for p in count_patterns):
        return "count"
    
    # Breakdown/Distribution queries
    breakdown_patterns = ["breakdown", "distribution", "group by", "grouped by", "by project", "by priority", "by state", "by status"]
    if any(p in q for p in breakdown_patterns):
        return "breakdown"
    
    # Comparison queries
    comparison_patterns = ["compare", "versus", "vs", "difference between", "contrast"]
    if any(p in q for p in comparison_patterns):
        return "comparison"
    
    # Analysis/Trend queries
    analysis_patterns = ["analyze", "analysis", "trend", "pattern", "insight", "what are the", "why", "how does"]
    if any(p in q for p in analysis_patterns):
        return "analysis"
    
    # Export queries
    export_patterns = ["export", "download", "save", "excel", "csv", "spreadsheet"]
    if any(p in q for p in export_patterns):
        return "export"
    
    # Search queries
    search_patterns = ["find", "search", "show me", "get me", "look for"]
    if any(p in q for p in search_patterns):
        detail_patterns = ["about", "detail", "information on", "tell me about"]
        if any(p in q for p in detail_patterns):
            return "detail"
        return "search"
    
    # List queries
    list_patterns = ["list", "show all", "display", "what are", "which"]
    if any(p in q for p in list_patterns):
        return "list"
    
    return "search"


def main():
    """Test the scenario classification with various query types."""
    
    test_queries = [
        # Count queries
        ("How many bugs are there?", "count"),
        ("Count all high priority work items", "count"),
        ("What's the total number of projects?", "count"),
        
        # Breakdown queries
        ("Show bugs by priority", "breakdown"),
        ("Breakdown work items by state", "breakdown"),
        ("Group projects by status", "breakdown"),
        
        # List queries
        ("List all active projects", "list"),
        ("Show all high priority bugs", "list"),
        ("What are the current cycles?", "list"),
        
        # Detail queries
        ("Tell me about Project Alpha", "detail"),
        ("Show details for bug #123", "detail"),
        ("Find information on the Authentication project", "detail"),
        
        # Comparison queries
        ("Compare Project A and Project B", "comparison"),
        ("What's the difference between Sprint 1 and Sprint 2?", "comparison"),
        
        # Analysis queries
        ("Analyze bug trends this month", "analysis"),
        ("What are the patterns in work item creation?", "analysis"),
        ("Why are there so many bugs?", "analysis"),
        
        # Search queries
        ("Find documentation about authentication", "search"),
        ("Search for notes on API design", "search"),
        
        # Export queries
        ("Export bugs to Excel", "export"),
        ("Download project list as CSV", "export"),
    ]
    
    print("=" * 80)
    print("SCENARIO CLASSIFICATION TEST")
    print("=" * 80)
    print()
    
    correct = 0
    total = len(test_queries)
    
    for query, expected_scenario in test_queries:
        detected_scenario = classify_query_scenario(query)
        is_correct = detected_scenario == expected_scenario
        
        if is_correct:
            correct += 1
            status = "✅"
        else:
            status = "❌"
        
        print(f"{status} Query: \"{query}\"")
        print(f"   Expected: {expected_scenario.upper()}")
        print(f"   Detected: {detected_scenario.upper()}")
        print()
    
    print("=" * 80)
    print(f"RESULTS: {correct}/{total} correct ({100*correct/total:.1f}%)")
    print("=" * 80)


if __name__ == "__main__":
    main()
