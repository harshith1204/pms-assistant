"""
Enhanced Dashboard API Router - Rich interactive dashboards with comprehensive components
"""
import os
from fastapi import APIRouter, HTTPException
from .dashboard_models import DashboardQueryRequest
from .enhanced_dashboard_generator import EnhancedDashboardGenerator
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

router = APIRouter()


class EnhancedDashboardResponse(BaseModel):
    """Response for enhanced dashboard with rich components"""
    metadata: Dict[str, Any]
    components: List[Dict[str, Any]]
    rawData: Optional[List[Dict[str, Any]]] = None
    insights: Optional[List[str]] = None
    success: bool = True
    error: Optional[str] = None


@router.post("/generate-dashboard-enhanced", response_model=EnhancedDashboardResponse)
async def generate_enhanced_dashboard(req: DashboardQueryRequest) -> EnhancedDashboardResponse:
    """
    Generate a comprehensive interactive dashboard with rich components.
    
    This endpoint creates dashboards with:
    - KPI Cards with trends and metrics
    - Interactive Data Grids with sorting/filtering
    - Progress bars and completion metrics
    - Comparison cards
    - Statistical summaries
    - Heatmaps
    - List views
    - Alert indicators
    - And more!
    
    Goes beyond simple charts to provide a complete analytical experience.
    
    Example queries:
    - "show work items grouped by priority"
    - "count projects by status"
    - "display team performance metrics"
    - "analyze bug distribution by severity"
    """
    
    from mongo.constants import mongodb_tools, DATABASE_NAME
    from planner import plan_and_execute_query
    
    try:
        # Ensure MongoDB connection
        if not mongodb_tools.connected:
            await mongodb_tools.connect()
        
        # Execute query using intelligent planner
        result = await plan_and_execute_query(req.query)
        
        if not result["success"]:
            return EnhancedDashboardResponse(
                metadata={
                    "title": "Query Failed",
                    "description": "",
                    "generatedFrom": req.query,
                    "dataSource": "unknown",
                    "totalRecords": 0,
                    "lastUpdated": "",
                    "dashboardType": "enhanced"
                },
                components=[],
                success=False,
                error=result.get("error", "Unknown error")
            )
        
        # Extract results
        mongo_data = result.get("result", [])
        intent = result.get("intent", {})
        primary_entity = intent.get("primary_entity", "documents")
        
        # Parse data
        if isinstance(mongo_data, str):
            import json
            try:
                mongo_data = json.loads(mongo_data)
            except Exception:
                mongo_data = []
        
        # Handle MongoDB response format
        if isinstance(mongo_data, list) and len(mongo_data) > 0:
            if isinstance(mongo_data[0], str) and mongo_data[0].startswith("Found"):
                documents = []
                for item in mongo_data[1:]:
                    if isinstance(item, str):
                        try:
                            import json
                            documents.append(json.loads(item))
                        except Exception:
                            continue
                    else:
                        documents.append(item)
                mongo_data = documents
        
        # Generate enhanced dashboard
        dashboard = EnhancedDashboardGenerator.create_enhanced_dashboard(
            mongo_result=mongo_data,
            query=req.query,
            collection=primary_entity,
            intent=intent
        )
        
        return EnhancedDashboardResponse(**dashboard)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        return EnhancedDashboardResponse(
            metadata={
                "title": "Error",
                "description": "",
                "generatedFrom": req.query,
                "dataSource": "unknown",
                "totalRecords": 0,
                "lastUpdated": "",
                "dashboardType": "enhanced"
            },
            components=[],
            success=False,
            error=f"Dashboard generation failed: {str(e)}"
        )
