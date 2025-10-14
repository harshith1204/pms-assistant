# Dashboard Feature - Quick Start Guide

## 🚀 What Was Added

A complete **Natural Language to Dashboard** system that:
1. Takes natural language queries (e.g., "show work items by priority")
2. Converts them to MongoDB aggregations using your existing query planner
3. Generates interactive Chart.js dashboards
4. Provides AI-powered insights (optional)

## 📁 New Files

### Backend (Python)
```
generate/
├── dashboard_models.py      # Pydantic models for requests/responses
├── dashboard_generator.py   # Converts MongoDB data → Chart.js configs
└── dashboard_router.py      # FastAPI endpoints

main.py                      # Updated to include dashboard router
```

### Frontend (TypeScript/React)
```
frontend/src/
├── api/dashboard.ts         # API client for dashboard endpoints
├── components/
│   └── DashboardViewer.tsx  # Main dashboard component
└── pages/
    └── Dashboard.tsx        # Full dashboard page

package.json                 # Updated with chart.js dependencies
```

## 🔧 Installation

### 1. Install Frontend Dependencies

```bash
cd frontend
npm install
```

The required packages (`chart.js` and `react-chartjs-2`) are already added to `package.json`.

### 2. No Backend Changes Needed

All backend dependencies are already available in your environment!

## 🎯 Usage Examples

### Example 1: Basic API Call

Test the endpoint directly:

```bash
curl -X POST http://localhost:7000/generate-dashboard \
  -H "Content-Type: application/json" \
  -d '{
    "query": "show work items grouped by priority"
  }'
```

Response:
```json
{
  "metadata": {
    "title": "Dashboard: Show work items grouped by priority",
    "dataSource": "workItem",
    "totalRecords": 150
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
      "title": "Work Items by Priority",
      "data": {
        "labels": ["High", "Medium", "Low"],
        "datasets": [{
          "data": [45, 60, 45],
          "backgroundColor": ["rgba(54, 162, 235, 0.8)", ...]
        }]
      }
    }
  ],
  "insights": [
    "Found 150 workItem records.",
    "'Medium' has the most items with 60 records."
  ]
}
```

### Example 2: Using the React Component

```tsx
import DashboardViewer from './components/DashboardViewer';

function MyDashboard() {
  return (
    <DashboardViewer 
      initialQuery="show work items by status"
      tenantId="your-tenant-id"
    />
  );
}
```

### Example 3: Add Dashboard to Your Router

In your `App.tsx` or main router:

```tsx
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Dashboard from './pages/Dashboard';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Your existing routes */}
        <Route path="/analytics" element={<Dashboard />} />
      </Routes>
    </BrowserRouter>
  );
}
```

### Example 4: Custom Dashboard with API

```tsx
import { useState } from 'react';
import { generateDashboard } from './api/dashboard';

function CustomDashboard() {
  const [dashboard, setDashboard] = useState(null);
  
  const handleQuery = async () => {
    const result = await generateDashboard({
      query: "count projects by status"
    });
    
    if (result.success) {
      setDashboard(result);
      console.log('Charts:', result.charts);
      console.log('Insights:', result.insights);
    }
  };
  
  return (
    <div>
      <button onClick={handleQuery}>Generate Dashboard</button>
      {dashboard && (
        <div>
          <h2>{dashboard.metadata.title}</h2>
          {/* Render your charts here */}
        </div>
      )}
    </div>
  );
}
```

## 🎨 Supported Query Types

### Work Items
```
✅ "show work items by priority"
✅ "count bugs by status"
✅ "display work items grouped by assignee"
✅ "show open tasks"
```

### Projects
```
✅ "count projects by status"
✅ "show active projects"
✅ "list projects by team"
```

### Team Analytics
```
✅ "show team members by role"
✅ "count members per project"
✅ "display workload distribution"
```

### Time-based
```
✅ "show work items created this month"
✅ "count bugs by creation date"
✅ "display project timeline"
```

## 📊 Chart Types

The system automatically chooses the best visualization:

