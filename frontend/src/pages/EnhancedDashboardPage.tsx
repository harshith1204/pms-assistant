/**
 * Enhanced Dashboard Page
 * Showcases comprehensive analytics with rich interactive components
 */
import React from 'react';
import EnhancedDashboard from '../components/EnhancedDashboard';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';

export default function EnhancedDashboardPage() {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-blue-50 dark:from-gray-900 dark:to-blue-900">
      <div className="container mx-auto">
        <div className="py-8">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-4xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent mb-2">
              Enhanced Analytics Dashboard
            </h1>
            <p className="text-gray-600 dark:text-gray-400 text-lg">
              Comprehensive business intelligence with KPIs, metrics, data grids, and actionable insights
            </p>
          </div>
          
          {/* Feature Highlights */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
            <Card className="border-t-4 border-blue-500">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">10+ Components</CardTitle>
                <CardDescription>
                  KPIs, data grids, progress bars, alerts, comparisons, and more
                </CardDescription>
              </CardHeader>
            </Card>
            
            <Card className="border-t-4 border-purple-500">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Interactive</CardTitle>
                <CardDescription>
                  Sort, filter, search, paginate - full data exploration
                </CardDescription>
              </CardHeader>
            </Card>
            
            <Card className="border-t-4 border-green-500">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Smart Insights</CardTitle>
                <CardDescription>
                  AI-powered analysis with actionable recommendations
                </CardDescription>
              </CardHeader>
            </Card>
          </div>
          
          {/* Main Dashboard */}
          <EnhancedDashboard />
          
          {/* Examples Section */}
          <div className="mt-12">
            <Card className="bg-white dark:bg-gray-800 shadow-lg">
              <CardHeader>
                <CardTitle className="text-2xl">Example Queries</CardTitle>
                <CardDescription>
                  Try these queries to see different dashboard configurations
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {/* Work Items */}
                  <div className="space-y-3">
                    <h3 className="font-semibold text-lg text-blue-600 dark:text-blue-400">
                      📋 Work Items
                    </h3>
                    <ul className="space-y-2 text-sm">
                      <li className="p-2 bg-blue-50 dark:bg-blue-900/20 rounded cursor-pointer hover:bg-blue-100 dark:hover:bg-blue-900/30">
                        show work items grouped by priority
                      </li>
                      <li className="p-2 bg-blue-50 dark:bg-blue-900/20 rounded cursor-pointer hover:bg-blue-100 dark:hover:bg-blue-900/30">
                        count work items by status
                      </li>
                      <li className="p-2 bg-blue-50 dark:bg-blue-900/20 rounded cursor-pointer hover:bg-blue-100 dark:hover:bg-blue-900/30">
                        display work items by assignee
                      </li>
                      <li className="p-2 bg-blue-50 dark:bg-blue-900/20 rounded cursor-pointer hover:bg-blue-100 dark:hover:bg-blue-900/30">
                        show bugs created this month
                      </li>
                    </ul>
                  </div>
                  
                  {/* Projects */}
                  <div className="space-y-3">
                    <h3 className="font-semibold text-lg text-purple-600 dark:text-purple-400">
                      🎯 Projects
                    </h3>
                    <ul className="space-y-2 text-sm">
                      <li className="p-2 bg-purple-50 dark:bg-purple-900/20 rounded cursor-pointer hover:bg-purple-100 dark:hover:bg-purple-900/30">
                        count projects by status
                      </li>
                      <li className="p-2 bg-purple-50 dark:bg-purple-900/20 rounded cursor-pointer hover:bg-purple-100 dark:hover:bg-purple-900/30">
                        show active projects
                      </li>
                      <li className="p-2 bg-purple-50 dark:bg-purple-900/20 rounded cursor-pointer hover:bg-purple-100 dark:hover:bg-purple-900/30">
                        list projects by business
                      </li>
                      <li className="p-2 bg-purple-50 dark:bg-purple-900/20 rounded cursor-pointer hover:bg-purple-100 dark:hover:bg-purple-900/30">
                        display project completion rates
                      </li>
                    </ul>
                  </div>
                  
                  {/* Team Analytics */}
                  <div className="space-y-3">
                    <h3 className="font-semibold text-lg text-green-600 dark:text-green-400">
                      👥 Team Analytics
                    </h3>
                    <ul className="space-y-2 text-sm">
                      <li className="p-2 bg-green-50 dark:bg-green-900/20 rounded cursor-pointer hover:bg-green-100 dark:hover:bg-green-900/30">
                        show team members by role
                      </li>
                      <li className="p-2 bg-green-50 dark:bg-green-900/20 rounded cursor-pointer hover:bg-green-100 dark:hover:bg-green-900/30">
                        count members per project
                      </li>
                      <li className="p-2 bg-green-50 dark:bg-green-900/20 rounded cursor-pointer hover:bg-green-100 dark:hover:bg-green-900/30">
                        display workload distribution
                      </li>
                      <li className="p-2 bg-green-50 dark:bg-green-900/20 rounded cursor-pointer hover:bg-green-100 dark:hover:bg-green-900/30">
                        show team performance metrics
                      </li>
                    </ul>
                  </div>
                  
                  {/* Cycles & Sprints */}
                  <div className="space-y-3">
                    <h3 className="font-semibold text-lg text-orange-600 dark:text-orange-400">
                      🔄 Cycles & Sprints
                    </h3>
                    <ul className="space-y-2 text-sm">
                      <li className="p-2 bg-orange-50 dark:bg-orange-900/20 rounded cursor-pointer hover:bg-orange-100 dark:hover:bg-orange-900/30">
                        show work items by cycle
                      </li>
                      <li className="p-2 bg-orange-50 dark:bg-orange-900/20 rounded cursor-pointer hover:bg-orange-100 dark:hover:bg-orange-900/30">
                        count active cycles
                      </li>
                      <li className="p-2 bg-orange-50 dark:bg-orange-900/20 rounded cursor-pointer hover:bg-orange-100 dark:hover:bg-orange-900/30">
                        display sprint velocity
                      </li>
                      <li className="p-2 bg-orange-50 dark:bg-orange-900/20 rounded cursor-pointer hover:bg-orange-100 dark:hover:bg-orange-900/30">
                        show cycle completion trends
                      </li>
                    </ul>
                  </div>
                  
                  {/* Modules */}
                  <div className="space-y-3">
                    <h3 className="font-semibold text-lg text-pink-600 dark:text-pink-400">
                      📦 Modules
                    </h3>
                    <ul className="space-y-2 text-sm">
                      <li className="p-2 bg-pink-50 dark:bg-pink-900/20 rounded cursor-pointer hover:bg-pink-100 dark:hover:bg-pink-900/30">
                        count work items by module
                      </li>
                      <li className="p-2 bg-pink-50 dark:bg-pink-900/20 rounded cursor-pointer hover:bg-pink-100 dark:hover:bg-pink-900/30">
                        show module progress
                      </li>
                      <li className="p-2 bg-pink-50 dark:bg-pink-900/20 rounded cursor-pointer hover:bg-pink-100 dark:hover:bg-pink-900/30">
                        list modules by project
                      </li>
                      <li className="p-2 bg-pink-50 dark:bg-pink-900/20 rounded cursor-pointer hover:bg-pink-100 dark:hover:bg-pink-900/30">
                        analyze module complexity
                      </li>
                    </ul>
                  </div>
                  
                  {/* Pages & Documentation */}
                  <div className="space-y-3">
                    <h3 className="font-semibold text-lg text-indigo-600 dark:text-indigo-400">
                      📄 Pages & Docs
                    </h3>
                    <ul className="space-y-2 text-sm">
                      <li className="p-2 bg-indigo-50 dark:bg-indigo-900/20 rounded cursor-pointer hover:bg-indigo-100 dark:hover:bg-indigo-900/30">
                        count pages by type
                      </li>
                      <li className="p-2 bg-indigo-50 dark:bg-indigo-900/20 rounded cursor-pointer hover:bg-indigo-100 dark:hover:bg-indigo-900/30">
                        show recent documentation
                      </li>
                      <li className="p-2 bg-indigo-50 dark:bg-indigo-900/20 rounded cursor-pointer hover:bg-indigo-100 dark:hover:bg-indigo-900/30">
                        list pages by visibility
                      </li>
                      <li className="p-2 bg-indigo-50 dark:bg-indigo-900/20 rounded cursor-pointer hover:bg-indigo-100 dark:hover:bg-indigo-900/30">
                        display page engagement
                      </li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
          
          {/* Feature Comparison */}
          <div className="mt-12 mb-8">
            <Card className="bg-gradient-to-r from-blue-600 to-purple-600 text-white">
              <CardHeader>
                <CardTitle className="text-2xl">Why Enhanced Dashboard?</CardTitle>
                <CardDescription className="text-blue-100">
                  More than just charts - a complete business intelligence solution
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-3">
                    <h4 className="font-semibold text-lg">Traditional Charts</h4>
                    <ul className="space-y-1 text-sm text-blue-100">
                      <li>• Basic visualizations</li>
                      <li>• Static displays</li>
                      <li>• Limited interaction</li>
                      <li>• Manual interpretation</li>
                    </ul>
                  </div>
                  <div className="space-y-3">
                    <h4 className="font-semibold text-lg">Enhanced Dashboard ⭐</h4>
                    <ul className="space-y-1 text-sm text-blue-100">
                      <li>✓ 10+ interactive components</li>
                      <li>✓ Real-time filtering & sorting</li>
                      <li>✓ Smart alerts & recommendations</li>
                      <li>✓ AI-powered insights</li>
                      <li>✓ Full data grid with export</li>
                      <li>✓ KPIs with trend indicators</li>
                      <li>✓ Progress metrics & comparisons</li>
                    </ul>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
