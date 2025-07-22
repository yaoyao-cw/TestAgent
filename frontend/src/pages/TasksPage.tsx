import React, { useState } from 'react'
import { Plus, Search, Filter, RefreshCw, Play, Square, RotateCcw } from 'lucide-react'
import { useTasks, useCancelTask, useRetryTask } from '@/hooks/useTasks'
import { cn, formatDate, formatDuration, getStatusColor, getStatusText } from '@/lib/utils'
import type { Task } from '@/types'

const STATUS_OPTIONS = [
  { value: '', label: '全部状态' },
  { value: 'pending', label: '等待中' },
  { value: 'running', label: '运行中' },
  { value: 'completed', label: '已完成' },
  { value: 'failed', label: '失败' },
  { value: 'cancelled', label: '已取消' },
]

const TASK_TYPE_OPTIONS = [
  { value: '', label: '全部类型' },
  { value: 'test_case_generation', label: '测试用例生成' },
  { value: 'test_analysis', label: '测试分析' },
  { value: 'code_review', label: '代码审查' },
  { value: 'bug_analysis', label: 'Bug分析' },
]

export function TasksPage() {
  const [filters, setFilters] = useState({
    status: '',
    task_type: '',
    search: '',
    page: 1,
    page_size: 20,
  })
  
  const { data: tasksData, isLoading, refetch } = useTasks(filters)
  const cancelTaskMutation = useCancelTask()
  const retryTaskMutation = useRetryTask()

  const handleFilterChange = (key: string, value: any) => {
    setFilters(prev => ({
      ...prev,
      [key]: value,
      page: 1, // 重置页码
    }))
  }

  const handleCancelTask = (taskId: string) => {
    if (confirm('确定要取消这个任务吗？')) {
      cancelTaskMutation.mutate(taskId)
    }
  }

  const handleRetryTask = (taskId: string) => {
    if (confirm('确定要重试这个任务吗？')) {
      retryTaskMutation.mutate(taskId)
    }
  }

  const getActionButtons = (task: Task) => {
    const buttons = []

    if (task.status === 'running' || task.status === 'pending') {
      buttons.push(
        <button
          key="cancel"
          onClick={() => handleCancelTask(task.task_id)}
          className="btn btn-ghost btn-sm text-error-600 hover:text-error-700"
          disabled={cancelTaskMutation.isPending}
        >
          <Square className="w-3 h-3 mr-1" />
          取消
        </button>
      )
    }

    if (task.status === 'failed') {
      buttons.push(
        <button
          key="retry"
          onClick={() => handleRetryTask(task.task_id)}
          className="btn btn-ghost btn-sm text-warning-600 hover:text-warning-700"
          disabled={retryTaskMutation.isPending}
        >
          <RotateCcw className="w-3 h-3 mr-1" />
          重试
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
          <div>
            <h1 className="text-2xl font-bold text-gray-900">任务管理</h1>
            <p className="text-gray-600 mt-1">
              管理和监控所有测试任务的执行状态
            </p>
          </div>
          <div className="flex items-center space-x-3">
            <button
              onClick={() => refetch()}
              className="btn btn-ghost btn-sm"
              disabled={isLoading}
            >
              <RefreshCw className={cn("w-4 h-4", isLoading && "animate-spin")} />
              刷新
            </button>
            <button className="btn btn-primary">
              <Plus className="w-4 h-4 mr-2" />
              新建任务
            </button>
          </div>
        </div>
      </div>

      {/* 过滤器 */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center space-x-4">
          {/* 搜索框 */}
          <div className="flex-1 max-w-md">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="搜索任务..."
                value={filters.search}
                onChange={(e) => handleFilterChange('search', e.target.value)}
                className="input pl-10"
              />
            </div>
          </div>

          {/* 状态过滤 */}
          <select
            value={filters.status}
            onChange={(e) => handleFilterChange('status', e.target.value)}
            className="input w-32"
          >
            {STATUS_OPTIONS.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>

          {/* 类型过滤 */}
          <select
            value={filters.task_type}
            onChange={(e) => handleFilterChange('task_type', e.target.value)}
            className="input w-40"
          >
            {TASK_TYPE_OPTIONS.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* 任务列表 */}
      <div className="flex-1 overflow-y-auto p-6">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <div className="text-center">
              <RefreshCw className="w-8 h-8 animate-spin text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500">加载任务列表...</p>
            </div>
          </div>
        ) : tasksData?.tasks.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-gray-400 mb-4">
              <Play className="w-16 h-16 mx-auto" />
            </div>
            <h3 className="text-lg font-medium text-gray-900 mb-2">
              暂无任务
            </h3>
            <p className="text-gray-500 mb-6">
              还没有创建任何任务，点击"新建任务"开始
            </p>
            <button className="btn btn-primary">
              <Plus className="w-4 h-4 mr-2" />
              新建任务
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {tasksData?.tasks.map((task) => (
              <div
                key={task.task_id}
                className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md transition-shadow"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-3 mb-2">
                      <h3 className="text-lg font-medium text-gray-900">
                        {task.task_topic || `任务 ${task.task_id.slice(-8)}`}
                      </h3>
                      <span className={cn(
                        "px-2 py-1 text-xs font-medium rounded-full",
                        getStatusColor(task.status)
                      )}>
                        {getStatusText(task.status)}
                      </span>
                      {task.task_type && (
                        <span className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded-full">
                          {TASK_TYPE_OPTIONS.find(t => t.value === task.task_type)?.label || task.task_type}
                        </span>
                      )}
                    </div>

                    <div className="flex items-center space-x-6 text-sm text-gray-500 mb-3">
                      <span>ID: {task.task_id}</span>
                      <span>创建时间: {formatDate(task.created_at)}</span>
                      {task.execution_time && (
                        <span>执行时间: {formatDuration(task.execution_time)}</span>
                      )}
                    </div>

                    {/* 进度条 */}
                    {task.progress !== undefined && (
                      <div className="mb-3">
                        <div className="flex items-center justify-between text-sm mb-1">
                          <span className="text-gray-600">进度</span>
                          <span className="font-medium">{Math.round(task.progress)}%</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-2">
                          <div
                            className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                            style={{ width: `${task.progress}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {/* 当前步骤 */}
                    {task.current_step && (
                      <div className="mb-3">
                        <span className="text-sm text-gray-600">当前步骤: </span>
                        <span className="text-sm font-medium text-gray-900">
                          {task.current_step}
                        </span>
                      </div>
                    )}

                    {/* 错误信息 */}
                    {task.error && (
                      <div className="mb-3 p-3 bg-error-50 border border-error-200 rounded-lg">
                        <div className="text-sm font-medium text-error-800 mb-1">
                          执行失败
                        </div>
                        <div className="text-sm text-error-700">
                          {task.error}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* 操作按钮 */}
                  <div className="flex items-center space-x-2 ml-4">
                    <button className="btn btn-ghost btn-sm">
                      查看详情
                    </button>
                    {getActionButtons(task)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* 分页 */}
        {tasksData && tasksData.total > filters.page_size && (
          <div className="flex items-center justify-between mt-8">
            <div className="text-sm text-gray-500">
              显示 {(filters.page - 1) * filters.page_size + 1} - {Math.min(filters.page * filters.page_size, tasksData.total)} 
              ，共 {tasksData.total} 个任务
            </div>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => handleFilterChange('page', filters.page - 1)}
                disabled={filters.page <= 1}
                className="btn btn-ghost btn-sm"
              >
                上一页
              </button>
              <span className="text-sm text-gray-500">
                第 {filters.page} 页
              </span>
              <button
                onClick={() => handleFilterChange('page', filters.page + 1)}
                disabled={filters.page * filters.page_size >= tasksData.total}
                className="btn btn-ghost btn-sm"
              >
                下一页
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}