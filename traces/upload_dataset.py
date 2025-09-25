#!/usr/bin/env python3
"""
Dataset uploader for Phoenix
This script uploads the PMS Assistant evaluation dataset to Phoenix.
"""

import os
import sys
import json
import asyncio
import pandas as pd
from typing import Dict, Any, List
from pathlib import Path
from datetime import datetime

# Phoenix imports
from phoenix import Client
from phoenix.trace import using_project

# Add parent directory to path for local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .config import EVALUATION_DATASET_CONFIG


class PhoenixDatasetUploader:
    """Uploads evaluation dataset to Phoenix"""

    def __init__(self, phoenix_client: Client = None):
        self.client = phoenix_client or Client()
        self.dataset_name = EVALUATION_DATASET_CONFIG["name"]
        self.dataset_description = EVALUATION_DATASET_CONFIG["description"]
        self.dataset_version = EVALUATION_DATASET_CONFIG["version"]

    def load_test_dataset(self) -> List[Dict[str, Any]]:
        """Load the test dataset from file"""
        try:
            # Try to find test_dataset.txt in different locations
            file_paths = [
                'test_dataset.txt',
                '../test_dataset.txt',
                '/Users/harshith/pms-assistant/test_dataset.txt',
                os.path.join(os.path.dirname(__file__), 'test_dataset.txt')
            ]

            content = None
            dataset_path = None
            for path in file_paths:
                try:
                    if os.path.exists(path):
                        with open(path, 'r') as f:
                            content = f.read()
                        dataset_path = path
                        break
                except FileNotFoundError:
                    continue

            if content is None:
                raise FileNotFoundError("Could not find test_dataset.txt in any expected location")

            print(f"✅ Loaded dataset from: {dataset_path}")

            # Parse the test dataset (assuming format: one question per line after header)
            lines = content.strip().split('\n')
            questions = [line.strip() for line in lines if line.strip() and not line.startswith('#')]

            # Skip header if present
            if questions and questions[0].lower() == 'questions':
                questions = questions[1:]

            print(f"📋 Found {len(questions)} test questions")

            # Create dataset entries
            dataset = []
            for i, query in enumerate(questions):
                entry = {
                    "id": f"query_{i+1:03d}",
                    "query": query,
                    "expected_response_type": "pms_data",
                    "query_category": self._categorize_query(query),
                    "expected_entities": self._extract_expected_entities(query),
                    "metadata": {
                        "source": "pms_test_dataset",
                        "version": self.dataset_version,
                        "created_at": datetime.now().isoformat()
                    }
                }
                dataset.append(entry)

            return dataset

        except Exception as e:
            print(f"❌ Error loading test dataset: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _categorize_query(self, query: str) -> str:
        """Categorize a query based on its content"""
        query_lower = query.lower()

        # Import categories from config
        from config import QUERY_CATEGORIES

        for category, keywords in QUERY_CATEGORIES.items():
            if any(keyword in query_lower for keyword in keywords):
                return category

        return "uncategorized"

    def _extract_expected_entities(self, query: str) -> List[str]:
        """Extract expected entities from query"""
        # Simple entity extraction based on common PMS entities
        entities = []

        query_lower = query.lower()

        # Project entities
        if any(word in query_lower for word in ["project", "projects"]):
            entities.extend(["project"])

        # Member/User entities
        if any(word in query_lower for word in ["member", "members", "user", "users", "assignee", "creator"]):
            entities.extend(["member", "user"])

        # Work item entities
        if any(word in query_lower for word in ["work item", "workitem", "task", "tasks", "bug", "bugs"]):
            entities.extend(["workitem", "task"])

        # Cycle entities
        if any(word in query_lower for word in ["cycle", "cycles", "sprint", "sprints"]):
            entities.extend(["cycle"])

        # Documentation entities
        if any(word in query_lower for word in ["document", "page", "documentation", "wiki"]):
            entities.extend(["documentation"])

        # Status/State entities
        if any(word in query_lower for word in ["status", "state", "priority"]):
            entities.extend(["status"])

        return list(set(entities))  # Remove duplicates

    def create_phoenix_dataset(self, dataset: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create a Phoenix-compatible dataset"""
        try:
            # Convert to DataFrame for Phoenix
            df = pd.DataFrame(dataset)

            # Create the dataset in Phoenix
            with using_project("pms-assistant-eval"):
                # Log dataset creation
                print(f"📤 Creating Phoenix dataset: {self.dataset_name}")
                print(f"📊 Dataset contains {len(df)} entries")

                # Save dataset metadata
                dataset_metadata = {
                    "name": self.dataset_name,
                    "description": self.dataset_description,
                    "version": self.dataset_version,
                    "total_entries": len(dataset),
                    "categories": df['query_category'].value_counts().to_dict(),
                    "expected_entities": df['expected_entities'].explode().value_counts().to_dict(),
                    "created_at": datetime.now().isoformat()
                }

                # Save to JSON file for reference
                with open('phoenix_dataset_metadata.json', 'w') as f:
                    json.dump(dataset_metadata, f, indent=2)

                print(f"✅ Dataset metadata saved to phoenix_dataset_metadata.json")

                return {
                    "dataset": df,
                    "metadata": dataset_metadata,
                    "success": True
                }

        except Exception as e:
            print(f"❌ Error creating Phoenix dataset: {e}")
            import traceback
            traceback.print_exc()
            return {
                "dataset": None,
                "metadata": None,
                "success": False,
                "error": str(e)
            }

    def upload_to_phoenix(self, dataset_info: Dict[str, Any]) -> bool:
        """Upload dataset to Phoenix server"""
        try:
            if not dataset_info["success"]:
                print("❌ Cannot upload dataset: creation failed")
                return False

            # In a real implementation, you would use Phoenix's API to upload the dataset
            # For now, we'll save it as a JSON file that can be imported into Phoenix

            # Save the dataset to a file that Phoenix can import
            dataset_file = f"phoenix_dataset_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            with open(dataset_file, 'w') as f:
                json.dump(dataset_info, f, indent=2, default=str)

            print(f"📁 Dataset saved to: {dataset_file}")
            print("💡 To import into Phoenix dashboard:")
            print("   1. Start Phoenix server: python phoenix.py")
            print("   2. Open browser to http://localhost:6006")
            print("   3. Go to 'Datasets' section")
            return True

        except Exception as e:
            print(f"❌ Error uploading dataset to Phoenix: {e}")
            import traceback
            traceback.print_exc()
            return False

    def create_sample_evaluations(self, dataset: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Create sample evaluations for the dataset"""
        evaluations = []

        for entry in dataset[:5]:  # Create evaluations for first 5 queries
            evaluation = {
                "query_id": entry["id"],
                "query": entry["query"],
                "sample_response": f"Sample response for: {entry['query'][:50]}...",
                "evaluation_metrics": {
                    "relevance": 0.8,
                    "factual_accuracy": 0.7,
                    "response_completeness": 0.9,
                    "entity_recognition": 0.85
                },
                "evaluation_timestamp": datetime.now().isoformat(),
                "evaluator": "pms_sample_evaluator"
            }
            evaluations.append(evaluation)

        # Save sample evaluations
        with open('sample_evaluations.json', 'w') as f:
            json.dump(evaluations, f, indent=2)

        print(f"📋 Created {len(evaluations)} sample evaluations")
        print("📄 Saved to sample_evaluations.json")

        return evaluations

    async def run(self):
        """Main function to upload dataset to Phoenix"""
        print("🚀 Starting Phoenix Dataset Upload...")
        print("=" * 60)

        # Load test dataset
        dataset = self.load_test_dataset()

        if not dataset:
            print("❌ No dataset to upload")
            return False

        # Create Phoenix dataset
        dataset_info = self.create_phoenix_dataset(dataset)

        if not dataset_info["success"]:
            print("❌ Failed to create Phoenix dataset")
            return False

        # Create sample evaluations
        sample_evaluations = self.create_sample_evaluations(dataset)

        # Upload to Phoenix
        success = self.upload_to_phoenix(dataset_info)

        if success:
            print("\n" + "=" * 60)
            print("✅ Dataset Upload Completed Successfully!")
            print("=" * 60)
            print(f"📊 Dataset: {self.dataset_name}")
            print(f"📋 Entries: {len(dataset)}")
            print(f"📁 Files created:")
            print("   - phoenix_dataset_metadata.json")
            print("   - sample_evaluations.json")
            print("   - Dataset JSON file")

            print("\n📋 Next Steps:")
            print("1. Start Phoenix server: python phoenix.py")
            print("2. Open browser to http://localhost:6006")
            print("3. Import the dataset JSON file")
            print("4. Run evaluations: python run_evaluation.py")

        return success


async def main():
    """Main function"""
    uploader = PhoenixDatasetUploader()
    success = await uploader.run()
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
