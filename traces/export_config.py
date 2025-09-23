#!/usr/bin/env python3
"""
Export Configuration for Phoenix Traces and Evaluations
This module handles comprehensive export configuration for all tracing and evaluation data.
"""

import os
import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

# Phoenix imports
from phoenix.trace.exporter import HttpExporter, SimpleSpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter as OTELConsoleExporter

# File exporter not available - no separate package exists
FileSpanExporter = None  # Set to None for graceful fallback

# Local imports
from config import EXPORT_CONFIGS, get_export_config, get_current_environment


class PhoenixExportManager:
    """Manages comprehensive export configuration for Phoenix"""

    def __init__(self):
        self.environment = get_current_environment()
        self.export_config = get_export_config()
        self.exporters = {}
        self.processors = {}

    def setup_console_export(self):
        """Set up console export for development"""
        try:
            console_exporter = OTELConsoleExporter()
            console_processor = BatchSpanProcessor(console_exporter)
            self.exporters['console'] = console_exporter
            self.processors['console'] = console_processor
            print("✅ Console export configured")
        except Exception as e:
            print(f"⚠️  Failed to setup console export: {e}")

    def setup_file_export(self):
        """Set up file export for logs"""
        try:
            if not FileSpanExporter:
                print("⚠️  File exporter not available, skipping file export setup")
                return

            export_path = self.export_config.get("export_path", "./logs/phoenix_traces.jsonl")

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(export_path), exist_ok=True)

            file_exporter = FileSpanExporter(export_path)
            file_processor = BatchSpanProcessor(file_exporter)
            self.exporters['file'] = file_exporter
            self.processors['file'] = file_processor
            print(f"✅ File export configured: {export_path}")
        except Exception as e:
            print(f"⚠️  Failed to setup file export: {e}")

    def setup_phoenix_export(self):
        """Set up Phoenix HTTP export"""
        try:
            phoenix_endpoint = self.export_config.get("phoenix_endpoint", "http://localhost:6006/v1/traces")
            phoenix_exporter = HttpExporter(endpoint=phoenix_endpoint)
            phoenix_processor = BatchSpanProcessor(phoenix_exporter)
            self.exporters['phoenix'] = phoenix_exporter
            self.processors['phoenix'] = phoenix_processor
            print(f"✅ Phoenix export configured: {phoenix_endpoint}")
        except Exception as e:
            print(f"⚠️  Failed to setup Phoenix export: {e}")

    def setup_json_export(self):
        """Set up structured JSON export for evaluations"""
        try:
            json_export_path = self.export_config.get("json_export_path", "./logs/evaluations.json")

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(json_export_path), exist_ok=True)

            self.exporters['json'] = json_export_path
            print(f"✅ JSON export configured: {json_export_path}")
        except Exception as e:
            print(f"⚠️  Failed to setup JSON export: {e}")

    def setup_all_exports(self):
        """Set up all configured exports"""
        print(f"🔧 Setting up exports for environment: {self.environment}")
        print("=" * 50)

        # Setup console export (always enabled in development)
        if self.export_config.get("enable_console_export", True):
            self.setup_console_export()

        # Setup file export
        if self.export_config.get("enable_file_export", True):
            self.setup_file_export()

        # Setup Phoenix export
        if self.export_config.get("enable_phoenix_export", False):
            self.setup_phoenix_export()

        # Setup JSON export for evaluations
        self.setup_json_export()

        print(f"✅ Export configuration completed for {self.environment}")
        return list(self.exporters.keys())

    def get_active_processors(self) -> List:
        """Get list of active processors"""
        return [processor for name, processor in self.processors.items() if processor]

    def export_evaluation_data(self, evaluation_results: Dict[str, Any]) -> bool:
        """Export evaluation results to configured formats"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

            # Export to JSON (always)
            json_path = self.exporters.get('json', './logs/evaluations.json')
            self._export_to_json(evaluation_results, json_path, timestamp)

            # Export to CSV if configured
            if self.export_config.get("enable_csv_export", False):
                csv_path = self.export_config.get("csv_export_path", "./logs/evaluations.csv")
                self._export_to_csv(evaluation_results, csv_path, timestamp)

            # Export summary metrics
            self._export_summary_metrics(evaluation_results, timestamp)

            return True

        except Exception as e:
            print(f"❌ Error exporting evaluation data: {e}")
            return False

    def _export_to_json(self, data: Dict[str, Any], base_path: str, timestamp: str):
        """Export data to JSON format"""
        try:
            # Create timestamped filename
            base_name = os.path.basename(base_path)
            name_without_ext = os.path.splitext(base_name)[0]
            json_file = f"{name_without_ext}_{timestamp}.json"

            with open(json_file, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            # Also update the main file
            with open(base_path, 'w') as f:
                json.dump(data, f, indent=2, default=str)

            print(f"📄 Exported evaluation data to JSON: {json_file}")

        except Exception as e:
            print(f"Error exporting to JSON: {e}")

    def _export_to_csv(self, data: Dict[str, Any], base_path: str, timestamp: str):
        """Export evaluation results to CSV format"""
        try:
            results = data.get("results", [])

            if not results:
                print("⚠️  No evaluation results to export to CSV")
                return

            # Flatten the results for CSV export
            flattened_data = []
            for result in results:
                flat_result = {
                    "query_id": result.get("query_id", ""),
                    "query": result.get("query", ""),
                    "response": result.get("response", "")[:500],  # Truncate for CSV
                    "success": result.get("success", False),
                    "evaluation_time": result.get("evaluation_time", ""),
                }

                # Add metrics
                metrics = result.get("metrics", {})
                for metric_name, metric_value in metrics.items():
                    flat_result[f"metric_{metric_name}"] = metric_value

                flattened_data.append(flat_result)

            df = pd.DataFrame(flattened_data)

            # Create timestamped filename
            base_name = os.path.basename(base_path)
            name_without_ext = os.path.splitext(base_name)[0]
            csv_file = f"{name_without_ext}_{timestamp}.csv"

            df.to_csv(csv_file, index=False)

            # Also update the main file
            df.to_csv(base_path, index=False)

            print(f"📊 Exported evaluation data to CSV: {csv_file}")

        except Exception as e:
            print(f"Error exporting to CSV: {e}")

    def _export_summary_metrics(self, data: Dict[str, Any], timestamp: str):
        """Export summary metrics to a dedicated file"""
        try:
            summary = data.get("summary", {})
            export_data = {
                "timestamp": timestamp,
                "environment": self.environment,
                "evaluation_id": data.get("evaluation_id", ""),
                "total_queries": data.get("total_queries", 0),
                "successful_evaluations": data.get("successful_evaluations", 0),
                "failed_evaluations": data.get("failed_evaluations", 0),
                "success_rate": data.get("summary", {}).get("success_rate", 0),
                "average_metrics": summary.get("average_metrics", {}),
                "query_categories": summary.get("query_categories", {}),
                "performance_bands": summary.get("performance_bands", {}),
                "threshold_analysis": summary.get("threshold_analysis", {})
            }

            summary_file = f"./logs/summary_metrics_{timestamp}.json"
            with open(summary_file, 'w') as f:
                json.dump(export_data, f, indent=2, default=str)

            print(f"📈 Exported summary metrics: {summary_file}")

        except Exception as e:
            print(f"Error exporting summary metrics: {e}")

    def create_export_report(self, evaluation_results: Dict[str, Any]) -> str:
        """Create a comprehensive export report"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report = {
                "export_timestamp": datetime.now().isoformat(),
                "environment": self.environment,
                "export_config": self.export_config,
                "evaluation_summary": evaluation_results.get("summary", {}),
                "files_exported": [],
                "export_status": "success"
            }

            # Add file information
            json_path = self.exporters.get('json', './logs/evaluations.json')
            report["files_exported"].append({
                "type": "json",
                "path": json_path,
                "size": os.path.getsize(json_path) if os.path.exists(json_path) else 0
            })

            # Add CSV if configured
            if self.export_config.get("enable_csv_export", False):
                csv_path = self.export_config.get("csv_export_path", "./logs/evaluations.csv")
                report["files_exported"].append({
                    "type": "csv",
                    "path": csv_path,
                    "size": os.path.getsize(csv_path) if os.path.exists(csv_path) else 0
                })

            # Save report
            report_file = f"./logs/export_report_{timestamp}.json"
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2, default=str)

            print(f"📋 Export report created: {report_file}")
            return report_file

        except Exception as e:
            print(f"Error creating export report: {e}")
            return None


