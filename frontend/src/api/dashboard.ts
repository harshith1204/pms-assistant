/**
 * Dashboard API Client
 * Handles communication with dashboard generation endpoints
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:7000';

export interface DashboardQueryRequest {
  query: string;
  tenantId?: string;
  projectId?: string;
  filters?: Record<string, any>;
}

export interface ChartConfig {
  id: string;
  type: 'bar' | 'line' | 'pie' | 'doughnut' | 'table' | 'metric' | 'area' | 'scatter';
  title: string;
  description?: string;
  data: any;
  options?: any;
  gridPosition?: {
    x: number;
    y: number;
    w: number;
    h: number;
  };
}

export interface DashboardMetadata {
  title: string;
  description?: string;
  generatedFrom: string;
  dataSource: string;
  totalRecords: number;
  lastUpdated: string;
}

export interface DashboardResponse {
  metadata: DashboardMetadata;
  charts: ChartConfig[];
  rawData?: any[];
  insights?: string[];
  success: boolean;
  error?: string;
}

/**
 * Generate a dashboard from a natural language query
 */
export async function generateDashboard(
  request: DashboardQueryRequest
): Promise<DashboardResponse> {
  const response = await fetch(`${API_BASE}/generate-dashboard`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Dashboard generation failed: ${error}`);
  }

  return response.json();
}

/**
 * Generate a dashboard with AI-enhanced insights
 */
export async function generateDashboardWithAI(
  request: DashboardQueryRequest
): Promise<DashboardResponse> {
  const response = await fetch(`${API_BASE}/generate-dashboard-ai`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`AI dashboard generation failed: ${error}`);
  }

  return response.json();
}