| Data Pattern | Chart Type | When Used |
|-------------|------------|-----------|
| Single value | Metric Card | Total counts, sums |
| 2-7 categories | Doughnut/Pie | Priority, status distribution |
| 8+ categories | Bar Chart | Many categories |
| Time series | Line Chart | Trends over time |
| Detailed data | Table | Raw data view |

## 🤖 AI-Enhanced Insights

Use the AI endpoint for enhanced insights:

```bash
curl -X POST http://localhost:7000/generate-dashboard-ai \
  -H "Content-Type: application/json" \
  -d '{
    "query": "show work items by priority"
  }'
```

Requires `GROQ_API_KEY` environment variable.

## ⚙️ Configuration

### Environment Variables

Create/update `.env`:

```bash
# Required for AI insights (optional for basic dashboards)
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-120b

# MongoDB (should already be configured)
MONGODB_CONNECTION_STRING=mongodb://localhost:27017
DATABASE_NAME=ProjectManagement
```

Frontend `.env`:
```bash
VITE_API_URL=http://localhost:7000
```

## 🔄 Integration with Existing Chat

You can integrate dashboards into your chat interface:

```tsx
// In your chat handler
if (message.type === 'dashboard_generated') {
  return (
    <DashboardViewer 
      initialQuery={message.query}
      tenantId={message.tenantId}
    />
  );
}
```

## 🧪 Testing

### Test Backend

```bash
# Start your backend
python main.py

# Test the endpoint
curl -X POST http://localhost:7000/generate-dashboard \
  -H "Content-Type: application/json" \
  -d '{"query": "show work items by priority"}'
```

### Test Frontend

```bash
# Start frontend
cd frontend
npm run dev

# Navigate to
http://localhost:5173/analytics
# or wherever you added the route
```

## 🎯 Real-World Examples

### 1. Sprint Dashboard
```typescript
const sprintDashboard = await generateDashboard({
  query: "show work items in current sprint by status",
  projectId: "sprint-123"
});
```

### 2. Team Performance
```typescript
const teamMetrics = await generateDashboard({
  query: "count completed work items by assignee this month",
  tenantId: "team-xyz"
});
```

### 3. Bug Analysis
```typescript
const bugReport = await generateDashboard({
  query: "show critical bugs by module",
  filters: { priority: "Critical" }
});
```

## 🐛 Troubleshooting

### Charts Not Showing

**Problem**: Dashboard loads but no charts appear

**Solution**:
```bash
# Ensure Chart.js is installed
cd frontend
npm install chart.js react-chartjs-2
npm run dev
```

### Empty Results

**Problem**: Dashboard shows "No data found"

**Solution**:
1. Check MongoDB connection
2. Verify your query matches your data
3. Test the query directly in MongoDB
4. Check backend logs for errors

### CORS Errors

**Problem**: Frontend can't reach API

**Solution**: Verify CORS is configured in `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or your frontend URL
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## 📈 Performance Tips

### Limit Large Datasets

```python
# Automatically handled - top 50 rows for tables
# Configurable in dashboard_generator.py
```

### Cache Common Queries

```python
# Add caching (future enhancement)
from functools import lru_cache

@lru_cache(maxsize=100)
def cached_query(query: str):
    # Your logic
```

## 🚀 Next Steps

1. **Add Navigation**: Link to dashboard from your main nav
2. **Create Presets**: Build common query templates
3. **Customize Styling**: Match your brand colors
4. **Add Filters**: Enable date range, project selection
5. **Export Feature**: Save dashboards as PDF/JSON

## 📚 Full Documentation

See [README_DASHBOARD.md](./README_DASHBOARD.md) for complete documentation.

## 🎉 You're Ready!

Start your servers and navigate to the dashboard page:

```bash
# Terminal 1: Backend
python main.py

# Terminal 2: Frontend
cd frontend
npm run dev

# Open browser
http://localhost:5173/analytics
```

Try queries like:
- "show work items by priority"
- "count projects by status"
- "display team members by role"

Enjoy your new analytics capabilities! 🎨📊
