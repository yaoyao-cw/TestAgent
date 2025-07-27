import React, { useState, useEffect } from 'react'
import { 
  AlertTriangle, 
  AlertCircle, 
  Info, 
  CheckCircle, 
  X, 
  Bell,
  BellOff,
  Filter,
  Clock
} from 'lucide-react'
import { cn, formatRelativeTime } from '@/lib/utils'
import toast from 'react-hot-toast'

export interface Alert {
  id: string
  type: 'error' | 'warning' | 'info' | 'success'
  title: string
  message: string
  timestamp: string
  source?: string
  acknowledged?: boolean
  auto_dismiss?: boolean
  dismiss_after?: number // seconds
}

interface AlertSystemProps {
  alerts: Alert[]
  onAcknowledge?: (alertId: string) => void
  onDismiss?: (alertId: string) => void
  maxVisible?: number
  className?: string
}

interface AlertItemProps {
  alert: Alert
  onAcknowledge?: (alertId: string) => void
  onDismiss?: (alertId: string) => void
}

function AlertItem({ alert, onAcknowledge, onDismiss }: AlertItemProps) {
  const [isVisible, setIsVisible] = useState(true)

  useEffect(() => {
    if (alert.auto_dismiss && alert.dismiss_after) {
      const timer = setTimeout(() => {
        setIsVisible(false)
        setTimeout(() => onDismiss?.(alert.id), 300) // 等待动画完成
      }, alert.dismiss_after * 1000)

      return () => clearTimeout(timer)
    }
  }, [alert, onDismiss])

  const getAlertIcon = (type: string) => {
    switch (type) {
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-600" />
      case 'warning':
        return <AlertTriangle className="w-5 h-5 text-yellow-600" />
      case 'success':
        return <CheckCircle className="w-5 h-5 text-green-600" />
      default:
        return <Info className="w-5 h-5 text-blue-600" />
    }
  }

  const getAlertColor = (type: string) => {
    switch (type) {
      case 'error':
        return 'border-red-200 bg-red-50'
      case 'warning':
        return 'border-yellow-200 bg-yellow-50'
      case 'success':
        return 'border-green-200 bg-green-50'
      default:
        return 'border-blue-200 bg-blue-50'
    }
  }

  const handleAcknowledge = () => {
    onAcknowledge?.(alert.id)
  }

  const handleDismiss = () => {
    setIsVisible(false)
    setTimeout(() => onDismiss?.(alert.id), 300)
  }

  if (!isVisible) {
    return null
  }

  return (
    <div className={cn(
      "border rounded-lg p-4 transition-all duration-300 transform",
      getAlertColor(alert.type),
      alert.acknowledged && "opacity-60",
      isVisible ? "translate-x-0 opacity-100" : "translate-x-full opacity-0"
    )}>
      <div className="flex items-start space-x-3">
        <div className="flex-shrink-0">
          {getAlertIcon(alert.type)}
        </div>
        
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium text-gray-900">
              {alert.title}
            </h4>
            <div className="flex items-center space-x-2">
              <span className="text-xs text-gray-500">
                {formatRelativeTime(alert.timestamp)}
              </span>
              <button
                onClick={handleDismiss}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
          
          <p className="text-sm text-gray-700 mt-1">
            {alert.message}
          </p>
          
          {alert.source && (
            <div className="flex items-center space-x-2 mt-2">
              <span className="text-xs text-gray-500">来源:</span>
              <span className="text-xs font-mono bg-gray-100 px-2 py-1 rounded">
                {alert.source}
              </span>
            </div>
          )}
          
          {!alert.acknowledged && onAcknowledge && (
            <div className="mt-3">
              <button
                onClick={handleAcknowledge}
                className="text-xs bg-white border border-gray-300 rounded px-3 py-1 hover:bg-gray-50 transition-colors"
              >
                确认
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export function AlertSystem({ 
  alerts, 
  onAcknowledge, 
  onDismiss, 
  maxVisible = 10,
  className 
}: AlertSystemProps) {
  const [filter, setFilter] = useState<'all' | 'error' | 'warning' | 'info' | 'success'>('all')
  const [showAcknowledged, setShowAcknowledged] = useState(false)
  const [isMuted, setIsMuted] = useState(false)

  // 过滤告警
  const filteredAlerts = alerts
    .filter(alert => filter === 'all' || alert.type === filter)
    .filter(alert => showAcknowledged || !alert.acknowledged)
    .slice(0, maxVisible)

  // 统计不同类型的告警数量
  const alertCounts = alerts.reduce((counts, alert) => {
    if (!alert.acknowledged) {
      counts[alert.type] = (counts[alert.type] || 0) + 1
    }
    return counts
  }, {} as Record<string, number>)

  // 播放告警声音
  useEffect(() => {
    if (!isMuted && alerts.length > 0) {
      const newAlerts = alerts.filter(alert => 
        !alert.acknowledged && 
        (alert.type === 'error' || alert.type === 'warning')
      )
      
      if (newAlerts.length > 0) {
        // 这里可以播放告警声音
        // new Audio('/alert-sound.mp3').play().catch(() => {})
        
        // 显示浏览器通知
        if ('Notification' in window && Notification.permission === 'granted') {
          new Notification('TestAgent 告警', {
            body: `${newAlerts.length} 个新告警需要处理`,
            icon: '/favicon.ico'
          })
        }
      }
    }
  }, [alerts, isMuted])

  const getFilterButtonClass = (filterType: string) => {
    return cn(
      "px-3 py-1 text-xs rounded-full transition-colors",
      filter === filterType
        ? "bg-primary-100 text-primary-700 border border-primary-200"
        : "bg-gray-100 text-gray-600 hover:bg-gray-200"
    )
  }

  if (alerts.length === 0) {
    return (
      <div className={cn("bg-white border border-gray-200 rounded-lg p-6", className)}>
        <div className="text-center">
          <CheckCircle className="w-8 h-8 text-green-500 mx-auto mb-2" />
          <p className="text-gray-500">系统运行正常，暂无告警</p>
        </div>
      </div>
    )
  }

  return (
    <div className={cn("bg-white border border-gray-200 rounded-lg", className)}>
      {/* 头部控制栏 */}
      <div className="border-b border-gray-200 p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center space-x-3">
            <h2 className="text-lg font-medium text-gray-900">系统告警</h2>
            <div className="flex items-center space-x-2">
              {alertCounts.error > 0 && (
                <span className="bg-red-100 text-red-800 text-xs px-2 py-1 rounded-full">
                  {alertCounts.error} 错误
                </span>
              )}
              {alertCounts.warning > 0 && (
                <span className="bg-yellow-100 text-yellow-800 text-xs px-2 py-1 rounded-full">
                  {alertCounts.warning} 警告
                </span>
              )}
            </div>
          </div>
          
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsMuted(!isMuted)}
              className={cn(
                "p-2 rounded-lg transition-colors",
                isMuted 
                  ? "bg-gray-100 text-gray-600" 
                  : "bg-blue-100 text-blue-600"
              )}
              title={isMuted ? "开启通知" : "静音通知"}
            >
              {isMuted ? <BellOff className="w-4 h-4" /> : <Bell className="w-4 h-4" />}
            </button>
          </div>
        </div>

        {/* 过滤器 */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Filter className="w-4 h-4 text-gray-500" />
            <div className="flex items-center space-x-1">
              <button
                onClick={() => setFilter('all')}
                className={getFilterButtonClass('all')}
              >
                全部 ({alerts.length})
              </button>
              <button
                onClick={() => setFilter('error')}
                className={getFilterButtonClass('error')}
              >
                错误 ({alertCounts.error || 0})
              </button>
              <button
                onClick={() => setFilter('warning')}
                className={getFilterButtonClass('warning')}
              >
                警告 ({alertCounts.warning || 0})
              </button>
              <button
                onClick={() => setFilter('info')}
                className={getFilterButtonClass('info')}
              >
                信息 ({alertCounts.info || 0})
              </button>
            </div>
          </div>

          <label className="flex items-center space-x-2 text-sm text-gray-600">
            <input
              type="checkbox"
              checked={showAcknowledged}
              onChange={(e) => setShowAcknowledged(e.target.checked)}
              className="rounded border-gray-300"
            />
            <span>显示已确认</span>
          </label>
        </div>
      </div>

      {/* 告警列表 */}
      <div className="p-4 max-h-96 overflow-y-auto">
        {filteredAlerts.length === 0 ? (
          <div className="text-center py-8">
            <Info className="w-8 h-8 text-gray-400 mx-auto mb-2" />
            <p className="text-gray-500">没有符合条件的告警</p>
          </div>
        ) : (
          <div className="space-y-3">
            {filteredAlerts.map((alert) => (
              <AlertItem
                key={alert.id}
                alert={alert}
                onAcknowledge={onAcknowledge}
                onDismiss={onDismiss}
              />
            ))}
          </div>
        )}
      </div>

      {/* 底部统计 */}
      {alerts.length > maxVisible && (
        <div className="border-t border-gray-200 px-4 py-2 bg-gray-50">
          <p className="text-xs text-gray-500 text-center">
            显示 {Math.min(maxVisible, filteredAlerts.length)} / {alerts.length} 个告警
          </p>
        </div>
      )}
    </div>
  )
}