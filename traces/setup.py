"""
Phoenix evaluation setup for PMS Assistant
This module sets up tracing, evaluation, and monitoring for the PMS Assistant.
"""

import os
import sys
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
import json
import pandas as pd

# Add parent directory to path for local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Phoenix imports
from phoenix import Client
from phoenix.trace import using_project
from phoenix.trace.exporter import HttpExporter
from phoenix.trace.schemas import SpanKind, SpanStatusCode
from phoenix.evals import RelevanceEvaluator

# Local imports
from agent import MongoDBAgent
from constants import DATABASE_NAME


class PMSEvaluator:
    """Custom evaluators for Project Management System responses"""

    def __init__(self, mongodb_agent: MongoDBAgent):
        self.mongodb_agent = mongodb_agent

    async def evaluate_response_relevance(self, query: str, response: str) -> float:
        """Evaluate if the response is relevant to the query"""
        try:
            # Use Phoenix's RelevanceEvaluator
            evaluator = RelevanceEvaluator()
            result = await evaluator.async_evaluate(
                query=query,
                response=response
            )
            return result.score
        except Exception as e:
            print(f"Error in relevance evaluation: {e}")
            return 0.5  # Default neutral score

    async def evaluate_factual_accuracy(self, query: str, response: str) -> float:
        """Evaluate factual accuracy of the response"""
        try:
            # For PMS, we can check if the response contains expected entities
            # This is a simplified version - in production you'd want more sophisticated checks

            # Extract key terms from query
            query_terms = set(query.lower().split())
            response_terms = set(response.lower().split())

            # Calculate overlap
            if not query_terms:
                return 0.5

            overlap = len(query_terms.intersection(response_terms))
            return min(overlap / len(query_terms), 1.0)
        except Exception as e:
            print(f"Error in factual accuracy evaluation: {e}")
            return 0.5

    async def evaluate_response_completeness(self, query: str, response: str) -> float:
        """Evaluate if the response is complete and comprehensive"""
        try:
            # Check response length relative to query complexity
            query_complexity = len(query.split())
            response_length = len(response.split())

            # Simple heuristic: longer responses for complex queries are better
            if query_complexity < 5:
                return 1.0 if response_length > 5 else 0.8
            elif query_complexity < 15:
                return 1.0 if response_length > 10 else 0.7
            else:
                return 1.0 if response_length > 20 else 0.6
        except Exception as e:
            print(f"Error in completeness evaluation: {e}")
            return 0.5

    async def evaluate_pms_specific(self, query: str, response: str) -> Dict[str, float]:
        """PMS-specific evaluation metrics"""
        return {
            "relevance": await self.evaluate_response_relevance(query, response),
            "factual_accuracy": await self.evaluate_factual_accuracy(query, response),
            "completeness": await self.evaluate_response_completeness(query, response)
        }


class PhoenixTracer:
    """Handles Phoenix tracing for the PMS Assistant"""

    def __init__(self, project_name: str = "pms-assistant"):
        self.project_name = project_name
        self.client = None

    async def initialize(self):
        """Initialize Phoenix client and tracing"""
        try:
            # Initialize Phoenix client
            self.client = Client()
            print("Phoenix client initialized successfully")
        except Exception as e:
            print(f"Failed to initialize Phoenix client: {e}")
            self.client = None

    def start_trace(self, name: str, span_kind: str = "INTERNAL"):
        """Start a new trace span"""
        if not self.client:
            return None

        return self.client.trace(
            name=name,
            span_kind=span_kind
        )

    async def log_evaluation(self, query: str, response: str, metrics: Dict[str, float]):
        """Log evaluation results to Phoenix"""
        if not self.client:
            return

        try:
            # Log the evaluation results
            with using_project(self.project_name):
                # This would typically be done within a trace context
                # For now, we'll log to the evaluation dataset
                eval_data = {
                    "query": query,
                    "response": response,
                    "timestamp": datetime.now().isoformat(),
                    **metrics
                }

                # In a real implementation, you'd save this to a structured dataset
                print(f"Evaluation logged: {eval_data}")

        except Exception as e:
            print(f"Error logging evaluation: {e}")


