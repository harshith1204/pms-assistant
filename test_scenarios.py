#!/usr/bin/env python3
"""
Test script to demonstrate scenario-based query classification.

This script shows how different queries are classified into scenarios
and which finalization prompts would be used.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent import _classify_query_scenario, FINALIZATION_PROMPTS


def test_scenario_classification():
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
        ("Show distribution of bugs by assignee", "breakdown"),
        
        # List queries
        ("List all active projects", "list"),
        ("Show all high priority bugs", "list"),
        ("Display recent work items", "list"),
        ("What are the current cycles?", "list"),
        
        # Detail queries
        ("Tell me about Project Alpha", "detail"),
        ("Show details for bug #123", "detail"),
        ("Information on the Authentication project", "detail"),
        ("Find details about user John Doe", "detail"),
        
        # Comparison queries
        ("Compare Project A and Project B", "comparison"),
        ("What's the difference between Sprint 1 and Sprint 2?", "comparison"),
        ("Compare bugs vs features", "comparison"),
        
        # Analysis queries
        ("Analyze bug trends this month", "analysis"),
        ("What are the patterns in work item creation?", "analysis"),
        ("Why are there so many high priority bugs?", "analysis"),
        ("Show insights on project performance", "analysis"),
        
        # Search queries
        ("Find documentation about authentication", "search"),
        ("Search for notes on API design", "search"),
        ("Look for pages about testing", "search"),
        
        # Export queries
        ("Export bugs to Excel", "export"),
        ("Download project list as CSV", "export"),
        ("Save work items to spreadsheet", "export"),
    ]
    
    print("=" * 80)
    print("SCENARIO CLASSIFICATION TEST")
    print("=" * 80)
    print()
    
    correct = 0
    total = len(test_queries)
    
    for query, expected_scenario in test_queries:
        detected_scenario = _classify_query_scenario(query)
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
    print()
    
    # Show example finalization prompts
    print("=" * 80)
    print("EXAMPLE FINALIZATION PROMPTS")
    print("=" * 80)
    print()
    
    scenarios_to_show = ["count", "breakdown", "list", "analysis"]
    for scenario in scenarios_to_show:
        print(f"▸ SCENARIO: {scenario.upper()}")
        print("-" * 80)
        prompt = FINALIZATION_PROMPTS.get(scenario, "No prompt defined")
        # Show first 300 chars
        preview = prompt[:400] + "..." if len(prompt) > 400 else prompt
        print(preview)
        print()


if __name__ == "__main__":
    test_scenario_classification()
