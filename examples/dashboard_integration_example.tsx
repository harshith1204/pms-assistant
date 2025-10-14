/**
 * Dashboard Integration Examples
 * 
 * This file shows different ways to integrate the dashboard feature
 * into your existing application.
 */

import React, { useState } from 'react';
import { generateDashboard, generateDashboardWithAI } from '../frontend/src/api/dashboard';
import DashboardViewer from '../frontend/src/components/DashboardViewer';

// ============================================================================
// Example 1: Standalone Dashboard Page
// ============================================================================

export function StandaloneDashboardPage() {
  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Analytics Dashboard</h1>
      <DashboardViewer />
    </div>
  );
}

// ============================================================================
// Example 2: Dashboard with Preset Queries
// ============================================================================

const PRESET_QUERIES = [
  { label: 'Work Items by Priority', query: 'show work items grouped by priority' },
  { label: 'Projects by Status', query: 'count projects by status' },
  { label: 'Team Members by Role', query: 'show team members by role' },
  { label: 'Bugs This Month', query: 'show bugs created this month' },
];

export function DashboardWithPresets() {
  const [selectedQuery, setSelectedQuery] = useState('');

  return (
    <div className="space-y-4">
      <div className="flex gap-2 flex-wrap">
        {PRESET_QUERIES.map((preset) => (
          <button
            key={preset.query}
            onClick={() => setSelectedQuery(preset.query)}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
          >
            {preset.label}
          </button>
        ))}
      </div>
      
      <DashboardViewer initialQuery={selectedQuery} />
    </div>
  );
}

// ============================================================================
// Example 3: Chat Integration - Dashboard as Chat Response
// ============================================================================

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant' | 'dashboard';
  content: string;
  dashboardData?: any;
}

export function ChatWithDashboard() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');

  const handleSend = async () => {
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: input,
    };
    
    setMessages([...messages, userMessage]);
    
    // Check if query is dashboard-related
    if (input.toLowerCase().includes('show') || 
        input.toLowerCase().includes('count') ||
        input.toLowerCase().includes('display')) {
      
      try {
        const dashboard = await generateDashboard({ query: input });
        
        const dashboardMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          type: 'dashboard',
          content: input,
          dashboardData: dashboard,
        };
        
        setMessages(prev => [...prev, dashboardMessage]);
      } catch (error) {
        console.error('Dashboard generation failed:', error);
      }
    }
    
    setInput('');
  };

  return (
    <div className="flex flex-col h-screen">
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg) => (
          <div key={msg.id}>
            {msg.type === 'dashboard' && msg.dashboardData ? (
              <div className="bg-white rounded-lg shadow p-4">
                <DashboardViewer initialQuery={msg.content} />
              </div>
            ) : (
              <div className={`p-3 rounded ${
                msg.type === 'user' ? 'bg-blue-100 ml-auto' : 'bg-gray-100'
              } max-w-2xl`}>
                {msg.content}
              </div>
            )}
          </div>
        ))}
      </div>
      
      <div className="p-4 border-t">
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSend()}
            className="flex-1 px-4 py-2 border rounded"
            placeholder="Ask for analytics..."
          />
          <button onClick={handleSend} className="px-6 py-2 bg-blue-500 text-white rounded">
            Send
          </button>
        </div>
      </div>
    </div>
  );
}

// ============================================================================
// Example 4: Dashboard with Custom Filters
// ============================================================================

export function FilteredDashboard() {
  const [filters, setFilters] = useState({
    projectId: '',
    dateRange: '',
    priority: '',
  });
  const [query, setQuery] = useState('');

  const handleGenerate = async () => {
    const dashboard = await generateDashboard({
      query,
      projectId: filters.projectId,
      filters: {
        priority: filters.priority,
        // Add more filters as needed
      },
    });
    
    // Handle dashboard response
    console.log(dashboard);
  };

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-3 gap-4">
        <select
          value={filters.projectId}
          onChange={(e) => setFilters({ ...filters, projectId: e.target.value })}
          className="px-4 py-2 border rounded"
        >
          <option value="">All Projects</option>
          <option value="proj-1">Project Alpha</option>
          <option value="proj-2">Project Beta</option>
        </select>
        
        <select
          value={filters.priority}
          onChange={(e) => setFilters({ ...filters, priority: e.target.value })}
          className="px-4 py-2 border rounded"
        >
          <option value="">All Priorities</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
        </select>
        
        <input
          type="date"
          value={filters.dateRange}
          onChange={(e) => setFilters({ ...filters, dateRange: e.target.value })}
          className="px-4 py-2 border rounded"
        />
      </div>
      
      <DashboardViewer initialQuery={query} projectId={filters.projectId} />
    </div>
  );
}

// ============================================================================
// Example 5: Multi-Dashboard Layout
// ============================================================================

export function MultiDashboardLayout() {
  const dashboards = [
    { id: '1', query: 'show work items by priority', title: 'Priority Distribution' },
    { id: '2', query: 'count projects by status', title: 'Project Status' },
    { id: '3', query: 'show bugs this month', title: 'Bug Trends' },
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 p-6">
      {dashboards.map((dashboard) => (
        <div key={dashboard.id} className="bg-white rounded-lg shadow">
          <div className="p-4 border-b">
            <h3 className="text-lg font-semibold">{dashboard.title}</h3>
          </div>
          <DashboardViewer initialQuery={dashboard.query} />
        </div>
      ))}
    </div>
  );
}