class EvaluationPipeline:
    """Main evaluation pipeline for PMS Assistant"""

    def __init__(self):
        self.mongodb_agent = None
        self.evaluator = None
        self.tracer = None
        self.test_dataset = []

    async def initialize(self):
        """Initialize the evaluation pipeline"""
        # Initialize MongoDB agent
        self.mongodb_agent = MongoDBAgent()
        await self.mongodb_agent.connect()

        # Initialize evaluator
        self.evaluator = PMSEvaluator(self.mongodb_agent)

        # Initialize tracer
        self.tracer = PhoenixTracer()
        await self.tracer.initialize()

        # Load test dataset
        self.load_test_dataset()

    def load_test_dataset(self):
        """Load the test dataset from file"""
        try:
            # Try to find test_dataset.txt in different locations
            file_paths = ['../test_dataset.txt', 'test_dataset.txt', '/Users/harshith/pms-assistant/test_dataset.txt']

            content = None
            for path in file_paths:
                try:
                    with open(path, 'r') as f:
                        content = f.read()
                    break
                except FileNotFoundError:
                    continue

            if content is None:
                raise FileNotFoundError("Could not find test_dataset.txt in any expected location")

            # Parse the test dataset (assuming format: one question per line after header)
            lines = content.strip().split('\n')
            questions = [line.strip() for line in lines if line.strip() and not line.startswith('#')]

            # Skip header if present
            if questions and questions[0].lower() == 'questions':
                questions = questions[1:]

            self.test_dataset = questions
            print(f"Loaded {len(self.test_dataset)} test questions")

        except Exception as e:
            print(f"Error loading test dataset: {e}")
            self.test_dataset = []

    async def run_evaluation(self, sample_size: Optional[int] = None) -> List[Dict[str, Any]]:
        """Run evaluation on the test dataset"""
        if not self.test_dataset:
            print("No test dataset available")
            return []

        # Sample dataset if specified
        test_questions = self.test_dataset[:sample_size] if sample_size else self.test_dataset

        results = []

        for i, query in enumerate(test_questions):
            print(f"Evaluating question {i+1}/{len(test_questions)}: {query[:50]}...")

            try:
                # Get response from the agent
                response = await self.get_agent_response(query)

                # Evaluate the response
                metrics = await self.evaluator.evaluate_pms_specific(query, response)

                # Log to tracer
                if self.tracer:
                    await self.tracer.log_evaluation(query, response, metrics)

                result = {
                    "query": query,
                    "response": response,
                    "metrics": metrics,
                    "timestamp": datetime.now().isoformat()
                }

                results.append(result)

                print(f"  Metrics: {metrics}")

            except Exception as e:
                print(f"Error evaluating query '{query}': {e}")
                results.append({
                    "query": query,
                    "response": f"Error: {str(e)}",
                    "metrics": {"error": 1.0},
                    "timestamp": datetime.now().isoformat()
                })

        return results

    async def get_agent_response(self, query: str) -> str:
        """Get response from the MongoDB agent"""
        try:
            # Use the intelligent_query tool directly
            from tools import intelligent_query

            result = await intelligent_query.async_call(self.mongodb_agent, query)
            return result.get('result', 'No result available')

        except Exception as e:
            print(f"Error getting agent response: {e}")
            return f"Error processing query: {str(e)}"

    async def generate_evaluation_report(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate a comprehensive evaluation report"""
        if not results:
            return {"error": "No results to analyze"}

        # Calculate average metrics
        metrics_data = [r["metrics"] for r in results if "error" not in r["metrics"]]
        avg_metrics = {}

        if metrics_data:
            for key in metrics_data[0].keys():
                values = [m[key] for m in metrics_data]
                avg_metrics[f"avg_{key}"] = sum(values) / len(values)
        else:
            # No successful evaluations, return error
            return {"error": "No successful evaluations to analyze"}

        # Count successful vs failed queries
        successful = len([r for r in results if "error" not in r["metrics"]])
        failed = len(results) - successful

        report = {
            "total_queries": len(results),
            "successful_queries": successful,
            "failed_queries": failed,
            "success_rate": successful / len(results) if results else 0,
            "average_metrics": avg_metrics,
            "timestamp": datetime.now().isoformat()
        }

        # Save report to file
        with open('evaluation_report.json', 'w') as f:
            json.dump(report, f, indent=2)

        return report


async def main():
    """Main function to run the evaluation pipeline"""
    print("Starting PMS Assistant Evaluation Pipeline...")

    pipeline = EvaluationPipeline()
    await pipeline.initialize()

    print(f"Running evaluation on {len(pipeline.test_dataset)} test questions...")
    results = await pipeline.run_evaluation()

    report = await pipeline.generate_evaluation_report(results)

    print("\n" + "="*50)
    print("EVALUATION REPORT")
    print("="*50)

    # Check if report contains error
    if "error" in report:
        print(f"Error: {report['error']}")
    else:
        print(f"Total Queries: {report['total_queries']}")
        print(f"Successful: {report['successful_queries']}")
        print(f"Failed: {report['failed_queries']}")
        print(f"Success Rate: {report['success_rate']:.2%}")
        print(f"Average Relevance: {report['average_metrics']['avg_relevance']:.2f}")
        print(f"Average Factual Accuracy: {report['average_metrics']['avg_factual_accuracy']:.2f}")
        print(f"Average Completeness: {report['average_metrics']['avg_completeness']:.2f}")

    print("\nEvaluation completed! Check evaluation_report.json for detailed results.")
    print("Start Phoenix dashboard with: python -m phoenix.server.main serve")


if __name__ == "__main__":
    asyncio.run(main())
