/**
 * DashboardViewer Component
 * Renders interactive dashboards with charts generated from natural language queries
 */
import React, { useState } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Bar, Line, Pie, Doughnut } from 'react-chartjs-2';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Alert, AlertDescription } from './ui/alert';
import { Loader2, TrendingUp, RefreshCw } from 'lucide-react';
import { generateDashboard, generateDashboardWithAI, type DashboardResponse, type ChartConfig } from '../api/dashboard';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

interface DashboardViewerProps {
  initialQuery?: string;
  tenantId?: string;
  projectId?: string;
}

const MetricCard: React.FC<{ chart: ChartConfig }> = ({ chart }) => {
  return (
    <Card className="bg-gradient-to-br from-blue-50 to-indigo-50 dark:from-blue-950 dark:to-indigo-950">
      <CardHeader className="pb-2">
        <CardTitle className="text-lg font-medium text-gray-600 dark:text-gray-300">
          {chart.title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-4xl font-bold text-gray-900 dark:text-gray-100">
          {chart.data?.value?.toLocaleString() || 0}
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          {chart.data?.label || ''}
        </p>
      </CardContent>
    </Card>
  );
};

const TableView: React.FC<{ chart: ChartConfig }> = ({ chart }) => {
  const rows = chart.data?.rows || [];
  const columns = chart.data?.columns || [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>{chart.title}</CardTitle>
        {chart.description && <CardDescription>{chart.description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto max-h-96">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800 sticky top-0">
              <tr>
                {columns.map((col: string, idx: number) => (
                  <th key={idx} className="px-4 py-2 text-left font-medium text-gray-700 dark:text-gray-300">
                    {col}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row: any, idx: number) => (
                <tr key={idx} className="border-t dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800">
                  {columns.map((col: string, colIdx: number) => (
                    <td key={colIdx} className="px-4 py-2 text-gray-600 dark:text-gray-400">
                      {typeof row[col] === 'object' ? JSON.stringify(row[col]) : String(row[col] || '-')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </CardContent>
    </Card>
  );
};

const ChartRenderer: React.FC<{ chart: ChartConfig }> = ({ chart }) => {
  const defaultOptions = {
    responsive: true,
    maintainAspectRatio: false,
    ...chart.options,
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{chart.title}</CardTitle>
        {chart.description && <CardDescription>{chart.description}</CardDescription>}
      </CardHeader>
      <CardContent>
        <div style={{ height: '300px' }}>
          {chart.type === 'bar' && <Bar data={chart.data} options={defaultOptions} />}
          {chart.type === 'line' && <Line data={chart.data} options={defaultOptions} />}
          {chart.type === 'area' && <Line data={chart.data} options={defaultOptions} />}
          {chart.type === 'pie' && <Pie data={chart.data} options={defaultOptions} />}
          {chart.type === 'doughnut' && <Doughnut data={chart.data} options={defaultOptions} />}
        </div>
      </CardContent>
    </Card>
  );
};

export const DashboardViewer: React.FC<DashboardViewerProps> = ({
  initialQuery = '',
  tenantId,
  projectId,
}) => {
  const [query, setQuery] = useState(initialQuery);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async (useAI: boolean = false) => {
    if (!query.trim()) {
      setError('Please enter a query');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = useAI
        ? await generateDashboardWithAI({ query, tenantId, projectId })
        : await generateDashboard({ query, tenantId, projectId });

      if (response.success) {
        setDashboard(response);
      } else {
        setError(response.error || 'Dashboard generation failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full space-y-6 p-6">
      {/* Query Input */}
      <Card>
        <CardHeader>
          <CardTitle>Natural Language Dashboard Query</CardTitle>
          <CardDescription>
            Ask questions like: "Show work items by priority", "Count projects by status", "Display bugs per team member"
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Enter your query (e.g., show work items grouped by priority)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleGenerate(false)}
              className="flex-1"
            />
            <Button onClick={() => handleGenerate(false)} disabled={loading}>
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <TrendingUp className="h-4 w-4" />}
              <span className="ml-2">Generate</span>
            </Button>
            <Button onClick={() => handleGenerate(true)} disabled={loading} variant="outline">
              <RefreshCw className="h-4 w-4" />
              <span className="ml-2">AI Enhanced</span>
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Dashboard Display */}
      {dashboard && dashboard.success && (
        <div className="space-y-6">
          {/* Dashboard Header */}
          <Card className="bg-gradient-to-r from-blue-600 to-indigo-600 text-white">
            <CardHeader>
              <CardTitle className="text-2xl">{dashboard.metadata.title}</CardTitle>
              <CardDescription className="text-blue-100">
                {dashboard.metadata.description}
              </CardDescription>
              <div className="flex gap-4 text-sm mt-2 text-blue-100">
                <span>Source: {dashboard.metadata.dataSource}</span>
                <span>•</span>
                <span>Records: {dashboard.metadata.totalRecords}</span>
                <span>•</span>
                <span>Updated: {new Date(dashboard.metadata.lastUpdated).toLocaleString()}</span>
              </div>
            </CardHeader>
          </Card>

          {/* Insights */}
          {dashboard.insights && dashboard.insights.length > 0 && (
            <Card className="border-l-4 border-blue-500">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-blue-500" />
                  Key Insights
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {dashboard.insights.map((insight, idx) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-blue-500 font-bold">•</span>
                      <span className="text-gray-700 dark:text-gray-300">{insight}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Charts Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {dashboard.charts.map((chart) => (
              <div key={chart.id} className={chart.type === 'table' ? 'lg:col-span-3' : ''}>
                {chart.type === 'metric' && <MetricCard chart={chart} />}
                {chart.type === 'table' && <TableView chart={chart} />}
                {!['metric', 'table'].includes(chart.type) && <ChartRenderer chart={chart} />}
              </div>
            ))}
          </div>

          {/* Raw Data (Optional) */}
          {dashboard.rawData && dashboard.rawData.length > 0 && (
            <details className="mt-4">
              <summary className="cursor-pointer text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100">
                View Raw Data ({dashboard.rawData.length} records)
              </summary>
              <pre className="mt-2 p-4 bg-gray-100 dark:bg-gray-800 rounded text-xs overflow-auto max-h-96">
                {JSON.stringify(dashboard.rawData, null, 2)}
              </pre>
            </details>
          )}
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-blue-500" />
          <span className="ml-3 text-gray-600 dark:text-gray-400">Generating dashboard...</span>
        </div>
      )}
    </div>
  );
};

export default DashboardViewer;
