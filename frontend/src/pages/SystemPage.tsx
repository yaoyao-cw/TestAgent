import React from 'react'
import { Activity, Cpu, HardDrive, Wifi, Users, Clock } from 'lucide-react'
import { useSystemStatus, useSystemMetrics } from '@/hooks/useSystemStatus'
import { formatDuration, cn } from '@/lib/utils'

export function SystemPage() {
  const { data: systemStatus, isLoading } = useSystemStatus()
  const { data: metrics } = useSystemMetrics(24)

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
        return 'text-success-600 bg-success-50'
      case 'degraded':
        return 'text-warning-600 bg-warning-50'
      case 'unhealthy':
        return 'text-error-600 bg-error-50'
      default:
        return 'text-gray-600 bg-gray-50'
    }
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <Activity className="w-8 h-8 animate-pulse text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500">加载系统状态...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 bg-gray-50 min-h-full">
      <div className="max-w-7xl mx-auto">
        {/* 页面头部 */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-gray-900 mb-2">系统监控</h1>
          <p className="text-gray-600">
            实时监控TestAgent系统的运行状态和性能指标
          </p>
        </div>

        {/* 系统概览 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">系统状态</p>
                <div className="flex items-center space-x-2 mt-2">
                  <span className={cn(
                    "px-2 py-1 text-xs font-medium rounded-full",
                    getStatusColor(systemStatus?.system.status || 'unknown')
                  )}>
                    {systemStatus?.system.status || '未知'}
                  </span>
                </div>
              </div>
              <Activity className="w-8 h-8 text-primary-600" />
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">运行时间</p>
                <p className="text-2xl font-bold text-gray-900 mt-2">
                  {systemStatus ? formatDuration(systemStatus.system.uptime) : '--'}
                </p>
              </div>
              <Clock className="w-8 h-8 text-primary-600" />
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">活跃任务</p>
                <p className="text-2xl font-bold text-gray-900 mt-2">
                  {systemStatus?.execution_stats.running_tasks || 0}
                </p>
              </div>
              <Users className="w-8 h-8 text-primary-600" />
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-gray-600">总任务数</p>
                <p className="text-2xl font-bold text-gray-900 mt-2">
                  {systemStatus?.execution_stats.total_tasks || 0}
                </p>
              </div>
              <Activity className="w-8 h-8 text-primary-600" />
            </div>
          </div>
        </div>

        {/* 资源使用情况 */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">资源使用</h3>
            
            <div className="space-y-4">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <Cpu className="w-4 h-4 text-gray-500" />
                    <span className="text-sm font-medium text-gray-700">CPU</span>
                  </div>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus?.resources.cpu_usage.toFixed(1)}%
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-primary-600 h-2 rounded-full"
                    style={{ width: `${systemStatus?.resources.cpu_usage || 0}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <HardDrive className="w-4 h-4 text-gray-500" />
                    <span className="text-sm font-medium text-gray-700">内存</span>
                  </div>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus?.resources.memory_usage.toFixed(1)}%
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-warning-500 h-2 rounded-full"
                    style={{ width: `${systemStatus?.resources.memory_usage || 0}%` }}
                  />
                </div>
              </div>

              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center space-x-2">
                    <HardDrive className="w-4 h-4 text-gray-500" />
                    <span className="text-sm font-medium text-gray-700">磁盘</span>
                  </div>
                  <span className="text-sm font-medium text-gray-900">
                    {systemStatus?.resources.disk_usage.toFixed(1)}%
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-success-500 h-2 rounded-full"
                    style={{ width: `${systemStatus?.resources.disk_usage || 0}%` }}
                  />
                </div>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">执行统计</h3>
            
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">已完成任务</span>
                <span className="text-sm font-medium text-success-600">
                  {systemStatus?.execution_stats.completed_tasks || 0}
                </span>
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">失败任务</span>
                <span className="text-sm font-medium text-error-600">
                  {systemStatus?.execution_stats.failed_tasks || 0}
                </span>
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">等待任务</span>
                <span className="text-sm font-medium text-warning-600">
                  {systemStatus?.execution_stats.pending_tasks || 0}
                </span>
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">平均执行时间</span>
                <span className="text-sm font-medium text-gray-900">
                  {systemStatus ? formatDuration(systemStatus.execution_stats.average_execution_time) : '--'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* 组件状态 */}
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-medium text-gray-900 mb-4">组件状态</h3>
          
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {systemStatus?.components.map((component, index) => (
              <div
                key={index}
                className="border border-gray-200 rounded-lg p-4"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-gray-900">
                    {component.name}
                  </span>
                  <div className={cn(
                    "w-3 h-3 rounded-full",
                    component.healthy ? "bg-success-500" : "bg-error-500"
                  )} />
                </div>
                
                <div className="text-sm text-gray-600">
                  状态: {component.status}
                </div>
                
                <div className="text-xs text-gray-500 mt-1">
                  最后检查: {new Date(component.last_check).toLocaleTimeString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}