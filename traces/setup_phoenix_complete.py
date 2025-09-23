#!/usr/bin/env python3
"""
Complete Phoenix Setup for PMS Assistant
This script sets up the complete Phoenix evaluation and tracing system.
"""

import asyncio
import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path for local imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from phoenix import Client
from upload_dataset import PhoenixDatasetUploader
from comprehensive_eval import ComprehensiveEvaluationPipeline
from export_config import ExportConfigurationManager
from dashboard_config import PhoenixDashboardManager


class CompletePhoenixSetup:
    """Complete Phoenix setup for PMS Assistant"""

    def __init__(self):
        self.phoenix_client = None
        self.dataset_uploader = None
        self.evaluation_pipeline = None
        self.export_manager = None
        self.dashboard_manager = None
        self.setup_complete = False

    async def initialize(self):
        """Initialize the complete Phoenix setup"""
        print("🚀 Initializing Complete Phoenix Setup for PMS Assistant")
        print("=" * 70)

        try:
            # Initialize Phoenix client
            self.phoenix_client = Client()
            print("✅ Phoenix client initialized")

            # Initialize components
            self.dataset_uploader = PhoenixDatasetUploader(self.phoenix_client)
            self.evaluation_pipeline = ComprehensiveEvaluationPipeline()
            self.export_manager = ExportConfigurationManager()
            self.dashboard_manager = PhoenixDashboardManager()

            print("✅ All components initialized")
            return True

        except Exception as e:
            print(f"❌ Error initializing setup: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def setup_dataset(self):
        """Set up the evaluation dataset"""
        print("\n📊 Setting up evaluation dataset...")
        print("=" * 50)

        try:
            await self.dataset_uploader.run()
            print("✅ Dataset setup completed")
            return True

        except Exception as e:
            print(f"❌ Error setting up dataset: {e}")
            return False

    async def setup_evaluation_pipeline(self):
        """Set up the comprehensive evaluation pipeline"""
        print("\n🔬 Setting up evaluation pipeline...")
        print("=" * 50)

        try:
            await self.evaluation_pipeline.initialize()
            print("✅ Evaluation pipeline setup completed")
            return True

        except Exception as e:
            print(f"❌ Error setting up evaluation pipeline: {e}")
            return False

    async def setup_export_configuration(self):
        """Set up export configuration"""
        print("\n📤 Setting up export configuration...")
        print("=" * 50)

        try:
            await self.export_manager.initialize()
            print("✅ Export configuration setup completed")
            return True

        except Exception as e:
            print(f"❌ Error setting up export configuration: {e}")
            return False

    async def setup_dashboard(self):
        """Set up Phoenix dashboard"""
        print("\n📋 Setting up Phoenix dashboard...")
        print("=" * 50)

        try:
            self.dashboard_manager.setup_complete_dashboard()
            print("✅ Dashboard setup completed")
            return True

        except Exception as e:
            print(f"❌ Error setting up dashboard: {e}")
            return False

    async def run_sample_evaluation(self):
        """Run a sample evaluation to test the complete system"""
        print("\n🧪 Running sample evaluation...")
        print("=" * 50)

        try:
            # Run evaluation on a small sample
            results = await self.evaluation_pipeline.run(sample_size=3)

            if results:
                # Export the results
                await self.export_manager.export_evaluation(results)

                print("✅ Sample evaluation completed successfully")
                print(f"📊 Success rate: {results['summary']['success_rate']:.1%}")
                return True
            else:
                print("❌ Sample evaluation failed")
                return False

        except Exception as e:
            print(f"❌ Error running sample evaluation: {e}")
            return False

    async def create_setup_summary(self):
        """Create a comprehensive setup summary"""
        print("\n📋 Creating setup summary...")
        print("=" * 50)

        try:
            summary = {
                "setup_timestamp": datetime.now().isoformat(),
                "setup_status": "completed",
                "components_configured": [
                    "Phoenix Client",
                    "Dataset Uploader",
                    "Evaluation Pipeline",
                    "Export Configuration",
                    "Dashboard Configuration"
                ],
                "files_created": [],
                "next_steps": [
                    "Start Phoenix server: python phoenix.py",
                    "Open browser to http://localhost:6006",
                    "Import evaluation dataset",
                    "Run full evaluation: python comprehensive_eval.py",
                    "Monitor performance in dashboard"
                ],
                "sample_evaluation_run": True
            }

            # Collect created files
            logs_dir = Path("./logs")
            traces_dir = Path("./traces")

            for json_file in logs_dir.glob("*.json"):
                summary["files_created"].append({
                    "type": "log",
                    "path": str(json_file),
                    "size": json_file.stat().st_size
                })

            for py_file in traces_dir.glob("*.py"):
                summary["files_created"].append({
                    "type": "script",
                    "path": str(py_file),
                    "size": py_file.stat().st_size
                })

            # Save summary
            summary_file = "./logs/phoenix_setup_summary.json"
            with open(summary_file, 'w') as f:
                json.dump(summary, f, indent=2)

            print(f"✅ Setup summary created: {summary_file}")
            return summary_file

        except Exception as e:
            print(f"Error creating setup summary: {e}")
            return None

    async def run_complete_setup(self):
        """Run the complete Phoenix setup process"""
        print("🎯 Starting Complete Phoenix Setup Process")
        print("=" * 70)

        steps = [
            ("Initialize Components", self.initialize),
            ("Setup Dataset", self.setup_dataset),
            ("Setup Evaluation Pipeline", self.setup_evaluation_pipeline),
            ("Setup Export Configuration", self.setup_export_configuration),
            ("Setup Dashboard", self.setup_dashboard),
            ("Run Sample Evaluation", self.run_sample_evaluation),
            ("Create Setup Summary", self.create_setup_summary)
        ]

        results = {}

        for step_name, step_func in steps:
            print(f"\n🔄 Step: {step_name}")
            try:
                result = await step_func()
                results[step_name] = "✅ Success" if result else "❌ Failed"
                print(f"Result: {results[step_name]}")

                if not result:
                    print(f"⚠️  Setup failed at step: {step_name}")
                    break

            except Exception as e:
                results[step_name] = f"❌ Error: {str(e)}"
                print(f"Error in {step_name}: {e}")
                break

        # Print final results
        print("\n" + "=" * 70)
        print("📋 COMPLETE SETUP RESULTS")
        print("=" * 70)

        all_success = all("✅ Success" in result for result in results.values())

        for step_name, result in results.items():
            print(f"{step_name}: {result}")

        print("\n" + "=" * 70)
        if all_success:
            print("🎉 COMPLETE PHOENIX SETUP SUCCESSFUL!")
            print("=" * 70)
            print("🚀 Your PMS Assistant now has:")
            print("   ✅ Real-time tracing with Phoenix")
            print("   ✅ Comprehensive evaluation pipeline")
            print("   ✅ Multiple export configurations")
            print("   ✅ Rich dashboard with monitoring panels")
            print("   ✅ Sample data and evaluations")
            print()
            print("📋 Next Steps:")
            print("1. Start Phoenix server: python phoenix.py")
            print("2. Open browser: http://localhost:6006")
            print("3. Import your dataset")
            print("4. Run evaluations: python comprehensive_eval.py")
            print("5. Monitor in real-time dashboard")
        else:
            print("⚠️  SETUP COMPLETED WITH SOME ISSUES")
            print("🔍 Check the results above and fix any failed steps")

        print("=" * 70)
        return all_success

    def print_setup_instructions(self):
        """Print comprehensive setup instructions"""
        print("\n📚 COMPREHENSIVE SETUP INSTRUCTIONS")
        print("=" * 70)

        instructions = """
PMS ASSISTANT PHOENIX SETUP - COMPLETE GUIDE
=============================================

OVERVIEW
--------
This setup provides comprehensive tracing, evaluation, and monitoring
capabilities for your PMS Assistant using Phoenix.

COMPONENTS INSTALLED
-------------------
✅ Phoenix Tracing Integration
✅ Comprehensive Evaluation Pipeline
✅ Multiple Export Configurations
✅ Rich Monitoring Dashboard
✅ Dataset Management System

QUICK START
-----------
1. Start Phoenix Server:
   python phoenix.py

2. Open Dashboard:
   http://localhost:6006

3. Import Dataset:
   python traces/upload_dataset.py

4. Run Evaluations:
   python traces/comprehensive_eval.py

5. Monitor Performance:
   View real-time metrics in Phoenix dashboard

AVAILABLE SCRIPTS
-----------------
• phoenix.py - Start/stop Phoenix server
• upload_dataset.py - Upload evaluation dataset
• comprehensive_eval.py - Run full evaluation pipeline
• run_evaluation.py - Run basic evaluations
• simple_eval.py - Run simple evaluations
• setup_phoenix_complete.py - Complete setup (this script)
• dashboard_config.py - Configure Phoenix dashboard
• export_config.py - Configure data exports
• traced_agent.py - Agent with Phoenix tracing

DASHBOARD PANELS
----------------
• Evaluation Metrics Overview
• Query Performance Trends
• Error Analysis
• Entity Recognition Accuracy
• Query Type Distribution
• Response Time Histogram
• Tool Usage Analysis
• Conversation Flow Analysis

EVALUATION METRICS
------------------
• Response Relevance (0-1)
• Factual Accuracy (0-1)
• Response Completeness (0-1)
• Toxicity Score (0-1)
• PMS-Specific Metrics

EXPORT FORMATS
--------------
• JSON - Structured evaluation data
• CSV - Spreadsheet-compatible format
• Console - Development debugging
• Phoenix - Real-time dashboard
• Batch - Historical data exports

CONFIGURATION FILES
-------------------
• traces/config.py - Main configuration
• phoenix_config.json - Phoenix server config
• phoenix_dataset_metadata.json - Dataset info
• evaluation_report.json - Latest evaluation results

MONITORING & ALERTS
-------------------
• High Error Rate Alert (>10%)
• Low Accuracy Alert (<50%)
• Slow Response Alert (>5s)
• Performance Trend Monitoring
• Query Category Analysis

BEST PRACTICES
--------------
1. Run evaluations regularly to track performance
2. Monitor error rates and response times
3. Use query category analysis to optimize
4. Export data regularly for backup
5. Set up alerts for critical thresholds

TROUBLESHOOTING
---------------
• Check logs/ directory for error details
• Verify Phoenix server is running on port 6006
• Ensure MongoDB connection is working
• Check evaluation dataset format
• Review export configuration settings

ADVANCED FEATURES
-----------------
• Custom evaluation metrics
• Batch historical data export
• Real-time performance monitoring
• Custom dashboard panels
• Integration with external systems

SUPPORT
-------
For issues or questions:
1. Check the logs directory
2. Review configuration files
3. Run diagnostic scripts
4. Check Phoenix dashboard for errors
"""

        print(instructions)


async def main():
    """Main function to run complete setup"""
    setup = CompletePhoenixSetup()

    # Run complete setup
    success = await setup.run_complete_setup()

    # Print instructions
    setup.print_setup_instructions()

    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
