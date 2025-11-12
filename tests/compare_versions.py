"""
Compare current vs legacy agent implementations.

This script highlights the key differences that might cause issues.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def compare_imports():
    """Compare import statements between versions"""
    print("=" * 70)
    print("IMPORT PATH COMPARISON")
    print("=" * 70)
    
    differences = [
        {
            "file": "agent.py",
            "current": "from agent.memory import conversation_memory",
            "legacy": "from memory import conversation_memory",
            "impact": "HIGH - May cause ModuleNotFoundError"
        },
        {
            "file": "tools.py",
            "current": "from agent.orchestrator import Orchestrator",
            "legacy": "from orchestrator import Orchestrator",
            "impact": "HIGH - May cause ModuleNotFoundError"
        },
        {
            "file": "websocket_handler.py",
            "current": "from agent.planner import plan_and_execute_query",
            "legacy": "from planner import plan_and_execute_query",
            "impact": "MEDIUM - Affects planner functionality"
        },
        {
            "file": "tools.py",
            "current": "from agent.tools import set_generation_context",
            "legacy": "from tools import set_generation_context",
            "impact": "MEDIUM - Affects content generation"
        }
    ]
    
    for diff in differences:
        print(f"\n📁 File: {diff['file']}")
        print(f"   Impact: {diff['impact']}")
        print(f"   Current: {diff['current']}")
        print(f"   Legacy:  {diff['legacy']}")

def compare_logging():
    """Compare logging approaches"""
    print("\n" + "=" * 70)
    print("LOGGING COMPARISON")
    print("=" * 70)
    
    print("\nCurrent Version (agent/):")
    print("  - Uses: logging.getLogger(__name__)")
    print("  - Methods: logger.error(), logger.warning(), logger.info()")
    print("  - Visibility: Errors may be hidden if LOG_LEVEL not set")
    
    print("\nLegacy Version (legacy code/):")
    print("  - Uses: print() statements")
    print("  - Methods: print(f'Error: {e}'), print('Warning: ...')")
    print("  - Visibility: All output immediately visible in console")
    
    print("\n⚠️ Impact: Current version might hide errors during development")
    print("   Solution: Set LOG_LEVEL=DEBUG in .env or add print() statements")

def check_structure():
    """Check if package structure is correct"""
    print("\n" + "=" * 70)
    print("PACKAGE STRUCTURE CHECK")
    print("=" * 70)
    
    required_files = [
        ("agent/__init__.py", "Makes agent a package"),
        ("agent/agent.py", "Main agent implementation"),
        ("agent/tools.py", "Tool definitions"),
        ("agent/memory.py", "Conversation memory"),
        ("agent/orchestrator.py", "Tool orchestration"),
        ("agent/planner.py", "Query planner"),
    ]
    
    print("\nChecking required files:")
    all_exist = True
    for file_path, description in required_files:
        full_path = project_root / file_path
        exists = full_path.exists()
        status = "✅" if exists else "❌"
        print(f"  {status} {file_path:30s} - {description}")
        if not exists:
            all_exist = False
    
    if all_exist:
        print("\n✅ All required files present")
    else:
        print("\n❌ Missing files detected - this may cause import errors")

def show_recommendations():
    """Show recommendations for fixing issues"""
    print("\n" + "=" * 70)
    print("RECOMMENDATIONS")
    print("=" * 70)
    
    recommendations = [
        {
            "issue": "Import Errors",
            "solutions": [
                "Ensure PYTHONPATH includes workspace root",
                "Add __init__.py to agent/ directory",
                "Use absolute imports consistently",
                "Or use relative imports (from . import ...)"
            ]
        },
        {
            "issue": "Hidden Errors",
            "solutions": [
                "Set LOG_LEVEL=DEBUG in .env",
                "Add print() statements for debugging",
                "Check logs in real-time: tail -f logs/agent.log",
                "Use verbose=True in LLM initialization"
            ]
        },
        {
            "issue": "Tool Not Called",
            "solutions": [
                "Verify tools are in tools list (tools.tools)",
                "Check system prompt includes tool instructions",
                "Test with test_tool_calling.py",
                "Review LLM response for tool_calls attribute"
            ]
        },
        {
            "issue": "Context Not Preserved",
            "solutions": [
                "Check conversation_id is consistent",
                "Verify Redis is running and accessible",
                "Check MongoDB conversation storage",
                "Test with test_agent_conversation.py multi-turn test"
            ]
        }
    ]
    
    for rec in recommendations:
        print(f"\n🔧 {rec['issue']}:")
        for i, solution in enumerate(rec['solutions'], 1):
            print(f"   {i}. {solution}")

def main():
    print("\n" + "=" * 70)
    print("AGENT VERSION COMPARISON TOOL")
    print("=" * 70)
    print("\nThis tool compares the current agent implementation with the")
    print("legacy working version to identify potential issues.")
    
    # Run comparisons
    compare_imports()
    compare_logging()
    check_structure()
    show_recommendations()
    
    # Final advice
    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
1. Run the test suite to identify specific issues:
   python tests/run_all_tests.py

2. If tests fail, check the specific test output and:
   - Review DEBUGGING_GUIDE.md for detailed troubleshooting
   - Compare failing component with legacy version
   - Check logs for hidden errors

3. Common quick fixes:
   - Export PYTHONPATH=/workspace (for import issues)
   - Set LOG_LEVEL=DEBUG in .env (to see hidden errors)
   - Restart services: docker-compose restart

4. For deeper debugging:
   - Add print() statements to see execution flow
   - Run individual tests: python tests/test_tool_calling.py
   - Compare with legacy: git diff with older branches

5. If still stuck:
   - Check the specific error message in test output
   - Look for that error pattern in DEBUGGING_GUIDE.md
   - Try the legacy version to verify it works
    """)

if __name__ == "__main__":
    main()
