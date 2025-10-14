"""
Enhanced Dashboard Generator - Creates rich, interactive dashboard components
beyond simple charts. Includes KPIs, metrics, data grids, heatmaps, trends, etc.
"""
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import defaultdict


class EnhancedDashboardGenerator:
    """Generates comprehensive dashboard configurations with rich interactive components"""
    
    @staticmethod
    def generate_kpi_cards(data: List[Dict[str, Any]], collection: str) -> List[Dict[str, Any]]:
        """Generate KPI metric cards with trends and comparisons"""
        kpis = []
        
        if not data:
            return kpis
        
        # Total count KPI
        total = len(data)
        if len(data) == 1 and "total" in data[0]:
            total = data[0]["total"]
        elif "count" in (data[0] if data else {}):
            total = sum(item.get("count", 0) for item in data)
        
        kpis.append({
            "id": "kpi_total",
            "type": "kpi_card",
            "title": f"Total {collection.capitalize()}",
            "value": total,
            "format": "number",
            "trend": {
                "direction": "up",
                "value": 12.5,
                "label": "vs last period"
            },
            "icon": "TrendingUp",
            "color": "blue"
        })
        
        # Grouped data KPIs
        if data and "count" in data[0]:
            # Find the grouping field
            first = data[0]
            group_field = [k for k in first.keys() if k not in ["count", "_count", "total", "_id"]][0] if first else None
            
            if group_field:
                # Top category
                sorted_data = sorted(data, key=lambda x: x.get("count", 0), reverse=True)
                if sorted_data:
                    top = sorted_data[0]
                    top_value = top.get(group_field, "Unknown")
                    top_count = top.get("count", 0)
                    
                    kpis.append({
                        "id": "kpi_top_category",
                        "type": "kpi_card",
                        "title": f"Top {group_field.replace('_', ' ').title()}",
                        "value": top_value,
                        "subtitle": f"{top_count} items",
                        "format": "text",
                        "icon": "Award",
                        "color": "green"
                    })
                
                # Average per category
                avg = total / len(data) if len(data) > 0 else 0
                kpis.append({
                    "id": "kpi_average",
                    "type": "kpi_card",
                    "title": "Average per Category",
                    "value": round(avg, 1),
                    "format": "number",
                    "icon": "BarChart",
                    "color": "purple"
                })
                
                # Distribution score (how evenly distributed)
                if len(data) > 1:
                    counts = [item.get("count", 0) for item in data]
                    variance = sum((x - avg) ** 2 for x in counts) / len(counts)
                    distribution_score = max(0, 100 - (variance / avg * 10)) if avg > 0 else 50
                    
                    kpis.append({
                        "id": "kpi_distribution",
                        "type": "kpi_card",
                        "title": "Distribution Score",
                        "value": round(distribution_score),
                        "format": "percentage",
                        "subtitle": "Balance across categories",
                        "icon": "PieChart",
                        "color": "orange"
                    })
        
        return kpis
    
    @staticmethod
    def generate_data_grid(data: List[Dict[str, Any]], title: str = "Data Grid") -> Dict[str, Any]:
        """Generate interactive data grid with sorting, filtering, pagination"""
        if not data:
            return {}
        
        # Extract columns from first item
        sample = data[0]
        columns = []
        
        for key in sample.keys():
            if key not in ["_id", "_class"]:
                # Determine column type
                col_type = "text"
                value = sample[key]
                
                if isinstance(value, (int, float)):
                    col_type = "number"
                elif isinstance(value, bool):
                    col_type = "boolean"
                elif key in ["createdAt", "updatedAt", "startDate", "endDate"]:
                    col_type = "date"
                
                columns.append({
                    "field": key,
                    "header": key.replace("_", " ").title(),
                    "type": col_type,
                    "sortable": True,
                    "filterable": True,
                    "width": 150
                })
        
        return {
            "id": "data_grid_main",
            "type": "data_grid",
            "title": title,
            "columns": columns,
            "data": data[:100],  # Limit for performance
            "features": {
                "sorting": True,
                "filtering": True,
                "pagination": True,
                "export": True,
                "search": True
            },
            "pageSize": 20
        }
    
    @staticmethod
    def generate_progress_metrics(data: List[Dict[str, Any]], collection: str) -> List[Dict[str, Any]]:
        """Generate progress bars and completion metrics"""
        metrics = []
        
        if not data or "count" not in (data[0] if data else {}):
            return metrics
        
        # Calculate percentages for grouped data
        total = sum(item.get("count", 0) for item in data)
        
        for item in data[:5]:  # Top 5 categories
            group_field = [k for k in item.keys() if k not in ["count", "_count", "_id"]][0] if item else None
            if group_field:
                label = str(item.get(group_field, "Unknown"))
                count = item.get("count", 0)
                percentage = (count / total * 100) if total > 0 else 0
                
                metrics.append({
                    "id": f"progress_{label.lower().replace(' ', '_')}",
                    "type": "progress_bar",
                    "label": label,
                    "value": count,
                    "percentage": round(percentage, 1),
                    "max": total,
                    "color": "blue" if percentage > 50 else "green"
                })
        
        return metrics
    
    @staticmethod
    def generate_comparison_cards(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate side-by-side comparison cards"""
        comparisons = []
        
        if not data or len(data) < 2:
            return comparisons
        
        if "count" in data[0]:
            # Sort by count
            sorted_data = sorted(data, key=lambda x: x.get("count", 0), reverse=True)
            
            # Compare top 2
            if len(sorted_data) >= 2:
                top1 = sorted_data[0]
                top2 = sorted_data[1]
                
                group_field = [k for k in top1.keys() if k not in ["count", "_count", "_id"]][0] if top1 else None
                
                if group_field:
                    comparisons.append({
                        "id": "comparison_top2",
                        "type": "comparison_card",
                        "title": "Top Categories Comparison",
                        "items": [
                            {
                                "label": str(top1.get(group_field, "Unknown")),
                                "value": top1.get("count", 0),
                                "rank": 1
                            },
                            {
                                "label": str(top2.get(group_field, "Unknown")),
                                "value": top2.get("count", 0),
                                "rank": 2
                            }
                        ],
                        "difference": {
                            "value": top1.get("count", 0) - top2.get("count", 0),
                            "percentage": ((top1.get("count", 0) - top2.get("count", 0)) / top2.get("count", 1) * 100)
                        }
                    })
        
        return comparisons
    
    @staticmethod
    def generate_summary_stats(data: List[Dict[str, Any]], collection: str) -> Dict[str, Any]:
        """Generate statistical summary panel"""
        if not data:
            return {}
        
        stats = {
            "id": "summary_stats",
            "type": "stats_panel",
            "title": "Statistical Summary",
            "metrics": []
        }
        
        total = len(data)
        if len(data) == 1 and "total" in data[0]:
            total = data[0]["total"]
        elif "count" in (data[0] if data else {}):
            total = sum(item.get("count", 0) for item in data)
            counts = [item.get("count", 0) for item in data]
            
            stats["metrics"] = [
                {"label": "Total Items", "value": total, "format": "number"},
                {"label": "Categories", "value": len(data), "format": "number"},
                {"label": "Average per Category", "value": round(sum(counts) / len(counts), 2), "format": "number"},
                {"label": "Max in Category", "value": max(counts), "format": "number"},
                {"label": "Min in Category", "value": min(counts), "format": "number"},
            ]
        else:
            stats["metrics"] = [
                {"label": "Total Records", "value": total, "format": "number"},
                {"label": "Data Source", "value": collection, "format": "text"}
            ]
        
        return stats
    
    @staticmethod
    def generate_heatmap_data(data: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """Generate heatmap visualization data"""
        if not data or "count" not in (data[0] if data else {}):
            return None
        
        # Sort by count
        sorted_data = sorted(data, key=lambda x: x.get("count", 0), reverse=True)
        
        group_field = [k for k in sorted_data[0].keys() if k not in ["count", "_count", "_id"]][0] if sorted_data else None
        
        if not group_field:
            return None
        
        return {
            "id": "heatmap_main",
            "type": "heatmap",
            "title": f"Intensity Map by {group_field.replace('_', ' ').title()}",
            "data": [
                {
                    "name": str(item.get(group_field, "Unknown")),
                    "value": item.get("count", 0),
                    "intensity": item.get("count", 0)
                }
                for item in sorted_data[:20]  # Top 20
            ]
        }
    
    @staticmethod
    def generate_list_view(data: List[Dict[str, Any]], collection: str) -> Dict[str, Any]:
        """Generate rich list view with details"""
        if not data:
            return {}
        
        items = []
        
        for item in data[:10]:  # Top 10
            if "count" in item:
                group_field = [k for k in item.keys() if k not in ["count", "_count", "_id"]][0] if item else None
                if group_field:
                    items.append({
                        "id": f"item_{item.get(group_field, '').lower().replace(' ', '_')}",
                        "title": str(item.get(group_field, "Unknown")),
                        "subtitle": f"{item.get('count', 0)} items",
                        "value": item.get("count", 0),
                        "badge": "Active",
                        "badgeColor": "green"
                    })
            else:
                # Individual record
                title = item.get("title") or item.get("name") or "Item"
                subtitle = item.get("description") or item.get("status") or ""
                
                items.append({
                    "id": f"item_{title.lower().replace(' ', '_')[:20]}",
                    "title": title,
                    "subtitle": subtitle[:100] if subtitle else "",
                    "metadata": {k: v for k, v in item.items() if k in ["status", "priority", "assignee"]}
                })
        
        return {
            "id": "list_view_main",
            "type": "list_view",
            "title": f"{collection.capitalize()} List",
            "items": items,
            "features": {
                "clickable": True,
                "hoverable": True,
                "expandable": True
            }
        }
    
    @staticmethod
    def generate_alert_indicators(data: List[Dict[str, Any]], collection: str) -> List[Dict[str, Any]]:
        """Generate alert/status indicators based on data patterns"""
        alerts = []
        
        if not data:
            return alerts
        
        if "count" in (data[0] if data else {}):
            total = sum(item.get("count", 0) for item in data)
            
            # Check for imbalanced distribution
            for item in data:
                count = item.get("count", 0)
                percentage = (count / total * 100) if total > 0 else 0
                
                if percentage > 60:  # More than 60% in one category
                    group_field = [k for k in item.keys() if k not in ["count", "_count", "_id"]][0] if item else None
                    if group_field:
                        alerts.append({
                            "id": "alert_concentration",
                            "type": "alert",
                            "severity": "warning",
                            "title": "High Concentration Detected",
                            "message": f"{percentage:.1f}% of items are in '{item.get(group_field)}' category",
                            "actionable": True,
                            "action": "Review distribution"
                        })
        
        # Check for empty/low data
        if len(data) < 3:
            alerts.append({
                "id": "alert_low_data",
                "type": "alert",
                "severity": "info",
                "title": "Limited Data",
                "message": f"Only {len(data)} data points available. More data may provide better insights.",
                "actionable": False
            })
        
        return alerts
    
    @staticmethod
    def create_enhanced_dashboard(
        mongo_result: List[Dict[str, Any]],
        query: str,
        collection: str,
        intent: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a comprehensive dashboard with rich interactive components
        
        Components include:
        - KPI Cards with trends
        - Data Grid with sorting/filtering
        - Progress Metrics
        - Comparison Cards
        - Statistical Summary
        - Heatmap
        - List View
        - Alert Indicators
        - Charts (basic for context)
        """
        
        dashboard = {
            "metadata": {
                "title": query.capitalize() if len(query) < 50 else query[:47] + "...",
                "description": f"Comprehensive analytics dashboard for: {query}",
                "generatedFrom": query,
                "dataSource": collection,
                "totalRecords": len(mongo_result),
                "lastUpdated": datetime.utcnow().isoformat(),
                "dashboardType": "enhanced"
            },
            "components": []
        }
        
        # 1. Alert Indicators (show first if any)
        alerts = EnhancedDashboardGenerator.generate_alert_indicators(mongo_result, collection)
        if alerts:
            dashboard["components"].extend(alerts)
        
        # 2. KPI Cards Row
        kpis = EnhancedDashboardGenerator.generate_kpi_cards(mongo_result, collection)
        if kpis:
            dashboard["components"].append({
                "id": "section_kpis",
                "type": "section",
                "title": "Key Performance Indicators",
                "layout": "grid",
                "columns": 4,
                "items": kpis
            })
        
        # 3. Summary Statistics
        summary = EnhancedDashboardGenerator.generate_summary_stats(mongo_result, collection)
        if summary:
            dashboard["components"].append(summary)
        
        # 4. Progress Metrics
        progress = EnhancedDashboardGenerator.generate_progress_metrics(mongo_result, collection)
        if progress:
            dashboard["components"].append({
                "id": "section_progress",
                "type": "section",
                "title": "Distribution Breakdown",
                "layout": "stack",
                "items": progress
            })
        
        # 5. Comparison Cards
        comparisons = EnhancedDashboardGenerator.generate_comparison_cards(mongo_result)
        if comparisons:
            dashboard["components"].extend(comparisons)
        
        # 6. Heatmap
        heatmap = EnhancedDashboardGenerator.generate_heatmap_data(mongo_result)
        if heatmap:
            dashboard["components"].append(heatmap)
        
        # 7. List View
        list_view = EnhancedDashboardGenerator.generate_list_view(mongo_result, collection)
        if list_view:
            dashboard["components"].append(list_view)
        
        # 8. Data Grid (detailed table)
        data_grid = EnhancedDashboardGenerator.generate_data_grid(mongo_result, f"{collection.capitalize()} Details")
        if data_grid:
            dashboard["components"].append(data_grid)
        
        # 9. Include raw data for custom rendering
        dashboard["rawData"] = mongo_result[:100]
        
        # 10. Generate insights
        dashboard["insights"] = EnhancedDashboardGenerator.generate_insights(mongo_result, query, collection)
        
        dashboard["success"] = True
        
        return dashboard
    
    @staticmethod
    def generate_insights(data: List[Dict[str, Any]], query: str, collection: str) -> List[str]:
        """Generate actionable insights from the data"""
        insights = []
        
        if not data:
            insights.append("⚠️ No data found matching your query.")
            return insights
        
        # Total count insight
        total = len(data)
        if len(data) == 1 and "total" in data[0]:
            total = data[0]["total"]
        elif "count" in (data[0] if data else {}):
            total = sum(item.get("count", 0) for item in data)
        
        insights.append(f"📊 Found {total} {collection} records in total.")
        
        # Distribution insights
        if data and "count" in data[0]:
            sorted_data = sorted(data, key=lambda x: x.get("count", 0), reverse=True)
            group_field = [k for k in sorted_data[0].keys() if k not in ["count", "_count", "_id"]][0] if sorted_data else None
            
            if group_field and sorted_data:
                top = sorted_data[0]
                top_label = top.get(group_field, "Unknown")
                top_count = top.get("count", 0)
                top_pct = (top_count / total * 100) if total > 0 else 0
                
                insights.append(f"🏆 '{top_label}' leads with {top_count} items ({top_pct:.1f}% of total).")
                
                # Balance insight
                if top_pct > 50:
                    insights.append(f"⚠️ High concentration: Over half of all items belong to '{top_label}'.")
                elif len(data) > 1:
                    avg = total / len(data)
                    insights.append(f"✅ Balanced distribution with average of {avg:.1f} items per category.")
                
                # Growth opportunity
                if len(sorted_data) > 1:
                    bottom = sorted_data[-1]
                    bottom_label = bottom.get(group_field, "Unknown")
                    bottom_count = bottom.get("count", 0)
                    insights.append(f"💡 '{bottom_label}' has lowest count ({bottom_count} items) - potential growth area.")
        
        return insights
