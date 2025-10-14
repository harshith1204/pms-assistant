# Interactive Dynamic Dashboard Feature

This feature enables you to generate interactive analytical dashboards from natural language queries and MongoDB data.

## Overview

The dashboard system consists of:

1. **Backend** (Python/FastAPI)
   - Natural language query processing
   - MongoDB aggregation pipeline generation
   - Chart configuration generation
   - AI-enhanced insights

2. **Frontend** (React/TypeScript)
   - Interactive dashboard rendering
   - Chart.js visualizations
   - Query interface

## Architecture

```
User Query → AI Processing → MongoDB Query → Data Transformation → Dashboard Config → Chart Rendering
```

## Backend Components

### 1. Dashboard Models (`generate/dashboard_models.py`)

Pydantic models for request/response handling:

```python
class DashboardQueryRequest(BaseModel):
    query: str  # Natural language query
    tenantId: Optional[str] = None
    projectId: Optional[str] = None
    filters: Optional[Dict[str, Any]] = None

class DashboardResponse(BaseModel):
    metadata: DashboardMetadata
    charts: List[ChartConfig]
    rawData: Optional[List[Dict[str, Any]]] = None
    insights: Optional[List[str]] = None
```

### 2. Dashboard Generator (`generate/dashboard_generator.py`)

Converts MongoDB query results into dashboard configurations:

```python
class DashboardGenerator:
    @staticmethod
    def detect_visualization_type(data, query) -> str:
        # Intelligently chooses: bar, line, pie, doughnut, table, metric
        
    @staticmethod
    def generate_chart_config(data, chart_type, title) -> Dict:
        # Generates Chart.js compatible config
        
    @staticmethod
    def create_dashboard_from_mongo_result(mongo_result, query, collection) -> Dict:
        # Main method - creates complete dashboard
```

### 3. Dashboard Router (`generate/dashboard_router.py`)

FastAPI endpoints:

- **POST `/generate-dashboard`**: Basic dashboard generation
- **POST `/generate-dashboard-ai`**: AI-enhanced with Groq insights

## API Endpoints

### Generate Dashboard

```bash
POST http://localhost:7000/generate-dashboard

Request:
{
  "query": "show work items by priority",
  "tenantId": "optional-tenant-id",
  "projectId": "optional-project-id"
}

Response:
{
  "metadata": {
    "title": "Dashboard: Show work items by priority",
    "description": "Interactive analytics dashboard...",
    "generatedFrom": "show work items by priority",
    "dataSource": "workItem",
    "totalRecords": 150,
    "lastUpdated": "2025-10-14T12:00:00"
  },
  "charts": [
    {
      "id": "total_metric",
      "type": "metric",
      "title": "Total Count",
      "data": {
        "value": 150,
        "label": "Total WorkItems"
      }
    },
    {
      "id": "main_chart",
      "type": "doughnut",
      "title": "Show work items by priority",
      "data": {
        "labels": ["High", "Medium", "Low"],
        "datasets": [{
          "data": [45, 60, 45],
          "backgroundColor": [...]
        }]
      },
      "options": {...}
    }
  ],
  "insights": [
    "Found 150 workItem records.",
    "'High' has the most items with 60 records.",
    "Average of 50.0 items per category across 3 categories."
  ],
  "success": true
}
```

## Frontend Components

### Dashboard Viewer Component

```tsx
import DashboardViewer from './components/DashboardViewer';

<DashboardViewer 
  initialQuery="show work items by priority"
  tenantId="your-tenant-id"
  projectId="your-project-id"
/>
```

### Dashboard Page

Full page implementation at `frontend/src/pages/Dashboard.tsx`

## Supported Visualization Types

1. **Metric Card** - Single value display (totals, counts)
2. **Bar Chart** - Categorical comparisons
3. **Line Chart** - Trends over time
4. **Pie/Doughnut Chart** - Distribution (≤7 categories)
5. **Table** - Detailed data view

## Example Queries

### Work Items
```
- "Show work items grouped by priority"
- "Count work items by status"
- "Display work items by assignee"
- "Show bugs created this month"
```

### Projects
```
- "Count projects by status"
- "Show active projects"
- "List projects by team"
```

### Team Analytics
```
- "Show team members by role"
- "Count members per project"
- "Display workload by assignee"
```

## Installation

### 1. Install Backend Dependencies

No additional dependencies needed - uses existing packages.

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install chart.js react-chartjs-2
```

### 3. Update Main App Router

Add the dashboard route to your React app:

```tsx
// In App.tsx or router config
import Dashboard from './pages/Dashboard';

<Route path="/dashboard" element={<Dashboard />} />
```

## Usage

### Basic Usage

```typescript
import { generateDashboard } from './api/dashboard';

const response = await generateDashboard({
  query: "show work items by priority"
});