class BatchExportManager:
    """Manages batch export of historical data"""

    def __init__(self, export_manager: PhoenixExportManager):
        self.export_manager = export_manager
        self.batch_size = 100

    async def export_historical_traces(self, start_date: datetime, end_date: datetime):
        """Export historical traces for a date range"""
        try:
            print(f"📤 Exporting historical traces from {start_date} to {end_date}")

            # In a real implementation, this would query Phoenix for historical traces
            # For now, we'll simulate this process

            export_data = {
                "export_type": "historical_traces",
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "timestamp": datetime.now().isoformat(),
                "status": "completed"
            }

            # Save to historical export file
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_file = f"./logs/historical_traces_{timestamp}.json"
            with open(export_file, 'w') as f:
                json.dump(export_data, f, indent=2)

            print(f"📄 Historical traces exported: {export_file}")
            return export_file

        except Exception as e:
            print(f"Error exporting historical traces: {e}")
            return None

    async def export_evaluation_history(self, days: int = 30):
        """Export evaluation history for the past N days"""
        try:
            print(f"📤 Exporting evaluation history for past {days} days")

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Collect evaluation files
            evaluation_files = []
            logs_dir = Path("./logs")
            for json_file in logs_dir.glob("evaluations*.json"):
                if json_file.stat().st_mtime >= start_date.timestamp():
                    evaluation_files.append(json_file)

            # Aggregate data
            aggregated_data = {
                "export_type": "evaluation_history",
                "period_days": days,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "files_processed": len(evaluation_files),
                "summary": {
                    "total_evaluations": 0,
                    "total_success": 0,
                    "total_failed": 0,
                    "avg_success_rate": 0.0
                },
                "timestamp": datetime.now().isoformat()
            }

            # Process files
            success_rates = []
            for file_path in evaluation_files:
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)

                    results = data.get("results", [])
                    successful = sum(1 for r in results if r.get("success", False))

                    if results:
                        success_rate = successful / len(results)
                        success_rates.append(success_rate)
                        aggregated_data["summary"]["total_evaluations"] += len(results)
                        aggregated_data["summary"]["total_success"] += successful
                        aggregated_data["summary"]["total_failed"] += len(results) - successful

                except Exception as e:
                    print(f"Error processing {file_path}: {e}")

            if success_rates:
                aggregated_data["summary"]["avg_success_rate"] = sum(success_rates) / len(success_rates)

            # Save aggregated data
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            export_file = f"./logs/evaluation_history_{days}days_{timestamp}.json"
            with open(export_file, 'w') as f:
                json.dump(aggregated_data, f, indent=2)

            print(f"📄 Evaluation history exported: {export_file}")
            return export_file

        except Exception as e:
            print(f"Error exporting evaluation history: {e}")
            return None


