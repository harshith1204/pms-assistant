"""
Dashboard Generator - Converts MongoDB query results into interactive dashboards
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import Counter


class DashboardGenerator:
    """Generates dashboard configurations from MongoDB aggregation results"""
    
    @staticmethod
    def detect_visualization_type(data: List[Dict[str, Any]], query: str) -> str:
        """Intelligently detect the best visualization type for the data"""
        if not data or len(data) == 0:
            return "metric"
        
        first_item = data[0]
        
        # Single metric (total count, sum, etc.)
        if len(data) == 1 and "total" in first_item:
            return "metric"
        
        # Grouped/aggregated data with counts
        if "count" in first_item or "_count" in first_item:
            num_groups = len(data)
            
            # Time series data (dates in key)
            keys = list(first_item.keys())
            date_keys = [k for k in keys if any(d in k.lower() for d in ["date", "month", "year", "time"])]
            if date_keys:
                return "line"
            
            # Few categories -> pie/doughnut
            if num_groups <= 7:
                return "doughnut"
            # Many categories -> bar chart
            else:
                return "bar"
        
        # List of documents -> table
        if len(data) > 1 and not ("count" in first_item):
            return "table"
        
        return "bar"  # Default fallback
    
    @staticmethod
    def generate_chart_config(
        data: List[Dict[str, Any]],
        chart_type: str,
        title: str,
        description: Optional[str] = None,
        chart_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate Chart.js compatible configuration"""
        
        if chart_id is None:
            chart_id = f"chart_{datetime.now().timestamp()}"
        
        config: Dict[str, Any] = {
            "id": chart_id,
            "type": chart_type,
            "title": title,
            "description": description,
            "data": {},
            "options": {}
        }
        
        if chart_type == "metric":
            # Single value metric
            if data and len(data) > 0:
                first = data[0]
                value = first.get("total") or first.get("count") or len(data)
                config["data"] = {
                    "value": value,
                    "label": title
                }
        
        elif chart_type in ["bar", "line", "area"]:
            # Bar/Line chart - grouped data
            labels = []
            values = []
            
            for item in data:
                # Find the grouping field (not 'count')
                label_field = [k for k in item.keys() if k not in ["count", "_count", "total", "_id"]][0] if item else None
                
                if label_field:
                    label = str(item.get(label_field, "Unknown"))
                    value = item.get("count") or item.get("total") or 0
                    labels.append(label)
                    values.append(value)
            
            config["data"] = {
                "labels": labels,
                "datasets": [{
                    "label": title,
                    "data": values,
                    "backgroundColor": [
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(255, 206, 86, 0.8)',
                        'rgba(75, 192, 192, 0.8)',
                        'rgba(153, 102, 255, 0.8)',
                        'rgba(255, 159, 64, 0.8)',
                        'rgba(199, 199, 199, 0.8)',
                    ],
                    "borderWidth": 1
                }]
            }
            
            config["options"] = {
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {
                    "legend": {"display": True},
                    "title": {"display": True, "text": title}
                },
                "scales": {
                    "y": {"beginAtZero": True}
                }
            }
        
        elif chart_type in ["pie", "doughnut"]:
            # Pie/Doughnut chart
            labels = []
            values = []
            
            for item in data:
                label_field = [k for k in item.keys() if k not in ["count", "_count", "total", "_id"]][0] if item else None
                
                if label_field:
                    label = str(item.get(label_field, "Unknown"))
                    value = item.get("count") or item.get("total") or 0
                    labels.append(label)
                    values.append(value)
            
            config["data"] = {
                "labels": labels,
                "datasets": [{
                    "data": values,
                    "backgroundColor": [
                        'rgba(54, 162, 235, 0.8)',
                        'rgba(255, 99, 132, 0.8)',
                        'rgba(255, 206, 86, 0.8)',
                        'rgba(75, 192, 192, 0.8)',
                        'rgba(153, 102, 255, 0.8)',
                        'rgba(255, 159, 64, 0.8)',
                        'rgba(199, 199, 199, 0.8)',
                        'rgba(201, 203, 207, 0.8)',
                    ],
                    "borderWidth": 1
                }]
            }
            
            config["options"] = {
                "responsive": True,
                "maintainAspectRatio": False,
                "plugins": {
                    "legend": {"position": "right"},
                    "title": {"display": True, "text": title}
                }
            }
        
        elif chart_type == "table":
            # Table view
            config["data"] = {
                "rows": data[:50],  # Limit to 50 rows for performance
                "columns": list(data[0].keys()) if data else []
            }
        
        return config
    
    @staticmethod
    def generate_insights(
        data: List[Dict[str, Any]], 
        query: str,
        collection: str
    ) -> List[str]:
        """Generate AI-like insights from the data"""
        insights = []
        
        if not data:
            insights.append("No data found matching your query.")
            return insights
        
        # Total count insight
        if isinstance(data, list):
            total = len(data)
            if len(data) == 1 and "total" in data[0]:
                total = data[0]["total"]
            insights.append(f"Found {total} {collection} records.")
        
        # Distribution insights for grouped data
        if data and "count" in data[0]:
            # Find top category
            sorted_data = sorted(data, key=lambda x: x.get("count", 0), reverse=True)
            if sorted_data:
                top = sorted_data[0]
                group_field = [k for k in top.keys() if k not in ["count", "_count", "_id"]][0] if top else None
                if group_field:
                    top_value = top.get(group_field, "Unknown")
                    top_count = top.get("count", 0)
                    insights.append(f"'{top_value}' has the most items with {top_count} records.")
            
            # Distribution insight
            if len(data) > 1:
                total_items = sum(item.get("count", 0) for item in data)
                avg = total_items / len(data)
                insights.append(f"Average of {avg:.1f} items per category across {len(data)} categories.")
        
        return insights
    
    @staticmethod
    def create_dashboard_from_mongo_result(
        mongo_result: List[Dict[str, Any]],
        query: str,
        collection: str,
        intent: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Main method to convert MongoDB query results into a dashboard configuration
        
        Args:
            mongo_result: Raw MongoDB aggregation results
            query: Original natural language query
            collection: Primary collection queried
            intent: Parsed intent from the query planner (optional)
        
        Returns:
            Complete dashboard configuration with charts and metadata
        """
        
        # Detect best visualization
        chart_type = DashboardGenerator.detect_visualization_type(mongo_result, query)
        
        # Generate title from query
        title = query.capitalize() if len(query) < 50 else query[:47] + "..."
        
        # Generate main chart
        main_chart = DashboardGenerator.generate_chart_config(
            data=mongo_result,
            chart_type=chart_type,
            title=title,
            description=f"Analysis based on your query: {query}",
            chart_id="main_chart"
        )
        
        charts = [main_chart]
        
        # Add supplementary charts if we have grouped data
        if mongo_result and "count" in mongo_result[0] and len(mongo_result) > 3:
            # Add a table view as supplementary
            table_chart = DashboardGenerator.generate_chart_config(
                data=mongo_result,
                chart_type="table",
                title=f"{collection.capitalize()} Details",
                description="Detailed breakdown of the data",
                chart_id="detail_table"
            )
            charts.append(table_chart)
        
        # Add total metric if applicable
        if mongo_result:
            total = len(mongo_result)
            if len(mongo_result) == 1 and "total" in mongo_result[0]:
                total = mongo_result[0]["total"]
            elif "count" in mongo_result[0]:
                total = sum(item.get("count", 0) for item in mongo_result)
            
            metric_chart = {
                "id": "total_metric",
                "type": "metric",
                "title": "Total Count",
                "data": {
                    "value": total,
                    "label": f"Total {collection.capitalize()}"
                }
            }
            charts.insert(0, metric_chart)  # Add at the beginning
        
        # Generate insights
        insights = DashboardGenerator.generate_insights(mongo_result, query, collection)
        
        # Create metadata
        metadata = {
            "title": f"Dashboard: {title}",
            "description": f"Interactive analytics dashboard generated from query: '{query}'",
            "generatedFrom": query,
            "dataSource": collection,
            "totalRecords": len(mongo_result),
            "lastUpdated": datetime.utcnow().isoformat()
        }
        
        return {
            "metadata": metadata,
            "charts": charts,
            "rawData": mongo_result[:100],  # Include raw data (limited)
            "insights": insights,
            "success": True
        }
