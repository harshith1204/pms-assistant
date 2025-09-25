"""
Phoenix configuration for PMS Assistant evaluation
This module contains all Phoenix-specific configurations and settings.
"""

import os
from typing import Dict, Any, List, Optional
from pathlib import Path

# Phoenix server configuration
PHOENIX_CONFIG = {
    "host": "localhost",
    "port": 6006,
    "enable_prometheus": False,
    "enable_websockets": True,
    "cors_origins": ["http://localhost:5173", "http://127.0.0.1:5173"],
    "log_level": "INFO"
}

# Evaluation dataset configuration
EVALUATION_DATASET_CONFIG = {
    "name": "pms-assistant-eval-dataset",
    "description": "Evaluation dataset for Project Management System Assistant",
    "version": "1.0.0",
    "schema": {
        "query": "string",
        "response": "string",
        "expected_entities": "list[string]",
        "response_metadata": "dict",
        "evaluation_metrics": "dict"
    }
}

# Custom evaluation metrics for PMS
PMS_EVALUATION_METRICS = [
    {
        "name": "response_relevance",
        "description": "Measures how relevant the response is to the query",
        "range": (0.0, 1.0),
        "higher_is_better": True
    },
    {
        "name": "factual_accuracy",
        "description": "Measures factual accuracy of the response against database",
        "range": (0.0, 1.0),
        "higher_is_better": True
    },
    {
        "name": "response_completeness",
        "description": "Measures how complete and comprehensive the response is",
        "range": (0.0, 1.0),
        "higher_is_better": True
    },
    {
        "name": "entity_recognition",
        "description": "Measures accuracy in recognizing and using correct entities",
        "range": (0.0, 1.0),
        "higher_is_better": True
    },
    {
        "name": "query_understanding",
        "description": "Measures how well the system understood the user's intent",
        "range": (0.0, 1.0),
        "higher_is_better": True
    }
]

# Phoenix dashboard configuration
DASHBOARD_CONFIG = {
    "title": "PMS Assistant Evaluation Dashboard",
    "panels": [
        {
            "name": "Evaluation Metrics Overview",
            "type": "metric_summary",
            "metrics": ["response_relevance", "factual_accuracy", "response_completeness"]
        },
        {
            "name": "Query Performance Trends",
            "type": "time_series",
            "metrics": ["query_response_time", "success_rate"]
        },
        {
            "name": "Error Analysis",
            "type": "error_breakdown",
            "group_by": ["error_type", "query_category"]
        },
        {
            "name": "Entity Recognition Accuracy",
            "type": "accuracy_heatmap",
            "metrics": ["entity_recognition"]
        },
        {
            "name": "Query Type Distribution",
            "type": "category_distribution",
            "categories": ["project_queries", "member_queries", "workitem_queries", "cycle_queries"]
        }
    ]
}

# Tracing configuration
TRACING_CONFIG = {
    "enable_tracing": True,
    "trace_all_tools": True,
    "trace_llm_calls": True,
    "trace_database_operations": True,
    "sample_rate": 1.0,  # Sample 100% of requests for evaluation
    "max_span_attributes": 100,
    "max_event_attributes": 50,
    "max_link_attributes": 50
}

# Export configuration for different environments
EXPORT_CONFIGS = {
    "development": {
        "enable_console_export": True,
        "enable_file_export": True,
        "export_path": "./logs/phoenix_traces.jsonl",
        "enable_phoenix_export": False
    },
    "production": {
        "enable_console_export": False,
        "enable_file_export": True,
        "export_path": "./logs/phoenix_traces.jsonl",
        "enable_phoenix_export": True,
        "phoenix_endpoint": "http://localhost:6006/v1/traces"
    },
    "evaluation": {
        "enable_console_export": True,
        "enable_file_export": True,
        "export_path": "./logs/evaluation_traces.jsonl",
        "enable_phoenix_export": True,
        "phoenix_endpoint": "http://localhost:6006/v1/traces"
    }
}

# Query categorization for analysis
QUERY_CATEGORIES = {
    "project_queries": [
        "project", "projects", "project status", "project details",
        "start date", "end date", "project lead", "project creator"
    ],
    "member_queries": [
        "member", "members", "team", "assignee", "role", "email",
        "project member", "user", "creator"
    ],
    "workitem_queries": [
        "work item", "task", "workitem", "bug", "priority", "state",
        "assigned to", "created by", "status", "work items"
    ],
    "cycle_queries": [
        "cycle", "cycles", "sprint", "active cycle", "cycle status",
        "start date", "end date", "cycle details"
    ],
    "documentation_queries": [
        "page", "pages", "documentation", "document", "wiki",
        "public", "private", "visibility"
    ]
}

def get_query_category(query: str) -> str:
    """Categorize a query based on its content"""
    query_lower = query.lower()

    for category, keywords in QUERY_CATEGORIES.items():
        if any(keyword in query_lower for keyword in keywords):
            return category

    return "uncategorized"

def get_current_environment() -> str:
    """Determine the current environment"""
    env = os.getenv("ENVIRONMENT", "development").lower()

    if env in EXPORT_CONFIGS:
        return env

    return "development"

def get_export_config() -> Dict[str, Any]:
    """Get export configuration for current environment"""
    env = get_current_environment()
    return EXPORT_CONFIGS.get(env, EXPORT_CONFIGS["development"])

# Database connection settings for Phoenix
PHOENIX_DB_CONFIG = {
    "database_url": "sqlite:///phoenix.db",  # Use SQLite for simplicity
    "echo": False,  # Set to True for SQL debugging
    "pool_pre_ping": True
}

# Evaluation thresholds
EVALUATION_THRESHOLDS = {
    "response_relevance": 0.7,
    "factual_accuracy": 0.8,
    "response_completeness": 0.6,
    "entity_recognition": 0.7,
    "query_understanding": 0.75,
    "overall_score": 0.7
}

# Alert configuration
ALERT_CONFIG = {
    "enable_alerts": True,
    "alert_thresholds": {
        "error_rate": 0.1,  # Alert if >10% of queries fail
        "low_accuracy": 0.5,  # Alert if accuracy drops below 50%
        "response_time": 5.0  # Alert if response time >5 seconds
    },
    "alert_channels": ["console", "log_file"]  # Add "email", "slack" for production
}

# Phoenix server startup script
PHOENIX_SERVER_CONFIG = {
    "app": {
        "title": "PMS Assistant Evaluation Dashboard",
        "description": "Comprehensive evaluation and monitoring dashboard for the Project Management System Assistant"
    },
    "ui": {
        "default_project": "pms-assistant-eval",
        "enable_public_projects": False,
        "max_projects": 10
    }
}