class ExportConfigurationManager:
    """Main export configuration manager"""

    def __init__(self):
        self.phoenix_exporter = PhoenixExportManager()
        self.batch_exporter = BatchExportManager(self.phoenix_exporter)
        self.configured = False

    async def initialize(self):
        """Initialize export configuration"""
        try:
            print("🚀 Initializing Export Configuration...")
            print("=" * 50)

            # Setup all exports
            active_exports = self.phoenix_exporter.setup_all_exports()

            print(f"✅ Active exports: {', '.join(active_exports)}")
            self.configured = True

            print("🎯 Export Configuration Ready!")
            return True

        except Exception as e:
            print(f"❌ Error initializing export configuration: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def export_evaluation(self, evaluation_results: Dict[str, Any]) -> bool:
        """Export evaluation results using configured exporters"""
        try:
            if not self.configured:
                await self.initialize()

            # Export using Phoenix export manager
            success = self.phoenix_exporter.export_evaluation_data(evaluation_results)

            # Create export report
            self.phoenix_exporter.create_export_report(evaluation_results)

            return success

        except Exception as e:
            print(f"Error exporting evaluation: {e}")
            return False

    async def run_batch_export(self):
        """Run batch export of historical data"""
        try:
            print("📦 Running Batch Export...")

            # Export historical traces (last 7 days)
            traces_export = await self.batch_exporter.export_historical_traces(
                datetime.now() - timedelta(days=7),
                datetime.now()
            )

            # Export evaluation history (last 30 days)
            eval_export = await self.batch_exporter.export_evaluation_history(30)

            print("✅ Batch export completed")
            return [traces_export, eval_export]

        except Exception as e:
            print(f"Error in batch export: {e}")
            return []

    def get_export_status(self) -> Dict[str, Any]:
        """Get current export status"""
        return {
            "environment": self.phoenix_exporter.environment,
            "configured": self.configured,
            "active_exports": list(self.phoenix_exporter.exporters.keys()),
            "export_config": self.phoenix_exporter.export_config,
            "timestamp": datetime.now().isoformat()
        }


# Global export manager instance
export_manager = ExportConfigurationManager()


async def main():
    """Main function to test export configuration"""
    try:
        await export_manager.initialize()

        # Create sample evaluation data
        sample_data = {
            "evaluation_id": "test_export_001",
            "total_queries": 5,
            "successful_evaluations": 4,
            "failed_evaluations": 1,
            "summary": {
                "success_rate": 0.8,
                "average_metrics": {
                    "avg_relevance": 0.75,
                    "avg_factual_accuracy": 0.82,
                    "avg_completeness": 0.68
                }
            },
            "results": [
                {
                    "query_id": "test_001",
                    "query": "Test query",
                    "response": "Test response",
                    "success": True,
                    "metrics": {
                        "relevance": 0.8,
                        "factual_accuracy": 0.9,
                        "completeness": 0.7
                    }
                }
            ]
        }

        # Export the sample data
        success = await export_manager.export_evaluation(sample_data)

        if success:
            print("✅ Export test completed successfully!")
        else:
            print("❌ Export test failed!")

        # Get export status
        status = export_manager.get_export_status()
        print(f"📊 Export Status: {json.dumps(status, indent=2)}")

    except Exception as e:
        print(f"Error in export test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
