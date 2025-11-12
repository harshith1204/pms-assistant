"""
Master test runner - Runs all debug tests in sequence.

This provides a comprehensive report of what's working and what's not.
"""
import asyncio
import sys
from pathlib import Path
import importlib.util
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def load_test_module(test_file):
    """Dynamically load a test module"""
    spec = importlib.util.spec_from_file_location("test_module", test_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

async def run_test_suite(test_name, test_file):
    """Run a single test suite and return results"""
    print("\n" + "=" * 70)
    print(f"RUNNING: {test_name}")
    print("=" * 70)
    
    try:
        # Load and run the test module
        module = load_test_module(test_file)
        
        # Run the main function
        if hasattr(module, 'main'):
            success = await module.main()
            return success
        else:
            print(f"⚠️ Test module {test_name} has no main() function")
            return False
    except Exception as e:
        print(f"❌ Failed to run {test_name}: {e}")
        import traceback
        traceback.print_exc()
        return False

async def main():
    """Run all test suites"""
    print("=" * 70)
    print("COMPREHENSIVE AGENT DEBUG TEST SUITE")
    print("=" * 70)
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Load environment
    from dotenv import load_dotenv
    load_dotenv()
    
    tests_dir = Path(__file__).parent
    
    # Define test suites in order
    test_suites = [
        ("Tool Calling Tests", tests_dir / "test_tool_calling.py"),
        ("Agent Conversation Tests", tests_dir / "test_agent_conversation.py"),
        ("WebSocket Interaction Tests", tests_dir / "test_websocket_interaction.py"),
    ]
    
    results = {}
    
    # Run each test suite
    for test_name, test_file in test_suites:
        if not test_file.exists():
            print(f"\n⚠️ Test file not found: {test_file}")
            results[test_name] = False
            continue
        
        try:
            success = await run_test_suite(test_name, test_file)
            results[test_name] = success
        except KeyboardInterrupt:
            print("\n\n⚠️ Testing interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Unexpected error in {test_name}: {e}")
            results[test_name] = False
    
    # Print final summary
    print("\n" + "=" * 70)
    print("FINAL TEST SUMMARY")
    print("=" * 70)
    print(f"Completed at: {datetime.now().isoformat()}\n")
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{test_name:40s}: {status}")
    
    total = len(results)
    passed = sum(results.values())
    percentage = (passed / total * 100) if total > 0 else 0
    
    print(f"\n{'=' * 70}")
    print(f"OVERALL: {passed}/{total} test suites passed ({percentage:.1f}%)")
    print("=" * 70)
    
    if passed == total:
        print("\n🎉 All tests passed! Agent is working correctly.")
        return True
    elif passed == 0:
        print("\n❌ All tests failed. Major issues detected.")
        print("\nTroubleshooting steps:")
        print("1. Check if MongoDB and Qdrant are running")
        print("2. Verify .env file has correct credentials")
        print("3. Check if required dependencies are installed")
        print("4. Review DEBUGGING_GUIDE.md for common issues")
        return False
    else:
        print(f"\n⚠️ Some tests failed. Check output above for details.")
        print("\nFailed test suites:")
        for test_name, passed in results.items():
            if not passed:
                print(f"  - {test_name}")
        print("\nReview DEBUGGING_GUIDE.md for troubleshooting steps.")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTesting interrupted by user")
        sys.exit(130)
