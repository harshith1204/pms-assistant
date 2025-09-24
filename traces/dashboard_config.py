#!/usr/bin/env python3
"""
Phoenix Dashboard Configuration for PMS Assistant
This module sets up comprehensive dashboard configurations and panels for monitoring.
"""

import json
import os
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path

# Phoenix imports
from phoenix import Client
from phoenix.trace import using_project


class PhoenixDashboardManager:
    """Manages Phoenix dashboard configuration and setup"""

    def __init__(self):
        self.client = Client()
        self.dashboard_configs = {}
        self.panel_configs = {}

    def create_pms_dashboard_config(self) -> Dict[str, Any]:
        """Create comprehensive dashboard configuration for PMS Assistant"""

        dashboard_config = {
            "name": "PMS Assistant Evaluation Dashboard",
            "description": "Comprehensive monitoring and evaluation dashboard for the Project Management System Assistant",
            "version": "1.0.0",
            "created_at": datetime.now().isoformat(),
            "panels": [
                {
                    "id": "evaluation_metrics_overview",
                    "name": "Evaluation Metrics Overview",
                    "type": "metric_summary",
                    "description": "Key performance indicators for the PMS Assistant",
                    "position": {"x": 0, "y": 0, "width": 12, "height": 4},
                    "config": {
                        "metrics": ["relevance", "factual_accuracy", "completeness", "toxicity"],
                        "show_trends": True,
                        "time_range": "24h",
                        "refresh_interval": 30
                    }
                },
                {
                    "id": "query_performance_trends",
                    "name": "Query Performance Trends",
                    "type": "time_series",
                    "description": "Performance trends over time",
                    "position": {"x": 0, "y": 4, "width": 12, "height": 4},
                    "config": {
                        "metrics": ["response_time", "success_rate", "query_volume"],
                        "time_range": "7d",
                        "aggregation": "mean",
                        "group_by": ["hour"]
                    }
                },
                {
                    "id": "error_analysis",
                    "name": "Error Analysis",
                    "type": "error_breakdown",
                    "description": "Analysis of errors and failures",
                    "position": {"x": 0, "y": 8, "width": 6, "height": 4},
                    "config": {
                        "group_by": ["error_type", "query_category"],
                        "show_percentages": True,
                        "max_items": 10
                    }
                },
                {
                    "id": "entity_recognition_accuracy",
                    "name": "Entity Recognition Accuracy",
                    "type": "accuracy_heatmap",
                    "description": "Accuracy of entity recognition across different categories",
                    "position": {"x": 6, "y": 8, "width": 6, "height": 4},
                    "config": {
                        "metrics": ["entity_recognition"],
                        "group_by": ["entity_type", "query_category"]
                    }
                },
                {
                    "id": "query_category_distribution",
                    "name": "Query Type Distribution",
                    "type": "category_distribution",
                    "description": "Distribution of queries by category",
                    "position": {"x": 0, "y": 12, "width": 6, "height": 4},
                    "config": {
                        "categories": ["project_queries", "member_queries", "workitem_queries", "cycle_queries", "documentation_queries"],
                        "show_percentages": True
                    }
                },
                {
                    "id": "response_time_histogram",
                    "name": "Response Time Distribution",
                    "type": "histogram",
                    "description": "Distribution of response times",
                    "position": {"x": 6, "y": 12, "width": 6, "height": 4},
                    "config": {
                        "metric": "response_time",
                        "bins": 20,
                        "range": {"min": 0, "max": 10}
                    }
                },
                {
                    "id": "tool_usage_analysis",
                    "name": "Tool Usage Analysis",
                    "type": "bar_chart",
                    "description": "Analysis of tool usage patterns",
                    "position": {"x": 0, "y": 16, "width": 12, "height": 4},
                    "config": {
                        "metrics": ["tool_success_rate", "tool_execution_time"],
                        "group_by": ["tool_name"],
                        "sort_by": "usage_count"
                    }
                },
                {
                    "id": "conversation_flow",
                    "name": "Conversation Flow Analysis",
                    "type": "flow_diagram",
                    "description": "Analysis of conversation patterns and flows",
                    "position": {"x": 0, "y": 20, "width": 12, "height": 4},
                    "config": {
                        "show_message_flow": True,
                        "show_token_usage": True,
                        "max_conversations": 50
                    }
                }
            ],
            "alerts": [
                {
                    "id": "high_error_rate",
                    "name": "High Error Rate Alert",
                    "condition": "error_rate > 0.1",
                    "threshold": 0.1,
                    "severity": "warning",
                    "channels": ["console", "log"]
                },
                {
                    "id": "low_accuracy",
                    "name": "Low Accuracy Alert",
                    "condition": "factual_accuracy < 0.5",
                    "threshold": 0.5,
                    "severity": "critical",
                    "channels": ["console", "log"]
                },
                {
                    "id": "slow_response",
                    "name": "Slow Response Alert",
                    "condition": "response_time > 5.0",
                    "threshold": 5.0,
                    "severity": "warning",
                    "channels": ["console", "log"]
                }
            ],
            "data_sources": [
                {
                    "name": "pms_traces",
                    "type": "traces",
                    "project": "pms-assistant-traces",
                    "filters": {}
                },
                {
                    "name": "pms_evaluations",
                    "type": "evaluations",
                    "project": "pms-assistant-eval",
                    "filters": {}
                }
            ]
        }

        return dashboard_config

    def create_panel_configurations(self) -> Dict[str, Dict[str, Any]]:
        """Create detailed panel configurations"""

        panel_configs = {
            "evaluation_metrics_overview": {
                "title": "Key Performance Metrics",
                "metrics": [
                    {
                        "name": "relevance",
                        "label": "Response Relevance",
                        "format": "percentage",
                        "thresholds": {"good": 0.8, "warning": 0.6}
                    },
                    {
                        "name": "factual_accuracy",
                        "label": "Factual Accuracy",
                        "format": "percentage",
                        "thresholds": {"good": 0.8, "warning": 0.6}
                    },
                    {
                        "name": "completeness",
                        "label": "Response Completeness",
                        "format": "percentage",
                        "thresholds": {"good": 0.7, "warning": 0.5}
                    },
                    {
                        "name": "toxicity",
                        "label": "Response Quality",
                        "format": "percentage",
                        "thresholds": {"good": 0.9, "warning": 0.7}
                    }
                ],
                "layout": "grid",
                "refresh_rate": 30
            },
            "query_performance_trends": {
                "title": "Performance Over Time",
                "chart_type": "line",
                "time_range": "24h",
                "metrics": [
                    {
                        "name": "response_time",
                        "label": "Average Response Time (s)",
                        "color": "#2563eb"
                    },
                    {
                        "name": "success_rate",
                        "label": "Success Rate (%)",
                        "color": "#16a34a"
                    },
                    {
                        "name": "query_volume",
                        "label": "Query Volume",
                        "color": "#dc2626"
                    }
                ],
                "aggregation": "mean"
            },
            "error_analysis": {
                "title": "Error Breakdown",
                "chart_type": "pie",
                "max_items": 10,
                "show_percentages": True,
                "error_categories": [
                    "connection_error",
                    "parse_error",
                    "validation_error",
                    "timeout_error",
                    "not_found_error"
                ]
            },
            "entity_recognition_accuracy": {
                "title": "Entity Recognition Performance",
                "chart_type": "heatmap",
                "entity_types": [
                    "project", "member", "workitem", "cycle", "documentation"
                ],
                "metrics": ["precision", "recall", "f1_score"]
            },
            "query_category_distribution": {
                "title": "Query Categories",
                "chart_type": "doughnut",
                "categories": [
                    "project_queries",
                    "member_queries",
                    "workitem_queries",
                    "cycle_queries",
                    "documentation_queries",
                    "uncategorized"
                ]
            },
            "response_time_histogram": {
                "title": "Response Time Distribution",
                "chart_type": "histogram",
                "bins": 20,
                "range": {"min": 0, "max": 10},
                "color": "#7c3aed"
            },
            "tool_usage_analysis": {
                "title": "Tool Usage Statistics",
                "chart_type": "bar",
                "sort_by": "usage_count",
                "show_values": True,
                "metrics": ["success_rate", "avg_execution_time"]
            },
            "conversation_flow": {
                "title": "Conversation Patterns",
                "show_message_types": True,
                "show_token_counts": True,
                "max_conversations": 100
            }
        }

        return panel_configs

    def generate_phoenix_config_file(self) -> str:
        """Generate Phoenix configuration file"""

        config = {
            "app": {
                "title": "PMS Assistant Evaluation Dashboard",
                "description": "Comprehensive evaluation and monitoring dashboard for the Project Management System Assistant"
            },
            "ui": {
                "default_project": "pms-assistant-eval",
                "enable_public_projects": False,
                "max_projects": 10,
                "theme": "light"
            },
            "tracing": {
                "enabled": True,
                "export": {
                    "console": True,
                    "phoenix": True
                }
            },
            "evaluation": {
                "enabled": True,
                "auto_evaluate": False,
                "metrics": ["relevance", "factual_accuracy", "completeness", "toxicity"]
            },
            "dashboards": [self.create_pms_dashboard_config()],
            "alerts": {
                "enabled": True,
                "channels": {
                    "console": True,
                    "log_file": True
                }
            }
        }

        # Save to file
        config_file = "phoenix_config.json"
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)

        print(f"✅ Generated Phoenix configuration: {config_file}")
        return config_file

    def create_startup_script(self) -> str:
        """Create a startup script for Phoenix with the dashboard"""

        script_content = '''#!/bin/bash
# Phoenix Dashboard Startup Script for PMS Assistant
# This script starts Phoenix with the PMS Assistant dashboard configuration

echo "🚀 Starting Phoenix Dashboard for PMS Assistant..."
echo "=" * 60

# Check if Phoenix is already running
if pgrep -f "phoenix.server.main" > /dev/null; then
    echo "✅ Phoenix is already running"
    echo "🌐 Open your browser to: http://localhost:6006"
    exit 0
fi

# Set environment variables
export PHOENIX_HOST=localhost
export PHOENIX_PORT=6006
export PHOENIX_LOG_LEVEL=INFO

# Start Phoenix server
echo "🔧 Starting Phoenix server..."
python -m phoenix.server.main serve --config phoenix_config.json &

# Wait for server to start
sleep 3

# Check if server started successfully
if curl -s http://localhost:6006/health > /dev/null; then
    echo "✅ Phoenix server started successfully!"
    echo "🌐 Dashboard available at: http://localhost:6006"
    echo ""
    echo "📋 Available Dashboards:"
    echo "   • PMS Assistant Evaluation Dashboard"
    echo "   • Real-time Tracing"
    echo "   • Performance Analytics"
    echo ""
    echo "💡 Next Steps:"
    echo "   1. Open your browser to http://localhost:6006"
    echo "   2. Import your evaluation dataset"
    echo "   3. Start running evaluations"
    echo "   4. Monitor performance in real-time"
else
    echo "❌ Failed to start Phoenix server"
    echo "🔍 Check the logs for more information"
fi
'''

        script_file = "start_phoenix_dashboard.sh"
        with open(script_file, 'w') as f:
            f.write(script_content)

        # Make executable
        os.chmod(script_file, 0o755)

        print(f"✅ Generated startup script: {script_file}")
        return script_file

    def create_monitoring_guide(self) -> str:
        """Create a monitoring guide for users"""

        guide_content = '''# PMS Assistant Phoenix Dashboard Guide

## Overview
This guide explains how to use the Phoenix dashboard to monitor and evaluate your PMS Assistant.

## Getting Started

### 1. Start the Dashboard
```bash
# Run the startup script
./start_phoenix_dashboard.sh

# Or start Phoenix manually
python phoenix.py
```

### 2. Access the Dashboard
Open your browser and go to: http://localhost:6006

## Dashboard Panels

### Evaluation Metrics Overview
- **Purpose**: Shows key performance indicators
- **Metrics**: Relevance, Factual Accuracy, Completeness, Toxicity
- **Use**: Monitor overall system performance

### Query Performance Trends
- **Purpose**: Track performance over time
- **Metrics**: Response time, success rate, query volume
- **Use**: Identify performance patterns and trends

### Error Analysis
- **Purpose**: Analyze errors and failures
- **Metrics**: Error types, categories, frequencies
- **Use**: Identify and fix common issues

### Entity Recognition Accuracy
- **Purpose**: Monitor entity recognition performance
- **Metrics**: Precision, recall, F1-score by entity type
- **Use**: Improve entity extraction accuracy

### Query Category Distribution
- **Purpose**: Understand query patterns
- **Metrics**: Distribution across categories
- **Use**: Optimize for common query types

### Response Time Distribution
- **Purpose**: Analyze response time patterns
- **Metrics**: Histogram of response times
- **Use**: Identify performance bottlenecks

### Tool Usage Analysis
- **Purpose**: Monitor tool performance
- **Metrics**: Success rates, execution times
- **Use**: Optimize tool selection and execution

### Conversation Flow
- **Purpose**: Analyze conversation patterns
- **Metrics**: Message flows, token usage
- **Use**: Improve conversation handling

## Alerts and Monitoring

### Configured Alerts
1. **High Error Rate**: Triggers when error rate > 10%
2. **Low Accuracy**: Triggers when accuracy < 50%
3. **Slow Response**: Triggers when response time > 5s

### Alert Channels
- Console output
- Log file
- (Optional: Email, Slack)

## Data Sources

### Traces
- Source: PMS Assistant agent interactions
- Contains: Query, response, timing, metadata
- Update: Real-time

### Evaluations
- Source: Evaluation pipeline results
- Contains: Query, response, metrics, scores
- Update: Batch or manual

## Best Practices

### Regular Monitoring
1. Check dashboard daily for trends
2. Review error analysis weekly
3. Monitor response times during peak usage
4. Track accuracy metrics over time

### Performance Optimization
1. Use query category distribution to prioritize improvements
2. Monitor tool usage to identify bottlenecks
3. Use response time histograms to identify outliers
4. Track entity recognition accuracy for specific types

### Troubleshooting
1. High error rate: Check connection issues, data quality
2. Low accuracy: Review evaluation metrics, improve prompts
3. Slow responses: Optimize tool execution, database queries
4. Entity issues: Improve entity recognition patterns

## Advanced Features

### Custom Panels
You can create custom panels by:
1. Going to the dashboard editor
2. Adding new panel types
3. Configuring custom queries and filters

### Data Export
Export data for external analysis:
1. Go to the data export section
2. Select time range and metrics
3. Download CSV or JSON files

### Integration
Integrate with external monitoring:
1. Configure webhook endpoints
2. Set up external alerting
3. Connect to existing monitoring systems
'''

        guide_file = "PMS_Phoenix_Dashboard_Guide.md"
        with open(guide_file, 'w') as f:
            f.write(guide_content)

        print(f"✅ Generated monitoring guide: {guide_file}")
        return guide_file

    def setup_complete_dashboard(self):
        """Complete dashboard setup"""
        print("🚀 Setting up Phoenix Dashboard for PMS Assistant...")
        print("=" * 60)

        try:
            # Generate configuration files
            config_file = self.generate_phoenix_config_file()
            startup_script = self.create_startup_script()
            guide_file = self.create_monitoring_guide()

            print("\n" + "=" * 60)
            print("✅ Dashboard Setup Completed!")
            print("=" * 60)
            print("📁 Files created:")
            print(f"   • {config_file}")
            print(f"   • {startup_script}")
            print(f"   • {guide_file}")
            print()
            print("📋 Next Steps:")
            print("1. Start Phoenix: ./start_phoenix_dashboard.sh")
            print("2. Open browser: http://localhost:6006")
            print("3. Import evaluation dataset")
            print("4. Run evaluations to populate data")
            print("5. Monitor performance in real-time")

            return True

        except Exception as e:
            print(f"❌ Error setting up dashboard: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main function to set up the dashboard"""
    dashboard_manager = PhoenixDashboardManager()
    success = dashboard_manager.setup_complete_dashboard()
    return success


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
