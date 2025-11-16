from typing import TypedDict, List


class DashboardMeta(TypedDict, total=False):
    dashboard_id: int
    title: str
    tags: List[str]
    measures: List[str]
    dimensions: List[str]
    time_grains: List[str]
    supports_compare: bool
    filter_keys: List[str]
    example_prompts: List[str]


# Seed catalog with placeholders; replace IDs and metadata to your environment
CATALOG: List[DashboardMeta] = [
    {
        "dashboard_id": 1,
        "title": "Revenue Overview",
        "tags": ["revenue", "sales", "finance"],
        "measures": ["revenue", "arpu", "orders"],
        "dimensions": ["region", "product", "plan", "channel"],
        "time_grains": ["day", "week", "month"],
        "supports_compare": True,
        "filter_keys": ["date", "region", "product", "breakdown"],
        "example_prompts": [
            "Revenue by region last quarter",
            "ARPU trend by plan",
        ],
    },
    {
        "dashboard_id": 2,
        "title": "Retention & Cohorts",
        "tags": ["retention", "cohort", "customers"],
        "measures": ["retention_rate", "new_users", "active_users"],
        "dimensions": ["region", "plan", "cohort"],
        "time_grains": ["week", "month"],
        "supports_compare": False,
        "filter_keys": ["date", "plan", "region"],
        "example_prompts": [
            "Monthly retention by plan",
            "New users by region last 90 days",
        ],
    },
]
