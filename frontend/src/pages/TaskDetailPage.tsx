import React, { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { 
  ArrowLeft, 
  RefreshCw, 
  Play, 
  Square, 
  RotateCcw,
  FolderOpen,
  BarChart3,
  FileText,
  Clock
} from 'lucide-react'
import { useTask, useCancelTask, useRetryTask } from '@/hooks/useTasks'
import { WorkspaceViewer } from '@/components/workspace'
import { TaskCard } from '@/components/TaskCard'
import { cn, formatDate, formatDuration, getStatusColor, getStatusText } from '@/lib/utils'

export function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<'overview' | 'workspace' | 'logs'>('overview')
  
  const { data: task, isLoading, refetch } = useTask(taskId!)
  const cancelTaskMutation = useCancelTask()
  const retryTaskMutation = useRetryTask()

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <RefreshCw className="w-8 h-8 animate-spin text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500">加载任务详情...</p>
        </div>
      </div>
    )
  }

  if (!task) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <FileText className="w-8 h-8 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-500">任务不存在</p>
          <button
            onClick={() => navigate('/tasks')}
            className="mt-4 btn btn-primary"
          >
            返回任务列表
          </button>
        </div>
      </div>
    )
  }

  const handleCancelTask = () => {
    if (confirm('确定要取消这个任务吗？')) {
      cancelTaskMutation.mutate(taskId!)
    }
  }

  const handleRetryTask = () => {
    if (confirm('确定要重试这个任务吗？')) {
      retryTaskMutation.mutate(taskId!)
    }
  }

  const getActionButtons = () => {
    const buttons = []

    if (task.status === 'running' || task.status === 'pending') {
      buttons.push(
        <button
          key="cancel"
          onClick={handleCancelTask}
          className="btn btn-ghost text-error-600 hover:text-error-700"
          disabled={cancelTaskMutation.isPending}
        >
          <Square className="w-4 h-4 mr-2" />
          取消任务
        </button>
      )
    }

    if (task.status === 'failed') {
      buttons.push(
        <button
          key="retry"
          onClick={handleRetryTask}
          className="btn btn-ghost text-warning-600 hover:text-warning-700"
          disabled={retryTaskMutation.isPending}
        >
          <RotateCcw className="w-4 h-4 mr-2" />
          重试任务
        </button>
      )
    }

    return buttons
  }

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* 页面头部 */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <button
              onClick={() => navigate('/tasks')}
              className="btn btn-ghost btn-sm"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              返回
            </button>
            
            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {task.task_topic || `任务 ${taskId?.slice(-8)}`}
              </h1>
              <div className="flex items-center space-x-4 text-sm text-gray-500 mt-1">
                <span>ID: {taskId}</span>
                <span>创建时间: {formatDate(task.created_at)}</span>
                {task.execution_time && (
                  <span>执行时间: {formatDuration(task.execution_time)}</span>
                )}
              </div>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <span className={cn(
              "px-3 py-1 text-sm font-medium rounded-full",
              getStatusColor(task.status)
            )}>
              {getStatusText(task.status)}
            </span>
            
            <button
              onClick={() => refetch()}
              className="btn btn-ghost btn-sm"
              disabled={isLoading}
            >
              <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
            </button>

            {getActionButtons()}
          </div>
        </div>

        {/* 标签页导航 */}
        <div className="flex items-center space-x-1 mt-6 bg-gray-100 rounded-lg p-1 w-fit">
          <button
            onClick={() => setActiveTab('overview')}
            className={cn(
              "flex items-center space-x-2 px-4 py-2 text-sm font-medium rounded-md transition-colors",
              activeTab === 'overview'
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            )}
          >
            <BarChart3 className="w-4 h-4" />
            <span>概览</span>
          </button>
          <button
            onClick={() => setActiveTab('workspace')}
            className={cn(
              "flex items-center space-x-2 px-4 py-2 text-sm font-medium rounded-md transition-colors",
              activeTab === 'workspace'
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            )}
          >
            <FolderOpen className="w-4 h-4" />
            <span>工作空间</span>
          </button>
          <button
            onClick={() => setActiveTab('logs')}
            className={cn(
              "flex items-center space-x-2 px-4 py-2 text-sm font-medium rounded-md transition-colors",
              activeTab === 'logs'
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-600 hover:text-gray-900"
            )}
          >
            <FileText className="w-4 h-4" />
            <span>日志</span>
          </button>
        </div>
      </div>

      {/* 内容区域 */}
      <div className="flex-1 p-6 overflow-y-auto">
        {activeTab === 'overview' && (
          <div className="space-y-6">
            {/* 任务状态卡片 */}
            <TaskCard taskId={taskId!} />

            {/* 任务详细信息 */}
            <div className="bg-white border border-gray-200 rounded-lg p-6">
              <h3 className="text-lg font-medium text-gray-900 mb-4">任务详情</h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">基本信息</h4>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between">
                      <span className="text-gray-500">任务类型:</span>
                      <span className="text-gray-900">{task.task_type || '未指定'}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">当前状态:</span>
                      <span className={cn(
                        "font-medium",
                        task.status === 'completed' ? 'text-green-600' :
                        task.status === 'failed' ? 'text-red-600' :
                        task.status === 'running' ? 'text-blue-600' : 'text-gray-600'
                      )}>
                        {getStatusText(task.status)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">创建时间:</span>
                      <span className="text-gray-900">{formatDate(task.created_at)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">更新时间:</span>
                      <span className="text-gray-900">{formatDate(task.updated_at)}</span>
                    </div>
                  </div>
                </div>

                <div>
                  <h4 className="text-sm font-medium text-gray-700 mb-2">执行信息</h4>
                  <div className="space-y-2 text-sm">
                    {task.progress !== undefined && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">进度:</span>
                        <span className="text-gray-900">{Math.round(task.progress)}%</span>
                      </div>
                    )}
                    {task.current_step && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">当前步骤:</span>
                        <span className="text-gray-900">{task.current_step}</span>
                      </div>
                    )}
                    {task.execution_time && (
                      <div className="flex justify-between">
                        <span className="text-gray-500">执行时间:</span>
                        <span className="text-gray-900">{formatDuration(task.execution_time)}</span>
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* 错误信息 */}
              {task.error && (
                <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg">
                  <h4 className="text-sm font-medium text-red-800 mb-2">错误信息</h4>
                  <pre className="text-sm text-red-700 whitespace-pre-wrap">{task.error}</pre>
                </div>
              )}

              {/* 执行结果 */}
              {task.result && (
                <div className="mt-6 p-4 bg-gray-50 border border-gray-200 rounded-lg">
                  <h4 className="text-sm font-medium text-gray-800 mb-2">执行结果</h4>
                  <pre className="text-sm text-gray-700 whitespace-pre-wrap max-h-64 overflow-y-auto">
                    {typeof task.result === 'string' 
                      ? task.result 
                      : JSON.stringify(task.result, null, 2)
                    }
                  </pre>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'workspace' && (
          <WorkspaceViewer taskId={taskId!} />
        )}

        {activeTab === 'logs' && (
          <div className="bg-white border border-gray-200 rounded-lg p-6">
            <h3 className="text-lg font-medium text-gray-900 mb-4">执行日志</h3>
            
            {task.logs && task.logs.length > 0 ? (
              <div className="bg-gray-900 text-gray-100 p-4 rounded-lg font-mono text-sm max-h-96 overflow-y-auto">
                {task.logs.map((log, index) => (
                  <div key={index} className="mb-1">
                    {log}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <FileText className="w-8 h-8 text-gray-400 mx-auto mb-2" />
                <p className="text-gray-500">暂无日志信息</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}