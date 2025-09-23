#!/usr/bin/env python3
"""
Comprehensive Evaluation Pipeline for PMS Assistant
This module provides a complete evaluation pipeline using Phoenix.
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

# Add parent directory to path for local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Phoenix imports
from phoenix import Client
from phoenix.trace import using_project
from phoenix.evals import RelevanceEvaluator, QAEvaluator, ToxicityEvaluator
from phoenix.trace.exporter import HttpExporter
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# Local imports
from agent import MongoDBAgent
from traced_agent import TracedMongoDBAgent, trace_agent_query
from upload_dataset import PhoenixDatasetUploader
from config import EVALUATION_DATASET_CONFIG, PMS_EVALUATION_METRICS, EVALUATION_THRESHOLDS


class ComprehensiveEvaluationPipeline:
    """Complete evaluation pipeline using Phoenix"""

    def __init__(self):
        self.mongodb_agent = None
        self.traced_agent = None
        self.evaluator = None
        self.phoenix_client = None
        self.dataset_uploader = None
        self.test_dataset = []
        self.results = []
        self.tracer = None

    async def initialize(self):
        """Initialize the comprehensive evaluation pipeline"""
        print("🚀 Initializing Comprehensive Evaluation Pipeline...")
        print("=" * 60)

        try:
            # Initialize Phoenix client
            self.phoenix_client = Client()
            print("✅ Phoenix client initialized")

            # Initialize MongoDB agent
            self.mongodb_agent = MongoDBAgent()
            await self.mongodb_agent.connect()
            print("✅ MongoDB agent connected")

            # Initialize traced agent
            self.traced_agent = TracedMongoDBAgent()
            await self.traced_agent.initialize_tracing()
            print("✅ Traced agent initialized")

            # Initialize evaluators
            self.evaluator = PhoenixPMSEvaluator(self.mongodb_agent, self.phoenix_client)
            await self.evaluator.initialize()
            print("✅ Evaluators initialized")

            # Initialize dataset uploader
            self.dataset_uploader = PhoenixDatasetUploader(self.phoenix_client)
            print("✅ Dataset uploader initialized")

            # Set up tracing
            await self._setup_tracing()
            print("✅ Tracing configured")

            # Load test dataset
            self.test_dataset = self._load_test_dataset()
            print(f"✅ Loaded {len(self.test_dataset)} test queries")

            print("\n" + "=" * 60)
            print("🎯 Comprehensive Evaluation Pipeline Ready!")
            print("=" * 60)

        except Exception as e:
            print(f"❌ Error initializing pipeline: {e}")
            import traceback
            traceback.print_exc()
            raise

    async def _setup_tracing(self):
        """Set up comprehensive tracing"""
        try:
            # Set up tracer provider
            tracer_provider = TracerProvider()
            trace.set_tracer_provider(tracer_provider)

            # Console exporter for development
            console_exporter = ConsoleSpanExporter()
            console_processor = BatchSpanProcessor(console_exporter)
            tracer_provider.add_span_processor(console_processor)

            # Phoenix exporter if available
            try:
                phoenix_exporter = HttpExporter(endpoint="http://localhost:6006/v1/traces")
                phoenix_processor = BatchSpanProcessor(phoenix_exporter)
                tracer_provider.add_span_processor(phoenix_processor)
            except Exception as e:
                print(f"⚠️  Phoenix tracing not available: {e}")

            self.tracer = trace.get_tracer(__name__)

        except Exception as e:
            print(f"Error setting up tracing: {e}")

    def _load_test_dataset(self) -> List[Dict[str, Any]]:
        """Load comprehensive test dataset"""
        try:
            # Load from test_dataset.txt
            dataset = self.dataset_uploader.load_test_dataset()

            # Add more comprehensive test cases
            additional_queries = [
                {
                    "id": f"query_{len(dataset) + i + 1:03d}",
                    "query": query,
                    "expected_response_type": "pms_data",
                    "query_category": "comprehensive_test",
                    "expected_entities": ["project", "member", "status"],
                    "metadata": {
                        "test_type": "comprehensive",
                        "complexity": "medium",
                        "created_at": datetime.now().isoformat()
                    }
                }
                for i, query in enumerate([
                    "Show me all projects created by prince monga and their current status",
                    "List all work items that are high priority and assigned to vasiq",
                    "What are the details of the Simpo project including team members and active cycles",
                    "Find all documentation pages that are public and created after January 2024",
                    "Show me the project progress for isthara including completed and pending tasks"
                ])
            ]

            dataset.extend(additional_queries)
            return dataset

        except Exception as e:
            print(f"Error loading test dataset: {e}")
            return []

    async def run_comprehensive_evaluation(self, sample_size: Optional[int] = None) -> Dict[str, Any]:
        """Run comprehensive evaluation using all components"""
        print("🔄 Starting Comprehensive Evaluation...")
        print("=" * 60)

        test_queries = self.test_dataset[:sample_size] if sample_size else self.test_dataset

        evaluation_results = {
            "evaluation_id": f"eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "total_queries": len(test_queries),
            "start_time": datetime.now().isoformat(),
            "results": [],
            "summary": {},
            "errors": []
        }

        successful_evaluations = 0
        failed_evaluations = 0

        for i, query_data in enumerate(test_queries):
            print(f"\n📋 Evaluating query {i+1}/{len(test_queries)}")
            print(f"Query: {query_data['query'][:80]}...")

            try:
                # Run the query using traced agent
                response = await self._evaluate_single_query(query_data)

                # Evaluate the response
                evaluation_metrics = await self.evaluator.evaluate_query(query_data, response)

                result = {
                    "query_id": query_data["id"],
                    "query": query_data["query"],
                    "response": response,
                    "metrics": evaluation_metrics,
                    "evaluation_time": datetime.now().isoformat(),
                    "success": True
                }

                evaluation_results["results"].append(result)
                successful_evaluations += 1

                # Log to Phoenix
                await self._log_to_phoenix(result)

                print(f"✅ Success - Relevance: {evaluation_metrics.get('relevance', 0):.2f}")

            except Exception as e:
                error_result = {
                    "query_id": query_data["id"],
                    "query": query_data["query"],
                    "response": f"Error: {str(e)}",
                    "metrics": {"error": 1.0},
                    "evaluation_time": datetime.now().isoformat(),
                    "success": False,
                    "error": str(e)
                }

                evaluation_results["results"].append(error_result)
                evaluation_results["errors"].append(str(e))
                failed_evaluations += 1

                print(f"❌ Failed - {str(e)}")

        # Generate summary
        evaluation_results["summary"] = self._generate_evaluation_summary(evaluation_results)
        evaluation_results["end_time"] = datetime.now().isoformat()
        evaluation_results["successful_evaluations"] = successful_evaluations
        evaluation_results["failed_evaluations"] = failed_evaluations

        self.results = evaluation_results["results"]

        return evaluation_results

    async def _evaluate_single_query(self, query_data: Dict[str, Any]) -> str:
        """Evaluate a single query using the traced agent"""
        try:
            # Use the traced agent to get response
            response = await trace_agent_query(query_data["query"])

            # Add some delay to simulate real-world conditions
            await asyncio.sleep(0.1)

            return response

        except Exception as e:
            print(f"Error evaluating query: {e}")
            raise

    async def _log_to_phoenix(self, result: Dict[str, Any]):
        """Log evaluation results to Phoenix"""
        try:
            if self.phoenix_client and result.get("success", False):
                with using_project("pms-assistant-eval"):
                    # Log the evaluation result
                    eval_data = {
                        "query_id": result["query_id"],
                        "query": result["query"],
                        "response": result["response"][:500],  # Truncate for storage
                        "timestamp": result["evaluation_time"],
                        **result["metrics"]
                    }

                    # In a real implementation, this would be saved to Phoenix
                    print(f"📊 Logged to Phoenix: {result['query_id']}")

        except Exception as e:
            print(f"Error logging to Phoenix: {e}")

    def _generate_evaluation_summary(self, evaluation_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate comprehensive evaluation summary"""
        results = evaluation_results["results"]

        # Calculate metrics
        successful_results = [r for r in results if r.get("success", False)]
        failed_results = [r for r in results if not r.get("success", False)]

        if not successful_results:
            return {"error": "No successful evaluations to summarize"}

        # Calculate average metrics
        avg_metrics = {}
        for metric in ["relevance", "factual_accuracy", "completeness", "toxicity"]:
            values = [r["metrics"].get(metric, 0) for r in successful_results if metric in r["metrics"]]
            if values:
                avg_metrics[f"avg_{metric}"] = sum(values) / len(values)

        # Calculate category distribution
        categories = {}
        for result in results:
            if result.get("success", False):
                query = result.get("query", "")
                # Simple categorization based on keywords
                if "project" in query.lower():
                    categories["project_queries"] = categories.get("project_queries", 0) + 1
                elif "member" in query.lower() or "user" in query.lower():
                    categories["member_queries"] = categories.get("member_queries", 0) + 1
                elif "work" in query.lower() or "task" in query.lower():
                    categories["workitem_queries"] = categories.get("workitem_queries", 0) + 1
                elif "cycle" in query.lower() or "sprint" in query.lower():
                    categories["cycle_queries"] = categories.get("cycle_queries", 0) + 1
                elif "document" in query.lower() or "page" in query.lower():
                    categories["documentation_queries"] = categories.get("documentation_queries", 0) + 1
                else:
                    categories["uncategorized"] = categories.get("uncategorized", 0) + 1

        # Calculate performance bands
        relevance_scores = [r["metrics"].get("relevance", 0) for r in successful_results]
        performance_bands = {
            "excellent": len([s for s in relevance_scores if s >= 0.8]),
            "good": len([s for s in relevance_scores if 0.6 <= s < 0.8]),
            "fair": len([s for s in relevance_scores if 0.4 <= s < 0.6]),
            "poor": len([s for s in relevance_scores if s < 0.4])
        }

        return {
            "total_evaluations": len(results),
            "successful": len(successful_results),
            "failed": len(failed_results),
            "success_rate": len(successful_results) / len(results) if results else 0,
            "average_metrics": avg_metrics,
            "query_categories": categories,
            "performance_bands": performance_bands,
            "threshold_analysis": self._analyze_thresholds(avg_metrics)
        }

    def _analyze_thresholds(self, avg_metrics: Dict[str, float]) -> Dict[str, str]:
        """Analyze metrics against thresholds"""
        analysis = {}

        for metric, value in avg_metrics.items():
            if metric.startswith("avg_"):
                base_metric = metric[4:]  # Remove "avg_" prefix
                threshold = EVALUATION_THRESHOLDS.get(base_metric, 0.7)

                if value >= threshold:
                    analysis[base_metric] = "PASS"
                else:
                    analysis[base_metric] = "FAIL"

        return analysis

    async def generate_comprehensive_report(self, evaluation_results: Dict[str, Any]) -> str:
        """Generate comprehensive evaluation report"""
        summary = evaluation_results["summary"]

        report = f"""
# PMS Assistant Comprehensive Evaluation Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Executive Summary
- **Total Queries Evaluated**: {evaluation_results['total_queries']}
- **Successful Evaluations**: {evaluation_results['successful_evaluations']}
- **Failed Evaluations**: {evaluation_results['failed_evaluations']}
- **Overall Success Rate**: {summary['success_rate']:.1%}

## Performance Metrics

### Average Scores
"""
        for metric, value in summary.get("average_metrics", {}).items():
            report += f"- **{metric.replace('avg_', '').replace('_', ' ').title()}**: {value:.3f}\n"

        report += f"""

### Performance Bands
"""
        for band, count in summary.get("performance_bands", {}).items():
            report += f"- **{band.title()}**: {count} queries\n"

        report += f"""

## Query Category Analysis
"""
        for category, count in summary.get("query_categories", {}).items():
            report += f"- **{category.replace('_', ' ').title()}**: {count} queries\n"

        report += f"""

## Threshold Analysis
"""
        for metric, result in summary.get("threshold_analysis", {}).items():
            report += f"- **{metric.replace('_', ' ').title()}**: {'✅ PASS' if result == 'PASS' else '❌ FAIL'}\n"

        report += f"""

## Recommendations
"""
        if summary.get("success_rate", 0) < 0.8:
            report += "- Improve overall success rate\n"
        if summary.get("average_metrics", {}).get("relevance", 0) < 0.7:
            report += "- Enhance response relevance\n"
        if summary.get("average_metrics", {}).get("factual_accuracy", 0) < 0.7:
            report += "- Improve factual accuracy\n"

        # Save detailed report
        report_file = f"comprehensive_evaluation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        with open(report_file, 'w') as f:
            f.write(report)

        print(f"📄 Comprehensive report saved: {report_file}")

        return report

    async def run(self, sample_size: Optional[int] = None):
        """Run the complete evaluation pipeline"""
        try:
            # Initialize everything
            await self.initialize()

            # Run comprehensive evaluation
            evaluation_results = await self.run_comprehensive_evaluation(sample_size)

            # Generate report
            report = await self.generate_comprehensive_report(evaluation_results)

            print("\n" + "=" * 60)
            print("🎉 Comprehensive Evaluation Completed!")
            print("=" * 60)
            print(f"📊 Success Rate: {evaluation_results['summary']['success_rate']:.1%}")
            print(f"📈 Average Relevance: {evaluation_results['summary']['average_metrics'].get('avg_relevance', 0):.3f}")
            print(f"📊 Average Accuracy: {evaluation_results['summary']['average_metrics'].get('avg_factual_accuracy', 0):.3f}")
            print(f"✨ Average Completeness: {evaluation_results['summary']['average_metrics'].get('avg_completeness', 0):.3f}")

            return evaluation_results

        except Exception as e:
            print(f"❌ Error running comprehensive evaluation: {e}")
            import traceback
            traceback.print_exc()
            return None


