#!/usr/bin/env python3
"""
Simple evaluation runner for PMS Assistant
This script runs basic evaluation without complex dependencies.
"""

import asyncio
import json
import os
from typing import Dict, Any, List
from datetime import datetime

# Simple mock evaluator for demonstration
class SimplePMSEvaluator:
    """Simple evaluator for PMS responses"""

    async def evaluate_response_relevance(self, query: str, response: str) -> float:
        """Simple relevance evaluation"""
        if not response or response.startswith("Error"):
            return 0.0
        return 0.8  # Mock score

    async def evaluate_factual_accuracy(self, query: str, response: str) -> float:
        """Simple accuracy evaluation"""
        if not response or response.startswith("Error"):
            return 0.0
        return 0.7  # Mock score

    async def evaluate_response_completeness(self, query: str, response: str) -> float:
        """Simple completeness evaluation"""
        if not response or response.startswith("Error"):
            return 0.0
        return 0.9  # Mock score

    async def evaluate_pms_specific(self, query: str, response: str) -> Dict[str, float]:
        """PMS-specific evaluation metrics"""
        return {
            "relevance": await self.evaluate_response_relevance(query, response),
            "factual_accuracy": await self.evaluate_factual_accuracy(query, response),
            "completeness": await self.evaluate_response_completeness(query, response)
        }


class SimpleEvaluationPipeline:
    """Simple evaluation pipeline"""

    def __init__(self):
        self.evaluator = SimplePMSEvaluator()
        self.test_dataset = []

    def load_test_dataset(self):
        """Load the test dataset from file"""
        try:
            # Try multiple paths for the test dataset
            paths = ['../test_dataset.txt', 'test_dataset.txt', '/Users/harshith/pms-assistant/test_dataset.txt']

            for path in paths:
                try:
                    with open(path, 'r') as f:
                        content = f.read()
                    print(f"✅ Loaded test dataset from: {path}")
                    break
                except FileNotFoundError:
                    continue

            # Parse the test dataset
            lines = content.strip().split('\n')
            questions = [line.strip() for line in lines if line.strip() and not line.startswith('#')]

            # Skip header if present
            if questions and questions[0].lower() == 'questions':
                questions = questions[1:]

            self.test_dataset = questions[:10]  # Limit to first 10 for demo
            print(f"📋 Loaded {len(self.test_dataset)} test questions")

        except Exception as e:
            print(f"❌ Error loading test dataset: {e}")
            # Use some sample questions
            self.test_dataset = [
                "What is the status of the project Simpo?",
                "Show me all work items created by Vasiq.",
                "List all members of the MCU project."
            ]
            print(f"📋 Using {len(self.test_dataset)} sample questions")

    async def run_evaluation(self) -> List[Dict[str, Any]]:
        """Run evaluation on the test dataset"""
        if not self.test_dataset:
            return []

        results = []

        for i, query in enumerate(self.test_dataset):
            print(f"Evaluating {i+1}/{len(self.test_dataset)}: {query[:50]}...")

            # Mock response (in real implementation, this would call your agent)
            response = f"Mock response for: {query}"

            # Evaluate the response
            metrics = await self.evaluator.evaluate_pms_specific(query, response)

            result = {
                "query": query,
                "response": response,
                "metrics": metrics,
                "timestamp": datetime.now().isoformat()
            }

            results.append(result)
            print(f"  📊 Metrics: {metrics}")

        return results

    async def generate_evaluation_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a comprehensive evaluation report"""
        if not results:
            return {"error": "No results to analyze"}

        # Calculate average metrics
        metrics_data = [r["metrics"] for r in results]
        avg_metrics = {}

        if metrics_data:
            for key in metrics_data[0].keys():
                values = [m[key] for m in metrics_data]
                avg_metrics[f"avg_{key}"] = sum(values) / len(values)

        report = {
            "total_queries": len(results),
            "successful_queries": len(results),
            "failed_queries": 0,
            "success_rate": 1.0,
            "average_metrics": avg_metrics,
            "timestamp": datetime.now().isoformat()
        }

        # Save report to file
        with open('evaluation_report.json', 'w') as f:
            json.dump(report, f, indent=2)

        return report


async def main():
    """Main function to run the evaluation pipeline"""
    print("🚀 Starting Simple PMS Assistant Evaluation Pipeline...")
    print("=" * 60)

    pipeline = SimpleEvaluationPipeline()
    pipeline.load_test_dataset()

    print(f"📋 Evaluating {len(pipeline.test_dataset)} test questions...")

    # Run evaluation
    results = await pipeline.run_evaluation()

    # Generate report
    report = await pipeline.generate_evaluation_report(results)

    print("\n" + "=" * 60)
    print("📊 EVALUATION REPORT")
    print("=" * 60)

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
    print("\n💡 Next steps:")
    print("1. Start Phoenix server: python phoenix_server.py")
    print("2. Open browser to http://localhost:6006")
    print("3. Upload evaluation_report.json for analysis")


if __name__ == "__main__":
    asyncio.run(main())