// ============================================================================
// Example 6: Programmatic Dashboard Generation
// ============================================================================

export function ProgrammaticDashboard() {
  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(false);

  const generateCustomDashboard = async () => {
    setLoading(true);
    
    try {
      // Generate dashboard programmatically
      const result = await generateDashboard({
        query: 'show work items by priority',
      });
      
      if (result.success) {
        // You now have access to:
        console.log('Metadata:', result.metadata);
        console.log('Charts:', result.charts);
        console.log('Insights:', result.insights);
        console.log('Raw Data:', result.rawData);
        
        setDashboardData(result);
        
        // You can now:
        // 1. Save to database
        // 2. Share via link
        // 3. Export to PDF
        // 4. Send via email
        // 5. Display in custom UI
      }
    } catch (error) {
      console.error('Error:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <button 
        onClick={generateCustomDashboard}
        disabled={loading}
        className="px-4 py-2 bg-blue-500 text-white rounded"
      >
        {loading ? 'Generating...' : 'Generate Dashboard'}
      </button>
      
      {dashboardData && (
        <div className="mt-4">
          <h2>{dashboardData.metadata.title}</h2>
          <p>Total Records: {dashboardData.metadata.totalRecords}</p>
          
          {dashboardData.insights?.map((insight, idx) => (
            <p key={idx} className="text-gray-600">{insight}</p>
          ))}
          
          {/* Render charts manually if needed */}
          {dashboardData.charts.map((chart) => (
            <div key={chart.id}>
              {/* Custom chart rendering */}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Example 7: AI-Enhanced Dashboard
// ============================================================================

export function AIDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [query, setQuery] = useState('');

  const handleGenerateWithAI = async () => {
    const result = await generateDashboardWithAI({
      query,
    });
    
    // AI version includes enhanced insights from Groq
    if (result.success) {
      setDashboard(result);
      
      // AI insights are richer and more actionable
      console.log('AI Insights:', result.insights);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter query for AI analysis..."
          className="flex-1 px-4 py-2 border rounded"
        />
        <button
          onClick={handleGenerateWithAI}
          className="px-6 py-2 bg-purple-500 text-white rounded hover:bg-purple-600"
        >
          Generate with AI
        </button>
      </div>
      
      {dashboard && (
        <div className="bg-gradient-to-r from-purple-50 to-blue-50 p-6 rounded-lg">
          <h3 className="text-xl font-bold mb-4">AI-Generated Insights</h3>
          <ul className="space-y-2">
            {dashboard.insights?.map((insight, idx) => (
              <li key={idx} className="flex items-start gap-2">
                <span className="text-purple-500">✨</span>
                <span>{insight}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ============================================================================
// Example 8: Real-time Dashboard Updates
// ============================================================================

export function RealtimeDashboard() {
  const [dashboard, setDashboard] = useState(null);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  // Refresh dashboard every 30 seconds
  React.useEffect(() => {
    const interval = setInterval(async () => {
      const result = await generateDashboard({
        query: 'show current sprint progress',
      });
      
      if (result.success) {
        setDashboard(result);
        setLastUpdate(new Date());
      }
    }, 30000); // 30 seconds

    return () => clearInterval(interval);
  }, []);

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-2xl font-bold">Real-time Dashboard</h2>
        <span className="text-sm text-gray-500">
          Last updated: {lastUpdate.toLocaleTimeString()}
        </span>
      </div>
      
      {dashboard && <DashboardViewer initialQuery="show current sprint progress" />}
    </div>
  );
}

// ============================================================================
// Example 9: Export Dashboard
// ============================================================================

export function ExportableDashboard() {
  const [dashboard, setDashboard] = useState(null);

  const exportAsJSON = () => {
    if (!dashboard) return;
    
    const blob = new Blob(
      [JSON.stringify(dashboard, null, 2)], 
      { type: 'application/json' }
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `dashboard-${Date.now()}.json`;
    a.click();
  };

  const exportAsPNG = async () => {
    // Using html2canvas (install separately)
    // const canvas = await html2canvas(document.getElementById('dashboard'));
    // const link = document.createElement('a');
    // link.download = 'dashboard.png';
    // link.href = canvas.toDataURL();
    // link.click();
  };

  return (
    <div>
      <div className="flex gap-2 mb-4">
        <button onClick={exportAsJSON} className="px-4 py-2 bg-blue-500 text-white rounded">
          Export as JSON
        </button>
        <button onClick={exportAsPNG} className="px-4 py-2 bg-green-500 text-white rounded">
          Export as PNG
        </button>
      </div>
      
      <div id="dashboard">
        <DashboardViewer initialQuery="show work items by priority" />
      </div>
    </div>
  );
}

// ============================================================================
// Example 10: Embedded Dashboard Widget
// ============================================================================

export function DashboardWidget({ query, title, height = '400px' }) {
  return (
    <div 
      className="bg-white rounded-lg shadow p-4" 
      style={{ height }}
    >
      <h3 className="text-lg font-semibold mb-3">{title}</h3>
      <DashboardViewer initialQuery={query} />
    </div>
  );
}

// Usage:
// <DashboardWidget 
//   query="show work items by priority" 
//   title="Priority Distribution"
//   height="300px"
// />
