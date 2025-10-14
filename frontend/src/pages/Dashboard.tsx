/**
 * Dashboard Page
 * Main page for viewing and interacting with analytics dashboards
 */
import React from 'react';
import DashboardViewer from '../components/DashboardViewer';

export default function Dashboard() {
  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <div className="container mx-auto">
        <div className="py-8">
          <h1 className="text-4xl font-bold text-gray-900 dark:text-gray-100 mb-2">
            Analytics Dashboard
          </h1>
          <p className="text-gray-600 dark:text-gray-400 mb-8">
            Generate interactive dashboards from natural language queries
          </p>
          
          <DashboardViewer />
          
          {/* Example Queries */}
          <div className="mt-12 p-6 bg-white dark:bg-gray-800 rounded-lg shadow">
            <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-gray-100">
              Example Queries
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <h3 className="font-medium text-gray-700 dark:text-gray-300">Work Items</h3>
                <ul className="text-sm space-y-1 text-gray-600 dark:text-gray-400">
                  <li>• Show work items grouped by priority</li>
                  <li>• Count work items by status</li>
                  <li>• Display work items by assignee</li>
                  <li>• Show bugs created this month</li>
                </ul>
              </div>
              
              <div className="space-y-2">
                <h3 className="font-medium text-gray-700 dark:text-gray-300">Projects</h3>
                <ul className="text-sm space-y-1 text-gray-600 dark:text-gray-400">
                  <li>• Count projects by status</li>
                  <li>• Show active projects</li>
                  <li>• List projects by team</li>
                  <li>• Display project completion rates</li>
                </ul>
              </div>
              
              <div className="space-y-2">
                <h3 className="font-medium text-gray-700 dark:text-gray-300">Team</h3>
                <ul className="text-sm space-y-1 text-gray-600 dark:text-gray-400">
                  <li>• Show team members by role</li>
                  <li>• Count members per project</li>
                  <li>• Display workload by assignee</li>
                  <li>• List active team members</li>
                </ul>
              </div>
              
              <div className="space-y-2">
                <h3 className="font-medium text-gray-700 dark:text-gray-300">Analytics</h3>
                <ul className="text-sm space-y-1 text-gray-600 dark:text-gray-400">
                  <li>• Show completion trends over time</li>
                  <li>• Count work items by cycle</li>
                  <li>• Display sprint velocity</li>
                  <li>• Analyze bug density by module</li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
