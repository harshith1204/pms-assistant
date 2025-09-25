#!/usr/bin/env python3
"""
Standalone evaluation runner for PMS Assistant
This script runs the evaluation pipeline independently.
"""

import asyncio
import sys
import os

# Add parent directory to path to import local modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from setup import EvaluationPipeline
from setup import PhoenixTracer


async def main():
    """Main function to run the evaluation pipeline"""
    print("🚀 Starting PMS Assistant Evaluation Pipeline...")
    print("=" * 60)

    # Initialize and run evaluation pipeline
    try:
        pipeline = EvaluationPipeline()
        await pipeline.initialize()

        print(f"📋 Found {len(pipeline.test_dataset)} test questions")

        # Ask user if they want to run full evaluation
        run_evaluation = input("\nRun full evaluation on test dataset? (y/n): ").lower().strip()

        if run_evaluation == 'y':
            print("\n🔄 Running evaluation...")
            results = await pipeline.run_evaluation()

            # Generate and display report
            report = await pipeline.generate_evaluation_report(results)

            print("\n" + "=" * 60)
            print("📊 EVALUATION REPORT")
            print("=" * 60)

            # Check if report contains error
            if "error" in report:
                print(f"❌ Error: {report['error']}")
            else:
                print(f"✅ Total Queries: {report['total_queries']}")
                print(f"✅ Successful: {report['successful_queries']}")
                print(f"❌ Failed: {report['failed_queries']}")
                print(f"📈 Success Rate: {report['success_rate']:.2%}")
                print(f"🎯 Avg Relevance: {report['average_metrics']['avg_relevance']:.2f}")
                print(f"📊 Avg Accuracy: {report['average_metrics']['avg_factual_accuracy']:.2f}")
                print(f"✨ Avg Completeness: {report['average_metrics']['avg_completeness']:.2f}")

            print("\n📁 Evaluation completed!")
            print("📄 Check evaluation_report.json for detailed results")

        else:
            print("⏭️  Skipping evaluation run")

    except Exception as e:
        print(f"❌ Error running evaluation: {e}")
        import traceback
        traceback.print_exc()

    print("\n💡 Tip: Start Phoenix server separately with: python phoenix.py")


if __name__ == "__main__":
    asyncio.run(main())
