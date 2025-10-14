"""
Dashboard API Router - Handles natural language queries and generates interactive dashboards
"""
import os
from fastapi import APIRouter, HTTPException
from .dashboard_models import DashboardQueryRequest, DashboardResponse
from .dashboard_generator import DashboardGenerator

try:
    from groq import Groq
except Exception:
    Groq = None

router = APIRouter()


@router.post("/generate-dashboard", response_model=DashboardResponse)
async def generate_dashboard(req: DashboardQueryRequest) -> DashboardResponse:
    """
    Generate an interactive analytical dashboard from a natural language query.
    
    This endpoint:
    1. Takes a natural language query (e.g., "show work items by priority")
    2. Uses AI to convert it to a MongoDB aggregation pipeline
    3. Executes the query against MongoDB
    4. Generates dashboard configuration with charts and insights
    5. Returns Chart.js compatible configuration for frontend rendering
    
    Example queries:
    - "Show work items grouped by priority"
    - "Count projects by status"
    - "Display bugs assigned to each team member"
    - "Show work items created over time"
    """
    
    # Import MongoDB tools
    from mongo.constants import mongodb_tools, DATABASE_NAME
    from planner import plan_and_execute_query
    
    try:
        # Ensure MongoDB connection
        if not mongodb_tools.connected:
            await mongodb_tools.connect()
        
        # Use the intelligent query planner to execute the query
        result = await plan_and_execute_query(req.query)
        
        if not result["success"]:
            return DashboardResponse(
                metadata={
                    "title": "Query Failed",
                    "description": "",
                    "generatedFrom": req.query,
                    "dataSource": "unknown",
                    "totalRecords": 0,
                    "lastUpdated": ""
                },
                charts=[],
                success=False,
                error=result.get("error", "Unknown error")
            )
        
        # Extract results
        mongo_data = result.get("result", [])
        intent = result.get("intent", {})
        primary_entity = intent.get("primary_entity", "documents")
        
        # Handle stringified JSON results
        if isinstance(mongo_data, str):
            import json
            try:
                mongo_data = json.loads(mongo_data)
            except Exception:
                mongo_data = []
        
        # Parse MongoDB response format if needed
        if isinstance(mongo_data, list) and len(mongo_data) > 0:
            if isinstance(mongo_data[0], str) and mongo_data[0].startswith("Found"):
                # Skip the message, parse remaining JSON strings
                documents = []
                for item in mongo_data[1:]:
                    if isinstance(item, str):
                        try:
                            documents.append(json.loads(item))
                        except Exception:
                            continue
                    else:
                        documents.append(item)
                mongo_data = documents
        
        # Generate dashboard configuration
        dashboard = DashboardGenerator.create_dashboard_from_mongo_result(
            mongo_result=mongo_data,
            query=req.query,
            collection=primary_entity,
            intent=intent
        )
        
        return DashboardResponse(**dashboard)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        return DashboardResponse(
            metadata={
                "title": "Error",
                "description": "",
                "generatedFrom": req.query,
                "dataSource": "unknown",
                "totalRecords": 0,
                "lastUpdated": ""
            },
            charts=[],
            success=False,
            error=f"Dashboard generation failed: {str(e)}"
        )


@router.post("/generate-dashboard-ai", response_model=DashboardResponse)
async def generate_dashboard_with_ai(req: DashboardQueryRequest) -> DashboardResponse:
    """
    Alternative endpoint that uses Groq AI to generate dashboard insights and chart configurations.
    This provides more intelligent chart selection and AI-generated insights.
    """
    
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY not configured")
    
    if Groq is None:
        raise HTTPException(status_code=500, detail="groq package not installed on server")
    
    from mongo.constants import mongodb_tools, DATABASE_NAME
    from planner import plan_and_execute_query
    
    try:
        # Execute MongoDB query
        if not mongodb_tools.connected:
            await mongodb_tools.connect()
        
        result = await plan_and_execute_query(req.query)
        
        if not result["success"]:
            return DashboardResponse(
                metadata={
                    "title": "Query Failed",
                    "description": "",
                    "generatedFrom": req.query,
                    "dataSource": "unknown",
                    "totalRecords": 0,
                    "lastUpdated": ""
                },
                charts=[],
                success=False,
                error=result.get("error", "Unknown error")
            )
        
        mongo_data = result.get("result", [])
        intent = result.get("intent", {})
        primary_entity = intent.get("primary_entity", "documents")
        
        # Parse data
        if isinstance(mongo_data, str):
            import json
            mongo_data = json.loads(mongo_data)
        
        # Use AI to generate enhanced insights
        client = Groq(api_key=api_key)
        
        system_prompt = """You are a data analytics assistant specialized in generating insights from project management data.
        Given MongoDB query results, provide:
        1. Key insights and patterns in the data
        2. Recommendations for stakeholders
        3. Notable trends or anomalies
        
        Return insights as a JSON array of strings, each insight being a concise, actionable statement.
        Format: {"insights": ["insight 1", "insight 2", ...]}
        """
        
        user_prompt = f"""
Query: {req.query}
Collection: {primary_entity}
Data Summary: {len(mongo_data)} records returned

Sample Data:
{mongo_data[:5]}

Generate 3-5 actionable insights from this data.
"""
        
        try:
            completion = client.chat.completions.create(
                model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
                temperature=0.3,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            
            import json
            ai_response = completion.choices[0].message.content or "{}"
            insights_data = json.loads(ai_response)
            ai_insights = insights_data.get("insights", [])
        except Exception as e:
            print(f"AI insights generation failed: {e}")
            ai_insights = []
        
        # Generate dashboard with AI insights
        dashboard = DashboardGenerator.create_dashboard_from_mongo_result(
            mongo_result=mongo_data,
            query=req.query,
            collection=primary_entity,
            intent=intent
        )
        
        # Merge AI insights with generated insights
        if ai_insights:
            dashboard["insights"] = ai_insights + (dashboard.get("insights") or [])
        
        return DashboardResponse(**dashboard)
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        
        return DashboardResponse(
            metadata={
                "title": "Error",
                "description": "",
                "generatedFrom": req.query,
                "dataSource": "unknown",
                "totalRecords": 0,
                "lastUpdated": ""
            },
            charts=[],
            success=False,
            error=f"Dashboard generation failed: {str(e)}"
        )
