import React, { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { 
  RefreshCw, 
  Settings, 
  Download, 
  Maximize2, 
  Minimize2,
  Activity,
  Server,
  Users,
  AlertTriangle
} from 'lucide-react'
import { 
  MetricsCard,
  KVCacheHitRateCard,
  ResponseTimeCard,
  ErrorRateCard,
  ActiveConnectionsCard
} from './MetricsCard'
import { 
  RealtimeChart,
  KVCacheChart,
  ResponseTimeChart,
  ErrorRateChart,
  MemoryUsageChart
} from './RealtimeChart'
import { AgentMonitor } from './AgentMonitor'
import { AlertSystem, type Alert } from './AlertSystem'
import { apiClient } from '@/lib/api'
import { useWebSocket } from '@/hooks/useWebSocket'
import { cn } from '@/lib/utils'
import type { SystemMetrics, PerformanceMetrics, AgentMetrics } from '@/types'
import toast from 'react-hot-toast'

interface MonitoringDashboardProps {
  className?: string
}

export function MonitoringDashboard({ className }: MonitoringDashboardProps) {
  const [isFullscreen, setIsFullscreen] = useState(false)
  const [refreshInterval, setRefreshInterval] = useState(5000) // 5秒
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [metricsHistory, setMetricsHistory] = useState<{
    kvCache: any[]
    responseTime: any[]
    errorRate: any[]
    memoryUsage: any[]
  }>({
    kvCache: [],
    responseTime: [],
    errorRate: [],
    memoryUsage: []
  })

  // 获取系统指标
  const { 
    data: systemMetrics, 
    isLoading, 
    refetch: refetchMetrics 
  } = useQuery<SystemMetrics>({
    queryKey: ['system-metrics'],
    queryFn: async () => {
      const response = await apiClient.getSystemMetrics()
      return response.data
    },
    refetchInterval: refreshInterval,
  })

  // WebSocket连接用于实时数据
  const { isConnected, sendMessage } = useWebSocket({
    onMessage: (message) => {
      if (message.type === 'metrics_update') {
        handleMetricsUpdate(message.data)
      } else if (message.type === 'alert') {
        handleNewAlert(message.data)
      }
    },
    onConnect: () => {
      // 订阅指标更新
      sendMessage({
        type: 'subscribe_metrics',
        interval: refreshInterval
      })
    }
  })

  // 处理指标更新
  const handleMetricsUpdate = (metrics: SystemMetrics) => {
    const timestamp = new Date().toISOString()
    
    setMetricsHistory(prev => ({
      kvCache: [...prev.kvCache.slice(-49), {
        timestamp,
        value: metrics.performance.kv_cache_hit_rate
      }],
      responseTime: [...prev.responseTime.slice(-49), {
        timestamp,
        value: metrics.performance.average_response_time
      }],
      errorRate: [...prev.errorRate.slice(-49), {
        timestamp,
        value: metrics.performance.error_rate
      }],
      memoryUsage: [...prev.memoryUsage.slice(-49), {
        timestamp,
        value: metrics.performance.memory_usage
      }]
    }))

    // 检查告警条件
    checkAlertConditions(metrics)
  }

  // 处理新告警
  const handleNewAlert = (alert: Alert) => {
    setAlerts(prev => [alert, ...prev.slice(0, 99)]) // 保持最多100个告警
    
    // 显示toast通知
    switch (alert.type) {
      case 'error':
        toast.error(alert.title)
        break
      case 'warning':
        toast(alert.title, { icon: '⚠️' })
        break
      case 'success':
        toast.success(alert.title)
        break
      default:
        toast(alert.title, { icon: 'ℹ️' })
    }
  }

  // 检查告警条件
  const checkAlertConditions = (metrics: SystemMetrics) => {
    const { performance, agents } = metrics
    const now = new Date().toISOString()

    // KV缓存命中率过低
    if (performance.kv_cache_hit_rate < 80) {
      const alert: Alert = {
        id: `kv-cache-${Date.now()}`,
        type: 'warning',
        title: 'KV缓存命中率过低',
        message: `当前命中率为 ${performance.kv_cache_hit_rate.toFixed(1)}%，建议检查缓存配置`,
        timestamp: now,
        source: 'performance-monitor',
        auto_dismiss: true,
        dismiss_after: 30
      }
      handleNewAlert(alert)
    }

    // 错误率过高
    if (performance.error_rate > 5) {
      const alert: Alert = {
        id: `error-rate-${Date.now()}`,
        type: 'error',
        title: '系统错误率过高',
        message: `当前错误率为 ${performance.error_rate.toFixed(2)}%，需要立即处理`,
        timestamp: now,
        source: 'error-monitor'
      }
      handleNewAlert(alert)
    }

    // 响应时间过长
    if (performance.average_response_time > 5000) {
      const alert: Alert = {
        id: `response-time-${Date.now()}`,
        type: 'warning',
        title: '响应时间过长',
        message: `平均响应时间为 ${performance.average_response_time.toFixed(0)}ms，可能影响用户体验`,
        timestamp: now,
        source: 'performance-monitor',
        auto_dismiss: true,
        dismiss_after: 60
      }
      handleNewAlert(alert)
    }

    // 智能体成功率过低
    agents.forEach(agent => {
      if (agent.success_rate < 85) {
        const alert: Alert = {
          id: `agent-${agent.agent_name}-${Date.now()}`,
          type: 'warning',
          title: `智能体 ${agent.agent_name} 成功率过低`,
          message: `成功率为 ${agent.success_rate.toFixed(1)}%，建议检查智能体配置`,
          timestamp: now,
          source: agent.agent_name
        }
        handleNewAlert(alert)
      }
    })
  }

  // 确认告警
  const handleAcknowledgeAlert = (alertId: string) => {
    setAlerts(prev => prev.map(alert => 
      alert.id === alertId ? { ...alert, acknowledged: true } : alert
    ))
  }

  // 删除告警
  const handleDismissAlert = (alertId: string) => {
    setAlerts(prev => prev.filter(alert => alert.id !== alertId))
  }

  // 导出监控数据
  const handleExportData = () => {
    const data = {
      timestamp: new Date().toISOString(),
      metrics: systemMetrics,
      history: metricsHistory,
      alerts: alerts
    }
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `monitoring-data-${new Date().toISOString().split('T')[0]}.json`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    
    toast.success('监控数据导出成功')
  }

  if (isLoading && !systemMetrics) {
    return (
      <div className={cn("flex items-center justify-center h-64", className)}>
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500">加载监控数据...</p>
        </div>
      </div>
    )
  }

  const performance = systemMetrics?.performance
  const agents = systemMetrics?.agents || []

  return (
    <div className={cn(
      "space-y-6",
      isFullscreen && "fixed inset-4 z-50 bg-white p-6 overflow-y-auto",
      className
    )}>
      {/* 头部控制栏 */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <h1 className="text-2xl font-bold text-gray-900">实时监控仪表板</h1>
          <div className="flex items-center space-x-2">
            <div className={cn(
              "w-2 h-2 rounded-full",
              isConnected ? "bg-green-500 animate-pulse" : "bg-red-500"
            )} />
            <span className="text-sm text-gray-600">
              {isConnected ? '实时连接' : '连接断开'}
            </span>
          </div>
        </div>

        <div className="flex items-center space-x-2">
          <select
            value={refreshInterval}
            onChange={(e) => setRefreshInterval(Number(e.target.value))}
            className="text-sm border border-gray-300 rounded px-3 py-1"
          >
            <option value={1000}>1秒</option>
            <option value={5000}>5秒</option>
            <option value={10000}>10秒</option>
            <option value={30000}>30秒</option>
          </select>

          <button
            onClick={refetchMetrics}
            className="btn btn-ghost btn-sm"
            disabled={isLoading}
          >
            <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
          </button>

          <button
            onClick={handleExportData}
            className="btn btn-ghost btn-sm"
          >
            <Download className="w-4 h-4" />
          </button>

          <button
            onClick={() => setIsFullscreen(!isFullscreen)}
            className="btn btn-ghost btn-sm"
          >
            {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* 关键指标卡片 */}
      {performance && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <KVCacheHitRateCard value={performance.kv_cache_hit_rate} />
          <ResponseTimeCard value={performance.average_response_time} />
          <ErrorRateCard value={performance.error_rate} />
          <ActiveConnectionsCard value={performance.active_connections} />
        </div>
      )}

      {/* 实时图表 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <KVCacheChart data={metricsHistory.kvCache} />
        <ResponseTimeChart data={metricsHistory.responseTime} />
        <ErrorRateChart data={metricsHistory.errorRate} />
        <MemoryUsageChart data={metricsHistory.memoryUsage} />
      </div>

      {/* 智能体监控 */}
      <AgentMonitor agents={agents} />

      {/* 告警系统 */}
      <AlertSystem
        alerts={alerts}
        onAcknowledge={handleAcknowledgeAlert}
        onDismiss={handleDismissAlert}
        maxVisible={10}
      />
    </div>
  )
}