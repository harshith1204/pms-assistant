/**
 * Enhanced Dashboard Component
 * Renders rich, interactive dashboard with comprehensive components
 * beyond simple charts - KPIs, data grids, metrics, comparisons, etc.
 */
import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Alert, AlertDescription, AlertTitle } from './ui/alert';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';
import { 
  Loader2, TrendingUp, TrendingDown, Award, BarChart, PieChart, 
  AlertTriangle, Info, CheckCircle, ArrowUp, ArrowDown, Download
} from 'lucide-react';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:7000';

interface EnhancedDashboardProps {
  initialQuery?: string;
  tenantId?: string;
  projectId?: string;
}

// KPI Card Component
const KPICard: React.FC<{ component: any }> = ({ component }) => {
  const icons = {
    TrendingUp: TrendingUp,
    Award: Award,
    BarChart: BarChart,
    PieChart: PieChart,
  };
  
  const colors = {
    blue: 'from-blue-500 to-blue-600',
    green: 'from-green-500 to-green-600',
    purple: 'from-purple-500 to-purple-600',
    orange: 'from-orange-500 to-orange-600',
  };
  
  const Icon = icons[component.icon as keyof typeof icons] || TrendingUp;
  const gradient = colors[component.color as keyof typeof colors] || colors.blue;
  
  return (
    <Card className={`bg-gradient-to-br ${gradient} text-white`}>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium opacity-90">
            {component.title}
          </CardTitle>
          <Icon className="h-4 w-4 opacity-75" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-bold">
          {component.format === 'percentage' && `${component.value}%`}
          {component.format === 'number' && component.value.toLocaleString()}
          {component.format === 'text' && component.value}
        </div>
        {component.subtitle && (
          <p className="text-xs opacity-75 mt-1">{component.subtitle}</p>
        )}
        {component.trend && (
          <div className="flex items-center mt-2 text-xs opacity-90">
            {component.trend.direction === 'up' ? (
              <ArrowUp className="h-3 w-3 mr-1" />
            ) : (
              <ArrowDown className="h-3 w-3 mr-1" />
            )}
            <span>{component.trend.value}% {component.trend.label}</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Data Grid Component
const DataGrid: React.FC<{ component: any }> = ({ component }) => {
  const [sortField, setSortField] = useState<string | null>(null);
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('asc');
  const [searchTerm, setSearchTerm] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  
  const pageSize = component.pageSize || 20;
  
  // Filter data
  const filteredData = searchTerm
    ? component.data.filter((row: any) =>
        Object.values(row).some((val) =>
          String(val).toLowerCase().includes(searchTerm.toLowerCase())
        )
      )
    : component.data;
  
  // Sort data
  const sortedData = sortField
    ? [...filteredData].sort((a, b) => {
        const aVal = a[sortField];
        const bVal = b[sortField];
        const direction = sortDirection === 'asc' ? 1 : -1;
        return aVal > bVal ? direction : -direction;
      })
    : filteredData;
  
  // Paginate
  const totalPages = Math.ceil(sortedData.length / pageSize);
  const paginatedData = sortedData.slice(
    (currentPage - 1) * pageSize,
    currentPage * pageSize
  );
  
  const handleSort = (field: string) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };
  
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle>{component.title}</CardTitle>
          {component.features?.export && (
            <Button variant="outline" size="sm">
              <Download className="h-4 w-4 mr-2" />
              Export
            </Button>
          )}
        </div>
        {component.features?.search && (
          <Input
            placeholder="Search..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="mt-2"
          />
        )}
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 dark:bg-gray-800">
              <tr>
                {component.columns.map((col: any) => (
                  <th
                    key={col.field}
                    className="px-4 py-2 text-left font-medium cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-700"
                    onClick={() => col.sortable && handleSort(col.field)}
                    style={{ width: col.width }}
                  >
                    <div className="flex items-center gap-2">
                      {col.header}
                      {sortField === col.field && (
                        <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                      )}
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {paginatedData.map((row: any, idx: number) => (
                <tr
                  key={idx}
                  className="border-t dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800"
                >
                  {component.columns.map((col: any) => (
                    <td key={col.field} className="px-4 py-2">
                      {typeof row[col.field] === 'object'
                        ? JSON.stringify(row[col.field])
                        : String(row[col.field] || '-')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {component.features?.pagination && totalPages > 1 && (
          <div className="flex items-center justify-between mt-4">
            <div className="text-sm text-gray-600">
              Showing {(currentPage - 1) * pageSize + 1} to{' '}
              {Math.min(currentPage * pageSize, sortedData.length)} of{' '}
              {sortedData.length} results
            </div>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(currentPage - 1)}
                disabled={currentPage === 1}
              >
                Previous
              </Button>
              <div className="flex items-center gap-1">
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  const page = i + 1;
                  return (
                    <Button
                      key={page}
                      variant={currentPage === page ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => setCurrentPage(page)}
                    >
                      {page}
                    </Button>
                  );
                })}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage(currentPage + 1)}
                disabled={currentPage === totalPages}
              >
                Next
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Progress Bar Component
const ProgressBar: React.FC<{ component: any }> = ({ component }) => {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{component.label}</span>
        <span className="text-sm text-gray-600">
          {component.value} / {component.max} ({component.percentage}%)
        </span>
      </div>
      <Progress value={component.percentage} className="h-2" />
    </div>
  );
};

// Stats Panel Component
const StatsPanel: React.FC<{ component: any }> = ({ component }) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{component.title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {component.metrics?.map((metric: any, idx: number) => (
            <div key={idx} className="text-center p-4 bg-gray-50 dark:bg-gray-800 rounded">
              <div className="text-2xl font-bold text-blue-600">
                {metric.format === 'number' && metric.value.toLocaleString()}
                {metric.format === 'text' && metric.value}
                {metric.format === 'percentage' && `${metric.value}%`}
              </div>
              <div className="text-xs text-gray-600 mt-1">{metric.label}</div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

// List View Component
const ListView: React.FC<{ component: any }> = ({ component }) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{component.title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-2">
          {component.items?.map((item: any) => (
            <div
              key={item.id}
              className="flex items-center justify-between p-3 border rounded hover:bg-gray-50 dark:hover:bg-gray-800 cursor-pointer"
            >
              <div className="flex-1">
                <div className="font-medium">{item.title}</div>
                {item.subtitle && (
                  <div className="text-sm text-gray-600">{item.subtitle}</div>
                )}
              </div>
              <div className="flex items-center gap-2">
                {item.value && (
                  <Badge variant="secondary">{item.value}</Badge>
                )}
                {item.badge && (
                  <Badge className={item.badgeColor === 'green' ? 'bg-green-500' : ''}>
                    {item.badge}
                  </Badge>
                )}
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
};

// Comparison Card Component
const ComparisonCard: React.FC<{ component: any }> = ({ component }) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{component.title}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {component.items?.map((item: any, idx: number) => (
            <div
              key={idx}
              className={`p-4 rounded ${
                idx === 0 ? 'bg-blue-50 dark:bg-blue-900/20' : 'bg-gray-50 dark:bg-gray-800'
              }`}
            >
              <div className="text-xs text-gray-600 mb-1">#{item.rank}</div>
              <div className="text-xl font-bold">{item.value.toLocaleString()}</div>
              <div className="text-sm mt-1">{item.label}</div>
            </div>
          ))}
        </div>
        {component.difference && (
          <div className="mt-4 p-3 bg-yellow-50 dark:bg-yellow-900/20 rounded">
            <div className="text-sm">
              <span className="font-medium">Difference:</span>{' '}
              {component.difference.value} ({component.difference.percentage.toFixed(1)}%)
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Alert Component
const AlertIndicator: React.FC<{ component: any }> = ({ component }) => {
  const severityConfig = {
    warning: { icon: AlertTriangle, className: 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20' },
    info: { icon: Info, className: 'border-blue-500 bg-blue-50 dark:bg-blue-900/20' },
    success: { icon: CheckCircle, className: 'border-green-500 bg-green-50 dark:bg-green-900/20' },
  };
  
  const config = severityConfig[component.severity as keyof typeof severityConfig] || severityConfig.info;
  const Icon = config.icon;
  
  return (
    <Alert className={`border-l-4 ${config.className}`}>
      <Icon className="h-4 w-4" />
      <AlertTitle>{component.title}</AlertTitle>
      <AlertDescription>
        {component.message}
        {component.actionable && component.action && (
          <div className="mt-2">
            <Button variant="outline" size="sm">
              {component.action}
            </Button>
          </div>
        )}
      </AlertDescription>
    </Alert>
  );
};

// Main Enhanced Dashboard Component
export const EnhancedDashboard: React.FC<EnhancedDashboardProps> = ({
  initialQuery = '',
  tenantId,
  projectId,
}) => {
  const [query, setQuery] = useState(initialQuery);
  const [dashboard, setDashboard] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!query.trim()) {
      setError('Please enter a query');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE}/generate-dashboard-enhanced`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, tenantId, projectId }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      const data = await response.json();

      if (data.success) {
        setDashboard(data);
      } else {
        setError(data.error || 'Dashboard generation failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const renderComponent = (component: any) => {
    switch (component.type) {
      case 'kpi_card':
        return <KPICard key={component.id} component={component} />;
      
      case 'data_grid':
        return <DataGrid key={component.id} component={component} />;
      
      case 'progress_bar':
        return <ProgressBar key={component.id} component={component} />;
      
      case 'stats_panel':
        return <StatsPanel key={component.id} component={component} />;
      
      case 'list_view':
        return <ListView key={component.id} component={component} />;
      
      case 'comparison_card':
        return <ComparisonCard key={component.id} component={component} />;
      
      case 'alert':
        return <AlertIndicator key={component.id} component={component} />;
      
      case 'section':
        return (
          <div key={component.id} className="space-y-4">
            <h3 className="text-xl font-semibold">{component.title}</h3>
            <div
              className={`grid gap-4 ${
                component.layout === 'grid'
                  ? `grid-cols-1 md:grid-cols-${component.columns || 3}`
                  : 'grid-cols-1'
              }`}
            >
              {component.items?.map((item: any) => renderComponent(item))}
            </div>
          </div>
        );
      
      default:
        return null;
    }
  };

  return (
    <div className="w-full space-y-6 p-6">
      {/* Query Input */}
      <Card>
        <CardHeader>
          <CardTitle>Enhanced Analytics Dashboard</CardTitle>
          <CardDescription>
            Get comprehensive insights with KPIs, metrics, data grids, and more
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder="Enter your query (e.g., show work items by priority)"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleGenerate()}
              className="flex-1"
            />
            <Button onClick={handleGenerate} disabled={loading}>
              {loading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <TrendingUp className="h-4 w-4" />
              )}
              <span className="ml-2">Generate</span>
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
          {/* Header */}
          <Card className="bg-gradient-to-r from-indigo-600 to-purple-600 text-white">
            <CardHeader>
              <CardTitle className="text-2xl">{dashboard.metadata.title}</CardTitle>
              <CardDescription className="text-indigo-100">
                {dashboard.metadata.description}
              </CardDescription>
              <div className="flex gap-4 text-sm mt-2 text-indigo-100">
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
            <Card className="border-l-4 border-purple-500">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <TrendingUp className="h-5 w-5 text-purple-500" />
                  Key Insights
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-2">
                  {dashboard.insights.map((insight: string, idx: number) => (
                    <li key={idx} className="flex items-start gap-2">
                      <span className="text-purple-500 font-bold mt-1">•</span>
                      <span className="text-gray-700 dark:text-gray-300">{insight}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          {/* Components */}
          <div className="space-y-6">
            {dashboard.components?.map((component: any) => renderComponent(component))}
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-purple-500" />
          <span className="ml-3 text-gray-600 dark:text-gray-400">
            Generating comprehensive dashboard...
          </span>
        </div>
      )}
    </div>
  );
};

export default EnhancedDashboard;
