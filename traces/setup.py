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
from phoenix.evals import RelevanceEvaluator, QAEvaluator, ToxicityEvaluator
from phoenix.evals.models import OpenAIModel

# Local imports
from agent import MongoDBAgent
from constants import DATABASE_NAME


class PMSEvaluator:
    """Custom evaluators for Project Management System responses"""

    def __init__(self, mongodb_agent: MongoDBAgent):
        self.mongodb_agent = mongodb_agent
        self.relevance_evaluator = None
        self.qa_evaluator = None
        self.toxicity_evaluator = None

    async def initialize_evaluators(self):
        """Initialize Phoenix evaluators"""
        try:
            # Initialize Phoenix evaluators
            self.relevance_evaluator = RelevanceEvaluator()
            self.qa_evaluator = QAEvaluator()
            self.toxicity_evaluator = ToxicityEvaluator()

            print("✅ Phoenix evaluators initialized")
        except Exception as e:
            print(f"⚠️  Could not initialize some Phoenix evaluators: {e}")
            print("💡 Continuing with custom evaluators")

    async def evaluate_response_relevance(self, query: str, response: str) -> float:
        """Evaluate if the response is relevant to the query"""
        try:
            if self.relevance_evaluator:
                # Use Phoenix's RelevanceEvaluator
                result = await self.relevance_evaluator.async_evaluate(
                    query=query,
                    response=response
                )
                return result.score
            else:
                # Fallback custom implementation
                return await self._custom_relevance_evaluation(query, response)
        except Exception as e:
            print(f"Error in relevance evaluation: {e}")
            return await self._custom_relevance_evaluation(query, response)

    async def _custom_relevance_evaluation(self, query: str, response: str) -> float:
        """Custom relevance evaluation as fallback"""
        try:
            # Simple keyword overlap method
            query_terms = set(self._extract_keywords(query))
            response_terms = set(self._extract_keywords(response))

            if not query_terms:
                return 0.5

            overlap = len(query_terms.intersection(response_terms))
            return min(overlap / len(query_terms) * 1.2, 1.0)  # Slight boost for matches
        except Exception:
            return 0.5

    async def evaluate_factual_accuracy(self, query: str, response: str) -> float:
        """Evaluate factual accuracy of the response"""
        try:
            if self.qa_evaluator:
                # Use Phoenix's QAEvaluator for factual accuracy
                result = await self.qa_evaluator.async_evaluate(
                    query=query,
                    response=response
                )
                return result.score
            else:
                # Fallback custom implementation
                return await self._custom_factual_accuracy_evaluation(query, response)
        except Exception as e:
            print(f"Error in factual accuracy evaluation: {e}")
            return await self._custom_factual_accuracy_evaluation(query, response)

    async def _custom_factual_accuracy_evaluation(self, query: str, response: str) -> float:
        """Custom factual accuracy evaluation as fallback"""
        try:
            # Check for PMS-specific factual accuracy
            query_lower = query.lower()
            response_lower = response.lower()

            # Check for entity consistency
            expected_entities = self._extract_pms_entities(query_lower)
            found_entities = self._extract_pms_entities(response_lower)

            entity_match_score = 0.0
            if expected_entities:
                matched_entities = expected_entities.intersection(found_entities)
                entity_match_score = len(matched_entities) / len(expected_entities)

            # Check for numerical consistency (dates, counts, etc.)
            numerical_consistency = self._check_numerical_consistency(query_lower, response_lower)

            # Check for status/state consistency
            status_consistency = self._check_status_consistency(query_lower, response_lower)

            # Combine scores
            return (entity_match_score * 0.5 + numerical_consistency * 0.3 + status_consistency * 0.2)
        except Exception:
            return 0.5

    async def evaluate_response_completeness(self, query: str, response: str) -> float:
        """Evaluate if the response is complete and comprehensive"""
        try:
            # Custom completeness evaluation
            return await self._custom_completeness_evaluation(query, response)
        except Exception as e:
            print(f"Error in completeness evaluation: {e}")
            return await self._custom_completeness_evaluation(query, response)

    async def _custom_completeness_evaluation(self, query: str, response: str) -> float:
        """Custom completeness evaluation"""
        try:
            # Check response length relative to query complexity
            query_complexity = len(self._extract_keywords(query))
            response_length = len(self._extract_keywords(response))

            # Base score on length ratio
            if query_complexity == 0:
                return 0.5

            length_ratio = min(response_length / query_complexity, 2.0)
            length_score = min(length_ratio / 2.0, 1.0)

            # Check for comprehensive information
            completeness_indicators = [
                self._has_meaningful_content(response),
                self._has_specific_details(response),
                self._has_contextual_information(query, response)
            ]

            completeness_score = sum(completeness_indicators) / len(completeness_indicators)

            # Combine scores
            return (length_score * 0.6 + completeness_score * 0.4)
        except Exception:
            return 0.5

    async def evaluate_toxicity(self, response: str) -> float:
        """Evaluate if the response contains toxic content"""
        try:
            if self.toxicity_evaluator:
                result = await self.toxicity_evaluator.async_evaluate(response=response)
                return 1.0 - result.score  # Invert toxicity score (lower toxicity = higher score)
            else:
                return await self._custom_toxicity_evaluation(response)
        except Exception as e:
            print(f"Error in toxicity evaluation: {e}")
            return await self._custom_toxicity_evaluation(response)

    async def _custom_toxicity_evaluation(self, response: str) -> float:
        """Custom toxicity evaluation as fallback"""
        try:
            # Simple toxicity indicators
            toxic_words = ['error', 'fail', 'invalid', 'not found', 'cannot', 'unable']
            response_lower = response.lower()

            toxic_count = sum(1 for word in toxic_words if word in response_lower)
            toxicity_ratio = min(toxic_count / len(response.split()), 1.0)

            return max(1.0 - toxicity_ratio, 0.1)  # At least 0.1 score
        except Exception:
            return 0.8

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from text"""
        import re
        # Remove punctuation and split
        words = re.findall(r'\b\w+\b', text.lower())
        # Filter out common stop words
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'can'}
        return [word for word in words if word not in stop_words and len(word) > 2]

    def _extract_pms_entities(self, text: str) -> set:
        """Extract PMS-specific entities from text"""
        entities = set()
        text_lower = text.lower()

        # Project entities
        if any(word in text_lower for word in ['project', 'projects', 'simpo', 'isthara', 'mcu']):
            entities.add('project')

        # Member/User entities
        if any(word in text_lower for word in ['member', 'members', 'user', 'users', 'assignee', 'creator', 'vasiq', 'vikas', 'anand', 'prince']):
            entities.add('member')

        # Work item entities
        if any(word in text_lower for word in ['work item', 'workitem', 'task', 'tasks', 'bug', 'bugs', 'ticket']):
            entities.add('workitem')

        # Cycle entities
        if any(word in text_lower for word in ['cycle', 'cycles', 'sprint', 'sprints', 'iteration']):
            entities.add('cycle')

        # Status/State entities
        if any(word in text_lower for word in ['status', 'state', 'active', 'completed', 'backlog', 'not started', 'in progress']):
            entities.add('status')

        return entities

    def _check_numerical_consistency(self, query: str, response: str) -> float:
        """Check numerical consistency between query and response"""
        # Simple implementation - check for numbers
        import re
        query_numbers = re.findall(r'\d+', query)
        response_numbers = re.findall(r'\d+', response)

        if not query_numbers:
            return 1.0  # No numbers to check

        matches = sum(1 for num in query_numbers if num in response_numbers)
        return matches / len(query_numbers)

    def _check_status_consistency(self, query: str, response: str) -> float:
        """Check status/state consistency"""
        status_words = ['active', 'completed', 'in progress', 'not started', 'backlog', 'done', 'closed']
        query_lower = query.lower()
        response_lower = response.lower()

        query_statuses = [word for word in status_words if word in query_lower]
        response_statuses = [word for word in status_words if word in response_lower]

        if not query_statuses:
            return 1.0  # No statuses to check

        matches = sum(1 for status in query_statuses if status in response_statuses)
        return matches / len(query_statuses)

    def _has_meaningful_content(self, response: str) -> bool:
        """Check if response has meaningful content"""
        return len(response.strip()) > 20

    def _has_specific_details(self, response: str) -> bool:
        """Check if response contains specific details"""
        # Look for specific patterns like names, dates, IDs, etc.
        import re
        specific_patterns = [
            r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',  # Names like "John Doe"
            r'\d{4}-\d{2}-\d{2}',  # Dates like "2024-01-01"
            r'[A-Z]{2,}-\d+',  # IDs like "PROJ-123"
            r'\b\d+\s+(items?|tasks?|bugs?)\b'  # Counts like "5 items"
        ]

        return any(re.search(pattern, response, re.IGNORECASE) for pattern in specific_patterns)

    def _has_contextual_information(self, query: str, response: str) -> bool:
        """Check if response provides contextual information"""
        query_terms = set(self._extract_keywords(query))
        response_terms = set(self._extract_keywords(response))

        # Check if response adds new information beyond just echoing the query
        new_info = response_terms - query_terms
        return len(new_info) > len(query_terms) * 0.3  # At least 30% new information

    async def evaluate_pms_specific(self, query: str, response: str) -> Dict[str, float]:
        """PMS-specific evaluation metrics"""
        return {
            "relevance": await self.evaluate_response_relevance(query, response),
            "factual_accuracy": await self.evaluate_factual_accuracy(query, response),
            "completeness": await self.evaluate_response_completeness(query, response),
            "toxicity": await self.evaluate_toxicity(response)
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
        await self.evaluator.initialize_evaluators()

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