console.log(response.charts);  // Chart configurations
console.log(response.insights); // AI-generated insights
```

### With AI Enhancement

```typescript
import { generateDashboardWithAI } from './api/dashboard';

const response = await generateDashboardWithAI({
  query: "show work items by priority"
});

// Includes AI-generated insights from Groq
```

## How It Works

### 1. Query Processing

```
User: "show work items by priority"
  ↓
Query Planner (existing system)
  ↓
MongoDB Aggregation Pipeline
  ↓
[
  { $match: {...} },
  { $group: { _id: "$priority", count: { $sum: 1 } } },
  { $sort: { count: -1 } }
]
```

### 2. Data Transformation

```python
MongoDB Result:
[
  { "priority": "High", "count": 60 },
  { "priority": "Medium", "count": 45 },
  { "priority": "Low", "count": 45 }
]
  ↓
Dashboard Generator
  ↓
Chart.js Config:
{
  "type": "doughnut",
  "data": {
    "labels": ["High", "Medium", "Low"],
    "datasets": [{ "data": [60, 45, 45], ... }]
  }
}
```

### 3. Frontend Rendering

```tsx
<Doughnut data={chartConfig.data} options={chartConfig.options} />
```

## Configuration

### Environment Variables

```bash
# Backend (.env)
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b  # or another model
MONGODB_CONNECTION_STRING=mongodb://localhost:27017
```

### Frontend

```bash
# Frontend (.env)
VITE_API_URL=http://localhost:7000
```

## Customization

### Add Custom Chart Types

Edit `generate/dashboard_generator.py`:

```python
elif chart_type == "my_custom_chart":
    config["data"] = {
        # Your custom configuration
    }
```

### Customize Insights

Edit the `generate_insights` method in `dashboard_generator.py`:

```python
def generate_insights(data, query, collection):
    insights = []
    # Your custom insight logic
    return insights
```

### Add New Query Templates

In your frontend, create query templates:

```tsx
const QUERY_TEMPLATES = {
  workItems: [
    "show work items by priority",
    "count bugs by assignee",
    // ...
  ],
  projects: [
    "list active projects",
    // ...
  ]
};
```

## Advanced Features

### Grid Layout (Future Enhancement)

Charts include optional `gridPosition` for advanced layouts:

```typescript
{
  gridPosition: {
    x: 0,  // column
    y: 0,  // row
    w: 2,  // width
    h: 1   // height
  }
}
```

### Export Dashboards

Add export functionality:

```typescript
const exportDashboard = (dashboard: DashboardResponse) => {
  const blob = new Blob([JSON.stringify(dashboard, null, 2)], 
    { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  // Download logic
};
```

### Real-time Updates

Implement WebSocket updates:

```typescript
const ws = new WebSocket('ws://localhost:7000/ws/dashboard');
ws.onmessage = (event) => {
  const updatedDashboard = JSON.parse(event.data);
  setDashboard(updatedDashboard);
};
```

## Testing

### Test Backend Endpoint

```bash
curl -X POST http://localhost:7000/generate-dashboard \
  -H "Content-Type: application/json" \
  -d '{
    "query": "show work items by priority"
  }'
```

### Test Frontend Component

```tsx
import { render, screen } from '@testing-library/react';
import DashboardViewer from './DashboardViewer';

test('renders dashboard viewer', () => {
  render(<DashboardViewer />);
  expect(screen.getByPlaceholder(/enter your query/i)).toBeInTheDocument();
});
```

## Troubleshooting

### Charts Not Rendering

1. Ensure Chart.js is installed: `npm install chart.js react-chartjs-2`
2. Check browser console for errors
3. Verify data structure matches Chart.js format

### Empty Dashboard

1. Check MongoDB connection
2. Verify query returns data
3. Check browser network tab for API errors

### AI Insights Not Showing

1. Verify `GROQ_API_KEY` is set
2. Use `/generate-dashboard` instead of `/generate-dashboard-ai` for basic version
3. Check Groq API quota/limits

## Performance Optimization

### Limit Data

```python
# In dashboard_generator.py
config["data"] = {
    "rows": data[:50],  # Limit to 50 rows
}
```

### Cache Dashboards

Implement caching in your API:

```python
from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_dashboard(query: str):
    # Your logic
```

### Lazy Loading

Load charts progressively:

```tsx
const [visibleCharts, setVisibleCharts] = useState(3);
// Load more on scroll
```

## Future Enhancements

- [ ] Dashboard templates/presets
- [ ] Scheduled dashboard updates
- [ ] Dashboard sharing/collaboration
- [ ] Custom color themes
- [ ] Export to PDF/PNG
- [ ] Drill-down capabilities
- [ ] Comparison views (time-based)
- [ ] Alert thresholds

## License

Same as main project.

## Support

For issues or questions, please open an issue in the main repository.
