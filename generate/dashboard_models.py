from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel


class DashboardQueryRequest(BaseModel):
    """Request model for dashboard generation from natural language query"""
    query: str  # Natural language query like "show work items by priority"
    tenantId: Optional[str] = None
    projectId: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None


class ChartConfig(BaseModel):
    """Configuration for a single chart/widget in the dashboard"""
    id: str
    type: Literal["bar", "line", "pie", "doughnut", "table", "metric", "area", "scatter"]
    title: str
    description: Optional[str] = None
    data: Dict[str, Any]  # Chart.js compatible data structure
    options: Optional[Dict[str, Any]] = None  # Chart.js options
    gridPosition: Optional[Dict[str, int]] = None  # {x, y, w, h} for grid layout


class DashboardMetadata(BaseModel):
    """Metadata about the dashboard"""
    title: str
    description: Optional[str] = None
    generatedFrom: str  # The original query
    dataSource: str  # e.g., "workItem", "project", etc.
    totalRecords: int
    lastUpdated: str


class DashboardResponse(BaseModel):
    """Response containing the complete dashboard configuration"""
    metadata: DashboardMetadata
    charts: List[ChartConfig]
    rawData: Optional[List[Dict[str, Any]]] = None  # Original MongoDB data
    insights: Optional[List[str]] = None  # AI-generated insights
    success: bool = True
    error: Optional[str] = None
