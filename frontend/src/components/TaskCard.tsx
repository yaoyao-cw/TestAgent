import React from 'react'
import { Clock, CheckCircle, XCircle, AlertCircle, Loader2 } from 'lucide-react'
import { useTask } from '@/hooks/useTasks'
import { useTaskWebSocket } from '@/hooks/useWebSocket'
import { cn, formatDuration, getStatusColor, getStatusText } from '@/lib/utils'

interface TaskCardProps {
  taskId: string
  compact?: boolean
}

export function TaskCard({ taskId, compact = false }: TaskCardProps) {
  const { data: task, isLoading } = useTask(taskId)
  const { taskStatus, isConnected } = useTaskWebSocket(taskId)

  // 使用WebSocket状态或API状态
  const currentTask = taskStatus || task

  if (isLoading) {
    return (
      <div className="flex items-center justify-center p-4 bg-gray-50 rounded-lg">
        <Loader2 className="w-4 h-4 animate-spin mr-2" />
        <span className="text-sm text-gray-500">加载任务信息...</span>
      </div>
    )
  }

  if (!currentTask) {
    return (
      <div className="p-4 bg-gray-50 rounded-lg">
        <span className="text-sm text-gray-500">任务信息不可用</span>
      </div>
    )
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-success-600" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-error-600" />
      case 'running':
        return <Loader2 className="w-4 h-4 text-warning-600 animate-spin" />
      case 'pending':
        return <Clock className="w-4 h-4 text-gray-600" />
      default:
        return <AlertCircle className="w-4 h-4 text-gray-600" />
    }
  }

  if (compact) {
    return (
      <div className="inline-flex items-center space-x-2 px-3 py-1 bg-gray-50 rounded-full">
        {getStatusIcon(currentTask.status)}
        <span className="text-sm font-medium">
          {getStatusText(currentTask.status)}
        </span>
        {currentTask.progress && (
          <span className="text-xs text-gray-500">
            {Math.round(currentTask.progress)}%
          </span>
        )}
      </div>
    )
  }

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-sm">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-2">
          {getStatusIcon(currentTask.status)}
          <span className="font-medium text-gray-900">
            任务 {taskId.slice(-8)}
          </span>
          <span className={cn(
            "px-2 py-1 text-xs font-medium rounded-full",
            getStatusColor(currentTask.status)
          )}>
            {getStatusText(currentTask.status)}
          </span>
        </div>
        
        {isConnected && (
          <div className="flex items-center space-x-1 text-xs text-gray-500">
            <div className="w-2 h-2 bg-success-500 rounded-full" />
            <span>实时</span>
          </div>
        )}
      </div>

      {/* 进度条 */}
      {currentTask.progress !== undefined && (
        <div className="mb-3">
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-gray-600">进度</span>
            <span className="font-medium">{Math.round(currentTask.progress)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-2">
            <div
              className="bg-primary-600 h-2 rounded-full transition-all duration-300"
              style={{ width: `${currentTask.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* 当前步骤 */}
      {currentTask.current_step && (
        <div className="mb-3">
          <span className="text-sm text-gray-600">当前步骤: </span>
          <span className="text-sm font-medium text-gray-900">
            {currentTask.current_step}
          </span>
        </div>
      )}

      {/* 执行时间 */}
      {currentTask.execution_time && (
        <div className="mb-3">
          <span className="text-sm text-gray-600">执行时间: </span>
          <span className="text-sm font-medium text-gray-900">
            {formatDuration(currentTask.execution_time)}
          </span>
        </div>
      )}

      {/* 错误信息 */}
      {currentTask.error && (
        <div className="mb-3 p-3 bg-error-50 border border-error-200 rounded-lg">
          <div className="flex items-start space-x-2">
            <XCircle className="w-4 h-4 text-error-600 mt-0.5 flex-shrink-0" />
            <div>
              <div className="text-sm font-medium text-error-800 mb-1">
                执行失败
              </div>
              <div className="text-sm text-error-700">
                {currentTask.error}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 结果预览 */}
      {currentTask.result && (
        <div className="mt-3 p-3 bg-gray-50 rounded-lg">
          <div className="text-sm font-medium text-gray-900 mb-2">
            执行结果
          </div>
          <div className="text-sm text-gray-700">
            {typeof currentTask.result === 'string' 
              ? currentTask.result.slice(0, 200) + (currentTask.result.length > 200 ? '...' : '')
              : JSON.stringify(currentTask.result, null, 2).slice(0, 200) + '...'
            }
          </div>
        </div>
      )}

      {/* 操作按钮 */}
      <div className="flex items-center justify-end space-x-2 mt-4 pt-3 border-t border-gray-100">
        <button className="text-sm text-primary-600 hover:text-primary-700">
          查看详情
        </button>
        {currentTask.status === 'failed' && (
          <button className="text-sm text-warning-600 hover:text-warning-700">
            重试
          </button>
        )}
        {(currentTask.status === 'running' || currentTask.status === 'pending') && (
          <button className="text-sm text-error-600 hover:text-error-700">
            取消
          </button>
        )}
      </div>
    </div>
  )
}