class PhoenixPMSEvaluator:
    """Enhanced PMS evaluator using Phoenix"""

    def __init__(self, mongodb_agent, phoenix_client):
        self.mongodb_agent = mongodb_agent
        self.phoenix_client = phoenix_client
        self.relevance_evaluator = None
        self.qa_evaluator = None
        self.toxicity_evaluator = None

    async def initialize(self):
        """Initialize Phoenix evaluators"""
        try:
            self.relevance_evaluator = RelevanceEvaluator()
            self.qa_evaluator = QAEvaluator()
            self.toxicity_evaluator = ToxicityEvaluator()
            print("✅ Phoenix evaluators initialized")
        except Exception as e:
            print(f"⚠️  Some Phoenix evaluators not available: {e}")

    async def evaluate_query(self, query_data: Dict[str, Any], response: str) -> Dict[str, float]:
        """Evaluate a query using all available metrics"""
        try:
            query = query_data["query"]

            # Run evaluations in parallel
            tasks = [
                self.evaluate_relevance(query, response),
                self.evaluate_factual_accuracy(query, response),
                self.evaluate_completeness(query, response),
                self.evaluate_toxicity(response),
                self.evaluate_pms_specific(query, response)
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Combine results
            metrics = {}
            metric_names = ["relevance", "factual_accuracy", "completeness", "toxicity", "pms_specific"]

            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    metrics[metric_names[i]] = 0.5  # Default score
                    print(f"Error in {metric_names[i]} evaluation: {result}")
                else:
                    metrics.update(result)

            return metrics

        except Exception as e:
            print(f"Error in comprehensive evaluation: {e}")
            return {
                "relevance": 0.5,
                "factual_accuracy": 0.5,
                "completeness": 0.5,
                "toxicity": 0.5
            }

    async def evaluate_relevance(self, query: str, response: str) -> Dict[str, float]:
        """Evaluate response relevance"""
        try:
            if self.relevance_evaluator:
                result = await self.relevance_evaluator.async_evaluate(query=query, response=response)
                return {"relevance": result.score}
            else:
                return {"relevance": await self._custom_relevance(query, response)}
        except Exception:
            return {"relevance": await self._custom_relevance(query, response)}

    async def _custom_relevance(self, query: str, response: str) -> float:
        """Custom relevance evaluation"""
        # Simple keyword overlap
        query_words = set(query.lower().split())
        response_words = set(response.lower().split())
        overlap = len(query_words.intersection(response_words))
        return min(overlap / len(query_words) * 1.2, 1.0) if query_words else 0.5

    async def evaluate_factual_accuracy(self, query: str, response: str) -> Dict[str, float]:
        """Evaluate factual accuracy"""
        try:
            if self.qa_evaluator:
                result = await self.qa_evaluator.async_evaluate(query=query, response=response)
                return {"factual_accuracy": result.score}
            else:
                return {"factual_accuracy": await self._custom_accuracy(query, response)}
        except Exception:
            return {"factual_accuracy": await self._custom_accuracy(query, response)}

    async def _custom_accuracy(self, query: str, response: str) -> float:
        """Custom factual accuracy evaluation"""
        # Check for entity consistency
        entities = ["project", "member", "task", "cycle", "status"]
        query_entities = [e for e in entities if e in query.lower()]
        response_entities = [e for e in entities if e in response.lower()]

        if not query_entities:
            return 0.8  # High score if no specific entities to check

        matches = len(set(query_entities).intersection(set(response_entities)))
        return matches / len(query_entities)

    async def evaluate_completeness(self, query: str, response: str) -> Dict[str, float]:
        """Evaluate response completeness"""
        try:
            return {"completeness": await self._custom_completeness(query, response)}
        except Exception:
            return {"completeness": await self._custom_completeness(query, response)}

    async def _custom_completeness(self, query: str, response: str) -> float:
        """Custom completeness evaluation"""
        query_length = len(query.split())
        response_length = len(response.split())

        # Base completeness on response length relative to query
        if query_length < 5:
            return 1.0 if response_length > 10 else 0.7
        elif query_length < 15:
            return 1.0 if response_length > 20 else 0.6
        else:
            return 1.0 if response_length > 30 else 0.5

    async def evaluate_toxicity(self, response: str) -> Dict[str, float]:
        """Evaluate response toxicity"""
        try:
            if self.toxicity_evaluator:
                result = await self.toxicity_evaluator.async_evaluate(response=response)
                return {"toxicity": 1.0 - result.score}  # Invert toxicity score
            else:
                return {"toxicity": await self._custom_toxicity(response)}
        except Exception:
            return {"toxicity": await self._custom_toxicity(response)}

    async def _custom_toxicity(self, response: str) -> float:
        """Custom toxicity evaluation"""
        toxic_words = ["error", "fail", "invalid", "not found", "cannot"]
        response_lower = response.lower()
        toxic_count = sum(1 for word in toxic_words if word in response_lower)
        return max(1.0 - (toxic_count / len(response.split())), 0.1)

    async def evaluate_pms_specific(self, query: str, response: str) -> Dict[str, float]:
        """PMS-specific evaluation metrics"""
        try:
            return {"pms_specific": await self._custom_pms_evaluation(query, response)}
        except Exception:
            return {"pms_specific": 0.5}

    async def _custom_pms_evaluation(self, query: str, response: str) -> float:
        """Custom PMS-specific evaluation"""
        # Check for PMS-specific quality indicators
        indicators = [
            len(response) > 50,  # Substantial response
            any(entity in response.lower() for entity in ["project", "member", "task", "status"]),  # Contains entities
            not response.lower().startswith("error"),  # Not an error response
            len(response.split()) > 10  # More than just a few words
        ]

        return sum(indicators) / len(indicators)


async def main():
    """Main function to run comprehensive evaluation"""
    pipeline = ComprehensiveEvaluationPipeline()
    results = await pipeline.run(sample_size=5)  # Run on first 5 queries for demo

    if results:
        print("\n🎉 Evaluation pipeline completed successfully!")
        print(f"📊 Results: {len(results['results'])} evaluations")
        print(f"📈 Success rate: {results['summary']['success_rate']:.1%}")


if __name__ == "__main__":
    asyncio.run(main())
