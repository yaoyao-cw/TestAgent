import React from 'react'
import { 
  Clock, 
  User, 
  FileText, 
  AlertCircle, 
  CheckCircle, 
  Play, 
  Square,
  Edit,
  Zap
} from 'lucide-react'
import { cn, formatDate, formatDuration, formatRelativeTime } from '@/lib/utils'
import type { TimelineEvent, TaskTimeline } from '@/types'

interface TimelineProps {
  timeline: TaskTimeline
  className?: string
}

interface TimelineEventProps {
  event: TimelineEvent
  isLast: boolean
}

function TimelineEventItem({ event, isLast }: TimelineEventProps) {
  const getEventIcon = (eventType: string) => {
    switch (eventType) {
      case 'agent_start':
        return <Play className="w-4 h-4 text-blue-600" />
      case 'agent_complete':
        return <CheckCircle className="w-4 h-4 text-green-600" />
      case 'file_created':
        return <FileText className="w-4 h-4 text-purple-600" />
      case 'file_updated':
        return <Edit className="w-4 h-4 text-orange-600" />
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-600" />
      case 'status_change':
        return <Zap className="w-4 h-4 text-yellow-600" />
      default:
        return <Clock className="w-4 h-4 text-gray-600" />
    }
  }

  const getEventColor = (eventType: string) => {
    switch (eventType) {
      case 'agent_start':
        return 'border-blue-200 bg-blue-50'
      case 'agent_complete':
        return 'border-green-200 bg-green-50'
      case 'file_created':
        return 'border-purple-200 bg-purple-50'
      case 'file_updated':
        return 'border-orange-200 bg-orange-50'
      case 'error':
        return 'border-red-200 bg-red-50'
      case 'status_change':
        return 'border-yellow-200 bg-yellow-50'
      default:
        return 'border-gray-200 bg-gray-50'
    }
  }

  const getEventTitle = (event: TimelineEvent) => {
    switch (event.event_type) {
      case 'agent_start':
        return `${event.agent_name} 开始执行`
      case 'agent_complete':
        return `${event.agent_name} 执行完成`
      case 'file_created':
        return '创建文件'
      case 'file_updated':
        return '更新文件'
      case 'error':
        return '执行错误'
      case 'status_change':
        return '状态变更'
      default:
        return event.description
    }
  }

  return (
    <div className="relative flex items-start space-x-3">
      {/* 时间线连接线 */}
      {!isLast && (
        <div className="absolute left-6 top-8 w-0.5 h-full bg-gray-200" />
      )}
      
      {/* 事件图标 */}
      <div className={cn(
        "flex items-center justify-center w-12 h-12 rounded-full border-2 bg-white",
        getEventColor(event.event_type)
      )}>
        {getEventIcon(event.event_type)}
      </div>

      {/* 事件内容 */}
      <div className="flex-1 min-w-0 pb-6">
        <div className="flex items-center justify-between">
          <div>
            <h4 className="text-sm font-medium text-gray-900">
              {getEventTitle(event)}
            </h4>
            <p className="text-sm text-gray-600 mt-1">
              {event.description}
            </p>
          </div>
          <div className="text-xs text-gray-500 ml-4">
            {formatRelativeTime(event.timestamp)}
          </div>
        </div>

        {/* 事件详细信息 */}
        <div className="mt-2 space-y-2">
          {event.file_path && (
            <div className="flex items-center space-x-2 text-xs text-gray-600">
              <FileText className="w-3 h-3" />
              <span className="font-mono">{event.file_path}</span>
            </div>
          )}

          {event.duration && (
            <div className="flex items-center space-x-2 text-xs text-gray-600">
              <Clock className="w-3 h-3" />
              <span>耗时: {formatDuration(event.duration)}</span>
            </div>
          )}

          {event.status && (
            <div className="flex items-center space-x-2 text-xs text-gray-600">
              <Square className="w-3 h-3" />
              <span>状态: {event.status}</span>
            </div>
          )}

          {event.details && (
            <div className="mt-2 p-2 bg-gray-50 rounded text-xs text-gray-700">
              <pre className="whitespace-pre-wrap font-mono">
                {typeof event.details === 'string' 
                  ? event.details 
                  : JSON.stringify(event.details, null, 2)
                }
              </pre>
            </div>
          )}
        </div>

        {/* 时间戳 */}
        <div className="mt-2 text-xs text-gray-400">
          {formatDate(event.timestamp)}
        </div>
      </div>
    </div>
  )
}

export function Timeline({ timeline, className }: TimelineProps) {
  if (!timeline.events || timeline.events.length === 0) {
    return (
      <div className={cn("p-6 text-center text-gray-500", className)}>
        <Clock className="w-8 h-8 mx-auto mb-2 text-gray-400" />
        <p>暂无执行记录</p>
      </div>
    )
  }

  return (
    <div className={cn("bg-white border border-gray-200 rounded-lg", className)}>
      {/* 时间线头部 */}
      <div className="border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-medium text-gray-900">执行时间线</h3>
            <p className="text-sm text-gray-600 mt-1">
              任务执行的详细轨迹和事件记录
            </p>
          </div>
          <div className="text-sm text-gray-500">
            <div>开始时间: {formatDate(timeline.start_time)}</div>
            {timeline.end_time && (
              <div>结束时间: {formatDate(timeline.end_time)}</div>
            )}
            {timeline.total_duration && (
              <div>总耗时: {formatDuration(timeline.total_duration)}</div>
            )}
          </div>
        </div>
      </div>

      {/* 时间线内容 */}
      <div className="p-6">
        <div className="space-y-0">
          {timeline.events.map((event, index) => (
            <TimelineEventItem
              key={event.id}
              event={event}
              isLast={index === timeline.events.length - 1}
            />
          ))}
        </div>
      </div>

      {/* 时间线统计 */}
      <div className="border-t border-gray-200 px-6 py-4 bg-gray-50">
        <div className="flex items-center justify-between text-sm text-gray-600">
          <span>共 {timeline.total_events} 个事件</span>
          {timeline.total_duration && (
            <span>总执行时间: {formatDuration(timeline.total_duration)}</span>
          )}
        </div>
      </div>
    </div>
  )
}