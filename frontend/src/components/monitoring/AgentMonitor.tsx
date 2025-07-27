import React from 'react'
import { 
  User, 
  Clock, 
  CheckCircle, 
  XCircle, 
  Loader2, 
  Pause,
  Activity,
  TrendingUp,
  AlertTriangle
} from 'lucide-react'
import { cn, formatDuration, formatRelativeTime } from '@/lib/utils'
import type { AgentMetrics } from '@/types'

interface AgentMonitorProps {
  agents: AgentMetrics[]
  className?: string
}

interface AgentCardProps {
  agent: AgentMetrics
}

function AgentCard({ agent }: AgentCardProps) {
  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'running':
        return <Loader2 className="w-4 h-4 text-blue-600 animate-spin" />
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-green-600" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-red-600" />
      case 'idle':
        return <Pause className="w-4 h-4 text-gray-600" />
      default:
        return <Activity className="w-4 h-4 text-gray-600" />
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running':
        return 'bg-blue-50 border-blue-200'
      case 'completed':
        return 'bg-green-50 border-green-200'
      case 'failed':
        return 'bg-red-50 border-red-200'
      case 'idle':
        return 'bg-gray-50 border-gray-200'
      default:
        return 'bg-gray-50 border-gray-200'
    }
  }

  const getSuccessRateColor = (rate: number) => {
    if (rate >= 95) return 'text-green-600'
    if (rate >= 85) return 'text-yellow-600'
    return 'text-red-600'
  }

  return (
    <div className={cn(
      "bg-white border rounded-lg p-4 hover:shadow-md transition-shadow",
      getStatusColor(agent.current_status)
    )}>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <User className="w-5 h-5 text-gray-600" />
          <h3 className="font-medium text-gray-900">{agent.agent_name}</h3>
        </div>
        <div className="flex items-center space-x-2">
          {getStatusIcon(agent.current_status)}
          <span className="text-sm text-gray-600 capitalize">
            {agent.current_status}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-3">
        <div>
          <div className="text-xs text-gray-500 mb-1">总执行次数</div>
          <div className="text-lg font-semibold text-gray-900">
            {agent.total_executions.toLocaleString()}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500 mb-1">成功率</div>
          <div className={cn(
            "text-lg font-semibold",
            getSuccessRateColor(agent.success_rate)
          )}>
            {agent.success_rate.toFixed(1)}%
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 mb-3">
        <div>
          <div className="text-xs text-gray-500 mb-1">平均执行时间</div>
          <div className="text-sm font-medium text-gray-900">
            {formatDuration(agent.average_execution_time)}
          </div>
        </div>
        <div>
          <div className="text-xs text-gray-500 mb-1">最后执行</div>
          <div className="text-sm font-medium text-gray-900">
            {formatRelativeTime(agent.last_execution)}
          </div>
        </div>
      </div>

      {/* 性能指标条 */}
      <div className="space-y-2">
        <div>
          <div className="flex items-center justify-between text-xs mb-1">
            <span className="text-gray-500">成功率</span>
            <span className="font-medium">{agent.success_rate.toFixed(1)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-1.5">
            <div
              className={cn(
                "h-1.5 rounded-full transition-all duration-300",
                agent.success_rate >= 95 ? "bg-green-500" :
                agent.success_rate >= 85 ? "bg-yellow-500" : "bg-red-500"
              )}
              style={{ width: `${agent.success_rate}%` }}
            />
          </div>
        </div>
      </div>

      {/* 警告指示器 */}
      {agent.success_rate < 85 && (
        <div className="mt-3 flex items-center space-x-2 text-xs text-yellow-600 bg-yellow-50 rounded-lg p-2">
          <AlertTriangle className="w-3 h-3" />
          <span>成功率偏低，需要关注</span>
        </div>
      )}
    </div>
  )
}

export function AgentMonitor({ agents, className }: AgentMonitorProps) {
  const totalExecutions = agents.reduce((sum, agent) => sum + agent.total_executions, 0)
  const averageSuccessRate = agents.length > 0 
    ? agents.reduce((sum, agent) => sum + agent.success_rate, 0) / agents.length 
    : 0
  const runningAgents = agents.filter(agent => agent.current_status === 'running').length

  if (agents.length === 0) {
    return (
      <div className={cn("bg-white border border-gray-200 rounded-lg p-6", className)}>
        <div className="text-center">
          <User className="w-8 h-8 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500">暂无智能体数据</p>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("bg-white border border-gray-200 rounded-lg", className)}>
      {/* 头部统计 */}
      <div className="border-b border-gray-200 p-4">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-gray-900">智能体监控</h2>
          <div className="flex items-center space-x-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
            <span className="text-sm text-gray-600">实时监控</span>
          </div>
        </div>

        <div className="grid grid-cols-4 gap-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900">{agents.length}</div>
            <div className="text-xs text-gray-500">总智能体数</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-blue-600">{runningAgents}</div>
            <div className="text-xs text-gray-500">运行中</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-900">
              {totalExecutions.toLocaleString()}
            </div>
            <div className="text-xs text-gray-500">总执行次数</div>
          </div>
          <div className="text-center">
            <div className={cn(
              "text-2xl font-bold",
              averageSuccessRate >= 95 ? "text-green-600" :
              averageSuccessRate >= 85 ? "text-yellow-600" : "text-red-600"
            )}>
              {averageSuccessRate.toFixed(1)}%
            </div>
            <div className="text-xs text-gray-500">平均成功率</div>
          </div>
        </div>
      </div>

      {/* 智能体列表 */}
      <div className="p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map((agent) => (
            <AgentCard key={agent.agent_name} agent={agent} />
          ))}
        </div>
      </div>
    </div>
  )
}